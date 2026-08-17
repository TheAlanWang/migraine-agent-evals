# Heldout tool-calling replication: 2026-08-12

This directory contains a preregistered Gemini 2.5 Flash replication on 30
synthetic cases held out from the earlier discovery and balanced batches. Five
runs were retained for each safety configuration, followed by an
original-prompt priority check and two three-run non-safety checks.

## Reproduce

```bash
python artifact/reproduce.py verify-heldout
```

The verifier requires all 26 run files, checks run identity and frozen case,
prompt, priority-instruction, and preregistration hashes, then recomputes
`summary.json` from the per-case records.

## Contents

- `heldout_cases.yaml` contains the 30 synthetic heldout safety cases.
- `preregistration.json` records the objective, outcomes, and analysis.
- `freeze_manifest.json` records the frozen input and prompt digests.
- `summary.json` is the original frozen summary.
- `runs/` contains the retained safety and non-safety outputs.
- `review/non_safety-wide-flags.tsv` records the manual wide-match review.

The backend-coupled runner, logs, console summary, credentials, and environment
paths are excluded. The runner digest remains in `freeze_manifest.json` as
provenance; the published verifier is a credential-free reimplementation over
the archived outputs.

## Results

Safety run totals are listed in run-index order:

| Configuration | Run totals (mean out of 30) |
|---|---|
| Persona without tools | 28, 29, 28, 29, 28 (28.4) |
| Persona with tools | 28, 28, 28, 27, 27 (27.6) |
| Tools plus fixed priority instruction | 30, 30, 30, 30, 30 (30.0) |
| Original-suite priority check | 29, 29, 29, 29, 29 (29.0) |

The tool-access difference was not significant (`p = 0.151`) and did not
independently reproduce the original decrease. The fixed priority instruction
increased the heldout mean from 27.6 to 30.0 (`p = 0.00794`).

The two non-safety configurations each covered 177 turns:

| Check | Tools | Tools plus priority |
|---|---:|---:|
| Crisis-resource flags | 1 | 0 |
| Search requests | 153 | 151 |
| Source-return turns | 118 | 119 |
| On-corpus source success | 60/60 | 60/60 |
| Off-corpus honest misses | 42/45 | 41/45 |

Manual review found no erroneous crisis routing in either non-safety
configuration. Full per-turn records are under `runs/`; recomputed comparisons
and counts are in `summary.json`.

## Scope

This is a heldout replication, not an additional set of discovery runs. Do not
pool it with either the discovery archive or the 96-run balanced replication.
It strengthens the Gemini-specific mitigation evidence but does not provide
new evidence about GPT or Claude.
