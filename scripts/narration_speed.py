#!/usr/bin/env python3
"""Estimate whether narration fits a real dialogue-free video window."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def estimate_base_seconds(text: str, language: str) -> tuple[float, str, int]:
    chinese = re.findall(r"[\u3400-\u9fff]", text)
    words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", text)
    if language == "auto":
        language = "zh" if len(chinese) > len(words) else "en"
    pauses = 0.32 * len(re.findall(r"[。！？!?]", text)) + 0.14 * len(re.findall(r"[，,；;：:]", text))
    if language == "zh":
        units = len(chinese)
        seconds = units / 3.6 + pauses
    else:
        units = len(words)
        seconds = units / 2.5 + pauses
    return max(seconds, 0.1), language, units


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--text-file", type=Path)
    parser.add_argument("--available-seconds", type=float, required=True)
    parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto")
    parser.add_argument("--default-speed", type=float, default=1.1)
    parser.add_argument("--min-speed", type=float, default=0.95)
    parser.add_argument("--max-speed", type=float, default=1.25)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    if args.available_seconds <= 0 or not (0 < args.min_speed <= args.default_speed <= args.max_speed):
        parser.error("invalid duration or speed range")
    text = args.text if args.text is not None else args.text_file.read_text(encoding="utf-8-sig")
    base, language, units = estimate_base_seconds(text.strip(), args.language)
    required = base / args.available_seconds
    recommended = args.default_speed if base / args.default_speed <= args.available_seconds else required
    feasible = recommended <= args.max_speed
    recommended = round(min(max(recommended, args.min_speed), args.max_speed), 2)
    predicted = base / recommended
    result = {
        "language": language,
        "unit_count": units,
        "available_seconds": round(args.available_seconds, 3),
        "estimated_seconds_at_1_0": round(base, 3),
        "required_speed": round(required, 3),
        "recommended_speed": recommended,
        "predicted_seconds": round(predicted, 3),
        "feasible": feasible,
        "shortfall_seconds_at_max_speed": round(max(0.0, base / args.max_speed - args.available_seconds), 3),
        "note": "Estimate only; measure the generated WAV before mixing.",
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    return 0 if feasible else 2


if __name__ == "__main__":
    raise SystemExit(main())
