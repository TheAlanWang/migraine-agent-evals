# Analysis scripts

These are secondary or post hoc analyses. The main paper values can be checked
from the repository root with `python artifact/reproduce.py`.

| Script | Role |
|---|---|
| `analyze_mechanism.py` | Summarizes the one-feature-at-a-time mechanism runs. |
| `analysis_retrieval_confound.py` | Historical retrieval-length check, superseded by the mechanism experiment. |
| `annotation_agreement.py` | Computes agreement when private per-annotator labels and their key are supplied. |
| `report_harmful_assistance.py` | Inspects the post hoc answer-content review. |
| `screen_unrefused.py` | Historical screen for answers that were not refusals. |
| `adjudicate_harmful_assistance.py` | Author-side adjudication helper. |
| `annotation_survey.py` | Generates and summarizes the annotation task survey. |
