"""Generate synthetic document images with field-level PII bounding boxes.

Documents (invoice, form, ID-style card) are drawn with Pillow. The bounding box
of every PII field comes from the drawing call itself, so boxes are exact.
All values are fabricated (see piikit.text_gen).

Usage:
    python -m piikit.doc_gen --n 200 --seed 42 --out-dir data/raw/docs

Writes <out-dir>/images/doc-XXXXXX.png and <out-dir>/docs.jsonl.
"""

import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from piikit import __version__
from piikit.text_gen import (
    GENERATORS, CITIES, make_address, make_dob, make_email,
    make_id_number, make_person, make_phone,
)

SOURCE = "synthetic/doc_gen"

PAPER_COLORS = [(255, 255, 255), (250, 248, 240), (245, 247, 250)]
INK_COLORS = [(20, 20, 20), (35, 35, 60), (30, 45, 30)]
ITEMS = ["Consulting hours", "Hosting plan", "Support package", "Licence renewal",
         "Training session", "Hardware kit", "Setup fee", "Maintenance"]


class Page:
    """A drawing surface that records a bounding box for each labelled text."""

    def __init__(self, width, height, rng):
        self.width, self.height, self.rng = width, height, rng
        self.paper = rng.choice(PAPER_COLORS)
        self.ink = rng.choice(INK_COLORS)
        self.image = Image.new("RGB", (width, height), self.paper)
        self.draw = ImageDraw.Draw(self.image)
        self.fields = []

    def font(self, size):
        return ImageFont.load_default(size=size)

    def text(self, xy, text, size, label=None, fill=None):
        font = self.font(size)
        self.draw.text(xy, text, font=font, fill=fill or self.ink)
        if label:
            x0, y0, x1, y1 = self.draw.textbbox(xy, text, font=font)
            self.fields.append({"label": label, "text": text, "bbox": [x0, y0, x1, y1]})
        return self.draw.textbbox(xy, text, font=font)

    def line(self, xy, width=1, fill=(150, 150, 150)):
        self.draw.line(xy, fill=fill, width=width)

    def rect(self, xy, outline=(120, 120, 120), width=2, fill=None):
        self.draw.rectangle(xy, outline=outline, width=width, fill=fill)


def draw_invoice(page: Page):
    rng = page.rng
    m = rng.randint(40, 70)
    base = rng.choice([18, 20, 22])
    page.text((m, m), f"{rng.choice(CITIES)} Supplies Ltd", base + 8)
    page.text((page.width - m - 190, m), "INVOICE", base + 10)
    page.text((page.width - m - 190, m + 45), f"No. INV-{rng.randint(1000, 9999)}", base - 2)
    page.text((page.width - m - 190, m + 70), f"Date: 2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", base - 2)

    y = m + 130
    page.text((m, y), "Bill to:", base)
    y += 34
    page.text((m, y), make_person(rng), base, label="PERSON")
    y += 30
    page.text((m, y), make_address(rng), base, label="ADDRESS")
    y += 30
    page.text((m, y), make_email(rng), base, label="EMAIL")
    if rng.random() < 0.6:
        y += 30
        page.text((m, y), make_phone(rng), base, label="PHONE")

    y += 70
    page.line((m, y, page.width - m, y), width=2)
    page.text((m, y + 8), "Description", base - 2)
    page.text((page.width - m - 260, y + 8), "Qty", base - 2)
    page.text((page.width - m - 120, y + 8), "Price", base - 2)
    page.line((m, y + 40, page.width - m, y + 40))
    y += 52
    total = 0
    for item in rng.sample(ITEMS, rng.randint(3, 5)):
        qty, price = rng.randint(1, 5), rng.randint(20, 400)
        total += qty * price
        page.text((m, y), item, base - 2)
        page.text((page.width - m - 250, y), str(qty), base - 2)
        page.text((page.width - m - 120, y), f"{price}.00", base - 2)
        y += 34
    page.line((m, y + 6, page.width - m, y + 6), width=2)
    page.text((page.width - m - 260, y + 18), f"Total: {total}.00", base)
    page.text((m, page.height - m - 20), "Payment due within 30 days.", base - 4)


