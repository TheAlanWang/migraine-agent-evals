"""Gate the artifact release. Exits non-zero unless every condition holds.

Written because the release plan recorded in the paper was unsafe: it said this
repository would be flipped public once the company approved. It cannot be. Eight
commits early in its history contain 332 unredacted passages of proprietary
clinical corpus text, archived before the redaction step existed. A later visibility
check found the GitHub remote public with one affected blob still matching `main`;
deleting or redacting the working-tree files does not remove that exposed history.
Remote visibility and incident response therefore have to be handled separately.

So the release path is a fresh repository containing a reviewed snapshot with a new
first commit, and this script is the check that runs before that snapshot is cut.

    ../.venv-agent/bin/python tools/check_release_ready.py
    ../.venv-agent/bin/python tools/check_release_ready.py --history   # slow, full scan
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
REPOSITORY = ROOT.parent
ARCHIVE = HERE / "archived_runs"
PAST_RECORDS = ARCHIVE / "past_records"
DISCOVERY_MANIFEST = PAST_RECORDS / "results_manifest.json"

# Paths that must never be tracked, whatever a future .gitignore says. Matched as
# path components, not substrings: "runs/" as a substring also matches the
# legitimate "archived_runs/", which is the one directory that is meant to ship.
FORBIDDEN_PREFIXES = ("runs/", "artifact/runs/", "unredacted_backup/",
                      "artifact/unredacted_backup/")
FORBIDDEN_SUBSTRINGS = ("annotation_key", ".env")


def _sh(*args: str) -> str:
    result = subprocess.run(
        args,
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({' '.join(args)}): {result.stderr.strip()}"
        )
    return result.stdout


def is_git_repository() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
    )
    return (
        result.returncode == 0
        and Path(result.stdout.strip()).resolve() == REPOSITORY.resolve()
    )


def _unredacted(doc) -> int:
    if not isinstance(doc, dict):
        return 0
    total = sum(1 for case in doc.get("cases", [])
                for turn in (case.get("turns") or [])
                for ctx in (turn.get("contexts") or [])
                if isinstance(ctx, str) and not ctx.startswith("[redacted"))

    def previews(node) -> int:
        if isinstance(node, dict):
            return sum(
                (
                    int(
                        key == "preview"
                        and isinstance(value, str)
                        and not re.fullmatch(
                            r"\[redacted: \d+ chars of retrieved clinical corpus text\]",
                            value,
                        )
                    )
                    + previews(value)
                )
                for key, value in node.items()
            )
        if isinstance(node, list):
            return sum(previews(value) for value in node)
        return 0

    return total + previews(doc)


def check_working_tree() -> list[str]:
    bad = []
    total = 0
    for path in ARCHIVE.rglob("*.json"):
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        n = _unredacted(doc)
        total += n
        if n:
                bad.append(f"{path.relative_to(HERE)}: {n} unredacted contexts")
    print(f"  working tree: {total} unredacted contexts/previews in archived_runs/")
    return bad


def check_tracked_files() -> list[str]:
    if not is_git_repository():
        print("  tracked files: unavailable (snapshot has no Git repository)")
        return ["tracked-file gate requires a freshly initialized Git repository"]
    tracked = _sh("git", "ls-files").splitlines()
    hits = [f for f in tracked
            if f.startswith(FORBIDDEN_PREFIXES)
            or any(sub in f for sub in FORBIDDEN_SUBSTRINGS)]
    print(f"  tracked files: {len(tracked)}, "
          f"{len(hits)} matching forbidden patterns")
    return [f"forbidden path is tracked: {f}" for f in hits]


def check_history() -> list[str]:
    """Scan every commit. Slow, so opt-in, but it is the whole point of the gate."""
    if not is_git_repository():
        print("  history: unavailable (snapshot has no Git repository)")
        return ["history gate requires a fresh Git repository and initial commit"]
    commits = _sh("git", "rev-list", "--all").split()
    if not commits:
        print("  history: Git repository has no commits")
        return ["history gate requires an initial commit"]
    dirty = []
    for commit in commits:
        files = [f for f in _sh("git", "ls-tree", "-r", "--name-only", commit).splitlines()
                 if (f.startswith("archived_runs/") or
                     f.startswith("artifact/archived_runs/")) and
                 f.endswith(".json")]
        n = 0
        for f in files:
            try:
                n += _unredacted(json.loads(_sh("git", "show", f"{commit}:{f}")))
            except json.JSONDecodeError:
                continue
        if n:
            subject = _sh("git", "log", "-1", "--format=%s", commit).strip()
            dirty.append(f"{commit[:8]} carries {n} unredacted contexts: {subject[:50]}")
    print(f"  history: {len(commits)} commits scanned, {len(dirty)} carry corpus text")
    if dirty:
        dirty.append("=> publish a fresh repository with a new first commit; "
                     "do not make this one public")
    return dirty


def check_sensitive_scan() -> list[str]:
    """Content-based scan, not key-based.

    The original check looked only at `contexts`, which is where the first leak was
    found, and that shape of check missed the next one: 98 source document names,
    including an internal guideline filename, sitting in `sources` and inside trace
    entries across 16 archived files. Whether those may ship is a company decision,
    so they are reported here and blocked at snapshot time.
    """
    r = subprocess.run([sys.executable, str(ROOT / "src" / "tools" /
                                            "scan_for_sensitive.py"),
                        "--for-release"],
                       cwd=HERE, capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() if "flagged" in l]
    print(f"  content scan: {tail[-1] if tail else 'scanner produced no summary'}")
    if r.returncode:
        return ["sensitive-content scan found an unredacted context, trace preview, "
                "or other blocking value"]
    return []


def check_paper_numbers() -> list[str]:
    r = subprocess.run([sys.executable, str(HERE / "reproduce.py")],
                       cwd=HERE, capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() if "checks run" in l]
    print(f"  paper numbers: {tail[0] if tail else 'verifier produced no summary'}")
    problems = []
    if r.returncode != 0:
        problems.append("verify_paper_numbers.py fails; the paper cites numbers "
                        "the archive does not support")
    if "KNOWN GAP" in r.stdout:
        problems.append("verify_paper_numbers.py still reports a KNOWN GAP")
    return problems


def check_replication_batches() -> list[str]:
    problems = []
    for command, label in (
        ("verify-equalized", "equalized replication"),
        ("verify-heldout", "heldout replication"),
    ):
        r = subprocess.run(
            [sys.executable, str(HERE / "reproduce.py"), command],
            cwd=HERE,
            capture_output=True,
            text=True,
        )
        tail = [line for line in r.stdout.splitlines() if "checks run" in line]
        print(f"  {label}: {tail[-1] if tail else 'verifier produced no summary'}")
        if r.returncode:
            problems.append(f"{label} verifier fails")
    return problems


def check_archive_layout() -> list[str]:
    """Keep historical records organized and prevent silent evidence loss."""
    loose = sorted(path.name for path in ARCHIVE.glob("*.json"))
    required = (
        PAST_RECORDS / "discovery_runs" / "2026-07-21T15-30-52Z.json",
        PAST_RECORDS / "ladder" / "persona_ladder-3run-original.json",
    )
    problems = [f"loose archive JSON: {name}" for name in loose]
    problems.extend(
        "required historical record missing: "
        f"{path.relative_to(ARCHIVE).as_posix()}"
        for path in required
        if not path.exists()
    )
    present = sum(path.exists() for path in required)
    print(f"  archive layout: {len(loose)} loose JSON file(s), "
          f"{present}/{len(required)} retained records present")
    return problems


def check_manifest() -> list[str]:
    path = DISCOVERY_MANIFEST
    if not path.exists():
        return ["no past_records/results_manifest.json; run freeze_results.py"]
    m = json.loads(path.read_text())
    head = (
        _sh("git", "rev-parse", "HEAD").strip()
        if is_git_repository()
        and _sh("git", "rev-list", "--all").strip()
        else "<uncommitted snapshot>"
    )
    print(f"  manifest: generated {m.get('generated')} at "
          f"{str(m.get('evals_commit'))[:8]} (HEAD is {head[:8]})")
    problems = []
    for name, digest in (m.get("inputs") or {}).items():
        import hashlib
        p = PAST_RECORDS / name
        if not p.exists():
            problems.append(f"manifest input missing: {name}")
        elif hashlib.sha256(p.read_bytes()).hexdigest()[:16] != digest:
            problems.append(f"manifest is stale: {name} changed since it was frozen")
    return problems


# Single record of what the company has and has not approved, so the scanners, the
# documents and this gate stop giving three different answers. Counts are not written
# here; _source_counts() generates them, because three files previously carried three
# different numbers.
APPROVED = [
    ("open-sourcing the evaluation suite", "Andrea Pope, 5 Aug 2026"),
    ("the deployed persona prompt, verbatim", "Andrea Pope, 5 Aug 2026"),
    ("the tool schemas and descriptions, verbatim", "Andrea Pope, 5 Aug 2026"),
    ("the published research paper names", "Andrea Pope, 5 Aug 2026"),
]
WITHHELD = [
    ("the in-house guidance document's name",
     "withheld by agreement; pseudonymized, and cases.yaml asserts on it, so both "
     "sides are substituted"),
    ("retrieved corpus passages",
     "publisher copyright, which no party here can waive; replaced by their length"),
    ("the safety gate's reference-phrase list",
     "security, not commercial: publishing it is a bypass recipe"),
    ("the clinical review's blinding key",
     "that review has not happened; publishing it would settle it in advance"),
]
NOT_CHECKABLE_HERE = [
    "an existing remote's visibility, forks, caches, and historical exposure are "
    "outside this local gate; publish only from a fresh reviewed history",
]



def print_approvals() -> None:
    print("  approved for publication:")
    for what, who in APPROVED:
        print(f"    {what}  ({who})")
    print("  withheld:")
    for what, why in WITHHELD:
        print(f"    {what}: {why}")
    for note in NOT_CHECKABLE_HERE:
        print(f"  note: {note}")


def _source_counts() -> dict:
    """Distinct source documents in the archives, generated rather than remembered.

    Documents, not spellings: cases.yaml writes the bare stem in expect_sources while
    archived runs write the full relative path, so counting strings double-counts.
    """
    import yaml
    names: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("sources", "expect_sources") and isinstance(v, list):
                    names.update(x for x in v if isinstance(x, str) and x.strip())
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for path in ARCHIVE.rglob("*.json"):
        try:
            walk(json.loads(path.read_text()))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    cases = HERE / "cases.yaml"
    if cases.exists():
        for case in yaml.safe_load(cases.read_text()):
            names.update(case.get("expect_sources") or [])

    docs = {Path(n).stem.lower() for n in names}
    # The private audit tree contains both the old opaque name and the original
    # identity reintroduced by the replication outputs. They identify one document;
    # the public snapshot substitutes the latter back to doc_001.
    private_aliases = {d for d in docs if "doc_001" in d}
    if private_aliases:
        docs.difference_update(private_aliases)
        docs.add("doc_001")
    withheld = {d for d in docs if "doc_001" in d}
    return {"documents": len(docs), "withheld": len(withheld),
            "published": len(docs) - len(withheld)}


def check_documentation() -> list[str]:
    """Do the shipped documents still describe the shipped code?

    Every failure this catches was found by a human reading the files: README called
    the retired composite heuristic the paper's outcome, quoted 61 verifier checks when
    there were 81, pointed at a figure the paper no longer has, and said the paired
    analysis needs no SciPy next to a script that imports it. DATA_CARD said the prompt
    was withheld after it was published, and three files carried three different source
    counts. None of it was caught by a gate, because every gate here asks whether
    something sensitive leaked, and none asked whether the prose is still true.
    """
    print("  documentation:", end=" ")
    problems = []
    counts = _source_counts()

    readme = ((REPOSITORY / "README.md").read_text()
              if (REPOSITORY / "README.md").exists() else "")
    card = (HERE / "DATA_CARD.md").read_text() if (HERE / "DATA_CARD.md").exists() else ""

    # The primary outcome must not be attributed to the retired heuristic.
    for name, text in (("README.md", readme), ("DATA_CARD.md", card)):
        for phrase in ("crisis_safe.py`** — the outcome heuristic used in the paper",
                       "crisis-safe outcome heuristic used throughout the paper"):
            if phrase in text:
                problems.append(f"{name} still calls crisis_safe the paper's outcome")

    # Verifier check count, read from the verifier rather than from memory.
    r = subprocess.run([sys.executable, str(HERE / "reproduce.py")],
                       cwd=HERE, capture_output=True, text=True)
    m = re.search(r"(\d+) checks run", r.stdout)
    if m:
        n = m.group(1)
        stale = re.findall(r"(\d+) checks at present", readme)
        if stale and n not in stale:
            problems.append(f"README says {stale} checks, verifier runs {n}")

    # Source counts, generated above.
    if card:
        if str(counts["documents"]) not in card:
            problems.append(f"DATA_CARD does not state the real document count "
                            f"({counts['documents']})")
        if str(counts["published"]) not in card:
            problems.append(f"DATA_CARD does not state the real published count "
                            f"({counts['published']})")

    # Figure numbers the paper no longer has, and a SciPy claim the code contradicts.
    if "Fig. 4" in readme or "Fig. 3" in readme:
        problems.append("README cites a figure number the paper does not have")
    pa = HERE / "src" / "paper" / "paired_analysis.py"
    if pa.exists() and "scipy" in pa.read_text().lower() and "no SciPy" in readme:
        problems.append("README says no SciPy; paired_analysis.py imports it")

    print(f"{counts['documents']} documents "
          f"({counts['published']} published, {counts['withheld']} withheld); "
          f"{len(problems)} inconsistency(ies)")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--history", action="store_true",
                    help="scan every commit for corpus text (slow)")
    args = ap.parse_args()

    print("release gates\n")
    problems: list[str] = []
    problems += check_working_tree()
    problems += check_sensitive_scan()
    problems += check_tracked_files()
    problems += check_archive_layout()
    problems += check_manifest()
    problems += check_paper_numbers()
    problems += check_replication_batches()
    problems += check_documentation()
    if args.history:
        problems += check_history()
    else:
        print("  history: skipped (pass --history; required before any release)")

    print()
    if problems:
        print(f"NOT READY: {len(problems)} blocking issue(s)")
        for p in problems:
            print(f"  - {p}")
        print()
        print_approvals()
        raise SystemExit(1)
    print("all automated gates pass.")
    print()
    print_approvals()


if __name__ == "__main__":
    main()
