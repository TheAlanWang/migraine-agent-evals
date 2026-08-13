# Balanced replication: 2026-08-13

This directory publishes the Gemini 2.5 Flash subset of the balanced staged
comparison: four configurations, eight runs per configuration, and 30 synthetic
safety cases in every run.

## Evidence boundary

This batch is independent of the earlier discovery runs in the parent directory.
Do not pool its runs with the discovery runs. The batch has its own frozen plan,
preregistration, input digests, summary manifest, and verifier:

```bash
python artifact/reproduce.py verify-equalized
```

The command validates all 32 published files, their plan hash,
model/configuration/run identity, planned case order, per-run totals, input
SHA-256 digests, cell means, run-level Mann–Whitney tests, majority-case
comparisons, split-even exclusions, and McNemar tests.

## Contents

- `plan.json` and `preregistration.json` are kept verbatim from the original
  registered design. This archive publishes only the Gemini run files.
- `runs/` contains model answers and derived labels for the 32 Gemini runs.
- `results_manifest.json` contains batch-local summaries and SHA-256 digests.

Retrieved trace previews are replaced by
`[redacted: N chars of retrieved clinical corpus text]`. Synthetic questions,
model answers, source names, tool events, and derived labels remain. Runtime
logs, provider credentials, environment paths, orchestration code, and the
backend-coupled runner are excluded.

## Result

For the tool-calling transition (`persona` → `persona_tools`), mean
crisis-resource inclusion out of 30 for Gemini 2.5 Flash was 28.000 → 24.125.
The priority instruction recovered it to 29.000. Exact and tie-aware
permutation values are in `results_manifest.json`.

This public subset does not replace the discovery archive. The preregistration
is preserved verbatim; the later publication decision is documented here rather
than rewriting it.
