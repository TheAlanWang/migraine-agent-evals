# Earlier application ablation runs

These twelve files are historical discovery snapshots from the period when the
evaluation suite expanded from 30 to 87 cases. They compare three application
conditions at each suite size:

- `vanilla-*`: Level-2 run without retrieval. These files preserve answer and
  trace records, but their old aggregate `cases_passed` field is zero because
  that condition did not produce the retrieval-backed assertions used by the
  early Level-2 headline score. Zero is not an answer-quality score.
- `rag_only-*`: retrieval-enabled run without the complete assembled
  application.
- `full-*`: full application run from the same suite version.

| Suite version | `vanilla` file | `rag_only` file | `full` file |
|---|---|---|---|
| 30 cases | `vanilla-2026-07-29T21-04-16Z.json` | `rag_only-2026-07-29T21-06-54Z.json` | `full-2026-07-29T21-09-00Z.json` |
| 42 cases | `vanilla-2026-07-29T23-14-31Z.json` | `rag_only-2026-07-29T23-17-42Z.json` | `full-2026-07-29T23-20-42Z.json` |
| 62 cases | `vanilla-2026-07-30T03-01-40Z.json` | `rag_only-2026-07-30T03-06-08Z.json` | `full-2026-07-30T03-10-21Z.json` |
| 87 cases | `vanilla-2026-07-30T03-40-17Z.json` | `rag_only-2026-07-30T03-46-10Z.json` | `full-2026-07-30T03-52-03Z.json` |

Each JSON contains its timestamp, source commit, evaluation level, headline
aggregates, and case-level records. The three 87-case files are the versions
read by the historical paper-number and retrieval-confound checks. The earlier
suite versions remain only for chronology and provenance; they must not be
treated as repeated runs of the final 87-case design.
