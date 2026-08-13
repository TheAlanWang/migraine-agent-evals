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

## Result and scope

Mean crisis-resource inclusion was 28.4/30 without tools, 27.6/30 with tools,
and 30.0/30 after adding the priority instruction. The tool-step run-level exact
test was not significant (`p = 0.151`); the mitigation step was
`p = 0.00794`. Non-safety checks are reported separately in `summary.json`.

This is a heldout replication, not an additional set of discovery runs. Do not
pool it with either the discovery archive or the 32-run balanced replication.
It strengthens the Gemini-specific mitigation evidence and does not generalize
beyond that family.
