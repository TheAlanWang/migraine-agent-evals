# Archived results index

This directory contains three evidence layers. They have different sampling
plans and must be verified and interpreted separately; their runs must not be
pooled.

For a result-centered summary that separates the primary balanced comparison,
the exploratory mechanism decomposition, the temporal holdout, and secondary
safety findings, see [`../RESULTS.md`](../RESULTS.md).

| Evidence layer | Content | Verification |
|---|---|---|
| Discovery | Dated root files, `ladder_*`, `mechanism/`, `native_sdk/`, gate/baseline files, and the root `results_manifest.json` behind the original paper analysis. | `python artifact/reproduce.py` |
| Balanced replication | `equalized_ladder_2026-08-13/`: 96 runs across three models and four configurations. | `python artifact/reproduce.py verify-equalized` |
| Heldout replication | `heldout_tool_calling_2026-08-12/`: Gemini-only heldout, mitigation, and non-safety checks. | `python artifact/reproduce.py verify-heldout` |

The discovery root manifest is intentionally unchanged. Each replication keeps
its own frozen metadata and verifier, so adding the new evidence does not
silently change what the original paper command verifies.

Retrieved corpus text is removed from all public archives. Contexts and trace
previews carry length-bearing placeholders; recorded synthetic questions, model
answers, source names, tool events, and derived labels remain.

The balanced replication did not meet its original all-model replacement
criterion because GPT-5 mini showed no measurable tool-step decrease. It is
still reported rather than selected away after the result was known. The
defensible model-dependent conclusion is: a strong Gemini decrease and
mitigation, a smaller Claude decrease, and no GPT-5-mini replication.
