# RkrattsbaserScraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `RkrattsbaserScraper` — a class that fetches Swedish law metadata, amendment history, and consolidated text from `rkrattsbaser.gov.se`, replacing the defunct `rinfo.gov.se`.

**Architecture:** Three dataclasses (`SFSMetadata`, `SFSAndring`, `SFSText`) in `scripts/import/rkrattsbaser_scraper.py`. The `RkrattsbaserScraper` class has a thin HTTP layer (requests + retry) and three public methods: `enumerate_sfs_numbers()`, `fetch_metadata()`, `fetch_text()`. All HTML parsing uses BeautifulSoup4. Tests use inline HTML fixtures — no network calls.

**Tech Stack:** Python 3.11+, `requests`, `beautifulsoup4`, `re`, `dataclasses`, `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/import/rkrattsbaser_scraper.py` | Create | Dataclasses + `RkrattsbaserScraper` class |
| `tests/test_rkrattsbaser_scraper.py` | Create | Unit tests with HTML fixtures, no network |

---

## Task 1: Dataclasses + scraper skeleton

**Files:**
- Create: `scripts/import/rkrattsbaser_scraper.py`
- Create: `tests/test_rkrattsbaser_scraper.py`

- [ ] **Step 1: Write failing tests for dataclasses**

```python
# tests/test_rkrattsbaser_scraper.py
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/alexandromartini/Documents/dev/lagl-get
python -m pytest tests/test_rkrattsbaser_scraper.py::TestDataclasses -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create the file with dataclasses and skeleton**

```python
# scripts/import/rkrattsbaser_scraper.py
"""Scraper for rkrattsbaser.gov.se — Swedish legal database.

Fetches consolidated law texts, metadata, and amendment history
as replacement for the defunct rinfo.gov.se (Lagrummet).

Endpoints used:
  /sfsr/adv?sort=asc&page=N  — paginated list of all SFS numbers
  /sfsr?bet=YYYY:NNN          — metadata + amendment register
  /sfst?bet=YYYY:NNN          — consolidated law text
"""

import logging
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SFSAndring:
    sfs: str
    rubrik: str | None = None
    omfattning: str | None = None
    ikraftträdande: str | None = None
    forarbete_prop: str | None = None
    forarbete_bet: str | None = None
    forarbete_rskr: str | None = None


@dataclass
class SFSMetadata:
    sfs: str
    titel: str
    departement: str
    ikraftträdande: str | None = None
    utfärdad: str | None = None
    forarbete_prop: str | None = None
    forarbete_bet: str | None = None
    forarbete_rskr: str | None = None
    andringar: list[SFSAndring] = field(default_factory=list)


@dataclass
class SFSText:
    sfs: str
    text: str
    andring_intom: str | None = None
    uppdaterad: str | None = None


