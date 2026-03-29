# ProtParser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `ProtParser` — a class that extracts voting results (Ja/Nej/Avstår + party affiliations) from Riksdagen protocol texts across three historical eras, and integrate it into `historical_import.py`.

**Architecture:** A single `ProtParser` class in `scripts/import/prot_parser.py` with three era-specific private methods dispatched by `parse_votering()` based on the riksmöte year. Network calls stay in `historical_import.py`; the parser only receives already-fetched text. A new helper `fetch_protokoll_section()` in `historical_import.py` fetches the right protocol text given a betänkande reference.

**Tech Stack:** Python 3.11+, `re`, `dataclasses`, `beautifulsoup4` (already in requirements.txt or add it), `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/import/prot_parser.py` | Create | `VoteringResult` dataclass, `ProtParser` class with three era strategies |
| `tests/test_prot_parser.py` | Create | Unit tests for all parser logic — no network calls |
| `scripts/import/historical_import.py` | Modify | Add `fetch_protokoll_section()`, `format_votering_for_commit()`, wire into `run_import()` |

---

## Task 1: VoteringResult dataclass + rm_to_year()

**Files:**
- Create: `scripts/import/prot_parser.py`
- Create: `tests/test_prot_parser.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_prot_parser.py
import pytest
from scripts.import.prot_parser import VoteringResult, ProtParser


class TestRmToYear:
    def test_single_year(self):
        assert ProtParser.rm_to_year("1971") == 1971

    def test_single_year_1867(self):
        assert ProtParser.rm_to_year("1867") == 1867

    def test_slash_year(self):
        assert ProtParser.rm_to_year("1975/76") == 1975

    def test_slash_year_modern(self):
        assert ProtParser.rm_to_year("2002/03") == 2002

    def test_slash_year_century_boundary(self):
        assert ProtParser.rm_to_year("1999/00") == 1999

    def test_invalid_returns_0(self):
        assert ProtParser.rm_to_year("okänd") == 0
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /path/to/lagl-get
python -m pytest tests/test_prot_parser.py::TestRmToYear -v
```

Expected: `ModuleNotFoundError` or `ImportError` — file doesn't exist yet.

- [ ] **Step 3: Create prot_parser.py with dataclass and rm_to_year**

```python
# scripts/import/prot_parser.py
"""Parse voting results from Riksdagen protocol texts.

Supports three eras:
  - 1971–1992: OCR-scanned prose protocols
  - 1993/94–2001/02: Word-processed snabbprotokoll
  - 2002/03+:  Structured HTML votering documents
"""

import re
from dataclasses import dataclass, field


@dataclass
class VoteringResult:
    ja: int | None
    nej: int | None
    avstar: int | None
    franvarande: int | None
    partier: dict[str, str] = field(default_factory=dict)
    metod: str = "okänd"   # "acklamation" | "omröstning" | "okänd"
    källa: str = ""


class ProtParser:
    """Extract voting results from Riksdagen protocol texts."""

    @staticmethod
    def rm_to_year(rm: str) -> int:
        """Convert riksmöte string to start year.

        Examples:
            "1971"    -> 1971
            "1975/76" -> 1975
            "2002/03" -> 2002
        """
        match = re.match(r"^(\d{4})(?:/\d{2,4})?$", rm.strip())
        if not match:
            return 0
        return int(match.group(1))
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_prot_parser.py::TestRmToYear -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/import/prot_parser.py tests/test_prot_parser.py
git commit -m "feat: add VoteringResult dataclass and rm_to_year()"
```

---

## Task 2: Era 1 — OCR prose parser (1971–1992)

**Files:**
- Modify: `scripts/import/prot_parser.py`
- Modify: `tests/test_prot_parser.py`

- [ ] **Step 1: Add Era 1 tests**

Append to `tests/test_prot_parser.py`:

