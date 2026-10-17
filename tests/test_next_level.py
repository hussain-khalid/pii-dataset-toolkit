import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from piikit.doc_gen import generate_doc
from piikit.leaderboard_html import render_html, main as lb_html_main
from piikit.schema import LABELS
from piikit.speech_gen import LOCALE_VOICES, _pick_voice
from piikit.submit import submit
from piikit.systems.ner_baseline import _EMAIL_RE, _ID_RE, _PHONE_RE, SPACY_TO_LABEL, predict_text_ner
from piikit.text_gen import SUPPORTED_LOCALES, generate, generate_record
from piikit.validate import validate_record
from piikit.validate_docs import validate_record as validate_doc_record


def test_multilingual_text_generation():
    for loc in ("de", "fr", "es"):
        records = generate(30, seed=42, locale=loc)
        assert len(records) == 30
        for r in records:
            assert validate_record(r) == []
            assert r["locale"] == loc
            # Spans match text
            for s in r["spans"]:
                assert r["text"][s["start"]:s["end"]] == s["text"]


def test_hard_mode_text_generation():
    records = generate(30, seed=42, hard=True)
    assert len(records) == 30
    for r in records:
        assert validate_record(r) == []
        assert r["hard"] is True
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]] == s["text"]


def test_speech_gen_locale_voices():
    for loc in ("en", "de", "fr", "es"):
        assert loc in LOCALE_VOICES
        rec = {"seed": 42, "id": "txt-000001", "locale": loc}
        voice = _pick_voice(rec)
        assert voice in LOCALE_VOICES[loc]


def test_doc_gen_noisy_flag():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        rec = generate_doc(0, seed=42, out_dir=out_dir, noisy=True)
        assert rec["noisy"] is True
        img_path = out_dir / rec["image"]
        assert img_path.exists()
        assert validate_doc_record(rec, out_dir) == []


def test_ner_baseline_regex_and_mapping():
    assert _EMAIL_RE.search("contact user@example.com today") is not None
    assert _PHONE_RE.search("call 555-0142 now") is not None
    assert _ID_RE.search("ID AB-123456 verified") is not None

    mock_doc = MagicMock()
    mock_ent = MagicMock()
    mock_ent.label_ = "PERSON"
    mock_ent.start_char = 0
    mock_ent.end_char = 9
    mock_doc.ents = [mock_ent]

    mock_nlp = MagicMock(return_value=mock_doc)
    text = "John Doe has email john.doe@example.com"
    spans = predict_text_ner(text, mock_nlp)
    labels = {s["label"] for s in spans}
    assert "PERSON" in labels
    assert "EMAIL" in labels


def test_leaderboard_html_generation():
    with tempfile.TemporaryDirectory() as tmp:
        bench_dir = Path(tmp) / "benchmark"
        results_dir = bench_dir / "results"
        results_dir.mkdir(parents=True)

        sample_res = {
            "name": "regex-rules",
            "task": "text",
            "label_set": "none",
            "records": 50,
            "frozen_id": "testfrozenid12345",
            "metrics": {
                "strict": {
                    "precision": 0.85,
                    "recall": 0.80,
                    "f1": 0.824,
                    "f1_ci95": [0.78, 0.86],
                    "tp": 80, "fp": 15, "fn": 20,
                    "per_label": {}
                },
                "relaxed": {
                    "precision": 0.90,
                    "recall": 0.85,
                    "f1": 0.874,
                    "f1_ci95": [0.83, 0.91],
                    "tp": 85, "fp": 10, "fn": 15,
                    "per_label": {}
                }
            }
        }
        (results_dir / "text__regex-rules__none.json").write_text(json.dumps(sample_res), encoding="utf-8")
        (bench_dir / "FROZEN.json").write_text(json.dumps({"frozen_id": "testfrozenid12345"}), encoding="utf-8")
        html_out = Path(tmp) / "leaderboard.html"
        html = render_html([sample_res], "testfrozenid12345")
        assert "<!DOCTYPE html>" in html
        assert "regex-rules" in html
        assert "0.824" in html

        with patch("sys.argv", ["leaderboard_html", "--bench", str(bench_dir), "--out", str(html_out)]):
            lb_html_main()
        assert html_out.exists()
        assert "regex-rules" in html_out.read_text(encoding="utf-8")


def test_submit_cli_orchestration():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pred_file = tmp_path / "pred.jsonl"
        pred_file.write_text('{"id": "txt-000000", "spans": []}\n', encoding="utf-8")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            submit(
                task="text",
                pred=pred_file,
                name="test-sys",
                bench=tmp_path / "bench",
                label_set="none",
                with_html=True
            )
            # Should have called score, leaderboard, and leaderboard_html
            assert mock_run.call_count == 3
