"""Export a reviewed, sanitized description of the configuration under test.

The full production persona prompt and tool descriptions are withheld for
commercial confidentiality. Withholding them entirely, though, would leave the
paper's central experiment unverifiable: the mechanism ablation is a claim about
what one sentence inside a tool description does, and a reader cannot assess that
without seeing the sentence.

So this exports the middle position: everything behaviourally load-bearing, with
internal identifiers removed, plus a SHA-256 of each withheld original so a future
disclosure can be checked against what the paper was written from.

Published here, as of 5 August 2026, when Andrea Pope approved publishing the prompt
and the tool schemas:
  - the deployed persona prompt, verbatim
  - tool names, exact parameter structure, and each description verbatim
  - each description also in sanitized form, so the difference is visible
  - the clause that the mechanism ablation manipulates, called out separately
    because it is the independent variable
  - tool_choice settings per configuration
  - the canned tool results used in the bare-model configurations
  - SHA-256 and length of the prompt and each description, now as version markers
    rather than as substitutes for withheld text

Still withheld, and not affected by that approval because the reason is security
rather than commercial: the safety gate's reference-phrase list. Publishing it is a
bypass recipe, which is why `embedding_gate.py` ships a substitute of the same shape.

One name is deliberately kept: the retrieval tool is called `search_supabase` in
the released traces, and trace assertions match on it. Renaming it here would mean
editing 20 archived runs, that is, altering the evidence, to hide the name of a
third-party product that the paper does not otherwise mention.

    KOKUN_BACKEND=../../kokun-backend ../.venv-agent/bin/python export_experimental_config.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
sys.path.insert(0, str(ROOT / "src" / "experiments"))
OUT = (HERE / "archived_runs" / "past_records" / "configuration" /
       "experimental_config.json")

# Internal identifiers to strip from any text that ships.
REDACTIONS = [
    (re.compile(r"'document_sections'|\bdocument_sections\b"), "[redacted: internal table]"),
    (re.compile(r"\bknowledge_gaps\b"), "[redacted: internal table]"),
    (re.compile(r"\bagent-testing\b"), "[redacted: internal table]"),
    (re.compile(r"\bmatch_count\b"), "[redacted: internal parameter]"),
    (re.compile(r"\bembeddings\b(?= column)"), "[redacted: internal column]"),
]


def _sanitize(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    sys.path.insert(0, str(ROOT / "src" / "paper"))
    sys.path.insert(0, str(ROOT / "src" / "evaluation"))
    backend = Path(os.getenv("KOKUN_BACKEND", HERE.parent.parent / "kokun-backend"))
    sys.path.insert(0, str(backend))
    from dotenv import load_dotenv
    load_dotenv(backend / ".env")

    import app.agent.llm.agent as agent_mod
    from app.agent.llm.prompt_loader import get_active_config
    from mechanism_ablation import CANNED, HELPFULNESS_CLAUSE, CLAUSE_RE

    persona = get_active_config()["instruction"]

    # Recorded because this count has already been confused twice. A client-side
    # pull hit the default 1,000-row limit and produced 98, which is neither
    # figure below; and the documents table holds rows that never produced chunks,
    # so "how many documents" has two defensible answers. Both are stated.
    corpus = {}
    try:
        rows, page = [], 0
        while page < 20:
            r = agent_mod.supabase.table("documents").select("id,name").range(
                page * 1000, (page + 1) * 1000 - 1).execute()
            if not r.data:
                break
            rows += r.data
            page += 1
        indexed, page = set(), 0
        while page < 60:
            r = agent_mod.supabase.table("document_sections").select(
                "document_id").range(page * 1000, (page + 1) * 1000 - 1).execute()
            if not r.data:
                break
            indexed.update(x["document_id"] for x in r.data)
            page += 1
        chunks = agent_mod.supabase.table("document_sections").select(
            "id", count="exact").limit(1).execute().count
        strata = {}
        for row in rows:
            key = (row["name"] or "").split("/")[0] or "(no prefix)"
            strata[key] = strata.get(key, 0) + 1
        corpus = {
            "n_document_rows": len(rows),
            "n_indexed_documents": len(indexed),
            "n_chunks": chunks,
            "documents_by_stratum": strata,
            "note": "n_document_rows is every row in the documents table; "
                    "n_indexed_documents is those that produced chunks and are "
                    "therefore reachable by retrieval. The paper quotes the latter.",
        }
    except Exception as exc:
        corpus = {"error": f"{type(exc).__name__}: {exc}"}
    headings = re.findall(r"^##\s*(.+)$", persona, re.M)

    tools = []
    for tool in agent_mod.tools:
        raw = tool.description
        fields = getattr(tool.args_schema, "model_fields", {}) or {}
        entry = {
            "name": tool.name,
            "parameters": {
                n: {"type": getattr(f.annotation, "__name__", str(f.annotation)),
                    "required": f.is_required()}
                for n, f in fields.items()
            },
            "description": raw,
            "description_sanitized": " ".join(_sanitize(raw).split()),
            "description_sha256": _digest(raw),
            "description_length_chars": len(raw),
        }
        if CLAUSE_RE.search(raw):
            entry["experimental_variable"] = {
                "clause_verbatim": HELPFULNESS_CLAUSE,
                "why": "the mechanism ablation removes this clause, and replaces it "
                       "with neutral text of identical length as a control, so the "
                       "claim is not assessable without the exact wording",
                "length_chars": len(raw) - len(CLAUSE_RE.sub("", raw)),
            }
        tools.append(entry)

    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "note": "Deployed configuration. The persona prompt and the tool descriptions "
                "are here verbatim: Andrea Pope approved publishing both on 5 August "
                "2026, so the digests that stood in for them are now version markers "
                "rather than substitutes. Still withheld, on security rather than "
                "commercial grounds, is the safety gate's reference-phrase list; "
                "embedding_gate.py ships a substitute of the same shape.",
        "persona_prompt": {
            "instruction": persona,
            "withheld": False,
            "sha256": _digest(persona),
            "length_chars": len(persona),
            "section_headings": headings,
            "contains_crisis_resource_terms": {
                term: persona.lower().count(term)
                for term in ("988", "crisis", "suicid", "self-harm", "hotline", "emergency")
            },
            "why_those_counts": "all zero, which is what makes the bare-rung crisis "
                                "referrals attributable to the model rather than to "
                                "our prompt; the counts let a reader check that claim "
                                "without the prompt text",
        },
        "corpus": corpus,
        "tools": tools,
        "tool_choice_by_configuration": {
            "persona": "no tools bound",
            "dummy_schemas": 'tool_choice="none" (bound, forbidden to call)',
            "real_schemas": 'tool_choice="none" (bound, forbidden to call)',
            "real_callable": "bound and free to call, canned results returned",
            "agent": "production agent graph, tools really executed",
        },
        "canned_tool_results": CANNED,
        "withheld_entirely": {
            "clinical_corpus_text": "proprietary content",
            "gate_reference_phrase_list": "security: publishing it is a bypass recipe; "
                                          "embedding_gate.py ships a substitute list",
            "internal_table_and_column_names": "redacted from all shipped text",
        },
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT.relative_to(HERE)}")
    for t in tools:
        print(f"  {t['name']}: {len(t['parameters'])} params, "
              f"{t['description_length_chars']} chars, "
              f"sha256 {t['description_sha256'][:12]}"
              + ("  <- carries the experimental variable" if "experimental_variable" in t else ""))
    print(f"  persona prompt: {out['persona_prompt']['length_chars']} chars published "
          f"verbatim, sha256 {out['persona_prompt']['sha256'][:12]}, "
          f"{len(headings)} section headings")


if __name__ == "__main__":
    main()
