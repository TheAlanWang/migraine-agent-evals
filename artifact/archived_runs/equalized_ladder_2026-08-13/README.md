# Balanced replication: 2026-08-13

This directory is the clean, balanced replication of the staged comparison. It
contains 96 complete runs: three model families, four configurations, and eight
runs per cell, with 30 synthetic safety cases in every run.

## Evidence boundary

This batch is independent of the earlier discovery runs in the parent directory.
Do not pool its runs with the discovery runs. The batch has its own frozen plan,
preregistration, input digests, summary manifest, and verifier:

```bash
python artifact/reproduce.py verify-equalized
```

The command validates all 96 files, their plan hash, model/configuration/run
identity, planned case order, per-run totals, input SHA-256 digests, cell means,
run-level Mann–Whitney tests, majority-case comparisons, split-even exclusions,
and McNemar tests.

## Contents

- `plan.json` freezes the 3 × 4 × 8 execution plan and case orders.
- `preregistration.json` records outcomes, comparisons, retention rules, and the
  original criterion for replacing the formal archive.
- `runs/` contains model answers and derived labels for every complete run.
- `results_manifest.json` contains batch-local summaries and SHA-256 digests.

Retrieved trace previews are replaced by
`[redacted: N chars of retrieved clinical corpus text]`. Synthetic questions,
model answers, source names, tool events, and derived labels remain. Runtime
logs, provider credentials, environment paths, orchestration code, and the
backend-coupled runner are excluded.

## Result

For the tool-calling transition (`persona` → `persona_tools`), mean
crisis-resource inclusion out of 30 was:

- Gemini 2.5 Flash: 28.000 → 24.125, the largest observed decrease.
- GPT-5 mini: 29.500 → 29.625, no measurable decrease.
- Claude Sonnet 5: 29.125 → 28.500, a small decrease.

The priority instruction raised Gemini to 29.000 and Claude to 29.375; GPT was
29.500. Exact and tie-aware permutation values are in `results_manifest.json`.

The preregistered replacement criterion was not met because GPT-5 mini did not
decrease. The batch is nevertheless reported as the primary balanced
replication: retaining discovery results only when replication was favorable
would create outcome-dependent selection. The preregistration is preserved
verbatim; the later publication decision is documented here rather than
rewriting it.