class RkrattsbaserScraper:
    """Fetch Swedish law data from rkrattsbaser.gov.se."""

    BASE_URL = "https://rkrattsbaser.gov.se"
    REQUEST_DELAY = 1.0
    USER_AGENT = "Lagläget/1.0 (github.com/lardinator/lagl-get)"

    def enumerate_sfs_numbers(self) -> list[str]:
        """Fetch all SFS numbers via paginated list (~372 pages)."""
        raise NotImplementedError

    def fetch_metadata(self, sfs: str) -> SFSMetadata | None:
        """Fetch metadata + full amendment register for one SFS number."""
        raise NotImplementedError

    def fetch_text(self, sfs: str) -> SFSText | None:
        """Fetch consolidated law text for one SFS number."""
        raise NotImplementedError
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestDataclasses -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/rkrattsbaser_scraper.py tests/test_rkrattsbaser_scraper.py
git commit -m "feat: add RkrattsbaserScraper skeleton and dataclasses"
```

---

## Task 2: enumerate_sfs_numbers() parser

**Files:**
- Modify: `scripts/import/rkrattsbaser_scraper.py`
- Modify: `tests/test_rkrattsbaser_scraper.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_rkrattsbaser_scraper.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseSfsList -v
```

Expected: `AttributeError: 'RkrattsbaserScraper' object has no attribute '_parse_sfs_list_page'`

- [ ] **Step 3: Implement `_parse_sfs_list_page`**

Add to `RkrattsbaserScraper` class:

```python
    def _parse_sfs_list_page(self, html: str) -> list[str]:
        """Parse one page of the /sfsr/adv listing. Returns SFS numbers."""
        soup = BeautifulSoup(html, "html.parser")
        result = []
        for div in soup.find_all("div", class_="search-hit-info-num"):
            text = div.get_text(strip=True)
            # "SFS-nummer: 1962:700"
            m = re.search(r"SFS-nummer:\s*(\d{4}:\w+)", text)
            if m:
                result.append(m.group(1))
        return result
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseSfsList -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/rkrattsbaser_scraper.py tests/test_rkrattsbaser_scraper.py
git commit -m "feat: add _parse_sfs_list_page()"
```

---

## Task 3: fetch_metadata() — base metadata parser

**Files:**
- Modify: `scripts/import/rkrattsbaser_scraper.py`
- Modify: `tests/test_rkrattsbaser_scraper.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_rkrattsbaser_scraper.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseMetadata -v
```

Expected: `AttributeError: 'RkrattsbaserScraper' object has no attribute '_parse_metadata_html'`

- [ ] **Step 3: Implement `_parse_metadata_html`**

Add these class-level patterns and method to `RkrattsbaserScraper`:

```python
    # Förarbeten regex patterns
    _RE_PROP = re.compile(r"Prop\.\s*(\d{4}(?:/\d{2})?:\d+)", re.IGNORECASE)
    _RE_BET  = re.compile(r"bet\.\s*(\d{4}(?:/\d{2})?:\w+)", re.IGNORECASE)
    _RE_RSKR = re.compile(r"[Rr]skr\.?\s*(\d{4}(?:/\d{2})?:\d+)")

    def _parse_metadata_html(self, sfs: str, html: str) -> SFSMetadata | None:
        """Parse /sfsr?bet=YYYY:NNN HTML into SFSMetadata."""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        boxes = soup.find_all("div", class_="result-inner-box")
        if not boxes:
            return None

        titel = departement = ikraftträdande = utfärdad = None
        forarbete_prop = forarbete_bet = forarbete_rskr = None

        for box in boxes:
            text = box.get_text(separator=" ", strip=True)
            bold = box.find("span", class_="bold")
            bold_text = bold.get_text(strip=True) if bold else ""

            if bold_text and not bold_text.endswith(":") and "SFS-nummer" not in text:
                # Title box: bold span contains the law name
                if "(" in bold_text and ":" in bold_text:
                    titel = bold_text
            elif "Departement:" in text:
                departement = text.replace("Departement:", "").strip()
            elif "Ikraft:" in text:
                ikraftträdande = text.replace("Ikraft:", "").strip()
            elif "Utfärdad:" in text:
                utfärdad = text.replace("Utfärdad:", "").strip()
            elif "Förarbeten:" in text:
                forarbete_text = text.replace("Förarbeten:", "")
                m = self._RE_PROP.search(forarbete_text)
                if m:
                    forarbete_prop = m.group(1)
                m = self._RE_BET.search(forarbete_text)
                if m:
                    forarbete_bet = m.group(1)
                m = self._RE_RSKR.search(forarbete_text)
                if m:
                    forarbete_rskr = m.group(1)

        if not titel or not departement:
            return None

        return SFSMetadata(
            sfs=sfs,
            titel=titel,
            departement=departement,
            ikraftträdande=ikraftträdande,
            utfärdad=utfärdad,
            forarbete_prop=forarbete_prop,
            forarbete_bet=forarbete_bet,
            forarbete_rskr=forarbete_rskr,
        )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseMetadata -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/rkrattsbaser_scraper.py tests/test_rkrattsbaser_scraper.py
