#!/usr/bin/env python3
"""Validate the only supported V4.2 example-structured director prompt."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_PATTERNS = {
    "storyboard_title": r"^\s*分镜\s*\d+\s*[（(]\s*\d+\s*秒\s*[）)]",
    "scene_heading": r"(?:^|\n)\s*场景\s*(?:\n|$)",
    "fixed_lock_heading": r"(?:^|\n)\s*本分镜固定锁定\s*(?:\n|$)",
    "initial_state_heading": r"(?:^|\n)\s*人物初始(?:状态|站位与朝向)\s*(?:\n|$)",
    "camera_a_timeline": r"\d+\s*[–—-]\s*\d+\s*秒\s*｜\s*机位A",
    "camera_b_timeline": r"\d+\s*[–—-]\s*\d+\s*秒\s*｜\s*机位B",
    "lens": r"(?<![A-Za-z])\d{2,3}\s*mm(?![A-Za-z])",
    "focus_or_purpose": r"焦点|叙事目的",
    "action_expression": r"动作与表情|动作链|表演链",
    "space_continuity": r"空间连续性|轴线|不得跨轴|左右关系",
    "sound_heading": r"(?:^|\n)\s*音效\s*(?:\n|$)",
    "silent_narration_or_no_narration": r"旁白画面锚点|不生成旁白声音|无旁白|不得朗读",
    "final_state": r"最后一帧|最终结束状态|结束状态固定",
}

FORBIDDEN_TEXT = (
    "可执行精简版",
    "平台精简版",
    "V4精简版",
    "V4 精简版",
    "【音频硬约束｜最高优先级】",
    "【剧梦资产绑定标记",
    "资产引用白名单",
    "SCRIPT_SPLIT_PREFLIGHT",
    "ASSET_PREFLIGHT",
    "V4_ADDON",
    "V4_CORE",
    "PLATFORM_TOTAL",
    "continuity_link",
    "continuity_control",
    "required_asset_keys",
    "EP08_",
    ".png",
)

CAMERA_PATTERN = re.compile(
    r"(?P<start>\d+)\s*[–—-]\s*(?P<end>\d+)\s*秒\s*｜\s*机位(?P<label>[A-Z])"
)


def length_floor(duration: float) -> int:
    if duration < 3:
        raise ValueError("V4.2 formal shots must be at least 3 seconds")
    if duration <= 7:
        return 1800
    if duration <= 15:
        return 3200
    if duration < 20:
        return 4500
    if duration <= 30:
        return 6000
    raise ValueError("Shots longer than 30 seconds must be split before V4.2 generation")


def minimum_camera_count(duration: float) -> int:
    if duration <= 7:
        return 1
    if duration <= 15:
        return 2
    if duration < 20:
        return 3
    return 5


def timeline_errors(text: str, duration: float) -> tuple[list[str], int]:
    segments = [
        (int(match.group("start")), int(match.group("end")), match.group("label"))
        for match in CAMERA_PATTERN.finditer(text)
    ]
    errors: list[str] = []
    if not segments:
        return ["no time-coded camera segments found"], 0
    if segments[0][0] != 0:
        errors.append(f"timeline starts at {segments[0][0]} instead of 0")
    for previous, current in zip(segments, segments[1:]):
        if previous[1] != current[0]:
            errors.append(
                f"timeline gap/overlap between camera {previous[2]} ending {previous[1]} "
                f"and camera {current[2]} starting {current[0]}"
            )
    if segments[-1][1] != int(duration):
        errors.append(f"timeline ends at {segments[-1][1]} instead of {int(duration)}")
    return errors, len(segments)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    text = args.prompt.read_text(encoding="utf-8-sig")
    char_count = len(text)
    minimum_chars = length_floor(args.duration)
    missing_sections = [
        name
        for name, pattern in REQUIRED_PATTERNS.items()
        if not re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    ]
    forbidden_text = [label for label in FORBIDDEN_TEXT if label in text]
    timeline_problems, camera_count = timeline_errors(text, args.duration)
    camera_count_minimum = minimum_camera_count(args.duration)
    if camera_count < camera_count_minimum:
        timeline_problems.append(
            f"camera count {camera_count} is below V4.2 minimum {camera_count_minimum} for this duration"
        )
    if char_count > 15000:
        timeline_problems.append(f"prompt length {char_count} exceeds the 15000-character platform limit")

    passed = (
        char_count >= minimum_chars
        and not missing_sections
        and not forbidden_text
        and not timeline_problems
    )
    result = {
        "status": "V4_2_TEMPLATE_PREFLIGHT_PASS" if passed else "V4_2_TEMPLATE_PREFLIGHT_BLOCKED",
        "prompt": str(args.prompt.resolve()),
        "duration_seconds": args.duration,
        "character_count": char_count,
        "minimum_characters": minimum_chars,
        "maximum_characters": 15000,
        "camera_count": camera_count,
        "minimum_camera_count": camera_count_minimum,
        "missing_sections": missing_sections,
        "forbidden_text": forbidden_text,
        "timeline_problems": timeline_problems,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
