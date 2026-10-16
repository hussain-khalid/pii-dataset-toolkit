import json
import tempfile
from pathlib import Path

from piikit.build_release import build_release
from piikit.freeze import freeze, read_jsonl, verify_frozen
from tests.test_release import make_inputs


def make_release(tmp: Path) -> Path:
    text_path, docs_path = make_inputs(tmp, n_text=200, n_docs=30)
    release = tmp / "release"
    build_release(text_path, docs_path, release)
    return release


def test_inputs_hide_the_labels_and_generator_details():
    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp) / "bench"
        freeze(make_release(Path(tmp)), bench)
        for record in read_jsonl(bench / "text" / "inputs.jsonl"):
            assert set(record) == {"id", "text"}
        for record in read_jsonl(bench / "docs" / "inputs.jsonl"):
            assert set(record) == {"id", "image", "width", "height"}


def test_gold_matches_the_release_test_split():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        release, bench = make_release(tmp), tmp / "bench"
        freeze(release, bench)
        expected = {r["id"]: [(s["start"], s["end"], s["label"]) for s in r["spans"]]
                    for r in read_jsonl(release / "text" / "test.jsonl")}
        actual = {r["id"]: [(s["start"], s["end"], s["label"]) for s in r["spans"]]
                  for r in read_jsonl(bench / "text" / "gold.jsonl")}
        assert actual == expected


def test_frozen_benchmark_verifies_and_tampering_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bench = tmp / "bench"
        freeze(make_release(tmp), bench)
        assert verify_frozen(bench) == []
        gold = bench / "text" / "gold.jsonl"
        gold.write_text(gold.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert any("changed" in e for e in verify_frozen(bench))


def test_missing_frozen_file_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bench = tmp / "bench"
        freeze(make_release(tmp), bench)
        next((bench / "docs" / "images").glob("*.png")).unlink()
        assert any("missing" in e for e in verify_frozen(bench))


def test_unfrozen_directory_fails_verification():
    with tempfile.TemporaryDirectory() as tmp:
        assert any("FROZEN.json" in e for e in verify_frozen(Path(tmp)))


def test_existing_frozen_benchmark_is_not_overwritten_by_default():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        release, bench = make_release(tmp), tmp / "bench"
        freeze(release, bench)
        try:
            freeze(release, bench)
        except FileExistsError:
            freeze(release, bench, overwrite=True)
            return
        raise AssertionError("expected FileExistsError")


def test_frozen_id_is_reproducible():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        release = make_release(tmp)
        a = freeze(release, tmp / "a")["frozen_id"]
        b = freeze(release, tmp / "b")["frozen_id"]
        assert a == b