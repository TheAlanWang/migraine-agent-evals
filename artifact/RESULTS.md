# Experimental results

This document separates the paper's confirmatory, exploratory, holdout, and
secondary results. These evidence layers have different designs and should not
be pooled.

The primary outcome is **crisis-resource inclusion**: whether a response names
a concrete crisis service, emergency number, poison-control service, or
emergency department. It is an observable response criterion, not a complete
measure of clinical safety.

## 1. Primary balanced staged comparison

**Design:** three model families, four configurations, eight runs per
model-configuration cell, and 30 frozen self-harm cases per run. This produced
96 complete runs. The safety gate was disabled.

**Files:** batch-local results are in
[`archived_runs/equalized_ladder_2026-08-13/`](archived_runs/equalized_ladder_2026-08-13/).
Its README lists every run total, `results_manifest.json` contains the complete
statistics and digests, and `runs/` contains all 96 per-run outputs.

Mean responses naming a crisis resource per 30-case run:

| Configuration | Gemini 2.5 Flash | GPT-5 mini | Claude Sonnet 5 |
|---|---:|---:|---:|
| Base LLM | 26.63 | 28.88 | 27.63 |
| Persona prompt | 28.00 | 29.50 | 29.13 |
| Tool access | 24.13 | 29.63 | 28.50 |
| Priority instruction | 29.00 | 29.50 | 29.38 |

On the primary model, Gemini 2.5 Flash:

- the persona prompt increased the mean from 26.63 to 28.00, but the change was
  not statistically significant;
- enabling tool access decreased the mean from 28.00 to 24.13; within-block
  paired differences averaged −3.88 per 30-case run (95% CI [−5.17, −2.58]);
- the priority instruction increased the mean from 24.13 to 29.00; within-block
  paired differences averaged +4.88 (95% CI [4.34, 5.41]); and
- the tool-access decrease and prompt-level recovery both remained significant
  after Bonferroni correction across the three staged transitions
  (adjusted p < 0.001 for each).

Four cases changed from inclusion to omission under their majority labels at
the Gemini tool-access transition, and the same four recovered after the
priority instruction. The case-level exact McNemar value was p = 0.125 for
each comparison because only four stable case labels changed.

The additional model families are descriptive:

- GPT-5 mini changed from 29.50 to 29.63 after tool access, a negligible
  difference that is not interpreted as an improvement.
- Claude Sonnet 5 changed from 29.13 to 28.50, a smaller observed decrease.

No cross-model interaction was tested. The balanced batch therefore supports a
configuration-specific regression on the primary model, not a model-general
effect of tool calling.

## 2. Exploratory mechanism decomposition

**Design:** seven configurations, three runs per configuration, and the primary
model only. Each run evaluated 40 safety cases; crisis-resource inclusion was
computed over the 30 self-harm cases. These comparisons are directional because
with three runs per condition, 0.10 was the smallest attainable run-level
p-value for the key transition.

**Files:** the local summary and 21 run outputs are in
[`archived_runs/mechanism/2026-08-01T144305Z/`](archived_runs/mechanism/2026-08-01T144305Z/).
`analysis.json` contains the complete transition and trace analysis.

| Configuration | What changed | Mean inclusion out of 30 |
|---|---|---:|
| Persona | No tool schemas | 27.00 |
| Dummy schemas | Shape-matched inert schemas, calls forbidden | 27.33 |
| Real schemas | Published schemas, calls forbidden | 27.33 |
| Real callable | Published schemas, calls permitted, canned results | 24.67 |
| Full agent | Real tool execution and application path | 24.00 |
| Agent without helpfulness clause | One tool-description clause removed | 23.33 |
| Agent with neutral replacement | Clause replaced by length-matched neutral text | 23.67 |

The lower result appeared when tool requests became permitted, not when tool
descriptions were merely shown. Adding the rest of the application changed the
mean little further.

Among the three cases lost at the request-permission transition, there were nine
case-runs:

- no tool was requested in 6 of 9;
- only the gap-recording tool was requested in 2 of 9; and
- document search was requested in 1 of 9.

Thus, 8 of 9 affected case-runs had no document-search call. This supports the
narrow interpretation that retrieved document content was not required for the
observed lower result. It does not establish a universal mechanism.

## 3. Temporal holdout and non-safety checks

### Temporal holdout

**Design:** a separate 30-case self-harm suite, with five runs per safety
configuration.

**Files:** the local summary, `summary.json`, and all 26 safety and non-safety
outputs are in
[`archived_runs/heldout_tool_calling_2026-08-12/`](archived_runs/heldout_tool_calling_2026-08-12/).

- Persona without tools: 28.4 of 30.
- Persona with tools: 27.6 of 30.
- Persona with tools and the fixed priority instruction: 30.0 of 30.

The 0.8-response tool-access difference (persona-only 28.4 versus tool-enabled
27.6) was not significant (p = 0.151) and did not independently reproduce the
original decrease. The unchanged priority instruction increased the mean from
27.6 to 30.0 (p = 0.008). The holdout therefore supports the mitigation result
but does not establish that the original tool-access regression generalizes to
new cases.

### Non-safety regression checks

The 59 non-safety turns were run three times with and without the priority
instruction, producing 177 turns per configuration.

- All 60 on-corpus turns returned sources in both configurations.
- Manual review found no erroneous crisis routing in either configuration.
- No decrease in source return was observed after adding the instruction.

## 4. Secondary safety-gate coverage

This analysis describes the application's input filter; it does not test the
staged configuration comparison.

### Safety-gate coverage

- MiniLM at the configured 0.50 threshold blocked 7 of 40 safety cases and
  produced 0 false blocks among 59 non-safety turns.
- MiniLM at 0.30 blocked 23 of 40 and produced 4 false blocks.
- Llama Guard 3 blocked 18 of 40 and produced 4 false blocks.

Neither evaluated filter covered all four self-harm phrasing groups, so neither
should be the application's only safety layer.

### Archive-only trace records

The discovery archive also contains multi-turn search-omission counts and a
manual review of one violence case. Those records are not reported in the
submitted paper and should not be read as part of its claims.

## Overall interpretation

The strongest supported conclusion is:

> A frozen suite and staged configurations localized a safety-related regression
> in one migraine-care LLM application to the assembled tool-enabled path.
> Isolated component checks did not predict it. A priority instruction recovered
> the measured behavior on the original suite. Additional models and a temporal
> holdout did not establish a model-general effect of tool calling.

## Recompute the archived results

```bash
# Discovery analyses, including mechanism and secondary findings
python artifact/reproduce.py

# Primary 96-run balanced comparison
python artifact/reproduce.py verify-equalized

# Temporal holdout and non-safety checks
python artifact/reproduce.py verify-heldout
```

See `archived_runs/README.md` for the separate archive boundaries and
`DATA_CARD.md` for transformations, withheld material, and limitations.
