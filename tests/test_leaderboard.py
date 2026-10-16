from piikit.leaderboard import render


def text_result(name, f1, frozen="abc" * 6, label_set="none"):
    m = {"precision": f1, "recall": f1, "f1": f1, "f1_ci95": [f1 - 0.05, min(1.0, f1 + 0.05)]}
    return {"name": name, "task": "text", "label_set": label_set, "frozen_id": frozen,
            "metrics": {"strict": m, "relaxed": m},
            "false_alarm_rate_on_clean_records": 0.0}


def test_systems_are_ranked_by_strict_f1():
    frozen = "abc" * 6
    md = render([text_result("weak", 0.2), text_result("strong", 0.9)], frozen)
    assert md.index("strong") < md.index("weak")
    assert "| 1 | strong |" in md and "| 2 | weak |" in md


def test_results_from_another_frozen_benchmark_are_ignored():
    frozen = "abc" * 6
    md = render([text_result("current", 0.5), text_result("stale", 0.9, frozen="other")], frozen)
    assert "current" in md and "stale" not in md


def test_empty_leaderboard_explains_what_to_do():
    assert "No results yet" in render([], "abc" * 6)