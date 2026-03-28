#!/usr/bin/env python3
"""Reconstruct the full git history of Swedish law from rinfo.gov.se.

This script fetches SFS entries from Lagrummet (rinfo.gov.se) in chronological
order and creates git commits with historical dates for each legislative change.

Usage:
    python scripts/import/historical_import.py --from-year 1990 --dry-run
    python scripts/import/historical_import.py --from-year 1900
"""

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import git
import requests
import yaml

from sfs_parser import SFSParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RINFO_BASE = os.environ.get("RINFO_BASE", "https://rinfo.gov.se")
USER_AGENT = os.environ.get(
    "USER_AGENT", "Lagläget/1.0 (github.com/lardinator/lagl-get)"
)
REQUEST_DELAY = 2.0  # seconds between requests (0.5 req/sec)


def fetch_sfs_entry(year: int, number: int) -> dict | None:
    """Fetch a single SFS entry from rinfo.gov.se."""
    url = f"{RINFO_BASE}/publ/sfs/{year}:{number}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rdf+xml"}

    for attempt in range(4):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return {"url": url, "content": resp.text, "year": year, "number": number}
        except requests.RequestException as e:
            wait = 2 ** (attempt + 1)
            logger.warning("Request failed (%s), retrying in %ds...", e, wait)
            time.sleep(wait)

    logger.error("Failed to fetch %s after 4 attempts", url)
    return None


def fetch_consolidated_text(year: int, number: int) -> str | None:
    """Fetch the consolidated (current) text of an SFS entry."""
    url = f"{RINFO_BASE}/publ/sfs/{year}:{number}/konsoliderad"
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(4):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            wait = 2 ** (attempt + 1)
            logger.warning("Request failed (%s), retrying in %ds...", e, wait)
            time.sleep(wait)

    return None


def fetch_change_feed(since_date: str | None = None) -> list[dict]:
    """Fetch the Atom feed of recent changes from rinfo.gov.se."""
    url = f"{RINFO_BASE}/feed/current"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/atom+xml"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        # Parse Atom feed - simplified, real implementation would use feedparser
        return []
    except requests.RequestException as e:
        logger.error("Failed to fetch change feed: %s", e)
        return []


def determine_file_path(sfs_number: str, typ: str) -> Path:
    """Determine the file path for a given SFS number and type."""
    year, number = sfs_number.split(":")
    if typ == "grundlag":
        # Grundlagar have special paths
        return Path(f"grundlagar/SFS-{year}-{number}.md")
    elif typ == "förordning":
        return Path(f"förordningar/{year}/SFS-{year}-{number}.md")
    else:
        return Path(f"lagar/{year}/SFS-{year}-{number}.md")


def create_commit(
    repo: git.Repo,
    file_path: Path,
    content: str,
    sfs_number: str,
    description: str,
    ikraftträdande: str,
    proposition: str = "okänd",
    utskott: str = "okänd",
    votering: str = "okänd",
    riksdagen_dok: str = "okänd",
    departement: str = "Riksdagen",
    dry_run: bool = False,
) -> None:
    """Create a git commit with historical date for a legislative change."""
    commit_msg = (
        f"SFS {sfs_number} — {description}\n\n"
        f"Proposition: {proposition}\n"
        f"Utskott: {utskott}\n"
        f"Votering: {votering}\n"
        f"Ikraftträdande: {ikraftträdande}\n"
        f"Riksdagen-dok: {riksdagen_dok}\n"
    )

    if dry_run:
        logger.info("[DRY RUN] Would commit: %s -> %s", sfs_number, file_path)
        return

    # Ensure parent directory exists
    full_path = Path(repo.working_dir) / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")

    repo.index.add([str(file_path)])

    # Set historical dates
    author_date = f"{ikraftträdande}T00:00:00+01:00"
    author = git.Actor(departement, "noreply@riksdagen.se")

    repo.index.commit(
        commit_msg,
        author=author,
        committer=author,
        author_date=author_date,
        commit_date=author_date,
    )
    logger.info("Committed: SFS %s (%s)", sfs_number, ikraftträdande)


def create_annual_tags(repo: git.Repo, from_year: int, to_year: int) -> None:
    """Create annual v{YYYY}-01-01 tags for snapshot access."""
    for year in range(max(from_year, 1900), to_year + 1):
        tag_name = f"v{year}-01-01"
        # Find the last commit before January 1 of this year
        try:
            commits = list(
                repo.iter_commits(
                    until=f"{year}-01-01T00:00:00",
                    max_count=1,
                )
            )
            if commits:
                repo.create_tag(tag_name, ref=commits[0], message=f"Corpus snapshot {year}-01-01")
                logger.info("Created tag: %s", tag_name)
        except git.GitCommandError:
            logger.warning("Could not create tag %s", tag_name)


def run_import(from_year: int, to_year: int, dry_run: bool = False) -> None:
    """Run the historical import from rinfo.gov.se."""
    repo_path = Path(__file__).resolve().parent.parent.parent
    repo = git.Repo(repo_path)

    parser = SFSParser()
    total_commits = 0

    logger.info(
        "Starting historical import from %d to %d%s",
        from_year,
        to_year,
        " (DRY RUN)" if dry_run else "",
    )

    for year in range(from_year, to_year + 1):
        logger.info("Processing year %d...", year)

        # Fetch all SFS entries for this year
        # In practice, we'd enumerate known SFS numbers from rinfo
        number = 1
        consecutive_misses = 0

        while consecutive_misses < 50:
            time.sleep(REQUEST_DELAY)

            entry = fetch_sfs_entry(year, number)
            if entry is None:
                consecutive_misses += 1
                number += 1
                continue

            consecutive_misses = 0

            try:
                parsed = parser.parse(entry["content"])
                file_path = determine_file_path(
                    parsed["sfs"], parsed.get("typ", "lag")
                )
                markdown = parser.to_markdown(parsed)

                create_commit(
                    repo=repo,
                    file_path=file_path,
                    content=markdown,
                    sfs_number=parsed["sfs"],
                    description=parsed.get("titel", "Ny författning"),
                    ikraftträdande=parsed.get(
                        "ikraftträdande", f"{year}-01-01"
                    ),
                    departement=parsed.get("departement", "Riksdagen"),
                    dry_run=dry_run,
                )
                total_commits += 1
            except Exception as e:
                logger.error(
                    "Failed to process SFS %d:%d: %s", year, number, e
                )

            number += 1

    if not dry_run:
        logger.info("Creating annual tags...")
        create_annual_tags(repo, from_year, to_year)

    logger.info("Import complete. Total commits: %d", total_commits)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import historical Swedish law from rinfo.gov.se"
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=1825,
        help="Start year for import (default: 1825)",
    )
    parser.add_argument(
        "--to-year",
        type=int,
        default=date.today().year,
        help="End year for import (default: current year)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes",
    )
    args = parser.parse_args()

    run_import(args.from_year, args.to_year, args.dry_run)


if __name__ == "__main__":
    main()
