# ProtParser — Design Spec
**Datum:** 2026-03-28
**Status:** Godkänd

## Syfte

Extrahera voteringdata (Ja/Nej/Avstår/Frånvarande + partitillhörighet) ur Riksdagens
protokolltexter för alla riksmöten från 1971 och framåt. Resultatet används för att
fylla i `Votering:`-fältet i git-commit-meddelanden under historisk import.

## Bakgrund

Riksdagens öppna data API har strukturerade voteringsdata (`doktyp=votering`) endast
från riksmötet 2002/03. För 1971–2001 finns voteringarna inbäddade i protokolltexterna
(`doktyp=prot`) i tre distinkta format beroende på era.

Kopplingen SFS → betänkande hämtas via `rpubl:forarbete`-tripplar i rinfo.gov.se RDF-data,
som `historical_import.py` redan konsumerar.

## Arkitektur

### Ny komponent

`scripts/import/prot_parser.py` — fristående klass `ProtParser`.

Parsern tar emot redan hämtad text (ingen nätverkslogik inuti klassen).
Nätverksanrop sköts av `historical_import.py` via befintlig `api_get()`-funktion.

### Returtyp

```python
@dataclass
class VoteringResult:
    ja: int | None
    nej: int | None
    avstar: int | None
    franvarande: int | None
    partier: dict[str, str]   # {"m": "nej", "v": "ja", "s": "ja", ...}
    metod: str                # "acklamation" | "omröstning" | "okänd"
    källa: str                # dok_id eller "protokoll YYYY:NNN §X"
```

`None` på numeriska fält = värdet ej tillgängligt (t.ex. acklamation eller OCR-fel).
`partier` är tom dict om partidata saknas.

### Klassgränssnitt

```python
class ProtParser:
    def parse_votering(self, text: str, rm: str) -> VoteringResult | None:
        """Välj era-strategi baserat på rm och extrahera votering."""

    def _parse_ocr_prose(self, text: str) -> VoteringResult | None:
        """Era 1971–1992: OCR-skannade protokoll, prosaformat."""

    def _parse_snabb(self, text: str) -> VoteringResult | None:
        """Era 1993/94–2001/02: Snabbprotokoll, strukturerade block."""

    def _parse_html(self, html: str) -> VoteringResult | None:
        """Era 2002/03+: HTML-tabell med en rad per ledamot."""

    @staticmethod
    def rm_to_year(rm: str) -> int:
        """Konvertera riksmöte-sträng till startår (1971 → 1971, 1975/76 → 1975)."""
```

## Era-strategier

### Era 1: 1971–1992 (OCR-prosa)

**Trigger:** `rm_to_year(rm) <= 1992`

Två regex-mönster:

```python
# Mönster A: "Ja: 234  Nej: 57  Avstår: 7"
PATTERN_A = re.compile(
    r"(?:Ja|J\s*a)[:\s]+(\d+).*?(?:Nej|N\s*ej)[:\s]+(\d+).*?(?:Avst[åa]r|Avst[åa])[:\s]+(\d+)",
    re.IGNORECASE | re.DOTALL
)

# Mönster B: "bifölls med 234 röster mot 57"
PATTERN_B = re.compile(
    r"bif[öo]lls\s+med\s+(\d+)\s+r[öo]ster\s+mot\s+(\d+)",
    re.IGNORECASE
)

# Acklamation: "bifölls" utan siffror i närheten
PATTERN_ACKLAM = re.compile(r"bif[öo]lls\b", re.IGNORECASE)
```

Partidata ej tillgänglig för denna era (individuella röster saknades i protokollen).

### Era 2: 1993/94–2001/02 (Snabbprotokoll)

**Trigger:** `1993 <= rm_to_year(rm) <= 2001`

```python
# Voteringblock: "NNN för utskottet" / "NNN för res. 1 (m)"
PATTERN_FOR = re.compile(
    r"(\d+)\s+f[öo]r\s+(utskottet|res(?:ervationen)?\s*\.?\s*\d+(?:\s*\([a-zåäö,\s]+\))?|men\..*?)$",
    re.IGNORECASE | re.MULTILINE
)

# Partiförkortning i parentes efter reservation
PATTERN_PARTI = re.compile(r"\(([a-zåäö,\s]+)\)", re.IGNORECASE)
```

Logik: summera "för utskottet" = ja-sidan, "för res." = nej-sidan.
Partier extraheras från parenteserna efter `res.` och `men.`

### Era 3: 2002/03+ (HTML-tabell)

**Trigger:** `rm_to_year(rm) >= 2002`

Källa: `doktyp=votering`-dokument (inte `prot`).

```python
# BeautifulSoup: parse HTML-tabell
# Varje rad: namn | parti | valkrets | bänknr | sakfrågan | Ja/Nej/Avstår/Frånvarande
# Aggregera: partier[parti] = majoritetsvote
```

## Integration i historical_import.py

```python
# I run_import(), efter att rinfo-entry parsats:
bet_beteckning = parsed.get("forarbete_bet")  # ur rpubl:forarbete RDF
if bet_beteckning:
    prot_text = fetch_protokoll_section(bet_beteckning, rm)
    votering = prot_parser.parse_votering(prot_text, rm)
    votering_str = format_votering_for_commit(votering)
else:
    votering_str = "ej tillgänglig"
```

`fetch_protokoll_section(bet_beteckning, rm)` är en ny hjälpfunktion i `historical_import.py`
som anropar Riksdagen API (`/dokumentlista/?doktyp=prot&rm=...`) för att hitta protokollet
som behandlar det givna betänkandet, och returnerar relevant textsnutt (eller HTML för 2002+).

`format_votering_for_commit()` producerar t.ex.:
- `"268 ja / 20 nej / 1 avstår (s, mp ja; m, kd nej)"`
- `"acklamation"`
- `"ej tillgänglig"`

## Felhantering

| Situation | Beteende |
|-----------|----------|
| Protokoll ej hittat i API | Returnera `None` → `"ej tillgänglig"` |
| Voteringsektion saknas i text | Returnera `None` → `"ej tillgänglig"` |
| Acklamation utan siffror | `metod="acklamation"`, numeriska fält `None` |
| OCR-brus gör regex opålitlig | Returnera `None`, logga warning |
| rinfo saknar `rpubl:forarbete` | Skippa voteringssökning |

Inga undantag propageras uppåt — parsern är best-effort.

## Tester

`tests/test_prot_parser.py` med fixture-text för varje era (ingen nätverksåtkomst).

Testfall per era:
- Typisk omröstning med siffror
- Acklamation utan siffror
- OCR-buggig text (Era 1)
- Förberedande + huvudvotering (Era 2)
- HTML-tabell med alla 349 ledamöter (Era 3, mockat)
- `rm_to_year()` för alla format

## Avgränsningar

- Parsern hanterar **inte** propositioner — bara protokoll/votering.
- Ingen backfill av befintliga commits (undviker SHA-rewrite).
- Pre-1971 lagar: `Votering: ej tillgänglig` utan försök till parsning.
- Individuella ledamötröster lagras **inte** i commit-meddelandet (bara aggregat + partier).
