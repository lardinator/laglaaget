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
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import git
import requests
import yaml

from prot_parser import ProtParser, VoteringResult
from sfs_parser import SFSParser
from rkrattsbaser_scraper import RkrattsbaserScraper, SFSMetadata

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

    # Set historical dates — gitpython requires "UNIX_TS +HHMM" format
    normalized = _normalize_date(ikraftträdande) or "1900-01-01"
    author_date = _date_to_git_ts(normalized)
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


_SWEDISH_MONTHS = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

_TZ_SE = timezone(timedelta(hours=1))


def _normalize_date(raw: str | None) -> str | None:
    """Normalize date to ISO 'YYYY-MM-DD'. Handles ISO and Swedish prose formats."""
    if not raw:
        return None
    raw = raw.strip()
    if raw[:4].isdigit() and len(raw) >= 10 and raw[4] == "-":
        return raw[:10]
    # Swedish prose: "den D MONTH YYYY" or "D MONTH YYYY"
    parts = raw.lower().replace("den ", "").split()
    if len(parts) == 3:
        try:
            day, month_name, year = parts
            month = _SWEDISH_MONTHS.get(month_name)
            if month:
                return f"{int(year):04d}-{month:02d}-{int(day):02d}"
        except (ValueError, KeyError):
            pass
    return None


