#!/usr/bin/env python3
"""Verify that all cross-references (§-hänvisningar) resolve to existing files and anchors.

Checks both internal links (within a file) and cross-file references.

Usage:
    python scripts/validate/cross_references.py
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAW_DIRS = ["lagar", "förordningar", "grundlagar", "upphävda"]

# Match Markdown links: [text](path#anchor) or [text](path)
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def find_all_law_files() -> dict[str, Path]:
    """Build a map of relative paths to absolute paths for all law files."""
    files = {}
    for dir_name in LAW_DIRS:
        dir_path = REPO_ROOT / dir_name
        if dir_path.is_dir():
            for md_file in dir_path.rglob("*.md"):
                rel = md_file.relative_to(REPO_ROOT)
                files[str(rel)] = md_file
    return files


def extract_anchors(file_path: Path) -> set[str]:
    """Extract all heading-based anchors from a Markdown file."""
    anchors = set()
    content = file_path.read_text(encoding="utf-8")

    for line in content.split("\n"):
        if line.startswith("#"):
            # Convert heading to GitHub-style anchor
            heading = line.lstrip("#").strip()
            anchor = heading.lower()
            anchor = re.sub(r"[^\w\s§-]", "", anchor)
            anchor = re.sub(r"\s+", "-", anchor)
            anchor = anchor.strip("-")
            anchors.add(anchor)

    return anchors


def check_references(file_path: Path, all_files: dict[str, Path]) -> list[str]:
    """Check all Markdown links in a file. Returns list of errors."""
    errors = []
    content = file_path.read_text(encoding="utf-8")
    file_dir = file_path.parent

    for match in LINK_PATTERN.finditer(content):
        link_text = match.group(1)
        link_target = match.group(2)

        # Skip external URLs
        if link_target.startswith(("http://", "https://", "mailto:")):
            continue

        # Split path and anchor
        if "#" in link_target:
            path_part, anchor_part = link_target.split("#", 1)
        else:
            path_part = link_target
            anchor_part = None

        # Resolve relative path
        if path_part:
            target_path = (file_dir / path_part).resolve()
            target_rel = None
            try:
                target_rel = str(target_path.relative_to(REPO_ROOT))
            except ValueError:
                errors.append(
                    f"{file_path}: Link [{link_text}] points outside repository: {link_target}"
                )
                continue

            if target_rel not in all_files and not target_path.exists():
                errors.append(
                    f"{file_path}: Broken link [{link_text}]({link_target}) — file not found"
                )
                continue

            # Check anchor if present
            if anchor_part:
                actual_path = all_files.get(target_rel, target_path)
                if actual_path.exists():
                    anchors = extract_anchors(actual_path)
                    if anchor_part not in anchors:
                        errors.append(
                            f"{file_path}: Broken anchor [{link_text}]({link_target}) "
                            f"— anchor '{anchor_part}' not found"
                        )
        elif anchor_part:
            # Internal anchor reference
            anchors = extract_anchors(file_path)
            if anchor_part not in anchors:
                errors.append(
                    f"{file_path}: Broken internal anchor [{link_text}](#{anchor_part})"
                )

    return errors


def main() -> None:
    all_files = find_all_law_files()
    all_errors = []

    for rel_path, abs_path in sorted(all_files.items()):
        errors = check_references(abs_path, all_files)
        all_errors.extend(errors)

    if all_errors:
        print(f"\nFound {len(all_errors)} broken reference(s):\n", file=sys.stderr)
        for error in all_errors:
            print(f"  ✗ {error}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"✓ All cross-references valid across {len(all_files)} files.")


if __name__ == "__main__":
    main()
