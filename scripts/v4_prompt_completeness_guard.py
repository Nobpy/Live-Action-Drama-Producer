#!/usr/bin/env python3
"""Fail closed when a formal V4 prompt is too short or lacks execution layers."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


LAYER_PATTERNS = {
    "script_boundary": (r"原文|覆盖范围|剧情边界|起止句|下一镜禁",),
    "asset_duties": (r"资产|引用|素材|参考图",),
    "space_blocking": (r"空间|站位|前景|中景|后景|拓扑",),
    "character_performance": (r"人物|角色|表演|动作链",),
    "camera_axis": (r"摄影机|机位|镜头|轴线|焦段",),
    "timeline": (r"时间轴|逐秒|\d+\s*[–—-]\s*\d+\s*秒",),
    "face_gaze": (r"面部|微表情|眼神|视线",),
    "continuity": (r"连续性|道具状态|场景状态|服装状态",),
    "sound_dialogue": (r"声音|对白|口型|环境声|动作音",),
    "negative_rules": (r"禁止|不得|负面",),
    "end_point": (r"结束点|最后一帧|尾帧|下一镜",),
}


def minimum_chars(duration: float) -> int:
    if duration < 3:
        raise ValueError("V4 formal shots must be at least 3 seconds")
    if duration <= 7:
        return 2500
    if duration <= 15:
        return 4000
    if duration < 20:
        return math.ceil(4000 + (duration - 15) * 800)
    if duration <= 30:
        return 8000
    raise ValueError("Shots longer than 30 seconds must be split before V4 generation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    text = args.prompt.read_text(encoding="utf-8")
    char_count = len(text)
    min_chars = minimum_chars(args.duration)
    missing_layers = [
        name
        for name, patterns in LAYER_PATTERNS.items()
        if not any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    ]
    forbidden_labels = [
        label
        for label in ("可执行精简版", "平台精简版", "V4精简版", "V4 精简版")
        if label in text
    ]
    passed = char_count >= min_chars and not missing_layers and not forbidden_labels
    result = {
        "status": "V4_DETAIL_PREFLIGHT_PASS" if passed else "V4_DETAIL_PREFLIGHT_BLOCKED",
        "prompt": str(args.prompt.resolve()),
        "duration_seconds": args.duration,
        "char_count": char_count,
        "minimum_chars": min_chars,
        "missing_layers": missing_layers,
        "forbidden_labels": forbidden_labels,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
