# RkrattsbaserScraper — Design Spec
**Datum:** 2026-03-28
**Status:** Godkänd

## Syfte

Hämta konsoliderade lagtexter, metadata och ändringsregister från
`rkrattsbaser.gov.se` som ersättning för den nedlagda `rinfo.gov.se`-tjänsten.
Producerar strukturerade dataklasser som `historical_import.py` konsumerar.

## Bakgrund

`rinfo.gov.se` (Lagrummet) och `data.lagrummet.se` är ECONNREFUSED — helt nersläckta.
`rkrattsbaser.gov.se` (Regeringskansliets rättsdatabaser) är den enda tillgängliga
auktoritativa källan för:
- Konsoliderade lagtexter (`/sfst?bet=YYYY:NNN`)
- Metadata inkl. förarbeten (`/sfsr?bet=YYYY:NNN`)
- Komplett ändringsregister per lag
- Enumeration av alla 11 141 SFS-nummer (`/sfsr/adv?sort=asc&page=N`)

Allt returneras som HTML — inget JSON/XML API finns.

## Datamodell

```python
@dataclass
class SFSMetadata:
    sfs: str                        # e.g. "1962:700"
    titel: str                      # e.g. "Brottsbalk (1962:700)"
    departement: str                # e.g. "Justitiedepartementet L5"
    ikraftträdande: str | None      # ISO date e.g. "1965-01-01"
    utfärdad: str | None            # ISO date e.g. "1962-12-21"
    forarbete_prop: str | None      # e.g. "1962:10"
    forarbete_bet: str | None       # e.g. "1LU 1962:42"
    forarbete_rskr: str | None      # e.g. "1962:390"
    andringar: list[SFSAndring]     # all amendments, oldest first


@dataclass
class SFSAndring:
    sfs: str                        # amending law e.g. "2026:253"
    rubrik: str | None              # title of amending law
    omfattning: str | None          # scope: which paragraphs changed
    ikraftträdande: str | None      # ISO date
    forarbete_prop: str | None      # e.g. "2025/26:34"
    forarbete_bet: str | None       # e.g. "2025/26:JuU8"
    forarbete_rskr: str | None      # e.g. "2025/26:96"


@dataclass
class SFSText:
    sfs: str
    text: str                       # plain text (HTML entities decoded, tags stripped)
    andring_intom: str | None       # "t.o.m. SFS 2026:253"
    uppdaterad: str | None          # from <meta id="rattsinfo-edited">
```

## Arkitektur

### Ny fil: `scripts/import/rkrattsbaser_scraper.py`

Fristående klass `RkrattsbaserScraper`. Inga sidoeffekter — returnerar dataklasser.
Nätverkslogik inuti klassen (till skillnad från `ProtParser` som fick text injicerat).

```python
class RkrattsbaserScraper:
    BASE_URL = "https://rkrattsbaser.gov.se"
    REQUEST_DELAY = 1.0  # sekunder

    def enumerate_sfs_numbers(self) -> list[str]:
        """Hämta alla SFS-nummer via paginerad lista. ~372 sidor."""

    def fetch_metadata(self, sfs: str) -> SFSMetadata | None:
        """Hämta metadata + ändringsregister för ett SFS-nummer."""

    def fetch_text(self, sfs: str) -> SFSText | None:
        """Hämta konsoliderad lagtext."""
```

## HTML-parsning

### enumerate_sfs_numbers()
URL: `/sfsr/adv?fritext=&sbet=&äbet=&org=&sort=asc&page={n}`
Extrahera: `<div class="search-hit-info-num">SFS-nummer: YYYY:NNN</div>`
Stopp: när sidan returnerar inga träffar (tom `search-hit`-lista).

### fetch_metadata() — `/sfsr?bet=YYYY:NNN`

**Basmetadata** från `<div class="result-inner-box">`:
- Titel: `<span class="bold">Lag (YYYY:NNN) om ...</span>`
- Departement: rad som börjar med "Departement:"
- Ikraftträdande: rad som börjar med "Ikraft:"
- Utfärdad: rad som börjar med "Utfärdad:"
- Förarbeten: rad som börjar med "Förarbeten:" — parsas med regex:
  - Prop: `(?:Prop\.\s*)(\d{4}(?:/\d{2})?:\d+)`
  - Bet: `(?:bet\.\s*)(\d{4}(?:/\d{2})?:\w+)`
  - Rskr: `(?:[Rr]skr\.?\s*)(\d{4}(?:/\d{2})?:\d+)`

**Ändringar** från `<div class="result-inner-sub-box-container">` (en per ändring):
- Rubrik: `<div class="result-inner-sub-box-header">Ändring, SFS YYYY:NNN</div>` → extrahera SFS-nummer
- Fält inuti: samma struktur som basmetadata (Rubrik, Omfattning, Förarbeten, Ikraftträdande)

### fetch_text() — `/sfst?bet=YYYY:NNN`

Lagtext: `<div class="result-box-text body-text">` → `BeautifulSoup.get_text()`
HTML-entiteter dekodas automatiskt av BS4.

Metadata ovanför texten:
- `andring_intom`: rad "Ändring införd: t.o.m. SFS YYYY:NNN"
- `uppdaterad`: `<meta id="rattsinfo-edited" content="YYYY-MM-DD HH:MM:SS">`

## Felhantering

| Situation | Beteende |
|-----------|----------|
| HTTP 404 (SFS finns ej) | Returnera `None` |
| HTTP 5xx / timeout | Retry ×3 med exponential backoff, sedan returnera `None` |
| HTML saknar förväntat element | Returnera partiell data (fält sätts till `None`) |
| Förarbeten kan ej parsas | `forarbete_*` fält sätts till `None`, logga warning |

Inga undantag propageras — scraper är best-effort.

## Rate limiting

`REQUEST_DELAY = 1.0` sekund mellan anrop (konservativt för HTML-scraping).
User-Agent: `Lagläget/1.0 (github.com/lardinator/lagl-get)`.

## Tester

`tests/test_rkrattsbaser_scraper.py` med HTML-fixture-filer — ingen nätverksåtkomst.

Testfall:
- `enumerate_sfs_numbers()`: parsning av söksida med 30 träffar
- `fetch_metadata()`: basmetadata + förarbeten för en lag med ändringar
- `fetch_metadata()`: lag utan förarbeten (gamla lagar)
- `fetch_text()`: lagtext extraheras och HTML-entiteter dekodas
- `fetch_text()`: `andring_intom` och `uppdaterad` parsas korrekt
- HTTP 404 → returnerar `None`

## Avgränsningar

- Parsern producerar **inte** git-commits — det är `historical_import.py`s ansvar.
- Inline versionmarkörer (`/Upphör att gälla U:DATE/`) i lagtexten bevaras som-är
  i `SFSText.text` — versionhantering hanteras i nästa sub-projekt.
- `enumerate_sfs_numbers()` hämtar bara SFS-nummer, inte full metadata (separata anrop).
