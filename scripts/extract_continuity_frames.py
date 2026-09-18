#!/usr/bin/env python3
"""Extract timestamped still-frame candidates from the end of a video."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def resolve_binary(explicit: str | None, fallback: str) -> str:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"binary not found: {path}")
        return str(path)
    found = shutil.which(fallback)
    if not found:
        raise FileNotFoundError(f"{fallback} was not found in PATH; pass --{fallback}")
    return found


def probe_duration(ffprobe: str, video: Path) -> float:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError(f"invalid video duration: {duration}")
    return duration


def timestamps(duration: float, window: float, count: int, exclude_tail: float) -> list[float]:
    end = max(0.0, duration - exclude_tail)
    start = max(0.0, end - window)
    if count == 1 or end <= start:
        return [end]
    step = (end - start) / (count - 1)
    return [start + step * index for index in range(count)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="source video")
    parser.add_argument("output_dir", type=Path, help="directory for PNG candidates")
    parser.add_argument("--window", type=float, default=1.2, help="seconds sampled before the excluded tail")
    parser.add_argument("--count", type=int, default=6, help="number of evenly spaced candidates")
    parser.add_argument("--exclude-tail", type=float, default=0.05, help="seconds ignored at file end")
    parser.add_argument("--prefix", default="tail-candidate", help="output filename prefix")
    parser.add_argument("--ffmpeg", help="absolute path to ffmpeg")
    parser.add_argument("--ffprobe", help="absolute path to ffprobe")
    args = parser.parse_args()

    video = args.video.expanduser().resolve()
    if not video.is_file():
        raise FileNotFoundError(f"video not found: {video}")
    if args.window <= 0 or args.count <= 0 or args.exclude_tail < 0:
        raise ValueError("window/count must be positive and exclude-tail cannot be negative")

    ffmpeg = resolve_binary(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_binary(args.ffprobe, "ffprobe")
    duration = probe_duration(ffprobe, video)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for index, timestamp in enumerate(
        timestamps(duration, args.window, args.count, args.exclude_tail), start=1
    ):
        filename = f"{args.prefix}-{index:02d}-{timestamp:.3f}s.png"
        output = output_dir / filename
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.6f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-y",
            str(output),
        ]
        subprocess.run(command, check=True)
        records.append({"index": index, "timestamp_seconds": round(timestamp, 6), "file": str(output)})

    print(
        json.dumps(
            {
                "source_video": str(video),
                "duration_seconds": round(duration, 6),
                "window_seconds": args.window,
                "exclude_tail_seconds": args.exclude_tail,
                "candidates": records,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
