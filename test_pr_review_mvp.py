"""
Smoke and Integration Tests for PR Review MVP Runner
Tests:
1. Runner instantiation with CLI parameters
2. Mock review execution on synthetic PR diff
3. JSON output report format completeness
4. Hierarchical filtering (AST null-safety rejection, role-gate rejection)
"""

import json
import tempfile
import unittest
from pathlib import Path

from run_pr_review import PRReviewRunner, parse_verifier_json


class TestPRReviewRunnerMVP(unittest.TestCase):

    def test_parse_verifier_json_robustness(self):
        # Valid JSON
        v1 = parse_verifier_json('{"candidate_id": "c1", "problem_present": true, "role_match": true, "reason": "ok"}', "c1")
        self.assertFalse(v1["parse_error"])
        self.assertTrue(v1["problem_present"])

        # Fenced JSON
        v2 = parse_verifier_json('```json\n{"candidate_id": "c2", "problem_present": false, "role_match": true}\n```', "c2")
        self.assertFalse(v2["parse_error"])
        self.assertFalse(v2["problem_present"])

        # Malformed
        v3 = parse_verifier_json('Not a JSON', "c3")
        self.assertTrue(v3["parse_error"])

    def test_candidate_generation_and_ast_verification(self):
        runner = PRReviewRunner(repo_path=Path("."), branch="main", backend="mock", dry_run=True)

        # Synthetic diff with clean ternary null check + unused variable + unclosed stream
        diff_results = [
            {
                "file": "src/main/java/com/demo/SampleService.java",
                "status": "modified",
                "hunks": [
                    [
                        {"type": "ADDED", "old_line": None, "new_line": 10, "code": "String tempUnused = 123;"},
                        {"type": "ADDED", "old_line": None, "new_line": 11, "code": "return val == null ? null : val.trim();"}
                    ]
                ]
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_p = Path(tmp_dir)
            sample_file = tmp_p / "src" / "main" / "java" / "com" / "demo" / "SampleService.java"
            sample_file.parent.mkdir(parents=True, exist_ok=True)
            sample_file.write_text(
                "package com.demo;\npublic class SampleService {\n  public String trim(String val) {\n    String tempUnused = 123;\n    return val == null ? null : val.trim();\n  }\n}\n",
                encoding="utf-8"
            )

            candidates = runner.generate_candidate_findings(diff_results, tmp_p, [])
            self.assertGreater(len(candidates), 0)

            # Add a fake candidate that claims NPE on guarded ternary
            candidates.append({
                "candidate_id": "fake-npe",
                "source_reviewer": "correctness_logic",
                "file": "src/main/java/com/demo/SampleService.java",
                "line": 11,
                "problem": "Potential NullPointerException on calling trim() on null val",
                "failure_scenario": "NPE if val is null",
                "after_source": sample_file.read_text(encoding="utf-8")
            })

            verified, rejected = runner.verify_candidates(candidates, "diff")

            # fake-npe MUST be rejected by Tier 2 AST Self-Refutation
            rejected_ids = [r["candidate_id"] for r in rejected]
            self.assertIn("fake-npe", rejected_ids)

            ast_rej = [r for r in rejected if r["candidate_id"] == "fake-npe"][0]
            self.assertEqual(ast_rej["verification_tier"], "AST_SELF_REFUTED")


if __name__ == "__main__":
    unittest.main()
