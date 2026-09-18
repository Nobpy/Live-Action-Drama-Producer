#!/usr/bin/env python3
"""Audit asset-registry.csv paths and fingerprints; optionally write safe updates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


FIELDS = [
    "asset_key", "asset_type", "canonical_name", "aliases", "platform_name", "local_file",
    "continuity_scope", "status", "match_confidence", "match_basis", "file_size",
    "modified_time", "sha256", "platform_asset_id", "last_verified_at", "notes",
]


def fingerprint(path: Path) -> tuple[str, str, str]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
    return str(stat.st_size), modified, digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="update fingerprints and changed statuses")
    args = parser.parse_args()

    with args.registry.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError("registry header does not match the v1.5.1 template")
        rows = list(reader)

    seen_keys: set[str] = set()
    seen_platform: set[str] = set()
    results: list[dict] = []
    for row in rows:
        key = row["asset_key"].strip()
        platform = row["platform_name"].strip()
        duplicate = key in seen_keys or (platform and platform in seen_platform)
        seen_keys.add(key)
        if platform:
            seen_platform.add(platform)
        root = args.asset_root.resolve()
        local = (root / row["local_file"]).resolve()
        if local != root and root not in local.parents:
            raise ValueError(f"asset path escapes asset root: {row['local_file']}")
        if not local.is_file():
            row["status"] = "MISSING"
            results.append({"asset_key": key, "result": "MISSING", "file": str(local)})
            continue
        size, modified, sha256 = fingerprint(local)
        first_seen = not bool(row["sha256"])
        changed = not first_seen and row["sha256"].lower() != sha256
        if changed or duplicate or (first_seen and not row["last_verified_at"]):
            row["status"] = "PENDING_CONFIRMATION"
            row["match_confidence"] = "LOW" if duplicate else ""
            row["last_verified_at"] = ""
        row["file_size"], row["modified_time"], row["sha256"] = size, modified, sha256
        result = "DUPLICATE" if duplicate else "CHANGED" if changed else "NEW" if first_seen else "OK"
        results.append({"asset_key": key, "result": result, "file": str(local)})

    if args.write:
        with args.registry.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 2 if any(item["result"] in {"MISSING", "DUPLICATE"} for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
