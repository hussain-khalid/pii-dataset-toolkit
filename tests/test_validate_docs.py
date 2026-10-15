import copy
import tempfile
from pathlib import Path

from piikit.doc_gen import generate_doc
from piikit.validate_docs import iou, validate_record


def make_good(tmp: str) -> dict:
    return generate_doc(0, 42, Path(tmp))


def test_valid_document_has_no_errors():
    with tempfile.TemporaryDirectory() as tmp:
        assert validate_record(make_good(tmp), Path(tmp)) == []


def test_bbox_outside_image_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        record = make_good(tmp)
        record["fields"][0]["bbox"] = [10, 10, record["width"] + 50, 40]
        assert any("outside the image" in e for e in validate_record(record, Path(tmp)))


def test_blank_box_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        record = make_good(tmp)
        record["fields"][0]["bbox"] = [1, 1, 15, 15]  # empty corner of the page
        assert any("no visible text" in e for e in validate_record(record, Path(tmp)))


def test_overlapping_boxes_are_reported():
    with tempfile.TemporaryDirectory() as tmp:
        record = make_good(tmp)
        record["fields"].append(copy.deepcopy(record["fields"][0]))
        assert any("overlap" in e for e in validate_record(record, Path(tmp)))


def test_missing_image_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        record = make_good(tmp)
        record["image"] = "images/does-not-exist.png"
        assert any("image not found" in e for e in validate_record(record, Path(tmp)))


def test_unknown_label_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        record = make_good(tmp)
        record["fields"][0]["label"] = "CREDIT_CARD"
        assert any("unknown label" in e for e in validate_record(record, Path(tmp)))


def test_missing_key_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        record = make_good(tmp)
        del record["doc_type"]
        assert any("missing keys" in e for e in validate_record(record, Path(tmp)))


def test_iou_basics():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0