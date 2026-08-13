"""Llama Guard baseline for the safety gate (local, no external API).

Runs every suite prompt through Llama Guard 3 (via local ollama) and reports
per-tier block recall on the 40 safety cases plus false blocks on the
non-safety turns, for a like-for-like comparison with the MiniLM denylist gate
(Table II / Fig. 4). Llama Guard classifies the user turn as safe/unsafe; we
count "unsafe" as a block.

    ../.venv/bin/python llamaguard_baseline.py

Writes archived_runs/llamaguard_baseline.json so the numbers reported in the
paper can be checked against an artifact rather than a console transcript.
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
import hashlib
import json
from datetime import datetime, timezone

import yaml
import ollama

MODEL = "llama-guard3"

TIERS = {
    "direct": ['bomb','hurt-someone','weapon-school','end-life','overdose',
               'self-harm-methods','weapon-acquire','cutting','rope-knot','silencer'],
    "indirect": ['self-harm-indirect','stop-existing','all-over','whats-the-point',
                 'disappear','cant-do-this','no-reason','tired-of-fighting',
                 'burden-family','wont-matter'],
    "third-person": ['harm-plan','self-harm-thirdperson','roommate-end-life',
                     'brother-suffer','friend-sleeping-pills','party-knife',
                     'classmate-cuts','cousin-pills','coworker-revenge','teammate-hurt'],
    "domain-disguised": ['overdose-migraine-meds','hurt-classmate','meds-alcohol',
                         'sumatriptan-max','stop-eating','strongest-dose','head-wall',
                         'caffeine-overdose','never-wake','gepant-lethal'],
}

CASES = yaml.safe_load((ROOT / "cases.yaml").read_text())
by_id = {c["id"]: c for c in CASES}


def is_unsafe(prompt: str) -> bool:
    """True if Llama Guard classifies the user turn as unsafe (= a block)."""
    r = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    verdict = r["message"]["content"].strip().lower()
    # Llama Guard replies "safe" or "unsafe\n<categories>".
    return verdict.startswith("unsafe")


def model_identity() -> dict:
    """Digests that pin which weights produced these numbers.

    The tag alone does not. "llama-guard3" resolves through Ollama's moving :latest, so a
    run recording only the tag cannot be reproduced against the same file: a re-pull can
    change the weights under an unchanged name. The paper claims a weight digest ships with
    the artifact, and until 3 Aug 2026 that claim was not backed, because this runner wrote
    the tag and nothing else. Read from the local manifest rather than computed, since
    hashing 4.9 GB per run buys nothing over the digest Ollama already stores.
    """
    manifest = Path.home() / (
        ".ollama/models/manifests/registry.ollama.ai/library"
        f"/{MODEL.split(':')[0]}/{MODEL.split(':')[1] if ':' in MODEL else 'latest'}")
    out = {"ollama_tag": MODEL, "manifest_path_read": str(manifest)}
    try:
        m = json.loads(manifest.read_text())
    except OSError as exc:                       # not fatal: the numbers are still valid
        out["error"] = f"could not read manifest: {exc}"
        return out
    out["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    for layer in m.get("layers", []):
        kind = layer["mediaType"].rsplit(".", 1)[-1]
        out[f"{kind}_sha256"] = layer["digest"].removeprefix("sha256:")
        if kind == "model":
            out["weight_bytes"] = layer["size"]
    try:
        show = ollama.show(MODEL)
        info = show.get("model_info") or {}
        out["quantization"] = (show.get("details") or {}).get("quantization_level")
        out["parameters"] = (show.get("details") or {}).get("parameter_size")
        out["context_length"] = next(
            (v for k, v in info.items() if k.endswith("context_length")), None)
    except Exception as exc:                     # ollama.show is a convenience, not a gate
        out["show_error"] = str(exc)
    return out


results = {"model": MODEL,
           "model_identity": model_identity(),
           "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
           "per_tier": {}, "false_blocks": None}

print(f"=== Llama Guard ({MODEL}) per-tier block recall ===")
overall_blk = overall_tot = 0
for tier, ids in TIERS.items():
    blk = sum(1 for i in ids if is_unsafe(by_id[i]["question"]))
    overall_blk += blk
    overall_tot += len(ids)
    results["per_tier"][tier] = {"blocked": blk, "total": len(ids)}
    print(f"{tier:16s} {blk}/{len(ids)}")
print(f"{'OVERALL':16s} {overall_blk}/{overall_tot}")
results["overall"] = {"blocked": overall_blk, "total": overall_tot}

# False blocks: non-safety turns Llama Guard flags as unsafe
false = tot = 0
for c in CASES:
    if c["category"] == "safety":
        continue
    for spec in (c.get("turns") or [c]):
        tot += 1
        if is_unsafe(spec["question"]):
            false += 1
print(f"\nFalse blocks (non-safety turns): {false}/{tot}")
results["false_blocks"] = {"blocked": false, "total": tot}

out = ROOT / "archived_runs" / "llamaguard_baseline.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2))
print(f"\narchived to {out.relative_to(ROOT)}")
