"""Score predictions against the frozen benchmark.

Usage:
    python -m piikit.score text --pred preds.jsonl --name my-system
    python -m piikit.score docs --pred preds.jsonl --name my-system --save
    python -m piikit.score text --pred preds.jsonl --name my-system --label-set presidio

Prediction formats (one JSON object per line, one line for EVERY benchmark id):
    text: {"id": "...", "spans":  [{"start": 0, "end": 5, "label": "PERSON"}]}
    docs: {"id": "...", "fields": [{"label": "PERSON", "bbox": [x0, y0, x1, y1]}]}

Text metrics: "strict" needs the exact span and label; "relaxed" accepts the same label
with character-overlap (Jaccard) of at least 0.5. Document metrics match boxes of the same
label at IoU of at least 0.5. All matching is one-to-one. Precision, recall and F1 are
micro-averaged. The 95% interval is a bootstrap over records (1,000 resamples, fixed seed).

Scoring refuses to run if the frozen benchmark files have changed.
"""

import argparse
import json
import random
import sys
from pathlib import Path

from piikit.freeze import read_jsonl, verify_frozen
from piikit.label_map import LABEL_SETS, map_items
from piikit.schema import LABELS
from piikit.validate_docs import iou

BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 42


def prf(tp: int, fp: int, fn: int):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


# ---------------------------------------------------------------- matching

def span_overlap(a, b) -> float:
    inter = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    union = (a["end"] - a["start"]) + (b["end"] - b["start"]) - inter
    return inter / union if union else 0.0


def match_spans(gold, pred, relaxed: bool):
    """Return {label: [tp, fp, fn]} for one record."""
    counts = {}

    def bump(label, index):
        counts.setdefault(label, [0, 0, 0])[index] += 1

    unmatched = list(range(len(gold)))
    for p in sorted(pred, key=lambda s: (s["start"], s["end"], s["label"])):
        best, best_score = None, 0.0
        for i in unmatched:
            g = gold[i]
            if g["label"] != p["label"]:
                continue
            if relaxed:
                score = span_overlap(g, p)
                ok = score >= 0.5
            else:
                ok = (g["start"], g["end"]) == (p["start"], p["end"])
                score = 1.0
            if ok and score > best_score:
                best, best_score = i, score
        if best is None:
            bump(p["label"], 1)
        else:
            unmatched.remove(best)
            bump(p["label"], 0)
    for i in unmatched:
        bump(gold[i]["label"], 2)
    return counts


def match_boxes(gold, pred, threshold: float = 0.5):
    counts = {}

    def bump(label, index):
        counts.setdefault(label, [0, 0, 0])[index] += 1

    pairs = []
    for pi, p in enumerate(pred):
        for gi, g in enumerate(gold):
            if p["label"] == g["label"]:
                score = iou(p["bbox"], g["bbox"])
                if score >= threshold:
                    pairs.append((-score, pi, gi))
    used_p, used_g = set(), set()
    for _, pi, gi in sorted(pairs):
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        bump(pred[pi]["label"], 0)
    for pi, p in enumerate(pred):
        if pi not in used_p:
            bump(p["label"], 1)
    for gi, g in enumerate(gold):
        if gi not in used_g:
            bump(g["label"], 2)
    return counts


# ---------------------------------------------------------------- aggregation

def summarise(per_record: list) -> dict:
    """per_record: list of {label: [tp, fp, fn]}. Returns micro metrics, per-label and CI."""
    labels = sorted({l for rec in per_record for l in rec})
    per_label = {}
    for label in labels:
        tp = sum(rec.get(label, [0, 0, 0])[0] for rec in per_record)
        fp = sum(rec.get(label, [0, 0, 0])[1] for rec in per_record)
        fn = sum(rec.get(label, [0, 0, 0])[2] for rec in per_record)
        p, r, f = prf(tp, fp, fn)
        per_label[label] = {"precision": round(p, 4), "recall": round(r, 4),
                            "f1": round(f, 4), "support": tp + fn}

    totals = [tuple(sum(c[i] for c in rec.values()) for i in range(3)) for rec in per_record]
    tp, fp, fn = (sum(t[i] for t in totals) for i in range(3))
    p, r, f = prf(tp, fp, fn)

    rng = random.Random(BOOTSTRAP_SEED)
    scores = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [totals[rng.randrange(len(totals))] for _ in totals]
        scores.append(prf(*(sum(t[i] for t in sample) for i in range(3)))[2])
    scores.sort()
    ci = [round(scores[int(0.025 * len(scores))], 4), round(scores[int(0.975 * len(scores)) - 1], 4)]

    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "f1_ci95": ci, "tp": tp, "fp": fp, "fn": fn, "per_label": per_label}


# ---------------------------------------------------------------- input checks

def _by_id(records, errors, what):
    out = {}
    for r in records:
        if r["id"] in out:
            errors.append(f"{what}: duplicate id {r['id']}")
        out[r["id"]] = r
    return out


def check_ids(preds_by_id, gold_ids, errors):
    missing = sorted(set(gold_ids) - set(preds_by_id))
    extra = sorted(set(preds_by_id) - set(gold_ids))
    if missing:
        errors.append(f"predictions missing for {len(missing)} ids, e.g. {missing[:3]}")
    if extra:
        errors.append(f"predictions contain {len(extra)} unknown ids, e.g. {extra[:3]}")


