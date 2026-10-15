import hashlib
import tempfile
from pathlib import Path

from piikit.schema import LABELS
from piikit.text_gen import generate, generate_record, write_jsonl
from piikit.validate import validate_file, validate_record


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generates_requested_number_of_records():
    assert len(generate(25, seed=1)) == 25


def test_every_generated_record_passes_validation():
    for record in generate(500, seed=42):
        assert validate_record(record) == [], record


def test_span_offsets_match_text():
    for record in generate(300, seed=7):
        for span in record["spans"]:
            assert record["text"][span["start"]:span["end"]] == span["text"]


def test_same_seed_gives_identical_files():
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.jsonl", Path(tmp) / "b.jsonl"
        write_jsonl(generate(200, seed=42), a)
        write_jsonl(generate(200, seed=42), b)
        assert _file_hash(a) == _file_hash(b)


def test_different_seeds_give_different_data():
    first = [r["text"] for r in generate(50, seed=1)]
    second = [r["text"] for r in generate(50, seed=2)]
    assert first != second


def test_record_does_not_depend_on_dataset_size():
    # Record 10 must be identical whether we generate 20 or 2000 records.
    assert generate(20, seed=5)[10] == generate(2000, seed=5)[10]
    assert generate_record(10, seed=5) == generate(20, seed=5)[10]


def test_all_labels_appear_in_a_reasonable_sample():
    seen = {span["label"] for r in generate(500, seed=42) for span in r["spans"]}
    assert seen == set(LABELS)


def test_some_records_have_no_pii():
    records = generate(500, seed=42)
    assert any(not r["spans"] for r in records)


def test_emails_use_reserved_example_domains_only():
    for record in generate(500, seed=42):
        for span in record["spans"]:
            if span["label"] == "EMAIL":
                assert span["text"].split("@")[1] in {"example.com", "example.org", "example.net"}


def test_phone_numbers_use_fictional_range():
    for record in generate(500, seed=42):
        for span in record["spans"]:
            if span["label"] == "PHONE":
                assert "555" in span["text"]


def test_generated_file_validates_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "text.jsonl"
        write_jsonl(generate(100, seed=3), path)
        errors, stats = validate_file(path)
        assert errors == []
        assert stats["records"] == 100