```python
class TestParseOcrProse:
    def setup_method(self):
        self.parser = ProtParser()

    def test_pattern_a_explicit_counts(self):
        text = """
        Vid omröstning genom omröstningsapparat.
        Ja: 234   Nej: 57   Avstår: 7
        """
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 234
        assert result.nej == 57
        assert result.avstar == 7
        assert result.metod == "omröstning"

    def test_pattern_b_prose_sentence(self):
        text = "Utskottets hemställan bifölls med 151 röster mot 149 för reservationen."
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 151
        assert result.nej == 149
        assert result.avstar is None
        assert result.metod == "omröstning"

    def test_acclamation_no_numbers(self):
        text = "Utskottets hemställan bifölls."
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.metod == "acklamation"
        assert result.ja is None
        assert result.nej is None

    def test_ocr_noise_ja_with_space(self):
        # OCR sometimes splits "Ja" as "J a"
        text = "J a: 200  N ej: 30  Avstår: 5"
        result = self.parser._parse_ocr_prose(text)
        assert result is not None
        assert result.ja == 200
        assert result.nej == 30

    def test_no_voting_returns_none(self):
        text = "Riksdagen behandlade frågan om statsbudgeten."
        result = self.parser._parse_ocr_prose(text)
        assert result is None

    def test_partier_empty_for_era1(self):
        text = "Ja: 100  Nej: 50  Avstår: 0"
        result = self.parser._parse_ocr_prose(text)
        assert result.partier == {}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_prot_parser.py::TestParseOcrProse -v
```

Expected: `AttributeError: 'ProtParser' object has no attribute '_parse_ocr_prose'`

- [ ] **Step 3: Implement _parse_ocr_prose**

Add to the `ProtParser` class in `scripts/import/prot_parser.py`:

```python
    # --- Era 1: OCR prose (1971–1992) ---

    _PATTERN_A = re.compile(
        r"(?:Ja|J\s*a)[:\s]+(\d+)\s+(?:Nej|N\s*ej)[:\s]+(\d+)\s+(?:Avst[åa]r?)[:\s]+(\d+)",
        re.IGNORECASE,
    )
    _PATTERN_A_DOTALL = re.compile(
        r"(?:Ja|J\s*a)[:\s]+(\d+).*?(?:Nej|N\s*ej)[:\s]+(\d+).*?(?:Avst[åa]r?)[:\s]+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    _PATTERN_B = re.compile(
        r"bif[öo]lls\s+med\s+(\d+)\s+r[öo]ster\s+mot\s+(\d+)",
        re.IGNORECASE,
    )
    _PATTERN_ACKLAM = re.compile(r"bif[öo]lls\b", re.IGNORECASE)

    def _parse_ocr_prose(self, text: str) -> "VoteringResult | None":
        """Era 1971–1992: OCR-scanned prose protocols."""
        # Try Pattern A (explicit Ja/Nej/Avstår on one or nearby lines)
        m = self._PATTERN_A.search(text) or self._PATTERN_A_DOTALL.search(text)
        if m:
            return VoteringResult(
                ja=int(m.group(1)),
                nej=int(m.group(2)),
                avstar=int(m.group(3)),
                franvarande=None,
                metod="omröstning",
            )

        # Try Pattern B (prose: "bifölls med NNN röster mot NNN")
        m = self._PATTERN_B.search(text)
        if m:
            return VoteringResult(
                ja=int(m.group(1)),
                nej=int(m.group(2)),
                avstar=None,
                franvarande=None,
                metod="omröstning",
            )

        # Acclamation: "bifölls" without numbers
        if self._PATTERN_ACKLAM.search(text):
            return VoteringResult(
                ja=None, nej=None, avstar=None, franvarande=None,
                metod="acklamation",
            )

        return None
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_prot_parser.py::TestParseOcrProse -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/import/prot_parser.py tests/test_prot_parser.py
git commit -m "feat: add Era 1 OCR prose parser"
```

---

## Task 3: Era 2 — Snabbprotokoll parser (1993/94–2001/02)

**Files:**
- Modify: `scripts/import/prot_parser.py`
- Modify: `tests/test_prot_parser.py`

- [ ] **Step 1: Add Era 2 tests**

Append to `tests/test_prot_parser.py`:

