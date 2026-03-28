#!/usr/bin/env python3
"""Ensure no duplicate SFS numbers exist across all law files.

Usage:
    python scripts/validate/sfs_uniqueness.py
"""

import sys
from collections import defaultdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAW_DIRS = ["lagar", "förordningar", "grundlagar", "upphävda"]


def extract_sfs_number(file_path: Path) -> str | None:
    """Extract the SFS number from a file's YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        frontmatter = yaml.safe_load(parts[1])
        return frontmatter.get("sfs")
    except yaml.YAMLError:
        return None


def main() -> None:
    sfs_map: dict[str, list[str]] = defaultdict(list)

    for dir_name in LAW_DIRS:
        dir_path = REPO_ROOT / dir_name
        if not dir_path.is_dir():
            continue

        for md_file in dir_path.rglob("*.md"):
            sfs = extract_sfs_number(md_file)
            if sfs:
                rel_path = str(md_file.relative_to(REPO_ROOT))
                sfs_map[sfs].append(rel_path)

    duplicates = {sfs: paths for sfs, paths in sfs_map.items() if len(paths) > 1}

    if duplicates:
        print(f"\nFound {len(duplicates)} duplicate SFS number(s):\n", file=sys.stderr)
        for sfs, paths in sorted(duplicates.items()):
            print(f"  ✗ SFS {sfs} appears in:", file=sys.stderr)
            for path in paths:
                print(f"      - {path}", file=sys.stderr)
        sys.exit(1)
    else:
        total = len(sfs_map)
        print(f"✓ All {total} SFS numbers are unique.")


if __name__ == "__main__":
    main()
