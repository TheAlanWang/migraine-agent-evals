"""Focused tests for the Level-2 concept matcher."""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import _match_concept, _semantic_concept_match, evaluate_case


class FakeEncoder:
    def __init__(self, vectors):
        self.vectors = vectors

    def encode(self, texts, **_kwargs):
        return np.asarray([self.vectors[text] for text in texts], dtype=float)


class ConceptMatcherTests(unittest.TestCase):
    def setUp(self):
        self.concept = {
            "id": "monthly_day_threshold",
            "any_of": ["15", "fifteen"],
            "semantic_any_of": ["headache on at least fifteen days each month"],
            "semantic_not": ["one attack lasts for several hours"],
        }

    def test_surface_form_is_the_fast_path(self):
        check = _match_concept(
            "Chronic migraine means 15 or more headache days per month.",
            self.concept,
            model=object(),
        )
        self.assertTrue(check["matched"])
        self.assertEqual(check["method"], "surface_form")

    def test_semantic_paraphrase_can_match_without_a_listed_term(self):
        answer = "The chronic form occurs on about half the days in a month."
        model = FakeEncoder({
            answer: [0.90, 0.10],
            self.concept["semantic_any_of"][0]: [1.00, 0.00],
            self.concept["semantic_not"][0]: [0.00, 1.00],
        })
        check = _semantic_concept_match(answer, self.concept, model=model)
        self.assertTrue(check["matched"])
        self.assertGreater(check["margin"], check["min_margin"])

    def test_related_but_different_statement_is_rejected(self):
        answer = "One episode may continue for many hours."
        model = FakeEncoder({
            answer: [0.20, 0.98],
            self.concept["semantic_any_of"][0]: [1.00, 0.00],
            self.concept["semantic_not"][0]: [0.00, 1.00],
        })
        check = _semantic_concept_match(answer, self.concept, model=model)
        self.assertFalse(check["matched"])
        self.assertLess(check["margin"], 0)

    def test_evaluation_archives_semantic_match_details(self):
        answer = "The chronic form occurs on about half the days in a month."
        model = FakeEncoder({
            answer: [0.90, 0.10],
            self.concept["semantic_any_of"][0]: [1.00, 0.00],
            self.concept["semantic_not"][0]: [0.00, 1.00],
        })
        case = {
            "id": "semantic-example",
            "category": "on_corpus",
            "question": "How common is chronic migraine?",
            "expect_concepts": [self.concept],
        }

        def agent(_question, _user_id, _conn_id):
            return (answer, ["source.pdf"],
                    [{"event": "tool_call", "tool": "search_supabase"}])

        with patch("harness._semantic_model", return_value=model):
            result = evaluate_case(case, agent, level=2)
        self.assertTrue(result.passed)
        self.assertTrue(result.turns[0]["concept_checks"][0]["matched"])
        self.assertEqual(result.turns[0]["concept_checks"][0]["method"], "semantic")


if __name__ == "__main__":
    unittest.main()
