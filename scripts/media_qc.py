#!/usr/bin/env python3
"""Run technical media QC with FFmpeg and emit a JSON report."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
VIDEO_RE = re.compile(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})(?:[^\n]*?([\d.]+)\s*fps)?")


def find_ffmpeg(explicit: str | None) -> str:
    value = explicit or shutil.which("ffmpeg")
    if not value:
        raise RuntimeError("ffmpeg not found; pass --ffmpeg")
    return value


def metadata(ffmpeg: str, path: Path) -> dict:
    run = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    text = run.stderr + run.stdout
    duration = DURATION_RE.search(text)
    video = VIDEO_RE.search(text)
    return {
        "duration": None if not duration else round(int(duration.group(1)) * 3600 + int(duration.group(2)) * 60 + float(duration.group(3)), 3),
        "width": None if not video else int(video.group(1)),
        "height": None if not video else int(video.group(2)),
        "fps": None if not video or not video.group(3) else float(video.group(3)),
        "has_video": "Video:" in text,
        "has_audio": "Audio:" in text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("--reference-video", type=Path)
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    if not args.media.is_file() or args.media.stat().st_size == 0:
        raise FileNotFoundError("media file is missing or empty")
    ffmpeg = find_ffmpeg(args.ffmpeg)
    meta = metadata(ffmpeg, args.media)
    issues: list[dict] = []
    if not meta["has_video"]:
        issues.append({"category": "missing_video", "severity": "FAIL"})
    if not meta["has_audio"]:
        issues.append({"category": "missing_audio", "severity": "FAIL"})
    if args.expected_width and meta["width"] != args.expected_width:
        issues.append({"category": "width_mismatch", "severity": "FAIL", "actual": meta["width"]})
    if args.expected_height and meta["height"] != args.expected_height:
        issues.append({"category": "height_mismatch", "severity": "FAIL", "actual": meta["height"]})

    filter_expr = "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-50dB:d=1.5"
    audio_expr = "silencedetect=noise=-50dB:d=1.0,astats=metadata=1:reset=1"
    decode = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "info", "-i", str(args.media), "-vf", filter_expr,
         "-af", audio_expr, "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    log = decode.stderr + decode.stdout
    if decode.returncode:
        issues.append({"category": "decode_error", "severity": "FAIL", "detail": log[-1000:]})
    black = re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)", log)
    freeze_starts = re.findall(r"freeze_start:\s*([\d.]+)", log)
    freeze_ends = re.findall(r"freeze_end:\s*([\d.]+)\s*\|\s*freeze_duration:\s*([\d.]+)", log)
    if black:
        issues.append({"category": "black_segments", "severity": "REVIEW_REQUIRED", "segments": black})
    if freeze_starts or freeze_ends:
        issues.append({"category": "freeze_segments", "severity": "REVIEW_REQUIRED", "starts": freeze_starts, "ends": freeze_ends})
    silence_starts = re.findall(r"silence_start:\s*([\d.]+)", log)
    silence_ends = re.findall(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", log)
    if silence_starts or silence_ends:
        issues.append({"category": "audio_silence", "severity": "REVIEW_REQUIRED", "starts": silence_starts, "ends": silence_ends})
    peaks = [float(value) for value in re.findall(r"Peak level dB:\s*(-?[\d.]+)", log)]
    if peaks and max(peaks) >= -0.1:
        issues.append({"category": "possible_audio_clipping", "severity": "REVIEW_REQUIRED", "peak_db": max(peaks)})

    reference = None
    if args.reference_video:
        reference = metadata(ffmpeg, args.reference_video)
        for key, tolerance in (("duration", 0.06), ("fps", 0.02)):
            if meta[key] is not None and reference[key] is not None and abs(meta[key] - reference[key]) > tolerance:
                issues.append({"category": f"{key}_changed", "severity": "FAIL", "actual": meta[key], "reference": reference[key]})
        for key in ("width", "height"):
            if meta[key] != reference[key]:
                issues.append({"category": f"{key}_changed", "severity": "FAIL", "actual": meta[key], "reference": reference[key]})

    status = "FAIL" if any(x["severity"] == "FAIL" for x in issues) else "REVIEW_REQUIRED" if issues else "PASS"
    report = {"file": str(args.media.resolve()), "technical_status": status, "metadata": meta, "reference": reference, "issues": issues}
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    return 2 if status == "FAIL" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
