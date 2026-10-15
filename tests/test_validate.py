import json
import tempfile
from pathlib import Path

from piikit.validate import validate_file, validate_record


def good_record():
    return {
        "id": "txt-000001",
        "text": "Contact Anna Keller today.",
        "spans": [{"start": 8, "end": 19, "label": "PERSON", "text": "Anna Keller"}],
        "source": "synthetic/text_gen",
        "generator_version": "0.1.0",
        "seed": 42,
        "template_id": "t01",
    }


def test_valid_record_has_no_errors():
    assert validate_record(good_record()) == []


def test_missing_key_is_reported():
    record = good_record()
    del record["source"]
    assert any("missing keys" in e for e in validate_record(record))


def test_wrong_offsets_are_reported():
    record = good_record()
    record["spans"][0]["start"] = 9
    assert any("expected" in e for e in validate_record(record))


def test_offsets_outside_text_are_reported():
    record = good_record()
    record["spans"][0]["end"] = 500
    assert any("outside text" in e for e in validate_record(record))


def test_unknown_label_is_reported():
    record = good_record()
    record["spans"][0]["label"] = "CREDIT_CARD"
    assert any("unknown label" in e for e in validate_record(record))


def test_overlapping_spans_are_reported():
    record = good_record()
    # "Keller" sits inside the existing "Anna Keller" span, so the two overlap.
    record["spans"].append({"start": 13, "end": 19, "label": "PERSON", "text": "Keller"})
    assert any("overlaps" in e for e in validate_record(record))


def test_empty_text_is_reported():
    record = good_record()
    record["text"] = "   "
    assert validate_record(record)


def test_file_level_checks_catch_duplicate_ids_and_bad_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.jsonl"
        good = json.dumps(good_record())
        path.write_text(good + "\n" + good + "\n" + "{not json}\n", encoding="utf-8")
        errors, _ = validate_file(path)
        messages = " ".join(m for _, m in errors)
        assert "duplicate id" in messages
        assert "invalid JSON" in messages