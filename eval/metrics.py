"""Small statistics helpers for the eval: rank metrics with bootstrap confidence intervals.

With 50-90 questions a difference of 0.02 is mostly noise; every headline number is therefore shown with
a 95 % percentile bootstrap interval (resampling questions with replacement).
"""

import random
from collections.abc import Callable, Sequence

Rank = int | None  # position of the first correct hit, None = not found in the top-k


def mrr(ranks: Sequence[Rank]) -> float:
    return sum(1 / r for r in ranks if r) / len(ranks)


def recall_at(k: int) -> Callable[[Sequence[Rank]], float]:
    return lambda ranks: sum(r is not None and r <= k for r in ranks) / len(ranks)


def fraction(values: Sequence[bool | None]) -> float:
    """Share of True among the values (None counts as False)."""
    return sum(bool(v) for v in values) / len(values)


def bootstrap(values: Sequence, stat: Callable[[Sequence], float], n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """(point estimate, lower, upper) of the 95 % interval."""
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    stats = sorted(stat([values[rng.randrange(len(values))] for _ in values]) for _ in range(n))
    return stat(values), stats[int(0.025 * n)], stats[int(0.975 * n)]


def fmt(interval: tuple[float, float, float], digits: int = 2) -> str:
    point, lo, hi = interval
    return f"{point:.{digits}f} [{lo:.{digits}f}–{hi:.{digits}f}]"


def best_threshold(pos: Sequence[float], neg: Sequence[float]) -> float:
    """Score threshold that maximises (answerable kept + unanswerable refused) / 2 on the given scores."""
    best_t, best_value = 0.0, -1.0
    for t in sorted(set(pos) | set(neg)):
        value = (sum(s >= t for s in pos) / len(pos) + sum(s < t for s in neg) / len(neg)) / 2
        if value > best_value:
            best_t, best_value = t, value
    return best_t


def auc(pos: Sequence[float], neg: Sequence[float]) -> float:
    """P(answerable top-1 score > unanswerable top-1 score); 0.5 = no separation."""
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
