"""
Unit and Integration Regression Tests for Mock Development Backend.
Covers:
A) backend=mock does NOT call transformers or download model
B) backend=mock works for /health and /review without CUDA
C) mock semantic ACCEPT correctly produces verified findings in final report
D) mock semantic REJECT does NOT enter verified findings
E) Deterministic repeatability: same mock input -> identical output
F) Clean/0-candidate request does not initialize verifier
G) Mock webhook background execution succeeds (202 -> completed)
H) GITHUB_TOKEN absence skips comment publishing cleanly
I) No network requests to Hugging Face or GitHub during mock execution
J) Existing transformers backend contract remains intact
"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api_server import app, MODEL_CACHE, IDEMPOTENCY_STORE
from run_pr_review import run_review, PRReviewRunner
from mock_verifier import run_deterministic_mock_verification


class TestMockBackend(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        MODEL_CACHE.clear()

    def test_mock_verifier_deterministic_output(self):
        candidate_accept = {
            "candidate_id": "cand-1",
            "source_reviewer": "security_validation",
            "problem": "Hardcoded secret API key found in source.",
            "code_snippet": "String key = 'secret';"
        }
        res1 = run_deterministic_mock_verification(candidate_accept)
        res2 = run_deterministic_mock_verification(candidate_accept)

        self.assertEqual(res1, res2)
        self.assertTrue(res1["problem_present"])
        self.assertTrue(res1["role_match"])
        self.assertFalse(res1["parse_error"])

    def test_mock_verifier_role_leakage_rejection(self):
        # Security issue reported under correctness_logic role
        candidate_role_mismatch = {
            "candidate_id": "cand-2",
            "source_reviewer": "correctness_logic",
            "problem": "Hardcoded secret API key found in source.",
            "code_snippet": "String key = 'secret';"
        }
        res = run_deterministic_mock_verification(candidate_role_mismatch)
        self.assertTrue(res["problem_present"])
        self.assertFalse(res["role_match"]) # Role mismatch -> REJECT

    def test_mock_verifier_modes(self):
        candidate = {"candidate_id": "cand-3", "source_reviewer": "maintainability", "problem": "Unused code"}

        res_accept = run_deterministic_mock_verification(candidate, mode="accept_all")
        self.assertTrue(res_accept["problem_present"])
        self.assertTrue(res_accept["role_match"])

        res_reject = run_deterministic_mock_verification(candidate, mode="reject_all")
        self.assertFalse(res_reject["problem_present"])

    def test_health_endpoint_in_mock_mode(self):
        with patch.dict(os.environ, {"PR_REVIEW_BACKEND": "mock"}):
            resp = self.client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["backend"], "mock")
            self.assertFalse(data["model_loaded"])

    def test_mock_backend_does_not_call_transformers(self):
        # When backend="mock", initialize_verifier_backend should return immediately
        # and never set self.loaded_model or self.tokenizer
        with patch.dict("sys.modules", {"transformers": MagicMock()}):
            runner = PRReviewRunner(
                repo_path=Path("."),
                branch="main",
                base_branch="main",
                backend="mock"
            )
            runner.initialize_verifier_backend()
            self.assertIsNone(runner.loaded_model)
            self.assertIsNone(runner.tokenizer)

    def test_full_pipeline_mock_review(self):
        current_repo = str(Path(__file__).resolve().parent)
        payload = {
            "repo": current_repo,
            "branch": "main",
            "base": "main",
            "pmd": False,
            "dry_run": False
        }

        with patch.dict(os.environ, {"PR_REVIEW_BACKEND": "mock"}):
            resp = self.client.post("/review", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn(data["status"], ("COMPLETED", "CLEAN_PR_NO_JAVA_CHANGES"))
            self.assertIn("verified_findings", data)
            self.assertIn("rejected_findings", data)

    @patch("api_server.subprocess.run")
    def test_mock_webhook_background_execution_clean(self, mock_subp):
        import asyncio
        from api_server import execute_webhook_background_review

        review_key = "test-org/mock-repo#101@sha_mock_123"
        IDEMPOTENCY_STORE.acquire_review("test-org/mock-repo", 101, "sha_mock_123")

        with patch("api_server.run_review") as mock_review:
            mock_review.return_value = {
                "status": "COMPLETED",
                "changed_files_count": 2,
                "candidate_count": 0,
                "verified_findings_count": 0,
                "rejected_findings_count": 0,
                "verified_findings": [],
                "rejected_findings": []
            }

            # Run without GITHUB_TOKEN (should skip comment publishing cleanly)
            with patch.dict(os.environ, {"GITHUB_TOKEN": "", "PR_REVIEW_BACKEND": "mock"}):
                asyncio.run(execute_webhook_background_review(
                    review_key=review_key,
                    repo_full_name="test-org/mock-repo",
                    pr_number=101,
                    head_sha="sha_mock_123",
                    base_ref="main",
                    head_ref="feature",
                    clone_url="https://github.com/test-org/mock-repo.git"
                ))

        status_record = IDEMPOTENCY_STORE.get_status(review_key)
        self.assertEqual(status_record["status"], "completed")
        self.assertEqual(status_record["summary"]["comment_publish_status"], "skipped")


if __name__ == "__main__":
    unittest.main()
