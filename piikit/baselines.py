"""Baseline systems for the benchmark.

Usage:
    python -m piikit.baselines text-empty  --bench benchmark --out preds_empty.jsonl
    python -m piikit.baselines text-regex  --bench benchmark --out preds_regex.jsonl
    python -m piikit.baselines docs-empty  --bench benchmark --out preds_docs_empty.jsonl
    python -m piikit.baselines docs-ocr    --bench benchmark --out preds_docs_ocr.jsonl

text-empty / docs-empty predict nothing (the floor). text-regex is a rule-based system
written with knowledge of the formats this generator emits (reserved email domains, the
555-01xx phone range, the two-letter ID format, ...). Treat its score as an optimistic
reference for simple rules, not as evidence about real-world text.

docs-ocr runs Tesseract on every document image, then applies the same regex rules to
the recognised text and maps matches back to pixel bounding boxes. Requires pytesseract
and a system Tesseract installation (brew install tesseract / apt-get install tesseract-ocr).
On clean synthetic documents Tesseract performs near-perfectly; treat the result as an
upper bound for simple OCR+regex rather than evidence about real scanned documents.
"""

import argparse
import json
import re
from pathlib import Path

from piikit.freeze import read_jsonl, verify_frozen

MONTHS = ("January|February|March|April|May|June|July|August|"
          "September|October|November|December")

# Order matters: specific patterns claim their characters before the name heuristic runs.
PATTERNS = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("PHONE", re.compile(r"(?:\+1[-\s])?(?:\(555\)\s|555[-\s])\d{4}")),
    ("ADDRESS", re.compile(
        r"\b\d{1,3} [A-Z][a-z]+ (?:Street|Road|Avenue|Lane|Way|Drive|Court), [A-Z][a-z]+\b")),
    ("ID_NUMBER", re.compile(r"\b[A-Z]{2}-\d{6}\b")),
    ("DATE_OF_BIRTH", re.compile(
        rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{2}}/\d{{2}}/\d{{4}}\b|\b(?:{MONTHS}) \d{{1,2}}, \d{{4}}\b")),
]
CAPITAL_RUN = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b")
NOT_NAMES = {"Customer", "Hello", "Hi", "Please", "Thanks", "Dear", "Patient", "Registered",
             "Contact", "Support", "Reference", "Verification", "Shipping", "Forwarded"}


def _overlaps(start, end, taken):
    return any(start < e and s < end for s, e in taken)


def predict_text(text: str) -> list:
    spans, taken = [], []
    for label, pattern in PATTERNS:
        for m in pattern.finditer(text):
            if not _overlaps(m.start(), m.end(), taken):
                spans.append({"start": m.start(), "end": m.end(), "label": label})
                taken.append((m.start(), m.end()))

    for m in CAPITAL_RUN.finditer(text):
        words = m.group().split(" ")
        offset = m.start()
        while words and words[0] in NOT_NAMES:
            offset += len(words[0]) + 1
            words = words[1:]
        if len(words) >= 2:
            start, end = offset, offset + len(" ".join(words))
            if not _overlaps(start, end, taken):
                spans.append({"start": start, "end": end, "label": "PERSON"})
                taken.append((start, end))
    return sorted(spans, key=lambda s: (s["start"], s["end"]))


def run(kind: str, bench_dir: Path, out: Path):
    errors = verify_frozen(bench_dir)
    if errors:
        raise ValueError("frozen benchmark check failed: " + "; ".join(errors))

    if kind.startswith("text"):
        records = read_jsonl(bench_dir / "text" / "inputs.jsonl")
        if kind == "text-ner":
            from piikit.systems.ner_baseline import run_ner_baseline
            return run_ner_baseline(bench_dir, out)
        preds = [{"id": r["id"], "spans": predict_text(r["text"]) if kind == "text-regex" else []}
                 for r in records]
    elif kind == "docs-ocr":
        from piikit.systems.ocr_baseline import run_ocr_baseline
        return run_ocr_baseline(bench_dir, out)
    else:
        records = read_jsonl(bench_dir / "docs" / "inputs.jsonl")
        preds = [{"id": r["id"], "fields": []} for r in records]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for p in preds:
            f.write(json.dumps(p, sort_keys=True) + "\n")
    return preds


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["text-empty", "text-regex", "text-ner",
                                         "docs-empty", "docs-ocr"])
    parser.add_argument("--bench", type=Path, default=Path("benchmark"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    preds = run(args.kind, args.bench, args.out)
    print(f"Wrote {len(preds)} predictions to {args.out}")


if __name__ == "__main__":
    main()