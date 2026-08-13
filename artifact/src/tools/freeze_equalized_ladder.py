"""Freeze the complete 8× balanced replication into a batch-local manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
ARTIFACT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

from archive_replication_batch import (  # noqa: E402
    EQUALIZED_CONFIGS,
    EQUALIZED_MODELS,
    expected_run_names,
)
from replication_statistics import (  # noqa: E402
    majority_labels,
    mannwhitney,
    mcnemar_exact,
)


DEFAULT_BATCH = ARTIFACT / "archived_runs" / "equalized_ladder_2026-08-13"
STEPS = (
    ("base", "persona", "persona_prompt"),
    ("persona", "persona_tools", "tool_calling"),
    ("persona_tools", "mitigated", "priority_instruction"),
)


class FreezeError(ValueError):
    """The archived batch is incomplete or no longer matches its frozen plan."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan_hash(run: dict, expected: str, name: str) -> None:
    if run.get("plan_sha256") != expected:
        raise FreezeError(f"{name}: plan hash does not match archived plan")


def verify_input_digests(
    root: Path,
    inputs: dict[str, str],
    expected_paths: set[str] | None = None,
) -> None:
    if expected_paths is not None and set(inputs) != expected_paths:
        missing = sorted(expected_paths - set(inputs))
        unexpected = sorted(set(inputs) - expected_paths)
        raise FreezeError(
            "incomplete input digest set"
            f"; missing={missing[:5]}; unexpected={unexpected[:5]}"
        )
    for relative, expected in inputs.items():
        path = root / relative
        if not path.is_file():
            raise FreezeError(f"missing manifest input: {relative}")
        if sha256(path) != expected:
            raise FreezeError(f"stale input digest: {relative}")


def _load_runs(batch: Path) -> tuple[dict[tuple[str, str], list[dict]], str]:
    plan_path = batch / "plan.json"
    preregistration = batch / "preregistration.json"
    runs_dir = batch / "runs"
    if not plan_path.is_file() or not preregistration.is_file():
        raise FreezeError("plan.json and preregistration.json are required")
    expected = expected_run_names("equalized")
    available = {path.name for path in runs_dir.glob("*.json")} if runs_dir.is_dir() else set()
    missing = sorted(expected - available)
    if missing:
        raise FreezeError(f"missing {len(missing)} runs: {', '.join(missing[:5])}")
    unexpected = sorted(available - expected)
    if unexpected:
        raise FreezeError(f"unexpected run files: {', '.join(unexpected[:5])}")

    plan = json.loads(plan_path.read_text())
    if (
        plan.get("models") != list(EQUALIZED_MODELS)
        or plan.get("configs") != list(EQUALIZED_CONFIGS)
        or plan.get("runs_per_cell") != 8
        or plan.get("cases_per_run") != 30
    ):
        raise FreezeError("plan shape does not match the registered 3×4×8 design")
    raw_plan_cells = plan.get("cells") or []
    plan_cells = {
        (cell["model"], cell["config"], cell["run_index"]): cell
        for cell in raw_plan_cells
    }
    if len(raw_plan_cells) != 96 or len(plan_cells) != 96:
        raise FreezeError("plan must contain exactly 96 unique cells")

    plan_digest = sha256(plan_path)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for model in EQUALIZED_MODELS:
        for config in EQUALIZED_CONFIGS:
            cell = []
            for run_index in range(1, 9):
                name = f"{model}-{config}-run{run_index}.json"
                run = json.loads((runs_dir / name).read_text())
                validate_plan_hash(run, plan_digest, name)
                if (
                    run.get("status") != "complete"
                    or run.get("model") != model
                    or run.get("config") != config
                    or run.get("run_index") != run_index
                    or run.get("completed_cases") != 30
                    or len(run.get("records") or []) != 30
                ):
                    raise FreezeError(f"incomplete or misidentified run: {name}")
                planned_cell = plan_cells.get((model, config, run_index))
                if (
                    planned_cell is None
                    or run.get("block") != planned_cell.get("block")
                    or run.get("block") != run_index
                ):
                    raise FreezeError(f"{name}: run block does not match plan cell")
                expected_order = plan.get("case_orders", {}).get(str(run["block"]))
                actual_order = [record.get("case_id") for record in run["records"]]
                if actual_order != expected_order:
                    raise FreezeError(f"{name}: records do not match planned case order")
                recomputed = sum(
                    bool(record.get("crisis_resource_included"))
                    for record in run["records"]
                )
                if recomputed != run.get("crisis_resource_total"):
                    raise FreezeError(f"stale crisis_resource_total: {name}")
                cell.append(run)
            grouped[model, config] = cell
    return grouped, plan_digest


