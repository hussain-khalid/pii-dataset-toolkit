"""Generate synthetic speech recordings with word-level PII timestamps.

Takes the text records produced by piikit.text_gen (which already carry
character-offset PII spans) and runs Microsoft Edge TTS on each record.
Edge TTS streams back WordBoundary events that give the character offset
and audio timestamp of each word, which are used to map PII spans from
character space into time space.

Usage:
    python -m piikit.speech_gen --n 50 --seed 42 \\
        --text data/raw/text.jsonl --out-dir data/raw/speech

Output (one directory):
    audio/txt-XXXXXX.mp3
    speech.jsonl               one record per line (format below)

Record format
-------------
{
  "id":                "txt-000042",
  "audio":             "audio/txt-000042.mp3",
  "duration_s":        3.87,
  "text":              "Hello, my name is Anna Keller ...",
  "spans": [
    {
      "start": 18, "end": 29, "label": "PERSON", "text": "Anna Keller",
      "start_s": 0.875, "end_s": 1.325
    }
  ],
  "tts_voice":         "en-US-JennyNeural",
  "source":            "synthetic/speech_gen",
  "generator_version": "0.2.0",
  "seed":              42,
  "template_id":       "t01"
}

start_s / end_s are the earliest word-start and latest word-end within
the PII span.  None means no TTS word boundary fell inside the span
(rare; can happen with hard-format entities like 'anna.keller [at] domain').

Requires
--------
    edge-tts >= 6.1  (pip install edge-tts)
    Internet access for the first call; subsequent calls stream from Microsoft
    Azure TTS (free, no key required).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from pathlib import Path

try:
    import edge_tts
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "edge-tts is required for speech generation. "
        "Install it with: pip install edge-tts"
    ) from exc

from piikit import __version__
from piikit.schema import LABELS

SOURCE = "synthetic/speech_gen"

# Voices: one per gender; pick by record index for reproducibility.
VOICES = [
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
]

LOCALE_VOICES = {
    "en": VOICES,
    "de": ["de-DE-KatjaNeural", "de-DE-KillianNeural"],
    "fr": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
    "es": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
}

_100NS = 10_000_000  # 100-nanosecond ticks per second


# ---------------------------------------------------------------------------
# Core alignment logic (pure — no TTS, fully unit-testable)
# ---------------------------------------------------------------------------

def _ticks_to_s(ticks: int) -> float:
    """Convert 100-nanosecond ticks to seconds."""
    return ticks / _100NS


def _align_spans(text_spans: list[dict], cues: list[dict]) -> list[dict]:
    """Map character-offset spans onto audio timestamps.

    edge-tts 7.x returns sentence-level boundaries (SentenceBoundary) rather
    than word-level ones.  We do proportional interpolation within each
    sentence cue to approximate word-level timing.

    For a PII span inside sentence cue [s_start, s_end] with audio window
    [t_start, t_end]:

        span_t_start = t_start + (span_char_start - s_start) / s_len * t_dur
        span_t_end   = t_start + (span_char_end   - s_start) / s_len * t_dur

    Spans that straddle two sentences take the union of both windows.

    Args:
        text_spans:  spans from text_gen, each with ``start``, ``end``,
                     ``label`` and ``text`` keys.
        cues:        sentence cues, each with ``char_start``, ``char_end``,
                     ``t_start``, ``t_end``.

    Returns:
        A new list of span dicts with ``start_s`` and ``end_s`` added.
        Both are ``None`` when no cue overlaps the span.
    """
    result = []
    for span in text_spans:
        s_start, s_end = span["start"], span["end"]

        overlapping = [
            c for c in cues
            if c["char_start"] < s_end and c["char_end"] > s_start
        ]

        if not overlapping:
            result.append({**span, "start_s": None, "end_s": None})
            continue

        times_start, times_end = [], []
        for cue in overlapping:
            c_len = max(cue["char_end"] - cue["char_start"], 1)
            t_dur = cue["t_end"] - cue["t_start"]
            eff_start = max(s_start, cue["char_start"]) - cue["char_start"]
            eff_end = min(s_end, cue["char_end"]) - cue["char_start"]
            times_start.append(cue["t_start"] + eff_start / c_len * t_dur)
            times_end.append(cue["t_start"] + eff_end / c_len * t_dur)

        result.append({
            **span,
            "start_s": round(min(times_start), 4),
            "end_s": round(max(times_end), 4),
        })
    return result


# ---------------------------------------------------------------------------
# TTS synthesis (async; isolated for easy mocking in tests)
# ---------------------------------------------------------------------------

async def _synthesize(text: str, voice: str, out_path: Path) -> list[dict]:
    """Run Edge TTS, write the audio file, return sentence cue dicts.

    Each cue dict has:
        char_start, char_end  – character range in the source text
        t_start, t_end        – audio time window in seconds
        text                  – the sentence text

    edge-tts 7.x emits SentenceBoundary events (not WordBoundary).  We
    locate each sentence back in the original text to get character offsets.
    """
    communicate = edge_tts.Communicate(text, voice)
    sub_maker = edge_tts.SubMaker()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            else:
                sub_maker.feed(chunk)

    # Locate each sentence in the source text sequentially.
    cues: list[dict] = []
    cursor = 0
    for sub in sub_maker.cues:
        t_start = sub.start.total_seconds()
        t_end = sub.end.total_seconds()
        sentence = sub.content
        pos = text.find(sentence, cursor)
        if pos == -1:
            # Partial-match fallback
            for trim in range(len(sentence), 0, -1):
                pos = text.find(sentence[:trim], cursor)
                if pos != -1:
                    sentence = sentence[:trim]
                    break
        if pos == -1:
            continue
        cues.append({
            "char_start": pos,
            "char_end": pos + len(sentence),
            "t_start": t_start,
            "t_end": t_end,
            "text": sentence,
        })
        cursor = pos + len(sentence)
    return cues


# ---------------------------------------------------------------------------
# Per-record and batch generation
# ---------------------------------------------------------------------------

def _pick_voice(record: dict, locale: str | None = None) -> str:
    """Pick a voice deterministically from the record's seed and index."""
    rec_locale = locale or record.get("locale") or "en"
    voice_pool = LOCALE_VOICES.get(rec_locale, VOICES)
    rng = random.Random(f"{record['seed']}-voice-{record['id']}")
    return rng.choice(voice_pool)


