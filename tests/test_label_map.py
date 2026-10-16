from piikit.label_map import LABEL_SETS, map_items, map_label
from piikit.schema import LABELS


def test_none_keeps_labels():
    assert all(map_label(l, "none") == l for l in LABELS)


def test_presidio_mapping():
    assert map_label("EMAIL", "presidio") == "EMAIL_ADDRESS"
    assert map_label("PHONE", "presidio") == "PHONE_NUMBER"
    assert map_label("ID_NUMBER", "presidio") is None


def test_conll_keeps_only_person_and_location():
    kept = {l: map_label(l, "conll") for l in LABELS if map_label(l, "conll")}
    assert kept == {"PERSON": "PER", "ADDRESS": "LOC"}


def test_every_label_is_covered_by_every_mapping():
    for name, mapping in LABEL_SETS.items():
        if mapping is not None:
            assert set(mapping) == set(LABELS), name


def test_unknown_label_set_is_rejected():
    try:
        map_label("PERSON", "nope")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_map_items_relabels_and_drops_unmapped():
    items = [{"label": "PERSON", "start": 0}, {"label": "ID_NUMBER", "start": 5}]
    assert map_items(items, "presidio") == [{"label": "PERSON", "start": 0}]
    assert map_items([{"label": "EMAIL"}], "presidio") == [{"label": "EMAIL_ADDRESS"}]