#!/usr/bin/env python3
"""Single command-line entry point for this research artifact."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(script: Path, args: list[str]) -> int:
    return subprocess.call([sys.executable, str(script), *args], cwd=ROOT)


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "paper"
    args = sys.argv[2:]

    if command in {"-h", "--help", "help"}:
        print(
            "usage: python artifact/reproduce.py "
            "[paper|suite|test|paired|verify-equalized|verify-heldout] [options]\n\n"
            "  paper   verify the numbers reported in the paper (default)\n"
            "  suite   run the 87-case suite; uses the toy agent if no options follow\n"
            "  test    test the Level-2 concept matcher\n"
            "  paired  rerun the detailed paired analysis\n"
            "  verify-equalized  verify the 32-run Gemini balanced replication\n"
            "  verify-heldout    verify the 26-run heldout replication"
        )
        return 0

    if command in {"paper", "verify"}:
        return run(ROOT / "src" / "paper" / "verify_paper_numbers.py", args)

    if command == "suite":
        if not args:
            args = [
                "--agent", "example_agent:run_agent",
                "--level", "1",
                "--retrieval-tool", "search",
            ]
        return run(ROOT / "src" / "evaluation" / "harness.py", args)

    if command == "test":
        return run(ROOT / "src" / "evaluation" / "test_harness.py", args)

    if command == "paired":
        return run(ROOT / "src" / "paper" / "paired_analysis.py", args)

    if command == "verify-equalized":
        return run(ROOT / "src" / "tools" / "verify_equalized_ladder.py", args)

    if command == "verify-heldout":
        return run(ROOT / "src" / "tools" / "verify_heldout_tool_calling.py", args)

    print(f"unknown command: {command!r}; run "
          "'python artifact/reproduce.py --help'",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
