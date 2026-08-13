"""Build a sanitized public snapshot in a new directory. Never edits this repo.

Two reasons this is a copy rather than a rewrite. The private repository is the
internal audit trail: replacing source document names in place would destroy the
ability to check later what was actually retrieved. And this repository's history
carries 332 unredacted corpus passages in its first eight commits, so the public
artifact has to be a fresh tree with a new first commit regardless.

What it does to source document identities: replaces each with a stable opaque
identifier, `doc_001`, `doc_002`, and so on. Deliberately *not* a hash of the
filename. Research paper titles are guessable, so a hash is reversible by dictionary
attack against any corpus of published titles; a counter carries no information about
what it replaces. The assignment is deterministic (sorted by the original name) so
the same corpus always produces the same mapping.

The mapping is written outside the snapshot. The public tree keeps only the opaque
identifiers, and no digest of any original name, since a per-name digest is the same
dictionary-attack problem. The mapping file as a whole gets one checksum, recorded
privately, so a future disclosure can be shown to match what was published against.

Substitution covers every text file, not only JSON and YAML: `cases.yaml` asserts on a
document name in `expect_sources`, and the README, worked examples and annotation
material quote names in prose. Matching covers the full relative path, the basename,
the stem without extension, case-normalized forms, and URL-decoded forms.

It also removes every retrieved-text `preview` from legacy trace events. New
replication imports are already sanitized, but older discovery files predate that
rule; the private audit tree remains unchanged while the public copy receives the
same length-bearing placeholders.

    ../.venv-agent/bin/python make_public_snapshot.py --out ../../public-snapshot
    ../.venv-agent/bin/python make_public_snapshot.py --out ... --keep-source-names
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[2]
HERE = ARTIFACT.parent

# Never copied into a public snapshot, whatever .gitignore currently says.
# round2_hold_back is material deliberately kept from the clinical reviewer until a
# second round; publishing it decides that round in advance.
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "unredacted_backup",
                "round2_hold_back", "clinical_review"}
# The per-release provenance.json is meant to ship: it is the reproducibility
# record for the sheet annotators actually received.
#
# task4_key.json is the clinical review's blinding key. The review has not happened
# yet, and A/B order plus the withheld configuration is the whole reason its answers
# will mean anything, so publishing the key would settle the review before it starts.
# Revisit once the review is complete, when the key becomes a record rather than a leak.
# RELEASE.md is about this private repository and opens by saying it must not be made
# public. Copied into the snapshot it tells a reader of the public repo the opposite of
# the truth. The public tree's own provenance is in DATA_CARD.md and the root commit.
EXCLUDE_NAMES = {"annotation_key.csv", ".env", "task4_key.json", ".DS_Store",
                 "RELEASE.md"}
EXCLUDE_RELATIVE_PREFIXES = {
    "runs/",
    "artifact/runs/",
    "annotation/release-",
    "artifact/annotation/release-",
}
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".csv", ".txt", ".cfg",
                 ".toml", ".ini", ".sh"}
PREVIEW_PLACEHOLDER = "[redacted: {n} chars of retrieved clinical corpus text]"
REDACTED_PREVIEW = re.compile(
    r"^\[redacted: \d+ chars of retrieved clinical corpus text\]$"
)


def _collect_source_names() -> list[str]:
    """Every source document identity appearing anywhere in this repo."""
    names: set[str] = set()

    def from_json(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("sources", "expect_sources") and isinstance(v, list):
                    names.update(x for x in v if isinstance(x, str) and x.strip())
                else:
                    from_json(v)
        elif isinstance(node, list):
            for v in node:
                from_json(v)

    for path in (HERE / "artifact" / "archived_runs").rglob("*.json"):
        try:
            from_json(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue

    import yaml
    for case in yaml.safe_load((HERE / "artifact" / "cases.yaml").read_text()) or []:
        names.update(case.get("expect_sources") or [])

    return sorted(names)


def _variants(name: str) -> list[str]:
    """Forms the same identity can take in text, longest first so nesting is safe."""
    base = Path(name).name
    out = {name, base, Path(name).stem, Path(base).stem,
           urllib.parse.quote(name), urllib.parse.unquote(name),
           name.replace("/", "\\")}
    out = {v for v in out if len(v) > 6}          # too short to match unambiguously
    return sorted(out, key=len, reverse=True)


def build_mapping(names: list[str]) -> dict[str, str]:
    """Original identity -> opaque id, one id per document rather than per spelling.

    The same document arrives in more than one form: cases.yaml writes the bare stem
    in expect_sources, archived runs write the full relative path. Assigning an id per
    string would publish one document as two. Grouping by stem fixes that, and sorting
    the group keys keeps the assignment reproducible for a given corpus.
    """
    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(Path(name).stem.lower(), []).append(name)
    mapping = {}
    for i, key in enumerate(sorted(groups), 1):
        for name in groups[key]:
            mapping[name] = f"doc_{i:03d}"
    return mapping


def _sub_json(node, mapping: dict[str, str], counter: list[int]):
    """Substitute inside a parsed structure, not in the serialized text.

    Doing it on raw text silently misses any identity whose JSON encoding differs
    from its value: a title containing a quote appears as \\" in the file, and
    re.escape of the decoded string then matches nothing. Three of 101 names were
    missed that way, all with escaped quotes, a non-breaking space or a U+2010
    hyphen, and the acceptance check is what caught it.
    """
    if isinstance(node, dict):
        return {k: _sub_json(v, mapping, counter) for k, v in node.items()}
    if isinstance(node, list):
        return [_sub_json(v, mapping, counter) for v in node]
    if isinstance(node, str):
        for variant, alias in sorted(
                ((v, a) for name, a in mapping.items() for v in _variants(name)),
                key=lambda pair: len(pair[0]), reverse=True):
            if variant.lower() in node.lower():
                pattern = re.compile(re.escape(variant), re.I)
                node, k = pattern.subn(alias, node)
                counter[0] += k
        return node
    return node


def _substitute(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    n = 0
    # Longest variants across all names first, so a stem does not pre-empt a path.
    pairs = sorted(((v, alias) for name, alias in mapping.items()
                    for v in _variants(name)),
                   key=lambda p: len(p[0]), reverse=True)
    for variant, alias in pairs:
        pattern = re.compile(re.escape(variant), re.I)
        text, k = pattern.subn(alias, text)
        n += k
    return text, n


def redact_previews(node) -> int:
    """Replace every non-placeholder preview in a parsed JSON document."""
    redacted = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "preview" and isinstance(value, str):
                if not REDACTED_PREVIEW.fullmatch(value):
                    node[key] = PREVIEW_PLACEHOLDER.format(n=len(value))
                    redacted += 1
            else:
                redacted += redact_previews(value)
    elif isinstance(node, list):
        for value in node:
            redacted += redact_previews(value)
    return redacted


def refresh_manifest_inputs(artifact: Path) -> int:
    """Refresh input digests after publication-only redaction/pseudonymization."""
    refreshed = 0
    archive = artifact / "archived_runs"
    for manifest_path in archive.rglob("results_manifest.json"):
        manifest = json.loads(manifest_path.read_text())
        inputs = manifest.get("inputs") or {}
        changed = False
        for relative, old_digest in inputs.items():
            path = manifest_path.parent / relative
            if not path.is_file():
                raise RuntimeError(
                    f"manifest input missing after snapshot copy: {path}"
                )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:len(old_digest)]
            if digest != old_digest:
                inputs[relative] = digest
                refreshed += 1
                changed = True
        if changed:
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return refreshed


def excluded_from_snapshot(relative: Path) -> bool:
    relative_text = relative.as_posix()
    return (
        any(part in EXCLUDE_DIRS for part in relative.parts)
        or any(
            relative_text.startswith(prefix)
            for prefix in EXCLUDE_RELATIVE_PREFIXES
        )
        or relative.name in EXCLUDE_NAMES
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=Path,
                    help="target directory for the snapshot; must not exist")
    ap.add_argument("--mapping", type=Path,
                    help="where to write the private mapping (default: alongside "
                         "--out, as a sibling, so it is never inside the snapshot)")
    ap.add_argument("--keep-source-names", action="store_true",
                    help="skip pseudonymization, for when the company has approved "
                         "publishing document identities")
    ap.add_argument("--withhold", action="append", metavar="SUBSTRING", default=[],
                    help="pseudonymize only identities containing this substring and "
                         "keep every other name as-is; repeatable. The case Andrea "
                         "approved on 5 Aug 2026: the corpus is published literature "
                         "whose titles carry no company information, while one internal "
                         "clinical guidance document must not be named.")
    args = ap.parse_args()
    if args.keep_source_names and args.withhold:
        raise SystemExit("--keep-source-names keeps everything; --withhold contradicts it")

    out = args.out.resolve()
    if out.exists():
        raise SystemExit(f"{out} exists; point --out at a fresh directory")
    if HERE in out.parents or out == HERE:
        raise SystemExit("refusing to write the snapshot inside this repository")

    names = _collect_source_names()
    if args.keep_source_names:
        mapping, kept = {}, names
    elif args.withhold:
        # Publishing 1,098 real titles and hiding one does not conceal that the hidden
        # one is the internal guideline: the paper says the corpus is research papers
        # plus one clinical guidance document, so its role is already public. What is
        # withheld is its filename, which is the part that is company information.
        hidden = [n for n in names if any(w.lower() in n.lower() for w in args.withhold)]
        if not hidden:
            raise SystemExit(f"--withhold matched nothing among {len(names)} identities")
        mapping = build_mapping(hidden)
        kept = [n for n in names if n not in mapping]
    else:
        mapping, kept = build_mapping(names), []
    print(f"{len(names)} source document identities found; "
          f"{len(mapping)} pseudonymized, {len(kept)} kept as-is")
    for original, opaque in sorted(mapping.items()):
        print(f"  withheld: {original!r} -> {opaque}")

    copied = substituted = previews_redacted = 0
    for src in sorted(HERE.rglob("*")):
        rel = src.relative_to(HERE)
        if excluded_from_snapshot(rel):
            continue
        if not src.is_file():
            continue
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".json":
            try:
                doc = json.loads(src.read_text())
            except (UnicodeDecodeError, json.JSONDecodeError):
                shutil.copy2(src, dest)
                copied += 1
                continue
            counter = [0]
            if mapping:
                doc = _sub_json(doc, mapping, counter)
            redacted = redact_previews(doc)
            if counter[0] or redacted:
                dest.write_text(json.dumps(doc, indent=2) + "\n")
            else:
                shutil.copy2(src, dest)
            substituted += counter[0]
            previews_redacted += redacted
        elif mapping and src.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = src.read_text()
            except UnicodeDecodeError:
                shutil.copy2(src, dest)
                copied += 1
                continue
            new, n = _substitute(text, mapping)
            dest.write_text(new)
            substituted += n
        else:
            shutil.copy2(src, dest)
        copied += 1

    refreshed = refresh_manifest_inputs(out / "artifact")
    print(f"{copied} file(s) copied, {substituted} identity occurrence(s) replaced, "
          f"{previews_redacted} trace preview(s) redacted, "
          f"{refreshed} manifest digest(s) refreshed")

    if mapping:
        mapping_path = (args.mapping or out.parent /
                        f"{out.name}-source-name-mapping.json").resolve()
        if out in mapping_path.parents or mapping_path.is_relative_to(out):
            raise SystemExit("the mapping must not live inside the snapshot")
        payload = {
            "note": "Private. Maps original source document identities to the opaque "
                    "identifiers used in the public snapshot. Not to be published, and "
                    "no per-name digest is published either, since research titles are "
                    "guessable and a per-name hash is reversible by dictionary attack.",
            "snapshot": str(out),
            "mapping": mapping,
        }
        mapping_path.write_text(json.dumps(payload, indent=2))
        digest = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
        print(f"mapping -> {mapping_path}")
        print(f"mapping file sha256 (record this privately): {digest}")

    # ---- acceptance checks on the snapshot --------------------------------
    print("\nacceptance checks")
    problems = []

    if mapping:
        leaked = []
        for path in out.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            if path.suffix.lower() == ".json":
                try:                      # compare decoded values, not the encoding
                    text = json.dumps(json.loads(text), ensure_ascii=False)
                except json.JSONDecodeError:
                    pass
            for name in mapping:          # only the withheld ones can leak
                for variant in _variants(name):
                    if re.search(re.escape(variant), text, re.I):
                        leaked.append(f"{path.relative_to(out)}: {variant!r}")
                        break
        print(f"  original identities remaining: {len(leaked)}")
        problems += [f"identity still present: {x}" for x in leaked[:10]]

        import yaml
        snapshot_cases = yaml.safe_load((out / "artifact" / "cases.yaml").read_text()) or []
        asserted = [s for c in snapshot_cases for s in (c.get("expect_sources") or [])]
        bad = [s for s in asserted if not re.fullmatch(r"doc_\d{3}", s)]
        print(f"  expect_sources entries: {len(asserted)}, "
              f"{len(bad)} not opaque identifiers")
        problems += [f"expect_sources not pseudonymized: {s}" for s in bad]

    r = subprocess.run(["python3", "artifact/src/tools/scan_for_sensitive.py",
                        "--for-release", "archived_runs"], cwd=out,
                       capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() if "flagged" in l]
    print(f"  content scan: {tail[-1] if tail else 'no summary'}")
    if r.returncode != 0:
        problems.append("the sensitive-content scan fails on the snapshot")

    print()
    if problems:
        print(f"NOT PUBLISHABLE: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    print("snapshot passes the automated checks.")
    print("Company approval of what may be published is on record; see the APPROVED "
          "list in artifact/src/tools/check_release_ready.py. Before publication, "
          "review the "
          "generated snapshot itself and then:")
    print("  - run artifact/reproduce.py inside the snapshot, to confirm "
          "pseudonymization changed no reported number.")


if __name__ == "__main__":
    main()
