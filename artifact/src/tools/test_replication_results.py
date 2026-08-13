from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
ARTIFACT = TOOLS.parents[1]
ARCHIVE = ARTIFACT / "archived_runs"
sys.path.insert(0, str(TOOLS))

from freeze_equalized_ladder import (  # noqa: E402
    FreezeError,
    _step as equalized_step,
    build_manifest,
    validate_plan_hash,
    verify_input_digests,
)
from replication_statistics import majority_labels, mannwhitney  # noqa: E402
from verify_equalized_ladder import verify as verify_equalized  # noqa: E402
from verify_heldout_tool_calling import (  # noqa: E402
    build_summary,
    validate_freeze_metadata,
    validate_run_identity,
    verify_summary,
)


EQUALIZED = ARCHIVE / "equalized_ladder_2026-08-13"
HELDOUT = ARCHIVE / "heldout_tool_calling_2026-08-12"


class StatisticsTests(unittest.TestCase):
    def test_tie_aware_permutation_reaches_expected_eight_by_eight_floor(self):
        result = mannwhitney([1] * 8, [2] * 8)

        self.assertEqual(result["U"], 0.0)
        self.assertAlmostEqual(result["p"], 0.0001554001554001554)
        self.assertAlmostEqual(result["p_permutation"], 0.0001554001554001554)
        self.assertAlmostEqual(result["min_attainable_p"], 0.0001554001554001554)

    def test_majority_labels_exclude_split_even_cases(self):
        runs = [
            [{"case_id": "stable", "score": True}, {"case_id": "tie", "score": True}],
            [{"case_id": "stable", "score": True}, {"case_id": "tie", "score": False}],
        ]

        labels, ties = majority_labels(runs, "score")

        self.assertEqual(labels["stable"], True)
        self.assertEqual(ties, {"tie"})

    def test_equalized_step_excludes_split_even_case_from_mcnemar(self):
        runs_from = [
            {
                "crisis_resource_total": 2,
                "records": [
                    {"case_id": "stable", "crisis_resource_included": True},
                    {"case_id": "tie", "crisis_resource_included": True},
                ],
            },
            {
                "crisis_resource_total": 1,
                "records": [
                    {"case_id": "stable", "crisis_resource_included": True},
                    {"case_id": "tie", "crisis_resource_included": False},
                ],
            },
        ]
        runs_to = [
            {
                "crisis_resource_total": 2,
                "records": [
                    {"case_id": "stable", "crisis_resource_included": True},
                    {"case_id": "tie", "crisis_resource_included": True},
                ],
            },
            {
                "crisis_resource_total": 2,
                "records": [
                    {"case_id": "stable", "crisis_resource_included": True},
                    {"case_id": "tie", "crisis_resource_included": True},
                ],
            },
        ]

        step = equalized_step(runs_from, runs_to)

        self.assertEqual(step["excluded_split_even"], ["tie"])
        self.assertEqual(step["lost"], [])
        self.assertEqual(step["gained"], [])
        self.assertEqual(step["mcnemar_p"], 1.0)


class EqualizedManifestTests(unittest.TestCase):
    def test_builds_pinned_balanced_results(self):
        manifest = build_manifest(EQUALIZED)

        gemini = manifest["models"]["gemini-2.5-flash"]
        self.assertEqual(list(manifest["models"]), ["gemini-2.5-flash"])
        self.assertEqual(gemini["cells"]["persona"]["mean"], 28.0)
        self.assertEqual(gemini["cells"]["persona_tools"]["mean"], 24.125)
        self.assertEqual(gemini["cells"]["mitigated"]["mean"], 29.0)
        self.assertEqual(gemini["steps"]["tool_calling"]["mean_change"], -3.875)
        self.assertFalse(manifest["replacement_decision"]["criterion_met"])
        self.assertEqual(
            manifest["replacement_decision"]["decision"],
            "public_gemini_subset_does_not_replace_discovery",
        )

    def test_verifier_accepts_the_archived_batch(self):
        result = verify_equalized(EQUALIZED, require_manifest=False)

        self.assertGreaterEqual(result["checks"], 15)
        self.assertEqual(result["failures"], [])

    def test_rejects_altered_plan_hash(self):
        with self.assertRaisesRegex(FreezeError, "plan hash"):
            validate_plan_hash(
                {"plan_sha256": "wrong"},
                "expected",
                "gemini-2.5-flash-persona-run1.json",
            )

    def test_rejects_stale_input_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "input.json").write_text('{"value": 1}\n')
            manifest_inputs = {"input.json": "0" * 64}

            with self.assertRaisesRegex(FreezeError, "stale input"):
                verify_input_digests(root, manifest_inputs)

    def test_rejects_incomplete_input_digest_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.json").write_text("{}")
            (root / "two.json").write_text("{}")

            with self.assertRaisesRegex(FreezeError, "incomplete input digest set"):
                verify_input_digests(
                    root,
                    {"one.json": "unused"},
                    expected_paths={"one.json", "two.json"},
                )

    def test_rejects_missing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plan.json").write_text("{}")
            (root / "preregistration.json").write_text("{}")
            (root / "runs").mkdir()

            with self.assertRaisesRegex(FreezeError, "missing 32 runs"):
                build_manifest(root)


class HeldoutVerifierTests(unittest.TestCase):
    def test_rejects_heldout_identity_that_disagrees_with_filename(self):
        run = {
            "kind": "heldout",
            "config": "persona_tools",
            "run_index": 2,
            "completed": "2026-08-13T00:00:00+00:00",
            "records": [{}] * 30,
        }

        with self.assertRaisesRegex(ValueError, "identity does not match"):
            validate_run_identity(
                "heldout-persona_tools-run1.json",
                run,
            )

    def test_rejects_mismatched_heldout_freeze_metadata(self):
        freeze = {
            "case_sha256": "cases",
            "preregistration_sha256": "prereg",
            "base_prompt_sha256": "base",
            "priority_prompt_sha256": "priority",
            "priority_instruction_sha256": "instruction",
        }
        run = {
            "case_file_sha256": "cases",
            "preregistration_sha256": "prereg",
            "prompt_sha256": "base",
            "priority_instruction_sha256": "wrong",
            "priority_occurrences": 0,
            "config": "persona_tools",
        }

        with self.assertRaisesRegex(ValueError, "priority instruction hash"):
            validate_freeze_metadata("heldout-persona_tools-run1.json", run, freeze)

    def test_recomputed_summary_matches_frozen_summary(self):
        recomputed = build_summary(HELDOUT)
        frozen = json.loads((HELDOUT / "summary.json").read_text())

        self.assertEqual(recomputed, frozen["phases"])
        self.assertEqual(recomputed["heldout"]["persona_no_tools"]["mean"], 28.4)
        self.assertEqual(recomputed["heldout"]["persona_tools"]["mean"], 27.6)
        self.assertEqual(recomputed["heldout"]["persona_tools_priority"]["mean"], 30.0)

    def test_verifier_accepts_the_archived_batch(self):
        result = verify_summary(HELDOUT)

        self.assertGreaterEqual(result["checks"], 10)
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main()
