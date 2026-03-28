# Lagläget — Development Guide

## Project Overview

**Lagläget** models the entire Swedish legal corpus (SFS — Svensk författningssamling) as a
GitHub repository, where every git primitive maps to a legislative concept. The authoritative
data source is Riksdagens öppna data (`data.riksdagen.se`) and the legal information system
`rinfo.gov.se` (Lagrummet).

## Key Concepts

- One file per lag/förordning in Markdown with YAML frontmatter
- Commits represent riksdagsbeslut (legislative decisions)
- Tags represent ikraftträdandedatum (entry-into-force dates)
- PRs represent propositioner (government bills)
- CODEOWNERS maps departements to their SFS ranges

## File Format

Every law file is Markdown with YAML frontmatter. See `schema/law.schema.json` for the
full schema. Key fields: `sfs`, `titel`, `departement`, `typ`, `ikraftträdande`.

## Commit Message Format

```
SFS YYYY:NNN — <kort beskrivning>

Proposition: YYYY/YY:NNN
Utskott: <utskottskod>
Votering: NNN ja / NNN nej / NNN avstår
Ikraftträdande: YYYY-MM-DD
Riksdagen-dok: <dokumentid>
```

## Scripts

- `scripts/import/historical_import.py` — Reconstruct full git history from rinfo.gov.se
- `scripts/import/riksdagen_sync.py` — Nightly API sync with Riksdagen
- `scripts/import/sfs_parser.py` — Parse SFS XML → Markdown
- `scripts/validate/frontmatter.py` — Validate YAML frontmatter
- `scripts/validate/cross_references.py` — Check §-hänvisningar
- `scripts/validate/sfs_uniqueness.py` — Ensure no duplicate SFS numbers
- `scripts/release/create_corpus_snapshot.py` — Bundle laws in force on a date

## Validation

Run before committing:
```bash
python scripts/validate/frontmatter.py lagar/
python scripts/validate/cross_references.py
python scripts/validate/sfs_uniqueness.py
```

## API Rate Limits

- Riksdagen API: 1 req/sec with exponential backoff
- rinfo.gov.se: 0.5 req/sec during historical import
- Always set `User-Agent: Lagläget/1.0`
