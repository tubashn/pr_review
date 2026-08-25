"""
Unit and Integration Tests for Fix Agent Evaluation Harness Framework
Comprehensive tests covering:
1. Dataset validation passes & split disjointness
2. Canonical source match & CRLF/LF normalization
3. Java token equivalence (trailing whitespace, blank lines, indentation)
4. Preservation of string literals, identifiers, numbers, operators
5. FA-003, FA-004, FA-007 deletion + blank line semantic acceptance
6. Semantic oracle multi-tier evaluation & success modes
7. Unknown alternative classification as semantic_review_required
8. Confirmed wrong fix classification
9. Raw result re-evaluation capability
10. Mock DEV execution & HOLDOUT isolation
"""

import difflib
import json
import sys
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"
SPLITS_FILE = EVAL_DIR / "splits.json"

# Add repo root to path
PR_REVIEW_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PR_REVIEW_ROOT) not in sys.path:
    sys.path.insert(0, str(PR_REVIEW_ROOT))

from semantic_oracle import (
    evaluate_semantic_correctness,
    normalize_source_code,
    check_token_equivalence
)
from evaluate_fix_results import compute_metrics, recompute_item_semantics
from run_fix_eval import run_evaluation
from patch_validator import apply_unified_diff_to_text


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


class TestJavaTokenEquivalenceAndNormalization(unittest.TestCase):
    """Verifies Java lexical token stream comparison and normalization rules."""

    def test_identical_canonical_source_matches(self):
        code_a = "public class A { int x = 1; }"
        code_b = "public class A { int x = 1; }"
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertTrue(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "canonical")
        self.assertEqual(res["failure_subtype"], "success_canonical")

    def test_crlf_lf_difference_is_not_failure(self):
        code_a = "public class A {\r\n    int x = 1;\r\n}"
        code_b = "public class A {\n    int x = 1;\n}"
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertTrue(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])

    def test_trailing_whitespace_is_token_equivalent(self):
        code_a = "public class A {   \n    int x = 1;  \n}"
        code_b = "public class A {\n    int x = 1;\n}"
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertTrue(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])

    def test_whitespace_only_blank_line_is_token_equivalent(self):
        code_a = "public class A {\n\n    int x = 1;\n\n}"
        code_b = "public class A {\n    int x = 1;\n}"
        self.assertTrue(check_token_equivalence(code_a, code_b))
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertFalse(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "token_equivalent")

    def test_indentation_difference_is_token_equivalent(self):
        code_a = "public class A {\n        int x = 1;\n}"
        code_b = "public class A {\n    int x = 1;\n}"
        self.assertTrue(check_token_equivalence(code_a, code_b))
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])

    def test_string_literal_whitespace_difference_not_token_equivalent(self):
        code_a = 'public class A { String s = "hello world"; }'
        code_b = 'public class A { String s = "hello   world"; }'
        self.assertFalse(check_token_equivalence(code_a, code_b))
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertFalse(res["token_equivalent"])
        self.assertFalse(res["semantic_match"])

    def test_identifier_change_not_token_equivalent(self):
        code_a = "public class A { int x = 1; }"
        code_b = "public class A { int y = 1; }"
        self.assertFalse(check_token_equivalence(code_a, code_b))
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertFalse(res["token_equivalent"])
        self.assertFalse(res["semantic_match"])

    def test_numeric_literal_change_not_token_equivalent(self):
        code_a = "public class A { int x = 10; }"
        code_b = "public class A { int x = 20; }"
        self.assertFalse(check_token_equivalence(code_a, code_b))
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertFalse(res["token_equivalent"])

    def test_operator_change_not_token_equivalent(self):
        code_a = "public class A { boolean x = a < b; }"
        code_b = "public class A { boolean x = a > b; }"
        self.assertFalse(check_token_equivalence(code_a, code_b))
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertFalse(res["token_equivalent"])