def _duration_from_cues(cues: list[dict]) -> float:
    """Estimate audio duration from the last sentence cue's end time."""
    if not cues:
        return 0.0
    return round(max(c["t_end"] for c in cues), 4)


async def _generate_record_async(record: dict, out_dir: Path,
                                  voice: str | None = None,
                                  locale: str | None = None) -> dict:
    voice = voice or _pick_voice(record, locale=locale)
    audio_rel = f"audio/{record['id']}.mp3"
    audio_path = out_dir / audio_rel

    cues = await _synthesize(record["text"], voice, audio_path)
    timed_spans = _align_spans(record.get("spans", []), cues)
    duration_s = _duration_from_cues(cues)

    rec = {
        "id": record["id"],
        "audio": audio_rel,
        "duration_s": duration_s,
        "text": record["text"],
        "spans": timed_spans,
        "tts_voice": voice,
        "source": SOURCE,
        "generator_version": __version__,
        "seed": record["seed"],
        "template_id": record.get("template_id"),
    }
    if "locale" in record:
        rec["locale"] = record["locale"]
    elif locale and locale != "en":
        rec["locale"] = locale
    return rec


def generate_speech_record(record: dict, out_dir: Path,
                            voice: str | None = None,
                            locale: str | None = None) -> dict:
    """Synchronous wrapper around the async generator (convenience function)."""
    return asyncio.run(_generate_record_async(record, out_dir, voice, locale=locale))


async def _generate_batch_async(records: list[dict], out_dir: Path,
                                 voice: str | None = None,
                                 concurrency: int = 4,
                                 locale: str | None = None) -> list[dict]:
    """Generate multiple records with bounded concurrency."""
    sem = asyncio.Semaphore(concurrency)

    async def _one(record):
        async with sem:
            return await _generate_record_async(record, out_dir, voice, locale=locale)

    return await asyncio.gather(*[_one(r) for r in records])


def generate_speech(records: list[dict], out_dir: Path,
                    voice: str | None = None,
                    concurrency: int = 4,
                    locale: str | None = None) -> list[dict]:
    """Generate speech for a list of text records.

    Args:
        records:     records from text_gen (must have ``id``, ``text``,
                     ``spans``, ``seed``).
        out_dir:     directory to write audio files and speech.jsonl.
        voice:       Edge TTS voice name.  If None, one is picked
                     deterministically per record from VOICES.
        concurrency: maximum parallel TTS requests.
        locale:      optional locale ('en', 'de', 'fr', 'es') to select voices.

    Returns:
        List of speech record dicts (same order as ``records``).
    """
    return asyncio.run(_generate_batch_async(records, out_dir, voice, concurrency, locale=locale))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", type=Path, default=Path("data/raw/text.jsonl"),
                        help="source text JSONL from piikit.text_gen")
    parser.add_argument("--n", type=int, default=50,
                        help="number of records to synthesise (default: 50)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed used to choose first n records")
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw/speech"),
                        help="output directory for audio/ and speech.jsonl")
    parser.add_argument("--voice", default=None,
                        help="force a specific Edge TTS voice for all records")
    parser.add_argument("--locale", choices=list(LOCALE_VOICES.keys()), default=None,
                        help="locale for speech voices ('en', 'de', 'fr', 'es')")
    parser.add_argument("--concurrency", type=int, default=4,
                        help="parallel TTS requests (default: 4)")
    args = parser.parse_args()

    all_records = _read_jsonl(args.text)
    rng = random.Random(args.seed)
    records = rng.sample(all_records, min(args.n, len(all_records)))

    print(f"Synthesising {len(records)} records → {args.out_dir}")
    speech_records = generate_speech(records, args.out_dir,
                                     voice=args.voice,
                                     concurrency=args.concurrency,
                                     locale=args.locale)
    _write_jsonl(speech_records, args.out_dir / "speech.jsonl")

    n_aligned = sum(
        1 for r in speech_records
        for s in r["spans"] if s.get("start_s") is not None
    )
    n_total = sum(len(r["spans"]) for r in speech_records)
    n_missing = n_total - n_aligned
    print(f"Wrote {len(speech_records)} records to {args.out_dir}/speech.jsonl")
    print(f"Aligned {n_aligned}/{n_total} PII spans "
          f"({n_missing} unaligned — hard-format entities or TTS tokenisation differences)")


if __name__ == "__main__":
    main()
