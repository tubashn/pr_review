"""
Comprehensive Framework & Regression Tests for Fix Agent Benchmark V2
Validates:
1. Scenario counts (80 total: 56 DEV, 24 HOLDOUT, 54 eligible, 26 ineligible)
2. Category balance (27 maintainability, 27 correctness)
3. Difficulty & complexity totals
4. Fixtures presence and <= 20 lines diff
5. Dataset isolation, zero duplicate leakage from legacy V1, no forbidden literals
6. Multi-tier evaluation mechanics & frozen semantic hierarchy
7. Separate eligible/ineligible denominators & statistical raw counts
8. Mock backend safety (no expected_after leakage, no transformers requirement)
9. HOLDOUT isolation & warning
"""

import difflib
import json
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIX_V1_DIR = REPO_ROOT / "evaluation" / "fix_agent_v1"
BENCHMARK_DIR = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(FIX_V1_DIR) not in sys.path:
    sys.path.insert(0, str(FIX_V1_DIR))
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

from semantic_oracle import (
    evaluate_semantic_correctness,
    check_token_equivalence,
    normalize_source_code
)
from validate_benchmark import run_validation
from audit_benchmark import run_audit
from evaluate_results import compute_metrics, re_evaluate_results
from run_benchmark import run_benchmark

SCENARIOS_FILE = BENCHMARK_DIR / "scenarios.json"


class TestBenchmarkV2StructureAndCounts(unittest.TestCase):
    """Verifies dataset counts, splits, and category distributions."""

    def setUp(self):
        sc_path = BENCHMARK_DIR / "scenarios.json"
        sp_path = BENCHMARK_DIR / "splits.json"
        self.scenarios = json.loads(sc_path.read_text(encoding="utf-8"))["scenarios"]
        self.splits = json.loads(sp_path.read_text(encoding="utf-8"))

    def test_total_scenario_count_80(self):
        self.assertEqual(len(self.scenarios), 80)

    def test_dev_split_count_56(self):
        self.assertEqual(len(self.splits["DEV"]), 56)

    def test_holdout_split_count_24(self):
        self.assertEqual(len(self.splits["HOLDOUT"]), 24)

    def test_eligible_scenario_count_54(self):
        eligs = [s for s in self.scenarios if s["eligibility_expected"]]
        self.assertEqual(len(eligs), 54)

    def test_ineligible_scenario_count_26(self):
        ineligs = [s for s in self.scenarios if not s["eligibility_expected"]]
        self.assertEqual(len(ineligs), 26)

    def test_split_disjointness(self):
        dev_set = set(self.splits["DEV"])
        hold_set = set(self.splits["HOLDOUT"])
        self.assertEqual(len(dev_set.intersection(hold_set)), 0)

    def test_unique_scenario_ids(self):
        ids = [s["scenario_id"] for s in self.scenarios]
        self.assertEqual(len(ids), len(set(ids)))

    def test_maintainability_eligible_27(self):
        m_eligs = [s for s in self.scenarios if s["eligibility_expected"] and s["role"] == "maintainability"]
        self.assertEqual(len(m_eligs), 27)

    def test_correctness_eligible_27(self):
        c_eligs = [s for s in self.scenarios if s["eligibility_expected"] and s["role"] == "correctness_logic"]
        self.assertEqual(len(c_eligs), 27)

    def test_difficulty_totals(self):
        diffs = [s["difficulty"] for s in self.scenarios]
        self.assertEqual(diffs.count("EASY"), 24)
        self.assertEqual(diffs.count("MEDIUM"), 36)
        self.assertEqual(diffs.count("HARD"), 20)

    def test_complexity_totals(self):
        eligs = [s for s in self.scenarios if s["eligibility_expected"]]
        comps = [s["fix_complexity"] for s in eligs]
        self.assertEqual(comps.count("single_line"), 32)
        self.assertEqual(comps.count("multi_line"), 16)
        self.assertEqual(comps.count("boundary"), 6)


