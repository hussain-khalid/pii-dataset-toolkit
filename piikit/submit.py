"""One-command submission: score a predictions file and add it to the leaderboard.

Usage:
    python -m piikit.submit --task text \\
        --pred build/preds/my_system.jsonl \\
        --name "My GPT-4 System" \\
        [--label-set presidio] \\
        [--bench benchmark] \\
        [--html]

This is a thin wrapper around piikit.score + piikit.leaderboard (+ piikit.leaderboard_html).
It validates the predictions, scores them against the frozen benchmark, saves the result
JSON, regenerates LEADERBOARD.md, and optionally regenerates the HTML leaderboard.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def submit(
    task: str,
    pred: Path,
    name: str,
    bench: Path,
    label_set: str,
    with_html: bool,
) -> None:
    # 1. Score
    score_cmd = [
        sys.executable, "-m", "piikit.score",
        task,
        "--pred", str(pred),
        "--name", name,
        "--bench", str(bench),
        "--save",
    ]
    if label_set:
        score_cmd += ["--label-set", label_set]

    print("─" * 60)
    print(f"Scoring   : {pred}")
    print(f"System    : {name}")
    print(f"Task      : {task}")
    if label_set:
        print(f"Label set : {label_set}")
    print("─" * 60)

    result = subprocess.run(score_cmd, check=False)
    if result.returncode != 0:
        sys.exit(f"\nScoring failed (exit {result.returncode}). Fix the errors above and retry.")

    # 2. Regenerate markdown leaderboard
    lb_cmd = [sys.executable, "-m", "piikit.leaderboard", "--bench", str(bench)]
    subprocess.run(lb_cmd, check=True)

    # 3. Optionally regenerate HTML leaderboard
    if with_html:
        html_cmd = [sys.executable, "-m", "piikit.leaderboard_html",
                    "--bench", str(bench), "--out", "docs/leaderboard.html"]
        subprocess.run(html_cmd, check=True)

    print("\n✓ Submission complete. Your result has been added to the leaderboard.")
    print(f"  Markdown : {bench / 'LEADERBOARD.md'}")
    if with_html:
        print("  HTML     : docs/leaderboard.html")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["text", "docs"], required=True,
                        help="Benchmark task: text (span detection) or docs (field detection).")
    parser.add_argument("--pred", type=Path, required=True,
                        help="Path to your predictions JSONL file.")
    parser.add_argument("--name", required=True,
                        help="Display name for your system on the leaderboard.")
    parser.add_argument("--bench", type=Path, default=Path("benchmark"),
                        help="Path to the benchmark directory (default: benchmark).")
    parser.add_argument("--label-set", default="none",
                        choices=["none", "presidio", "conll"],
                        help="Label mapping to apply before scoring (default: none).")
    parser.add_argument("--html", action="store_true",
                        help="Also regenerate docs/leaderboard.html.")
    args = parser.parse_args()

    submit(args.task, args.pred, args.name, args.bench, args.label_set, args.html)


if __name__ == "__main__":
    main()
