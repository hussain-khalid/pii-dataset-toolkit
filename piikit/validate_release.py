"""Validate a built release directory.

Usage:
    python -m piikit.validate_release data/release/v0.1.0

Checks: every file in MANIFEST.json exists with the recorded checksum and record
count; every split file passes the text or document validator; every record has
provenance and a modality; and no record leaks across splits (same id, same
normalised text, or same image content). Exits with status 1 on any problem.
"""

import argparse
import json
import sys
from pathlib import Path

from piikit import validate, validate_docs
from piikit.dedup import file_sha256, normalize_text
from piikit.splits import SPLITS

PROVENANCE_KEYS = ("generator", "input_file", "input_line", "input_sha256", "synthetic", "license")


def find_leaks(split_records: dict, key_fn, what: str):
    """split_records maps split name -> records. Report keys present in more than one split."""
    owner, leaks = {}, []
    for name in SPLITS:
        for record in split_records.get(name, []):
            key = key_fn(record)
            if key in owner and owner[key] != name:
                leaks.append(f"{what} appears in both {owner[key]} and {name}: {key!r}"[:200])
            owner.setdefault(key, name)
    return leaks


def image_key(root: Path, record: dict) -> str:
    """Content hash of a document image; a missing file gets a unique placeholder
    (it is reported elsewhere) instead of crashing the leak check."""
    path = root / "docs" / record["image"]
    return file_sha256(path) if path.exists() else f"missing:{record['image']}"


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def validate_release(root: Path):
    """Return a list of problems (empty if the release is sound)."""
    root = Path(root)
    errors = []

    manifest_path = root / "MANIFEST.json"
    if not manifest_path.exists():
        return ["MANIFEST.json is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists():
            errors.append(f"{entry['path']}: listed in manifest but missing")
            continue
        if file_sha256(path) != entry["sha256"]:
            errors.append(f"{entry['path']}: checksum does not match the manifest")
        if "records" in entry:
            actual = sum(1 for line in path.open(encoding="utf-8") if line.strip())
            if actual != entry["records"]:
                errors.append(f"{entry['path']}: {actual} records, manifest says {entry['records']}")

    text_splits, doc_splits = {}, {}
    for name in SPLITS:
        text_path, docs_path = root / "text" / f"{name}.jsonl", root / "docs" / f"{name}.jsonl"
        for path, validator in ((text_path, validate.validate_file),
                                (docs_path, validate_docs.validate_file)):
            if not path.exists():
                errors.append(f"{path.relative_to(root)}: missing")
                continue
            problems, stats = validator(path)
            errors.extend(f"{path.relative_to(root)} line {n}: {m}" for n, m in problems)
            if stats["records"] == 0:
                errors.append(f"{path.relative_to(root)}: split is empty")

        if text_path.exists():
            text_splits[name] = read_jsonl(text_path)
        if docs_path.exists():
            doc_splits[name] = read_jsonl(docs_path)

    for modality, splits in (("text", text_splits), ("document", doc_splits)):
        for name, records in splits.items():
            for record in records:
                prov = record.get("provenance")
                if not isinstance(prov, dict) or any(k not in prov for k in PROVENANCE_KEYS):
                    errors.append(f"{record.get('id')}: incomplete provenance")
                if record.get("modality") != modality:
                    errors.append(f"{record.get('id')}: modality should be {modality!r}")

    errors += find_leaks(text_splits, lambda r: r["id"], "text id")
    errors += find_leaks(text_splits, lambda r: normalize_text(r["text"]), "text")
    errors += find_leaks(doc_splits, lambda r: r["id"], "document id")
    errors += find_leaks(doc_splits, lambda r: image_key(root, r), "document image")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    errors = validate_release(args.path)
    if errors:
        print(f"FAILED with {len(errors)} problem(s):")
        for message in errors[:20]:
            print(f"  {message}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        sys.exit(1)
    print("OK: manifest, checksums, schemas, provenance and split isolation all pass.")


if __name__ == "__main__":
    main()