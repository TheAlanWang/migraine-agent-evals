"""Small exact-statistics helpers shared by replication verifiers."""
from __future__ import annotations

from itertools import combinations
from math import comb


def mcnemar_exact(lost: int, gained: int) -> float:
    n = lost + gained
    if n == 0:
        return 1.0
    k = min(lost, gained)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def mannwhitney(a: list[int], b: list[int]) -> dict:
    """Two-sided run-level Mann–Whitney with a tie-aware permutation check."""
    import warnings

    from scipy.stats import mannwhitneyu

    n1, n2 = len(a), len(b)
    pooled = a + b
    centre = n1 * n2 / 2

    ranks = [0.0] * len(pooled)
    ordered = sorted(range(len(pooled)), key=pooled.__getitem__)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and pooled[ordered[end]] == pooled[ordered[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2
        for index in ordered[start:end]:
            ranks[index] = average_rank
        start = end

    def u_for(indices: tuple[int, ...]) -> float:
        return sum(ranks[i] for i in indices) - n1 * (n1 + 1) / 2

    null = [u_for(indices) for indices in combinations(range(n1 + n2), n1)]

    distances = [abs(u - centre) for u in null]

    def p_for_distance(distance: float) -> float:
        return sum(value >= distance - 1e-9 for value in distances) / len(distances)

    observed = u_for(tuple(range(n1)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exact = mannwhitneyu(a, b, alternative="two-sided", method="exact")
    return {
        "U": observed,
        "p": float(exact.pvalue),
        "p_permutation": p_for_distance(abs(observed - centre)),
        "min_attainable_p": p_for_distance(max(distances)),
        "n_runs": [n1, n2],
        "ties_in_pooled": len(pooled) - len(set(pooled)),
        "centre": centre,
    }


def block_paired(totals_from: list[int], totals_to: list[int]) -> dict:
    """Within-block paired differences when run index aligns across configurations."""
    if len(totals_from) != len(totals_to):
        raise ValueError("paired run totals must have equal length")
    diffs = [b - a for a, b in zip(totals_from, totals_to)]
    n = len(diffs)
    mean = sum(diffs) / n
    if n < 2:
        return {"n_blocks": n, "diffs": diffs, "mean": mean, "ci_95": [mean, mean]}
    import statistics

    from scipy import stats

    sem = statistics.stdev(diffs) / n**0.5
    lo, hi = stats.t.interval(0.95, df=n - 1, loc=mean, scale=sem)
    # SciPy returns numpy scalars, and the last bits differ across platforms.
    # Store native floats at a fixed precision so the frozen manifest matches
    # the Linux verifier.
    return {
        "n_blocks": n,
        "diffs": diffs,
        "mean": mean,
        "ci_95": [round(float(lo), 10), round(float(hi), 10)],
    }


def majority_labels(
    runs: list[list[dict]], key: str
) -> tuple[dict[str, bool], set[str]]:
    votes: dict[str, list[bool]] = {}
    for run in runs:
        for record in run:
            votes.setdefault(record["case_id"], []).append(bool(record[key]))
    labels = {case_id: sum(values) * 2 > len(values) for case_id, values in votes.items()}
    ties = {
        case_id
        for case_id, values in votes.items()
        if sum(values) * 2 == len(values)
    }
    return labels, ties
