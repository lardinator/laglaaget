from unittest.mock import patch, MagicMock
import requests

from rkrattsbaser_scraper import SFSMetadata, SFSAndring, SFSText, RkrattsbaserScraper


class TestDataclasses:
    def test_sfs_metadata_defaults(self):
        m = SFSMetadata(sfs="1962:700", titel="Brottsbalk (1962:700)", departement="Justitiedepartementet L5")
        assert m.ikraftträdande is None
        assert m.andringar == []
        assert m.forarbete_prop is None

    def test_sfs_andring_defaults(self):
        a = SFSAndring(sfs="2026:253")
        assert a.rubrik is None
        assert a.forarbete_prop is None

    def test_sfs_text_defaults(self):
        t = SFSText(sfs="1962:700", text="1 § Brott är...")
        assert t.andring_intom is None
        assert t.uppdaterad is None

    def test_scraper_instantiates(self):
        s = RkrattsbaserScraper()
        assert s.BASE_URL == "https://rkrattsbaser.gov.se"


class TestParseSfsList:
    LIST_PAGE_HTML = """
    <html><body>
    <div class="search-hit">
      <div class="search-hit-info-num">SFS-nummer: 1962:700</div>
    </div>
    <div class="search-hit">
      <div class="search-hit-info-num">SFS-nummer: 1962:701</div>
    </div>
    <div class="search-hit">
      <div class="search-hit-info-num">SFS-nummer: 1949:381</div>
    </div>
    </body></html>
    """

    EMPTY_PAGE_HTML = """
    <html><body>
    <p>Inga träffar</p>
    </body></html>
    """

    def test_extracts_sfs_numbers_from_page(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_sfs_list_page(self.LIST_PAGE_HTML)
        assert result == ["1962:700", "1962:701", "1949:381"]

    def test_empty_page_returns_empty_list(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_sfs_list_page(self.EMPTY_PAGE_HTML)
        assert result == []

    def test_preserves_order(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_sfs_list_page(self.LIST_PAGE_HTML)
        assert result[0] == "1962:700"
        assert result[2] == "1949:381"


class TestParseMetadata:
    METADATA_HTML = """
    <html><body>
    <div class="result-inner-box bold">
      SFS-nummer · 1962:700 · <a href="/sfst?bet=1962:700">Visa fulltext</a>
    </div>
    <div class="result-inner-box">
      <span class="bold">Brottsbalk (1962:700)</span>
    </div>
    <div class="result-inner-box">
      <span class="bold">Departement:</span> Justitiedepartementet L5
    </div>
    <div class="result-inner-box">
      <span class="bold">Utfärdad:</span> 1962-12-21
    </div>
    <div class="result-inner-box">
      <span class="bold">Ikraft:</span> 1965-01-01
    </div>
    <div class="result-inner-box">
      <span class="bold">Förarbeten:</span> Prop. 1962:10; 1LU 1962:42, 43; Rskr 1962:390
    </div>
    </body></html>
    """

    MODERN_HTML = """
    <html><body>
    <div class="result-inner-box bold">
      SFS-nummer · 2017:310 · <a href="/sfst?bet=2017:310">Visa fulltext</a>
    </div>
    <div class="result-inner-box">
      <span class="bold">Lag om framtidsfullmakter (2017:310)</span>
    </div>
    <div class="result-inner-box">
      <span class="bold">Departement:</span> Justitiedepartementet L2
    </div>
    <div class="result-inner-box">
      <span class="bold">Ikraft:</span> 2017-07-01
    </div>
    <div class="result-inner-box">
      <span class="bold">Förarbeten:</span> Prop. 2016/17:30, bet. 2016/17:CU11, rskr. 2016/17:221
    </div>
    </body></html>
    """

    NO_FORARBETEN_HTML = """
    <html><body>
    <div class="result-inner-box bold">
      SFS-nummer · 1949:381 · <a href="/sfst?bet=1949:381">Visa fulltext</a>
    </div>
    <div class="result-inner-box">
      <span class="bold">Föräldrabalk (1949:381)</span>
    </div>
    <div class="result-inner-box">
      <span class="bold">Departement:</span> Justitiedepartementet L2
    </div>
    </body></html>
    """

    def test_basic_fields(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("1962:700", self.METADATA_HTML)
        assert result is not None
        assert result.sfs == "1962:700"
        assert result.titel == "Brottsbalk (1962:700)"
        assert result.departement == "Justitiedepartementet L5"
        assert result.ikraftträdande == "1965-01-01"
        assert result.utfärdad == "1962-12-21"

    def test_old_forarbeten_parsed(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("1962:700", self.METADATA_HTML)
        assert result.forarbete_prop == "1962:10"
        assert result.forarbete_rskr == "1962:390"
        assert result.forarbete_bet is None

    def test_modern_forarbeten_parsed(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("2017:310", self.MODERN_HTML)
        assert result.forarbete_prop == "2016/17:30"
        assert result.forarbete_bet == "2016/17:CU11"
        assert result.forarbete_rskr == "2016/17:221"

    def test_no_forarbeten_returns_none_fields(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("1949:381", self.NO_FORARBETEN_HTML)
        assert result is not None
        assert result.forarbete_prop is None
        assert result.forarbete_bet is None
        assert result.forarbete_rskr is None
        assert result.ikraftträdande is None

    def test_empty_html_returns_none(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("9999:1", "<html><body></body></html>")
        assert result is None


class TestParseAndringar:
    HTML_WITH_ANDRINGAR = """
    <html><body>
    <div class="result-inner-box bold">SFS-nummer · 1962:700</div>
    <div class="result-inner-box"><span class="bold">Brottsbalk (1962:700)</span></div>
    <div class="result-inner-box"><span class="bold">Departement:</span> Justitiedepartementet L5</div>
    <div class="result-inner-box"><span class="bold">Ikraft:</span> 1965-01-01</div>

    <div class="result-inner-sub-box-container">
      <div class="result-inner-sub-box-header">Ändring, SFS 1965:280</div>
      <div class="result-inner-sub-box">
        <span class="bold">Rubrik:</span> Lag om ändring i brottsbalken
      </div>
      <div class="result-inner-sub-box">
        <span class="bold">Omfattning:</span> ändr. 20 kap 4 §
      </div>
      <div class="result-inner-sub-box">
        <span class="bold">Ikraftträdande:</span> 1965-07-01
      </div>
    </div>

    <div class="result-inner-sub-box-container">
      <div class="result-inner-sub-box-header">Ändring, SFS 2026:253</div>
      <div class="result-inner-sub-box">
        <span class="bold">Förarbeten:</span> Prop. 2025/26:34, bet. 2025/26:JuU8, rskr. 2025/26:96
      </div>
      <div class="result-inner-sub-box">
        <span class="bold">Ikraftträdande:</span> 2026-04-15
      </div>
    </div>
    </body></html>
    """

    def test_amendment_count(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("1962:700", self.HTML_WITH_ANDRINGAR)
        assert result is not None
        assert len(result.andringar) == 2

    def test_first_amendment_fields(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("1962:700", self.HTML_WITH_ANDRINGAR)
        a = result.andringar[0]
        assert a.sfs == "1965:280"
        assert a.rubrik == "Lag om ändring i brottsbalken"
        assert a.omfattning == "ändr. 20 kap 4 §"
        assert a.ikraftträdande == "1965-07-01"

    def test_second_amendment_forarbeten(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("1962:700", self.HTML_WITH_ANDRINGAR)
        a = result.andringar[1]
        assert a.sfs == "2026:253"
        assert a.forarbete_prop == "2025/26:34"
        assert a.forarbete_bet == "2025/26:JuU8"
        assert a.forarbete_rskr == "2025/26:96"
        assert a.ikraftträdande == "2026-04-15"

    def test_no_amendments_returns_empty_list(self):
        html = """<html><body>
        <div class="result-inner-box bold">SFS-nummer · 2017:310</div>
        <div class="result-inner-box"><span class="bold">Lag om framtidsfullmakter (2017:310)</span></div>
        <div class="result-inner-box"><span class="bold">Departement:</span> Justitiedepartementet L2</div>
        </body></html>"""
        scraper = RkrattsbaserScraper()
        result = scraper._parse_metadata_html("2017:310", html)
        assert result.andringar == []


class TestParseText:
    TEXT_HTML = """
    <html>
    <head>
      <meta id="rattsinfo-edited" content="2026-03-23 11:42:51" />
    </head>
    <body>
    <div class="result-inner-box">Ändring införd: t.o.m. SFS 2026:253</div>
    <div class="result-box-text body-text">
FÖRSTA AVDELNINGEN

1 kap. Om brott och brottspåföljder

1 &#167; Brott &#228;r en g&#228;rning som &#228;r beskriven i denna balk eller i annan lag
eller f&#246;rfattning och f&#246;r vilken p&#229;f&#246;ljd som s&#228;gs nedan &#228;r f&#246;reskriven.
    </div>
    </body></html>
    """

    EMPTY_HTML = "<html><body></body></html>"

    def test_text_extracted(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_text_html("1962:700", self.TEXT_HTML)
        assert result is not None
        assert "FÖRSTA AVDELNINGEN" in result.text
        assert "1 § Brott är" in result.text

    def test_html_entities_decoded(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_text_html("1962:700", self.TEXT_HTML)
        # &#228; = ä, &#167; = §, &#246; = ö, &#229; = å
        assert "är" in result.text
        assert "§" in result.text
        assert "för" in result.text

    def test_andring_intom_parsed(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_text_html("1962:700", self.TEXT_HTML)
        assert result.andring_intom == "t.o.m. SFS 2026:253"

    def test_uppdaterad_parsed(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_text_html("1962:700", self.TEXT_HTML)
        assert result.uppdaterad == "2026-03-23 11:42:51"

    def test_no_text_div_returns_none(self):
        scraper = RkrattsbaserScraper()
        result = scraper._parse_text_html("1962:700", self.EMPTY_HTML)
        assert result is None


class TestHttpLayer:
    def test_get_returns_html_on_200(self):
        scraper = RkrattsbaserScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>ok</html>"
        with patch("rkrattsbaser_scraper.requests.get", return_value=mock_resp) as mock_get:
            result = scraper._get("/sfsr", params={"bet": "1962:700"})
        assert result == "<html>ok</html>"
        mock_get.assert_called_once()

    def test_get_returns_none_on_404(self):
        scraper = RkrattsbaserScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = requests.HTTPError("404")
        http_err.response = MagicMock()
        http_err.response.status_code = 404
        mock_resp.raise_for_status.side_effect = http_err
        with patch("rkrattsbaser_scraper.requests.get", return_value=mock_resp):
            result = scraper._get("/sfsr", params={"bet": "9999:1"})
        assert result is None

    def test_fetch_metadata_returns_none_on_404(self):
        scraper = RkrattsbaserScraper()
        scraper.REQUEST_DELAY = 0
        with patch.object(scraper, "_get", return_value=None):
            result = scraper.fetch_metadata("9999:1")
        assert result is None

    def test_fetch_text_returns_none_on_404(self):
        scraper = RkrattsbaserScraper()
        scraper.REQUEST_DELAY = 0
        with patch.object(scraper, "_get", return_value=None):
            result = scraper.fetch_text("9999:1")
        assert result is None

    def test_enumerate_returns_empty_on_first_empty_page(self):
        scraper = RkrattsbaserScraper()
        scraper.REQUEST_DELAY = 0
        with patch.object(scraper, "_get", return_value="<html><body></body></html>"):
            result = scraper.enumerate_sfs_numbers()
        assert result == []
