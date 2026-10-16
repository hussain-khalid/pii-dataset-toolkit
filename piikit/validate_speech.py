"""Validate a speech JSONL produced by piikit.speech_gen.

Usage:
    python -m piikit.validate_speech data/raw/speech/speech.jsonl

Checks every record for:
  - All required top-level keys present
  - Required span keys present, including start_s / end_s
  - start_s < end_s (when both are set)
  - end_s <= duration_s
  - audio file exists relative to the JSONL parent directory
  - label is one of the known LABELS set
  - character span start < end and the text slice matches the span text
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from piikit.schema import LABELS, SPEECH_REQUIRED_KEYS, SPEECH_REQUIRED_SPAN_KEYS


def validate_speech(jsonl_path: Path) -> list[str]:
    """Validate a speech JSONL file.

    Args:
        jsonl_path: path to the speech.jsonl file.

    Returns:
        A list of human-readable error strings (empty = all good).
    """
    base_dir = jsonl_path.parent
    errors: list[str] = []

    with jsonl_path.open(encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]

    if not lines:
        return ["file is empty"]

    seen_ids: set[str] = set()

    for lineno, line in enumerate(lines, start=1):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON — {exc}")
            continue

        rid = rec.get("id", f"<line {lineno}>")

        # Duplicate IDs
        if rid in seen_ids:
            errors.append(f"{rid}: duplicate id")
        seen_ids.add(rid)

        # Required top-level keys
        for k in SPEECH_REQUIRED_KEYS:
            if k not in rec:
                errors.append(f"{rid}: missing key '{k}'")

        # Audio file existence
        audio_rel = rec.get("audio")
        if audio_rel:
            audio_path = base_dir / audio_rel
            if not audio_path.exists():
                errors.append(f"{rid}: audio file not found: {audio_path}")
        else:
            errors.append(f"{rid}: 'audio' key is empty or missing")

        # Duration must be positive
        duration_s = rec.get("duration_s")
        if duration_s is not None and duration_s <= 0:
            errors.append(f"{rid}: duration_s must be > 0, got {duration_s}")

        # Spans
        text = rec.get("text", "")
        for i, span in enumerate(rec.get("spans", [])):
            sid = f"{rid}/span[{i}]"

            # Required span keys
            for k in SPEECH_REQUIRED_SPAN_KEYS:
                if k not in span:
                    errors.append(f"{sid}: missing key '{k}'")

            label = span.get("label")
            if label and label not in LABELS:
                errors.append(f"{sid}: unknown label '{label}'")

            # Character offsets
            s, e = span.get("start"), span.get("end")
            if s is not None and e is not None:
                if s >= e:
                    errors.append(f"{sid}: start ({s}) >= end ({e})")
                elif text:
                    actual = text[s:e]
                    expected = span.get("text", "")
                    if actual != expected:
                        errors.append(
                            f"{sid}: text slice mismatch: "
                            f"got '{actual}', expected '{expected}'"
                        )

            # Time offsets (None is allowed — hard-format entity)
            start_s = span.get("start_s")
            end_s = span.get("end_s")
            if start_s is not None and end_s is not None:
                if start_s >= end_s:
                    errors.append(
                        f"{sid}: start_s ({start_s}) >= end_s ({end_s})"
                    )
                if duration_s is not None and end_s > duration_s + 0.05:
                    # 50 ms tolerance for duration estimation rounding
                    errors.append(
                        f"{sid}: end_s ({end_s}) > duration_s ({duration_s})"
                    )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jsonl", type=Path, help="speech.jsonl to validate")
    args = parser.parse_args()

    errors = validate_speech(args.jsonl)
    if errors:
        for e in errors:
            print("ERROR:", e)
        raise SystemExit(1)

    with args.jsonl.open(encoding="utf-8") as f:
        n = sum(1 for line in f if line.strip())
    print(f"OK — {n} records, no errors found in {args.jsonl}")


if __name__ == "__main__":
    main()
