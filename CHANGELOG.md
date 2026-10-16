# Changelog

## Unreleased

- Documentation: `docs/pipeline.md`, generated dataset card copy, licences, this changelog.
- CI: GitHub Actions workflow that runs the tests, rebuilds the datasets from their seeds,
  validates the release, verifies the committed benchmark checksums and checks the
  leaderboard is up to date.
- `Makefile` with `make all` to run the full pipeline.
- `piikit.preview --per-type` writes stable example images for the README.
- Tests that check README and docs links point at files that exist.
- `piikit/systems/ocr_baseline.py`: Tesseract OCR baseline for document field detection.
  Reads word-level bounding boxes via pytesseract, runs the same regex rules as the
  text-regex baseline, and maps matches back to pixel bounding boxes. Added as `docs-ocr`
  choice in `piikit.baselines` and wired into the Makefile benchmark target and CI.
- `piikit/speech_gen.py` (milestone 3): synthetic speech pilot using Microsoft Edge TTS.
  Takes text records from `text_gen` (which already carry character-offset PII spans),
  calls Edge TTS to generate MP3 audio, then aligns spans from character space into
  audio time space using WordBoundary events. Output: `speech.jsonl` with `start_s` /
  `end_s` timestamps per span. None when TTS tokenises an entity differently (hard-format).
- `piikit/validate_speech.py`: validates speech.jsonl — required keys, audio file
  existence, span text-slice consistency, and time offsets within duration bounds.
- `tests/test_speech_gen.py`: 17 tests covering pure alignment helpers, mocked TTS
  (no network), validator logic, and one real end-to-end integration test
  (skipped when PIIKIT_SKIP_NETWORK=1).
- `schema.py`: added SPEECH_REQUIRED_KEYS and SPEECH_REQUIRED_SPAN_KEYS.

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