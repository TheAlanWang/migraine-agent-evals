"""Archive the threshold sweep computed with the *deployed* gate configuration.

Fig. 4 in the paper reports a per-tier threshold sweep for the gate that is
actually in production, whose reference-phrase list is not published. The
released `embedding_gate.py` reproduces the shape of that result with a
substitute list, so an outside reader can check the finding but not the exact
numbers. This script closes the gap on our side: it recomputes the sweep from
the deployed list and writes the result to `archived_runs/`, so the figure's
numbers rest on an artifact rather than on a transcript.

Needs the Kokun backend checked out (for its reference-phrase list) and the
encoder extra. Nothing here is published beyond the aggregate counts.

    KOKUN_BACKEND=../../kokun-backend ../.venv/bin/python archive_deployed_sweep.py
"""
from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
BACKEND = Path(os.getenv("KOKUN_BACKEND", HERE.parent.parent / "kokun-backend"))
SWEEP = (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50)


def _deployed_topics() -> tuple[dict[str, list[str]], float]:
    """Read the production gate's reference phrasings and threshold.

    Parsed out of the source rather than imported: importing the module would
    pull in the backend's whole dependency tree (Supabase, Vertex) to obtain two
    literals, and this script only needs the data.
    """
    src = (BACKEND / "app/agent/llm/llama_checker.py").read_text()
    tree = ast.parse(src)
    topics = threshold = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):   # BANNED_TOPICS carries a type annotation
            targets = [node.target]
        else:
            continue
        for target in targets:
            name = getattr(target, "id", None)
            if name == "BANNED_TOPICS":
                topics = ast.literal_eval(node.value)
            elif name == "BANNED_THRESHOLD":
                threshold = ast.literal_eval(node.value)
    if topics is None or threshold is None:
        raise SystemExit(f"could not read the gate configuration from {BACKEND}")
    return topics, float(threshold)


def main() -> None:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    topics, deployed_threshold = _deployed_topics()
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    refs = {cat: model.encode(phrases) for cat, phrases in topics.items()}

    def peak(question: str) -> float:
        emb = model.encode([question])
        return max(float(cosine_similarity(emb, e)[0].max()) for e in refs.values())

    cases = yaml.safe_load((HERE / "cases.yaml").read_text())
    safety = [c for c in cases if c["category"] == "safety"]
    benign_turns = [q for c in cases if c["category"] != "safety"
                    for q in [s["question"] for s in (c.get("turns") or [c])]]

    scored_safety = [(c["tier"], peak(c["question"])) for c in safety]
    scored_benign = [peak(q) for q in benign_turns]
    tiers = sorted({t for t, _ in scored_safety})

    out = {
        "encoder": "sentence-transformers/all-MiniLM-L6-v2",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "deployed_threshold": deployed_threshold,
        "reference_phrase_counts": {c: len(p) for c, p in topics.items()},
        "note": "computed from the deployed reference-phrase list, which is not "
                "published; embedding_gate.py reproduces the shape with a substitute list",
        "sweep": [],
    }
    print(f"{'thresh':>7}  " + "  ".join(f"{t:>16}" for t in tiers)
          + f"  {'overall':>8}  {'false':>9}")
    for threshold in SWEEP:
        per_tier = {t: sum(1 for tt, s in scored_safety if tt == t and s >= threshold)
                    for t in tiers}
        blocked = sum(per_tier.values())
        false = sum(1 for s in scored_benign if s >= threshold)
        out["sweep"].append({
            "threshold": threshold,
            "per_tier": {t: {"blocked": per_tier[t],
                             "total": sum(1 for tt, _ in scored_safety if tt == t)}
                         for t in tiers},
            "overall": {"blocked": blocked, "total": len(scored_safety)},
            "false_blocks": {"blocked": false, "total": len(scored_benign)},
        })
        print(f"{threshold:>7.2f}  "
              + "  ".join(f"{per_tier[t]}/10".rjust(16) for t in tiers)
              + f"  {f'{blocked}/40':>8}  {f'{false}/{len(scored_benign)}':>9}")

    path = HERE / "archived_runs" / "deployed_gate_sweep.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"\narchived to {path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
