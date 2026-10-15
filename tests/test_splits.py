from collections import Counter

from piikit.splits import SPLITS, assign_split


def test_assignment_is_deterministic():
    assert assign_split("txt-000001", 42) == assign_split("txt-000001", 42)


def test_assignment_depends_on_seed():
    names_a = [assign_split(f"txt-{i:06d}", 1) for i in range(200)]
    names_b = [assign_split(f"txt-{i:06d}", 2) for i in range(200)]
    assert names_a != names_b


def test_ratios_are_roughly_respected():
    counts = Counter(assign_split(f"txt-{i:06d}", 42) for i in range(10000))
    assert set(counts) == set(SPLITS)
    assert 7800 <= counts["train"] <= 8200
    assert 800 <= counts["validation"] <= 1200
    assert 800 <= counts["test"] <= 1200


def test_bad_ratios_are_rejected():
    try:
        assign_split("x", 1, ratios=(50, 50, 50))
    except ValueError:
        return
    raise AssertionError("expected ValueError")