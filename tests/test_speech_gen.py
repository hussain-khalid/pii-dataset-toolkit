"""Tests for piikit.speech_gen and piikit.validate_speech.

Unit tests cover _align_spans and helpers with no network access.
Integration tests call edge-tts over the network and are skipped when
the PIIKIT_SKIP_NETWORK env var is set or edge-tts is not installed.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ── helpers ─────────────────────────────────────────────────────────────────

edge_tts = pytest.importorskip("edge_tts", reason="edge-tts not installed")

from piikit.speech_gen import (
    _100NS,
    _align_spans,
    _duration_from_cues,
    _pick_voice,
    _ticks_to_s,
    VOICES,
    generate_speech_record,
)
from piikit.validate_speech import validate_speech

SKIP_NETWORK = pytest.mark.skipif(
    os.getenv("PIIKIT_SKIP_NETWORK", "0") != "0",
    reason="PIIKIT_SKIP_NETWORK is set",
)

# ── pure unit tests (no TTS) ─────────────────────────────────────────────────


def _cue(text, char_start, char_end, t_start, t_end):
    """Build a sentence cue dict matching _synthesize's return format."""
    return {"text": text, "char_start": char_start, "char_end": char_end,
            "t_start": t_start, "t_end": t_end}


def test_ticks_to_s_converts_correctly():
    assert _ticks_to_s(0) == 0.0
    assert abs(_ticks_to_s(_100NS) - 1.0) < 1e-9
    assert abs(_ticks_to_s(_100NS // 2) - 0.5) < 1e-9


def test_duration_from_cues_empty():
    assert _duration_from_cues([]) == 0.0


def test_duration_from_cues_single():
    c = [_cue("Hello.", 0, 6, 0.1, 0.6)]
    assert abs(_duration_from_cues(c) - 0.6) < 1e-4


def test_duration_from_cues_multiple():
    c = [_cue("Hello.", 0, 6, 0.1, 0.6), _cue("Bye.", 7, 11, 0.7, 1.4)]
    assert abs(_duration_from_cues(c) - 1.4) < 1e-4


def test_align_spans_finds_entity_within_sentence():
    # text: "Hello Anna Keller today."
    #        0         1         2
    #        0123456789012345678901234
    # Anna Keller = chars 6-17
    cues = [_cue("Hello Anna Keller today.", 0, 24, 0.1, 2.5)]
    spans = [{"start": 6, "end": 17, "label": "PERSON", "text": "Anna Keller"}]
    result = _align_spans(spans, cues)
    assert len(result) == 1
    s = result[0]
    assert s["label"] == "PERSON"
    assert s["start_s"] is not None and s["end_s"] is not None
    # proportional: 6/24 * 2.4 + 0.1 = 0.7; 17/24 * 2.4 + 0.1 = 1.8
    assert s["start_s"] < s["end_s"]
    assert 0.1 <= s["start_s"] < s["end_s"] <= 2.5


def test_align_spans_no_overlap_returns_none():
    cues = [_cue("Hello.", 0, 6, 0.0, 0.5)]
    spans = [{"start": 10, "end": 20, "label": "EMAIL", "text": "x@example.com"}]
    result = _align_spans(spans, cues)
    assert result[0]["start_s"] is None
    assert result[0]["end_s"] is None


def test_align_spans_preserves_other_keys():
    cues = [_cue("Anna.", 0, 5, 0.0, 0.5)]
    spans = [{"start": 0, "end": 4, "label": "PERSON", "text": "Anna",
               "extra_key": "keep_me"}]
    result = _align_spans(spans, cues)
    assert result[0]["extra_key"] == "keep_me"


def test_align_spans_straddles_two_sentences():
    # span covers tail of sentence 1 and head of sentence 2
    cues = [
        _cue("Hello Anna.", 0, 11, 0.0, 1.0),
        _cue("Keller works here.", 12, 30, 1.1, 3.0),
    ]
    # "Anna Keller" = chars 6-17 — straddles both cues
    spans = [{"start": 6, "end": 17, "label": "PERSON", "text": "Anna Keller"}]
    result = _align_spans(spans, cues)
    assert result[0]["start_s"] is not None
    assert result[0]["end_s"] is not None
    assert result[0]["start_s"] < result[0]["end_s"]


def test_pick_voice_is_deterministic():
    rec = {"id": "txt-000001", "seed": 42}
    v1 = _pick_voice(rec)
    v2 = _pick_voice(rec)
    assert v1 == v2
    assert v1 in VOICES


def test_pick_voice_differs_across_records():
    voices = {_pick_voice({"id": f"txt-{i:06d}", "seed": 42}) for i in range(20)}
    assert len(voices) > 1  # not all the same voice


# ── mocked TTS tests (no network) ───────────────────────────────────────────

def _make_text_record(n=0):
    return {
        "id": f"txt-{n:06d}",
        "text": "Hello, my name is Anna Keller.",
        "spans": [{"start": 18, "end": 29, "label": "PERSON", "text": "Anna Keller"}],
        "seed": 42,
        "template_id": "t01",
        "source": "synthetic/text_gen",
        "generator_version": "0.2.0",
    }


async def _mock_synthesize(text, voice, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"FAKE_MP3_DATA")
    # Return sentence cues matching the test text:
    # "Hello, my name is Anna Keller."
    return [_cue("Hello, my name is Anna Keller.", 0, 30, 0.1, 1.85)]


def test_generate_speech_record_mocked():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rec = _make_text_record()
        with patch("piikit.speech_gen._synthesize", side_effect=_mock_synthesize):
            result = generate_speech_record(rec, tmp)

    assert result["id"] == "txt-000000"
    assert result["audio"].endswith(".mp3")
    assert result["duration_s"] > 0
    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["label"] == "PERSON"
    assert span["start_s"] is not None
    assert span["end_s"] is not None
    assert span["start_s"] < span["end_s"]


def test_generate_speech_record_audio_file_written():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rec = _make_text_record()
        with patch("piikit.speech_gen._synthesize", side_effect=_mock_synthesize):
            result = generate_speech_record(rec, tmp)
        assert (tmp / result["audio"]).exists()


def test_generate_speech_record_has_required_keys():
    required = {"id", "audio", "duration_s", "text", "spans",
                 "tts_voice", "source", "generator_version", "seed", "template_id"}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rec = _make_text_record()
        with patch("piikit.speech_gen._synthesize", side_effect=_mock_synthesize):
            result = generate_speech_record(rec, tmp)
    assert required.issubset(result.keys())


# ── validator tests (using mocked data) ─────────────────────────────────────

def _write_speech_jsonl(tmp: Path, records: list[dict]) -> Path:
    """Write speech records to a temp dir and return the JSONL path."""
    jsonl = tmp / "speech.jsonl"
    # Write fake audio files
    for r in records:
        audio_path = tmp / r["audio"]
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"FAKE")
    with jsonl.open("w") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    return jsonl


def _good_record(n=0):
    return {
        "id": f"txt-{n:06d}",
        "audio": f"audio/txt-{n:06d}.mp3",
        "duration_s": 1.85,
        "text": "Hello, my name is Anna Keller.",
        "spans": [{
            "start": 18, "end": 29, "label": "PERSON", "text": "Anna Keller",
            "start_s": 0.875, "end_s": 1.325,
        }],
        "tts_voice": "en-US-JennyNeural",
        "source": "synthetic/speech_gen",
        "generator_version": "0.2.0",
        "seed": 42,
        "template_id": "t01",
    }


def test_validator_accepts_valid_record():
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), [_good_record()])
        errors = validate_speech(jsonl)
    assert errors == []


