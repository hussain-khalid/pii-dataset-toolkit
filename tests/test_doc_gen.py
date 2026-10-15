import hashlib
import tempfile
from pathlib import Path

from piikit.doc_gen import generate_doc, generate_docs, write_annotations
from piikit.schema import DOC_TYPES, LABELS
from piikit.validate_docs import validate_file


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(tmp: str, n: int, seed: int) -> Path:
    out = Path(tmp)
    records = generate_docs(n, seed, out)
    write_annotations(records, out / "docs.jsonl")
    return out


def test_generates_images_and_annotations():
    with tempfile.TemporaryDirectory() as tmp:
        out = _build(tmp, 12, seed=1)
        assert len(list((out / "images").glob("*.png"))) == 12
        assert (out / "docs.jsonl").exists()


def test_generated_dataset_passes_validation():
    with tempfile.TemporaryDirectory() as tmp:
        out = _build(tmp, 60, seed=42)
        errors, stats = validate_file(out / "docs.jsonl")
        assert errors == [], errors[:5]
        assert stats["records"] == 60


def test_same_seed_gives_identical_annotations_and_images():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        out_a, out_b = _build(a, 20, seed=42), _build(b, 20, seed=42)
        assert _hash(out_a / "docs.jsonl") == _hash(out_b / "docs.jsonl")
        for i in range(20):
            name = f"images/doc-{i:06d}.png"
            assert _hash(out_a / name) == _hash(out_b / name)


def test_different_seeds_give_different_documents():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        fields_a = [r["fields"] for r in generate_docs(10, 1, Path(a))]
        fields_b = [r["fields"] for r in generate_docs(10, 2, Path(b))]
        assert fields_a != fields_b


def test_document_does_not_depend_on_dataset_size():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        small = generate_docs(10, 5, Path(a))[7]
        alone = generate_doc(7, 5, Path(b))
        assert small == alone


def test_all_labels_and_document_types_appear():
    with tempfile.TemporaryDirectory() as tmp:
        records = generate_docs(120, 42, Path(tmp))
        assert {f["label"] for r in records for f in r["fields"]} == set(LABELS)
        assert {r["doc_type"] for r in records} == set(DOC_TYPES)


def test_every_document_has_at_least_one_labelled_field():
    with tempfile.TemporaryDirectory() as tmp:
        assert all(r["fields"] for r in generate_docs(60, 42, Path(tmp)))