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

    # Förarbeten regex patterns
    _RE_PROP = re.compile(r"Prop\.\s*(\d{4}(?:/\d{2})?:\d+)", re.IGNORECASE)
    _RE_BET  = re.compile(r"bet\.\s*(\d{4}(?:/\d{2})?:\w+)", re.IGNORECASE)
    _RE_RSKR = re.compile(r"rskr\.?\s*(\d{4}(?:/\d{2})?:\d+)", re.IGNORECASE)

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
                logger.warning("HTTP error %s (attempt %d/4)", e, attempt + 1)
                if attempt < 3:
                    wait = 2 ** attempt
                    time.sleep(wait)
            except requests.RequestException as e:
                logger.warning("Request failed %s (attempt %d/4)", e, attempt + 1)
                if attempt < 3:
                    wait = 2 ** attempt
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
                logger.warning("enumerate_sfs_numbers: failed to fetch page %d, stopping early", page)
                break
            numbers = self._parse_sfs_list_page(html)
            if not numbers:
                logger.debug("enumerate_sfs_numbers: empty page %d, pagination complete", page)
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
                departement = text.split(":", 1)[-1].strip()
            elif "Ikraft:" in text:
                ikraftträdande = text.split(":", 1)[-1].strip()
            elif "Utfärdad:" in text:
                utfärdad = text.split(":", 1)[-1].strip()
            elif "Förarbeten:" in text:
                forarbete_text = text.split("Förarbeten:", 1)[-1]
                m = self._RE_PROP.search(forarbete_text)
                if m:
                    forarbete_prop = m.group(1)
                m = self._RE_BET.search(forarbete_text)
                if m:
                    forarbete_bet = m.group(1)
                m = self._RE_RSKR.search(forarbete_text)
                if m:
                    forarbete_rskr = m.group(1)

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
                    andring.rubrik = sub_text.split(":", 1)[-1].strip()
                elif sub_text.startswith("Omfattning:"):
                    andring.omfattning = sub_text.split(":", 1)[-1].strip()
                elif sub_text.startswith("Ikraftträdande:"):
                    andring.ikraftträdande = sub_text.split(":", 1)[-1].strip()
                elif "Förarbeten:" in sub_text:
                    fa = sub_text.split("Förarbeten:", 1)[-1]
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

        if not titel:
            logger.warning("_parse_metadata_html: could not detect title for SFS %s", sfs)
        if not departement:
            logger.warning("_parse_metadata_html: could not detect departement for SFS %s", sfs)
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
            andringar=andringar,
        )

    def _parse_text_html(self, sfs: str, html: str) -> SFSText | None:
        """Parse /sfst?bet=YYYY:NNN HTML into SFSText."""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        text_div = soup.find("div", class_="result-box-text")
        if not text_div:
            return None
        text = text_div.get_text().strip()

        andring_intom = None
        for box in soup.find_all("div", class_="result-inner-box"):
            box_text = box.get_text(strip=True)
            if "Ändring införd:" in box_text:
                andring_intom = box_text.split("Ändring införd:", 1)[-1].strip()
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