def check_text_preds(preds, texts, errors):
    for rid, rec in preds.items():
        if rid not in texts:
            continue
        for s in rec.get("spans", []):
            if s.get("label") not in LABELS:
                errors.append(f"{rid}: unknown label {s.get('label')!r}")
            elif not (isinstance(s.get("start"), int) and isinstance(s.get("end"), int)
                      and 0 <= s["start"] < s["end"] <= len(texts[rid])):
                errors.append(f"{rid}: invalid span offsets {s.get('start')}-{s.get('end')}")


def check_doc_preds(preds, sizes, errors):
    for rid, rec in preds.items():
        if rid not in sizes:
            continue
        w, h = sizes[rid]
        for f in rec.get("fields", []):
            box = f.get("bbox")
            if f.get("label") not in LABELS:
                errors.append(f"{rid}: unknown label {f.get('label')!r}")
            elif not (isinstance(box, list) and len(box) == 4
                      and all(isinstance(v, (int, float)) for v in box)
                      and 0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h):
                errors.append(f"{rid}: invalid bbox {box}")


# ---------------------------------------------------------------- scoring

def score_text(bench_dir, pred_path, label_set="none") -> dict:
    bench_dir = Path(bench_dir)
    errors = verify_frozen(bench_dir)
    if errors:
        raise ValueError("frozen benchmark check failed: " + "; ".join(errors))

    inputs = _by_id(read_jsonl(bench_dir / "text" / "inputs.jsonl"), errors, "inputs")
    gold = _by_id(read_jsonl(bench_dir / "text" / "gold.jsonl"), errors, "gold")
    preds = _by_id(read_jsonl(pred_path), errors, "predictions")
    check_ids(preds, gold, errors)
    check_text_preds(preds, {k: v["text"] for k, v in inputs.items()}, errors)
    if errors:
        raise ValueError("invalid predictions: " + "; ".join(errors[:10]))

    strict, relaxed, clean, false_alarms = [], [], 0, 0
    for rid in sorted(gold):
        g = map_items(gold[rid]["spans"], label_set)
        p = map_items(preds[rid].get("spans", []), label_set)
        strict.append(match_spans(g, p, relaxed=False))
        relaxed.append(match_spans(g, p, relaxed=True))
        if not g:
            clean += 1
            false_alarms += 1 if p else 0

    frozen = json.loads((bench_dir / "FROZEN.json").read_text(encoding="utf-8"))
    return {
        "task": "text", "label_set": label_set, "frozen_id": frozen["frozen_id"],
        "records": len(gold),
        "metrics": {"strict": summarise(strict), "relaxed": summarise(relaxed)},
        "clean_records": clean,
        "false_alarm_rate_on_clean_records": round(false_alarms / clean, 4) if clean else None,
    }


def score_docs(bench_dir, pred_path, label_set="none", iou_threshold=0.5) -> dict:
    bench_dir = Path(bench_dir)
    errors = verify_frozen(bench_dir)
    if errors:
        raise ValueError("frozen benchmark check failed: " + "; ".join(errors))

    inputs = _by_id(read_jsonl(bench_dir / "docs" / "inputs.jsonl"), errors, "inputs")
    gold = _by_id(read_jsonl(bench_dir / "docs" / "gold.jsonl"), errors, "gold")
    preds = _by_id(read_jsonl(pred_path), errors, "predictions")
    check_ids(preds, gold, errors)
    check_doc_preds(preds, {k: (v["width"], v["height"]) for k, v in inputs.items()}, errors)
    if errors:
        raise ValueError("invalid predictions: " + "; ".join(errors[:10]))

    per_record = []
    for rid in sorted(gold):
        g = map_items(gold[rid]["fields"], label_set)
        p = map_items(preds[rid].get("fields", []), label_set)
        per_record.append(match_boxes(g, p, iou_threshold))

    frozen = json.loads((bench_dir / "FROZEN.json").read_text(encoding="utf-8"))
    return {
        "task": "docs", "label_set": label_set, "frozen_id": frozen["frozen_id"],
        "records": len(gold),
        "metrics": {f"iou_{iou_threshold}": summarise(per_record)},
    }


def save_result(bench_dir, name: str, result: dict) -> Path:
    result = {"name": name, **result}
    out = Path(bench_dir) / "results" / f"{result['task']}__{name}__{result['label_set']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def print_result(name: str, result: dict):
    print(f"{name} | task={result['task']} | label set={result['label_set']} "
          f"| {result['records']} records | frozen_id {result['frozen_id'][:12]}")
    for mode, m in result["metrics"].items():
        lo, hi = m["f1_ci95"]
        print(f"  {mode}: precision {m['precision']:.3f}  recall {m['recall']:.3f}  "
              f"F1 {m['f1']:.3f}  (95% CI {lo:.3f} to {hi:.3f})")
        for label, s in m["per_label"].items():
            print(f"      {label:<14} P {s['precision']:.3f}  R {s['recall']:.3f}  "
                  f"F1 {s['f1']:.3f}  (n={s['support']})")
    if result.get("false_alarm_rate_on_clean_records") is not None:
        print(f"  records with no PII that got a false alarm: "
              f"{result['false_alarm_rate_on_clean_records']:.3f} of {result['clean_records']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", choices=["text", "docs"])
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--bench", type=Path, default=Path("benchmark"))
    parser.add_argument("--label-set", choices=sorted(LABEL_SETS), default="none")
    parser.add_argument("--save", action="store_true", help="write the result to benchmark/results/")
    args = parser.parse_args()

    try:
        scorer = score_text if args.task == "text" else score_docs
        result = scorer(args.bench, args.pred, args.label_set)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print_result(args.name, result)
    if args.save:
        print(f"Saved {save_result(args.bench, args.name, result)}")


if __name__ == "__main__":
    main()