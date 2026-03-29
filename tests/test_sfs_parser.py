import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "import"))

from sfs_parser import SFSParser
from rkrattsbaser_scraper import SFSMetadata, SFSAndring, SFSText


class TestParseFromScraper:
    METADATA = SFSMetadata(
        sfs="1962:700",
        titel="Brottsbalk (1962:700)",
        departement="Justitiedepartementet L5",
        ikraftträdande="1965-01-01",
        utfärdad="1962-12-21",
        forarbete_prop="1962:10",
        forarbete_bet="1LU 1962:42",
        forarbete_rskr="1962:390",
        andringar=[
            SFSAndring(
                sfs="2026:253",
                rubrik="Lag om ändring i brottsbalken",
                ikraftträdande="2026-04-15",
                forarbete_prop="2025/26:34",
            )
        ],
    )

    TEXT = SFSText(
        sfs="1962:700",
        text="FÖRSTA AVDELNINGEN\n\n1 § Brott är...",
        andring_intom="t.o.m. SFS 2026:253",
        uppdaterad="2026-03-23 11:42:51",
    )

    def test_sfs_field(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["sfs"] == "1962:700"

    def test_titel_field(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["titel"] == "Brottsbalk (1962:700)"

    def test_departement_field(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["departement"] == "Justitiedepartementet L5"

    def test_ikraftträdande_field(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["ikraftträdande"] == "1965-01-01"

    def test_utfärdad_field(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["utfärdad"] == "1962-12-21"

    def test_forarbeten_fields(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["forarbete_prop"] == "1962:10"
        assert result["forarbete_bet"] == "1LU 1962:42"
        assert result["forarbete_rskr"] == "1962:390"

    def test_body_text_from_sfstext(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["body_text"] == "FÖRSTA AVDELNINGEN\n\n1 § Brott är..."

    def test_body_text_empty_when_no_text(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, None)
        assert result["body_text"] == ""

    def test_andringar_list(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert len(result["andringar"]) == 1
        assert result["andringar"][0].sfs == "2026:253"

    def test_kapitel_is_empty(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["kapitel"] == []

    def test_kortnamn_is_none(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["kortnamn"] is None

    def test_upphävd_is_none(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["upphävd"] is None


class TestTypHärledning:
    def test_lag_is_default(self):
        parser = SFSParser()
        from rkrattsbaser_scraper import SFSMetadata
        m = SFSMetadata(sfs="1962:700", titel="Brottsbalk (1962:700)", departement="Justitiedepartementet L5")
        result = parser.parse_from_scraper(m, None)
        assert result["typ"] == "lag"

    def test_förordning_detected_from_titel(self):
        parser = SFSParser()
        from rkrattsbaser_scraper import SFSMetadata
        m = SFSMetadata(sfs="1998:1252", titel="Förordning (1998:1252) om områdesskydd", departement="Miljödepartementet")
        result = parser.parse_from_scraper(m, None)
        assert result["typ"] == "förordning"

    def test_grundlag_detected_from_sfs(self):
        parser = SFSParser()
        from rkrattsbaser_scraper import SFSMetadata
        m = SFSMetadata(sfs="1974:152", titel="Kungörelse (1974:152) om beslutad ny regeringsform", departement="Justitiedepartementet L6")
        result = parser.parse_from_scraper(m, None)
        assert result["typ"] == "grundlag"

    def test_all_grundlag_sfs_numbers(self):
        parser = SFSParser()
        from rkrattsbaser_scraper import SFSMetadata
        for sfs in ["1974:152", "1974:713", "1949:105", "1810:926"]:
            m = SFSMetadata(sfs=sfs, titel=f"Lag ({sfs})", departement="Justitiedepartementet")
            result = parser.parse_from_scraper(m, None)
            assert result["typ"] == "grundlag", f"Expected grundlag for {sfs}"


class TestToMarkdownWithBodyText:
    def _make_parsed(self):
        from rkrattsbaser_scraper import SFSMetadata, SFSAndring, SFSText
        metadata = SFSMetadata(
            sfs="1962:700",
            titel="Brottsbalk (1962:700)",
            departement="Justitiedepartementet L5",
            ikraftträdande="1965-01-01",
            forarbete_prop="1962:10",
            forarbete_rskr="1962:390",
            andringar=[
                SFSAndring(
                    sfs="2026:253",
                    rubrik="Lag om ändring i brottsbalken",
                    ikraftträdande="2026-04-15",
                )
            ],
        )
        text = SFSText(
            sfs="1962:700",
            text="FÖRSTA AVDELNINGEN\n\n1 § Brott är...",
            andring_intom="t.o.m. SFS 2026:253",
        )
        return SFSParser().parse_from_scraper(metadata, text)

    def test_body_text_in_markdown(self):
        parser = SFSParser()
        parsed = self._make_parsed()
        md = parser.to_markdown(parsed)
        assert "FÖRSTA AVDELNINGEN" in md
        assert "1 § Brott är..." in md

    def test_forarbete_prop_in_frontmatter(self):
        parser = SFSParser()
        parsed = self._make_parsed()
        md = parser.to_markdown(parsed)
        assert "1962:10" in md

    def test_ändringshistorik_in_frontmatter(self):
        parser = SFSParser()
        parsed = self._make_parsed()
        md = parser.to_markdown(parsed)
        assert "2026:253" in md

    def test_andring_intom_in_frontmatter(self):
        parser = SFSParser()
        parsed = self._make_parsed()
        md = parser.to_markdown(parsed)
        assert "t.o.m. SFS 2026:253" in md

    def test_empty_body_text_no_garbage(self):
        parser = SFSParser()
        from rkrattsbaser_scraper import SFSMetadata
        m = SFSMetadata(sfs="1962:700", titel="Brottsbalk (1962:700)", departement="Justitiedepartementet L5")
        parsed = parser.parse_from_scraper(m, None)
        md = parser.to_markdown(parsed)
        assert "None" not in md
        assert "body_text" not in md
