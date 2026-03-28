#!/usr/bin/env python3
"""Create a corpus snapshot for a given date.

Merges qualifying PRs whose ikraftträdandedatum matches the target date,
creates a git tag, and generates a GitHub Release.

Usage:
    python scripts/release/create_corpus_snapshot.py --date today
    python scripts/release/create_corpus_snapshot.py --date 2024-07-01
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import git
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def get_target_date(date_str: str) -> date:
    """Parse the target date string."""
    if date_str == "today":
        return date.today()
    return date.fromisoformat(date_str)


def find_laws_in_force(target: date) -> list[dict]:
    """Find all law files in force on the target date."""
    laws = []
    for dir_name in ["lagar", "förordningar", "grundlagar"]:
        dir_path = REPO_ROOT / dir_name
        if not dir_path.is_dir():
            continue

        for md_file in sorted(dir_path.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            try:
                fm = yaml.safe_load(parts[1])
            except yaml.YAMLError:
                continue

            ikraft = fm.get("ikraftträdande")
            upphävd = fm.get("upphävd")

            if not ikraft:
                continue

            ikraft_date = date.fromisoformat(str(ikraft))
            if ikraft_date > target:
                continue

            if upphävd:
                upphävd_date = date.fromisoformat(str(upphävd))
                if upphävd_date <= target:
                    continue

            laws.append(
                {
                    "sfs": fm.get("sfs", ""),
                    "titel": fm.get("titel", ""),
                    "path": str(md_file.relative_to(REPO_ROOT)),
                    "ikraftträdande": str(ikraft),
                }
            )

    return laws


def create_tag_and_release(target: date, laws: list[dict]) -> None:
    """Create a git tag and GitHub release for the snapshot."""
    repo = git.Repo(REPO_ROOT)
    tag_name = f"v{target.isoformat()}"

    # Check if tag already exists
    if tag_name in [t.name for t in repo.tags]:
        logger.info("Tag %s already exists, skipping", tag_name)
        return

    # Create annotated tag
    message = f"Corpus snapshot {target.isoformat()}\n\n"
    message += f"{len(laws)} laws in force on this date.\n"

    repo.create_tag(tag_name, message=message)
    logger.info("Created tag: %s", tag_name)

    # Create GitHub Release using gh CLI
    release_body = f"## Lagkorpus {target.isoformat()}\n\n"
    release_body += f"**{len(laws)} författningar i kraft på detta datum.**\n\n"

    if laws:
        release_body += "### Författningar\n\n"
        for law in laws[:50]:  # Limit to first 50 in release notes
            release_body += f"- {law['titel']} (`{law['sfs']}`)\n"
        if len(laws) > 50:
            release_body += f"\n…och {len(laws) - 50} till.\n"

    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        try:
            subprocess.run(
                [
                    "gh", "release", "create", tag_name,
                    "--title", f"Lagkorpus {target.isoformat()}",
                    "--notes", release_body,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Created GitHub release for %s", tag_name)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning("Could not create GitHub release: %s", e)
    else:
        logger.info("No GITHUB_TOKEN set, skipping GitHub release creation")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a corpus snapshot for a given date"
    )
    parser.add_argument(
        "--date",
        type=str,
        default="today",
        help="Target date (ISO format or 'today')",
    )
    args = parser.parse_args()

    target = get_target_date(args.date)
    logger.info("Creating corpus snapshot for %s", target.isoformat())

    laws = find_laws_in_force(target)
    logger.info("Found %d laws in force on %s", len(laws), target.isoformat())

    create_tag_and_release(target, laws)


if __name__ == "__main__":
    main()
