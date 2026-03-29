# historical_import.py Integration — Design Spec
**Datum:** 2026-03-29
**Status:** Godkänd

## Syfte

Ersätta det döda `rinfo.gov.se`-anropet i `historical_import.py` med
`RkrattsbaserScraper` + `SFSParser.parse_from_scraper()`.

## Bakgrund

`run_import()` loopar år för år, gissar SFS-nummer sekventiellt (1, 2, 3…),
och anropar `fetch_sfs_entry()` → `rinfo.gov.se` (ECONNREFUSED).
Det nya flödet hämtar **alla** SFS-nummer via `enumerate_sfs_numbers()` (en paginerad
lista med 11 141 poster) och processar dem kronologiskt efter ikraftträdandedatum.

## Nytt dataflöde

```
RkrattsbaserScraper.enumerate_sfs_numbers()   -> list[str]  (~11 141 st)
          ↓ sortera efter ikraftträdandedatum
for sfs in sorted_numbers:
    metadata = scraper.fetch_metadata(sfs)    -> SFSMetadata | None
    text     = scraper.fetch_text(sfs)        -> SFSText | None
    parsed   = parser.parse_from_scraper(metadata, text)
    markdown = parser.to_markdown(parsed)
    create_commit(...)
```

## Ändringar i `historical_import.py`

### Ny funktion: `run_import_rkrattsbaser()`

Ersätter `run_import()` som ny default-entry-point. Behåller `run_import()` oförändrad
(bakåtkompatibel om man vill testa mot rinfo).

```python
def run_import_rkrattsbaser(
    dry_run: bool = False,
    sfs_filter: list[str] | None = None,
) -> None:
```

- `sfs_filter`: om angivet, processa bara dessa SFS-nummer (för tester/delskörd)
- Sorterar SFS-nummer efter `metadata.ikraftträdande` (None sist, kronologisk annars)
- Anropar `create_commit()` med samma signatur som befintlig kod

### Ny hjälpfunktion: `sort_key_for_sfs()`

```python
def sort_key_for_sfs(metadata: SFSMetadata) -> str:
    """Return sortable key: ikraftträdande ISO date, or '9999-99-99' for None."""
    return metadata.ikraftträdande or "9999-99-99"
```

### Uppdatering av `main()`

Lägg till `--source` flagga:
- `--source rkrattsbaser` (ny default) → anropar `run_import_rkrattsbaser()`
- `--source rinfo` → anropar befintlig `run_import()` (backward compat)

Lägg till `--sfs` flagga för att begränsa körning till enstaka SFS-nummer (debug).

## Filer

| Fil | Action |
|-----|--------|
| `scripts/import/historical_import.py` | Modify — add `run_import_rkrattsbaser()`, update `main()` |
| `tests/test_historical_import.py` | Create — unit tests, mocked scraper, no network |

## Tester

- `run_import_rkrattsbaser(dry_run=True, sfs_filter=["1962:700"])`: mockar scraper, verifierar att `create_commit` anropas med rätt argument
- `sort_key_for_sfs()`: None → "9999-99-99", datum → datum
- `main()` med `--source rkrattsbaser --dry-run --sfs 1962:700` (integration CLI test)
- Verifierar att `run_import()` (gamla rinfo-funktionen) är oförändrad

## Avgränsningar

- `fetch_sfs_entry()`, `fetch_consolidated_text()`, `fetch_change_feed()` lämnas oförändrade
- Votering-logiken (`fetch_protokoll_section`, `prot_parser`) återanvänds oförändrad
- Enum-steget (`enumerate_sfs_numbers`) sker en gång per körning, inte per år
- Ingen parallell hämtning — sekventiell med `REQUEST_DELAY` som scraper hanterar