def test_validator_accepts_null_timestamps():
    """None start_s/end_s are valid (hard-format entity)."""
    rec = _good_record()
    rec["spans"][0]["start_s"] = None
    rec["spans"][0]["end_s"] = None
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), [rec])
        errors = validate_speech(jsonl)
    assert errors == []


def test_validator_rejects_missing_audio():
    rec = _good_record()
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = tmp / Path("speech.jsonl")
        with jsonl.open("w") as f:
            f.write(json.dumps(rec) + "\n")
        errors = validate_speech(jsonl)
    assert any("audio file not found" in e for e in errors)


def test_validator_rejects_inverted_time_span():
    rec = _good_record()
    rec["spans"][0]["start_s"] = 1.5
    rec["spans"][0]["end_s"] = 0.5
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), [rec])
        errors = validate_speech(jsonl)
    assert any("start_s" in e and ">=" in e for e in errors)


def test_validator_rejects_end_beyond_duration():
    rec = _good_record()
    rec["spans"][0]["end_s"] = 99.0  # way beyond duration_s=1.85
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), [rec])
        errors = validate_speech(jsonl)
    assert any("duration_s" in e for e in errors)


def test_validator_rejects_text_slice_mismatch():
    rec = _good_record()
    rec["spans"][0]["text"] = "Wrong Name"
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), [rec])
        errors = validate_speech(jsonl)
    assert any("mismatch" in e for e in errors)


def test_validator_rejects_unknown_label():
    rec = _good_record()
    rec["spans"][0]["label"] = "SSID"
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), [rec])
        errors = validate_speech(jsonl)
    assert any("unknown label" in e for e in errors)


def test_validator_rejects_duplicate_ids():
    recs = [_good_record(0), _good_record(0)]  # same id
    with tempfile.TemporaryDirectory() as tmp:
        jsonl = _write_speech_jsonl(Path(tmp), recs)
        errors = validate_speech(jsonl)
    assert any("duplicate id" in e for e in errors)


# ── integration test (real network, real TTS) ────────────────────────────────

@SKIP_NETWORK
def test_real_tts_produces_aligned_spans():
    """End-to-end: call Edge TTS, check the output is valid."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rec = _make_text_record()
        result = generate_speech_record(rec, tmp, voice="en-US-JennyNeural")

        assert (tmp / result["audio"]).stat().st_size > 1000
        assert result["duration_s"] > 0.5
        span = result["spans"][0]
        assert span["start_s"] is not None
        assert span["start_s"] < span["end_s"] <= result["duration_s"] + 0.1

        jsonl = tmp / "speech.jsonl"
        with jsonl.open("w") as f:
            f.write(json.dumps(result, sort_keys=True) + "\n")
        errors = validate_speech(jsonl)
        assert errors == [], errors
