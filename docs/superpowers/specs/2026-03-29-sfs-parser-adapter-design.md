# SFSParser Adapter — Design Spec
**Datum:** 2026-03-29
**Status:** Godkänd

## Syfte

Lägga till `SFSParser.parse_from_scraper()` som tar `SFSMetadata + SFSText` från
`RkrattsbaserScraper` och returnerar samma dict-format som befintlig `parse()`.
Uppdatera `to_markdown()` för att inkludera `body_text` när `kapitel` är tomt.

## Bakgrund

`SFSParser.parse()` förväntar sig XML från `rinfo.gov.se` (ECONNREFUSED — nedlagd).
`RkrattsbaserScraper` returnerar `SFSMetadata` och `SFSText` från HTML-scraping.
Dessa måste bridgas utan att bryta `to_markdown()` eller `historical_import.py`.

## Dataflöde

```
RkrattsbaserScraper.fetch_metadata(sfs) -> SFSMetadata
RkrattsbaserScraper.fetch_text(sfs)     -> SFSText | None
          ↓
SFSParser.parse_from_scraper(metadata, text) -> dict
          ↓
SFSParser.to_markdown(parsed) -> str (Markdown + YAML frontmatter)
```

## Ny metod: `parse_from_scraper()`

```python
def parse_from_scraper(
    self,
    metadata: SFSMetadata,
    text: SFSText | None,
) -> dict:
```

### Dict-nycklar (superset av befintlig `parse()`)

| Nyckel | Källa | Notering |
|--------|-------|---------|
| `sfs` | `metadata.sfs` | |
| `titel` | `metadata.titel` | t.ex. "Brottsbalk (1962:700)" |
| `kortnamn` | `None` | Ej tillgänglig från HTML |
| `departement` | `metadata.departement` | |
| `typ` | Härledd | Se logik nedan |
| `ikraftträdande` | `metadata.ikraftträdande` | ISO-datum |
| `utfärdad` | `metadata.utfärdad` | ISO-datum |
| `upphävd` | `None` | Ej tillgänglig från HTML |
| `eu_direktiv` | `[]` | Ej tillgänglig från HTML |
| `kapitel` | `[]` | Ej parsad struktur |
| `forarbete_prop` | `metadata.forarbete_prop` | |
| `forarbete_bet` | `metadata.forarbete_bet` | |
| `forarbete_rskr` | `metadata.forarbete_rskr` | |
| `andringar` | `metadata.andringar` | lista av `SFSAndring` |
| `body_text` | `text.text` om text finns, annars `""` | Rå lagtext |
| `andring_intom` | `text.andring_intom` om text finns | t.ex. "t.o.m. SFS 2026:253" |

### Typ-härledning

```python
GRUNDLAGAR = {"1974:152", "1974:713", "1949:105", "1810:926"}

if metadata.sfs in GRUNDLAGAR:
    typ = "grundlag"
elif "förordning" in metadata.titel.lower():
    typ = "förordning"
else:
    typ = "lag"
```

## Uppdatering av `to_markdown()`

Lägg till i frontmatter:
- `forarbete_prop`, `forarbete_bet`, `forarbete_rskr` (str | None)
- `andring_intom` (str | None)
- `ändringshistorik`: lista av dicts med `sfs`, `ikraftträdande`, `rubrik` från `parsed["andringar"]`

Lägg till i body efter titel-raden:
- Om `kapitel` är tomt och `body_text` finns: lägg till `body_text` direkt

## Filer

| Fil | Action |
|-----|--------|
| `scripts/import/sfs_parser.py` | Modify — add `parse_from_scraper()`, update `to_markdown()` |
| `tests/test_sfs_parser.py` | Create — unit tests, no network |

## Tester

- `parse_from_scraper()` med fullständig metadata (titel, departement, ikraft, förarbeten, ändringar)
- `parse_from_scraper()` med text=None (body_text blir "")
- Typ-härledning: grundlag, förordning, lag
- `to_markdown()` med body_text inkluderar texten i body
- `to_markdown()` med ändringshistorik i frontmatter
- Befintliga `to_markdown()` och `parse_markdown()` tester bryter ej

## Avgränsningar

- `SFSParser.parse()` (XML-parsern) lämnas oförändrad för bakåtkompatibilitet
- `kapitel` förblir alltid `[]` — strukturerad kapitel-parsning är ett separat projekt
- `kortnamn` och `upphävd` förblir `None` — ej tillgängliga från `rkrattsbaser.gov.se`
