# Archived results index

This directory contains separate experiment batches and historical discovery
records. Their sampling plans differ, so their runs must not be pooled.
[`../RESULTS.md`](../RESULTS.md) gives the result-centered summary; this file
explains where each underlying record lives.

## Directory map

| Path | What it contains | Status |
|---|---|---|
| [`equalized_ladder_2026-08-13/`](equalized_ladder_2026-08-13/) | Frozen balanced comparison: 3 models x 4 configurations x 8 runs, 96 run files total. | Primary balanced evidence |
| [`heldout_tool_calling_2026-08-12/`](heldout_tool_calling_2026-08-12/) | Five-run temporal holdout, mitigation checks, and non-safety regression checks. | Independent holdout evidence |
| [`mechanism/2026-08-01T144305Z/`](mechanism/2026-08-01T144305Z/) | Seven-condition, three-run mechanism decomposition. | Exploratory mechanism evidence |
| [`native_sdk/2026-08-01T153311Z/`](native_sdk/2026-08-01T153311Z/) | Native-provider control for persona-only versus schemas-present conditions. | Exploratory control |
| [`ablation/`](ablation/) | Earlier `vanilla`, `rag_only`, and `full` application runs collected while the suite expanded. | Historical discovery evidence |
| [`past_records/`](past_records/) | The files that previously sat loose in this directory: dated runs, ladder outputs, derived analyses, safety-gate outputs, configuration metadata, and provenance. | Historical discovery evidence |

The root now contains directories and this index only. No result JSON is left
loose at the top level.

## What the files inside each batch mean

### Balanced replication

See
[`equalized_ladder_2026-08-13/README.md`](equalized_ladder_2026-08-13/README.md)
for every run total and the exact plan.

- `plan.json`: frozen models, configurations, case count, block order, and input
  hashes.
- `preregistration.json`: hypotheses, outcomes, exclusions, stopping rules, and
  the prespecified interpretation rule.
- `results_manifest.json`: derived statistics plus SHA-256 digests for every
  accepted run.
- `runs/<model>--<configuration>--run<N>.json`: one 30-case run. Each file
  contains model answers, tool traces, per-case labels, and plan linkage.

### Heldout replication

See
[`heldout_tool_calling_2026-08-12/README.md`](heldout_tool_calling_2026-08-12/README.md)
for the run totals and interpretation.

- `plan.json`: frozen holdout cases and configuration definitions.
- `preregistration.json`: hypotheses and analysis rules fixed before the batch.
- `summary.json`: derived comparisons and test results.
- `runs/<experiment>--<configuration>--run<N>.json`: one run for the temporal
  safety holdout, mitigation check, or non-safety regression check.

### Mechanism decomposition

See
[`mechanism/2026-08-01T144305Z/README.md`](mechanism/2026-08-01T144305Z/README.md)
for all seven conditions and their run totals.

- `provenance.json`: batch-wide prompt, schema, model, sampling, and input
  digests.
- `analysis.json`: derived run totals, pairwise comparisons, and tool-use counts.
- `<condition>-run<N>.json`: one 30-case run for one mechanism condition.

### Native-SDK control

See
[`native_sdk/2026-08-01T153311Z/README.md`](native_sdk/2026-08-01T153311Z/README.md).

- `provenance.json`: provider client, prompt and schema hashes, model, sampling,
  and case counts.
- `persona-run<N>.json`: native-provider run with the persona prompt and no
  declared tools.
- `real_schemas-run<N>.json`: native-provider run with the same prompt and real
  tool declarations present.

### Earlier ablation runs

See [`ablation/README.md`](ablation/README.md).

- `vanilla-<timestamp>.json`: earlier no-retrieval application condition.
- `rag_only-<timestamp>.json`: retrieval-enabled condition without the full
  assembled application.
- `full-<timestamp>.json`: full application condition from the same development
  period.

### Former loose files

[`past_records/README.md`](past_records/README.md) explains every moved file,
including the eight dated records and every ladder, analysis, gate, configuration,
manifest, and provenance JSON.

## Verification

Run from the repository root:

```bash
python artifact/reproduce.py
python artifact/reproduce.py verify-equalized
python artifact/reproduce.py verify-heldout
python artifact/reproduce.py paired --metric crisis_safe
```

The first command checks the historical discovery analysis. The two explicit
verification commands check the balanced and heldout batches independently.

## Interpretation and redaction boundaries

Retrieved corpus text is removed from all public archives. Context and trace
previews use length-bearing placeholders; synthetic questions, model answers,
tool events, source labels, and derived outcomes remain.

The balanced batch did not meet its original all-model replacement criterion:
Gemini showed a strong tool-step decrease and mitigation, Claude showed a
smaller decrease, and GPT-5 mini showed no measurable decrease. All outcomes
remain archived rather than being selected after the results were known.