def _date_to_git_ts(iso_date: str) -> str:
    """Convert 'YYYY-MM-DD' to git author_date format 'UNIX_TS +0100'."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=_TZ_SE)
    return f"{int(dt.timestamp())} +0100"


def sort_key_for_sfs(metadata) -> str:
    """Return sortable key: normalized ISO date, or '9999-99-99' for None."""
    return _normalize_date(metadata.ikraftträdande) or "9999-99-99"


def run_import_rkrattsbaser(
    dry_run: bool = False,
    sfs_filter: list[str] | None = None,
) -> None:
    """Run historical import using RkrattsbaserScraper (replaces defunct rinfo.gov.se)."""
    repo_path = Path(__file__).resolve().parent.parent.parent
    repo = git.Repo(repo_path)

    scraper = RkrattsbaserScraper()
    parser = SFSParser()
    prot_parser = ProtParser()
    total_commits = 0

    logger.info(
        "Starting rkrattsbaser import%s%s",
        f" (filter: {sfs_filter})" if sfs_filter else "",
        " (DRY RUN)" if dry_run else "",
    )

    # Get SFS numbers to process
    if sfs_filter is not None:
        sfs_numbers = sfs_filter
    else:
        logger.info("Enumerating all SFS numbers from rkrattsbaser.gov.se...")
        sfs_numbers = scraper.enumerate_sfs_numbers()
        logger.info("Found %d SFS numbers", len(sfs_numbers))

    # Fetch metadata for all, skip None, sort chronologically
    entries: list[tuple] = []
    for sfs in sfs_numbers:
        metadata = scraper.fetch_metadata(sfs)
        if metadata is None:
            logger.warning("No metadata for SFS %s, skipping", sfs)
            continue
        entries.append((metadata, sfs))

    entries.sort(key=lambda t: sort_key_for_sfs(t[0]))
    logger.info("Processing %d entries in chronological order", len(entries))

    for metadata, sfs in entries:
        try:
            text = scraper.fetch_text(sfs)
            parsed = parser.parse_from_scraper(metadata, text)
            file_path = determine_file_path(parsed["sfs"], parsed["typ"])
            markdown = parser.to_markdown(parsed)

            # Resolve votering from riksdag protocol
            bet_beteckning = parsed.get("forarbete_bet") or ""
            ikraft = _normalize_date(parsed.get("ikraftträdande")) or ""
            year = int(ikraft[:4]) if ikraft else 0
            rm = str(year) if year <= 1974 else f"{year}/{str(year + 1)[-2:]}" if year > 0 else ""
            votering_str = "ej tillgänglig"
            riksdagen_dok = "okänd"
            if bet_beteckning and rm and not dry_run:
                prot_result = fetch_protokoll_section(bet_beteckning, rm)
                if prot_result:
                    prot_text, riksdagen_dok = prot_result
                    votering = prot_parser.parse_votering(prot_text, rm)
                    votering_str = format_votering_for_commit(votering)

            create_commit(
                repo=repo,
                file_path=file_path,
                content=markdown,
                sfs_number=parsed["sfs"],
                description=parsed.get("titel", "Ny författning"),
                ikraftträdande=parsed.get("ikraftträdande", "1900-01-01"),
                proposition=parsed.get("forarbete_prop", "okänd"),
                utskott=parsed.get("forarbete_bet", "okänd"),
                votering=votering_str,
                riksdagen_dok=riksdagen_dok,
                departement=parsed.get("departement", "Riksdagen"),
                dry_run=dry_run,
            )
            total_commits += 1
        except Exception as e:
            logger.error("Failed to process SFS %s: %s", sfs, e)

    if not dry_run:
        logger.info("Creating annual tags...")
        years = [
            int(iso[:4]) for m, _ in entries
            if (iso := _normalize_date(m.ikraftträdande))
        ]
        if years:
            create_annual_tags(repo, min(years), max(years))

    logger.info("Import complete. Total commits: %d", total_commits)


def api_get(endpoint: str, params: dict | None = None) -> dict | None:
    """Fetch from Riksdagen API (data.riksdagen.se).

    Args:
        endpoint: API endpoint path, e.g. "/dokumentlista/" or "/dokument/{dok_id}"
        params: Query parameters dict

    Returns:
        Parsed JSON response as dict, or None on error.
    """
    base = "https://data.riksdagen.se"
    url = f"{base}{endpoint}"
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            wait = 2 ** attempt
            logger.warning("API request failed (%s), retrying in %ds...", e, wait)
            time.sleep(wait)

    logger.error("Failed to fetch %s after 3 attempts", url)
    return None


def format_votering_for_commit(votering: "VoteringResult | None") -> str:
    """Format a VoteringResult into the commit message Votering: line.

    Examples:
        "268 ja / 20 nej / 1 avstår (s, v ja; m nej)"
        "acklamation"
        "ej tillgänglig"
    """
    if votering is None:
        return "ej tillgänglig"

    if votering.metod == "acklamation":
        return "acklamation"

    parts = []
    if votering.ja is not None:
        parts.append(f"{votering.ja} ja")
    if votering.nej is not None:
        parts.append(f"{votering.nej} nej")
    if votering.avstar is not None:
        parts.append(f"{votering.avstar} avstår")

    result = " / ".join(parts) if parts else "ej tillgänglig"

    if votering.partier:
        ja_parties = sorted(p for p, v in votering.partier.items() if v == "ja")
        nej_parties = sorted(p for p, v in votering.partier.items() if v == "nej")
        party_parts = []
        if ja_parties:
            party_parts.append(f"{', '.join(ja_parties)} ja")
        if nej_parties:
            party_parts.append(f"{', '.join(nej_parties)} nej")
        if party_parts:
            result += f" ({'; '.join(party_parts)})"

    return result


def fetch_protokoll_section(bet_beteckning: str, rm: str) -> tuple[str, str] | None:
    """Fetch protocol text for the riksdag session that handled a betänkande.

    For rm >= 2002/03: fetches from doktyp=votering using bet_beteckning as dok_id prefix.
    For older rm: fetches prot document text and searches for the betänkande reference.

    Args:
        bet_beteckning: e.g. "2016/17:CU11" or "UU15"
        rm: riksmöte string e.g. "1996/97"

    Returns:
        Tuple of (text/HTML content, dok_id), or None if not found.
    """
    year = int(rm.split("/")[0]) if "/" in rm else int(rm) if rm.isdigit() else 0

    if year >= 2002:
        # Use dedicated votering document type
        data = api_get(
            "/dokumentlista/",
            params={"doktyp": "votering", "rm": rm, "bet": bet_beteckning},
        )
        if not data:
            return None
        docs = data.get("dokumentlista", {}).get("dokument", [])
        if isinstance(docs, dict):
            docs = [docs]
        if not docs:
            return None
        # Fetch first matching votering document
        time.sleep(REQUEST_DELAY)
        dok_id = docs[0].get("dok_id", "")
        resp = api_get(f"/dokument/{dok_id}")
        if resp:
            html = resp.get("dokument", {}).get("html", "")
            return (html, dok_id) if html else None
        return None

    else:
        # Fetch prot listing for this rm, then search for betänkande mention
        data = api_get(
            "/dokumentlista/",
            params={"doktyp": "prot", "rm": rm, "sort": "datum", "sortorder": "asc"},
        )
        if not data:
            return None
        docs = data.get("dokumentlista", {}).get("dokument", [])
        if isinstance(docs, dict):
            docs = [docs]

        # Search through protocols for one mentioning this betänkande
        for doc in docs[:20]:  # limit to first 20 protocols in session
            time.sleep(REQUEST_DELAY)
            dok_id = doc.get("dok_id", "")
            resp = api_get(f"/dokument/{dok_id}")
            if not resp:
                continue
            text = resp.get("dokument", {}).get("text", "") or ""
            # Check if this protocol mentions the betänkande
            bet_short = bet_beteckning.split(":")[-1] if ":" in bet_beteckning else bet_beteckning
            if bet_short.lower() in text.lower():
                return (text, dok_id)

        return None


def run_import(from_year: int, to_year: int, dry_run: bool = False) -> None:
    """Run the historical import from rinfo.gov.se."""
    repo_path = Path(__file__).resolve().parent.parent.parent
    repo = git.Repo(repo_path)

    parser = SFSParser()
    prot_parser = ProtParser()
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

                # Resolve votering from protocol
                bet_beteckning = parsed.get("forarbete_bet", "")
                rm = str(year) if year <= 1974 else f"{year}/{str(year + 1)[-2:]}"
                votering_str = "ej tillgänglig"
                riksdagen_dok = "okänd"
                if bet_beteckning and not dry_run:
                    prot_result = fetch_protokoll_section(bet_beteckning, rm)
                    if prot_result:
                        prot_text, riksdagen_dok = prot_result
                        votering = prot_parser.parse_votering(prot_text, rm)
                        votering_str = format_votering_for_commit(votering)

                create_commit(
                    repo=repo,
                    file_path=file_path,
                    content=markdown,
                    sfs_number=parsed["sfs"],
                    description=parsed.get("titel", "Ny författning"),
                    ikraftträdande=parsed.get("ikraftträdande", f"{year}-01-01"),
                    proposition=parsed.get("forarbete_prop", "okänd"),
                    utskott=parsed.get("forarbete_bet", "okänd"),
                    votering=votering_str,
                    riksdagen_dok=riksdagen_dok,
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
        description="Import Swedish law into git corpus"
    )
    parser.add_argument(
        "--source",
        choices=["rkrattsbaser", "rinfo"],
        default="rkrattsbaser",
        help="Data source (default: rkrattsbaser)",
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=1825,
        help="Start year (only used with --source rinfo)",
    )
    parser.add_argument(
        "--to-year",
        type=int,
        default=date.today().year,
        help="End year (only used with --source rinfo)",
    )
    parser.add_argument(
        "--sfs",
        action="append",
        metavar="YYYY:NNN",
        dest="sfs_filter",
        help="Limit to specific SFS number(s) (repeatable, only with rkrattsbaser)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes",
    )
    args = parser.parse_args()

    if args.source == "rinfo":
        run_import(args.from_year, args.to_year, args.dry_run)
    else:
        run_import_rkrattsbaser(dry_run=args.dry_run, sfs_filter=args.sfs_filter)


if __name__ == "__main__":
    main()
