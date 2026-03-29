# SFSParser Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SFSParser.parse_from_scraper()` that converts `SFSMetadata + SFSText` → dict, and update `to_markdown()` to include `body_text` and amendment history in the frontmatter.

**Architecture:** Single method addition to existing `SFSParser`. No new files except the test file. Backward-compatible — `parse()` and existing `to_markdown()` calls are unaffected.

**Tech Stack:** Python 3.11+, `dataclasses` (from rkrattsbaser_scraper), `yaml`, `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/import/sfs_parser.py` | Modify | Add `parse_from_scraper()`, update `to_markdown()` |
| `tests/test_sfs_parser.py` | Create | Unit tests for new method, no network |

---

## Task 1: parse_from_scraper() — base fields

**Files:**
- Modify: `scripts/import/sfs_parser.py`
- Create: `tests/test_sfs_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sfs_parser.py
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

    def test_body_text_from_sfsttext(self):
        parser = SFSParser()
        result = parser.parse_from_scraper(self.METADATA, self.TEXT)
        assert result["body_text"] == "FÖRSTA AVDELNINGEN\n\n1 § Brott är..."

    def test_body_text_none_when_no_text(self):
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/alexandromartini/Documents/dev/lagl-get
python -m pytest tests/test_sfs_parser.py::TestParseFromScraper -v
```

Expected: `AttributeError: 'SFSParser' object has no attribute 'parse_from_scraper'`

- [ ] **Step 3: Implement `parse_from_scraper()`**

Add import at top of `scripts/import/sfs_parser.py`:
```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from rkrattsbaser_scraper import SFSMetadata, SFSText
```

Add to `SFSParser` class:

```python
    GRUNDLAGAR = {"1974:152", "1974:713", "1949:105", "1810:926"}

    def parse_from_scraper(
        self,
        metadata: "SFSMetadata",
        text: "SFSText | None",
    ) -> dict:
        """Convert SFSMetadata + SFSText (from RkrattsbaserScraper) into a dict
        compatible with to_markdown()."""
        titel = metadata.titel
        sfs = metadata.sfs

        if sfs in self.GRUNDLAGAR:
            typ = "grundlag"
        elif "förordning" in titel.lower():
            typ = "förordning"
        else:
            typ = "lag"

        return {
            "sfs": sfs,
            "titel": titel,
            "kortnamn": None,
            "departement": metadata.departement,
            "typ": typ,
            "ikraftträdande": metadata.ikraftträdande,
            "utfärdad": metadata.utfärdad,
            "upphävd": None,
            "eu_direktiv": [],
            "kapitel": [],
            "forarbete_prop": metadata.forarbete_prop,
            "forarbete_bet": metadata.forarbete_bet,
            "forarbete_rskr": metadata.forarbete_rskr,
            "andringar": metadata.andringar,
            "body_text": text.text if text is not None else "",
            "andring_intom": text.andring_intom if text is not None else None,
        }
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_sfs_parser.py::TestParseFromScraper -v
```

Expected: 12 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/import/sfs_parser.py tests/test_sfs_parser.py
git commit -m "feat: add SFSParser.parse_from_scraper() for rkrattsbaser data"
```

---

## Task 2: Typ-härledning tests + to_markdown() updates

**Files:**
- Modify: `scripts/import/sfs_parser.py`
- Modify: `tests/test_sfs_parser.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sfs_parser.py`:

```python
class TestTypHärledning:
    def test_lag_is_default(self):
        parser = SFSParser()
        m = SFSMetadata(sfs="1962:700", titel="Brottsbalk (1962:700)", departement="Justitiedepartementet L5")
        result = parser.parse_from_scraper(m, None)
        assert result["typ"] == "lag"

    def test_förordning_detected_from_titel(self):
        parser = SFSParser()
        m = SFSMetadata(sfs="1998:1252", titel="Förordning (1998:1252) om områdesskydd", departement="Miljödepartementet")
        result = parser.parse_from_scraper(m, None)
        assert result["typ"] == "förordning"

    def test_grundlag_detected_from_sfs(self):
        parser = SFSParser()
        m = SFSMetadata(sfs="1974:152", titel="Kungörelse (1974:152) om beslutad ny regeringsform", departement="Justitiedepartementet L6")
        result = parser.parse_from_scraper(m, None)
        assert result["typ"] == "grundlag"

    def test_all_grundlag_sfs_numbers(self):
        parser = SFSParser()
        for sfs in ["1974:152", "1974:713", "1949:105", "1810:926"]:
            m = SFSMetadata(sfs=sfs, titel=f"Lag ({sfs})", departement="Justitiedepartementet")
            result = parser.parse_from_scraper(m, None)
            assert result["typ"] == "grundlag", f"Expected grundlag for {sfs}"