git commit -m "feat: add _parse_metadata_html() for base metadata"
```

---

## Task 4: fetch_metadata() — amendment parser

**Files:**
- Modify: `scripts/import/rkrattsbaser_scraper.py`
- Modify: `tests/test_rkrattsbaser_scraper.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_rkrattsbaser_scraper.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseAndringar -v
```

Expected: `AssertionError` — `andringar == []` (not yet parsed from containers)

- [ ] **Step 3: Update `_parse_metadata_html` to parse amendments**

In `_parse_metadata_html`, after the `boxes` loop and before the `if not titel or not departement` guard, add:

```python
        # Parse amendments from sub-box containers
        andringar: list[SFSAndring] = []
        for container in soup.find_all("div", class_="result-inner-sub-box-container"):
            header = container.find("div", class_="result-inner-sub-box-header")
            if not header:
                continue
            header_text = header.get_text(strip=True)
            sfs_match = re.search(r"SFS\s+(\d{4}:\d+)", header_text)
            if not sfs_match:
                continue
            andring_sfs = sfs_match.group(1)

            andring = SFSAndring(sfs=andring_sfs)
            for sub in container.find_all("div", class_="result-inner-sub-box"):
                sub_text = sub.get_text(separator=" ", strip=True)
                if sub_text.startswith("Rubrik:"):
                    andring.rubrik = sub_text.replace("Rubrik:", "").strip()
                elif sub_text.startswith("Omfattning:"):
                    andring.omfattning = sub_text.replace("Omfattning:", "").strip()
                elif sub_text.startswith("Ikraftträdande:"):
                    andring.ikraftträdande = sub_text.replace("Ikraftträdande:", "").strip()
                elif "Förarbeten:" in sub_text:
                    fa = sub_text.replace("Förarbeten:", "")
                    m = self._RE_PROP.search(fa)
                    if m:
                        andring.forarbete_prop = m.group(1)
                    m = self._RE_BET.search(fa)
                    if m:
                        andring.forarbete_bet = m.group(1)
                    m = self._RE_RSKR.search(fa)
                    if m:
                        andring.forarbete_rskr = m.group(1)
            andringar.append(andring)
```

Then update the `return SFSMetadata(...)` statement to include `andringar=andringar`.

The full updated `return` statement is:

```python
        return SFSMetadata(
            sfs=sfs,
            titel=titel,
            departement=departement,
            ikraftträdande=ikraftträdande,
            utfärdad=utfärdad,
            forarbete_prop=forarbete_prop,
            forarbete_bet=forarbete_bet,
            forarbete_rskr=forarbete_rskr,
            andringar=andringar,
        )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseAndringar -v
```

Expected: 4 PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/import/rkrattsbaser_scraper.py tests/test_rkrattsbaser_scraper.py
git commit -m "feat: parse amendments in _parse_metadata_html()"
```

---

## Task 5: fetch_text() — consolidated law text parser

**Files:**
- Modify: `scripts/import/rkrattsbaser_scraper.py`
- Modify: `tests/test_rkrattsbaser_scraper.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_rkrattsbaser_scraper.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseText -v
```

Expected: `AttributeError: 'RkrattsbaserScraper' object has no attribute '_parse_text_html'`

- [ ] **Step 3: Implement `_parse_text_html`**

Add to `RkrattsbaserScraper`:

```python
    def _parse_text_html(self, sfs: str, html: str) -> SFSText | None:
        """Parse /sfst?bet=YYYY:NNN HTML into SFSText."""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        text_div = soup.find("div", class_="result-box-text")
        if not text_div:
            return None
        text = text_div.get_text()

        andring_intom = None
        for box in soup.find_all("div", class_="result-inner-box"):
            box_text = box.get_text(strip=True)
            if "Ändring införd:" in box_text:
                andring_intom = box_text.replace("Ändring införd:", "").strip()
                break

        uppdaterad = None
        meta = soup.find("meta", id="rattsinfo-edited")
        if meta and meta.get("content"):
            uppdaterad = meta["content"]

        return SFSText(
            sfs=sfs,
            text=text,
            andring_intom=andring_intom,
            uppdaterad=uppdaterad,
        )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestParseText -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/rkrattsbaser_scraper.py tests/test_rkrattsbaser_scraper.py
git commit -m "feat: add _parse_text_html() for consolidated law text"
```

---

## Task 6: HTTP layer — _get(), fetch_metadata(), fetch_text(), enumerate_sfs_numbers()

**Files:**
- Modify: `scripts/import/rkrattsbaser_scraper.py`
- Modify: `tests/test_rkrattsbaser_scraper.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_rkrattsbaser_scraper.py`:

