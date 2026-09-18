#!/usr/bin/env python3
"""Mix cue-sheet narration into a video while copying the video stream."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def find_ffmpeg(explicit: str | None) -> str:
    candidate = explicit or shutil.which("ffmpeg")
    if not candidate:
        raise RuntimeError("ffmpeg not found; pass --ffmpeg with an executable path")
    return candidate


def probe(ffmpeg: str, path: Path) -> tuple[float, bool, bool]:
    run = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    text = run.stderr + run.stdout
    match = DURATION_RE.search(text)
    if not match:
        raise RuntimeError(f"cannot read duration: {path}")
    duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    return duration, "Video:" in text, "Audio:" in text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue_sheet", type=Path, help="UTF-8 JSON cue sheet")
    parser.add_argument("--ffmpeg", help="ffmpeg executable; defaults to PATH")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.cue_sheet.read_text(encoding="utf-8-sig"))
    video = Path(data["video"])
    narration = Path(data["narration"])
    output = Path(data["output"])
    cues = data.get("cues", [])
    duck = float(data.get("duck_gain", 0.55))
    timeline = data.get("dialogue_timeline")
    if not video.is_file() or not narration.is_file():
        raise FileNotFoundError("video or narration file does not exist")
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output exists; refusing to overwrite: {output}")
    if not cues:
        raise ValueError("cue sheet has no cues")
    if not 0.0 <= duck <= 1.0:
        raise ValueError("duck_gain must be between 0 and 1")
    if not isinstance(timeline, dict) or timeline.get("basis") != "actual_video_verified":
        raise ValueError(
            "dialogue_timeline.basis must be 'actual_video_verified'; "
            "predicted prompt timings or waveform-only estimates are not accepted"
        )

    ffmpeg = find_ffmpeg(args.ffmpeg)
    video_duration, has_video, has_audio = probe(ffmpeg, video)
    narration_duration, _, narration_audio = probe(ffmpeg, narration)
    if not has_video or not has_audio or not narration_audio:
        raise RuntimeError("expected video+audio in input video and audio in narration")

    guard = float(timeline.get("guard_seconds", 0.35))
    if guard < 0 or guard > 2.0:
        raise ValueError("dialogue_timeline.guard_seconds must be between 0 and 2 seconds")
    raw_dialogue = timeline.get("intervals")
    if not isinstance(raw_dialogue, list):
        raise ValueError("dialogue_timeline.intervals must be a list; use [] only after verifying no dialogue")

    protected_dialogue: list[dict[str, float | str]] = []
    last_dialogue_end = -1.0
    for index, interval in enumerate(raw_dialogue):
        if not isinstance(interval, dict) or "start" not in interval or "end" not in interval:
            raise ValueError(f"dialogue interval {index}: start and end are required")
        start = float(interval["start"])
        end = float(interval["end"])
        if start < 0 or end <= start or end > video_duration + 0.05:
            raise ValueError(f"dialogue interval {index}: invalid or outside video duration")
        if start < last_dialogue_end - 0.001:
            raise ValueError(f"dialogue interval {index}: intervals overlap or are out of order")
        last_dialogue_end = end
        protected_dialogue.append({
            "start": max(0.0, start - guard),
            "end": min(video_duration, end + guard),
            "speaker": str(interval.get("speaker", "unknown")),
        })

    normalized: list[dict[str, float | str]] = []
    last_target_end = -1.0
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict):
            raise ValueError(f"cue {index}: cue must be an object")
        cue_id = str(cue.get("cue_id", "")).strip()
        narration_text = str(cue.get("narration_text", "")).strip()
        if not cue_id or not narration_text:
            raise ValueError(f"cue {index}: cue_id and narration_text are required for audit")
        values = {key: float(cue[key]) for key in ("source_start", "source_end", "target_start", "target_end")}
        if values["source_start"] < 0 or values["source_end"] <= values["source_start"]:
            raise ValueError(f"cue {index}: invalid source range")
        if values["target_start"] < 0 or values["target_end"] <= values["target_start"]:
            raise ValueError(f"cue {index}: invalid target range")
        if values["source_end"] > narration_duration + 0.05 or values["target_end"] > video_duration + 0.05:
            raise ValueError(f"cue {index}: range exceeds source media")
        source_len = values["source_end"] - values["source_start"]
        target_len = values["target_end"] - values["target_start"]
        if source_len > target_len + 0.03:
            raise ValueError(f"cue {index}: narration is {source_len - target_len:.3f}s too long")
        if values["target_start"] < last_target_end - 0.001:
            raise ValueError(f"cue {index}: target windows overlap or are out of order")
        for protected in protected_dialogue:
            if values["target_start"] < float(protected["end"]) and values["target_end"] > float(protected["start"]):
                raise ValueError(
                    f"cue {index} ({cue_id}) overlaps protected dialogue "
                    f"{float(protected['start']):.3f}-{float(protected['end']):.3f}s "
                    f"(speaker={protected['speaker']}); refusing to mix"
                )
        last_target_end = values["target_end"]
        values["cue_id"] = cue_id
        normalized.append(values)

    duck_expr = "+".join(
        f"between(t,{cue['target_start']:.3f},{cue['target_end']:.3f})" for cue in normalized
    )
    filters = [f"[0:a]aresample=48000,volume='if(gt({duck_expr},0),{duck:.3f},1)'[base]"]
    narration_labels: list[str] = []
    source_labels = [f"nsrc{index}" for index in range(len(normalized))]
    split_outputs = "".join(f"[{label}]" for label in source_labels)
    if len(normalized) == 1:
        filters.append(f"[1:a]aresample=48000{split_outputs}")
    else:
        filters.append(f"[1:a]aresample=48000,asplit={len(normalized)}{split_outputs}")
    for index, cue in enumerate(normalized):
        length = cue["source_end"] - cue["source_start"]
        fade = min(0.03, length / 4)
        delay_ms = round(cue["target_start"] * 1000)
        label = f"n{index}"
        filters.append(
            f"[{source_labels[index]}]atrim=start={cue['source_start']:.3f}:end={cue['source_end']:.3f},"
            f"asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={max(0.0, length-fade):.3f}:d={fade:.3f},"
            f"adelay={delay_ms}:all=1[{label}]"
        )
        narration_labels.append(f"[{label}]")
    inputs = "[base]" + "".join(narration_labels)
    filters.append(f"{inputs}amix=inputs={1 + len(normalized)}:duration=first:normalize=0,alimiter=limit=0.97[aout]")

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-hide_banner", "-y" if args.overwrite else "-n", "-i", str(video), "-i", str(narration),
        "-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-shortest", str(output),
    ]
    run = subprocess.run(command)
    if run.returncode:
        return run.returncode
    print(str(output.resolve()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
