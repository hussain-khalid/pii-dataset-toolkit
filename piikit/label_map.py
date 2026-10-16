"""Map this dataset's labels onto other common label sets.

A value of None means "no equivalent label". The scorer drops those labels from
BOTH the gold annotations and the predictions, so a system is never penalised
for a label the target set cannot express.

These mappings are my own judgement and several are lossy (noted below). Check
them against the current version of the target label set before relying on them.
"""

LABEL_SETS = {
    # This dataset's own labels, unchanged.
    "none": None,
    # Microsoft Presidio-style entity names.
    "presidio": {
        "PERSON": "PERSON",
        "EMAIL": "EMAIL_ADDRESS",
        "PHONE": "PHONE_NUMBER",
        "ADDRESS": "LOCATION",          # lossy: LOCATION also covers cities, countries...
        "DATE_OF_BIRTH": "DATE_TIME",   # lossy: DATE_TIME covers any date or time
        "ID_NUMBER": None,              # no generic ID entity; nearest ones are national IDs
    },
    # CoNLL-2003 style NER tags.
    "conll": {
        "PERSON": "PER",
        "ADDRESS": "LOC",               # lossy: a full address is more than a location name
        "EMAIL": None,
        "PHONE": None,
        "DATE_OF_BIRTH": None,
        "ID_NUMBER": None,
    },
}


def map_label(label: str, label_set: str):
    """Return the label in the target set, or None if it has no equivalent."""
    if label_set not in LABEL_SETS:
        raise ValueError(f"unknown label set {label_set!r}; choose from {sorted(LABEL_SETS)}")
    mapping = LABEL_SETS[label_set]
    return label if mapping is None else mapping.get(label)


def map_items(items, label_set: str):
    """Relabel a list of span/field dicts, dropping those with no equivalent label."""
    out = []
    for item in items:
        mapped = map_label(item["label"], label_set)
        if mapped is not None:
            out.append({**item, "label": mapped})
    return out