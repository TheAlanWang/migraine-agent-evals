"""Summarize a mechanism-ablation batch into one archived artifact.

Kept separate from freeze_results.py so the batch can be checked for completeness and
internal consistency before its numbers are allowed anywhere near the paper. Scores
with the current primary metric rather than the count stored in each run file, which
was written by the superseded criterion.

    ../.venv-agent/bin/python analyze_mechanism.py
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
sys.path.insert(0, str(ROOT / "src" / "paper"))
sys.path.insert(0, str(ROOT / "src" / "evaluation"))
from outcome_metrics import bare_refusal, resource_supported  # noqa: E402
from paired_analysis import mcnemar_exact, mannwhitney        # noqa: E402

ORDER = ["persona", "dummy_schemas", "real_schemas", "real_callable",
         "agent", "agent_no_help", "agent_help_neutral"]
STEPS = [
    ("persona", "dummy_schemas", "tool interface present (inert, shape-matched)"),
    ("dummy_schemas", "real_schemas", "real schema semantics, still forbidden"),
    ("real_schemas", "real_callable", "permission to call"),
    ("real_callable", "agent", "real agent: real retrieval, graph, memory"),
    ("agent", "agent_help_neutral", "helpfulness clause content, length-matched"),
    ("agent", "agent_no_help", "helpfulness clause deleted"),
    ("persona", "agent", "whole step, equivalent to the ladder's erosion step"),
]


def main() -> None:
    batch = Path(sorted(glob.glob(str(HERE / "archived_runs" / "mechanism" / "*/")))[-1])
    cases = {c["id"]: c for c in yaml.safe_load((HERE / "cases.yaml").read_text())}
    prov = json.loads((batch / "provenance.json").read_text())
    n_runs = prov["n_runs"]

    def load(cfg):
        return [json.loads((batch / f"{cfg}-run{i}.json").read_text())["records"]
                for i in range(1, n_runs + 1)]

    def totals(runs):
        out = []
        for r in runs:
            vals = [resource_supported(x["answer"], cases.get(x["case_id"], {}))
                    for x in r]
            out.append(sum(bool(v) for v in vals if v is not None))
        return out

    def labels(runs):
        per: dict[str, list[bool]] = {}
        for r in runs:
            for x in r:
                v = resource_supported(x["answer"], cases.get(x["case_id"], {}))
                if v is not None:
                    per.setdefault(x["case_id"], []).append(bool(v))
        return ({k: sum(v) * 2 > len(v) for k, v in per.items()},
                {k for k, v in per.items() if sum(v) * 2 == len(v)})

    def tool_counts(runs):
        sh = [x for r in runs for x in r
              if cases.get(x["case_id"], {}).get("expect_block") == "self_harm"]
        return {
            "search": sum(1 for x in sh if "search_supabase" in (x.get("tools_called") or [])),
            "log_gap": sum(1 for x in sh if "log_gap" in (x.get("tools_called") or [])),
            "of": len(sh),
        }

    data = {cfg: load(cfg) for cfg in ORDER}
    out = {"batch": batch.name, "provenance": prov, "metric": "resource_supported",
           "configs": {}, "steps": []}

    for cfg in ORDER:
        t = totals(data[cfg])
        out["configs"][cfg] = {
            "run_totals": t, "mean": statistics.mean(t), "of": 30,
            "bare_refusals": sum(bare_refusal(x["answer"], cases.get(x["case_id"], {}))
                                 for r in data[cfg] for x in r),
            "tool_calls": tool_counts(data[cfg]),
        }

    for lo, hi, name in STEPS:
        ll, tl = labels(data[lo])
        lh, th = labels(data[hi])
        shared = [c for c in set(ll) & set(lh) if c not in (tl | th)]
        lost = [c for c in shared if ll[c] and not lh[c]]
        gained = [c for c in shared if not ll[c] and lh[c]]
        # For each lost case: did retrieval, or any tool, fire in the later config?
        detail = {}
        for cid in lost:
            calls = [x.get("tools_called") or []
                     for r in data[hi] for x in r if x["case_id"] == cid]
            detail[cid] = {
                "runs_with_search": sum(1 for c in calls if "search_supabase" in c),
                "runs_with_log_gap": sum(1 for c in calls if "log_gap" in c),
                "runs": len(calls),
            }
        out["steps"].append({
            "from": lo, "to": hi, "adds": name,
            "mean_from": statistics.mean(totals(data[lo])),
            "mean_to": statistics.mean(totals(data[hi])),
            "lost": len(lost), "gained": len(gained),
            "lost_cases": sorted(lost), "gained_cases": sorted(gained),
            "mcnemar_p": mcnemar_exact(len(lost), len(gained)),
            "mannwhitney": mannwhitney(totals(data[lo]), totals(data[hi])),
            "lost_case_tool_use": detail,
        })

    path = batch / "analysis.json"
    path.write_text(json.dumps(out, indent=2))

    print(f"batch {batch.name}   metric {out['metric']}   {n_runs} runs per config\n")
    print(f"{'config':<22}{'runs':>14}{'mean':>7}{'bare':>8}{'search':>8}{'log_gap':>9}")
    for cfg in ORDER:
        c = out["configs"][cfg]
        bare = f"{c['bare_refusals']}/90"
        search = f"{c['tool_calls']['search']}/{c['tool_calls']['of']}"
        gaps = f"{c['tool_calls']['log_gap']}/{c['tool_calls']['of']}"
        print(f"{cfg:<22}{str(c['run_totals']):>14}{c['mean']:>7.1f}"
              f"{bare:>8}{search:>8}{gaps:>9}")

    print(f"\n{'step':<46}{'lost':>5}{'gained':>7}{'MW p':>8}{'McN p':>7}")
    for st in out["steps"]:
        print(f"{st['adds']:<46}{st['lost']:>5}{st['gained']:>7}"
              f"{st['mannwhitney']['p']:>8.3f}{st['mcnemar_p']:>7.3f}")

    print(f"\nwritten to {path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
