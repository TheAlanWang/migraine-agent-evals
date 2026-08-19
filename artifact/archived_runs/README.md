# Archived results index

This directory contains separate experiment batches and historical discovery
records. Their sampling plans differ, so their runs must not be pooled.
[`../RESULTS.md`](../RESULTS.md) gives the result-centered summary; this file
explains where each underlying record lives.

Run JSON under `*/runs/` is frozen (SHA-256 manifests). Do not move or rename
those files.

## Paper Table 1 → directory

Caption: *Inclusion analyses.* Cell means from the
96-run staged batch are paper **Table II**, not Table 1.

| Table 1 analysis | Role | Directory |
|---|---|---|
| Gemini staged | Primary | [`equalized_ladder_2026-08-13/`](equalized_ladder_2026-08-13/) |
| GPT, Claude | Descriptive | same folder (one frozen 8-run plan; 3 models × 4 configs × 8 runs) |
| Decomposition | Exploratory | [`mechanism/2026-08-01T144305Z/`](mechanism/2026-08-01T144305Z/) |
| Instruction | Recovery | [`equalized_ladder_2026-08-13/`](equalized_ladder_2026-08-13/) |
| Second suite | Second suite | [`heldout_tool_calling_2026-08-12/`](heldout_tool_calling_2026-08-12/) (safety runs only; non-safety files in this folder are not Table 1) |

`verify-equalized` checks Table 1 rows 1, 2, and 4.
`verify-heldout` checks Table 1 row 5 and the non-safety checks stored with that
batch. The default `reproduce.py` command checks the discovery archive.

## Directory map

| Path | What it contains | Status |
|---|---|---|
| [`equalized_ladder_2026-08-13/`](equalized_ladder_2026-08-13/) | Frozen staged comparison: 3 models × 4 configurations × 8 runs, 96 run files. One batch, three Table 1 analyses (Gemini staged, GPT/Claude, Instruction). | Table 1: Primary / Descriptive / Recovery |
| [`heldout_tool_calling_2026-08-12/`](heldout_tool_calling_2026-08-12/) | Five-run second suite, mitigation checks, and non-safety regression checks. | Table 1: Second suite (non-safety in this folder is not Table 1) |
| [`mechanism/2026-08-01T144305Z/`](mechanism/2026-08-01T144305Z/) | Seven-condition, three-run mechanism decomposition. | Table 1: Exploratory |
| [`native_sdk/2026-08-01T153311Z/`](native_sdk/2026-08-01T153311Z/) | Native-provider control for persona-only versus schemas-present conditions. | Not Table 1 (exploratory control) |
| [`ablation/`](ablation/) | Earlier `vanilla`, `rag_only`, and `full` application runs collected while the suite expanded. | Not Table 1 (historical discovery) |
| [`past_records/`](past_records/) | The files that previously sat loose in this directory: dated runs, ladder outputs, derived analyses, safety-gate outputs, configuration metadata, and provenance. | Not Table 1 (historical discovery) |

The root now contains directories and this index only. No result JSON is left
loose at the top level.

## What the files inside each batch mean

### Staged batch (Table 1 rows 1, 2, and 4)

See
[`equalized_ladder_2026-08-13/README.md`](equalized_ladder_2026-08-13/README.md)
for every run total and the exact plan.

- `plan.json`: frozen models, configurations, case count, block order, and input
  hashes.
- `preregistration.json`: hypotheses, outcomes, exclusions, stopping rules, and
  the prespecified interpretation rule.
- `results_manifest.json`: derived statistics plus SHA-256 digests for every
  accepted run.
- `runs/<model>-<configuration>-run<N>.json`: one 30-case run. Each file
  contains model answers, tool traces, per-case labels, and plan linkage.

### Second suite (Table 1 row 5)

See
[`heldout_tool_calling_2026-08-12/README.md`](heldout_tool_calling_2026-08-12/README.md)
for the run totals and interpretation. Folder and file names are unchanged.

- `heldout_cases.yaml`: the 30 frozen second-suite safety cases.
- `freeze_manifest.json`: frozen input, prompt, priority-instruction, and
  preregistration digests.
- `preregistration.json`: hypotheses and analysis rules fixed before the batch.
- `summary.json`: derived comparisons and test results.
- `runs/<experiment>-<configuration>-run<N>.json`: one run for the second-suite
  safety comparison, mitigation check, or non-safety regression check (the last
  of these is not Table 1).

### Mechanism decomposition (Table 1 row 3)

See
[`mechanism/2026-08-01T144305Z/README.md`](mechanism/2026-08-01T144305Z/README.md)
for all seven conditions and their run totals.

- `provenance.json`: batch-wide prompt, schema, model, sampling, and input
  digests.
- `analysis.json`: derived run totals, pairwise comparisons, and tool-use counts.
- `<condition>-run<N>.json`: one 40-case run for one mechanism condition; the
  primary crisis-resource outcome is computed over its 30 self-harm cases.

### Native-SDK control (not Table 1)

See
[`native_sdk/2026-08-01T153311Z/README.md`](native_sdk/2026-08-01T153311Z/README.md).

- `provenance.json`: provider client, prompt and schema hashes, model, sampling,
  and case counts.
- `persona-run<N>.json`: native-provider run with the persona prompt and no
  declared tools.
- `real_schemas-run<N>.json`: native-provider run with the same prompt and real
  tool declarations present.

### Earlier ablation runs (not Table 1)

See [`ablation/README.md`](ablation/README.md).

- `vanilla-<timestamp>.json`: earlier no-retrieval application condition.
- `rag_only-<timestamp>.json`: retrieval-enabled condition without the full
  assembled application.
- `full-<timestamp>.json`: full application condition from the same development
  period.

### Former loose files (not Table 1)

[`past_records/README.md`](past_records/README.md) explains every moved file,
including the eight dated records and every ladder, analysis, gate, configuration,
manifest, and provenance JSON.

## Verification

Run from the repository root:

```bash
python artifact/reproduce.py
python artifact/reproduce.py verify-equalized
python artifact/reproduce.py verify-heldout
python artifact/reproduce.py paired
```

The first command checks the historical discovery analysis (including
Decomposition). `verify-equalized` checks Table 1 rows 1, 2, and 4.
`verify-heldout` checks Table 1 row 5 and the non-safety files in that batch.

## Interpretation and redaction boundaries

Retrieved corpus text is removed from all public archives. Context and trace
previews use length-bearing placeholders; synthetic questions, model answers,
tool events, source labels, and derived outcomes remain.

The staged batch did not meet its original all-model replacement criterion:
Gemini showed a strong tool-step decrease and mitigation, Claude showed a
smaller decrease, and GPT-5 mini showed no measurable decrease. All outcomes
remain archived rather than being selected after the results were known.
