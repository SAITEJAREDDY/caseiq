"""Small, deterministic paired-comparison statistics shared by the Phase 7
comparison reports. Pure functions over per-decision 0/1 outcomes -- no I/O,
no hidden truth. Uses Phase 6's bootstrap settings so results are repeatable.
"""
import random
from math import comb

from agent.jev_v2.config import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED


def mcnemar_exact_p(only_a_correct: int, only_b_correct: int) -> float:
    """Two-sided exact binomial (McNemar) p-value on the discordant pairs.
    1.0 when there are none. With few discordant pairs this is deliberately
    hard to make small -- that is the honest reading of a small sample."""
    n = only_a_correct + only_b_correct
    if n == 0:
        return 1.0
    k = min(only_a_correct, only_b_correct)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired_bootstrap_diff(a_flags: list, b_flags: list, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict:
    """Paired percentile-bootstrap CI for mean(a) - mean(b) over the same units."""
    n = len(a_flags)
    if n == 0 or n != len(b_flags):
        return {"n": n, "diff": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    diffs = []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(a_flags[i] - b_flags[i] for i in idx) / n)
    diffs.sort()
    return {
        "n": n, "diff": sum(a - b for a, b in zip(a_flags, b_flags)) / n,
        "ci_low": diffs[int(0.025 * resamples)], "ci_high": diffs[min(resamples - 1, int(0.975 * resamples))],
    }
