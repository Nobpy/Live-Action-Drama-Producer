#!/usr/bin/env python3
"""Validate V4 storyboard source-word budgets before prompt generation.

Input JSON:
{
  "shots": [
    {"shot": "1-1", "duration_seconds": 30, "source_text": "..."},
    {"shot": "1-2", "duration_seconds": 18, "source_text": "..."}
  ]
}

For word-delimited scripts, source_text must contain story text only: original
dialogue, narration and meaningful action/prose. Do not include scene headings,
speaker labels, timecodes, asset names or director instructions. For a project
using an externally confirmed tokenizer, provide coverage_words on every shot.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


WORD_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
FULL_DURATION = 30.0
MIN_DURATION = 4.0
MIN_WORDS = 70
MAX_WORDS = 90
MAX_SPREAD = 10
EPSILON = 0.001


def count_words(text: str) -> int:
    """Count lexical words in a word-delimited source range."""
    return len(WORD_RE.findall(text))


def is_full(duration: float) -> bool:
    return abs(duration - FULL_DURATION) <= EPSILON


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    shots = payload.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("input must contain a non-empty 'shots' array")

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for index, raw in enumerate(shots):
        if not isinstance(raw, dict):
            errors.append(f"shot {index + 1}: entry must be an object")
            continue

        shot_id = str(raw.get("shot", index + 1))
        try:
            duration = float(raw["duration_seconds"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{shot_id}: duration_seconds must be a number")
            continue

        if "coverage_words" in raw:
            try:
                words = int(raw["coverage_words"])
            except (TypeError, ValueError):
                errors.append(f"{shot_id}: coverage_words must be an integer")
                continue
            count_source = "external-confirmed-tokenizer"
        else:
            source_text = raw.get("source_text")
            if not isinstance(source_text, str) or not source_text.strip():
                errors.append(
                    f"{shot_id}: provide non-empty source_text or coverage_words"
                )
                continue
            words = count_words(source_text)
            count_source = "built-in-word-delimited"

        row_errors: list[str] = []
        if duration < MIN_DURATION - EPSILON or duration > FULL_DURATION + EPSILON:
            row_errors.append("duration must be within 4–30 seconds")

        is_last = index == len(shots) - 1
        if not is_last and not is_full(duration):
            row_errors.append("every shot before the final shot must be 30 seconds")

        if is_full(duration) and not MIN_WORDS <= words <= MAX_WORDS:
            row_errors.append("a 30-second shot must cover 70–90 source words")

        if is_last and not is_full(duration) and words > MAX_WORDS:
            row_errors.append("a shorter final shot cannot exceed 90 source words")
        elif is_last and not is_full(duration) and words >= MIN_WORDS:
            warnings.append(
                f"{shot_id}: shorter final shot has {words} words; confirm its actual performance capacity cannot naturally sustain 30 seconds"
            )

        if words <= 0:
            row_errors.append("coverage_words must be greater than zero")

        rows.append(
            {
                "shot": shot_id,
                "duration_seconds": duration,
                "coverage_words": words,
                "count_source": count_source,
                "status": "PASS" if not row_errors else "FAIL",
                "errors": row_errors,
            }
        )
        errors.extend(f"{shot_id}: {message}" for message in row_errors)

    full_counts = [row["coverage_words"] for row in rows if is_full(row["duration_seconds"])]
    spread = max(full_counts) - min(full_counts) if full_counts else 0
    if len(full_counts) > 1 and spread > MAX_SPREAD:
        errors.append(
            f"full-shot word-count spread is {spread}; maximum allowed is {MAX_SPREAD}"
        )

    average = sum(full_counts) / len(full_counts) if full_counts else None
    for row in rows:
        row["full_shot_average_deviation"] = (
            round(row["coverage_words"] - average, 2) if average is not None else None
        )

    return {
        "status": "SCRIPT_SPLIT_PREFLIGHT_PASS" if not errors else "SCRIPT_SPLIT_CONSTRAINT_BLOCKED",
        "full_shot_average_words": round(average, 2) if average is not None else None,
        "full_shot_word_spread": spread,
        "rows": rows,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate 70–90-word V4 storyboard budgets and final-shot duration rules."
    )
    parser.add_argument("input_json", type=Path, help="UTF-8 JSON file containing shots")
    parser.add_argument("--output-json", type=Path, help="optional path for the audit result")
    args = parser.parse_args()

    try:
        payload = json.loads(args.input_json.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("top-level JSON value must be an object")
        result = validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output_json:
        args.output_json.write_text(rendered + "\n", encoding="utf-8")

    return 0 if result["status"] == "SCRIPT_SPLIT_PREFLIGHT_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
