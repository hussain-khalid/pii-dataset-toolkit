"""Validate a text-PII JSONL file against the dataset schema.

Usage:
    python -m piikit.validate data/raw/text.jsonl

Exits with status 1 if any problem is found, so CI can fail on bad data.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from piikit.schema import LABELS, REQUIRED_KEYS, REQUIRED_SPAN_KEYS


def validate_record(record: dict) -> list:
    """Return a list of human-readable problems for one record (empty if valid)."""
    errors = []

    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        return [f"missing keys: {missing}"]

    text, spans = record["text"], record["spans"]
    if not isinstance(text, str) or not text.strip():
        errors.append("text must be a non-empty string")
        return errors
    if not isinstance(spans, list):
        return ["spans must be a list"]

    previous_end = -1
    for i, span in enumerate(spans):
        where = f"span {i}"
        missing_span = [k for k in REQUIRED_SPAN_KEYS if k not in span]
        if missing_span:
            errors.append(f"{where}: missing keys {missing_span}")
            continue

        start, end, label = span["start"], span["end"], span["label"]
        if label not in LABELS:
            errors.append(f"{where}: unknown label {label!r}")
        if not (isinstance(start, int) and isinstance(end, int)):
            errors.append(f"{where}: start and end must be integers")
            continue
        if not (0 <= start < end <= len(text)):
            errors.append(f"{where}: offsets {start}-{end} outside text of length {len(text)}")
            continue
        if text[start:end] != span["text"]:
            errors.append(
                f"{where}: text[{start}:{end}] is {text[start:end]!r}, expected {span['text']!r}"
            )
        if start < previous_end:
            errors.append(f"{where}: overlaps or is out of order with the previous span")
        previous_end = max(previous_end, end)

    return errors


def validate_file(path: Path):
    """Return (errors, stats). Errors are (line_number, message) pairs."""
    errors, ids = [], Counter()
    labels, n_records, n_without_spans = Counter(), 0, 0

    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                errors.append((line_number, "blank line"))
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append((line_number, f"invalid JSON: {exc}"))
                continue

            n_records += 1
            for problem in validate_record(record):
                errors.append((line_number, problem))

            if isinstance(record, dict):
                ids[record.get("id")] += 1
                spans = record.get("spans") if isinstance(record.get("spans"), list) else []
                if not spans:
                    n_without_spans += 1
                labels.update(s.get("label") for s in spans if isinstance(s, dict))

    for record_id, count in ids.items():
        if count > 1:
            errors.append((0, f"duplicate id {record_id!r} appears {count} times"))

    stats = {
        "records": n_records,
        "records_without_pii": n_without_spans,
        "spans_per_label": dict(sorted(labels.items())),
    }
    return errors, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    errors, stats = validate_file(args.path)
    print(f"Records: {stats['records']} ({stats['records_without_pii']} without PII)")
    for label, count in stats["spans_per_label"].items():
        print(f"  {label}: {count}")

    if errors:
        print(f"\nFAILED with {len(errors)} problem(s):")
        for line_number, message in errors[:20]:
            print(f"  line {line_number}: {message}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        sys.exit(1)
    print("\nOK: no problems found.")


if __name__ == "__main__":
    main()
"""Validate a text-PII JSONL file against the dataset schema.

Usage:
    python -m piikit.validate data/raw/text.jsonl

Exits with status 1 if any problem is found, so CI can fail on bad data.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from piikit.schema import LABELS, REQUIRED_KEYS, REQUIRED_SPAN_KEYS


def validate_record(record: dict) -> list:
    """Return a list of human-readable problems for one record (empty if valid)."""
    errors = []

    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        return [f"missing keys: {missing}"]

    text, spans = record["text"], record["spans"]
    if not isinstance(text, str) or not text.strip():
        errors.append("text must be a non-empty string")
        return errors
    if not isinstance(spans, list):
        return ["spans must be a list"]

    previous_end = -1
    for i, span in enumerate(spans):
        where = f"span {i}"
        missing_span = [k for k in REQUIRED_SPAN_KEYS if k not in span]
        if missing_span:
            errors.append(f"{where}: missing keys {missing_span}")
            continue

        start, end, label = span["start"], span["end"], span["label"]
        if label not in LABELS:
            errors.append(f"{where}: unknown label {label!r}")
        if not (isinstance(start, int) and isinstance(end, int)):
            errors.append(f"{where}: start and end must be integers")
            continue
        if not (0 <= start < end <= len(text)):
            errors.append(f"{where}: offsets {start}-{end} outside text of length {len(text)}")
            continue
        if text[start:end] != span["text"]:
            errors.append(
                f"{where}: text[{start}:{end}] is {text[start:end]!r}, expected {span['text']!r}"
            )
        if start < previous_end:
            errors.append(f"{where}: overlaps or is out of order with the previous span")
        previous_end = max(previous_end, end)

    return errors


def validate_file(path: Path):
    """Return (errors, stats). Errors are (line_number, message) pairs."""
    errors, ids = [], Counter()
    labels, n_records, n_without_spans = Counter(), 0, 0

    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                errors.append((line_number, "blank line"))
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append((line_number, f"invalid JSON: {exc}"))
                continue

            n_records += 1
            for problem in validate_record(record):
                errors.append((line_number, problem))

            if isinstance(record, dict):
                ids[record.get("id")] += 1
                spans = record.get("spans") if isinstance(record.get("spans"), list) else []
                if not spans:
                    n_without_spans += 1
                labels.update(s.get("label") for s in spans if isinstance(s, dict))

    for record_id, count in ids.items():
        if count > 1:
            errors.append((0, f"duplicate id {record_id!r} appears {count} times"))

    stats = {
        "records": n_records,
        "records_without_pii": n_without_spans,
        "spans_per_label": dict(sorted(labels.items())),
    }
    return errors, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    errors, stats = validate_file(args.path)
    print(f"Records: {stats['records']} ({stats['records_without_pii']} without PII)")
    for label, count in stats["spans_per_label"].items():
        print(f"  {label}: {count}")

    if errors:
        print(f"\nFAILED with {len(errors)} problem(s):")
        for line_number, message in errors[:20]:
            print(f"  line {line_number}: {message}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        sys.exit(1)
    print("\nOK: no problems found.")


if __name__ == "__main__":
    main()