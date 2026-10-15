"""Draw the labelled bounding boxes onto documents, for visual spot-checks.

Usage:
    python -m piikit.preview data/raw/docs/docs.jsonl --n 6 --out-dir docs/images/previews
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--n", type=int, default=6)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/images/previews"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with args.path.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()][: args.n]
    for record in records:
        out = args.out_dir / f"{record['id']}_{record['doc_type']}_boxes.png"
        render_preview(record, args.path.parent).save(out)
    print(f"Wrote {len(records)} preview images to {args.out_dir}")


if __name__ == "__main__":
    main()