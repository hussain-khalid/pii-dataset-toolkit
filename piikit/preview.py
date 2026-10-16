"""Draw the labelled bounding boxes onto documents, for visual spot-checks.

Usage:
    python -m piikit.preview data/raw/docs/docs.jsonl --n 6 --out-dir docs/images/previews
    python -m piikit.preview data/raw/docs/docs.jsonl --per-type --out-dir docs/images/previews

--per-type writes one example per document type under stable names
(example_invoice.png, example_form.png, example_id_card.png), which is what the
README links to.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLORS = {
    "PERSON": (220, 40, 40), "EMAIL": (40, 90, 220), "PHONE": (30, 150, 60),
    "ADDRESS": (220, 130, 20), "ID_NUMBER": (150, 50, 190), "DATE_OF_BIRTH": (0, 150, 160),
}


def render_preview(record: dict, base_dir: Path) -> Image.Image:
    image = Image.open(base_dir / record["image"]).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=13)
    for field in record["fields"]:
        color = COLORS.get(field["label"], (0, 0, 0))
        x0, y0, x1, y1 = field["bbox"]
        draw.rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 2), outline=color, width=2)
        tag = field["label"]
        tw = draw.textlength(tag, font=font)
        # Put the tag just right of the box (clamped to the page) so it never covers text.
        tx = min(x1 + 6, image.width - tw - 8)
        draw.rectangle((tx - 3, y0, tx + tw + 3, y0 + 16), fill=color)
        draw.text((tx, y0 + 1), tag, font=font, fill=(255, 255, 255))
    return image


def write_previews(records, base_dir: Path, out_dir: Path, n: int = 6, per_type: bool = False):
    """Write preview images and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if per_type:
        first = {}
        for record in records:
            first.setdefault(record["doc_type"], record)
        chosen = [(f"example_{t}.png", r) for t, r in sorted(first.items())]
    else:
        chosen = [(f"{r['id']}_{r['doc_type']}_boxes.png", r) for r in records[:n]]

    paths = []
    for name, record in chosen:
        path = out_dir / name
        render_preview(record, base_dir).save(path)
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--n", type=int, default=6)
    parser.add_argument("--per-type", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("docs/images/previews"))
    args = parser.parse_args()

    with args.path.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    paths = write_previews(records, args.path.parent, args.out_dir, args.n, args.per_type)
    print(f"Wrote {len(paths)} preview images to {args.out_dir}")


if __name__ == "__main__":
    main()