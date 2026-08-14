# Migraine-agent evaluation artifact

Evaluation code and recorded outputs for the BIBE 2026 paper:

> **Detecting a Safety-Related Response Regression After Enabling Tool Calling
> in a Migraine-Care LLM Application**

The study used 87 synthetic cases during internal testing of one migraine-care
application. It contains no patient conversations, and its findings are not a
claim that external functions always weaken crisis responses.

## Reproduce the paper results

```bash
python3 -m venv .venv
.venv/bin/pip install -r artifact/requirements/reproduce.txt
.venv/bin/python artifact/reproduce.py
```

`artifact/reproduce.py` is the repository's single command-line entry point. Its
default command recomputes the discovery-archive analyses. The balanced staged
comparison reported in Table I and the heldout analysis have independent
commands and manifests:

```bash
.venv/bin/python artifact/reproduce.py verify-equalized
.venv/bin/python artifact/reproduce.py verify-heldout
```

The evidence layers are intentionally not pooled. The default command remains
stable, while each later batch can be checked against its own frozen design.

## Replication result

The 96-run balanced replication found a model-dependent observed pattern. For the
tool-calling transition, mean crisis-resource inclusion out of 30 changed from
28.000 to 24.125 for Gemini 2.5 Flash, from 29.500 to 29.625 for GPT-5 mini,
and from 29.125 to 28.500 for Claude Sonnet 5. The GPT difference is negligible
and is not interpreted as an improvement. Claude showed a smaller observed
decrease, while Gemini showed the largest decrease and the clearest recovery
after the priority instruction. Additional-family results are descriptive; no
cross-model interaction test was performed.

The batch failed its preregistered all-model replacement criterion because GPT
did not decrease. It is nevertheless reported: retaining discovery data only
when a replication supports the original generalization would be
outcome-dependent selection. A separate heldout Gemini replication changed
from 28.4/30 without tools to 27.6/30 with tools and 30.0/30 after mitigation.
See the batch READMEs under `artifact/archived_runs/` for exact tests and scope.

## Repository map

| Path | What it contains |
|---|---|
| `artifact/reproduce.py` | The single reader-facing command. |
| `artifact/cases.yaml` | The 87 synthetic evaluation cases. |
| `artifact/archived_runs/` | Redacted discovery, balanced-replication, and heldout-replication outputs. |
| `artifact/src/` | Evaluation, analysis, and experiment implementation. |
| `artifact/requirements/` | Minimal reproduction and optional experiment dependencies. |
| `artifact/DATA_CARD.md` | Release boundaries and limitations. |

Readers checking the paper need only `artifact/`.
The experiment runners require the original application backend and provider
credentials; reproducing the reported numbers does not.

## Advanced usage

```bash
# Install the optional local semantic matcher used by the suite tests.
.venv/bin/pip install -r artifact/requirements/evaluation.txt

# Run the suite against the bundled toy implementation.
# A non-zero exit is expected because the toy intentionally fails many cases.
.venv/bin/python artifact/reproduce.py suite

# Test the Level-2 semantic concept matcher.
.venv/bin/python artifact/reproduce.py test

# Run the detailed paired analysis.
.venv/bin/python artifact/reproduce.py paired

# Verify the two later batches independently.
.venv/bin/python artifact/reproduce.py verify-equalized
.venv/bin/python artifact/reproduce.py verify-heldout
```

To evaluate another application, pass an importable callable that returns
`(answer, source_names, trace_events)`:

```bash
.venv/bin/python artifact/reproduce.py suite \
  --agent your_package.your_module:run_agent \
  --level 1 --retrieval-tool search
```

See [`artifact/DATA_CARD.md`](artifact/DATA_CARD.md) for release boundaries and
limitations, including the removed corpus passages, the withheld safety-gate
reference phrases, and the scope of the crisis-resource outcome. Licensed under
Apache-2.0; see `LICENSE` and `NOTICE`.
