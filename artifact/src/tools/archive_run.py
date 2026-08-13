"""Promote a harness run into the tracked archive, redacting corpus text.

`harness.py` writes to `runs/`, which is deliberately untracked: a Level-3 run
embeds the retrieved chunks the judge scored, and those are verbatim text from a
proprietary clinical corpus. This script is the one step between "a run
happened" and "a run backs a number in the paper": it copies the run into
`archived_runs/` and replaces each retrieved context with a length-preserving
placeholder on the way.

Run it for any run whose numbers you intend to cite. Three of the paper's
figures once rested on runs that were never promoted, and one of those runs was
later lost, so the number could not be reproduced from the release.

    ../.venv/bin/python archive_run.py                    # newest run in runs/
    ../.venv/bin/python archive_run.py path/to/run.json   # a specific run
    ../.venv/bin/python archive_run.py --all              # every run not yet archived
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
sys.path.insert(0, str(ROOT / "src" / "paper"))
sys.path.insert(0, str(ROOT / "src" / "evaluation"))
from redact_corpus_contexts import _redact_run  # noqa: E402

RUNS = HERE / "runs"
ARCHIVE = HERE / "archived_runs"
# Where harness.py writes when driven from the backend checkout.
BACKEND_RUNS = HERE.parent.parent / "kokun-backend" / "evals" / "runs"


def _source_dirs() -> list[Path]:
    return [d for d in (RUNS, BACKEND_RUNS) if d.is_dir()]


def _candidates() -> list[Path]:
    runs = [p for d in _source_dirs() for p in d.glob("*.json")]
    runs += [p for d in _source_dirs() for p in d.glob("ablation/*.json")]
    return sorted(runs, key=lambda p: p.stat().st_mtime)


def _archive_path(src: Path) -> Path:
    # keep the ablation/ subdirectory structure, since the paper's tables refer
    # to configurations by that layout
    return ARCHIVE / ("ablation" / Path(src.name) if src.parent.name == "ablation"
                      else Path(src.name))


def promote(src: Path, force: bool = False) -> bool:
    dest = _archive_path(src)
    if dest.exists() and not force:
        print(f"  already archived, skipping: {dest.relative_to(HERE)}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        run = json.loads(src.read_text())
    except json.JSONDecodeError:
        print(f"  not JSON, copying verbatim: {src.name}")
        shutil.copy2(src, dest)
        return True

    redacted = _redact_run(run) if isinstance(run, dict) else 0
    dest.write_text(json.dumps(run, indent=2))
    note = f", {redacted} corpus contexts redacted" if redacted else ""
    print(f"  archived {src.name} -> {dest.relative_to(HERE)}{note}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run", nargs="?", type=Path,
                    help="run JSON to archive (default: newest unarchived)")
    ap.add_argument("--all", action="store_true",
                    help="archive every run not already in archived_runs/")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an already-archived run")
    args = ap.parse_args()

    if args.run:
        targets = [args.run]
    else:
        found = _candidates()
        if not found:
            raise SystemExit(f"no runs found under {', '.join(map(str, _source_dirs()))}")
        targets = found if args.all else [found[-1]]

    promoted = sum(promote(t, force=args.force) for t in targets)
    print(f"\n{promoted} run(s) archived. Commit archived_runs/ so the numbers "
          f"they support stay reproducible.")


if __name__ == "__main__":
    main()
