import tempfile
from pathlib import Path

from piikit.dedup import dedup_docs, dedup_text, jaccard, normalize_text, shingles


def rec(i, text):
    return {"id": f"txt-{i:06d}", "text": text, "spans": []}


def test_normalize_ignores_case_and_whitespace():
    assert normalize_text("  Hello   WORLD ") == "hello world"


def test_exact_duplicates_are_removed_and_first_is_kept():
    records = [rec(0, "Please restart the application."),
               rec(1, "please  restart the APPLICATION."),
               rec(2, "Something else entirely.")]
    kept, removed = dedup_text(records)
    assert [r["id"] for r in kept] == ["txt-000000", "txt-000002"]
    assert removed == [{"id": "txt-000001", "reason": "exact_duplicate",
                        "duplicate_of": "txt-000000"}]


def test_near_duplicates_are_removed_above_threshold():
    base = "The quarterly report on sales and costs will be published next Tuesday morning"
    almost = base + " today"
    kept, removed = dedup_text([rec(0, base), rec(1, almost)], threshold=0.8)
    assert len(kept) == 1
    assert removed[0]["reason"] == "near_duplicate"
    assert removed[0]["jaccard"] >= 0.8


def test_distinct_texts_are_kept():
    records = [rec(0, "Hello, my name is Anna Keller and I need help."),
               rec(1, "Please send the invoice to the billing department.")]
    kept, removed = dedup_text(records)
    assert len(kept) == 2 and removed == []


def test_dedup_is_deterministic():
    records = [rec(i, f"Order {i % 5} shipped on Monday and will arrive soon") for i in range(40)]
    assert dedup_text(records) == dedup_text(records)


def test_jaccard_and_shingles_basics():
    assert jaccard({"a"}, {"a"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0
    assert shingles("one two three four", n=3) == {"one two three", "two three four"}
    assert shingles("hi there") == {"hi there"}


def doc(i, image, fields):
    return {"id": f"doc-{i:06d}", "image": image, "doc_type": "form",
            "fields": [{"label": l, "text": t, "bbox": [0, 0, 1, 1]} for l, t in fields]}


def test_docs_with_same_fields_are_duplicates():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.png").write_bytes(b"a")
        (Path(tmp) / "b.png").write_bytes(b"b")
        fields = [("PERSON", "Anna Keller"), ("PHONE", "555-0100")]
        kept, removed = dedup_docs([doc(0, "a.png", fields), doc(1, "b.png", fields[::-1])], Path(tmp))
        assert len(kept) == 1 and removed[0]["reason"] == "exact_duplicate"


def test_docs_with_identical_image_bytes_are_duplicates():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.png").write_bytes(b"same")
        (Path(tmp) / "b.png").write_bytes(b"same")
        kept, removed = dedup_docs(
            [doc(0, "a.png", [("PERSON", "Anna Keller")]),
             doc(1, "b.png", [("PERSON", "Omar Keller")])], Path(tmp))
        assert len(kept) == 1 and removed[0]["reason"] == "identical_image"