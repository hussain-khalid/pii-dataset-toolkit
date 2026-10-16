import json
import tempfile
from pathlib import Path

from piikit.build_release import build_release
from piikit.freeze import freeze, read_jsonl
from piikit.score import match_boxes, match_spans, prf, save_result, score_docs, score_text
from tests.test_release import make_inputs


def make_bench(tmp: Path) -> Path:
    text_path, docs_path = make_inputs(tmp, n_text=300, n_docs=60)
    release = tmp / "release"
    build_release(text_path, docs_path, release)
    bench = tmp / "bench"
    freeze(release, bench)
    return bench


def write(path: Path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def text_preds(bench: Path, transform=lambda spans: spans):
    return [{"id": r["id"], "spans": transform(r["spans"])}
            for r in read_jsonl(bench / "text" / "gold.jsonl")]


def doc_preds(bench: Path, transform=lambda fields: fields):
    return [{"id": r["id"], "fields": transform(r["fields"])}
            for r in read_jsonl(bench / "docs" / "gold.jsonl")]


def raises_value_error(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


# ---- unit tests on the matching rules

def test_prf_basics():
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)
    assert prf(2, 0, 0) == (1.0, 1.0, 1.0)
    p, r, f = prf(1, 1, 1)
    assert (p, r) == (0.5, 0.5) and f == 0.5


def span(start, end, label="PERSON"):
    return {"start": start, "end": end, "label": label}


def test_strict_needs_exact_boundaries_and_label():
    gold = [span(0, 10)]
    assert match_spans(gold, [span(0, 10)], relaxed=False) == {"PERSON": [1, 0, 0]}
    assert match_spans(gold, [span(1, 10)], relaxed=False) == {"PERSON": [0, 1, 1]}
    assert match_spans(gold, [span(0, 10, "EMAIL")], relaxed=False) == {
        "EMAIL": [0, 1, 0], "PERSON": [0, 0, 1]}


def test_relaxed_accepts_overlap_of_at_least_half():
    gold = [span(0, 10)]
    assert match_spans(gold, [span(1, 10)], relaxed=True) == {"PERSON": [1, 0, 0]}
    assert match_spans(gold, [span(6, 10)], relaxed=True) == {"PERSON": [0, 1, 1]}


def test_matching_is_one_to_one():
    gold = [span(0, 10)]
    counts = match_spans(gold, [span(0, 10), span(0, 10)], relaxed=False)
    assert counts == {"PERSON": [1, 1, 0]}


def test_box_matching_uses_iou_threshold():
    gold = [{"label": "PERSON", "bbox": [0, 0, 10, 10]}]
    near = [{"label": "PERSON", "bbox": [1, 0, 11, 10]}]     # IoU about 0.82
    far = [{"label": "PERSON", "bbox": [8, 0, 18, 10]}]      # IoU about 0.11
    assert match_boxes(gold, near) == {"PERSON": [1, 0, 0]}
    assert match_boxes(gold, far) == {"PERSON": [0, 1, 1]}


# ---- end-to-end scoring on a frozen benchmark

def test_perfect_text_predictions_score_one():
    with tempfile.TemporaryDirectory() as tmp:
        bench = make_bench(Path(tmp))
        preds = write(Path(tmp) / "p.jsonl", text_preds(bench))
        result = score_text(bench, preds)
        assert result["metrics"]["strict"]["f1"] == 1.0
        assert result["metrics"]["relaxed"]["f1"] == 1.0
        assert result["false_alarm_rate_on_clean_records"] == 0.0


def test_empty_text_predictions_score_zero():
    with tempfile.TemporaryDirectory() as tmp:
        bench = make_bench(Path(tmp))
        preds = write(Path(tmp) / "p.jsonl", text_preds(bench, lambda s: []))
        m = score_text(bench, preds)["metrics"]["strict"]
        assert m["recall"] == 0.0 and m["f1"] == 0.0


def test_shifted_spans_fail_strict_but_pass_relaxed():
    with tempfile.TemporaryDirectory() as tmp:
        bench = make_bench(Path(tmp))
        shift = lambda spans: [{**s, "start": s["start"] + 1} for s in spans]
        result = score_text(bench, write(Path(tmp) / "p.jsonl", text_preds(bench, shift)))
        assert result["metrics"]["strict"]["f1"] == 0.0
        assert result["metrics"]["relaxed"]["f1"] == 1.0


def test_false_alarm_on_clean_record_is_counted():
    with tempfile.TemporaryDirectory() as tmp:
        bench = make_bench(Path(tmp))
        gold = {r["id"]: r["spans"] for r in read_jsonl(bench / "text" / "gold.jsonl")}
        preds = text_preds(bench)
        clean_ids = [i for i, s in gold.items() if not s]
        assert clean_ids, "benchmark should contain records without PII"
        for p in preds:
            if p["id"] == clean_ids[0]:
                p["spans"] = [span(0, 3)]
        result = score_text(bench, write(Path(tmp) / "p.jsonl", preds))
        assert result["false_alarm_rate_on_clean_records"] == round(1 / len(clean_ids), 4)


def test_invalid_predictions_are_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bench = make_bench(tmp)
        good = text_preds(bench)

        assert raises_value_error(lambda: score_text(bench, write(tmp / "a.jsonl", good[1:])))
        assert raises_value_error(lambda: score_text(bench, write(tmp / "b.jsonl", good + [good[0]])))
        bad_label = [{"id": good[0]["id"], "spans": [span(0, 3, "CREDIT_CARD")]}] + good[1:]
        assert raises_value_error(lambda: score_text(bench, write(tmp / "c.jsonl", bad_label)))
        bad_offsets = [{"id": good[0]["id"], "spans": [span(0, 99999)]}] + good[1:]
        assert raises_value_error(lambda: score_text(bench, write(tmp / "d.jsonl", bad_offsets)))
        unknown = good + [{"id": "txt-999999", "spans": []}]
        assert raises_value_error(lambda: score_text(bench, write(tmp / "e.jsonl", unknown)))


def test_scoring_refuses_a_tampered_benchmark():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bench = make_bench(tmp)
        preds = write(tmp / "p.jsonl", text_preds(bench))
        gold = bench / "text" / "gold.jsonl"
        gold.write_text(gold.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert raises_value_error(lambda: score_text(bench, preds))


def test_label_set_mapping_drops_unmapped_labels():
    with tempfile.TemporaryDirectory() as tmp:
        bench = make_bench(Path(tmp))
        preds = write(Path(tmp) / "p.jsonl", text_preds(bench))
        result = score_text(bench, preds, label_set="presidio")
        labels = set(result["metrics"]["strict"]["per_label"])
        assert "ID_NUMBER" not in labels and "EMAIL_ADDRESS" in labels
        assert result["metrics"]["strict"]["f1"] == 1.0


def test_bootstrap_interval_is_deterministic_and_contains_the_estimate():
    with tempfile.TemporaryDirectory() as tmp:
        bench = make_bench(Path(tmp))
        drop_half = lambda spans: spans[::2]
        preds = write(Path(tmp) / "p.jsonl", text_preds(bench, drop_half))
        a, b = score_text(bench, preds), score_text(bench, preds)
        assert a == b
        m = a["metrics"]["strict"]
        assert m["f1_ci95"][0] <= m["f1"] <= m["f1_ci95"][1]


def test_document_scoring():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bench = make_bench(tmp)
        perfect = score_docs(bench, write(tmp / "a.jsonl", doc_preds(bench)))
        assert perfect["metrics"]["iou_0.5"]["f1"] == 1.0

        empty = score_docs(bench, write(tmp / "b.jsonl", doc_preds(bench, lambda f: [])))
        assert empty["metrics"]["iou_0.5"]["f1"] == 0.0

        nudge = lambda fields: [{**f, "bbox": [f["bbox"][0] + 1, *f["bbox"][1:]]} for f in fields]
        nudged = score_docs(bench, write(tmp / "c.jsonl", doc_preds(bench, nudge)))
        assert nudged["metrics"]["iou_0.5"]["f1"] == 1.0


def test_saved_result_has_a_predictable_name():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bench = make_bench(tmp)
        result = score_text(bench, write(tmp / "p.jsonl", text_preds(bench)))
        out = save_result(bench, "my-system", result)
        assert out.name == "text__my-system__none.json"
        assert json.loads(out.read_text())["name"] == "my-system"