```python
class TestParseSnabb:
    def setup_method(self):
        self.parser = ProtParser()

    def test_simple_vote(self):
        text = """
        Huvudvotering:
        268 för utskottet
        20 för res. 1
        1 avstod
        60 frånvarande
        """
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 268
        assert result.nej == 20
        assert result.metod == "omröstning"

    def test_party_in_reservation(self):
        text = """
        166 för utskottet
        124 för res. 2 (m, kd)
        59 frånvarande
        """
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 166
        assert result.nej == 124
        assert result.partier == {"m": "nej", "kd": "nej"}

    def test_multiple_reservations(self):
        text = """
        Förberedande votering:
        25 för res. 1 (nyd)
        12 för men. i motsv. del (v)
        251 avstod
        61 frånvarande

        Huvudvotering:
        268 för utskottet
        20 för res. 1 (nyd)
        1 avstod
        60 frånvarande
        """
        # Should parse the Huvudvotering block
        result = self.parser._parse_snabb(text)
        assert result is not None
        assert result.ja == 268
        assert result.nej == 20
        assert "nyd" in result.partier

    def test_utskottet_is_ja_side(self):
        text = "100 för utskottet\n50 för res. 3 (s)\n49 frånvarande"
        result = self.parser._parse_snabb(text)
        assert result.ja == 100
        assert result.nej == 50

    def test_no_voting_block_returns_none(self):
        text = "Riksdagen beslutade om statsbudgeten."
        result = self.parser._parse_snabb(text)
        assert result is None

    def test_party_names_lowercased(self):
        text = "200 för utskottet\n100 för res. 1 (M, KD, FP)"
        result = self.parser._parse_snabb(text)
        assert "m" in result.partier
        assert "kd" in result.partier
        assert "fp" in result.partier
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_prot_parser.py::TestParseSnabb -v
```

Expected: `AttributeError: 'ProtParser' object has no attribute '_parse_snabb'`

- [ ] **Step 3: Implement _parse_snabb**

Add to the `ProtParser` class:

```python
    # --- Era 2: Snabbprotokoll (1993/94–2001/02) ---

    _PATTERN_FOR = re.compile(
        r"^(\d+)\s+f[öo]r\s+(utskottet|res(?:ervationen)?\.?\s*\d*(?:\s*\([^)]+\))?|men\..*?)$",
        re.IGNORECASE | re.MULTILINE,
    )
    _PATTERN_PARTI = re.compile(r"\(([^)]+)\)")

    def _parse_snabb(self, text: str) -> "VoteringResult | None":
        """Era 1993/94–2001/02: Structured snabbprotokoll blocks."""
        # Prefer the Huvudvotering block if present
        huvudblock_match = re.search(
            r"Huvudvotering[:\s]*(.*?)(?=\n\n|\Z)", text, re.IGNORECASE | re.DOTALL
        )
        search_text = huvudblock_match.group(1) if huvudblock_match else text

        matches = self._PATTERN_FOR.findall(search_text)
        if not matches:
            return None

        ja = 0
        nej = 0
        partier: dict[str, str] = {}

        for count_str, label in matches:
            count = int(count_str)
            label_lower = label.lower()
            if "utskottet" in label_lower:
                ja += count
            else:
                # reservation or men. → nej side
                nej += count
                # Extract parties from parentheses
                pm = self._PATTERN_PARTI.search(label)
                if pm:
                    for parti in pm.group(1).split(","):
                        partier[parti.strip().lower()] = "nej"

        if ja == 0 and nej == 0:
            return None

        return VoteringResult(
            ja=ja,
            nej=nej,
            avstar=None,
            franvarande=None,
            partier=partier,
            metod="omröstning",
        )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_prot_parser.py::TestParseSnabb -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/import/prot_parser.py tests/test_prot_parser.py
git commit -m "feat: add Era 2 snabbprotokoll parser"
```

---

## Task 4: Era 3 — HTML votering parser (2002/03+)

**Files:**
- Modify: `scripts/import/prot_parser.py`
- Modify: `tests/test_prot_parser.py`
- Possibly modify: `requirements.txt` (add beautifulsoup4)

- [ ] **Step 1: Ensure beautifulsoup4 is in requirements.txt**

```bash
grep -i beautifulsoup requirements.txt
```

If not present, add it:
```
beautifulsoup4>=4.12
```

- [ ] **Step 2: Add Era 3 tests**

Append to `tests/test_prot_parser.py`:

```python
class TestParseHtml:
    def setup_method(self):
        self.parser = ProtParser()

    HTML_FIXTURE = """
    <html><body>
    <table>
    <tr><th>Namn</th><th>Parti</th><th>Valkrets</th><th>Bänk</th><th>Typ</th><th>Röst</th></tr>
    <tr><td>Anna Andersson</td><td>s</td><td>Stockholm</td><td class="vcenter">1</td><td>sakfrågan</td><td class="vcenter">Ja</td></tr>
    <tr><td>Björn Berg</td><td>s</td><td>Göteborg</td><td class="vcenter">2</td><td>sakfrågan</td><td class="vcenter">Ja</td></tr>
    <tr><td>Carl Carlsson</td><td>m</td><td>Malmö</td><td class="vcenter">3</td><td>sakfrågan</td><td class="vcenter">Nej</td></tr>
    <tr><td>Diana Dahl</td><td>m</td><td>Uppsala</td><td class="vcenter">4</td><td>sakfrågan</td><td class="vcenter">Nej</td></tr>
    <tr><td>Erik Ek</td><td>v</td><td>Lund</td><td class="vcenter">5</td><td>sakfrågan</td><td class="vcenter">Ja</td></tr>
    <tr><td>Fatima Falk</td><td>kd</td><td>Linköping</td><td class="vcenter">6</td><td>sakfrågan</td><td class="vcenter">Frånvarande</td></tr>
    </table>
    </body></html>
    """

    def test_aggregate_counts(self):
        result = self.parser._parse_html(self.HTML_FIXTURE)
        assert result is not None
        assert result.ja == 3        # Anna, Björn, Erik
        assert result.nej == 2       # Carl, Diana
        assert result.avstar == 0
        assert result.franvarande == 1  # Fatima
        assert result.metod == "omröstning"

    def test_party_majority_vote(self):
        result = self.parser._parse_html(self.HTML_FIXTURE)
        # s: 2 Ja → "ja"
        assert result.partier.get("s") == "ja"
        # m: 2 Nej → "nej"
        assert result.partier.get("m") == "nej"
        # v: 1 Ja → "ja"
        assert result.partier.get("v") == "ja"
        # kd: 1 Frånvarande → not in partier (or "frånvarande")
        assert "kd" not in result.partier or result.partier["kd"] == "frånvarande"

    def test_empty_table_returns_none(self):
        html = "<html><body><table></table></body></html>"
        result = self.parser._parse_html(html)
        assert result is None

    def test_no_table_returns_none(self):
        result = self.parser._parse_html("<html><body>Ingen votering</body></html>")
        assert result is None
```

- [ ] **Step 3: Run to verify tests fail**

```bash
python -m pytest tests/test_prot_parser.py::TestParseHtml -v
```

Expected: `AttributeError: 'ProtParser' object has no attribute '_parse_html'`

- [ ] **Step 4: Implement _parse_html**

Add import at top of `prot_parser.py`:
```python
from bs4 import BeautifulSoup
```

Add to the `ProtParser` class:

```python
    # --- Era 3: HTML votering documents (2002/03+) ---

    def _parse_html(self, html: str) -> "VoteringResult | None":
        """Era 2002/03+: HTML table with one row per member."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return None

        rows = table.find_all("tr")
        # Skip header row(s) — detect by presence of <th>
        data_rows = [r for r in rows if not r.find("th")]
        if not data_rows:
            return None

        ja = nej = avstar = franvarande = 0
        # party -> {vote -> count}
        party_votes: dict[str, dict[str, int]] = {}

        for row in data_rows:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            parti = cells[1].get_text(strip=True).lower()
            rost = cells[5].get_text(strip=True).lower()

            if rost == "ja":
                ja += 1
            elif rost == "nej":
                nej += 1
            elif rost in ("avstår", "avstar"):
                avstar += 1
            elif rost == "frånvarande":
                franvarande += 1

            if parti:
                party_votes.setdefault(parti, {"ja": 0, "nej": 0, "avstår": 0, "frånvarande": 0})
                if rost in party_votes[parti]:
                    party_votes[parti][rost] += 1

        if ja == 0 and nej == 0 and avstar == 0:
            return None

        # Determine majority vote per party (exclude frånvarande)
        partier: dict[str, str] = {}
        for parti, counts in party_votes.items():
            active = {v: c for v, c in counts.items() if v != "frånvarande" and c > 0}
            if active:
                partier[parti] = max(active, key=active.__getitem__)

        return VoteringResult(
            ja=ja,
            nej=nej,
            avstar=avstar,
            franvarande=franvarande,
            partier=partier,
            metod="omröstning",
        )
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_prot_parser.py::TestParseHtml -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/import/prot_parser.py tests/test_prot_parser.py requirements.txt
git commit -m "feat: add Era 3 HTML votering parser"
```

