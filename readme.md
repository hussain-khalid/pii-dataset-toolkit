# PII Dataset Toolkit

A small, reproducible toolkit for building and validating **synthetic** datasets for
personal-data (PII) detection. All data is fabricated: no real people, no real contact
details.

> Work in progress. This README grows with each milestone.

## Status

| Milestone | Status |
| --- | --- |
| 1. Synthetic text with PII spans, schema, validator, tests | done |
| 2. Synthetic document images with bounding boxes | planned |
| 3. Merge, deduplicate, provenance, dataset card | planned |
| 4. Benchmark: frozen split, scorer, baseline, leaderboard | planned |
| 5. Documentation and CI polish | planned |

## Quick start

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python -m piikit.text_gen --n 1000 --seed 42 --out data/raw/text.jsonl
python -m piikit.validate data/raw/text.jsonl
pytest -v
```

## Text record format (JSONL, one record per line)

```json
{
  "id": "txt-000000",
  "text": "Contact: elena_fischer@example.net or call +1 555 0170.",
  "spans": [
    {"start": 9, "end": 34, "label": "EMAIL", "text": "elena_fischer@example.net"},
    {"start": 43, "end": 54, "label": "PHONE", "text": "+1 555 0170"}
  ],
  "source": "synthetic/text_gen",
  "generator_version": "0.1.0",
  "seed": 42,
  "template_id": "t07"
}
```

Offsets are Python string indices (`text[start:end]`), end exclusive. Labels: `PERSON`,
`EMAIL`, `PHONE`, `ADDRESS`, `ID_NUMBER`, `DATE_OF_BIRTH`.

## How the synthetic data stays fake

- Emails use the reserved `example.com`, `example.org` and `example.net` domains.
- Phone numbers use the 555-0100 to 555-0199 range reserved for fiction.
- ID numbers follow a made-up format (two letters and six digits).
- Names are random combinations from short word lists, and addresses use invented
  street and city names. A generated name can still match a real person by chance.

## Validation checks (current)

- Required keys and types are present.
- Every span satisfies `text[start:end] == span["text"]`, and offsets lie inside the text.
- Labels belong to the allowed set, and spans do not overlap.
- Record ids are unique, and the file is valid JSONL.
- Same seed produces a byte-identical file (checked by a test).