def _cell(runs: list[dict]) -> dict:
    totals = [run["crisis_resource_total"] for run in runs]
    return {
        "n_runs": len(totals),
        "run_totals": totals,
        "of": 30,
        "mean": sum(totals) / len(totals),
        "min": min(totals),
        "max": max(totals),
    }


def _step(runs_from: list[dict], runs_to: list[dict]) -> dict:
    totals_from = [run["crisis_resource_total"] for run in runs_from]
    totals_to = [run["crisis_resource_total"] for run in runs_to]
    records_from = [run["records"] for run in runs_from]
    records_to = [run["records"] for run in runs_to]
    labels_from, ties_from = majority_labels(
        records_from, "crisis_resource_included"
    )
    labels_to, ties_to = majority_labels(records_to, "crisis_resource_included")
    shared = set(labels_from) & set(labels_to)
    unstable = (ties_from | ties_to) & shared
    paired = sorted(shared - unstable)
    lost = [
        case_id
        for case_id in paired
        if labels_from[case_id] and not labels_to[case_id]
    ]
    gained = [
        case_id
        for case_id in paired
        if not labels_from[case_id] and labels_to[case_id]
    ]
    mean_from = sum(totals_from) / len(totals_from)
    mean_to = sum(totals_to) / len(totals_to)
    return {
        "mean_from": mean_from,
        "mean_to": mean_to,
        "mean_change": mean_to - mean_from,
        "lost": lost,
        "gained": gained,
        "excluded_split_even": sorted(unstable),
        "mannwhitney": mannwhitney(totals_from, totals_to),
        "mcnemar_p": mcnemar_exact(len(lost), len(gained)),
    }


def _input_digests(batch: Path) -> dict[str, str]:
    paths = [batch / "plan.json", batch / "preregistration.json"]
    paths.extend(sorted((batch / "runs").glob("*.json")))
    return {
        path.relative_to(batch).as_posix(): sha256(path)
        for path in paths
    }


def build_manifest(batch: Path = DEFAULT_BATCH) -> dict:
    batch = batch.resolve()
    grouped, plan_digest = _load_runs(batch)
    preregistration = json.loads((batch / "preregistration.json").read_text())

    models = {}
    for model in EQUALIZED_MODELS:
        cells = {
            config: _cell(grouped[model, config])
            for config in EQUALIZED_CONFIGS
        }
        steps = {
            name: _step(grouped[model, source], grouped[model, target])
            for source, target, name in STEPS
        }
        models[model] = {"cells": cells, "steps": steps}

    primary = models["gemini-2.5-flash"]["steps"]
    failed_models = [
        model
        for model in ("gpt-5-mini", "claude-sonnet-5")
        if models[model]["steps"]["tool_calling"]["mean_change"] >= 0
    ]
    criterion_met = (
        primary["tool_calling"]["mean_change"] < 0
        and primary["tool_calling"]["mannwhitney"]["p"] < 0.05
        and primary["priority_instruction"]["mean_change"] > 0
        and primary["priority_instruction"]["mannwhitney"]["p"] < 0.05
        and not failed_models
    )
    return {
        "schema_version": 1,
        "generated": datetime.now(timezone.utc).isoformat(),
        "batch": "equalized_ladder_2026-08-13",
        "source_frozen_at": preregistration.get("frozen_at"),
        "design": {
            "models": list(EQUALIZED_MODELS),
            "configs": list(EQUALIZED_CONFIGS),
            "runs_per_cell": 8,
            "cases_per_run": 30,
            "primary_metric": "crisis_resource_included",
        },
        "plan_sha256": plan_digest,
        "inputs": _input_digests(batch),
        "models": models,
        "replacement_decision": {
            "criterion_met": criterion_met,
            "failed_models": failed_models,
            "decision": (
                "replace_formal_archive"
                if criterion_met
                else "criterion_not_met_report_as_independent_replication"
            ),
            "rule": preregistration.get("decision_rule_for_repo_replacement"),
        },
    }


def write_manifest(batch: Path = DEFAULT_BATCH) -> Path:
    manifest = build_manifest(batch)
    output = batch / "results_manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    args = parser.parse_args()
    try:
        output = write_manifest(args.batch)
    except FreezeError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
