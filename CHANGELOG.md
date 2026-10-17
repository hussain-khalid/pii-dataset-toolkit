# Changelog

## Unreleased

- `piikit/push_hub.py`: Hugging Face Hub dataset publishing; converts release into `DatasetDict` subsets (`text`, `docs`), uploads document images, and uploads the dataset card.
- `piikit/text_gen.py`: Added multilingual locale support (`--locale de/fr/es`) with localized names, streets, cities, and email domains; added adversarial non-standard formatting mode (`--hard`).
- `piikit/speech_gen.py`: Added locale-aware voice selection for Edge TTS neural voices (`de-DE-KatjaNeural`, `fr-FR-DeniseNeural`, `es-ES-ElviraNeural`).
- `piikit/doc_gen.py`: Added scan-like degradation (`--noisy`) with rotation, blur, and JPEG compression artifacts; added custom font loading via `--font` or `PIIKIT_FONT`.
- `piikit/systems/ner_baseline.py`: Neural NER baseline using spaCy English models (`en_core_web_trf` / `en_core_web_sm`) mapped to dataset labels, with regex rules for high-precision formats. Wired into `piikit.baselines` as `text-ner`.
- `piikit/leaderboard_html.py`: Interactive dark-themed standalone HTML dashboard generator (`docs/leaderboard.html`). Added `leaderboard-html` target in `Makefile`.
- `piikit/submit.py`: One-command submission CLI to validate, score, and append new systems to both markdown and HTML leaderboards.
- `tests/test_next_level.py`: Unit test coverage for multilingual text/speech, noisy docs, hard mode, NER mapping, HTML leaderboard, and submit orchestration.

- `piikit/systems/ocr_baseline.py`: Tesseract OCR baseline for document field detection.
  Reads word-level bounding boxes via pytesseract, runs the same regex rules as the
  text-regex baseline, and maps matches back to pixel bounding boxes. Added as `docs-ocr`
  choice in `piikit.baselines` and wired into the Makefile benchmark target and CI.
- `piikit/speech_gen.py` (milestone 3): synthetic speech pilot using Microsoft Edge TTS.
  Takes text records from `text_gen` (which already carry character-offset PII spans),
  calls Edge TTS to generate MP3 audio, then aligns spans from character space into
  audio time space using sentence-boundary cues (Edge TTS 7.x dropped word-level events;
  proportional interpolation is used within each sentence). Output: `speech.jsonl` with
  `start_s` / `end_s` timestamps per span. `null` when TTS tokenises an entity differently.
- `piikit/validate_speech.py`: validates speech.jsonl — required keys, audio file
  existence, span text-slice consistency, and time offsets within duration bounds.
- `tests/test_speech_gen.py`: 17 tests covering pure alignment helpers, mocked TTS
  (no network), validator logic, and one real end-to-end integration test
  (skipped when `PIIKIT_SKIP_NETWORK=1`).
- `schema.py`: added `SPEECH_REQUIRED_KEYS` and `SPEECH_REQUIRED_SPAN_KEYS`.
- `Makefile`: added `speech` target (runs after `data`, generates 50 records, validates).
- `requirements-dev.txt`: added `edge-tts` and `pytesseract`.
- CI: `PIIKIT_SKIP_NETWORK=1` on unit-test step; separate speech synthesis + validate step.
- README and `docs/pipeline.md`: updated for speech modality, OCR baseline, module table.

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