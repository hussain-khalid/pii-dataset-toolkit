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
NEGATIVE_RATE = 0.20  # share of records that contain no PII
HARD_RATE = 0.25      # share of values written in a less common format (typos aside)

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
    # Most use non-PII fillers (order numbers, versions, amounts...) that look
    # a little like identifiers but are not personal data.
    "n01": "The quarterly report will be published next {WEEKDAY}.",
    "n02": "Our office is closed on public holidays.",
    "n03": "Please restart the application and try again.",
    "n04": "The meeting was moved to {TIME} in the large conference room.",
    "n05": "Thank you for contacting support, we will reply within two days.",
    "n06": "Order #{ORDER_NO} shipped on {WEEKDAY} and should arrive soon.",
    "n07": "The {PRODUCT} is back in stock for {AMOUNT}.",
    "n08": "Release {VERSION} fixes a crash when opening large files.",
    "n09": "Your refund of {AMOUNT} for order #{ORDER_NO} has been processed.",
    "n10": "Maintenance is planned for {WEEKDAY} at {TIME}, expect short downtime.",
    "n11": "The {PRODUCT} requires version {VERSION} or newer to run.",
    "n12": "We received order #{ORDER_NO} and will ship the {PRODUCT} on {WEEKDAY}.",
    "n13": "Opening hours are 09:00 to 17:00, Monday to {WEEKDAY}.",
    "n14": "Please allow up to {ORDER_NO} seconds for the page to refresh.",
    "n15": "The report is due on {DATE}.",
    "n16": "Your subscription renews on {DATE}, no action is needed.",
    "n17": "Please send the parcel to {ORG} reception.",
    "n18": "{ORG} will confirm the delivery date on {WEEKDAY}.",
    "n19": "Invoice dated {DATE} has been paid in full.",
}

PLACEHOLDER = re.compile(r"\{([A-Z_]+)\}")


STREET_ABBREVIATIONS = {"Street": "St", "Road": "Rd", "Avenue": "Ave", "Lane": "Ln",
                        "Drive": "Dr", "Court": "Ct"}
SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def make_person(rng):
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    if rng.random() < HARD_RATE:
        return rng.choice([f"{last}, {first}", f"{first} {last}".lower(), f"{first} {last}".upper()])
    return f"{first} {last}"


def make_email(rng):
    first = rng.choice(FIRST_NAMES).lower()
    last = rng.choice(LAST_NAMES).lower()
    sep = rng.choice([".", "_", ""])
    suffix = rng.choice(["", "", str(rng.randint(1, 99))])
    local, domain = f"{first}{sep}{last}{suffix}", rng.choice(EMAIL_DOMAINS)
    if rng.random() < HARD_RATE:
        return f"{local} [at] {domain}"
    return f"{local}@{domain}"


def make_phone(rng):
    line = f"01{rng.randint(0, 99):02d}"  # 0100-0199, the range reserved for fiction
    if rng.random() < HARD_RATE:
        return rng.choice([f"555.{line}", f"555{line}", f"+1.555.{line}"])
    return rng.choice([f"555-{line}", f"+1-555-{line}", f"(555) {line}", f"+1 555 {line}"])


def make_address(rng):
    number, street, city = rng.randint(1, 999), rng.choice(STREETS), rng.choice(CITIES)
    if rng.random() < HARD_RATE:
        name, kind = street.rsplit(" ", 1)
        if kind in STREET_ABBREVIATIONS:
            return f"{number} {name} {STREET_ABBREVIATIONS[kind]}, {city}"
        return f"{number} {street} {city}"
    return f"{number} {street}, {city}"


def make_id_number(rng):
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    digits = rng.randint(100000, 999999)
    if rng.random() < HARD_RATE:
        return rng.choice([f"{letters} {digits}", f"{letters}{digits}"])
    return f"{letters}-{digits}"


def _date_text(rng, year, month, day, hard):
    if hard:
        return rng.choice([f"{day:02d}.{month:02d}.{year}",
                           f"{day} {SHORT_MONTHS[month - 1]} {year}",
                           f"{SHORT_MONTHS[month - 1]} {day} {year}"])
    style = rng.choice(["iso", "slash", "long"])
    if style == "iso":
        return f"{year}-{month:02d}-{day:02d}"
    if style == "slash":
        return f"{day:02d}/{month:02d}/{year}"
    return f"{MONTHS[month - 1]} {day}, {year}"


def make_dob(rng):
    year, month, day = rng.randint(1950, 2005), rng.randint(1, 12), rng.randint(1, 28)
    return _date_text(rng, year, month, day, rng.random() < HARD_RATE)


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PRODUCTS = ["standing desk", "travel mug", "wireless keyboard", "desk lamp", "backpack",
            "monitor stand", "notebook set", "water bottle"]


def make_weekday(rng):
    return rng.choice(WEEKDAYS)


def make_time(rng):
    return f"{rng.randint(8, 18):02d}:{rng.choice(['00', '15', '30', '45'])}"


def make_order_no(rng):
    return str(rng.randint(1000, 99999))


def make_amount(rng):
    return f"${rng.randint(5, 900)}.{rng.choice(['00', '50', '99'])}"


def make_product(rng):
    return rng.choice(PRODUCTS)


ORGS = ["Northgate Supplies", "Brookfield Logistics", "Eastvale Hardware", "Riverton Foods",
        "Stonebridge Office Goods", "Fairhaven Printing"]


def make_org(rng):
    return rng.choice(ORGS)


def make_date(rng):
    """An ordinary date (due dates, renewals). Same shapes as birth dates; only context differs."""
    return _date_text(rng, rng.randint(2026, 2028), rng.randint(1, 12), rng.randint(1, 28),
                      rng.random() < 0.3)


def make_version(rng):
    return f"{rng.randint(1, 9)}.{rng.randint(0, 20)}.{rng.randint(0, 9)}"


# Placeholders that are NOT personal data: filled in, but never labelled.
FILLERS = {
    "WEEKDAY": make_weekday,
    "TIME": make_time,
    "ORDER_NO": make_order_no,
    "AMOUNT": make_amount,
    "PRODUCT": make_product,
    "VERSION": make_version,
    "DATE": make_date,
    "ORG": make_org,
}

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
        if label in FILLERS:
            value = FILLERS[label](rng)
        else:
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
    negative = rng.random() < NEGATIVE_RATE
    pool = sorted(t for t in TEMPLATES if t.startswith("n") == negative)
    template_id = rng.choice(pool)
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