def draw_form(page: Page):
    rng = page.rng
    m = rng.randint(40, 70)
    base = rng.choice([18, 20, 22])
    page.text((m, m), "Application Form", base + 10)
    page.line((m, m + 50, page.width - m, m + 50), width=2)

    rows = [
        ("Full name:", make_person, "PERSON"),
        ("Date of birth:", make_dob, "DATE_OF_BIRTH"),
        ("Phone:", make_phone, "PHONE"),
        ("Email:", make_email, "EMAIL"),
        ("Address:", make_address, "ADDRESS"),
        ("ID number:", make_id_number, "ID_NUMBER"),
    ]
    chosen = sorted(rng.sample(range(len(rows)), rng.randint(4, 6)))
    y, col = m + 85, 230
    for i in chosen:
        name, maker, label = rows[i]
        page.text((m, y), name, base, fill=(80, 80, 80))
        page.text((m + col, y), maker(rng), base, label=label)
        page.line((m + col - 6, y + base + 12, page.width - m, y + base + 12))
        y += 62
    page.text((m, y + 20), "Signature: ____________________", base - 2, fill=(110, 110, 110))
    page.text((m, page.height - m - 20), "Office use only.", base - 4, fill=(130, 130, 130))


def draw_id_card(page: Page):
    rng = page.rng
    base = rng.choice([18, 20])
    page.rect((20, 20, page.width - 20, page.height - 20), width=3)
    page.draw.rectangle((20, 20, page.width - 20, 80), fill=(60, 80, 120))
    page.text((40, 36), rng.choice(["IDENTITY CARD", "MEMBER CARD", "STAFF CARD"]), base + 4,
              fill=(255, 255, 255))
    page.rect((40, 110, 170, 270), width=2)
    page.text((74, 180), "PHOTO", base - 4, fill=(150, 150, 150))

    x, y = 200, 110
    for name, maker, label in [
        ("NAME", make_person, "PERSON"),
        ("DOB", make_dob, "DATE_OF_BIRTH"),
        ("ID NO", make_id_number, "ID_NUMBER"),
        ("ADDRESS", make_address, "ADDRESS"),
    ]:
        page.text((x, y), name, base - 6, fill=(120, 120, 120))
        page.text((x, y + 18), maker(rng), base, label=label)
        y += 62


LAYOUTS = {
    "invoice": (draw_invoice, (800, 1000)),
    "form": (draw_form, (800, 700)),
    "id_card": (draw_id_card, (640, 400)),
}


def generate_doc(index: int, seed: int, out_dir: Path) -> dict:
    # Per-record RNG: document i is the same whatever n is.
    rng = random.Random(f"{seed}-doc-{index}")
    doc_type = rng.choice(sorted(LAYOUTS))
    draw_fn, (width, height) = LAYOUTS[doc_type]

    page = Page(width, height, rng)
    draw_fn(page)

    doc_id = f"doc-{index:06d}"
    image_dir = Path(out_dir) / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    page.image.save(image_dir / f"{doc_id}.png")

    return {
        "id": doc_id,
        "image": f"images/{doc_id}.png",
        "width": width,
        "height": height,
        "doc_type": doc_type,
        "fields": page.fields,
        "source": SOURCE,
        "generator_version": __version__,
        "seed": seed,
    }


def generate_docs(n: int, seed: int, out_dir: Path):
    return [generate_doc(i, seed, out_dir) for i in range(n)]


def write_annotations(records, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw/docs"))
    args = parser.parse_args()

    records = generate_docs(args.n, args.seed, args.out_dir)
    write_annotations(records, args.out_dir / "docs.jsonl")
    n_fields = sum(len(r["fields"]) for r in records)
    print(f"Wrote {len(records)} documents ({n_fields} labelled fields) to {args.out_dir}")


if __name__ == "__main__":
    main()