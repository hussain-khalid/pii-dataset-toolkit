"""Tests for the OCR baseline (piikit/systems/ocr_baseline.py).

These tests use real Tesseract calls on synthetic document images.
If Tesseract is not installed the tests are skipped automatically.
"""

import importlib
import tempfile
from pathlib import Path

import pytest

from piikit.doc_gen import generate_docs

# Skip the whole module if tesseract isn't available on this machine.
pytesseract = pytest.importorskip("pytesseract", reason="pytesseract not installed")
try:
    pytesseract.get_tesseract_version()
except Exception:
    pytest.skip("tesseract binary not found", allow_module_level=True)

from piikit.systems.ocr_baseline import (  # noqa: E402
    _build_text_index,
    _ocr_words,
    _predict_fields,
    _union_bbox,
    _words_for_span,
    ocr_document,
    run_ocr_baseline,
)


# ---- unit tests on helper functions (no Tesseract needed) ----

def _fake_words(*texts):
    """Build fake word dicts with sequential non-overlapping bboxes."""
    words, x = [], 0
    for t in texts:
        words.append({"text": t, "x0": x, "y0": 0, "x1": x + len(t) * 8, "y1": 20, "conf": 90})
        x += len(t) * 8 + 4
    return words


def test_build_text_index_joins_with_spaces_and_tracks_ranges():
    words = _fake_words("Hello", "World")
    text, ranges = _build_text_index(words)
    assert text == "Hello World"
    assert ranges[0] == (0, 5)
    assert ranges[1] == (6, 11)


def test_words_for_span_finds_overlapping_words():
    words = _fake_words("Anna", "Keller")
    _, ranges = _build_text_index(words)
    # "Anna Keller" is chars 0-11; both words should be found
    assert _words_for_span(0, 11, ranges) == [0, 1]
    # Only first word
    assert _words_for_span(0, 4, ranges) == [0]


def test_union_bbox_covers_all_words():
    words = _fake_words("Anna", "Keller")
    bbox = _union_bbox(words, [0, 1])
    assert bbox[0] == words[0]["x0"]
    assert bbox[2] == words[1]["x1"]


def test_predict_fields_finds_email_pattern():
    words = _fake_words("Email:", "anna@example.com")
    text, ranges = _build_text_index(words)
    fields = _predict_fields(text, words, ranges)
    labels = [f["label"] for f in fields]
    assert "EMAIL" in labels


def test_predict_fields_finds_person_pattern():
    words = _fake_words("Name:", "Anna", "Keller")
    text, ranges = _build_text_index(words)
    fields = _predict_fields(text, words, ranges)
    labels = [f["label"] for f in fields]
    assert "PERSON" in labels


# ---- integration tests: real Tesseract on synthetic images ----

def test_ocr_document_returns_field_list():
    with tempfile.TemporaryDirectory() as tmp:
        record = generate_docs(1, 42, Path(tmp))[0]
        image_path = Path(tmp) / record["image"]
        fields = ocr_document(image_path)
        assert isinstance(fields, list)
        # Every prediction must have label and valid bbox
        for f in fields:
            assert "label" in f and "bbox" in f
            x0, y0, x1, y1 = f["bbox"]
            assert x0 < x1 and y0 < y1


def test_ocr_document_predicts_at_least_one_field_on_id_card():
    """An ID card has NAME, DOB, ID NO, ADDRESS — OCR+regex should catch some."""
    with tempfile.TemporaryDirectory() as tmp:
        # Generate until we get an id_card (seed 42 gives one quickly)
        records = generate_docs(20, 42, Path(tmp))
        id_cards = [r for r in records if r["doc_type"] == "id_card"]
        assert id_cards, "no id_card in the first 20 docs — adjust the test"
        fields = ocr_document(Path(tmp) / id_cards[0]["image"])
        assert len(fields) > 0, "expected at least one PII field from an ID card"


def test_ocr_bbox_lies_inside_the_image():
    with tempfile.TemporaryDirectory() as tmp:
        record = generate_docs(1, 42, Path(tmp))[0]
        image_path = Path(tmp) / record["image"]
        fields = ocr_document(image_path)
        for f in fields:
            x0, y0, x1, y1 = f["bbox"]
            assert x0 >= 0 and y0 >= 0
            assert x1 <= record["width"] and y1 <= record["height"]


def test_run_ocr_baseline_writes_one_prediction_per_benchmark_id():
    from piikit.build_release import build_release
    from piikit.freeze import freeze, read_jsonl
    from tests.test_release import make_inputs

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp, n_text=200, n_docs=30)
        build_release(text_path, docs_path, tmp / "release")
        freeze(tmp / "release", tmp / "bench")

        preds = run_ocr_baseline(tmp / "bench", tmp / "preds.jsonl")
        bench_ids = {r["id"] for r in read_jsonl(tmp / "bench" / "docs" / "inputs.jsonl")}
        pred_ids = {p["id"] for p in preds}
        assert pred_ids == bench_ids


def test_run_ocr_baseline_refuses_tampered_benchmark():
    from piikit.build_release import build_release
    from piikit.freeze import freeze
    from tests.test_release import make_inputs

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp, n_text=200, n_docs=30)
        build_release(text_path, docs_path, tmp / "release")
        freeze(tmp / "release", tmp / "bench")

        inputs = tmp / "bench" / "docs" / "inputs.jsonl"
        inputs.write_text(inputs.read_text(encoding="utf-8") + "\n", encoding="utf-8")

        with pytest.raises(ValueError, match="frozen benchmark check failed"):
            run_ocr_baseline(tmp / "bench", tmp / "preds.jsonl")
