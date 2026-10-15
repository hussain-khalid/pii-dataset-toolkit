"""Exact and near-duplicate removal for the text and document datasets.

Text: records are exact duplicates if their normalised text matches (lower-case,
whitespace collapsed). Near-duplicates are caught with Jaccard similarity over
word 3-gram shingles; an inverted index means each record is only compared with
records that share at least one shingle.

Documents: exact duplicates have the same type and the same set of
(label, text) fields, or byte-identical image files.

In every case the first occurrence is kept, so results are deterministic.
"""

import hashlib
import re
from collections import defaultdict
from pathlib import Path


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def shingles(text: str, n: int = 3) -> set:
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) <= n:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def dedup_text(records, threshold: float = 0.8):
    """Return (kept_records, removed) where removed explains every dropped record."""
    kept, removed = [], []
    exact_seen = {}                 # normalised text -> id of the kept record
    kept_shingles = []              # shingle set per kept record
    index = defaultdict(list)       # shingle -> positions in kept

    for record in records:
        key = normalize_text(record["text"])
        if key in exact_seen:
            removed.append({"id": record["id"], "reason": "exact_duplicate",
                            "duplicate_of": exact_seen[key]})
            continue

        sh = shingles(record["text"])
        candidates = sorted({pos for g in sh for pos in index[g]})
        match, best = None, 0.0
        for pos in candidates:
            score = jaccard(sh, kept_shingles[pos])
            if score >= threshold and score > best:
                match, best = pos, score
        if match is not None:
            removed.append({"id": record["id"], "reason": "near_duplicate",
                            "duplicate_of": kept[match]["id"], "jaccard": round(best, 4)})
            continue

        exact_seen[key] = record["id"]
        kept_shingles.append(sh)
        for g in sh:
            index[g].append(len(kept))
        kept.append(record)

    return kept, removed


def doc_signature(record: dict):
    return (record["doc_type"],
            tuple(sorted((f["label"], f["text"]) for f in record["fields"])))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dedup_docs(records, base_dir: Path):
    """Return (kept_records, removed). Drops repeated field sets and identical images."""
    kept, removed = [], []
    signatures, image_hashes = {}, {}

    for record in records:
        sig = doc_signature(record)
        if sig in signatures:
            removed.append({"id": record["id"], "reason": "exact_duplicate",
                            "duplicate_of": signatures[sig]})
            continue
        digest = file_sha256(Path(base_dir) / record["image"])
        if digest in image_hashes:
            removed.append({"id": record["id"], "reason": "identical_image",
                            "duplicate_of": image_hashes[digest]})
            continue
        signatures[sig] = record["id"]
        image_hashes[digest] = record["id"]
        kept.append(record)

    return kept, removed