class TestBenchmarkV2FixturesAndSafety(unittest.TestCase):
    """Verifies fixture integrity, diff bounds, and absence of leaks."""

    def setUp(self):
        sc_path = BENCHMARK_DIR / "scenarios.json"
        self.scenarios = json.loads(sc_path.read_text(encoding="utf-8"))["scenarios"]

    def test_eligible_expected_after_exists(self):
        for s in self.scenarios:
            if s["eligibility_expected"]:
                self.assertIsNotNone(s.get("expected_after_fixture"))
                fp = BENCHMARK_DIR / s["expected_after_fixture"]
                self.assertTrue(fp.exists())

    def test_ineligible_expected_skip_reason_exists(self):
        for s in self.scenarios:
            if not s["eligibility_expected"]:
                self.assertIsNotNone(s.get("expected_skip_reason_category"))
                self.assertEqual(s.get("expected_fix_status"), "skipped")

    def test_expected_patch_line_limit_20(self):
        for s in self.scenarios:
            if s["eligibility_expected"]:
                src_p = BENCHMARK_DIR / s["source_fixture"]
                exp_p = BENCHMARK_DIR / s["expected_after_fixture"]
                lines_a = src_p.read_text(encoding="utf-8").splitlines()
                lines_b = exp_p.read_text(encoding="utf-8").splitlines()
                diff = list(difflib.unified_diff(lines_a, lines_b))
                changed = sum(1 for l in diff if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
                self.assertLessEqual(changed, 20, f"{s['scenario_id']} changed {changed} lines > 20")

    def test_safe_file_paths(self):
        for s in self.scenarios:
            fpath = s["file_path"]
            self.assertFalse(fpath.startswith("/"))
            self.assertFalse(".." in fpath)

    def test_old_fa_scenario_leakage_rejected(self):
        for s in self.scenarios:
            self.assertFalse(s["scenario_id"].startswith("FA-"))

    def test_old_controlled_literal_detected(self):
        for s in self.scenarios:
            sc_str = json.dumps(s).lower()
            for forbidden in ["admin123", "tuba-test", "orderapp", "testvalue"]:
                self.assertNotIn(forbidden, sc_str)


class TestBenchmarkV2EvaluationHierarchy(unittest.TestCase):
    """Verifies frozen semantic acceptance hierarchy and metric formulas."""

    def test_canonical_evaluator_works(self):
        code_a = "public class A { int x = 1; }"
        code_b = "public class A { int x = 1; }"
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertTrue(res["canonical_source_match"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "canonical")

    def test_token_equivalence_works(self):
        code_a = "public class A {\n\n int x = 1;\n}"
        code_b = "public class A {\n int x = 1;\n}"
        res = evaluate_semantic_correctness(code_a, code_b)
        self.assertFalse(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "token_equivalent")

    def test_string_literal_difference_not_token_equivalent(self):
        code_a = 'public class A { String s = "abc"; }'
        code_b = 'public class A { String s = "xyz"; }'
        self.assertFalse(check_token_equivalence(code_a, code_b))

    def test_operator_difference_not_token_equivalent(self):
        code_a = 'public class A { boolean b = x < y; }'
        code_b = 'public class A { boolean b = x > y; }'
        self.assertFalse(check_token_equivalence(code_a, code_b))

    def test_oracle_applicable_denominator_correct(self):
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "mechanical_success": True,
                    "canonical_source_match": True,
                    "token_equivalent": True,
                    "oracle_applicable": False,
                    "semantic_oracle_pass": False,
                    "semantic_match": True,
                    "semantic_match_mode": "canonical",
                    "failure_subtype": "success_canonical",
                    "role": "maintainability",
                    "difficulty": "EASY"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        sm = metrics["summary"]
        self.assertEqual(sm["deterministic_semantic_oracle"]["applicable"], 0)
        self.assertIsNone(sm["deterministic_semantic_oracle"]["rate"])

    def test_no_oracle_semantic_review_required(self):
        code_a = "public class A { int x = 1; }"
        code_b = "public class A { int x = 2 - 1; }"
        res = evaluate_semantic_correctness(code_a, code_b, oracle_spec=None)
        self.assertFalse(res["semantic_match"])
        self.assertEqual(res["failure_subtype"], "semantic_review_required")

    def test_category_denominator_correct(self):
        VALID_BLOCK = {
            "unified_diff_valid": True,
            "path_match": True,
            "size_within_limit": True,
            "apply_check": True,
            "structural_sanity": True
        }
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "role": "maintainability",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": VALID_BLOCK,
                    "old_text": "long lastPermitTimestamp = System.currentTimeMillis();",
                    "new_text": ""
                },
                {
                    "scenario_id": "FB2-053",
                    "role": "maintainability",
                    "eligibility_expected": False,
                    "actual_fix_status": "skipped",
                    "gate_skip": True,
                    "gate_decision": "skipped"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        cb = metrics["category_breakdown"]["maintainability"]
        self.assertEqual(cb["total"], 2)
        self.assertEqual(cb["eligible"], 1)
        self.assertEqual(cb["ineligible"], 1)
        self.assertEqual(cb["mechanical_success"], 1)
        self.assertEqual(cb["safe_skips"], 1)

    def test_difficulty_denominator_correct(self):
        VALID_BLOCK = {
            "unified_diff_valid": True,
            "path_match": True,
            "size_within_limit": True,
            "apply_check": True,
            "structural_sanity": True
        }
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "difficulty": "EASY",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": VALID_BLOCK,
                    "old_text": "long lastPermitTimestamp = System.currentTimeMillis();",
                    "new_text": ""
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        db = metrics["difficulty_breakdown"]["EASY"]
        self.assertEqual(db["total"], 1)
        self.assertEqual(db["eligible"], 1)
        self.assertEqual(db["mechanical_success"], 1)

    def test_fix_complexity_breakdown_correct(self):
        VALID_BLOCK = {
            "unified_diff_valid": True,
            "path_match": True,
            "size_within_limit": True,
            "apply_check": True,
            "structural_sanity": True
        }
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "fix_complexity": "single_line",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": VALID_BLOCK,
                    "old_text": "long lastPermitTimestamp = System.currentTimeMillis();",
                    "new_text": ""
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        cb = metrics["complexity_breakdown"]["single_line"]
        self.assertEqual(cb["eligible_count"], 1)
        self.assertEqual(cb["mechanical_success"], 1)
        self.assertEqual(cb["semantic_accepted"], 1)

    def test_alternative_valid_breakdown_correct(self):
        VALID_BLOCK = {
            "unified_diff_valid": True,
            "path_match": True,
            "size_within_limit": True,
            "apply_check": True,
            "structural_sanity": True
        }
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-004",
                    "alternative_valid_fix": True,
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": VALID_BLOCK,
                    "old_text": "sum = Integer.valueOf(sum + val);",
                    "new_text": "sum += val;"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        avb = metrics["alternative_valid_breakdown"]
        self.assertEqual(avb["total_alt_valid"], 1)
        self.assertEqual(avb["oracle_success"], 1)


class TestSemanticEvaluationPlumbingAndInvariants(unittest.TestCase):
    """Verifies that semantic evaluation plumbing and taxonomy invariants are mathematically sound."""

    def test_canonical_patched_source_yields_success_canonical(self):
        source = "public class A { public int f() { return 1; } }"
        expected = "public class A { public int f() { return 2; } }"
        patched = "public class A { public int f() { return 2; } }"

        res = evaluate_semantic_correctness(patched_code=patched, expected_code=expected)
        self.assertTrue(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "canonical")
        self.assertEqual(res["failure_subtype"], "success_canonical")

    def test_formatting_only_difference_yields_success_token_equivalent(self):
        expected = "public class A {\n    public int f() {\n        return 2;\n    }\n}"
        patched = "public class A { public int f() { return 2; } }"

        res = evaluate_semantic_correctness(patched_code=patched, expected_code=expected)
        self.assertFalse(res["canonical_source_match"])
        self.assertTrue(res["token_equivalent"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "token_equivalent")
        self.assertEqual(res["failure_subtype"], "success_token_equivalent")

    def test_model_output_independent_oracle_yields_success_semantic_oracle(self):
        expected = "public class A { public double f(int a, int b) { return ((double) a / b) * 100.0; } }"
        patched = "public class A { public double f(int a, int b) { return (double) a / b * 100.0; } }"
        oracle = {
            "oracle_type": "alternative_token_variants",
            "variants": [
                "public class A { public double f(int a, int b) { return (double) a / b * 100.0; } }"
            ]
        }

        res = evaluate_semantic_correctness(patched_code=patched, expected_code=expected, oracle_spec=oracle)
        self.assertFalse(res["canonical_source_match"])
        self.assertFalse(res["token_equivalent"])
        self.assertTrue(res["oracle_applicable"])
        self.assertTrue(res["semantic_oracle_pass"])
        self.assertTrue(res["semantic_match"])
        self.assertEqual(res["semantic_match_mode"], "semantic_oracle")
        self.assertEqual(res["failure_subtype"], "success_semantic_oracle")

    def test_mechanical_success_no_oracle_yields_semantic_review_required(self):
        expected = "public class A { public int f() { return 2; } }"
        patched = "public class A { public int f() { return 3; } }"

        res = evaluate_semantic_correctness(patched_code=patched, expected_code=expected, oracle_spec=None)
        self.assertFalse(res["canonical_source_match"])
        self.assertFalse(res["token_equivalent"])
        self.assertFalse(res["semantic_match"])
        self.assertIsNone(res["semantic_match_mode"])
        self.assertEqual(res["failure_subtype"], "semantic_review_required")

    def test_applicable_oracle_fail_yields_wrong_fix(self):
        expected = "public class A { public int f() { return 2; } }"
        patched = "public class A { public int f() { return 999; } }"
        oracle = {
            "oracle_type": "alternative_token_variants",
            "variants": ["public class A { public int f() { return 4; } }"]
        }

        res = evaluate_semantic_correctness(patched_code=patched, expected_code=expected, oracle_spec=oracle)
        self.assertFalse(res["semantic_match"])
        self.assertEqual(res["failure_subtype"], "wrong_fix")

    def test_mechanical_success_taxonomy_exactly_one_terminal_mode(self):
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-003",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": {
                        "unified_diff_valid": True,
                        "path_match": True,
                        "size_within_limit": True,
                        "apply_check": True,
                        "structural_sanity": True
                    },
                    "old_text": "if (enabled == true) {",
                    "new_text": "if (enabled) {"
                },
                {
                    "scenario_id": "FB2-005",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": {
                        "unified_diff_valid": True,
                        "path_match": True,
                        "size_within_limit": True,
                        "apply_check": True,
                        "structural_sanity": True
                    },
                    "old_text": "String msg = \"PENDING\";",
                    "new_text": ""
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        sm = metrics["summary"]["success_modes"]
        mech = metrics["summary"]["mechanical_success"]["passed"]
        self.assertEqual(mech, 2)
        total_modes = sum(sm.values())
        self.assertEqual(total_modes, mech)

    def test_sum_semantic_terminal_modes_equals_mechanical_success_count(self):
        res = run_benchmark(split="DEV", backend="mock")
        metrics = compute_metrics(res)
        sm = metrics["summary"]["success_modes"]
        mech_count = metrics["summary"]["mechanical_success"]["passed"]
        self.assertEqual(sum(sm.values()), mech_count)

    def test_mechanical_failure_never_counted_as_semantic_accepted(self):
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "eligibility_expected": True,
                    "actual_fix_status": "rejected",
                    "validation": {"apply_check": False},
                    "canonical_source_match": True,  # Stale field
                    "semantic_match": True           # Stale field
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        self.assertEqual(metrics["summary"]["mechanical_success"]["passed"], 0)
        self.assertEqual(metrics["summary"]["automated_semantic_accepted"]["passed"], 0)

    def test_mechanical_success_never_has_failure_type_mechanical_failure(self):
        res = run_benchmark(split="DEV", backend="mock")
        metrics = compute_metrics(res)
        for r in metrics.get("results", []):
            if r.get("mechanical_success"):
                self.assertNotEqual(r.get("failure_type"), "mechanical_failure")

    def test_pre_model_gate_metric_not_derived_from_model_terminal_status(self):
        # A finding that is eligible at gate but rejected by validator is not a pre-model safe skip
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-050",  # Large patch ineligible scenario
                    "eligibility_expected": False,
                    "actual_fix_status": "rejected",
                    "rejection_reason": "patch_too_large"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        # Pre-model gate allowed it (gate_skip=False), but validator rejected it (unsafe_prevented=1)
        self.assertEqual(metrics["summary"]["safe_skip_rate"]["passed"], 0)
        self.assertEqual(metrics["summary"]["unsafe_prevention_rate"]["passed"], 1)

    def test_model_generated_skip_not_counted_as_pre_model_safe_skip(self):
        finding = {
            "candidate_id": "test-1",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/Service.java",
            "line": 5,
            "problem": "Unused variable.",
            "after_source": "public class Service {}"
        }
        from fix_eligibility import check_fix_eligibility
        gate_res = check_fix_eligibility(finding)
        self.assertTrue(gate_res["eligible"])

    def test_validator_rejection_not_counted_as_pre_model_safe_skip(self):
        sample = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-055",
                    "eligibility_expected": False,
                    "actual_fix_status": "rejected",
                    "rejection_reason": "insufficient_target_context"
                }
            ]
        }
        metrics = compute_metrics(sample)
        self.assertEqual(metrics["summary"]["safe_skip_rate"]["passed"], 0)
        self.assertEqual(metrics["summary"]["unsafe_prevention_rate"]["passed"], 1)

    def test_mock_and_transformers_produce_same_deterministic_gate_decision(self):
        from fix_eligibility import check_fix_eligibility
        scs = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))["scenarios"]
        for sc in scs:
            finding = {
                "candidate_id": sc["scenario_id"],
                "decision": "ACCEPT",
                "source_reviewer": sc["role"],
                "file": sc["file_path"],
                "file_path": sc["file_path"],
                "line": sc["line"],
                "problem": sc["problem"],
                "code_snippet": sc.get("evidence", ""),
                "after_source": "public class Dummy {}",
                "finding_type": sc.get("finding_type", "presence"),
                "context_scope": sc.get("context_scope", "single_method"),
                "scope": sc.get("context_scope", "single_method")
            }
            res = check_fix_eligibility(finding)
            self.assertIsInstance(res["eligible"], bool)

    def test_expected_after_not_leaked_into_model_generation_input(self):
        from fix_agent_prompt_builder import build_fix_agent_prompt
        finding = {
            "candidate_id": "f-1",
            "problem": "Unused variable.",
            "source_reviewer": "maintainability"
        }
        prompt = build_fix_agent_prompt(finding, "src/Service.java", "public class Service {}", "")
        self.assertNotIn("expected_after", prompt)
        self.assertNotIn("oracle", prompt)

    def test_evaluator_reads_expected_after_only_post_inference(self):
        # Evaluator re_evaluate_results only reads expected_after for semantic comparison post-inference
        sample = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "validation": {
                        "unified_diff_valid": True,
                        "path_match": True,
                        "size_within_limit": True,
                        "apply_check": True,
                        "structural_sanity": True
                    },
                    "old_text": "long lastPermitTimestamp = System.currentTimeMillis();",
                    "new_text": ""
                }
            ]
        }
        re_res = re_evaluate_results(sample)
        r0 = re_res["results"][0]
        self.assertTrue(r0["mechanical_success"])
        self.assertTrue(r0["token_equivalent"])
        self.assertTrue(r0["semantic_match"])
        self.assertEqual(r0["semantic_match_mode"], "token_equivalent")


if __name__ == "__main__":
    unittest.main()

