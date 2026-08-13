from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parent
ARTIFACT = TOOLS.parents[1]
REPRODUCE = ARTIFACT / "reproduce.py"
SCANNER = TOOLS / "scan_for_sensitive.py"
sys.path.insert(0, str(TOOLS))

import check_release_ready as release_gate  # noqa: E402
from check_release_ready import check_replication_batches  # noqa: E402
from make_public_snapshot import (  # noqa: E402
    excluded_from_snapshot,
    redact_previews,
    refresh_manifest_inputs,
)
from scan_for_sensitive import scan_file  # noqa: E402


class ReproduceCliTests(unittest.TestCase):
    def test_help_exposes_both_replication_verifiers(self):
        result = subprocess.run(
            [sys.executable, str(REPRODUCE), "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("verify-equalized", result.stdout)
        self.assertIn("verify-heldout", result.stdout)

    def test_both_replication_commands_pass(self):
        for command in ("verify-equalized", "verify-heldout"):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, str(REPRODUCE), command],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SensitiveScannerTests(unittest.TestCase):
    def test_short_unredacted_preview_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps({
                "records": [{"trace": [{"preview": "short private passage"}]}],
            }))

            findings = scan_file(path, [])

            self.assertTrue(
                any(item.startswith("unredacted_preview") for item in findings)
            )
            result = subprocess.run(
                [sys.executable, str(SCANNER), "--for-release", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("unredacted_preview", result.stdout)

    def test_preregistered_decision_rule_is_not_mistaken_for_corpus(self):
        preregistration = (
            ARTIFACT
            / "archived_runs"
            / "equalized_ladder_2026-08-13"
            / "preregistration.json"
        )
        rule = json.loads(preregistration.read_text())[
            "decision_rule_for_repo_replacement"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preregistration.json"
            path.write_text(json.dumps({
                "decision_rule_for_repo_replacement": rule,
            }))

            findings = scan_file(path, [])

            self.assertFalse(any(item.startswith("corpus_text") for item in findings))

    def test_forged_decision_rule_does_not_bypass_corpus_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preregistration.json"
            path.write_text(json.dumps({
                "decision_rule_for_repo_replacement": "unregistered corpus " * 30,
            }))

            findings = scan_file(path, [])

            self.assertTrue(any(item.startswith("corpus_text") for item in findings))

    def test_archive_cannot_self_register_a_forged_decision_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / "artifact" / "src" / "tools"
            archive = root / "artifact" / "archived_runs" / "forged"
            tools.mkdir(parents=True)
            archive.mkdir(parents=True)
            copied_scanner = tools / "scan_for_sensitive.py"
            shutil.copy2(SCANNER, copied_scanner)
            target = archive / "preregistration.json"
            target.write_text(json.dumps({
                "decision_rule_for_repo_replacement": "forged corpus " * 40,
            }))

            result = subprocess.run(
                [sys.executable, str(copied_scanner), "--for-release", str(target)],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("corpus_text", result.stdout)

    def test_malformed_json_is_always_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text(
                '{"preview": "[redacted: 14 chars of retrieved clinical corpus text]'
                '\nprivate passage'
            )

            findings = scan_file(path, [])

            self.assertTrue(any(item.startswith("invalid_json") for item in findings))
            result = subprocess.run(
                [sys.executable, str(SCANNER), "--for-release", str(path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)


class ReleaseGateTests(unittest.TestCase):
    def test_replication_verifiers_are_release_gates(self):
        self.assertEqual(check_replication_batches(), [])

    def test_history_gate_fails_closed_without_a_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(release_gate, "REPOSITORY", Path(tmp)):
                self.assertFalse(release_gate.is_git_repository())
                self.assertTrue(release_gate.check_tracked_files())
                self.assertTrue(release_gate.check_history())

    def test_parent_worktree_does_not_count_as_snapshot_repository(self):
        repository = Path("/tmp/parent/snapshot")

        def fake_git(args, **_kwargs):
            if "--is-inside-work-tree" in args:
                return subprocess.CompletedProcess(args, 0, "true\n", "")
            return subprocess.CompletedProcess(args, 0, "/tmp/parent\n", "")

        with (
            patch.object(release_gate, "REPOSITORY", repository),
            patch.object(release_gate.subprocess, "run", side_effect=fake_git),
        ):
            self.assertFalse(release_gate.is_git_repository())


class PublicSnapshotTests(unittest.TestCase):
    def test_snapshot_keeps_archived_batch_runs_but_excludes_live_runs(self):
        self.assertTrue(excluded_from_snapshot(Path("artifact/runs/private.json")))
        self.assertTrue(excluded_from_snapshot(Path("runs/private.json")))
        self.assertFalse(excluded_from_snapshot(Path(
            "artifact/archived_runs/equalized_ladder_2026-08-13/"
            "runs/gpt-5-mini-persona-run1.json"
        )))

    def test_snapshot_redacts_legacy_previews_recursively(self):
        doc = {
            "trace": [{
                "preview": "legacy private passage",
                "nested": {"preview": "another passage"},
            }],
        }

        self.assertEqual(redact_previews(doc), 2)
        self.assertEqual(
            doc["trace"][0]["preview"],
            "[redacted: 22 chars of retrieved clinical corpus text]",
        )
        self.assertEqual(redact_previews(doc), 0)

    def test_snapshot_refreshes_manifest_input_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            batch = artifact / "archived_runs" / "batch"
            batch.mkdir(parents=True)
            (batch / "input.json").write_text('{"redacted": true}\n')
            manifest = batch / "results_manifest.json"
            manifest.write_text(json.dumps({
                "inputs": {"input.json": "0" * 64},
            }))

            refreshed = refresh_manifest_inputs(artifact)

            stored = json.loads(manifest.read_text())
            self.assertEqual(refreshed, 1)
            self.assertNotEqual(stored["inputs"]["input.json"], "0" * 64)
            self.assertEqual(len(stored["inputs"]["input.json"]), 64)


if __name__ == "__main__":
    unittest.main()
