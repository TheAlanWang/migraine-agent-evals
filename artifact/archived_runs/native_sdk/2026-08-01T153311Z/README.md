# Native-SDK control

This exploratory control used the Google `google.genai` client directly, without
LangChain or LangGraph. It tested whether merely presenting the real tool
declarations changed the measured response behavior when tool execution was not
part of the comparison.

It is not a replication of the complete tool-enabled application. In
particular, it does not include the `real_callable` condition where the
mechanism batch later localized the lower result.

## Results

| Configuration | Run totals out of 30 | Mean |
|---|---:|---:|
| Persona prompt, no declarations | 28, 27, 27 | 27.33 |
| Persona prompt with real declarations | 27, 29, 28 | 28.00 |

These three-run descriptive results show no decrease from declaration presence
alone in this native-client control.

## Files

- `provenance.json`: model and client identity, source commit, prompt hash,
  declaration hash, case-set hash, package versions, and the exact tool
  declarations used.
- `persona-run1.json`, `persona-run2.json`, `persona-run3.json`: the three
  persona-only runs. Each contains the run total, bare-refusal count, and 30
  case-level question, answer, and outcome records.
- `real_schemas-run1.json`, `real_schemas-run2.json`,
  `real_schemas-run3.json`: the three runs with the same persona and real tool
  declarations present. They have the same record structure as the persona
  files.

The discovery manifest at
`../../past_records/results_manifest.json` carries the derived control summary
and explicitly records that `real_callable` is outside this batch's scope.
