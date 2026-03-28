#!/usr/bin/env python3
"""Nightly sync with Riksdagen's open data API.

Polls for new propositioner that have been decided (beslutade) and creates
branches, commits, and PRs in the Lagläget repository.

Usage:
    python scripts/import/riksdagen_sync.py --since 2024-01-01
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

import git
import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RIKSDAGEN_API_BASE = os.environ.get(
    "RIKSDAGEN_API_BASE", "https://data.riksdagen.se"
)
USER_AGENT = os.environ.get(
    "USER_AGENT", "Lagläget/1.0 (github.com/lardinator/lagl-get)"
)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REQUEST_DELAY = 1.0  # 1 req/sec


def api_get(endpoint: str, params: dict | None = None) -> dict | None:
    """Make a GET request to the Riksdagen API with retry logic."""
    url = f"{RIKSDAGEN_API_BASE}{endpoint}"
    headers = {"User-Agent": USER_AGENT}
    if params is None:
        params = {}
    params["utformat"] = "json"

    for attempt in range(4):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            wait = 2 ** (attempt + 1)
            logger.warning("API request failed (%s), retrying in %ds...", e, wait)
            time.sleep(wait)

    logger.error("Failed to fetch %s after 4 attempts", url)
    return None


def fetch_new_propositioner(since: str) -> list[dict]:
    """Fetch propositioner decided since the given date."""
    data = api_get(
        "/dokumentlista/",
        params={
            "doktyp": "prop",
            "status": "beslutad",
            "from": since,
            "sort": "datum",
            "sortorder": "asc",
        },
    )

    if not data:
        return []

    documents = data.get("dokumentlista", {}).get("dokument", [])
    if isinstance(documents, dict):
        documents = [documents]

    logger.info("Found %d new propositioner since %s", len(documents), since)
    return documents


def fetch_document(doc_id: str) -> dict | None:
    """Fetch full document text by Riksdagen document ID."""
    time.sleep(REQUEST_DELAY)
    return api_get(f"/dokument/{doc_id}")


def fetch_votering(rm: str, bet: str) -> dict | None:
    """Fetch voting results for a specific betänkande."""
    time.sleep(REQUEST_DELAY)
    return api_get(
        "/voteringlista/",
        params={"rm": rm, "bet": bet},
    )


def extract_sfs_numbers(document: dict) -> list[str]:
    """Extract SFS numbers affected by a proposition from document text."""
    sfs_numbers = []
    text = json.dumps(document, ensure_ascii=False)

    import re

    for match in re.finditer(r"SFS\s*(\d{4}:\d+)", text):
        sfs = match.group(1)
        if sfs not in sfs_numbers:
            sfs_numbers.append(sfs)

    return sfs_numbers


def format_votering(votering_data: dict) -> str:
    """Format voting results as a string."""
    if not votering_data:
        return "okänd"

    voteringar = votering_data.get("voteringlista", {}).get("votering", [])
    if isinstance(voteringar, dict):
        voteringar = [voteringar]

    ja = nej = avstar = 0
    for v in voteringar:
        rost = v.get("rost", "").lower()
        if rost == "ja":
            ja += 1
        elif rost == "nej":
            nej += 1
        elif rost == "avstår":
            avstar += 1

    return f"{ja} ja / {nej} nej / {avstar} avstår"


def create_branch_and_pr(
    repo: git.Repo,
    proposition: dict,
    sfs_numbers: list[str],
    votering_str: str,
) -> None:
    """Create a branch, commit changes, and open a PR for a proposition."""
    dok_id = proposition.get("dok_id", "unknown")
    rm = proposition.get("rm", "")
    nummer = proposition.get("nummer", "")
    titel = proposition.get("titel", "Okänd proposition")
    datum = proposition.get("datum", "")
    organ = proposition.get("organ", "okänd")

    branch_name = f"prop/{rm}-{nummer}"

    # Create branch from main
    main = repo.heads.main if "main" in [h.name for h in repo.heads] else repo.active_branch
    new_branch = repo.create_head(branch_name, main)
    new_branch.checkout()

    # For each affected SFS, update the file
    for sfs in sfs_numbers:
        year, number = sfs.split(":")
        file_path = Path(f"lagar/{year}/SFS-{year}-{number}.md")
        full_path = Path(repo.working_dir) / file_path

        if full_path.exists():
            # Update existing file - add to ändringshistorik
            content = full_path.read_text(encoding="utf-8")
            logger.info("Would update %s for proposition %s/%s:%s", file_path, rm, rm, nummer)
        else:
            logger.info("SFS %s not found locally, skipping", sfs)

    # Create commit
    commit_msg = (
        f"SFS {', '.join(sfs_numbers)} — {titel}\n\n"
        f"Proposition: {rm}:{nummer}\n"
        f"Utskott: {organ}\n"
        f"Votering: {votering_str}\n"
        f"Ikraftträdande: {datum}\n"
        f"Riksdagen-dok: {dok_id}\n"
    )

    if repo.index.diff("HEAD") or repo.untracked_files:
        repo.index.commit(commit_msg)

    # Switch back to main
    main.checkout()

    logger.info("Created branch %s for proposition %s:%s", branch_name, rm, nummer)


def sync(since: str) -> None:
    """Run the sync process."""
    repo_path = Path(__file__).resolve().parent.parent.parent
    repo = git.Repo(repo_path)

    propositioner = fetch_new_propositioner(since)

    for prop in propositioner:
        dok_id = prop.get("dok_id", "")
        rm = prop.get("rm", "")
        nummer = prop.get("nummer", "")
        titel = prop.get("titel", "")
        organ = prop.get("organ", "")

        logger.info("Processing: %s:%s — %s", rm, nummer, titel)

        # Fetch full document
        document = fetch_document(dok_id)
        if not document:
            logger.warning("Could not fetch document %s", dok_id)
            continue

        # Extract affected SFS numbers
        sfs_numbers = extract_sfs_numbers(document)
        if not sfs_numbers:
            logger.warning("No SFS numbers found in %s", dok_id)
            continue

        # Fetch votering
        votering_data = fetch_votering(rm, f"{organ}{nummer}")
        votering_str = format_votering(votering_data)

        # Create branch and PR
        try:
            create_branch_and_pr(repo, prop, sfs_numbers, votering_str)
        except Exception as e:
            logger.error("Failed to process %s:%s: %s", rm, nummer, e)

        time.sleep(REQUEST_DELAY)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync with Riksdagen's open data API"
    )
    parser.add_argument(
        "--since",
        type=str,
        default=str(date.today()),
        help="Sync propositioner decided since this date (ISO format)",
    )
    args = parser.parse_args()

    sync(args.since)


if __name__ == "__main__":
    main()