class TestToMarkdownWithBodyText:
    METADATA = SFSMetadata(
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
    TEXT = SFSText(
        sfs="1962:700",
        text="FÖRSTA AVDELNINGEN\n\n1 § Brott är...",
        andring_intom="t.o.m. SFS 2026:253",
    )

    def test_body_text_in_markdown(self):
        parser = SFSParser()
        parsed = parser.parse_from_scraper(self.METADATA, self.TEXT)
        md = parser.to_markdown(parsed)
        assert "FÖRSTA AVDELNINGEN" in md
        assert "1 § Brott är..." in md

    def test_forarbete_prop_in_frontmatter(self):
        parser = SFSParser()
        parsed = parser.parse_from_scraper(self.METADATA, self.TEXT)
        md = parser.to_markdown(parsed)
        assert "forarbete_prop: '1962:10'" in md or "forarbete_prop: \"1962:10\"" in md or "forarbete_prop: 1962:10" in md

    def test_ändringshistorik_in_frontmatter(self):
        parser = SFSParser()
        parsed = parser.parse_from_scraper(self.METADATA, self.TEXT)
        md = parser.to_markdown(parsed)
        assert "2026:253" in md

    def test_andring_intom_in_frontmatter(self):
        parser = SFSParser()
        parsed = parser.parse_from_scraper(self.METADATA, self.TEXT)
        md = parser.to_markdown(parsed)
        assert "t.o.m. SFS 2026:253" in md

    def test_empty_body_text_no_garbage(self):
        parser = SFSParser()
        parsed = parser.parse_from_scraper(self.METADATA, None)
        md = parser.to_markdown(parsed)
        # Should not have body text placeholder or None
        assert "None" not in md
        assert "body_text" not in md
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_sfs_parser.py::TestToMarkdownWithBodyText -v
```

Expected: FAIL — `body_text` not yet in `to_markdown()` output.

- [ ] **Step 3: Update `to_markdown()` in `sfs_parser.py`**

Replace the `to_markdown` method with this updated version:

```python
    def to_markdown(self, parsed: dict) -> str:
        """Convert parsed SFS data to Markdown with YAML frontmatter."""
        # Build ändringshistorik from andringar list (SFSAndring objects or dicts)
        ändringshistorik = []
        for a in parsed.get("andringar", []):
            if hasattr(a, "sfs"):
                ändringshistorik.append({
                    "sfs": a.sfs,
                    "rubrik": a.rubrik,
                    "ikraftträdande": a.ikraftträdande,
                })
            elif isinstance(a, dict):
                ändringshistorik.append(a)

        frontmatter = {
            "sfs": parsed["sfs"],
            "titel": parsed["titel"],
            "departement": parsed["departement"],
            "typ": parsed["typ"],
            "ikraftträdande": parsed.get("ikraftträdande", "okänd"),
            "utfärdad": parsed.get("utfärdad"),
            "upphävd": parsed.get("upphävd"),
            "forarbete_prop": parsed.get("forarbete_prop"),
            "forarbete_bet": parsed.get("forarbete_bet"),
            "forarbete_rskr": parsed.get("forarbete_rskr"),
            "andring_intom": parsed.get("andring_intom"),
            "eu_direktiv": parsed.get("eu_direktiv", []),
            "relaterade_lagar": [],
            "riksdagen_dok_id": None,
            "ändringshistorik": ändringshistorik,
        }
        if parsed.get("kortnamn"):
            frontmatter["kortnamn"] = parsed["kortnamn"]

        fm_yaml = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        lines = [f"---\n{fm_yaml}---\n"]
        lines.append(f"# {parsed['titel']}\n")

        chapters = parsed.get("kapitel", [])
        if chapters:
            for chapter in chapters:
                nummer = chapter.get("nummer", "")
                rubrik = chapter.get("rubrik", "")
                lines.append(f"\n## {nummer} kap. {rubrik}\n")
                for para in chapter.get("paragrafer", []):
                    p_nummer = para.get("nummer", "")
                    p_text = para.get("text", "")
                    lines.append(f"\n### {p_nummer} §\n")
                    lines.append(f"{p_text}\n")
        else:
            body_text = parsed.get("body_text", "")
            if body_text:
                lines.append(f"\n{body_text}\n")

        return "\n".join(lines)
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/test_sfs_parser.py -v
```

Expected: all tests PASS (TestParseFromScraper + TestTypHärledning + TestToMarkdownWithBodyText)

- [ ] **Step 5: Run all tests**

```bash
python -m pytest -q
```

Expected: all tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add scripts/import/sfs_parser.py tests/test_sfs_parser.py
git commit -m "feat: update to_markdown() for body_text, förarbeten, and ändringshistorik"
```

---

## Self-Review Checklist

- [x] `parse_from_scraper()` returns all required keys — Task 1
- [x] Typ-härledning: grundlag, förordning, lag — Task 2
- [x] `to_markdown()` includes body_text when kapitel is empty — Task 2
- [x] `to_markdown()` includes forarbete_* and andring_intom in frontmatter — Task 2
- [x] `to_markdown()` includes ändringshistorik built from andringar — Task 2
- [x] Backward-compatible: old `parse()` + `to_markdown()` calls still work — verified by full test run
