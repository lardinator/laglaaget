# Lagläget 🇸🇪

**The entire Swedish legal corpus as a Git repository.**

Lagläget models SFS (Svensk författningssamling) using git primitives, where every
legislative concept maps to a git concept. The authoritative data sources are
[Riksdagens öppna data](https://data.riksdagen.se) and [Lagrummet](https://rinfo.gov.se).

## What This Enables

| You want to…                                | Git command                                              |
|----------------------------------------------|----------------------------------------------------------|
| See legislative history                      | `git log`                                                |
| Find who introduced a paragraph              | `git blame lagar/1962/SFS-1962-700.md`                   |
| Compare 50 years of legal change             | `git diff v1975-01-01 v2025-01-01`                       |
| View the exact legal corpus on a past date   | `git checkout v1985-01-01`                               |

## Legislative → Git Mapping

| Legislative concept               | Git concept          |
|------------------------------------|----------------------|
| SFS (Svensk författningssamling)   | Repository           |
| A lag or förordning                | File                 |
| Riksdagsbeslut (ändring i lag)     | Commit               |
| Proposition under beredning        | Branch               |
| Remissvar / lagrådsyttrande        | PR review comment    |
| Utskottsbetänkande (tillstyrkan)   | PR approval          |
| Riksdagsbeslut (omröstning)        | PR merge             |
| Ikraftträdandedatum                | Git tag + Release    |
| Grundlagarna (RF, TF, YGL, SO)    | Protected branch     |
| EU-direktiv (ej transponerat)      | Open Issue           |
| Departement                        | CODEOWNER            |
| Riksdagsledamot                    | Git author           |

## Query Examples

```bash
# What changed in Brottsbalken in the last 10 years?
git log --since="10 years ago" -- lagar/1962/SFS-1962-700.md

# What did Föräldrabalken look like in 1985?
git checkout v1985-01-01 -- lagar/1949/SFS-1949-381.md

# Which riksdagsbeslut introduced the word "barnäktenskap"?
git log -S "barnäktenskap" -- lagar/

# All EU-driven law changes since Sweden joined the EU
git log --grep="EU-direktiv" --after="1994-12-31"

# Which law file has the most commits (most amended law)?
git log --oneline --format="%H" -- lagar/ | \
  xargs -I{} git diff-tree --no-commit-id -r {} --name-only | \
  sort | uniq -c | sort -rn | head -20

# Every change on a specific ikraftträdandedatum
git diff v2020-01-01~1 v2020-01-01

# Laws introduced by Reinfeldts government (Oct 2006 – Oct 2014)
git log --after="2006-10-06" --before="2014-10-03" --oneline

# Exact wording of a paragraph when it was first written
git log --follow --diff-filter=A -- lagar/1962/SFS-1962-700.md | tail -1 | \
  awk '{print $1}' | xargs git show
```

## Repository Structure

```
swedish-law/
├── grundlagar/          ← The four fundamental laws (RF, TF, YGL, SO)
├── lagar/YYYY/          ← All laws, organized by year of enactment
├── förordningar/YYYY/   ← Government ordinances
├── upphävda/YYYY/       ← Repealed laws (archived)
├── schema/              ← JSON Schema for frontmatter + commit message spec
├── scripts/             ← Import, validation, and release scripts
└── .github/             ← Workflows, CODEOWNERS, issue templates
```

## Getting Started

```bash
# Clone
git clone https://github.com/lardinator/lagl-get.git
cd lagl-get

# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Set: GITHUB_TOKEN, RIKSDAGEN_API_BASE, RINFO_BASE

# Validate local files
python scripts/validate/frontmatter.py lagar/
python scripts/validate/cross_references.py

# Run a partial historical import (1990–present)
python scripts/import/historical_import.py --from-year 1990 --dry-run
python scripts/import/historical_import.py --from-year 1990

# Manual sync (without waiting for nightly cron)
python scripts/riksdagen_sync.py --since 2024-01-01
```

## Data Sources

- **Riksdagens öppna data**: `https://data.riksdagen.se` — propositioner, voteringar, ledamöter
- **Lagrummet (rinfo.gov.se)**: `https://rinfo.gov.se` — authoritative SFS texts, historical changes

## License

The Swedish legal corpus is public domain. The tooling in this repository is licensed
under the MIT License.
