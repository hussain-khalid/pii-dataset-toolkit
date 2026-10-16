"""Build LEADERBOARD.md from the result files in benchmark/results/.

Usage:
    python -m piikit.leaderboard --bench benchmark
"""

import argparse
import json
from pathlib import Path

PRIMARY = {"text": "strict", "docs": "iou_0.5"}


def load_results(bench_dir: Path):
    results = []
    for path in sorted((Path(bench_dir) / "results").glob("*.json")):
        results.append(json.loads(path.read_text(encoding="utf-8")))
    return results


def _cell(m):
    lo, hi = m["f1_ci95"]
    return f"{m['f1']:.3f} ({lo:.3f} to {hi:.3f})"


def render(results: list, frozen_id: str) -> str:
    lines = ["# Leaderboard", "",
             f"Frozen benchmark id: `{frozen_id[:16]}`. Systems are ranked by F1; the interval is a "
             "95% bootstrap over test records. Results from a different frozen id are not shown.", ""]

    text = [r for r in results if r["task"] == "text" and r["frozen_id"] == frozen_id]
    if text:
        text.sort(key=lambda r: (-r["metrics"]["strict"]["f1"], r["name"], r["label_set"]))
        lines += ["## Text PII detection", "",
                  "| Rank | System | Label set | Strict F1 (95% CI) | Relaxed F1 | Precision | Recall | False alarms on no-PII records |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for i, r in enumerate(text, start=1):
            s, x = r["metrics"]["strict"], r["metrics"]["relaxed"]
            fa = r.get("false_alarm_rate_on_clean_records")
            lines.append(f"| {i} | {r['name']} | {r['label_set']} | {_cell(s)} | {x['f1']:.3f} | "
                         f"{s['precision']:.3f} | {s['recall']:.3f} | "
                         f"{'n/a' if fa is None else f'{fa:.3f}'} |")
        lines.append("")

    docs = [r for r in results if r["task"] == "docs" and r["frozen_id"] == frozen_id]
    if docs:
        docs.sort(key=lambda r: (-r["metrics"]["iou_0.5"]["f1"], r["name"], r["label_set"]))
        lines += ["## Document field detection (box IoU of at least 0.5)", "",
                  "| Rank | System | Label set | F1 (95% CI) | Precision | Recall |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for i, r in enumerate(docs, start=1):
            m = r["metrics"]["iou_0.5"]
            lines.append(f"| {i} | {r['name']} | {r['label_set']} | {_cell(m)} | "
                         f"{m['precision']:.3f} | {m['recall']:.3f} |")
        lines.append("")

    if not text and not docs:
        lines.append("No results yet. Score a system with `python -m piikit.score ... --save`.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, default=Path("benchmark"))
    args = parser.parse_args()
    frozen = json.loads((args.bench / "FROZEN.json").read_text(encoding="utf-8"))
    out = args.bench / "LEADERBOARD.md"
    out.write_text(render(load_results(args.bench), frozen["frozen_id"]), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()