---

## Task 5: parse_votering() dispatcher

**Files:**
- Modify: `scripts/import/prot_parser.py`
- Modify: `tests/test_prot_parser.py`

- [ ] **Step 1: Add dispatcher tests**

Append to `tests/test_prot_parser.py`:

```python
class TestParseVoteringDispatch:
    def setup_method(self):
        self.parser = ProtParser()

    def test_routes_era1_by_rm(self):
        text = "Ja: 100  Nej: 50  Avstår: 0"
        result = self.parser.parse_votering(text, "1980/81")
        assert result is not None
        assert result.ja == 100

    def test_routes_era2_by_rm(self):
        text = "100 för utskottet\n50 för res. 1 (m)"
        result = self.parser.parse_votering(text, "1996/97")
        assert result is not None
        assert result.ja == 100

    def test_routes_era3_by_rm(self):
        html = """<table>
        <tr><td>Anna</td><td>s</td><td>Stockholm</td><td>1</td><td>sakfrågan</td><td>Ja</td></tr>
        </table>"""
        result = self.parser.parse_votering(html, "2010/11")
        assert result is not None
        assert result.ja == 1

    def test_pre_1971_returns_none(self):
        result = self.parser.parse_votering("Någon text", "1965")
        assert result is None

    def test_unknown_rm_returns_none(self):
        result = self.parser.parse_votering("Text", "okänd")
        assert result is None
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_prot_parser.py::TestParseVoteringDispatch -v
```

Expected: `AttributeError: 'ProtParser' object has no attribute 'parse_votering'`

- [ ] **Step 3: Implement parse_votering**

Add to the `ProtParser` class:

```python
    def parse_votering(self, text: str, rm: str) -> "VoteringResult | None":
        """Dispatch to era-specific parser based on riksmöte year.

        Args:
            text: Already-fetched protocol text or HTML.
            rm:   Riksmöte string e.g. "1980/81", "2002/03", "1971".

        Returns:
            VoteringResult or None if no voting found / era not supported.
        """
        year = self.rm_to_year(rm)
        if year == 0:
            return None
        if year < 1971:
            return None
        if year <= 1992:
            return self._parse_ocr_prose(text)
        if year <= 2001:
            return self._parse_snabb(text)
        return self._parse_html(text)
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_prot_parser.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/import/prot_parser.py tests/test_prot_parser.py
git commit -m "feat: add parse_votering() dispatcher"
```

---

## Task 6: fetch_protokoll_section() + format_votering_for_commit()

**Files:**
- Modify: `scripts/import/historical_import.py`
- Modify: `tests/test_prot_parser.py` (add integration-adjacent unit tests)

- [ ] **Step 1: Add tests for format_votering_for_commit**

Append to `tests/test_prot_parser.py`:

```python
from scripts.import.historical_import import format_votering_for_commit


class TestFormatVoteringForCommit:
    def test_full_result_with_parties(self):
        v = VoteringResult(
            ja=268, nej=20, avstar=1, franvarande=60,
            partier={"s": "ja", "mp": "ja", "m": "nej"},
            metod="omröstning", källa="GQ19KU2"
        )
        s = format_votering_for_commit(v)
        assert "268 ja" in s
        assert "20 nej" in s
        assert "1 avstår" in s

    def test_acclamation(self):
        v = VoteringResult(
            ja=None, nej=None, avstar=None, franvarande=None,
            metod="acklamation", källa="prot 1980:50 §3"
        )
        assert format_votering_for_commit(v) == "acklamation"

    def test_none_returns_ej_tillganglig(self):
        assert format_votering_for_commit(None) == "ej tillgänglig"

    def test_parties_sorted_in_output(self):
        v = VoteringResult(
            ja=100, nej=50, avstar=0, franvarande=10,
            partier={"m": "nej", "s": "ja", "v": "ja"},
            metod="omröstning", källa=""
        )
        s = format_votering_for_commit(v)
        assert "(s, v ja; m nej)" in s
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_prot_parser.py::TestFormatVoteringForCommit -v
```