class TestDeletionAndBlankLineEquivalence(unittest.TestCase):
    """Verifies that FA-003, FA-004, FA-007 style unused variable removals evaluate as semantic accepted."""

    def test_fa003_style_unused_declaration_deletion_blank_line(self):
        before = "package com.example;\npublic class LatencyTracker {\n    public void record(long ms) {\n        int debugCount = 0;\n        recordInternal(ms);\n    }\n}"
        expected = "package com.example;\npublic class LatencyTracker {\n    public void record(long ms) {\n        recordInternal(ms);\n    }\n}"
        # Model deletes the line leaving blank line
        generated_patched = "package com.example;\npublic class LatencyTracker {\n    public void record(long ms) {\n\n        recordInternal(ms);\n    }\n}"
        res = evaluate_semantic_correctness(generated_patched, expected)
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "token_equivalent")

    def test_fa004_style_unused_allocation_deletion_blank_line(self):
        before = "package com.example;\npublic class Formatter {\n    public String format(String p, String b) {\n        StringBuilder builder = new StringBuilder();\n        return p + b;\n    }\n}"
        expected = "package com.example;\npublic class Formatter {\n    public String format(String p, String b) {\n        return p + b;\n    }\n}"
        generated_patched = "package com.example;\npublic class Formatter {\n    public String format(String p, String b) {\n        \n        return p + b;\n    }\n}"
        res = evaluate_semantic_correctness(generated_patched, expected)
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])

    def test_fa007_style_unused_state_deletion_blank_line(self):
        before = "package com.example;\npublic class Runner {\n    public void run() {\n        String lastError = null;\n        execute();\n    }\n}"
        expected = "package com.example;\npublic class Runner {\n    public void run() {\n        execute();\n    }\n}"
        generated_patched = "package com.example;\npublic class Runner {\n    public void run() {\n\n        execute();\n    }\n}"
        res = evaluate_semantic_correctness(generated_patched, expected)
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])


class TestSemanticOracleAndSuccessModes(unittest.TestCase):
    """Verifies multi-tier success modes and fallback classification."""

    def test_success_mode_canonical(self):
        code = "public class Foo { int x = 1; }"
        res = evaluate_semantic_correctness(code, code)
        self.assertEqual(res["semantic_match_mode"], "canonical")
        self.assertEqual(res["failure_subtype"], "success_canonical")

    def test_success_mode_token_equivalent(self):
        code_a = "public class Foo {\n    int x = 1;\n}"
        code_b = "public class Foo { int x = 1; }"
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertEqual(res["semantic_match_mode"], "token_equivalent")
        self.assertEqual(res["failure_subtype"], "success_token_equivalent")

    def test_success_mode_semantic_oracle_fa015(self):
        expected = "public class P { double calc(int a, int b) { return ((double) a / b) * 100.0; } }"
        generated = "public class P { double calc(int a, int b) { return (double) a / b * 100.0; } }"
        oracle = {
            "oracle_type": "alternative_token_variants",
            "variants": [
                "public class P { double calc(int a, int b) { return (double) a / b * 100.0; } }",
                "public class P { double calc(int a, int b) { return ((double) a / b) * 100.0; } }"
            ]
        }
        res = evaluate_semantic_correctness(generated, expected, oracle_spec=oracle)
        self.assertFalse(res["canonical_source_match"])
        self.assertFalse(res["token_equivalent"])
        self.assertTrue(res["semantic_oracle_pass"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "semantic_oracle")
        self.assertEqual(res["failure_subtype"], "success_semantic_oracle")

    def test_unknown_alternative_without_oracle_is_semantic_review_required(self):
        expected = "public class P { int x = 1; }"
        generated = "public class P { int x = 1 + 0; }"
        res = evaluate_semantic_correctness(generated, expected, oracle_spec=None)
        self.assertFalse(res["semantic_match"])
        self.assertEqual(res["failure_subtype"], "semantic_review_required")

    def test_confirmed_wrong_fix_classification(self):
        expected = "public class P { int x = 1; }"
        generated = "public class P { int x = 999; }"
        oracle = {
            "oracle_type": "alternative_token_variants",
            "variants": ["public class P { int x = 1; }", "public class P { int x = 0 + 1; }"]
        }
        res = evaluate_semantic_correctness(generated, expected, oracle_spec=oracle)
        self.assertFalse(res["semantic_match"])
        self.assertEqual(res["failure_subtype"], "wrong_fix")


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
                    "canonical_source_match": True,
                    "token_equivalent": True,
                    "semantic_oracle_pass": True,
                    "semantic_match": True,
                    "semantic_match_mode": "canonical",
                    "semantic_success": True,
                    "extra_changed_lines": 0,
                    "failure_type": "success",
                    "failure_subtype": "success_canonical",
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
                    "canonical_source_match": False,
                    "token_equivalent": False,
                    "semantic_oracle_pass": False,
                    "semantic_match": False,
                    "semantic_match_mode": None,
                    "semantic_success": False,
                    "extra_changed_lines": 0,
                    "failure_type": "success",
                    "failure_subtype": "success_safe_skip",
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
        self.assertEqual(sm["canonical_source_match_rate"], 1.0)
        self.assertEqual(sm["token_equivalent_match_rate"], 1.0)
        self.assertEqual(sm["semantic_accepted_fix_rate"], 1.0)


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
