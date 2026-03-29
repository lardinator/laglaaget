# historical_import.py Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `run_import_rkrattsbaser()` to `historical_import.py` that uses `RkrattsbaserScraper` + `SFSParser.parse_from_scraper()` instead of the defunct `rinfo.gov.se` API.

**Architecture:** Add a new function alongside the existing `run_import()` (which is left intact). Update `main()` to route between them via `--source` flag. Reuses all existing helpers: `create_commit()`, `create_annual_tags()`, `determine_file_path()`, `fetch_protokoll_section()`, `format_votering_for_commit()`.

**Tech Stack:** Python 3.11+, `gitpython`, `requests`, `pytest`, `unittest.mock`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/import/historical_import.py` | Modify | Add `run_import_rkrattsbaser()`, `sort_key_for_sfs()`, update `main()` |
| `tests/test_historical_import.py` | Create | Unit tests, mocked scraper/git, no network |

---

## Task 1: sort_key_for_sfs() + run_import_rkrattsbaser() skeleton

**Files:**
- Modify: `scripts/import/historical_import.py`
- Create: `tests/test_historical_import.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_historical_import.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "import"))

from unittest.mock import MagicMock, patch
from historical_import import sort_key_for_sfs


class TestSortKeyForSfs:
    def test_date_returned_as_is(self):
        m = MagicMock()
        m.ikraftträdande = "1965-01-01"
        assert sort_key_for_sfs(m) == "1965-01-01"

    def test_none_returns_sentinel(self):
        m = MagicMock()
        m.ikraftträdande = None
        assert sort_key_for_sfs(m) == "9999-99-99"

    def test_none_sorts_after_real_dates(self):
        dates = ["2020-01-01", "9999-99-99", "1965-01-01"]
        assert sorted(dates) == ["1965-01-01", "2020-01-01", "9999-99-99"]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/alexandromartini/Documents/dev/lagl-get
python -m pytest tests/test_historical_import.py::TestSortKeyForSfs -v
```

Expected: `ImportError: cannot import name 'sort_key_for_sfs'`

- [ ] **Step 3: Add `sort_key_for_sfs()` and `run_import_rkrattsbaser()` skeleton**

Add these imports at the top of `scripts/import/historical_import.py` (after existing imports):

```python
from rkrattsbaser_scraper import RkrattsbaserScraper, SFSMetadata
from sfs_parser import SFSParser
```

Note: `SFSParser` is already imported. Only add `RkrattsbaserScraper, SFSMetadata` to the rkrattsbaser import.

Add these two functions anywhere after `create_annual_tags()`:

```python
def sort_key_for_sfs(metadata: "SFSMetadata") -> str:
    """Return sortable key: ikraftträdande ISO date, or '9999-99-99' for None."""
    return metadata.ikraftträdande or "9999-99-99"


def run_import_rkrattsbaser(
    dry_run: bool = False,
    sfs_filter: list[str] | None = None,
) -> None:
    """Run historical import using RkrattsbaserScraper (replaces defunct rinfo.gov.se)."""
    raise NotImplementedError
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_historical_import.py::TestSortKeyForSfs -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/historical_import.py tests/test_historical_import.py
git commit -m "feat: add sort_key_for_sfs() and run_import_rkrattsbaser() skeleton"
```

---

## Task 2: run_import_rkrattsbaser() implementation

**Files:**
- Modify: `scripts/import/historical_import.py`
- Modify: `tests/test_historical_import.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_historical_import.py`:

```python
from historical_import import run_import_rkrattsbaser
from rkrattsbaser_scraper import SFSMetadata, SFSAndring, SFSText


