"""Strip retrieved corpus text out of archived Level-3 runs before release.

The Level-3 (RAGAS) runs archive each turn's retrieved `contexts`, because the
judge needs them to score faithfulness. That text is verbatim content from a
proprietary clinical knowledge base, so it must not ship in a public artifact,
while everything the paper's claims rest on -- answers, traces, source document
names, per-metric scores -- must stay.

Each context string is replaced by a placeholder recording its length, so the
number of retrieved chunks and the rough context size per turn remain visible
(both matter when interpreting a faithfulness score); only the wording is gone.
Runs are marked `contexts_redacted: true` so a reader can tell this happened.

Idempotent: already-redacted files are left alone.

    python redact_corpus_contexts.py --check   # report, change nothing
    python redact_corpus_contexts.py           # rewrite in place
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
RUNS_DIR = HERE / "archived_runs"
PLACEHOLDER = "[redacted: {n} chars of retrieved clinical corpus text]"


def _redact_run(run: dict) -> int:
    """Replace context strings in place; return how many were redacted."""
    redacted = 0
    for case in run.get("cases") or []:
        for turn in case.get("turns") or []:
            contexts = turn.get("contexts")
            if not contexts:
                continue
            new = []
            for chunk in contexts:
                if isinstance(chunk, str) and not chunk.startswith("[redacted:"):
                    new.append(PLACEHOLDER.format(n=len(chunk)))
                    redacted += 1
                else:
                    new.append(chunk)
            turn["contexts"] = new
    if redacted:
        run["contexts_redacted"] = True
    return redacted


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="report what would be redacted without writing")
    args = ap.parse_args()

    total = 0
    for path in sorted(RUNS_DIR.rglob("*.json")):
        run = json.loads(path.read_text())
        if not isinstance(run, dict):
            continue  # ladder count/answer files have no contexts
        count = _redact_run(run)
        if not count:
            continue
        total += count
        print(f"{'would redact' if args.check else 'redacted'} {count:>4} "
              f"contexts in {path.relative_to(HERE)}")
        if not args.check:
            path.write_text(json.dumps(run, indent=2))

    if total == 0:
        print("nothing to redact — archived runs carry no corpus text")
    elif args.check:
        print(f"\n{total} context strings would be redacted; rerun without --check")


if __name__ == "__main__":
    main()
