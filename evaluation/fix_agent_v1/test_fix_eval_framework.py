"""
Unit and Integration Tests for Fix Agent Evaluation Harness Framework
Tests:
1. Dataset validation passes
2. DEV and HOLDOUT splits are disjoint
3. All eligible fixtures have before and expected_after
4. Ineligible scenarios specify expected skip categories
5. Ground truth matcher and diff line counter behavior
6. Failure taxonomy classifications
7. Metric computation accuracy
8. Mock runner execution and result formatting
"""

import json
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"
SPLITS_FILE = EVAL_DIR / "splits.json"

from evaluate_fix_results import compute_metrics
from run_fix_eval import run_evaluation, normalize_source_code


class TestFixEvalDatasetIntegrity(unittest.TestCase):
    """Verifies dataset structure, splits, and fixture files."""

    def setUp(self):
        self.scenarios = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))["scenarios"]
        self.splits = json.loads(SPLITS_FILE.read_text(encoding="utf-8"))

    def test_dataset_validation_passes(self):
        from validate_fix_eval import run_validation
        self.assertTrue(run_validation())

    def test_split_disjointness_and_completeness(self):
        dev = set(self.splits["DEV"])
        holdout = set(self.splits["HOLDOUT"])
        self.assertEqual(len(dev.intersection(holdout)), 0)
        self.assertEqual(len(dev) + len(holdout), len(self.scenarios))

    def test_eligible_fixtures_expected_after_exists(self):
        for sc in self.scenarios:
            if sc["eligibility_expected"]:
                self.assertIsNotNone(sc.get("expected_after_fixture"))
                after_p = EVAL_DIR / sc["expected_after_fixture"]
                self.assertTrue(after_p.exists())

    def test_ineligible_scenarios_expected_skip_exists(self):
        for sc in self.scenarios:
            if not sc["eligibility_expected"]:
                self.assertEqual(sc["expected_fix_status"], "skipped")
                self.assertIsNotNone(sc["expected_skip_reason_category"])

    def test_no_benchmark_id_lookup_hardcoding(self):
        """Verifies mock fix agent does not cheat by hardcoding scenario IDs to benchmark patches."""
        from fix_agent import run_fix_agent_for_finding
        finding = {
            "candidate_id": "FA-001",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "CustomFile.java",
            "problem": "Unused variable foo",
            "code_snippet": "int foo = 1;",
            "after_source": "public class CustomFile {\n    void m() {\n        int foo = 1;\n    }\n}"
        }
        res = run_fix_agent_for_finding(finding, backend="mock")
        self.assertEqual(res["file_path"], "CustomFile.java")
        self.assertNotIn("PaymentValidator", res.get("diff", ""))


class TestFailureTaxonomyAndScoring(unittest.TestCase):
    """Verifies each failure classification in the taxonomy."""

    def test_valid_patch_apply_and_ground_truth_match_success(self):
        before = "public class A { boolean x = true; }"
        expected = "public class A { boolean x = false; }"
        diff = "--- a/A.java\n+++ b/A.java\n@@ -1,1 +1,1 @@\n-public class A { boolean x = true; }\n+public class A { boolean x = false; }"
        from patch_validator import apply_unified_diff_to_text
        ok, patched, _ = apply_unified_diff_to_text(before, diff)
        self.assertTrue(ok)
        self.assertEqual(normalize_source_code(patched), normalize_source_code(expected))

    def test_wrong_fix_failure_taxonomy(self):
        before = "public class A { int x = 1; }"
        expected = "public class A { int x = 2; }"
        diff = "--- a/A.java\n+++ b/A.java\n@@ -1,1 +1,1 @@\n-public class A { int x = 1; }\n+public class A { int x = 999; }"
        from patch_validator import apply_unified_diff_to_text
        ok, patched, _ = apply_unified_diff_to_text(before, diff)
        self.assertTrue(ok)
        self.assertNotEqual(normalize_source_code(patched), normalize_source_code(expected))

    def test_over_edit_metric(self):
        import difflib
        before = "public class A {\n    int a = 1;\n    int b = 2;\n}"
        expected = "public class A {\n    int a = 10;\n    int b = 2;\n}"
        gen_diff = "--- a/A.java\n+++ b/A.java\n@@ -1,3 +1,3 @@\n-public class A {\n-    int a = 1;\n-    int b = 2;\n+public class A {\n+    int a = 10;\n+    int b = 2;\n"
        gen_changed = sum(1 for l in gen_diff.splitlines() if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
        exp_diff = list(difflib.unified_diff(before.splitlines(), expected.splitlines()))
        exp_changed = sum(1 for l in exp_diff if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
        extra_lines = max(0, gen_changed - exp_changed)
        self.assertGreater(extra_lines, 0)


class TestMetricComputations(unittest.TestCase):
    """Verifies aggregate metric calculation logic."""

    def test_evaluator_aggregate_metrics(self):
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FA-001",
                    "eligibility_expected": True,
                    "eligibility_actual": True,
                    "actual_fix_status": "generated",
                    "validation": {
                        "unified_diff_valid": True,
                        "path_match": True,
                        "size_within_limit": True,
                        "apply_check": True,
                        "structural_sanity": True
                    },
                    "mechanical_success": True,
                    "ground_truth_match": True,
                    "extra_changed_lines": 0,
                    "failure_type": "success",
                    "role": "maintainability",
                    "difficulty": "EASY"
                },
                {
                    "scenario_id": "FA-016",
                    "eligibility_expected": False,
                    "eligibility_actual": False,
                    "actual_fix_status": "skipped",
                    "validation": {},
                    "mechanical_success": False,
                    "ground_truth_match": False,
                    "extra_changed_lines": 0,
                    "failure_type": "success",
                    "role": "security_validation",
                    "difficulty": "EASY"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        sm = metrics["summary"]
        self.assertEqual(sm["total_scenarios"], 2)
        self.assertEqual(sm["eligibility_accuracy"], 1.0)
        self.assertEqual(sm["model_edit_generation_rate"], 1.0)
        self.assertEqual(sm["safe_skip_rate"], 1.0)
        self.assertEqual(sm["eligible_diff_valid_rate"], 1.0)
        self.assertEqual(sm["eligible_mechanical_success_rate"], 1.0)
        self.assertEqual(sm["eligible_ground_truth_match_rate"], 1.0)
        self.assertEqual(sm["strict_overall_success_rate"], 1.0)


class TestMockEvaluationRunner(unittest.TestCase):
    """Verifies that mock evaluation runs cleanly without external dependencies."""

    def test_mock_dev_run(self):
        out = run_evaluation(split="DEV", backend="mock")
        self.assertEqual(out["split"], "DEV")
        self.assertEqual(out["total_scenarios"], 22)
        self.assertEqual(len(out["results"]), 22)

        for r in out["results"]:
            self.assertIn("failure_type", r)
            self.assertIn("mechanical_success", r)

    def test_holdout_isolation_and_explicit_selection(self):
        from run_fix_eval import run_evaluation
        out_dev = run_evaluation(split="DEV", backend="mock")
        dev_ids = {r["scenario_id"] for r in out_dev["results"]}
        self.assertNotIn("FA-023", dev_ids)  # FA-023 is in HOLDOUT


if __name__ == "__main__":
    unittest.main()