Expected: `ImportError` — function doesn't exist yet.

- [ ] **Step 3: Add format_votering_for_commit to historical_import.py**

Add after the existing imports in `scripts/import/historical_import.py`:

```python
from prot_parser import ProtParser, VoteringResult
```

Add this function before `run_import()`:

```python
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
```

- [ ] **Step 4: Add fetch_protokoll_section to historical_import.py**

Add this function before `run_import()`:

```python
def fetch_protokoll_section(bet_beteckning: str, rm: str) -> str | None:
    """Fetch protocol text for the riksdag session that handled a betänkande.

    For rm >= 2002/03: fetches from doktyp=votering using bet_beteckning as dok_id prefix.
    For older rm: fetches prot document text and searches for the betänkande reference.

    Args:
        bet_beteckning: e.g. "2016/17:CU11" or "UU15"
        rm: riksmöte string e.g. "1996/97"

    Returns:
        Text/HTML content of the relevant protocol section, or None.
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
            return resp.get("dokument", {}).get("html", "")
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
                return text

        return None
```

- [ ] **Step 5: Run format tests**

```bash
python -m pytest tests/test_prot_parser.py::TestFormatVoteringForCommit -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/import/historical_import.py tests/test_prot_parser.py
git commit -m "feat: add format_votering_for_commit() and fetch_protokoll_section()"
```

---

## Task 7: Wire ProtParser into run_import()

**Files:**
- Modify: `scripts/import/historical_import.py`

- [ ] **Step 1: Update run_import() to use ProtParser**

In `scripts/import/historical_import.py`, find the `run_import()` function. Locate where `create_commit()` is called and add votering enrichment.

First, add `prot_parser = ProtParser()` at the top of `run_import()`:

```python
def run_import(from_year: int, to_year: int, dry_run: bool = False) -> None:
    """Run the historical import from rinfo.gov.se."""
    repo_path = Path(__file__).resolve().parent.parent.parent
    repo = git.Repo(repo_path)
    parser = SFSParser()
    prot_parser = ProtParser()          # ← add this
    total_commits = 0
    # ... rest unchanged
```

Then, inside the `try` block where `create_commit()` is called, add votering lookup before the call:

```python
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
                if bet_beteckning and not dry_run:
                    prot_text = fetch_protokoll_section(bet_beteckning, rm)
                    if prot_text:
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
                    departement=parsed.get("departement", "Riksdagen"),
                    dry_run=dry_run,
                )
```

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Quick smoke test (dry run, recent year)**

```bash
python scripts/import/historical_import.py --from-year 2023 --to-year 2023 --dry-run
```

Expected: log output showing `[DRY RUN] Would commit: ...` entries with no errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/import/historical_import.py
git commit -m "feat: integrate ProtParser into historical_import run_import()"
```

---

## Self-Review Checklist

- [x] `VoteringResult` dataclass — Task 1
- [x] `rm_to_year()` — Task 1
- [x] `_parse_ocr_prose()` Era 1 — Task 2
- [x] `_parse_snabb()` Era 2 — Task 3
- [x] `_parse_html()` Era 3 — Task 4
- [x] `parse_votering()` dispatcher — Task 5
- [x] `format_votering_for_commit()` — Task 6
- [x] `fetch_protokoll_section()` — Task 6
- [x] Integration in `run_import()` — Task 7
- [x] Tests for all eras + dispatcher + formatter — Tasks 1–6
- [x] Pre-1971 returns None — Task 5 test
- [x] Acclamation handling — Task 2 test + Task 6 test
- [x] Party extraction Era 2 + Era 3 — Tasks 3, 4

**Note on `forarbete_bet` / `forarbete_prop` fields:** `SFSParser.parse()` currently does not extract `rpubl:forarbete` from the RDF. Task 7 assumes these fields exist in `parsed`. A follow-up task should extend `SFSParser._extract_*` methods to parse `rpubl:forarbete` triples from the rinfo RDF response — but this is out of scope for the current plan since it requires probing actual rinfo.gov.se RDF responses first.
