"""Deterministic train / validation / test assignment.

A record's split depends only on its id and the seed, so adding or removing other
records never moves it, and the same input always gives the same split.
"""

import hashlib

SPLITS = ("train", "validation", "test")
DEFAULT_RATIOS = (80, 10, 10)  # percent; must sum to 100


def assign_split(record_id: str, seed: int, ratios=DEFAULT_RATIOS) -> str:
    if sum(ratios) != 100 or len(ratios) != len(SPLITS):
        raise ValueError("ratios must be three percentages that sum to 100")
    bucket = int(hashlib.sha256(f"{seed}:{record_id}".encode()).hexdigest(), 16) % 100
    upper = 0
    for name, share in zip(SPLITS, ratios):
        upper += share
        if bucket < upper:
            return name
    return SPLITS[-1]