```python
from unittest.mock import patch, MagicMock


class TestHttpLayer:
    def test_get_returns_html_on_200(self):
        scraper = RkrattsbaserScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>ok</html>"
        with patch("requests.get", return_value=mock_resp) as mock_get:
            result = scraper._get("/sfsr", params={"bet": "1962:700"})
        assert result == "<html>ok</html>"
        mock_get.assert_called_once()

    def test_get_returns_none_on_404(self):
        scraper = RkrattsbaserScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        with patch("requests.get", return_value=mock_resp):
            result = scraper._get("/sfsr", params={"bet": "9999:1"})
        assert result is None

    def test_fetch_metadata_returns_none_on_404(self):
        scraper = RkrattsbaserScraper()
        with patch.object(scraper, "_get", return_value=None):
            result = scraper.fetch_metadata("9999:1")
        assert result is None

    def test_fetch_text_returns_none_on_404(self):
        scraper = RkrattsbaserScraper()
        with patch.object(scraper, "_get", return_value=None):
            result = scraper.fetch_text("9999:1")
        assert result is None

    def test_enumerate_returns_empty_on_first_empty_page(self):
        scraper = RkrattsbaserScraper()
        with patch.object(scraper, "_get", return_value="<html><body></body></html>"):
            result = scraper.enumerate_sfs_numbers()
        assert result == []
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py::TestHttpLayer -v
```

Expected: `AttributeError: 'RkrattsbaserScraper' object has no attribute '_get'`

- [ ] **Step 3: Implement HTTP layer and wire up public methods**

Replace the three `raise NotImplementedError` stubs and add `_get()`:

```python
    def _get(self, path: str, params: dict | None = None) -> str | None:
        """GET request with retry. Returns HTML text or None."""
        url = f"{self.BASE_URL}{path}"
        headers = {"User-Agent": self.USER_AGENT}
        for attempt in range(4):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                resp.raise_for_status()
                return resp.text
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    return None
                wait = 2 ** attempt
                logger.warning("HTTP error %s, retrying in %ds...", e, wait)
                time.sleep(wait)
            except requests.RequestException as e:
                wait = 2 ** attempt
                logger.warning("Request failed (%s), retrying in %ds...", e, wait)
                time.sleep(wait)
        logger.error("Failed to fetch %s after 4 attempts", url)
        return None

    def enumerate_sfs_numbers(self) -> list[str]:
        """Fetch all SFS numbers via paginated list (~372 pages)."""
        all_numbers: list[str] = []
        page = 1
        while True:
            time.sleep(self.REQUEST_DELAY)
            html = self._get(
                "/sfsr/adv",
                params={"fritext": "", "sbet": "", "äbet": "", "org": "",
                        "sort": "asc", "page": page},
            )
            if not html:
                break
            numbers = self._parse_sfs_list_page(html)
            if not numbers:
                break
            all_numbers.extend(numbers)
            page += 1
        return all_numbers

    def fetch_metadata(self, sfs: str) -> SFSMetadata | None:
        """Fetch metadata + full amendment register for one SFS number."""
        time.sleep(self.REQUEST_DELAY)
        html = self._get("/sfsr", params={"bet": sfs})
        if not html:
            return None
        return self._parse_metadata_html(sfs, html)

    def fetch_text(self, sfs: str) -> SFSText | None:
        """Fetch consolidated law text for one SFS number."""
        time.sleep(self.REQUEST_DELAY)
        html = self._get("/sfst", params={"bet": sfs})
        if not html:
            return None
        return self._parse_text_html(sfs, html)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_rkrattsbaser_scraper.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/rkrattsbaser_scraper.py tests/test_rkrattsbaser_scraper.py
git commit -m "feat: add HTTP layer, wire up public methods"
```

---

## Self-Review Checklist

- [x] `SFSMetadata`, `SFSAndring`, `SFSText` dataclasses with correct defaults — Task 1
- [x] `_parse_sfs_list_page()` — Task 2
- [x] `_parse_metadata_html()` base fields (titel, departement, ikraft, utfärdad, förarbeten) — Task 3
- [x] `_parse_metadata_html()` amendments — Task 4
- [x] `_parse_text_html()` (text, andring_intom, uppdaterad) — Task 5
- [x] `_get()` with retry/404 handling — Task 6
- [x] `enumerate_sfs_numbers()`, `fetch_metadata()`, `fetch_text()` public API — Task 6
- [x] All tests use HTML fixtures, no network calls — Tasks 1–6
- [x] `REQUEST_DELAY` respected in all public methods — Task 6
- [x] User-Agent header set — Task 6

**Note:** `enumerate_sfs_numbers()` calls `_get()` which calls `time.sleep(REQUEST_DELAY)` inside `_get` is NOT true — sleep happens in the calling method. The `TestHttpLayer.test_enumerate_returns_empty_on_first_empty_page` patches `_get` so the sleep in `enumerate_sfs_numbers()` will still run. If this makes tests slow, patch `time.sleep` as well or set `REQUEST_DELAY = 0` on the scraper instance in tests.
