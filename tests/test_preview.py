import tempfile
from pathlib import Path

from PIL import Image

from piikit.doc_gen import generate_docs
from piikit.preview import render_preview, write_previews
from piikit.schema import DOC_TYPES


def test_preview_has_the_same_size_as_the_document():
    with tempfile.TemporaryDirectory() as tmp:
        record = generate_docs(1, 42, Path(tmp))[0]
        image = render_preview(record, Path(tmp))
        assert image.size == (record["width"], record["height"])


def test_boxes_change_the_pixels():
    with tempfile.TemporaryDirectory() as tmp:
        record = generate_docs(1, 42, Path(tmp))[0]
        original = Image.open(Path(tmp) / record["image"]).convert("RGB")
        assert render_preview(record, Path(tmp)).tobytes() != original.tobytes()


def test_per_type_writes_one_stable_name_per_document_type():
    with tempfile.TemporaryDirectory() as tmp:
        records = generate_docs(60, 42, Path(tmp))
        paths = write_previews(records, Path(tmp), Path(tmp) / "out", per_type=True)
        assert sorted(p.name for p in paths) == sorted(f"example_{t}.png" for t in DOC_TYPES)
        assert all(p.exists() for p in paths)


def test_numbered_previews_respect_n():
    with tempfile.TemporaryDirectory() as tmp:
        records = generate_docs(10, 42, Path(tmp))
        assert len(write_previews(records, Path(tmp), Path(tmp) / "out", n=4)) == 4