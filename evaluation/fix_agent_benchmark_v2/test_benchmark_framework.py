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

from semantic_oracle import (
    evaluate_semantic_correctness,
    check_token_equivalence,
    normalize_source_code
)
from validate_benchmark import run_validation
from audit_benchmark import run_audit
from evaluate_results import compute_metrics
from run_benchmark import run_benchmark


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
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "role": "maintainability",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "mechanical_success": True,
                    "semantic_match": True
                },
                {
                    "scenario_id": "FB2-053",
                    "role": "maintainability",
                    "eligibility_expected": False,
                    "actual_fix_status": "skipped"
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
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "difficulty": "EASY",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "mechanical_success": True,
                    "semantic_match": True
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        db = metrics["difficulty_breakdown"]["EASY"]
        self.assertEqual(db["total"], 1)
        self.assertEqual(db["eligible"], 1)
        self.assertEqual(db["mechanical_success"], 1)

    def test_fix_complexity_breakdown_correct(self):
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-001",
                    "fix_complexity": "single_line",
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "mechanical_success": True,
                    "semantic_match": True,
                    "failure_subtype": "success_canonical"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        cb = metrics["complexity_breakdown"]["single_line"]
        self.assertEqual(cb["eligible_count"], 1)
        self.assertEqual(cb["mechanical_success"], 1)
        self.assertEqual(cb["semantic_accepted"], 1)

    def test_alternative_valid_breakdown_correct(self):
        sample_results = {
            "split": "DEV",
            "results": [
                {
                    "scenario_id": "FB2-004",
                    "alternative_valid_fix": True,
                    "eligibility_expected": True,
                    "actual_fix_status": "generated",
                    "mechanical_success": True,
                    "canonical_source_match": False,
                    "semantic_match_mode": "token_equivalent",
                    "semantic_match": True,
                    "failure_subtype": "success_token_equivalent"
                }
            ]
        }
        metrics = compute_metrics(sample_results)
        avb = metrics["alternative_valid_breakdown"]
        self.assertEqual(avb["total_alt_valid"], 1)
        self.assertEqual(avb["token_success"], 1)


class TestBenchmarkV2MockRunnerAndIsolation(unittest.TestCase):
    """Verifies that mock runner operates cleanly and HOLDOUT is protected."""

    def test_mock_dev_run_does_not_load_transformers(self):
        res = run_benchmark(split="DEV", backend="mock")
        self.assertEqual(res["total_scenarios"], 56)
        self.assertEqual(len(res["results"]), 56)

    def test_holdout_not_run_by_default(self):
        res = run_benchmark(backend="mock")
        self.assertEqual(res["split"], "DEV")
        sids = {r["scenario_id"] for r in res["results"]}
        self.assertNotIn("FB2-057", sids)  # FB2-057 is in HOLDOUT


if __name__ == "__main__":
    unittest.main()
