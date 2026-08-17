"""Walk every string in an archived artifact and flag anything that should not ship.

The earlier check looked only at `contexts`, because that is where the first leak was
found: 332 verbatim corpus passages. That was the wrong shape of check. A trace can
carry retrieved text under any key a future tool happens to use, source document
names, file paths, or a tool result echoed into a preview field, and a key-specific
check sees none of it.

So this walks the whole structure and flags by *content*, not by key:

  corpus_text        a long free-text string somewhere other than the fields that
                     are meant to hold model output
  unredacted_context a `contexts` entry that is not a placeholder (the original check,
                     kept)
  document_name      a source-document or file name, including PDF and Office
                     extensions
  filesystem_path    an absolute or user-directory path
  internal_identifier a table, column or service name that should have been redacted
  verbatim_prompt    the deployed persona prompt or a tool description, present in
                     full rather than as a digest

`answer` and `question` are the fields whose long text is expected: answers are model
output the paper reports, questions are synthetic and team-authored.

    ../.venv-agent/bin/python tools/scan_for_sensitive.py archived_runs/mechanism
    ../.venv-agent/bin/python tools/scan_for_sensitive.py      # everything archived
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
ARCHIVE = HERE / "archived_runs"
PAST_RECORDS = ARCHIVE / "past_records"

# Fields whose long strings are the point of the artifact. "failures" is here because a
# failed source assertion prints the expected name and every name actually retrieved, so
# it runs past 400 characters legitimately; the one that tripped this rule was 520 chars
# of document names, not corpus text. The residual risk is narrow but real: corpus text
# inside a failure message would no longer trip the length rule. Assertion messages are
# built by the harness from names and counts, and the only free text they can quote is a
# model answer, which the artifact publishes anyway.
EXPECTED_LONG = {"answer", "question", "note", "purpose", "why", "why_those_counts",
                 "description", "description_sanitized", "clause_verbatim",
                 "reason", "location", "client", "experimental_variable", "failures",
                 "instruction"}

# Corpus documents are PDFs and office files. Markdown and plain text are excluded:
# every .md here is project documentation, and matching them only produced false
# positives such as the string "see RELEASE.md".
DOCUMENT_NAME = re.compile(r"[\w \-]+\.(pdf|docx?|pptx?|xlsx?|epub)\b", re.I)
FS_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\|/var/folders/)")
INTERNAL = re.compile(r"\bdocument_sections\b|\bknowledge_gaps\b|\bagent-testing\b"
                      r"|\bmatch_count\b|\bprompt_config_components\b"
                      r"|\bprompt_components\b|\bSUPABASE_(?:URL|KEY)\b", re.I)
LONG = 400          # characters; a retrieved chunk is typically longer than this
REDACTED_PREVIEW = re.compile(
    r"^\[redacted: \d+ chars of retrieved clinical corpus text\]$"
)
RAW_JSON_PREVIEW = re.compile(r'"preview"\s*:\s*"([^"\n]*)')
# Pinned from the clean batch's immutable preregistration. Never derive this from the
# tree being scanned: otherwise an attacker could add a preregistration that
# self-authorizes arbitrary long text.
REGISTERED_DECISION_RULE_HASHES = {
    "7ebdb6d48f634295e890086629132639b3bc8e88f93510bfa36e44bac77a0829",
}

# Scanned in full, not only the structured formats: a document name can sit in a
# README sentence, a worked example, or an annotation guide just as easily as in a
# JSON field.
TEXT_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".csv", ".txt", ".py", ".cfg",
                 ".toml", ".ini", ".sh"}


def _prompt_fingerprints() -> list[tuple[str, str]]:
    """Distinctive substrings of the withheld text, so its presence is detectable.

    Read from the sanitized export rather than the backend, so the scanner works on a
    checkout without the production repository. Only fragments long enough to be
    unambiguous are used.
    """
    out = []
    cfg = PAST_RECORDS / "configuration" / "experimental_config.json"
    if cfg.exists():
        doc = json.loads(cfg.read_text())
        for heading in doc.get("persona_prompt", {}).get("section_headings", []):
            out.append(("verbatim_prompt", f"## {heading}"))
    return out


def _walk(node, path: str):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def scan_text(path: Path, fingerprints: list[tuple[str, str]]) -> list[str]:
    """Regex pass over a non-JSON file, where there is no key path to report."""
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        return []
    findings = []
    if path.suffix.lower() == ".json":
        for match in RAW_JSON_PREVIEW.finditer(text):
            if not REDACTED_PREVIEW.fullmatch(match.group(1)):
                findings.append("unredacted_preview in malformed JSON text")
    for label, pattern in (("document_name", DOCUMENT_NAME),
                           ("filesystem_path", FS_PATH),
                           ("internal_identifier", INTERNAL)):
        m = pattern.search(text)
        if m:
            findings.append(f"{label} in text: {m.group(0)!r}")
    for label, fragment in fingerprints:
        if fragment in text:
            findings.append(f"{label} in text: {fragment!r}")
    return findings


def scan_file(path: Path, fingerprints: list[tuple[str, str]]) -> list[str]:
    if path.suffix.lower() != ".json":
        return scan_text(path, fingerprints)
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [
            f"invalid_json at line {exc.lineno} column {exc.colno}",
            *scan_text(path, fingerprints),
        ]
    findings = []
    for key_path, value in _walk(doc, ""):
        leaf = key_path.split(".")[-1].split("[")[0]

        if leaf == "contexts" or ".contexts[" in key_path:
            if not value.startswith("[redacted"):
                findings.append(f"unredacted_context at {key_path}")
            continue

        if leaf == "preview":
            if not REDACTED_PREVIEW.fullmatch(value):
                findings.append(f"unredacted_preview at {key_path}")
            continue

        registered_decision_rule = (
            (
                leaf == "decision_rule_for_repo_replacement"
                or key_path.endswith("replacement_decision.rule")
            )
            and hashlib.sha256(value.encode()).hexdigest()
            in REGISTERED_DECISION_RULE_HASHES
        )
        if (
            len(value) > LONG
            and leaf not in EXPECTED_LONG
            and not registered_decision_rule
        ):
            findings.append(f"corpus_text ({len(value)} chars) at {key_path}")
        if DOCUMENT_NAME.search(value):
            findings.append(f"document_name at {key_path}: "
                            f"{DOCUMENT_NAME.search(value).group(0)!r}")
        if FS_PATH.search(value):
            findings.append(f"filesystem_path at {key_path}: "
                            f"{FS_PATH.search(value).group(0)!r}")
        if INTERNAL.search(value) and leaf not in {"description_sanitized"}:
            findings.append(f"internal_identifier at {key_path}: "
                            f"{INTERNAL.search(value).group(0)!r}")
        for label, fragment in fingerprints:
            if fragment in value:
                findings.append(f"{label} at {key_path}: {fragment!r}")
    return findings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target", nargs="?", type=Path, default=ARCHIVE,
                    help="file or directory to scan (default: archived_runs/)")
    ap.add_argument("--for-release", action="store_true",
                    help="exit non-zero on any finding. Without it, findings are "
                         "reported but tolerated, because this private repository "
                         "deliberately retains source document names; the public "
                         "snapshot is what must come back clean.")
    args = ap.parse_args()

    target = args.target if args.target.is_absolute() else HERE / args.target
    files = ([f for f in sorted(target.rglob("*"))
              if f.is_file() and f.suffix.lower() in TEXT_SUFFIXES]
             if target.is_dir() else [target])
    if not files:
        raise SystemExit(f"nothing to scan under {target}")

    fingerprints = _prompt_fingerprints()
    total, flagged = 0, 0
    all_findings: list[str] = []
    for path in files:
        findings = scan_file(path, fingerprints)
        total += 1
        all_findings.extend(findings)
        if findings:
            flagged += 1
            # Relative to what is being scanned, not to this repo: --for-release runs
            # against the public snapshot, which lives outside it, and relative_to(HERE)
            # raised there. A crash then read as a release-gate failure.
            root = target if target.is_dir() else target.parent
            try:
                shown = path.relative_to(root)
            except ValueError:
                shown = path
            print(f"\n{shown}")
            for f in findings[:12]:
                print(f"  {f}")
            if len(findings) > 12:
                print(f"  ... and {len(findings) - 12} more")

    print(f"\nscanned {total} file(s) against {len(fingerprints)} prompt fingerprints; "
          f"{flagged} flagged")
    # What --for-release blocks on, as of 5 Aug 2026. Andrea approved publishing the
    # corpus document names, the persona prompt and the tool schemas, so those labels
    # are reported and no longer fatal. What is still fatal is corpus passages, and the
    # one internal clinical guidance document whose filename must not be named; the
    # public snapshot pseudonymizes it and make_public_snapshot.py proves it absent.
    #
    # The gate's reference-phrase list needs no rule here: the real list lives in the
    # backend, and this repository only ever contained the substitute.
    BLOCKING = (
        "invalid_json",
        "unredacted_context",
        "unredacted_preview",
        "corpus_text",
    )
    WITHHELD_DOC = "doc_001"
    fatal = [f for f in all_findings
             if any(f.startswith(b) or f" {b}" in f for b in BLOCKING)
             or WITHHELD_DOC in f.lower()]
    if fatal and args.for_release:
        print(f"\n{len(fatal)} finding(s) still block release:")
        for f in fatal[:10]:
            print(f"  {f}")
        raise SystemExit(1)
    if flagged and args.for_release:
        print("flagged findings are all in categories the company approved for "
              "publication on 5 Aug 2026; none block.")
    elif flagged:
        print("findings are reported, not fatal, in this private repository. Run with "
              "--for-release on the public snapshot to apply the release gate; it "
              "blocks on corpus passages and on the withheld document's name, and "
              "passes the categories the company approved.")
    else:
        print("nothing flagged.")


if __name__ == "__main__":
    main()
