# Past discovery records

These files supported the discovery-stage analysis before the balanced and
heldout batches were frozen. They were moved here from the
`artifact/archived_runs/` root so that historical records are not mixed with the
later replication batches. The move changed paths only; no recorded model
answer or result value was removed.

Do not pool these records with the balanced or heldout runs. Their suite size,
configuration, run count, and sampling plan differ.

## Central manifest

- `results_manifest.json`: frozen, derived summary of the discovery ladder. It
  contains per-model run totals, paired transitions, exact-test outputs,
  multiple-comparison metadata, mechanism summaries, native-SDK control
  summaries, the source commit, and digests of the three ladder-answer files.

## `discovery_runs/`

These timestamped JSON files are early end-to-end application snapshots. Each
contains a `headline` summary followed by case-level questions, answers,
retrieval traces, source labels, and evaluation outcomes. The suite expanded
over time, so later files contain more cases.

| File | Contents |
|---|---|
| `2026-07-21T04-26-38Z.json` | Level-1 snapshot on the initial 30-case suite. |
| `2026-07-21T15-30-52Z.json` | One-case smoke record used to check the archive path. It is retained as history and is not part of any reported experiment. |
| `2026-07-22T21-59-36Z.json` | Level-2 snapshot on the initial 30-case suite. |
| `2026-07-27T23-40-37Z.json` | Later Level-1 snapshot on the 30-case suite. |
| `2026-07-29T22-55-16Z.json` | Level-3 snapshot on 30 cases, including judge summaries. |
| `2026-07-29T23-29-10Z.json` | Level-3 snapshot after the suite expanded to 42 cases. |
| `2026-07-30T03-51-17Z.json` | Level-3 snapshot after the suite expanded to 62 cases. |
| `2026-07-30T04-20-09Z.json` | Level-3 snapshot on the final 87-case development suite. |

The seven suite snapshots document chronology and provenance; the eighth file is
the one-case smoke record. They are not repeated runs of one unchanged
experiment.

## `ladder/`

The ladder compares staged configurations named `base`, `persona`,
`persona_tools`, `full`, and `mitigated`. The model-specific files have unequal
historical run counts, so they are not the later balanced eight-run comparison.

- `ladder_answers-gemini-2.5-flash.json`: all archived Gemini discovery-ladder
  case records, grouped by configuration and run.
- `ladder_answers-gpt-5-mini.json`: all archived GPT-5 mini discovery-ladder
  case records, grouped by configuration and run.
- `ladder_answers-claude-sonnet-5.json`: all archived Claude discovery-ladder
  case records, grouped by configuration and run.
- `ladder_counts-gemini-2.5-flash.json`: legacy `crisis_safe` totals derived
  from the Gemini answer file.
- `ladder_counts-gpt-5-mini.json`: legacy `crisis_safe` totals derived from the
  GPT answer file.
- `ladder_counts-claude-sonnet-5.json`: legacy `crisis_safe` totals derived from
  the Claude answer file.
- `persona_ladder.json`: early three-run single-model `crisis_safe` totals for
  `base`, `persona`, and `persona_tools`; retained for provenance and superseded
  by the model-specific answer archives.
- `persona_ladder-3run-original.json`: byte-for-byte historical duplicate of the
  original three-run count record. It is retained because these files are no
  longer being deleted, but it is superseded and must not be counted as another
  experiment.

The `ladder_counts-*` and `persona_ladder.json` files contain aggregate counts
only. The `ladder_answers-*` files contain the underlying per-case records.

## `analysis/`

- `paired_analysis.json`: case-paired and run-level analysis of adjacent ladder
  transitions under the primary resource-inclusion metric and the legacy
  sensitivity metric.
- `annotation_agreement-2026-08-01T192844Z-2026-08-03T064327Z.json`:
  inter-annotator agreement, scorer-versus-annotator comparisons, and
  per-configuration annotation summaries for the named release.
- `harmful_assistance.json`: post hoc screen and adjudication summary for
  actionable harmful content in archived safety answers.
- `unrefused_screen.json`: deliberately sensitive shortlist of answers that
  contained neither a narrow refusal marker nor a crisis resource; its flag
  share is not a failure rate.
- `knowledge_gaps_snapshot.json`: aggregate snapshot of distinct logged
  knowledge gaps used to support the corresponding reported count.

## `safety_gates/`

- `deployed_gate_sweep.json`: aggregate recall and false-block counts across
  thresholds for the deployed MiniLM-based gate. The withheld reference phrase
  list is not included.
- `llamaguard_baseline.json`: Llama Guard 3 block counts by safety tier and
  false blocks on non-safety turns.
- `llamaguard_baseline_provenance.json`: post-run model-weight, template, and
  parameter digests for the Llama Guard baseline, with the limitation that the
  original run recorded a moving Ollama tag.

## `configuration/`

- `experimental_config.json`: sanitized export of the discovery experiment's
  model, prompt-section, tool-schema, and evaluation configuration. Sensitive
  internal identifiers and verbatim proprietary material are removed or
  represented by hashes.

The balanced plan contains an `experimental_config.json` input-hash key using
the basename that existed when the plan was frozen. The current public copy is
`configuration/experimental_config.json`; the frozen plan itself is unchanged.

## `provenance/`

- `unredacted_originals.sha256.json`: byte counts and SHA-256 digests for
  pre-redaction originals that are intentionally absent from the public
  repository. Its `name` values preserve paths at the time the ledger was
  recorded; `path_note` explains where the current redacted copies moved.

## Reproducing the historical analysis

From the repository root:

```bash
python artifact/reproduce.py
python artifact/reproduce.py paired
```

The full `paired` command reproduces both the primary and legacy sensitivity
metrics in one output. The current scripts read and write the organized paths
above.
