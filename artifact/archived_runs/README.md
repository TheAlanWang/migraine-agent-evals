# Archived results index

This directory contains three evidence layers. They have different sampling
plans and must be verified and interpreted separately; their runs must not be
pooled.

| Evidence layer | Content | Verification |
|---|---|---|
| Discovery | Dated root files, `ladder_*`, `mechanism/`, `native_sdk/`, gate/baseline files, and the root `results_manifest.json` behind the original paper analysis. | `python artifact/reproduce.py` |
| Balanced replication | `equalized_ladder_2026-08-13/`: 32 Gemini runs across four configurations. | `python artifact/reproduce.py verify-equalized` |
| Heldout replication | `heldout_tool_calling_2026-08-12/`: Gemini-only heldout, mitigation, and non-safety checks. | `python artifact/reproduce.py verify-heldout` |

The discovery root manifest is intentionally unchanged. Each replication keeps
its own frozen metadata and verifier, so adding the new evidence does not
silently change what the original paper command verifies.

Retrieved corpus text is removed from all public archives. Contexts and trace
previews carry length-bearing placeholders; recorded synthetic questions, model
answers, source names, tool events, and derived labels remain.

The published balanced subset is Gemini-only and does not replace the discovery
archive. The frozen plan and preregistration remain verbatim; publication scope
is documented in the batch README rather than rewritten into those files.
