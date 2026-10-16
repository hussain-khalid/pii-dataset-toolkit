# Changelog

## Unreleased

- Documentation: `docs/pipeline.md`, generated dataset card copy, licences, this changelog.
- CI: GitHub Actions workflow that runs the tests, rebuilds the datasets from their seeds,
  validates the release, verifies the committed benchmark checksums and checks the
  leaderboard is up to date.
- `Makefile` with `make all` to run the full pipeline.
- `piikit.preview --per-type` writes stable example images for the README.
- Tests that check README and docs links point at files that exist.

## 0.2.0

- Text generator: about 25% of values now use a less common format (name order and case,
  obfuscated emails, other phone, ID, date and address formats).
- Text generator: new no-PII records with lookalikes (ordinary dates, organisation names).
- Benchmark: frozen test split with checksums, strict and relaxed text scoring, box-IoU
  document scoring, bootstrap confidence intervals, label mappings (Presidio-style, CoNLL-style),
  empty and regex baselines, generated leaderboard.
- Reason for the generator change: the first regex baseline scored F1 1.000, so the
  benchmark could not rank anything.

## 0.1.0

- Synthetic text records with character-offset PII spans, and a validator.
- Synthetic document images (invoice, form, ID card) with exact bounding boxes, a validator
  and a preview renderer.
- Release builder: exact and near-duplicate removal, hash-based train/validation/test split,
  provenance on every record, checksum manifest, generated dataset card, release validator.