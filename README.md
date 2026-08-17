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

`artifact/reproduce.py` is the repository's supported reader-facing
reproduction entry point. Its default command recomputes the discovery-archive
analyses. The balanced staged comparison reported in Table I and the heldout
analysis have independent commands and manifests:

```bash
.venv/bin/python artifact/reproduce.py verify-equalized
.venv/bin/python artifact/reproduce.py verify-heldout
```

The evidence layers are intentionally not pooled. The default command remains
stable, while each later batch can be checked against its own frozen design.

## Results at a glance

The results are organized into four layers with different designs and evidential
strength:

1. **Primary balanced comparison:** 96 runs across three model families and four
   configurations. At the tool-access transition, mean crisis-resource
   inclusion out of 30 changed from 28.00 to 24.13 for Gemini 2.5 Flash, from
   29.50 to 29.63 for GPT-5 mini, and from 29.13 to 28.50 for Claude Sonnet 5.
   Inferential claims are limited to the primary model.
2. **Exploratory mechanism decomposition:** three runs per configuration
   localized the lower result to the transition where tool requests became
   possible. Eight of nine affected case-runs had no document-search call.
3. **Temporal holdout and non-safety checks:** the heldout tool-access difference
   was smaller and nonsignificant (28.4 to 27.6; p = 0.151), while the fixed
   priority instruction increased the mean to 30.0 (p = 0.008). No non-safety
   regression was observed in the tested turns.
4. **Secondary safety findings:** neither evaluated input filter covered all 40
   safety cases, and trace/manual-review checks found risks not captured by the
   primary response metric.

The results support a configuration-specific regression on the primary path,
not a model-general tool-calling effect. See
[`artifact/RESULTS.md`](artifact/RESULTS.md) for the organized results and
interpretation, and the batch READMEs under `artifact/archived_runs/` for exact
tests and archive boundaries.

## Repository map

| Path | What it contains |
|---|---|
| `artifact/reproduce.py` | The single reader-facing command. |
| `artifact/RESULTS.md` | Organized primary, mechanism, holdout, and secondary results. |
| `artifact/cases.yaml` | The 87 synthetic evaluation cases. |
| `artifact/archived_runs/` | Redacted discovery, balanced-replication, and heldout-replication outputs. |
| `artifact/src/` | Evaluation, analysis, and experiment implementation. |
| `artifact/requirements/` | Minimal reproduction and optional experiment dependencies. |
| `artifact/DATA_CARD.md` | Release boundaries and limitations. |

Readers checking the paper need only `artifact/`.
The application-coupled ladder, mechanism, and native-SDK runners require the
original application backend and provider credentials; local gate experiments
and archived-data reproduction do not.

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
