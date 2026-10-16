"""OCR baseline for the document benchmark.

Uses Tesseract (via pytesseract) to read word-level bounding boxes from each
document image, reconstructs the text with tracked character positions, then
runs the same regex patterns as the text-regex baseline.  Each regex match is
mapped back to the union of the word boxes that cover it.

The documents are synthetic, clean and axis-aligned, so Tesseract performs
near-perfectly here.  Treat this result as an upper bound for simple OCR+regex
rather than as evidence about real-world scanned documents.

Public API
----------
    ocr_document(image_path) -> list[dict]
        Return a list of {"label": ..., "bbox": [x0, y0, x1, y1]} predictions
        for one image.

    run_ocr_baseline(bench_dir, out) -> list[dict]
        Score every document in the frozen benchmark and write predictions.

Requires
--------
    pytesseract >= 0.3.13  (pip install pytesseract)
    tesseract   >= 4.0     (brew install tesseract  /  apt-get install tesseract-ocr)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pytesseract and Pillow are required for the OCR baseline. "
        "Install them with: pip install pytesseract pillow"
    ) from exc

from piikit.baselines import CAPITAL_RUN, NOT_NAMES, PATTERNS, _overlaps

# ---------------------------------------------------------------------------
# Word-level OCR -> tracked character positions
# ---------------------------------------------------------------------------

_CONF_THRESHOLD = 30  # Tesseract confidence 0-100; discard noisy reads


def _ocr_words(image_path: Path) -> list[dict]:
    """Return a list of word dicts with text and pixel bboxes.

    Each dict has:
        text  - the recognised word string (stripped)
        x0, y0, x1, y1 - pixel bounding box (origin top-left)
        conf  - Tesseract confidence (0-100)
    """
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        conf = int(data["conf"][i])
        if conf < _CONF_THRESHOLD:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append({"text": text, "x0": x, "y0": y, "x1": x + w, "y1": y + h, "conf": conf})
    return words


def _build_text_index(words: list[dict]) -> tuple[str, list[tuple[int, int]]]:
    """Join words into a single string and record each word's char range.

    Returns:
        full_text  - words joined by single spaces
        ranges     - list of (start, end) char index for each word in full_text
    """
    parts, ranges, cursor = [], [], 0
    for word in words:
        start = cursor
        end = cursor + len(word["text"])
        parts.append(word["text"])
        ranges.append((start, end))
        cursor = end + 1  # +1 for the space separator
    return " ".join(parts), ranges


def _union_bbox(words: list[dict], word_indices: list[int]) -> list[int]:
    """Return the pixel bounding box that covers all the given words."""
    xs0 = [words[i]["x0"] for i in word_indices]
    ys0 = [words[i]["y0"] for i in word_indices]
    xs1 = [words[i]["x1"] for i in word_indices]
    ys1 = [words[i]["y1"] for i in word_indices]
    return [min(xs0), min(ys0), max(xs1), max(ys1)]


def _words_for_span(char_start: int, char_end: int,
                    ranges: list[tuple[int, int]]) -> list[int]:
    """Return indices of words that overlap with [char_start, char_end)."""
    return [
        i for i, (ws, we) in enumerate(ranges)
        if ws < char_end and we > char_start
    ]


# ---------------------------------------------------------------------------
# Regex matching on OCR text -> field predictions
# ---------------------------------------------------------------------------

def _predict_fields(full_text: str, words: list[dict],
                    ranges: list[tuple[int, int]]) -> list[dict]:
    """Run regex + name heuristic on OCR text; map matches to pixel bboxes."""
    fields, taken = [], []

    for label, pattern in PATTERNS:
        for m in pattern.finditer(full_text):
            if _overlaps(m.start(), m.end(), taken):
                continue
            word_idx = _words_for_span(m.start(), m.end(), ranges)
            if not word_idx:
                continue
            fields.append({"label": label, "bbox": _union_bbox(words, word_idx)})
            taken.append((m.start(), m.end()))

    for m in CAPITAL_RUN.finditer(full_text):
        match_words = m.group().split(" ")
        offset = m.start()
        while match_words and match_words[0] in NOT_NAMES:
            offset += len(match_words[0]) + 1
            match_words = match_words[1:]
        if len(match_words) < 2:
            continue
        start = offset
        end = offset + len(" ".join(match_words))
        if _overlaps(start, end, taken):
            continue
        word_idx = _words_for_span(start, end, ranges)
        if not word_idx:
            continue
        fields.append({"label": "PERSON", "bbox": _union_bbox(words, word_idx)})
        taken.append((start, end))

    return fields


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ocr_document(image_path: Path) -> list[dict]:
    """Return predicted PII fields for one document image.

    Args:
        image_path: path to the PNG image.

    Returns:
        List of {"label": str, "bbox": [x0, y0, x1, y1]}.
    """
    words = _ocr_words(Path(image_path))
    if not words:
        return []
    full_text, ranges = _build_text_index(words)
    return _predict_fields(full_text, words, ranges)


def run_ocr_baseline(bench_dir: Path, out: Path) -> list[dict]:
    """Run the OCR baseline over the frozen benchmark and write predictions.

    Args:
        bench_dir: path to the frozen benchmark directory.
        out:       path to write the predictions JSONL file.

    Returns:
        The list of prediction dicts that were written.
    """
    from piikit.freeze import read_jsonl, verify_frozen

    errors = verify_frozen(bench_dir)
    if errors:
        raise ValueError("frozen benchmark check failed: " + "; ".join(errors))

    inputs = read_jsonl(bench_dir / "docs" / "inputs.jsonl")
    image_base = bench_dir / "docs"

    preds = []
    for record in inputs:
        image_path = image_base / record["image"]
        fields = ocr_document(image_path)
        preds.append({"id": record["id"], "fields": fields})

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for p in preds:
            f.write(json.dumps(p, sort_keys=True) + "\n")
    return preds
