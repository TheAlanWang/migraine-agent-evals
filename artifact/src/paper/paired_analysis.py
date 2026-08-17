"""Paired per-case analysis of the staged series, on two metrics, plus exact tests.

Reports the paper's primary outcome first and an earlier composite heuristic second,
clearly labelled as a sensitivity analysis. The two are different constructs, not two
strengths of one, so their p-values are not comparable; see METRICS below. Both
preserve the direction and the absence of any improving case, which is the point of
running the second one at all.

The tables report a mean and a range per configuration, which compares two
*aggregates*. That cannot distinguish "adding tools cost four cases" from "adding
tools cost nine and won five back", and those have different implications: the first
is a uniform weakening, the second says the surrounding system redistributes which
prompts get a crisis referral. Because every configuration is evaluated on the same
cases, the stronger comparison is free: pair them case by case and count transitions.

Two tests are reported, for different questions:

  McNemar (exact)   Uses case identity. Of the cases whose label *changes*
                    between two rungs, is the split between lost and gained
                    more lopsided than a coin flip? This is the test that
                    matches the design, since the same cases are re-run.

  Mann-Whitney U    Treats each run's total as one observation and asks
    (exact)         whether the two rungs' run-level totals separate. This is
                    the weaker test, reported because it makes no assumption
                    about per-case labels being stable, but it needs runs to
                    spend its power: with 3 runs per rung the smallest
                    attainable two-sided p is about 0.10, so a
                    three-versus-three comparison cannot reach significance
                    however large the effect. Five per rung brings the floor to
                    about 0.008. The floor is read off the enumerated null
                    rather than from a closed form, because ties in the pooled
                    run totals make the null asymmetric and can move it.

Per-case labels are aggregated across runs by majority vote, with the tie case
(an even number of runs splitting evenly) reported separately rather than broken
arbitrarily, since a case that is safe half the time is genuinely unstable and
counting it either way would overstate what the data shows.

    python artifact/reproduce.py paired                     # all models
    python artifact/reproduce.py paired --model gemini-2.5-flash
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
sys.path.insert(0, str(ROOT / "src" / "paper"))
ARCHIVE = ROOT / "archived_runs"
PAST_RECORDS = ARCHIVE / "past_records"
LADDER = PAST_RECORDS / "ladder"
OUT = PAST_RECORDS / "analysis" / "paired_analysis.json"

# The two metrics this script reports, in the order it reports them.
#
# resource_supported is the paper's outcome and is imported from outcome_metrics so
# there is exactly one implementation of it. It is defined only on the 30 self-harm
# cases and returns None elsewhere, which is how eligibility is decided here too.
#
# crisis_safe is the composite heuristic used earlier in development. It mixes refusal
# detection, redirection, crisis-resource inclusion, and both self-harm and violence
# cases in one label, so it is a different construct rather than a stricter or looser
# version of the same one; its p-values are not comparable with the primary metric's.
# Two defects made it unusable for the paper, both recorded in Internal validity: it
# required the literal string "988", which penalized non-US resources unevenly by
# vendor, and its refusal marker list missed one model's refusals entirely because
# that model writes apostrophes typographically. Retained as a sensitivity analysis
# only, because the direction and the absence of any improving case survive it.
METRICS = [
    ("resource_supported", "PRIMARY PAPER METRIC", 30),
    ("crisis_safe", "LEGACY SENSITIVITY METRIC \u2014 NOT THE PAPER OUTCOME", 40),
]


def _scorer(metric: str):
    """rec -> True/False, or None when the metric does not apply to that case."""
    if metric == "resource_supported":
        import yaml
        from outcome_metrics import resource_supported
        cases = {c["id"]: c for c in yaml.safe_load((HERE / "cases.yaml").read_text())}

        def score(rec):
            case = cases.get(rec["case_id"])
            if case is None:
                return None
            return resource_supported(rec["answer"], case)
        return score

    def score(rec):
        return bool(rec["crisis_safe"])
    return score

# Adjacent comparisons that the paper draws a conclusion from. `full` hangs off
# persona_tools rather than continuing the chain, because the gate is toggled on
# the retrieval configuration; `mitigated` likewise is the retrieval
# configuration plus an instruction, with the gate still off.
STEPS = [
    ("base", "persona", "persona prompt"),
    ("persona", "persona_tools", "retrieval tools"),
    ("persona_tools", "full", "safety gate"),
    ("persona_tools", "mitigated", "precedence instruction"),
]


def _tiers() -> dict[str, str]:
    """Evasion tier per case id, read from the suite rather than the run records.

    The ladder's per-case records do not carry the tier, so it is joined back in
    from `cases.yaml`, which is also the file the tier assignment is frozen in.
    """
    import yaml
    cases = yaml.safe_load((HERE / "cases.yaml").read_text())
    return {c["id"]: c.get("tier", "?") for c in cases}


def _labels(runs: list[list[dict]], score) -> tuple[dict[str, bool], set[str]]:
    """Majority-vote label per case, plus the unstable ones.

    Returns (label, ties) where `ties` holds cases that split exactly evenly
    across runs and are therefore excluded from the paired counts. Cases the
    metric does not apply to never enter, so the denominator is the metric's own
    eligible set rather than every case in the run.
    """
    per_case: dict[str, list[bool]] = {}
    for run in runs:
        for rec in run:
            v = score(rec)
            if v is None:
                continue
            per_case.setdefault(rec["case_id"], []).append(bool(v))
    labels, ties = {}, set()
    for case, votes in per_case.items():
        safe = sum(votes)
        if safe * 2 == len(votes):
            ties.add(case)
        labels[case] = safe * 2 > len(votes)
    return labels, ties


def mcnemar_exact(lost: int, gained: int) -> float:
    """Two-sided exact McNemar: binomial(n=lost+gained, p=0.5) tail doubled."""
    n = lost + gained
    if n == 0:
        return 1.0
    k = min(lost, gained)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def mannwhitney(a: list[int], b: list[int]) -> dict:
    """Two-sided Mann-Whitney U on run-level totals.

    The observation unit is a *run*: one total out of 40 per run, never the 40
    individual cases. Pooling case-run observations would be pseudoreplication,
    since repeated runs of the same case are not new cases.

    Two p-values are computed because they disagree here and the difference is
    not cosmetic. SciPy's `method="exact"` doubles a one-sided tail from the
    tie-free null; our run totals contain ties, so we also run a full permutation
    test that scores ties as half a point and calls an arrangement extreme by
    |U - centre|. On this data the two agree exactly where the groups separate
    completely and differ by up to a factor of two elsewhere. We report the SciPy
    value, because that is what a reader reproduces from the archived totals, and
    carry the permutation value as a cross-check. The attainable floor is read off
    the enumerated null rather than from 2/C(n1+n2, n1), which assumes a
    symmetric null and is wrong under ties.
    """
    import warnings
    from scipy.stats import mannwhitneyu

    n1, n2 = len(a), len(b)
    pooled = a + b
    centre = n1 * n2 / 2

    def _u(idx: tuple[int, ...]) -> float:
        ga = [pooled[i] for i in idx]
        gb = [pooled[i] for i in range(len(pooled)) if i not in set(idx)]
        return sum((x > y) + 0.5 * (x == y) for x in ga for y in gb)

    null = [_u(idx) for idx in combinations(range(n1 + n2), n1)]

    def two_sided(stat: float) -> float:
        return sum(1 for u in null
                   if abs(u - centre) >= abs(stat - centre) - 1e-9) / len(null)

    observed = _u(tuple(range(n1)))
    with warnings.catch_warnings():          # ties make the exact null approximate
        warnings.simplefilter("ignore")
        exact = mannwhitneyu(a, b, alternative="two-sided", method="exact")
    return {"U": observed, "p": float(exact.pvalue),
            "p_permutation": two_sided(observed),
            "min_attainable_p": min(two_sided(u) for u in null),
            "n_runs": [n1, n2], "ties_in_pooled": len(pooled) - len(set(pooled)),
            "centre": centre}


def analyse(model: str, answers: dict, metric: str) -> dict:
    score = _scorer(metric)
    print(f"\n{'=' * 74}\n{model}\n{'=' * 74}")
    tier = _tiers()
    result = {"model": model, "metric": metric,
              "runs_per_step": {k: len(v) for k, v in answers.items()},
              "steps": []}
    print("runs per step: " + ", ".join(f"{k}={len(v)}" for k, v in answers.items()))

    for lo, hi, what in STEPS:
        if lo not in answers or hi not in answers:
            print(f"\n{lo} -> {hi}: skipped (missing step)")
            continue
        lab_lo, ties_lo = _labels(answers[lo], score)
        lab_hi, ties_hi = _labels(answers[hi], score)
        shared = sorted(set(lab_lo) & set(lab_hi))
        unstable = (ties_lo | ties_hi) & set(shared)
        paired = [c for c in shared if c not in unstable]

        both = [c for c in paired if lab_lo[c] and lab_hi[c]]
        lost = [c for c in paired if lab_lo[c] and not lab_hi[c]]
        gained = [c for c in paired if not lab_lo[c] and lab_hi[c]]
        neither = [c for c in paired if not lab_lo[c] and not lab_hi[c]]
        p_mcn = mcnemar_exact(len(lost), len(gained))

        def _total(run):
            return sum(1 for r in run if score(r))
        totals_lo = [_total(run) for run in answers[lo]]
        totals_hi = [_total(run) for run in answers[hi]]
        mw = mannwhitney(totals_lo, totals_hi)

        print(f"\n{lo} -> {hi}   (adds: {what})")
        print(f"  run totals      {totals_lo} -> {totals_hi}"
              f"   mean {sum(totals_lo)/len(totals_lo):.1f} -> "
              f"{sum(totals_hi)/len(totals_hi):.1f}")
        print(f"  paired cases    {len(paired)}/{len(shared)} eligible "
              f"({len(unstable)} excluded as split-evenly across runs)")
        print(f"    safe -> safe      {len(both)}")
        print(f"    safe -> unsafe    {len(lost)}   (lost)")
        print(f"    unsafe -> safe    {len(gained)}   (gained)")
        print(f"    unsafe -> unsafe  {len(neither)}")
        print(f"  net              {len(gained) - len(lost):+d} cases")
        print(f"  McNemar exact    p = {p_mcn:.4f}  "
              f"(on {len(lost) + len(gained)} discordant cases)")
        print(f"  Mann-Whitney U   U = {mw['U']:g} on {mw['n_runs'][0]} vs "
              f"{mw['n_runs'][1]} run totals, p = {mw['p']:.4f} (exact)"
              f"   [permutation p = {mw['p_permutation']:.4f}; "
              f"floor {mw['min_attainable_p']:.4f}; "
              f"{mw['ties_in_pooled']} ties]")

        by_tier: dict[str, dict[str, int]] = {}
        for case in lost:
            by_tier.setdefault(tier.get(case, "?"), {}).setdefault("lost", 0)
            by_tier[tier.get(case, "?")]["lost"] += 1
        for case in gained:
            by_tier.setdefault(tier.get(case, "?"), {}).setdefault("gained", 0)
            by_tier[tier.get(case, "?")]["gained"] += 1
        if by_tier:
            print("  by tier          " + "; ".join(
                f"{t}: +{v.get('gained', 0)}/-{v.get('lost', 0)}"
                for t, v in sorted(by_tier.items())))

        result["steps"].append({
            "from": lo, "to": hi, "adds": what,
            "run_totals": {lo: totals_lo, hi: totals_hi},
            "paired_cases": len(paired),
            "excluded_unstable": sorted(unstable),
            "transitions": {"safe_safe": len(both), "lost": len(lost),
                            "gained": len(gained), "unsafe_unsafe": len(neither)},
            "lost_cases": lost, "gained_cases": gained,
            "net": len(gained) - len(lost),
            "mcnemar_exact_p": p_mcn,
            "mannwhitney": mw,
            "by_tier": by_tier,
        })
    return result


def directions(results: list[dict]) -> dict:
    """Whether each step moves the same way in every model, without a pooled p-value.

    There was a pooled sign test here. It is gone on purpose. The three models are
    evaluated on the same suite, so their discordant cases are not independent
    observations and pooling them is pseudoreplication, which is what the paper says
    in Section VI. A p-value computed that way is smaller than the evidence supports,
    and shipping one next to a paper that disavows it invites the objection the paper
    was written to foreclose.

    Agreement across models is still worth reporting. It raises confidence that an
    effect generalizes beyond one vendor; it does not add observations to a
    within-model test. So this reports counts and direction only.
    """
    out = {}
    for _lo, _hi, what in STEPS:
        per_model = {}
        for res in results:
            for step in res["steps"]:
                if step["adds"] == what:
                    per_model[res["model"]] = {
                        "lost": step["transitions"]["lost"],
                        "gained": step["transitions"]["gained"],
                    }
        if not per_model:
            continue
        worse = [m for m, v in per_model.items() if v["lost"] > v["gained"]]
        better = [m for m, v in per_model.items() if v["gained"] > v["lost"]]
        flat = [m for m, v in per_model.items() if v["gained"] == v["lost"]]
        unanimous = len(worse) == len(per_model) or len(better) == len(per_model)
        out[what] = {"per_model": per_model, "worse": worse, "better": better,
                     "no_net_change": flat, "same_direction_in_every_model": unanimous,
                     "pooled_p_value": None,
                     "why_no_pooled_p": "the models share one suite, so pooling the "
                                        "discordant cases would be pseudoreplication"}
        print(f"\n{what}")
        for m, v in per_model.items():
            print(f"  {m:20} lost {v['lost']}, gained {v['gained']}")
        verdict = ("same direction in every model" if unanimous
                   else "direction not unanimous")
        print(f"  {verdict}; no pooled p-value, see docstring")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", help="only this model id")
    ap.add_argument("--metric", choices=[m for m, _, _ in METRICS],
                    help="run one metric instead of both")
    args = ap.parse_args()

    files = sorted(LADDER.glob("ladder_answers-*.json"))
    if not files:
        raise SystemExit(f"no ladder answer archives in {LADDER}")

    wanted = [m for m in METRICS if args.metric in (None, m[0])]
    payload = {"primary_metric": "resource_supported", "analyses": {}}

    for metric, banner, n_cases in wanted:
        print(f"\n{'#' * 74}")
        print(f"# {banner}")
        print(f"# {metric}, eligible cases: {n_cases}")
        if metric == "crisis_safe":
            print("# This composite metric was used during earlier development and mixes")
            print("# refusal, redirection, crisis-resource inclusion, self-harm and")
            print("# violence cases. It is retained only as a sensitivity analysis, and")
            print("# its p-values are not comparable with the primary metric's.")
        print(f"{'#' * 74}")

        per_model = []
        for path in files:
            model = path.stem.replace("ladder_answers-", "")
            if args.model and model != args.model:
                continue
            per_model.append(analyse(model, json.loads(path.read_text()), metric))

        dirs = None
        if not args.model and len(per_model) > 1:
            print(f"\n{'=' * 74}\ndirection across models ({metric})\n{'=' * 74}")
            dirs = directions(per_model)

        payload["analyses"][metric] = {
            "role": ("paper_primary" if metric == "resource_supported"
                     else "legacy_sensitivity_only"),
            "n_cases": n_cases,
            "per_model": per_model,
            "direction_across_models": dirs,
        }

    OUT.write_text(json.dumps(payload, indent=2))
    print(f"\nwritten to {OUT.relative_to(HERE)}")


if __name__ == "__main__":
    main()
