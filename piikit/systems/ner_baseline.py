"""Neural NER baseline using spaCy en_core_web_trf (or en_core_web_sm as fallback).

Maps spaCy entity types onto this dataset's label set. Predictions that cannot be
mapped to a known label are dropped.

Usage:
    python -m piikit.systems.ner_baseline --bench benchmark --out build/preds/text_ner.jsonl

Requires:
    pip install spacy
    python -m spacy download en_core_web_trf   # transformer model (recommended)
    # or
    python -m spacy download en_core_web_sm    # small model (no GPU required)

Add to the leaderboard:
    python -m piikit.score text --pred build/preds/text_ner.jsonl --name spacy-trf --save
    python -m piikit.leaderboard --bench benchmark
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# spaCy label → this dataset's label mapping
# (spaCy ent type → dataset label, or None to drop)
# ---------------------------------------------------------------------------
SPACY_TO_LABEL: dict[str, str | None] = {
    "PERSON":   "PERSON",
    "ORG":      None,          # organisations are NOT PII in this dataset
    "GPE":      None,          # geopolitical entities, too coarse
    "LOC":      "ADDRESS",     # lossy: city/country → ADDRESS
    "FAC":      None,
    "EMAIL":    "EMAIL",       # spaCy 3.x sometimes tags emails
    "PHONE":    "PHONE",       # custom rule might fire
    "DATE":     "DATE_OF_BIRTH",  # lossy: any date → DOB (many false positives)
    "CARDINAL": None,
    "MONEY":    None,
    "PERCENT":  None,
    "TIME":     None,
    "NORP":     None,
    "LANGUAGE": None,
    "PRODUCT":  None,
    "EVENT":    None,
    "WORK_OF_ART": None,
    "LAW":      None,
    "QUANTITY": None,
    "ORDINAL":  None,
}

# Also add basic regex patterns for EMAIL and PHONE not caught by NER
import re

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
_PHONE_RE = re.compile(
    r"(?:\+1[-\s])?(?:\(555\)\s|555[-\s])\d{4}"
)
_ID_RE = re.compile(r"\b[A-Z]{2}-\d{6}\b")


def _regex_spans(text: str, existing: list[dict]) -> list[dict]:
    """Add regex-detected EMAIL, PHONE, ID_NUMBER spans not already found by NER."""
    taken = {(s["start"], s["end"]) for s in existing}
    extras = []
    for label, pattern in [("EMAIL", _EMAIL_RE), ("PHONE", _PHONE_RE), ("ID_NUMBER", _ID_RE)]:
        for m in pattern.finditer(text):
            if (m.start(), m.end()) not in taken:
                extras.append({"start": m.start(), "end": m.end(), "label": label})
                taken.add((m.start(), m.end()))
    return extras


def _load_spacy():
    """Load the best available spaCy model."""
    try:
        import spacy
    except ImportError:
        raise ImportError(
            "spaCy is required for the NER baseline.\n"
            "Install it with: pip install spacy\n"
            "Then download a model: python -m spacy download en_core_web_trf"
        )
    for model_name in ("en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm"):
        try:
            nlp = spacy.load(model_name)
            print(f"Loaded spaCy model: {model_name}")
            return nlp
        except OSError:
            continue
    raise OSError(
        "No spaCy English model found. Download one with:\n"
        "  python -m spacy download en_core_web_trf\n"
        "  or: python -m spacy download en_core_web_sm"
    )


def predict_text_ner(text: str, nlp) -> list[dict]:
    """Run spaCy NER on text and return spans in this dataset's format."""
    doc = nlp(text)
    spans = []
    for ent in doc.ents:
        mapped = SPACY_TO_LABEL.get(ent.label_)
        if mapped is not None:
            spans.append({"start": ent.start_char, "end": ent.end_char, "label": mapped})

    # Augment with regex for types spaCy often misses in this synthetic format
    spans.extend(_regex_spans(text, spans))
    return sorted(spans, key=lambda s: (s["start"], s["end"]))


def run_ner_baseline(bench_dir: Path, out: Path) -> list[dict]:
    from piikit.freeze import read_jsonl, verify_frozen

    errors = verify_frozen(bench_dir)
    if errors:
        raise ValueError("frozen benchmark check failed: " + "; ".join(errors))

    nlp = _load_spacy()
    records = read_jsonl(bench_dir / "text" / "inputs.jsonl")
    preds = [{"id": r["id"], "spans": predict_text_ner(r["text"], nlp)} for r in records]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for p in preds:
            f.write(json.dumps(p, sort_keys=True) + "\n")
    return preds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", type=Path, default=Path("benchmark"))
    parser.add_argument("--out", type=Path, default=Path("build/preds/text_ner.jsonl"))
    args = parser.parse_args()

    preds = run_ner_baseline(args.bench, args.out)
    print(f"Wrote {len(preds)} predictions to {args.out}")
    print("Score with: python -m piikit.score text --pred", args.out, "--name spacy-ner --save")


if __name__ == "__main__":
    main()
