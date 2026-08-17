# Experiment runners

These scripts produced or supported the application-specific experiments. They
are not needed to run the reusable harness or recompute the paper's numbers from
the archived files.

## Keep the two repeated designs separate

- The **primary balanced comparison** used eight runs per
  model-configuration cell: three models by four configurations by eight runs,
  for 96 complete runs. Its frozen plan and outputs are under
  `artifact/archived_runs/equalized_ladder_2026-08-13/` and are verified with
  `python artifact/reproduce.py verify-equalized`.
- The **mechanism decomposition** used three runs per configuration on the
  primary model. Its implementation is `mechanism_ablation.py`, and its archived
  outputs are under
  `artifact/archived_runs/mechanism/2026-08-01T144305Z/`.

The default `N_RUNS=3` in the discovery runners does not describe the later
eight-run balanced batch. See `artifact/RESULTS.md` for the result-centered
summary.

| Script | Role |
|---|---|
| `cross_vendor_ladder.py` | Staged base, persona, function-access, safety-gate, and mitigation comparison across three model families. |
| `mechanism_ablation.py` | Separates declared function descriptions, permission to call, returned content, and the full application path. |
| `native_sdk_control.py` | Repeats non-callable configurations through a provider SDK rather than the application client stack. |
| `embedding_gate.py` | Standalone illustration of the similarity-based safety gate using a substitute reference list. |
| `llamaguard_baseline.py` | Local Llama Guard 3 comparison for the 40 safety cases and 59 non-safety turns. |
| `persona_ladder.py` | Historical single-model runner retained for provenance; superseded by `cross_vendor_ladder.py`. |

The first three scripts require the original application backend and provider
credentials. See their module docstrings for the exact environment variables.
