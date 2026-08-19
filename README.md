# Migraine-agent evaluation artifact

Evaluation code and recorded outputs for the BIBE 2026 paper:

> **Localizing a Safety-Related Regression to the Tool-Access Transition in a
> Migraine-Care LLM Application**

The study used 87 synthetic cases during internal testing of one migraine-care
application. It contains no patient conversations, and its findings are not a
claim that tool calling generally harms self-harm safety.

## Reproduce the paper results

```bash
python3 -m venv .venv
.venv/bin/pip install -r artifact/requirements/reproduce.txt
.venv/bin/python artifact/reproduce.py
```

`artifact/reproduce.py` is the repository's supported reader-facing
reproduction entry point. Commands map to archives as follows:

| Command | What it checks | Paper Table 1 |
|---|---|---|
| `python artifact/reproduce.py` (default) | Discovery archive (mechanism, gate, and other historical analyses) | Row 3 is in this archive; default is not the 96-run batch |
| `python artifact/reproduce.py verify-equalized` | Frozen 8-run staged plan, 96 run files | Rows 1, 2, and 4 |
| `python artifact/reproduce.py verify-heldout` | Second-suite safety runs **and** non-safety checks in the same batch | Row 5; non-safety is not a Table 1 row |

The batches are intentionally not pooled. The default command remains stable,
while each later batch can be checked against its own frozen design.

## Paper Table 1 → files

Caption in the paper: *Inclusion analyses from the 87-case suite.* Each of the
first four rows uses 30 self-harm cases; **Second suite** uses a second 30.
Staged comparison randomized 12 model–configuration cells within eight blocks.

Gemini staged, GPT/Claude, and Instruction share
`artifact/archived_runs/equalized_ladder_2026-08-13/` because they were one
frozen 8-run plan (3 models × 4 configurations × 8 runs = 96 files).
Decomposition and Second suite are separate batches. Cell means from that
96-run batch are paper **Table II**, not Table 1.

| Analysis | Question | Role | Key number | Path |
|---|---|---|---|---|
| Gemini staged | Decrease after tool access? | Primary | Persona 28.00 → tool access 24.13; paired −3.88; 95% CI [−5.17, −2.58] | [`artifact/archived_runs/equalized_ladder_2026-08-13/`](artifact/archived_runs/equalized_ladder_2026-08-13/) |
| GPT, Claude | Same decrease on other models? | Descriptive | GPT 29.50 → 29.63; Claude 29.13 → 28.50 (unpooled) | same folder |
| Decomposition | Need a search call or retrieved content? | Exploratory | Schema 27.33; requests on 24.67; full app 24.00. Eight of nine lost case-runs had no document-search call | [`artifact/archived_runs/mechanism/2026-08-01T144305Z/`](artifact/archived_runs/mechanism/2026-08-01T144305Z/) |
| Instruction | Recover inclusion on original cases? | Recovery | Tool access 24.13 → instruction 29.00 | [`artifact/archived_runs/equalized_ladder_2026-08-13/`](artifact/archived_runs/equalized_ladder_2026-08-13/) |
| Second suite | Still raise inclusion on new cases? | Second suite | Persona 28.4 vs tools 27.6 (p = 0.151; does not replicate the drop); instruction 27.6 → 30.0 (p = 0.008) | [`artifact/archived_runs/heldout_tool_calling_2026-08-12/`](artifact/archived_runs/heldout_tool_calling_2026-08-12/) (safety runs in this folder; non-safety files in the same folder are **not** Table 1) |

Gate, non-safety, native-SDK, ablation, and discovery (`past_records/`) archives
are **not** Table 1 rows; they remain secondary / archive-only. See
[`artifact/RESULTS.md`](artifact/RESULTS.md) for numbers and interpretation, and
[`artifact/archived_runs/README.md`](artifact/archived_runs/README.md) for the
full directory index.

The results support localizing a configuration-specific regression on this
application's tool-access path. The second suite does not replicate the drop;
the instruction recovers inclusion on both the original cases and the second
suite.

## Repository map

| Path | What it contains |
|---|---|
| `artifact/reproduce.py` | The single reader-facing command. |
| `artifact/RESULTS.md` | Table 1 rows 1–5, then archive-only (not Table 1) results. |
| `artifact/cases.yaml` | The 87 synthetic evaluation cases. |
| `artifact/archived_runs/` | Redacted discovery, 96-run staged, mechanism, and second-suite outputs. |
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

# Table 1 rows 1, 2, and 4 (96-run staged batch).
.venv/bin/python artifact/reproduce.py verify-equalized

# Table 1 row 5 (second suite), plus non-safety checks in that batch.
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
