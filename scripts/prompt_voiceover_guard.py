#!/usr/bin/env python3
"""Lint a V4.2 prompt for spoken-narration risks without modifying it."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


RISKY = [
    re.compile(r"(?:男声|女声)\s*画外音", re.IGNORECASE),
    re.compile(r"旁白\s*(?:朗读|念出|发声)", re.IGNORECASE),
    re.compile(r"(?:使用|生成|加入|播放|出现).{0,12}(?:旁白声音|画外音|内心声音|解说声音|TTS)", re.IGNORECASE),
    re.compile(r"voice[- ]?over\s+narration", re.IGNORECASE),
    re.compile(r"\bvoiceover\b", re.IGNORECASE),
    re.compile(r"spoken\s+narration", re.IGNORECASE),
    re.compile(r"narrator(?:'s)?\s+voice", re.IGNORECASE),
    re.compile(r"(?:generate|add|play|include)\s+(?:a\s+)?(?:narration|narrator|tts)", re.IGNORECASE),
]
NEGATION = re.compile(
    r"不生成|不得|禁止|不要|绝对无|无旁白|不朗读|不是音频|"
    r"(?:do\s+not|don't|must\s+not|no)\s+(?:generate|add|play|include|spoken|voiceover|narration)",
    re.IGNORECASE,
)


def lint(text: str) -> list[str]:
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if NEGATION.search(line):
            continue
        for pattern in RISKY:
            if pattern.search(line):
                errors.append(f"line {number}: risky spoken-narration instruction: {line.strip()}")
    if len(text) > 15000:
        errors.append(f"prompt length {len(text)} exceeds the 15000-character platform limit")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 V4.2 prompt text file")
    parser.add_argument("--check-only", action="store_true", help="retained for CLI compatibility")
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8-sig")
    errors = lint(source)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
