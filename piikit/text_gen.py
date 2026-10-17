"""Generate synthetic text records with character-offset PII labels.

Every value is fabricated. Emails use the reserved example.* domains, phone
numbers use the fictional 555-01xx range, and ID numbers follow a made-up
format, so nothing here is a real person's data.

Usage:
    python -m piikit.text_gen --n 1000 --seed 42 --out data/raw/text.jsonl
    python -m piikit.text_gen --n 200  --seed 42 --locale de --out data/raw/text_de.jsonl

Supported locales: en (default), de (German), fr (French), es (Spanish).
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

# ---------------------------------------------------------------------------
# Multilingual locale data
# ---------------------------------------------------------------------------
SUPPORTED_LOCALES = ("en", "de", "fr", "es")

LOCALE_DATA: dict[str, dict] = {
    "en": {},  # uses module-level defaults defined below
    "de": {
        "first_names": [
            "Anna", "Lena", "Max", "Felix", "Sophie", "Jonas", "Emma", "Paul",
            "Laura", "Lukas", "Marie", "Tim", "Lisa", "Moritz", "Lea", "Tobias",
            "Hannah", "Jan", "Klara", "Stefan",
        ],
        "last_names": [
            "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
            "Becker", "Schulz", "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter",
            "Klein", "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann",
        ],
        "streets": [
            "Hauptstraße", "Bahnhofstraße", "Gartenweg", "Kirchgasse", "Lindenallee",
            "Rosenweg", "Schulstraße", "Bergstraße", "Birkenweg", "Schillerstraße",
        ],
        "cities": [
            "Musterstadt", "Neustadt", "Kleinfeld", "Großbach", "Waldkirchen",
            "Bergheim", "Sonnental", "Lindenbach", "Fichtenau", "Buchenried",
        ],
        "email_domains": ["example.de", "example.com", "example.net"],
        "tts_voice": "de-DE-KatjaNeural",
    },
    "fr": {
        "first_names": [
            "Léa", "Hugo", "Emma", "Louis", "Chloé", "Gabriel", "Inès", "Arthur",
            "Manon", "Raphaël", "Jade", "Antoine", "Zoé", "Mathis", "Camille", "Théo",
            "Alice", "Nathan", "Lucie", "Ethan",
        ],
        "last_names": [
            "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit",
            "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
            "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
        ],
        "streets": [
            "Rue de la Paix", "Avenue des Fleurs", "Rue du Moulin", "Allée des Chênes",
            "Boulevard Saint-Michel", "Rue des Lilas", "Chemin du Lac", "Impasse Verte",
            "Rue de la Forêt", "Avenue de la Gare",
        ],
        "cities": [
            "Bellerive", "Montclair", "Valdor", "Hauteville", "Rivière",
            "Clairmont", "Fontaine", "Boissy", "Grandchamp", "Lacroix",
        ],
        "email_domains": ["example.fr", "example.com", "example.net"],
        "tts_voice": "fr-FR-DeniseNeural",
    },
    "es": {
        "first_names": [
            "María", "José", "Carmen", "Antonio", "Ana", "Manuel", "Laura", "David",
            "Isabel", "Carlos", "Lucía", "Miguel", "Sara", "Francisco", "Elena",
            "Pablo", "Rosa", "Jorge", "Marta", "Alejandro",
        ],
        "last_names": [
            "García", "Martínez", "López", "Sánchez", "González", "Pérez", "Rodríguez",
            "Fernández", "Ramírez", "Torres", "Flores", "Rivera", "Moreno", "Ruiz",
            "Jiménez", "Díaz", "Vega", "Cruz", "Herrera", "Medina",
        ],
        "streets": [
            "Calle Mayor", "Avenida de la Paz", "Calle del Sol", "Paseo del Prado",
            "Calle de la Luna", "Avenida Central", "Calle Nueva", "Camino Real",
            "Calle de las Flores", "Avenida del Mar",
        ],
        "cities": [
            "Villanueva", "Montealto", "Puertoluz", "Valverde", "Rioseco",
            "Llanura", "Peñalba", "Fuenlabrada", "Altozano", "Camporreal",
        ],
        "email_domains": ["example.es", "example.com", "example.net"],
        "tts_voice": "es-ES-ElviraNeural",
    },
}


def _locale_val(locale: str, key: str, default):
    """Return locale-specific value or fall back to the module-level default."""
    return LOCALE_DATA.get(locale, {}).get(key, default)

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


def make_person(rng, locale="en", hard: bool = False):
    first_names = _locale_val(locale, "first_names", FIRST_NAMES)
    last_names = _locale_val(locale, "last_names", LAST_NAMES)
    first, last = rng.choice(first_names), rng.choice(last_names)
    is_hard = hard or (rng.random() < HARD_RATE)
    if is_hard:
        return rng.choice([f"{last}, {first}", f"{first} {last}".lower(), f"{first} {last}".upper()])
    return f"{first} {last}"


def make_email(rng, locale="en", hard: bool = False):
    first_names = _locale_val(locale, "first_names", FIRST_NAMES)
    last_names = _locale_val(locale, "last_names", LAST_NAMES)
    domains = _locale_val(locale, "email_domains", EMAIL_DOMAINS)
    # Normalise accented chars for email local part
    import unicodedata
    def _ascii(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    first = _ascii(rng.choice(first_names))
    last = _ascii(rng.choice(last_names))
    sep = rng.choice([".", "_", ""])
    suffix = rng.choice(["", "", str(rng.randint(1, 99))])
    local, domain = f"{first}{sep}{last}{suffix}", rng.choice(domains)
    is_hard = hard or (rng.random() < HARD_RATE)
    if is_hard:
        return f"{local} [at] {domain}"
    return f"{local}@{domain}"


def make_phone(rng, locale="en", hard: bool = False):
    """Phone numbers always use the 555-01xx fictional range regardless of locale."""
    line = f"01{rng.randint(0, 99):02d}"  # 0100-0199, the range reserved for fiction
    is_hard = hard or (rng.random() < HARD_RATE)
    if is_hard:
        return rng.choice([f"555.{line}", f"555{line}", f"+1.555.{line}"])
    return rng.choice([f"555-{line}", f"+1-555-{line}", f"(555) {line}", f"+1 555 {line}"])


def make_address(rng, locale="en", hard: bool = False):
    streets = _locale_val(locale, "streets", STREETS)
    cities = _locale_val(locale, "cities", CITIES)
    number, street, city = rng.randint(1, 999), rng.choice(streets), rng.choice(cities)
    is_hard = hard or (rng.random() < HARD_RATE)
    if locale == "en" and is_hard:
        parts = street.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in STREET_ABBREVIATIONS:
            return f"{number} {parts[0]} {STREET_ABBREVIATIONS[parts[1]]}, {city}"
        return f"{number} {street} {city}"
    return f"{number} {street}, {city}"


def make_id_number(rng, locale="en", hard: bool = False):
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    digits = rng.randint(100000, 999999)
    is_hard = hard or (rng.random() < HARD_RATE)
    if is_hard:
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


def make_dob(rng, locale="en", hard: bool = False):
    year, month, day = rng.randint(1950, 2005), rng.randint(1, 12), rng.randint(1, 28)
    is_hard = hard or (rng.random() < HARD_RATE)
    return _date_text(rng, year, month, day, is_hard)


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


def render(template: str, rng, locale: str = "en", hard: bool = False):
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
            value = GENERATORS[label](rng, locale=locale, hard=hard)
            spans.append({"start": pos, "end": pos + len(value), "label": label, "text": value})
        out.append(value)
        pos += len(value)
        cursor = match.end()

    tail = template[cursor:]
    out.append(tail)
    return "".join(out), spans


def generate_record(index: int, seed: int, locale: str = "en", hard: bool = False) -> dict:
    # Each record has its own RNG, so record i is the same whatever n is.
    rng = random.Random(f"{seed}-{index}")
    negative = rng.random() < NEGATIVE_RATE
    pool = sorted(t for t in TEMPLATES if t.startswith("n") == negative)
    template_id = rng.choice(pool)
    text, spans = render(TEMPLATES[template_id], rng, locale=locale, hard=hard)
    record = {
        "id": f"txt-{index:06d}",
        "text": text,
        "spans": spans,
        "source": SOURCE,
        "generator_version": __version__,
        "seed": seed,
        "template_id": template_id,
    }
    if locale != "en":
        record["locale"] = locale
    if hard:
        record["hard"] = True
    return record


def generate(n: int, seed: int, locale: str = "en", hard: bool = False):
    return [generate_record(i, seed, locale=locale, hard=hard) for i in range(n)]


def write_jsonl(records, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/raw/text.jsonl"))
    parser.add_argument("--locale", choices=SUPPORTED_LOCALES, default="en",
                        help="Language locale for synthetic names/addresses (default: en).")
    parser.add_argument("--hard", action="store_true",
                        help="Generate adversarial/hard format examples with non-standard PII shapes.")
    args = parser.parse_args()

    records = generate(args.n, args.seed, locale=args.locale, hard=args.hard)
    write_jsonl(records, args.out)
    with_pii = sum(1 for r in records if r["spans"])
    locale_tag = f" [{args.locale}]" if args.locale != "en" else ""
    hard_tag = " [hard]" if args.hard else ""
    print(f"Wrote {len(records)} records ({with_pii} with PII) to {args.out}{locale_tag}{hard_tag}")


if __name__ == "__main__":
    main()