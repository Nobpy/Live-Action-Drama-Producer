#!/usr/bin/env python3
"""Preflight the text expansion caused by 剧梦 one-click asset binding.

The approved V4.2 prompt is read-only.  A mapping file is a JSON object with a
``mappings`` list.  Each item needs ``name`` (the natural string already in the
prompt) and ``asset_name`` (the exact platform asset display name).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
TEMP_ALIAS_RE = re.compile(
    r"(^[_@#]+)|([_@#]+$)|(placeholder|temp(?:orary)?|alias|token)", re.IGNORECASE
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check natural asset anchors and the 15000-character expansion budget."
    )
    parser.add_argument("prompt", type=Path, help="Approved V4.2 prompt text file")
    parser.add_argument("mappings", type=Path, help="JSON mapping file")
    parser.add_argument("--max-chars", type=int, default=15000)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_mappings(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("mappings") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("mapping JSON must be a list or contain a 'mappings' list")
    return rows


def main() -> int:
    args = parse_args()
    prompt = args.prompt.read_text(encoding="utf-8-sig")
    errors: list[str] = []
    details: list[dict[str, object]] = []

    try:
        rows = load_mappings(args.mappings)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "status": "ASSET_REFERENCE_BUDGET_BLOCKED",
            "errors": [f"invalid mapping file: {exc}"],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    seen_names: set[str] = set()
    estimated_chars = len(prompt)
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"mapping {index}: item must be an object")
            continue
        name = row.get("name")
        asset_name = row.get("asset_name")
        if not isinstance(name, str) or not name:
            errors.append(f"mapping {index}: missing non-empty name")
            continue
        if not isinstance(asset_name, str) or not asset_name:
            errors.append(f"mapping {index}: missing non-empty asset_name")
            continue
        if name != name.strip():
            errors.append(f"mapping {index}: name has leading/trailing whitespace: {name!r}")
        if ZERO_WIDTH_RE.search(name):
            errors.append(f"mapping {index}: name contains zero-width/control characters: {name!r}")
        if TEMP_ALIAS_RE.search(name):
            errors.append(f"mapping {index}: temporary alias/marker is forbidden: {name!r}")
        if name in seen_names:
            errors.append(f"mapping {index}: duplicate mapping name: {name!r}")
        seen_names.add(name)

        occurrences = prompt.count(name)
        if occurrences == 0:
            errors.append(f"mapping {index}: natural name is not present in approved prompt: {name!r}")
        expansion = occurrences * max(0, len(asset_name) - len(name))
        estimated_chars += expansion
        details.append(
            {
                "name": name,
                "asset_name": asset_name,
                "occurrences": occurrences,
                "estimated_expansion": expansion,
            }
        )

    if estimated_chars > args.max_chars:
        errors.append(
            f"estimated expanded prompt length {estimated_chars} exceeds limit {args.max_chars}"
        )

    status = "ASSET_REFERENCE_BUDGET_PASS" if not errors else "ASSET_REFERENCE_BUDGET_BLOCKED"
    result = {
        "status": status,
        "prompt_chars": len(prompt),
        "estimated_expanded_chars": estimated_chars,
        "max_chars": args.max_chars,
        "mappings": details,
        "errors": errors,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
