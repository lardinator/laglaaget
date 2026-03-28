# Commit Message Format Specification

Every commit to the `main` branch MUST follow this format. The sync scripts and
the `validate.yml` workflow enforce it.

## Format

```
SFS YYYY:NNN — <kort beskrivning av ändringen>

Proposition: YYYY/YY:NNN
Utskott: <utskottskod>
Votering: NNN ja / NNN nej / NNN avstår
Ikraftträdande: YYYY-MM-DD
Riksdagen-dok: <dokumentid>
EU-direktiv: <direktiv-id>

<Optional: free-text description in 1–3 sentences>
```

## Fields

| Field            | Required | Description                                      |
|------------------|----------|--------------------------------------------------|
| Subject line     | Yes      | `SFS YYYY:NNN — <description>`                   |
| Proposition      | Yes      | Proposition number (use `okänd` if pre-1971)      |
| Utskott          | Yes      | Committee code (JuU, KU, SoU, FiU, etc.)         |
| Votering         | Yes      | Vote count: `ja / nej / avstår`                   |
| Ikraftträdande   | Yes      | ISO date when the change enters into force        |
| Riksdagen-dok    | Yes      | Riksdagen document ID                             |
| EU-direktiv      | No       | Only if the change transposes an EU directive      |
| Description      | No       | Free-text explanation (1–3 sentences)              |

## Committee Codes

| Code | Utskott                        |
|------|--------------------------------|
| KU   | Konstitutionsutskottet         |
| FiU  | Finansutskottet                |
| JuU  | Justitieutskottet              |
| CU   | Civilutskottet                 |
| FöU  | Försvarsutskottet              |
| SfU  | Socialförsäkringsutskottet     |
| SoU  | Socialutskottet                |
| KrU  | Kulturutskottet                |
| UbU  | Utbildningsutskottet           |
| TU   | Trafikutskottet                |
| MJU  | Miljö- och jordbruksutskottet  |
| NU   | Näringsutskottet               |
| AU   | Arbetsmarknadsutskottet        |
| UU   | Utrikesutskottet               |
| SkU  | Skatteutskottet                |

## Example

```
SFS 2024:487 — Skärpta straff för grova våldsbrott i 29 kap. BrB

Proposition: 2023/24:87
Utskott: JuU
Votering: 278 ja / 71 nej / 0 avstår
Ikraftträdande: 2024-07-01
Riksdagen-dok: H7C118

Straffminimum för grov misshandel höjs från fängelse i lägst ett år till
lägst ett år och sex månader. Ändringen berör 29 kap. 7 § brottsbalken.
```

## Validation

The commit message format is validated by:
- `scripts/validate/commit_message.py` (local)
- `.github/workflows/validate.yml` (CI)

For historical imports (pre-2000), some fields may be `okänd` (unknown).
