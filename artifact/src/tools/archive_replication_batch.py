"""Archive a complete replication batch while removing retrieved text previews.

The discovery archive has a different schema and remains untouched. This importer
accepts one explicitly named replication batch, verifies its frozen run set, copies
only publication inputs, and replaces every trace ``preview`` with a length-bearing
placeholder. Runtime logs and backend-coupled runner code are never copied.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


PREVIEW_PLACEHOLDER = "[redacted: {n} chars of retrieved clinical corpus text]"
REDACTED_PREVIEW = re.compile(
    r"^\[redacted: \d+ chars of retrieved clinical corpus text\]$"
)
EQUALIZED_MODELS = ("gemini-2.5-flash", "gpt-5-mini", "claude-sonnet-5")
EQUALIZED_CONFIGS = ("base", "persona", "persona_tools", "mitigated")
HELDOUT_GROUPS = {
    "heldout-persona_no_tools": 5,
    "heldout-persona_tools": 5,
    "heldout-persona_tools_priority": 5,
    "original_priority_check-persona_tools_priority": 5,
    "non_safety-persona_tools": 3,
    "non_safety-persona_tools_priority": 3,
}


class ArchiveError(ValueError):
    """The requested source cannot produce a complete publication archive."""


def expected_run_names(batch: str) -> set[str]:
    if batch == "equalized":
        return {
            f"{model}-{config}-run{run}.json"
            for model in EQUALIZED_MODELS
            for config in EQUALIZED_CONFIGS
            for run in range(1, 9)
        }
    if batch == "heldout":
        return {
            f"{prefix}-run{run}.json"
            for prefix, count in HELDOUT_GROUPS.items()
            for run in range(1, count + 1)
        }
    raise ArchiveError(f"unknown batch: {batch!r}")


def _redact_previews(node) -> int:
    redacted = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "preview" and isinstance(value, str):
                if not REDACTED_PREVIEW.fullmatch(value):
                    node[key] = PREVIEW_PLACEHOLDER.format(n=len(value))
                    redacted += 1
            else:
                redacted += _redact_previews(value)
    elif isinstance(node, list):
        for value in node:
            redacted += _redact_previews(value)
    return redacted


def sanitize_document(doc: dict) -> int:
    """Redact trace previews in place and return the newly redacted count."""
    redacted = _redact_previews(doc)
    if redacted:
        doc["trace_previews_redacted"] = True
        summary = doc.setdefault("redaction_summary", {})
        summary["trace_previews"] = summary.get("trace_previews", 0) + redacted
    return redacted


def _metadata(batch: str) -> tuple[tuple[str, str], ...]:
    if batch == "equalized":
        return (
            ("plan.json", "plan.json"),
            ("preregistration.json", "preregistration.json"),
        )
    return (
        ("heldout_cases.yaml", "heldout_cases.yaml"),
        ("preregistration.json", "preregistration.json"),
        ("freeze_manifest.json", "freeze_manifest.json"),
        ("summary.json", "summary.json"),
        ("non_safety-wide-flags.tsv", "review/non_safety-wide-flags.tsv"),
    )


def _load_runs(source: Path, batch: str) -> dict[str, dict]:
    expected = expected_run_names(batch)
    missing = sorted(name for name in expected if not (source / name).is_file())
    if missing:
        noun = "run" if len(missing) == 1 else "runs"
        raise ArchiveError(
            f"missing {len(missing)} expected {noun}: {', '.join(missing[:5])}"
        )

    runs = {}
    for name in sorted(expected):
        try:
            doc = json.loads((source / name).read_text())
        except json.JSONDecodeError as exc:
            raise ArchiveError(f"invalid JSON in {name}: {exc}") from exc
        if not isinstance(doc, dict):
            raise ArchiveError(f"{name} is not a JSON object")
        records = doc.get("records")
        if batch == "equalized":
            if doc.get("status") != "complete" or doc.get("completed_cases") != 30:
                raise ArchiveError(f"incomplete equalized run: {name}")
            identity = next(
                (
                    (model, config, run)
                    for model in EQUALIZED_MODELS
                    for config in EQUALIZED_CONFIGS
                    for run in range(1, 9)
                    if name == f"{model}-{config}-run{run}.json"
                ),
                None,
            )
            if identity is None or (
                doc.get("model"),
                doc.get("config"),
                doc.get("run_index"),
            ) != identity:
                raise ArchiveError(f"run identity does not match filename: {name}")
            if not isinstance(records, list) or len(records) != 30:
                raise ArchiveError(f"{name}: expected 30 records")
            case_ids = [record.get("case_id") for record in records]
            if None in case_ids or len(set(case_ids)) != 30:
                raise ArchiveError(f"{name}: expected 30 unique case identities")
        else:
            prefix, run_text = name.removesuffix(".json").rsplit("-run", 1)
            if prefix.startswith("heldout-"):
                expected_kind, expected_config = "heldout", prefix.removeprefix("heldout-")
                expected_records = 30
            elif prefix.startswith("original_priority_check-"):
                expected_kind = "original_priority_check"
                expected_config = prefix.removeprefix("original_priority_check-")
                expected_records = 30
            else:
                expected_kind, expected_config = "non_safety", prefix.removeprefix(
                    "non_safety-"
                )
                expected_records = 59
            identity = (expected_kind, expected_config, int(run_text))
            if (
                doc.get("kind"),
                doc.get("config"),
                doc.get("run_index"),
            ) != identity:
                raise ArchiveError(f"run identity does not match filename: {name}")
            if not doc.get("completed") or not isinstance(records, list):
                raise ArchiveError(f"incomplete heldout run: {name}")
            if len(records) != expected_records:
                raise ArchiveError(f"{name}: expected {expected_records} records")
        runs[name] = doc
    return runs


def archive_batch(source: Path, destination: Path, batch: str) -> dict[str, int]:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        raise ArchiveError(f"source directory does not exist: {source}")
    if destination.exists():
        raise ArchiveError(f"destination already exists: {destination}")

    metadata = _metadata(batch)
    missing_metadata = [src for src, _ in metadata if not (source / src).is_file()]
    if missing_metadata:
        raise ArchiveError(f"missing metadata: {', '.join(missing_metadata)}")
    runs = _load_runs(source, batch)

    destination.mkdir(parents=True)
    for src_name, dest_name in metadata:
        dest = destination / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / src_name, dest)

    runs_dir = destination / "runs"
    runs_dir.mkdir()
    redacted = 0
    for name, doc in runs.items():
        redacted += sanitize_document(doc)
        (runs_dir / name).write_text(json.dumps(doc, indent=2) + "\n")

    return {
        "run_files": len(runs),
        "trace_previews_redacted": redacted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--batch", required=True, choices=("equalized", "heldout"))
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = archive_batch(args.source, args.destination, args.batch)
    except ArchiveError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        f"archived {result['run_files']} {args.batch} runs; "
        f"redacted {result['trace_previews_redacted']} trace previews"
    )


if __name__ == "__main__":
    main()
