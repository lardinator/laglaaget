#!/usr/bin/env python3
"""Validate YAML frontmatter in law files against law.schema.json.

Usage:
    python scripts/validate/frontmatter.py lagar/ förordningar/ grundlagar/
"""

import json
import sys
from pathlib import Path

import jsonschema
import yaml

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schema" / "law.schema.json"


def load_schema() -> dict:
    """Load the JSON Schema for law file frontmatter."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def extract_frontmatter(file_path: Path) -> dict | None:
    """Extract YAML frontmatter from a Markdown file."""
    content = file_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        return yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        print(f"  YAML parse error in {file_path}: {e}", file=sys.stderr)
        return None


def validate_file(file_path: Path, schema: dict) -> list[str]:
    """Validate a single law file's frontmatter. Returns list of errors."""
    errors = []

    frontmatter = extract_frontmatter(file_path)
    if frontmatter is None:
        errors.append(f"{file_path}: Missing or invalid YAML frontmatter")
        return errors

    validator = jsonschema.Draft202012Validator(schema)
    for error in validator.iter_errors(frontmatter):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{file_path}: {path}: {error.message}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: frontmatter.py <directory> [directory...]", file=sys.stderr)
        sys.exit(1)

    schema = load_schema()
    all_errors = []

    for dir_arg in sys.argv[1:]:
        dir_path = Path(dir_arg)
        if not dir_path.is_dir():
            print(f"Warning: {dir_path} is not a directory, skipping", file=sys.stderr)
            continue

        for md_file in sorted(dir_path.rglob("*.md")):
            errors = validate_file(md_file, schema)
            all_errors.extend(errors)

    if all_errors:
        print(f"\nFound {len(all_errors)} validation error(s):\n", file=sys.stderr)
        for error in all_errors:
            print(f"  ✗ {error}", file=sys.stderr)
        sys.exit(1)
    else:
        file_count = sum(
            len(list(Path(d).rglob("*.md"))) for d in sys.argv[1:] if Path(d).is_dir()
        )
        print(f"✓ All {file_count} files passed frontmatter validation.")


if __name__ == "__main__":
    main()
