from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from archive_replication_batch import (  # noqa: E402
    ArchiveError,
    archive_batch,
    expected_run_names,
    sanitize_document,
)


MODELS = ("gemini-2.5-flash", "gpt-5-mini", "claude-sonnet-5")
CONFIGS = ("base", "persona", "persona_tools", "mitigated")


class SanitizeDocumentTests(unittest.TestCase):
    def test_redacts_trace_previews_and_preserves_publishable_fields(self):
        preview = "verbatim retrieved clinical corpus text"
        doc = {
            "status": "complete",
            "records": [{
                "question": "Synthetic question",
                "answer": "Model answer",
                "sources": ["research/example.pdf"],
                "trace": [{
                    "event": "tool_result",
                    "preview": preview,
                    "nested": {"preview": "second preview"},
                }],
            }],
        }

        count = sanitize_document(doc)

        self.assertEqual(count, 2)
        record = doc["records"][0]
        self.assertEqual(record["question"], "Synthetic question")
        self.assertEqual(record["answer"], "Model answer")
        self.assertEqual(record["sources"], ["research/example.pdf"])
        self.assertEqual(
            record["trace"][0]["preview"],
            f"[redacted: {len(preview)} chars of retrieved clinical corpus text]",
        )
        self.assertEqual(
            record["trace"][0]["nested"]["preview"],
            "[redacted: 14 chars of retrieved clinical corpus text]",
        )
        self.assertTrue(doc["trace_previews_redacted"])
        self.assertEqual(doc["redaction_summary"]["trace_previews"], 2)

    def test_sanitization_is_idempotent(self):
        doc = {
            "records": [{
                "trace": [{
                    "preview": "[redacted: 12 chars of retrieved clinical corpus text]",
                }],
            }],
            "trace_previews_redacted": True,
            "redaction_summary": {"trace_previews": 1},
        }

        self.assertEqual(sanitize_document(doc), 0)
        self.assertEqual(doc["redaction_summary"]["trace_previews"], 1)

    def test_redacts_preview_that_only_mimics_the_placeholder_prefix(self):
        value = "[redacted: forged prefix] followed by private corpus text"
        doc = {"records": [{"trace": [{"preview": value}]}]}

        self.assertEqual(sanitize_document(doc), 1)
        self.assertEqual(
            doc["records"][0]["trace"][0]["preview"],
            f"[redacted: {len(value)} chars of retrieved clinical corpus text]",
        )


class ArchiveBatchTests(unittest.TestCase):
    def _write_equalized_source(self, root: Path, complete: bool = True) -> None:
        (root / "plan.json").write_text('{"frozen": true}\n')
        (root / "preregistration.json").write_text('{"objective": "test"}\n')
        cells = [
            (model, config, run, f"{model}-{config}-run{run}.json")
            for model in MODELS
            for config in CONFIGS
            for run in range(1, 9)
        ]
        if not complete:
            cells.pop()
        for model, config, run, name in cells:
            (root / name).write_text(json.dumps({
                "status": "complete",
                "model": model,
                "config": config,
                "run_index": run,
                "completed_cases": 30,
                "records": [
                    {
                        "case_id": f"case-{case}",
                        "question": "Synthetic",
                        "answer": "Published output",
                        "sources": ["research/example.pdf"],
                        "trace": [{"preview": "private retrieved text"}],
                    }
                    for case in range(30)
                ],
            }))
        (root / "runner.py").write_text("SECRET = 'backend coupling'\n")
        (root / "one-run.log").write_text("runtime details\n")
        (root / "summary-output.txt").write_text("console output\n")

    def test_equalized_import_is_complete_sanitized_and_excludes_runtime_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "archive"
            source.mkdir()
            self._write_equalized_source(source)
            plan_bytes = (source / "plan.json").read_bytes()

            result = archive_batch(source, destination, "equalized")

            self.assertEqual(result["run_files"], 96)
            self.assertEqual(result["trace_previews_redacted"], 96 * 30)
            self.assertEqual((destination / "plan.json").read_bytes(), plan_bytes)
            self.assertTrue((destination / "preregistration.json").exists())
            self.assertEqual(len(list((destination / "runs").glob("*.json"))), 96)
            archived = json.loads(next((destination / "runs").glob("*.json")).read_text())
            self.assertTrue(archived["trace_previews_redacted"])
            self.assertNotIn("private retrieved text", json.dumps(archived))
            self.assertFalse((destination / "runner.py").exists())
            self.assertFalse((destination / "one-run.log").exists())
            self.assertFalse((destination / "summary-output.txt").exists())

    def test_rejects_incomplete_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._write_equalized_source(source, complete=False)

            with self.assertRaisesRegex(ArchiveError, "missing 1 expected run"):
                archive_batch(source, root / "archive", "equalized")

    def test_rejects_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "archive"
            source.mkdir()
            destination.mkdir()
            self._write_equalized_source(source)

            with self.assertRaisesRegex(ArchiveError, "destination already exists"):
                archive_batch(source, destination, "equalized")

    def test_rejects_status_claim_with_missing_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._write_equalized_source(source)
            path = source / "gpt-5-mini-persona_tools-run8.json"
            doc = json.loads(path.read_text())
            doc["records"].pop()
            path.write_text(json.dumps(doc))

            with self.assertRaisesRegex(ArchiveError, "expected 30 records"):
                archive_batch(source, root / "archive", "equalized")

    def test_rejects_run_whose_identity_disagrees_with_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            self._write_equalized_source(source)
            path = source / "gpt-5-mini-persona_tools-run8.json"
            doc = json.loads(path.read_text())
            doc["config"] = "persona"
            path.write_text(json.dumps(doc))

            with self.assertRaisesRegex(ArchiveError, "identity does not match"):
                archive_batch(source, root / "archive", "equalized")

    def test_expected_run_sets_are_frozen(self):
        self.assertEqual(len(expected_run_names("equalized")), 96)
        self.assertEqual(len(expected_run_names("heldout")), 26)
        self.assertIn(
            "gpt-5-mini-persona_tools-run8.json",
            expected_run_names("equalized"),
        )
        self.assertIn(
            "heldout-persona_tools_priority-run5.json",
            expected_run_names("heldout"),
        )


if __name__ == "__main__":
    unittest.main()
