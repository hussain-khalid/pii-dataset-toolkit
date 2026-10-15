"""Validate a document-image PII dataset (annotations plus image files).

Usage:
    python -m piikit.validate_docs data/raw/docs/docs.jsonl

Checks, per document: required keys, image exists and matches the stated size,
every box is inside the image with positive area, labels are allowed, boxes do
not overlap each other, and every box actually contains ink (not blank paper).
Exits with status 1 if any problem is found.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

from piikit.schema import (
    DOC_REQUIRED_FIELD_KEYS, DOC_REQUIRED_KEYS, DOC_TYPES, LABELS,
)

MAX_OVERLAP_IOU = 0.05


def iou(a, b) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def validate_record(record: dict, base_dir: Path) -> list:
    missing = [k for k in DOC_REQUIRED_KEYS if k not in record]
    if missing:
        return [f"missing keys: {missing}"]

    errors = []
    if record["doc_type"] not in DOC_TYPES:
        errors.append(f"unknown doc_type {record['doc_type']!r}")

    image_path = base_dir / record["image"]
    image = None
    if not image_path.exists():
        errors.append(f"image not found: {record['image']}")
    else:
        image = Image.open(image_path).convert("RGB")
        if image.size != (record["width"], record["height"]):
            errors.append(
                f"image size {image.size} differs from stated "
                f"{(record['width'], record['height'])}"
            )

    boxes = []
    for i, field in enumerate(record["fields"]):
        where = f"field {i}"
        missing_f = [k for k in DOC_REQUIRED_FIELD_KEYS if k not in field]
        if missing_f:
            errors.append(f"{where}: missing keys {missing_f}")
            continue
        if field["label"] not in LABELS:
            errors.append(f"{where}: unknown label {field['label']!r}")
        if not field["text"]:
            errors.append(f"{where}: empty text")

        bbox = field["bbox"]
        if not (isinstance(bbox, list) and len(bbox) == 4
                and all(isinstance(v, int) for v in bbox)):
            errors.append(f"{where}: bbox must be four integers [x0, y0, x1, y1]")
            continue
        x0, y0, x1, y1 = bbox
        if not (0 <= x0 < x1 <= record["width"] and 0 <= y0 < y1 <= record["height"]):
            errors.append(f"{where}: bbox {bbox} is empty or outside the image")
            continue

        if image is not None:
            lo, hi = image.crop((x0, y0, x1, y1)).convert("L").getextrema()
            if hi - lo < 40:
                errors.append(f"{where}: bbox {bbox} contains no visible text")
        boxes.append((i, bbox))

    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            if iou(boxes[a][1], boxes[b][1]) > MAX_OVERLAP_IOU:
                errors.append(f"fields {boxes[a][0]} and {boxes[b][0]} overlap")
    return errors


def validate_file(path: Path):
    base_dir = path.parent
    errors, ids = [], Counter()
    labels, types, n_records = Counter(), Counter(), 0

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
            for problem in validate_record(record, base_dir):
                errors.append((line_number, problem))
            if isinstance(record, dict):
                ids[record.get("id")] += 1
                types[record.get("doc_type")] += 1
                fields = record.get("fields") if isinstance(record.get("fields"), list) else []
                labels.update(x.get("label") for x in fields if isinstance(x, dict))

    for record_id, count in ids.items():
        if count > 1:
            errors.append((0, f"duplicate id {record_id!r} appears {count} times"))

    stats = {"records": n_records, "by_type": dict(sorted(types.items())),
             "fields_per_label": dict(sorted(labels.items()))}
    return errors, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    errors, stats = validate_file(args.path)
    print(f"Documents: {stats['records']}")
    for name, count in stats["by_type"].items():
        print(f"  {name}: {count}")
    print("Labelled fields:")
    for label, count in stats["fields_per_label"].items():
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