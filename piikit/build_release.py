"""Merge, deduplicate, split and document the text and document datasets.

Usage:
    python -m piikit.build_release --text data/raw/text.jsonl \\
        --docs data/raw/docs/docs.jsonl --out-dir data/release/v0.1.0 \\
        --seed 42 --version 0.1.0

Output layout under --out-dir:
    text/{train,validation,test}.jsonl
    docs/{train,validation,test}.jsonl, docs/images/*.png
    dedup_report.json, PROVENANCE.json, MANIFEST.json, DATASET_CARD.md

Nothing in the output depends on the clock or the machine, so the same inputs
and parameters always produce byte-identical files.
"""

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from piikit import __version__
from piikit.card import render_card
from piikit.dedup import dedup_docs, dedup_text, file_sha256
from piikit.splits import DEFAULT_RATIOS, SPLITS, assign_split

LICENSE = "CC0-1.0"


def read_jsonl(path: Path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(records, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def annotate(records, modality: str, input_path: Path, input_sha: str, line_of: dict):
    out = []
    for record in records:
        record = dict(record)
        record["modality"] = modality
        record["provenance"] = {
            "generator": record.get("source"),
            "input_file": Path(input_path).name,
            "input_line": line_of[record["id"]],
            "input_sha256": input_sha,
            "synthetic": True,
            "license": LICENSE,
        }
        out.append(record)
    return out


def split_records(records, seed: int, ratios):
    buckets = {s: [] for s in SPLITS}
    for record in records:
        buckets[assign_split(record["id"], seed, ratios)].append(record)
    return buckets


def split_stats(buckets, modality: str):
    stats = {}
    for name in SPLITS:
        labels, doc_types = Counter(), Counter()
        for record in buckets[name]:
            if modality == "text":
                labels.update(s["label"] for s in record["spans"])
            else:
                labels.update(f["label"] for f in record["fields"])
                doc_types[record["doc_type"]] += 1
        stats[name] = {"records": len(buckets[name]), "labels": dict(labels),
                       "doc_types": dict(doc_types)}
    return stats


def build_release(text_path, docs_path, out_dir, seed=42, version="0.1.0",
                  near_dup_threshold=0.8, ratios=DEFAULT_RATIOS, overwrite=False):
    text_path, docs_path, out_dir = Path(text_path), Path(docs_path), Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"{out_dir} already exists; pass overwrite=True to replace it")
        shutil.rmtree(out_dir)

    text_in, docs_in = read_jsonl(text_path), read_jsonl(docs_path)
    text_line = {r["id"]: i for i, r in enumerate(text_in, start=1)}
    docs_line = {r["id"]: i for i, r in enumerate(docs_in, start=1)}
    text_sha, docs_sha = file_sha256(text_path), file_sha256(docs_path)

    text_kept, text_removed = dedup_text(text_in, near_dup_threshold)
    docs_kept, docs_removed = dedup_docs(docs_in, docs_path.parent)

    text_kept = annotate(text_kept, "text", text_path, text_sha, text_line)
    docs_kept = annotate(docs_kept, "document", docs_path, docs_sha, docs_line)

    text_buckets = split_records(text_kept, seed, ratios)
    docs_buckets = split_records(docs_kept, seed, ratios)

    for name in SPLITS:
        write_jsonl(text_buckets[name], out_dir / "text" / f"{name}.jsonl")
        write_jsonl(docs_buckets[name], out_dir / "docs" / f"{name}.jsonl")
    for record in docs_kept:
        target = out_dir / "docs" / record["image"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(docs_path.parent / record["image"], target)

    stats = {
        "parameters": {"seed": seed, "version": version, "ratios": list(ratios),
                       "near_dup_threshold": near_dup_threshold},
        "license": LICENSE,
        "inputs": {
            "text": {"name": text_path.name, "sha256": text_sha, "records": len(text_in)},
            "docs": {"name": docs_path.name, "sha256": docs_sha, "records": len(docs_in)},
        },
        "text": {"input": len(text_in), "kept": len(text_kept),
                 "removed": dict(Counter(r["reason"] for r in text_removed)),
                 "per_split": split_stats(text_buckets, "text")},
        "docs": {"input": len(docs_in), "kept": len(docs_kept),
                 "removed": dict(Counter(r["reason"] for r in docs_removed)),
                 "per_split": split_stats(docs_buckets, "document")},
    }

    write_json({"parameters": stats["parameters"],
                "text_removed": text_removed, "docs_removed": docs_removed},
               out_dir / "dedup_report.json")
    write_json({"tool": "piikit", "tool_version": __version__, "license": LICENSE,
                "inputs": stats["inputs"], "parameters": stats["parameters"]},
               out_dir / "PROVENANCE.json")
    (out_dir / "DATASET_CARD.md").write_text(render_card(stats), encoding="utf-8")

    manifest_files = []
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file()):
        entry = {"path": path.relative_to(out_dir).as_posix(),
                 "sha256": file_sha256(path), "bytes": path.stat().st_size}
        if path.suffix == ".jsonl":
            entry["records"] = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        manifest_files.append(entry)
    write_json({"version": version, "files": manifest_files}, out_dir / "MANIFEST.json")
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--docs", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--near-dup-threshold", type=float, default=0.8)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    stats = build_release(args.text, args.docs, args.out_dir, args.seed, args.version,
                          args.near_dup_threshold, overwrite=args.overwrite)
    for key in ("text", "docs"):
        s = stats[key]
        removed = sum(s["removed"].values())
        print(f"{key}: {s['input']} in, {removed} duplicates removed, {s['kept']} kept "
              + "(" + ", ".join(f"{n} {s['per_split'][n]['records']}" for n in SPLITS) + ")")
    print(f"Release written to {args.out_dir}")


if __name__ == "__main__":
    main()