class TestRunImportRkrattsbaser:
    def _make_metadata(self, sfs="1962:700"):
        return SFSMetadata(
            sfs=sfs,
            titel=f"Brottsbalk ({sfs})",
            departement="Justitiedepartementet L5",
            ikraftträdande="1965-01-01",
            forarbete_prop="1962:10",
            forarbete_bet="1LU 1962:42",
        )

    def _make_text(self, sfs="1962:700"):
        return SFSText(sfs=sfs, text="1 § Brott är...", andring_intom=None)

    def test_dry_run_calls_no_git(self):
        meta = self._make_metadata()
        text = self._make_text()

        mock_scraper = MagicMock()
        mock_scraper.enumerate_sfs_numbers.return_value = ["1962:700"]
        mock_scraper.fetch_metadata.return_value = meta
        mock_scraper.fetch_text.return_value = text

        with patch("historical_import.RkrattsbaserScraper", return_value=mock_scraper), \
             patch("historical_import.git.Repo") as mock_repo, \
             patch("historical_import.fetch_protokoll_section", return_value=None):
            run_import_rkrattsbaser(dry_run=True)

        mock_repo.return_value.index.commit.assert_not_called()

    def test_sfs_filter_limits_processing(self):
        mock_scraper = MagicMock()
        mock_scraper.fetch_metadata.return_value = self._make_metadata("2017:310")
        mock_scraper.fetch_text.return_value = self._make_text("2017:310")

        with patch("historical_import.RkrattsbaserScraper", return_value=mock_scraper), \
             patch("historical_import.git.Repo"), \
             patch("historical_import.fetch_protokoll_section", return_value=None):
            run_import_rkrattsbaser(dry_run=True, sfs_filter=["2017:310"])

        mock_scraper.enumerate_sfs_numbers.assert_not_called()
        mock_scraper.fetch_metadata.assert_called_once_with("2017:310")

    def test_skips_none_metadata(self):
        mock_scraper = MagicMock()
        mock_scraper.enumerate_sfs_numbers.return_value = ["9999:1"]
        mock_scraper.fetch_metadata.return_value = None

        with patch("historical_import.RkrattsbaserScraper", return_value=mock_scraper), \
             patch("historical_import.git.Repo"), \
             patch("historical_import.fetch_protokoll_section", return_value=None):
            run_import_rkrattsbaser(dry_run=True)

        mock_scraper.fetch_text.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_historical_import.py::TestRunImportRkrattsbaser -v
```

Expected: `NotImplementedError`

- [ ] **Step 3: Implement `run_import_rkrattsbaser()`**

Replace the `raise NotImplementedError` stub with:

```python
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
    entries: list[tuple[SFSMetadata, str]] = []
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
            ikraft = parsed.get("ikraftträdande") or ""
            year = int(ikraft[:4]) if ikraft and len(ikraft) >= 4 else 0
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
        years = [int(m.ikraftträdande[:4]) for m, _ in entries if m.ikraftträdande]
        if years:
            create_annual_tags(repo, min(years), max(years))

    logger.info("Import complete. Total commits: %d", total_commits)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_historical_import.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -q
```

Expected: all tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add scripts/import/historical_import.py tests/test_historical_import.py
git commit -m "feat: implement run_import_rkrattsbaser() using RkrattsbaserScraper"
```

---

## Task 3: Update main() with --source and --sfs flags

**Files:**
- Modify: `scripts/import/historical_import.py`
- Modify: `tests/test_historical_import.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_historical_import.py`:

```python
import argparse
from historical_import import main


class TestMain:
    def test_default_source_is_rkrattsbaser(self):
        with patch("historical_import.run_import_rkrattsbaser") as mock_run, \
             patch("sys.argv", ["historical_import.py", "--dry-run"]):
            main()
        mock_run.assert_called_once_with(dry_run=True, sfs_filter=None)

    def test_source_rinfo_calls_run_import(self):
        with patch("historical_import.run_import") as mock_run, \
             patch("sys.argv", ["historical_import.py", "--source", "rinfo", "--dry-run"]):
            main()
        mock_run.assert_called_once()

    def test_sfs_filter_passed_to_rkrattsbaser(self):
        with patch("historical_import.run_import_rkrattsbaser") as mock_run, \
             patch("sys.argv", ["historical_import.py", "--dry-run", "--sfs", "1962:700", "--sfs", "2017:310"]):
            main()
        mock_run.assert_called_once_with(dry_run=True, sfs_filter=["1962:700", "2017:310"])
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_historical_import.py::TestMain -v
```

Expected: test failures (old main() doesn't have --source or --sfs)

- [ ] **Step 3: Update `main()`**

Replace the existing `main()` function in `scripts/import/historical_import.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_historical_import.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -q
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/import/historical_import.py tests/test_historical_import.py
git commit -m "feat: add --source and --sfs flags to historical_import main()"
```

---

## Self-Review Checklist

- [x] `sort_key_for_sfs()` — Task 1
- [x] `run_import_rkrattsbaser()` uses scraper, sorts chronologically, skips None metadata — Task 2
- [x] `run_import_rkrattsbaser()` calls `create_commit()` correctly — Task 2
- [x] `run_import_rkrattsbaser()` supports `sfs_filter` — Task 2
- [x] `main()` routes --source rkrattsbaser / rinfo — Task 3
- [x] `main()` passes --sfs filter — Task 3
- [x] Original `run_import()` unmodified — verified by full test run
