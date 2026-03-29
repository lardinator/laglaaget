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


from historical_import import main


class TestMain:
    def test_default_source_is_rkrattsbaser(self):
        with patch("historical_import.run_import_rkrattsbaser") as mock_run, \
             patch("sys.argv", ["historical_import.py", "--dry-run"]):
            main()
        mock_run.assert_called_once_with(dry_run=True, sfs_filter=None)

    def test_source_rinfo_calls_run_import(self):
        with patch("historical_import.run_import") as mock_run, \
             patch("sys.argv", ["historical_import.py", "--source", "rinfo", "--dry-run", "--from-year", "2000"]):
            main()
        mock_run.assert_called_once()

    def test_sfs_filter_passed_to_rkrattsbaser(self):
        with patch("historical_import.run_import_rkrattsbaser") as mock_run, \
             patch("sys.argv", ["historical_import.py", "--dry-run", "--sfs", "1962:700", "--sfs", "2017:310"]):
            main()
        mock_run.assert_called_once_with(dry_run=True, sfs_filter=["1962:700", "2017:310"])
