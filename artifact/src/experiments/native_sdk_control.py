"""Reproduce one ladder rung through a different SDK, bypassing LangChain.

The concern this answers: the tool-bearing rungs drive a LangGraph agent, and the
bare rungs still go through LangChain's `bind_tools`. If either layer were what
changed the model's behaviour, the paper would be attributing to "retrieval-tool
augmentation" something that belongs to an orchestration framework or a client
library.

`bind_tools` was first checked to send schemas as a structured `tools` request field
rather than as injected prompt text, so it is a format translation and not an
emulation. This script removes the translation as well.

*The declarations are not hand-written.* A first version was, and it was not a valid
control: LangChain's Gemini converter also emits `parameters.description` and
`parameters.title`, drops the `top_k` default, and preserves the docstring's literal
indentation. A hand-copy cannot match that, and any difference in the payload is a
difference in the experiment. So the declarations are produced by LangChain's own
converter, serialized, and rebuilt as `google.genai` objects, with a field-by-field
equality check that aborts the run if the two payloads differ. What changes between
this and the LangChain path is the client stack, and nothing else.

Two configurations, matching the ladder and the mechanism ablation:

    persona          persona prompt, no tools declared
    real_schemas     persona prompt, both declarations present, model forbidden to
                     call them (function-calling mode NONE)

    KOKUN_BACKEND=../../kokun-backend ../.venv-agent/bin/python native_sdk_control.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
sys.path.insert(0, str(ROOT / "src" / "paper"))
sys.path.insert(0, str(ROOT / "src" / "evaluation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from outcome_metrics import bare_refusal, resource_supported  # noqa: E402

MODEL = os.getenv("LADDER_MODEL", "gemini-2.5-flash")
N_RUNS = int(os.getenv("N_RUNS", "3"))


def _langchain_declarations() -> list[dict]:
    """The exact function declarations LangChain would put on the wire."""
    from google.protobuf.json_format import MessageToDict
    from langchain_google_genai._function_utils import (
        convert_to_genai_function_declarations,
    )
    import mechanism_ablation as M

    tool_proto = convert_to_genai_function_declarations(M._real_tools())
    payload = MessageToDict(
        tool_proto._pb if hasattr(tool_proto, "_pb") else tool_proto,
        preserving_proto_field_name=False)
    return payload["functionDeclarations"]


def _as_genai_tool(declarations: list[dict]):
    """Rebuild the declarations as google.genai objects and prove they still match."""
    from google.genai import types

    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration.model_validate(d) for d in declarations])

    # Round-trip back to the same shape and compare. If the SDKs disagree about any
    # field, this is not a clean control and the run must not proceed.
    rebuilt = [json.loads(fd.model_dump_json(exclude_none=True, by_alias=True))
               for fd in tool.function_declarations]

    def _norm(obj):
        if isinstance(obj, dict):
            return {k: _norm(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_norm(v) for v in obj]
        return obj

    a, b = _norm(declarations), _norm(rebuilt)
    if a != b:
        diff = {k: (a[0].get(k), b[0].get(k))
                for k in set(a[0]) | set(b[0]) if a[0].get(k) != b[0].get(k)}
        raise SystemExit(
            "the google.genai payload differs from the LangChain payload, so this "
            f"would not isolate the client stack. Differing fields: {diff}")
    return tool, rebuilt


def _persona_prompt() -> str:
    backend = Path(os.getenv("KOKUN_BACKEND", HERE.parent.parent / "kokun-backend"))
    sys.path.insert(0, str(backend))
    load_dotenv(backend / ".env")
    from app.agent.llm.prompt_loader import get_active_config
    return get_active_config()["instruction"]


def run(client, prompt: str, cases: list[dict], tool) -> tuple[int, int, list]:
    from google.genai import types

    config = types.GenerateContentConfig(system_instruction=prompt)
    if tool is not None:
        config.tools = [tool]
        # Declared but forbidden, matching the mechanism ablation's tool_choice="none".
        config.tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="NONE"))

    supported, bare, records = 0, 0, []
    for case in cases:
        reply = client.models.generate_content(
            model=MODEL, contents=case["question"], config=config)
        text = reply.text or ""
        ok = resource_supported(text, case)
        if ok is not None:
            supported += bool(ok)
        bare += bool(bare_refusal(text, case))
        records.append({"case_id": case["id"], "question": case["question"],
                        "answer": text, "resource_supported": ok})
    return supported, bare, records


def main() -> None:
    load_dotenv(HERE.parent.parent / ".env")
    from google import genai
    from importlib.metadata import version

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set")

    declarations = _langchain_declarations()
    tool, verified = _as_genai_tool(declarations)
    print("declarations derived from LangChain's converter and verified identical "
          "under google.genai:")
    for d in verified:
        print(f"  {d['name']}: fields {sorted(d)}, "
              f"parameter fields {sorted(d.get('parameters', {}))}")

    cases = [c for c in yaml.safe_load((HERE / "cases.yaml").read_text())
             if c["category"] == "safety"]
    n_self_harm = sum(1 for c in cases if c.get("expect_block") == "self_harm")
    prompt = _persona_prompt()

    def _commit():
        try:
            return subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"],
                                  capture_output=True, text=True,
                                  check=True).stdout.strip()
        except Exception:
            return "unknown"

    prov = {
        "model": MODEL,
        "client": "google.genai (vendor SDK; no LangChain, no LangGraph)",
        "evals_commit": _commit(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "declarations_sha256": hashlib.sha256(
            json.dumps(declarations, sort_keys=True).encode()).hexdigest(),
        "case_set_sha256": hashlib.sha256((HERE / "cases.yaml").read_bytes()).hexdigest(),
        "n_self_harm_cases": n_self_harm,
        "versions": {p: version(p) for p in ("google-genai", "langchain-google-genai")},
        "declarations": declarations,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = HERE / "archived_runs" / "native_sdk" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2))
    print(f"\noutput -> {out_dir.relative_to(HERE)}")

    client = genai.Client(api_key=key)
    configs = {"persona": None, "real_schemas": tool}
    order = list(configs)
    for run_index in range(1, N_RUNS + 1):
        order = order[::-1]        # alternate, so drift cannot align with a config
        for name in order:
            path = out_dir / f"{name}-run{run_index}.json"
            if path.exists():
                print(f"  skip {name} run {run_index}: already present")
                continue
            supported, bare, records = run(client, prompt, cases, configs[name])
            path.write_text(json.dumps(
                {"config": name, "run_index": run_index,
                 "completed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ"),
                 "resource_supported": supported, "of": n_self_harm,
                 "bare_refusals": bare, "records": records,
                 **{k: v for k, v in prov.items() if k != "declarations"}}, indent=2))
            print(f"  {name:<14} run {run_index}: {supported}/{n_self_harm} "
                  f"resource-supported, {bare} bare refusals")

    missing = [f"{c}-run{i}" for c in configs for i in range(1, N_RUNS + 1)
               if not (out_dir / f"{c}-run{i}.json").exists()]
    if missing:
        print(f"INCOMPLETE, missing: {', '.join(missing)}")
        raise SystemExit(1)
    print("both configurations complete.")


if __name__ == "__main__":
    main()
