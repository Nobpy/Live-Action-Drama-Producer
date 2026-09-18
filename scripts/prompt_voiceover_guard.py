#!/usr/bin/env python3
"""Convert a V4 storyboard prompt into a platform-safe silent-narration prompt."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


HEADER = """【音频硬约束｜最高优先级】
音频白名单：只允许角色现场开口对白、环境声、动作音效。
音频黑名单：不得生成旁白声音、内心独白声音、画外解说、背景音乐；不得生成任何字幕或屏幕文字。
文中所有“旁白占位”只控制画面、表演、停顿和时长，角色不朗读、不对口型，音轨保持无旁白。
"""

NARRATION_HEADING = re.compile(
    r"^(?P<indent>\s*)(?:【\s*)?(?:旁白|内心独白|画外解说)(?:\s*[（(][^）)]*[）)])?(?:\s*】)?\s*[：:]",
    re.IGNORECASE,
)
RISKY = [
    re.compile(r"(?:男声|女声)\s*画外音", re.IGNORECASE),
    re.compile(r"旁白\s*(?:朗读|念出|发声)", re.IGNORECASE),
    re.compile(r"voice[- ]?over\s+narration", re.IGNORECASE),
    re.compile(r"spoken\s+narration", re.IGNORECASE),
]
NEGATION = re.compile(r"不生成|不得|禁止|不要|无旁白|不朗读|not\s+(?:generate|spoken)", re.IGNORECASE)


def adapt(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        line = NARRATION_HEADING.sub(
            lambda m: f"{m.group('indent')}旁白占位（不生成声音，不朗读，不对口型）：",
            line,
            count=1,
        )
        out.append(line)
    body = "\n".join(out).strip()
    return f"{HEADER.strip()}\n\n{body}\n"


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
    parser.add_argument("input", type=Path, help="UTF-8 V4 prompt text file")
    parser.add_argument("output", type=Path, nargs="?", help="platform-safe output file")
    parser.add_argument("--check-only", action="store_true", help="lint without writing")
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8-sig")
    result = adapt(source)
    errors = lint(result)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    if not args.check_only:
        if args.output is None:
            parser.error("output is required unless --check-only is used")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
        print(str(args.output.resolve()))
    else:
        print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
