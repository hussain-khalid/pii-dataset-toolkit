"""Generate synthetic text records with character-offset PII labels.

Every value is fabricated. Emails use the reserved example.* domains, phone
numbers use the fictional 555-01xx range, and ID numbers follow a made-up
format, so nothing here is a real person's data.

Usage:
    python -m piikit.text_gen --n 1000 --seed 42 --out data/raw/text.jsonl
"""

import argparse
import json
import random
import re
from pathlib import Path

from piikit import __version__
from piikit.schema import LABELS

SOURCE = "synthetic/text_gen"

FIRST_NAMES = [
    "Anna", "Liam", "Sofia", "Noah", "Maya", "Omar", "Elena", "Jonas", "Priya", "Lucas",
    "Amira", "Daniel", "Mei", "Hugo", "Zara", "Tomas", "Nadia", "Felix", "Leila", "Marco",
    "Ingrid", "Samir", "Chloe", "Viktor", "Aisha", "Pavel", "Rosa", "Kenji", "Isla", "Mateo",
]
LAST_NAMES = [
    "Keller", "Moreau", "Haddad", "Novak", "Fischer", "Rossi", "Tanaka", "Ivanova", "Okafor",
    "Lindqvist", "Santos", "Petrov", "Dubois", "Kowalski", "Hansen", "Moretti", "Yilmaz",
    "Andersen", "Costa", "Bauer", "Silva", "Horvat", "Larsen", "Meyer", "Nguyen", "Weber",
]
STREETS = [
    "Maple Street", "Harbor Road", "Cedar Avenue", "Willow Lane", "Station Road",
    "Orchard Way", "Lakeview Drive", "Birch Court", "Mill Street", "Hillcrest Road",
]
CITIES = [
    "Brookfield", "Eastvale", "Northgate", "Riverton", "Stonebridge", "Fairhaven",
    "Oakmont", "Silverlake", "Westbury", "Clearwater",
]
EMAIL_DOMAINS = ["example.com", "example.org", "example.net"]
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]

TEMPLATES = {
    "t01": "Hello, my name is {PERSON} and I need help with my account.",
    "t02": "Please send the invoice to {EMAIL} and mark it for {PERSON}.",
    "t03": "You can reach {PERSON} on {PHONE} during office hours.",
    "t04": "Shipping address: {PERSON}, {ADDRESS}.",
    "t05": "Customer {PERSON} (ID {ID_NUMBER}) reported a billing problem.",
    "t06": "Date of birth: {DATE_OF_BIRTH}. Applicant: {PERSON}.",
    "t07": "Contact: {EMAIL} or call {PHONE}.",
    "t08": "{PERSON} moved to {ADDRESS} last month and asked to update the records.",
    "t09": "Verification failed for ID {ID_NUMBER}, please check the number again.",
    "t10": "Hi team, {PERSON} ({EMAIL}) will join the call on Monday.",
    "t11": "Patient record request: {PERSON}, born {DATE_OF_BIRTH}, phone {PHONE}.",
    "t12": "Reference {ID_NUMBER} was issued to {PERSON} at {ADDRESS}.",
    "t13": "Forwarded message from {EMAIL}: the delivery to {ADDRESS} is delayed.",
    "t14": "I was born on {DATE_OF_BIRTH} and my reference number is {ID_NUMBER}.",
    "t15": "Please call me back on {PHONE}. My name is {PERSON}.",
    "t16": "Registered user {PERSON} changed the login email to {EMAIL}.",
    "t17": "{PERSON} and {PERSON} share the same delivery address: {ADDRESS}.",
    "t18": "Support ticket opened by {EMAIL}; callback number {PHONE}.",
    # Records with no PII at all, so a detector can't just flag everything.
    "n01": "The quarterly report will be published next Tuesday.",
    "n02": "Our office is closed on public holidays.",
    "n03": "Please restart the application and try again.",
    "n04": "The meeting was moved to the large conference room.",
    "n05": "Thank you for contacting support, we will reply within two days.",
}

PLACEHOLDER = re.compile(r"\{([A-Z_]+)\}")


def make_person(rng):
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def make_email(rng):
    first = rng.choice(FIRST_NAMES).lower()
    last = rng.choice(LAST_NAMES).lower()
    sep = rng.choice([".", "_", ""])
    suffix = rng.choice(["", "", str(rng.randint(1, 99))])
    return f"{first}{sep}{last}{suffix}@{rng.choice(EMAIL_DOMAINS)}"


def make_phone(rng):
    line = f"01{rng.randint(0, 99):02d}"  # 0100-0199, the range reserved for fiction
    return rng.choice([f"555-{line}", f"+1-555-{line}", f"(555) {line}", f"+1 555 {line}"])


def make_address(rng):
    return f"{rng.randint(1, 999)} {rng.choice(STREETS)}, {rng.choice(CITIES)}"


def make_id_number(rng):
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    return f"{letters}-{rng.randint(100000, 999999)}"


def make_dob(rng):
    year, month, day = rng.randint(1950, 2005), rng.randint(1, 12), rng.randint(1, 28)
    style = rng.choice(["iso", "slash", "long"])
    if style == "iso":
        return f"{year}-{month:02d}-{day:02d}"
    if style == "slash":
        return f"{day:02d}/{month:02d}/{year}"
    return f"{MONTHS[month - 1]} {day}, {year}"


GENERATORS = {
    "PERSON": make_person,
    "EMAIL": make_email,
    "PHONE": make_phone,
    "ADDRESS": make_address,
    "ID_NUMBER": make_id_number,
    "DATE_OF_BIRTH": make_dob,
}

assert set(GENERATORS) == set(LABELS), "every label needs a generator"


def render(template: str, rng):
    """Fill a template and return (text, spans) with exact character offsets."""
    out, spans, pos = [], [], 0
    cursor = 0
    for match in PLACEHOLDER.finditer(template):
        literal = template[cursor:match.start()]
        out.append(literal)
        pos += len(literal)

        label = match.group(1)
        value = GENERATORS[label](rng)
        spans.append({"start": pos, "end": pos + len(value), "label": label, "text": value})
        out.append(value)
        pos += len(value)
        cursor = match.end()

    tail = template[cursor:]
    out.append(tail)
    return "".join(out), spans


def generate_record(index: int, seed: int) -> dict:
    # Each record has its own RNG, so record i is the same whatever n is.
    rng = random.Random(f"{seed}-{index}")
    template_id = rng.choice(sorted(TEMPLATES))
    text, spans = render(TEMPLATES[template_id], rng)
    return {
        "id": f"txt-{index:06d}",
        "text": text,
        "spans": spans,
        "source": SOURCE,
        "generator_version": __version__,
        "seed": seed,
        "template_id": template_id,
    }


def generate(n: int, seed: int):
    return [generate_record(i, seed) for i in range(n)]


def write_jsonl(records, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/raw/text.jsonl"))
    args = parser.parse_args()

    records = generate(args.n, args.seed)
    write_jsonl(records, args.out)
    with_pii = sum(1 for r in records if r["spans"])
    print(f"Wrote {len(records)} records ({with_pii} with PII) to {args.out}")


if __name__ == "__main__":
    main()