"""Verify the balanced Gemini replication directly from its 32 archived runs."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from freeze_equalized_ladder import (
    DEFAULT_BATCH,
    FreezeError,
    build_manifest,
    verify_input_digests,
)


EXPECTED_MEANS = {
    "gemini-2.5-flash": {
        "base": 26.625,
        "persona": 28.0,
        "persona_tools": 24.125,
        "mitigated": 29.0,
    },
}
EXPECTED_STEPS = {
    "gemini-2.5-flash": {
        "tool_calling": (-3.875, 0.0001554001554001554, 0.0001554001554001554),
        "priority_instruction": (4.875, 0.0001554001554001554, 0.0001554001554001554),
    },
}


def verify(batch: Path = DEFAULT_BATCH, require_manifest: bool = True) -> dict:
    batch = batch.resolve()
    current = build_manifest(batch)
    failures: list[str] = []
    checks = 0

    def check(label: str, got, want) -> None:
        nonlocal checks
        checks += 1
        equal = (
            math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-12)
            if isinstance(got, float) and isinstance(want, float)
            else got == want
        )
        if not equal:
            failures.append(f"{label}: got {got!r}, expected {want!r}")

    for model, configs in EXPECTED_MEANS.items():
        for config, expected in configs.items():
            check(
                f"{model}/{config} mean",
                current["models"][model]["cells"][config]["mean"],
                expected,
            )
            check(
                f"{model}/{config} n_runs",
                current["models"][model]["cells"][config]["n_runs"],
                8,
            )

    for model, steps in EXPECTED_STEPS.items():
        for step_name, (change, p_exact, p_permutation) in steps.items():
            step = current["models"][model]["steps"][step_name]
            check(f"{model}/{step_name} change", step["mean_change"], change)
            check(
                f"{model}/{step_name} exact p",
                step["mannwhitney"]["p"],
                p_exact,
            )
            check(
                f"{model}/{step_name} permutation p",
                step["mannwhitney"]["p_permutation"],
                p_permutation,
            )

    check(
        "replacement criterion",
        current["replacement_decision"]["criterion_met"],
        False,
    )

    if require_manifest:
        manifest_path = batch / "results_manifest.json"
        checks += 1
        if not manifest_path.is_file():
            failures.append("results_manifest.json is missing")
        else:
            stored = json.loads(manifest_path.read_text())
            try:
                verify_input_digests(
                    batch,
                    stored.get("inputs") or {},
                    expected_paths=set(current["inputs"]),
                )
            except FreezeError as exc:
                failures.append(str(exc))
            check("stored inputs", stored.get("inputs"), current["inputs"])
            check("stored plan digest", stored.get("plan_sha256"), current["plan_sha256"])
            check("stored design", stored.get("design"), current["design"])
            check("stored models", stored.get("models"), current["models"])
            check(
                "stored replacement decision",
                stored.get("replacement_decision"),
                current["replacement_decision"],
            )

    return {"checks": checks, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    args = parser.parse_args()
    try:
        result = verify(args.batch)
    except FreezeError as exc:
        raise SystemExit(str(exc)) from exc
    for failure in result["failures"]:
        print(f"FAIL: {failure}")
    print(
        f"{result['checks']} equalized checks run, "
        f"{len(result['failures'])} failed"
    )
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
