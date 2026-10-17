"""Push a built release to the Hugging Face Hub as a public dataset.

Usage:
    python -m piikit.push_hub --release data/release/v0.2.0 \\
        --repo your-username/pii-dataset \\
        --token $HF_TOKEN

The release directory must have been built with piikit.build_release and validated
with piikit.validate_release before pushing.

What is uploaded
----------------
  text/train.jsonl, text/validation.jsonl, text/test.jsonl  → DatasetDict split "text"
  docs/*.jsonl  (annotation files only, images are NOT pushed)  → split "docs"

Images are large binary files. If you want to push them, add --with-images and the
script will also upload the images folder using the Hub's upload_folder API.

Requires
--------
    pip install datasets huggingface_hub
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def push(release_dir: Path, repo_id: str, token: str | None, with_images: bool, private: bool) -> None:
    try:
        from datasets import Dataset, DatasetDict
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("datasets and huggingface_hub are required: pip install datasets huggingface_hub")

    release_dir = Path(release_dir)
    if not release_dir.exists():
        sys.exit(f"Release directory not found: {release_dir}")
    manifest_path = release_dir / "MANIFEST.json"
    if not manifest_path.exists():
        sys.exit(f"No MANIFEST.json in {release_dir} — run piikit.build_release first.")

    api = HfApi(token=token)

    # ---- Text splits --------------------------------------------------------
    text_dir = release_dir / "text"
    text_splits = {}
    for split in ("train", "validation", "test"):
        p = text_dir / f"{split}.jsonl"
        if p.exists():
            text_splits[split] = Dataset.from_list(_load_jsonl(p))

    # ---- Docs splits (annotations only) ------------------------------------
    docs_dir = release_dir / "docs"
    docs_splits = {}
    for split in ("train", "validation", "test"):
        p = docs_dir / f"{split}.jsonl"
        if p.exists():
            records = _load_jsonl(p)
            # Flatten fields list to JSON string so HF Dataset can handle it
            for r in records:
                r["fields"] = json.dumps(r.get("fields", []))
            docs_splits[split] = Dataset.from_list(records)

    dataset = DatasetDict({
        **{f"text_{k}": v for k, v in text_splits.items()},
        **{f"docs_{k}": v for k, v in docs_splits.items()},
    })

    print(f"Pushing dataset to  https://huggingface.co/datasets/{repo_id} ...")
    dataset.push_to_hub(repo_id, token=token, private=private)
    print("Dataset pushed ✓")

    # ---- Optional: upload images -------------------------------------------
    if with_images:
        images_dir = docs_dir / "images"
        if images_dir.exists():
            print(f"Uploading images from {images_dir} ...")
            api.upload_folder(
                folder_path=str(images_dir),
                repo_id=repo_id,
                repo_type="dataset",
                path_in_repo="docs/images",
                token=token,
            )
            print("Images uploaded ✓")
        else:
            print(f"Warning: --with-images requested but {images_dir} not found, skipping.")

    # ---- Upload dataset card -------------------------------------------------
    card_path = release_dir / "DATASET_CARD.md"
    if card_path.exists():
        print("Uploading dataset card (README.md) ...")
        api.upload_file(
            path_or_fileobj=str(card_path),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
        )
        print("Dataset card uploaded ✓")

    print(f"\nDone. View at: https://huggingface.co/datasets/{repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", type=Path, required=True,
                        help="Path to the built release directory (e.g. data/release/v0.2.0).")
    parser.add_argument("--repo", required=True,
                        help="HuggingFace Hub repo id, e.g. your-username/pii-dataset.")
    parser.add_argument("--token", default=None,
                        help="HuggingFace token. Falls back to HF_TOKEN env var or cached login.")
    parser.add_argument("--with-images", action="store_true",
                        help="Also upload document PNG images (large).")
    parser.add_argument("--private", action="store_true",
                        help="Create/push to a private repository.")
    args = parser.parse_args()

    import os
    token = args.token or os.environ.get("HF_TOKEN")
    push(args.release, args.repo, token, args.with_images, args.private)


if __name__ == "__main__":
    main()
