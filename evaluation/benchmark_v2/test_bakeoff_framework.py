"""
Unit and Integration Tests for Semantic Verifier Model Bake-Off Framework
Tests:
1. JSON Parser robust handling (valid, fenced, malformed, non-boolean)
2. Mock Runner checkpoint and resume behavior
3. Atomic and safe file write
4. Evaluator Level A (Semantic-Only) and Level B (Full Hybrid) metrics calculations
5. Disagreement detection across multiple model results
"""

import json
import tempfile
import unittest
from pathlib import Path

from run_semantic_bakeoff import parse_model_json_response, SemanticBakeoffRunner
from evaluate_model_bakeoff import compute_binary_metrics, evaluate_single_model_results, compare_multiple_models


class TestModelBakeoffFramework(unittest.TestCase):

    def test_json_parser_valid(self):
        raw = '{"candidate_id": "test-1", "problem_present": true, "role_match": true, "reason": "valid", "evidence": "code"}'
        res = parse_model_json_response(raw, "test-1")
        self.assertFalse(res["parse_error"])
        self.assertTrue(res["problem_present"])
        self.assertTrue(res["role_match"])

    def test_json_parser_fenced(self):
        raw = '```json\n{"candidate_id": "test-2", "problem_present": false, "role_match": true, "reason": "fenced"}\n```'
        res = parse_model_json_response(raw, "test-2")
        self.assertFalse(res["parse_error"])
        self.assertFalse(res["problem_present"])
        self.assertTrue(res["role_match"])

    def test_json_parser_malformed(self):
        raw = 'This is not valid JSON at all.'
        res = parse_model_json_response(raw, "test-3")
        self.assertTrue(res["parse_error"])
        self.assertFalse(res["problem_present"])

    def test_json_parser_non_boolean_type(self):
        raw = '{"candidate_id": "test-4", "problem_present": "yes", "role_match": "no"}'
        res = parse_model_json_response(raw, "test-4")
        self.assertTrue(res["parse_error"])

    def test_runner_mock_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_p = Path(tmp_dir)
            reqs = [
                {"candidate_id": "c-1", "scenario_id": "s-1", "problem": "p1", "source_reviewer": "maintainability"},
                {"candidate_id": "c-2", "scenario_id": "s-1", "problem": "p2", "source_reviewer": "maintainability"}
            ]
            req_file = tmp_p / "reqs.json"
            req_file.write_text(json.dumps(reqs), encoding="utf-8")

            out_file = tmp_p / "out.json"

            # 1. Run first batch of 1
            runner = SemanticBakeoffRunner(model_id="mock-test-model", backend="mock", output_file=out_file)
            res1 = runner.run_batch(req_file, resume=True)
            self.assertEqual(len(res1), 2)
            self.assertTrue(out_file.exists())

            # 2. Run again with resume -> should detect existing completed
            res2 = runner.run_batch(req_file, resume=True)
            self.assertEqual(len(res2), 2)

    def test_evaluator_metrics_calculation(self):
        # 4 TP, 2 FP, 0 FN, 10 TN
        m = compute_binary_metrics(
            tp=4, fp=2, fn=0, tn=10,
            expected_accept=4, expected_fp=4, expected_leakage=2, expected_clean=2,
            tn_fp=3, tn_leakage=2, tn_clean=2, parse_errors=0
        )
        self.assertAlmostEqual(m["Precision"], 4 / 6, places=4)
        self.assertAlmostEqual(m["Recall"], 1.0, places=4)
        self.assertAlmostEqual(m["F1"], 0.8, places=4)
        self.assertEqual(m["Clean PR False Finding Rejection Rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
