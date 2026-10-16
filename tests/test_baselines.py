import json
import tempfile
from pathlib import Path

from piikit.baselines import predict_text, run
from piikit.build_release import build_release
from piikit.freeze import freeze
from piikit.score import score_text
from tests.test_release import make_inputs


def found(text):
    return [(text[s["start"]:s["end"]], s["label"]) for s in predict_text(text)]


def test_regex_baseline_finds_each_label_in_its_common_format():
    assert ("anna.keller@example.com", "EMAIL") in found("Contact anna.keller@example.com today.")
    assert ("+1-555-0142", "PHONE") in found("Call +1-555-0142 now.")
    assert ("AB-123456", "ID_NUMBER") in found("Reference AB-123456 was issued.")
    assert ("1990-04-12", "DATE_OF_BIRTH") in found("Born 1990-04-12.")
    assert ("985 Birch Court, Westbury", "ADDRESS") in found("Lives at 985 Birch Court, Westbury today.")
    assert ("Anna Keller", "PERSON") in found("Hello, my name is Anna Keller and I need help.")


def test_regex_baseline_strips_leading_non_name_words():
    assert found("Customer Anna Keller reported a problem.") == [("Anna Keller", "PERSON")]


def test_regex_baseline_misses_uncommon_formats():
    assert found("my email is anna.keller [at] example.com") == []
    assert found("name: anna keller") == []


def test_regex_baseline_does_not_label_an_address_as_a_person():
    labels = [label for _, label in found("Ship to 985 Birch Court, Westbury please.")]
    assert labels == ["ADDRESS"]


def test_empty_baseline_predicts_nothing_for_every_id():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp, 200, 30)
        build_release(text_path, docs_path, tmp / "release")
        freeze(tmp / "release", tmp / "bench")
        preds = run("text-empty", tmp / "bench", tmp / "p.jsonl")
        assert preds and all(p["spans"] == [] for p in preds)


def test_regex_baseline_scores_between_empty_and_perfect():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp, 300, 30)
        build_release(text_path, docs_path, tmp / "release")
        freeze(tmp / "release", tmp / "bench")
        run("text-regex", tmp / "bench", tmp / "p.jsonl")
        m = score_text(tmp / "bench", tmp / "p.jsonl")["metrics"]["strict"]
        assert 0.3 < m["f1"] < 1.0


def test_baselines_refuse_a_tampered_benchmark():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        text_path, docs_path = make_inputs(tmp, 200, 30)
        build_release(text_path, docs_path, tmp / "release")
        freeze(tmp / "release", tmp / "bench")
        inputs = tmp / "bench" / "text" / "inputs.jsonl"
        inputs.write_text(inputs.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            run("text-regex", tmp / "bench", tmp / "p.jsonl")
        except ValueError:
            return
        raise AssertionError("expected ValueError")