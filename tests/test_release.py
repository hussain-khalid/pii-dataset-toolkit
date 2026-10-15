import hashlib
import json
import tempfile
from pathlib import Path

from piikit.build_release import build_release
from piikit.doc_gen import generate_docs, write_annotations
from piikit.splits import SPLITS
from piikit.text_gen import generate, write_jsonl
from piikit.validate_release import validate_release


def make_inputs(tmp: Path, n_text=300, n_docs=40, seed=42):
    text_path = tmp / "text.jsonl"
    write_jsonl(generate(n_text, seed), text_path)
    docs_dir = tmp / "docs_raw"
    write_annotations(generate_docs(n_docs, seed, docs_dir), docs_dir / "docs.jsonl")
    return text_path, docs_dir / "docs.jsonl"


def build(tmp: Path, name="release", **kwargs):
    text_path, docs_path = make_inputs(tmp)
    out = tmp / name
    stats = build_release(text_path, docs_path, out, **kwargs)
    return out, stats


def read(path):
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def test_release_builds_and_validates():
    with tempfile.TemporaryDirectory() as tmp:
        out, _ = build(Path(tmp))
        assert validate_release(out) == []
        for name in ("MANIFEST.json", "PROVENANCE.json", "DATASET_CARD.md", "dedup_report.json"):
            assert (out / name).exists()


def test_kept_records_account_for_all_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        out, stats = build(Path(tmp))
        kept = sum(len(read(out / "text" / f"{s}.jsonl")) for s in SPLITS)
        removed = sum(stats["text"]["removed"].values())
        assert kept == stats["text"]["kept"]
        assert kept + removed == stats["text"]["input"]


def test_splits_are_disjoint():
    with tempfile.TemporaryDirectory() as tmp:
        out, _ = build(Path(tmp))
        ids = [r["id"] for s in SPLITS for r in read(out / "text" / f"{s}.jsonl")]
        assert len(ids) == len(set(ids))


def test_every_record_has_provenance_and_modality():
    with tempfile.TemporaryDirectory() as tmp:
        out, _ = build(Path(tmp))
        for s in SPLITS:
            for r in read(out / "text" / f"{s}.jsonl"):
                assert r["modality"] == "text"
                assert r["provenance"]["synthetic"] is True
                assert r["provenance"]["license"] == "CC0-1.0"
            for r in read(out / "docs" / f"{s}.jsonl"):
                assert r["modality"] == "document"


def test_build_is_byte_for_byte_reproducible():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp)
        a, b = tmp / "a", tmp / "b"
        build_release(text_path, docs_path, a)
        build_release(text_path, docs_path, b)
        manifest_a = (a / "MANIFEST.json").read_bytes()
        assert hashlib.sha256(manifest_a).digest() == hashlib.sha256((b / "MANIFEST.json").read_bytes()).digest()
        assert (a / "DATASET_CARD.md").read_bytes() == (b / "DATASET_CARD.md").read_bytes()


def test_existing_output_directory_is_not_overwritten_by_default():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp)
        out = tmp / "release"
        build_release(text_path, docs_path, out)
        try:
            build_release(text_path, docs_path, out)
        except FileExistsError:
            build_release(text_path, docs_path, out, overwrite=True)
            return
        raise AssertionError("expected FileExistsError")


def test_dataset_card_reports_real_counts():
    with tempfile.TemporaryDirectory() as tmp:
        out, stats = build(Path(tmp))
        card = (out / "DATASET_CARD.md").read_text(encoding="utf-8")
        assert str(stats["text"]["kept"]) in card
        assert str(stats["text"]["input"]) in card
        assert "Limitations" in card and "synthetic" in card.lower()