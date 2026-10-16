"""Freeze the benchmark: split a release's test data into inputs and gold labels.

Usage:
    python -m piikit.freeze build --release data/release/v0.1.0 --out benchmark
    python -m piikit.freeze verify benchmark

The frozen benchmark contains, for the test split only:
    text/inputs.jsonl   id, text                      (what a system sees)
    text/gold.jsonl     id, spans (start, end, label)
    docs/inputs.jsonl   id, image, width, height
    docs/gold.jsonl     id, fields (label, bbox)
    docs/images/*.png
    FROZEN.json         SHA-256 of every file and one combined frozen id

Scoring refuses to run if any frozen file no longer matches FROZEN.json.
Building refuses to replace an existing frozen benchmark unless --overwrite is given.
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from piikit.dedup import file_sha256


def read_jsonl(path: Path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_jsonl(records, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def freeze(release_dir, out_dir, overwrite: bool = False) -> dict:
    release_dir, out_dir = Path(release_dir), Path(out_dir)
    if (out_dir / "FROZEN.json").exists():
        if not overwrite:
            raise FileExistsError(f"{out_dir} is already frozen; pass overwrite=True to replace it")
        for sub in ("text", "docs"):
            shutil.rmtree(out_dir / sub, ignore_errors=True)

    manifest = json.loads((release_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    release_hashes = {e["path"]: e["sha256"] for e in manifest["files"]
                      if e["path"] in ("text/test.jsonl", "docs/test.jsonl")}

    text = read_jsonl(release_dir / "text" / "test.jsonl")
    docs = read_jsonl(release_dir / "docs" / "test.jsonl")

    _write_jsonl([{"id": r["id"], "text": r["text"]} for r in text], out_dir / "text" / "inputs.jsonl")
    _write_jsonl([{"id": r["id"],
                   "spans": [{"start": s["start"], "end": s["end"], "label": s["label"]}
                             for s in r["spans"]]} for r in text], out_dir / "text" / "gold.jsonl")
    _write_jsonl([{"id": r["id"], "image": r["image"], "width": r["width"], "height": r["height"]}
                  for r in docs], out_dir / "docs" / "inputs.jsonl")
    _write_jsonl([{"id": r["id"],
                   "fields": [{"label": f["label"], "bbox": f["bbox"]} for f in r["fields"]]}
                  for r in docs], out_dir / "docs" / "gold.jsonl")
    for r in docs:
        target = out_dir / "docs" / r["image"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(release_dir / "docs" / r["image"], target)

    files = {}
    for sub in ("text", "docs"):
        for path in sorted(p for p in (out_dir / sub).rglob("*") if p.is_file()):
            files[path.relative_to(out_dir).as_posix()] = file_sha256(path)
    frozen_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()

    frozen = {
        "release_version": manifest["version"],
        "release_test_files": release_hashes,
        "records": {"text": len(text), "docs": len(docs)},
        "files": files,
        "frozen_id": frozen_id,
    }
    (out_dir / "FROZEN.json").write_text(
        json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frozen


def verify_frozen(bench_dir) -> list:
    """Return a list of problems (empty if the benchmark is exactly as frozen)."""
    bench_dir = Path(bench_dir)
    path = bench_dir / "FROZEN.json"
    if not path.exists():
        return ["FROZEN.json is missing: run `python -m piikit.freeze build` first"]
    frozen = json.loads(path.read_text(encoding="utf-8"))

    errors = []
    for rel, sha in frozen["files"].items():
        file = bench_dir / rel
        if not file.exists():
            errors.append(f"{rel}: frozen file is missing")
        elif file_sha256(file) != sha:
            errors.append(f"{rel}: contents changed since the benchmark was frozen")
    expected = hashlib.sha256(json.dumps(frozen["files"], sort_keys=True).encode()).hexdigest()
    if expected != frozen["frozen_id"]:
        errors.append("FROZEN.json: frozen_id does not match its file list")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--release", type=Path, required=True)
    build.add_argument("--out", type=Path, default=Path("benchmark"))
    build.add_argument("--overwrite", action="store_true")
    check = sub.add_parser("verify")
    check.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "build":
        frozen = freeze(args.release, args.out, args.overwrite)
        print(f"Frozen {frozen['records']['text']} text and {frozen['records']['docs']} document "
              f"test records from release {frozen['release_version']}")
        print(f"frozen_id: {frozen['frozen_id']}")
    else:
        errors = verify_frozen(args.path)
        if errors:
            print(f"FAILED with {len(errors)} problem(s):")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        print("OK: benchmark matches FROZEN.json.")


if __name__ == "__main__":
    main()