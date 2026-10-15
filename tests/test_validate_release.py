import json
import tempfile
from pathlib import Path

from piikit.build_release import build_release
from piikit.validate_release import find_leaks, validate_release
from tests.test_release import make_inputs


def build_valid(tmp: Path) -> Path:
    text_path, docs_path = make_inputs(tmp)
    out = tmp / "release"
    build_release(text_path, docs_path, out)
    assert validate_release(out) == []
    return out


def test_tampered_file_is_detected_by_checksum():
    with tempfile.TemporaryDirectory() as tmp:
        out = build_valid(Path(tmp))
        path = out / "text" / "test.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert any("checksum" in e for e in validate_release(out))


def test_missing_file_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        out = build_valid(Path(tmp))
        (out / "docs" / "validation.jsonl").unlink()
        assert any("missing" in e for e in validate_release(out))


def test_missing_manifest_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        out = build_valid(Path(tmp))
        (out / "MANIFEST.json").unlink()
        assert validate_release(out) == ["MANIFEST.json is missing"]


def test_deleted_image_is_detected():
    with tempfile.TemporaryDirectory() as tmp:
        out = build_valid(Path(tmp))
        next((out / "docs" / "images").glob("*.png")).unlink()
        assert validate_release(out) != []


def test_find_leaks_reports_records_shared_between_splits():
    splits = {"train": [{"id": "a"}, {"id": "b"}], "validation": [{"id": "c"}],
              "test": [{"id": "b"}]}
    leaks = find_leaks(splits, lambda r: r["id"], "text id")
    assert len(leaks) == 1 and "train and test" in leaks[0]


def test_find_leaks_is_quiet_for_clean_splits():
    splits = {"train": [{"id": "a"}], "validation": [{"id": "b"}], "test": [{"id": "c"}]}
    assert find_leaks(splits, lambda r: r["id"], "text id") == []