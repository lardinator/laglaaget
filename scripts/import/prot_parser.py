"""Parse voting results from Riksdagen protocol texts.

Supports three eras:
  - 1971–1992: OCR-scanned prose protocols
  - 1993/94–2001/02: Word-processed snabbprotokoll
  - 2002/03+:  Structured HTML votering documents
"""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class VoteringResult:
    ja: int | None = None
    nej: int | None = None
    avstar: int | None = None
    franvarande: int | None = None
    partier: dict[str, str] = field(default_factory=dict)
    metod: str = "okänd"   # "acklamation" | "omröstning" | "okänd"
    källa: str = ""


class ProtParser:
    """Extract voting results from Riksdagen protocol texts."""

    # --- Era 1: OCR prose (1971–1992) ---

    _PATTERN_A = re.compile(
        r"(?:Ja|J[^\S\n]*a)[:\s]+(\d+)[^\S\n]+(?:Nej|N[^\S\n]*ej)[:\s]+(\d+)[^\S\n]+(?:Avst(?:[åa]r?)?)[:\s]+(\d+)",
        re.IGNORECASE,
    )
    _PATTERN_A_DOTALL = re.compile(
        r"(?:Ja|J\s*a)[:\s]+(\d+).*?(?:Nej|N\s*ej)[:\s]+(\d+).*?(?:Avst(?:[åa]r?)?)[:\s]+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    _PATTERN_B = re.compile(
        r"bif[öo]lls\s+med\s+(\d+)\s+r[öo]ster\s+mot\s+(\d+)",
        re.IGNORECASE,
    )
    _PATTERN_ACKLAM = re.compile(r"bif[öo]lls\b", re.IGNORECASE)

    # --- Era 2: Snabbprotokoll (1993/94–2001/02) ---

    _PATTERN_FOR = re.compile(
        r"^\s*(\d+)\s+f[öo]r\s+(utskottet|res(?:ervationen)?\.?\s*\d*(?:\s*\([^)]+\))?|men\..*?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    _PATTERN_PARTI = re.compile(r"\(([^)]+)\)")
    _PATTERN_AVSTAR = re.compile(r"^\s*(\d+)\s+avst[oå]d\s*$", re.IGNORECASE | re.MULTILINE)
    _PATTERN_FRANV = re.compile(r"^\s*(\d+)\s+fr[åa]nvarande\s*$", re.IGNORECASE | re.MULTILINE)

    @staticmethod
    def rm_to_year(rm: str) -> int:
        """Convert riksmöte string to start year.

        Returns 0 for invalid/unrecognized input (sentinel for "unknown era").

        Examples:
            "1971"    -> 1971
            "1975/76" -> 1975
            "2002/03" -> 2002
            "okänd"   -> 0
        """
        match = re.match(r"^(\d{4})(?:/\d{2,4})?$", rm.strip())
        if not match:
            return 0
        return int(match.group(1))

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

    def _parse_ocr_prose(self, text: str) -> "VoteringResult | None":
        """Era 1971–1992: OCR-scanned prose protocols."""
        if not text:
            return None
        # Try Pattern A (explicit Ja/Nej/Avstår on one or nearby lines)
        m = self._PATTERN_A.search(text) or self._PATTERN_A_DOTALL.search(text)
        if m:
            return VoteringResult(
                ja=int(m.group(1)),
                nej=int(m.group(2)),
                avstar=int(m.group(3)),
                metod="omröstning",
            )

        # Try Pattern B (prose: "bifölls med NNN röster mot NNN")
        m = self._PATTERN_B.search(text)
        if m:
            return VoteringResult(
                ja=int(m.group(1)),
                nej=int(m.group(2)),
                metod="omröstning",
            )

        # Acclamation: "bifölls" without any numbers nearby
        if self._PATTERN_ACKLAM.search(text) and not re.search(r'\d', text):
            return VoteringResult(metod="acklamation")

        return None

    def _parse_snabb(self, text: str) -> "VoteringResult | None":
        """Era 1993/94–2001/02: Structured snabbprotokoll blocks."""
        if not text:
            return None
        text = text.replace('\r\n', '\n').replace('\r', '\n')   # normalise CRLF

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
                # Extract parties from all parenthetical groups in label
                for pm in self._PATTERN_PARTI.finditer(label):
                    for parti in pm.group(1).split(","):
                        cleaned = parti.strip().lower()
                        if cleaned:
                            partier[cleaned] = "nej"

        avstar_m = self._PATTERN_AVSTAR.search(search_text)
        avstar = int(avstar_m.group(1)) if avstar_m else None
        franv_m = self._PATTERN_FRANV.search(search_text)
        franvarande = int(franv_m.group(1)) if franv_m else None

        if ja == 0 or nej == 0:
            return None

        return VoteringResult(
            ja=ja,
            nej=nej,
            avstar=avstar,
            franvarande=franvarande,
            partier=partier,
            metod="omröstning",
        )

    # --- Era 3: HTML votering documents (2002/03+) ---

    _ROST_NORM: dict[str, str] = {"avstar": "avstår", "franvarande": "frånvarande"}

    def _parse_html(self, html: str) -> "VoteringResult | None":
        """Era 2002/03+: HTML table with one row per member."""
        if not html:
            return None

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
            # Normalise ASCII fallbacks to canonical UTF-8 form
            rost = self._ROST_NORM.get(rost, rost)

            if rost == "ja":
                ja += 1
            elif rost == "nej":
                nej += 1
            elif rost in ("avstår", "avstar"):
                avstar += 1
            elif rost in ("frånvarande", "franvarande"):
                franvarande += 1

            if parti:
                party_votes.setdefault(parti, {"ja": 0, "nej": 0, "avstår": 0, "frånvarande": 0})
                vote_key = rost if rost in party_votes[parti] else None
                if vote_key:
                    party_votes[parti][vote_key] += 1

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
