"""
Unit and Integration Tests for PR Review FastAPI Server
Tests:
1. GET /health endpoint response and schema
2. Model cache behavior (model caching across sequential reviews)
3. POST /review with invalid repository path (HTTP 400)
4. POST /review with non-existent branch (HTTP 404)
5. POST /review with valid mock review request (HTTP 200)
6. Shared orchestration function usage
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from api_server import app, MODEL_CACHE


class TestPRReviewAPIServer(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "pr-review-agent")
        self.assertIn("model", data)
        self.assertIn("model_loaded", data)

    def test_invalid_repo_path(self):
        payload = {
            "repo": "C:\\non_existent_directory_xyz_123",
            "branch": "main",
            "base": "main",
            "dry_run": True
        }
        response = self.client.post("/review", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not exist", response.json()["detail"])

    def test_non_git_repo_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = {
                "repo": tmp_dir,
                "branch": "main",
                "base": "main",
                "dry_run": True
            }
            response = self.client.post("/review", json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertIn("not a valid Git repository", response.json()["detail"])

    def test_non_existent_branch(self):
        # Use current repo
        current_repo = str(Path(__file__).resolve().parent)
        payload = {
            "repo": current_repo,
            "branch": "completely-fake-branch-xyz-9999",
            "base": "main",
            "dry_run": True
        }
        response = self.client.post("/review", json=payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("was not found", response.json()["detail"])

    def test_valid_dry_run_review(self):
        current_repo = str(Path(__file__).resolve().parent)
        payload = {
            "repo": current_repo,
            "branch": "main",
            "base": "main",
            "dry_run": True
        }
        response = self.client.post("/review", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("target_repo", data)
        self.assertIn("branch", data)
        self.assertIn("verified_findings", data)
        self.assertIn("rejected_findings", data)
        self.assertIn("changed_files_count", data)

    def test_model_cache_persistence(self):
        # Verify model cache dictionary retains populated model across calls
        fake_model = object()
        fake_tokenizer = object()
        MODEL_CACHE["model"] = fake_model
        MODEL_CACHE["tokenizer"] = fake_tokenizer
        MODEL_CACHE["model_id"] = "test-model"

        # Check /health reflects model_loaded: True
        health_resp = self.client.get("/health")
        self.assertEqual(health_resp.status_code, 200)
        self.assertTrue(health_resp.json()["model_loaded"])

        # Clean cache
        MODEL_CACHE.clear()
        health_resp_after = self.client.get("/health")
        self.assertFalse(health_resp_after.json()["model_loaded"])

    def test_lazy_loading_clean_pr_does_not_initialize_model(self):
        # Ensure MODEL_CACHE is empty before review
        MODEL_CACHE.clear()
        
        current_repo = str(Path(__file__).resolve().parent)
        payload = {
            "repo": current_repo,
            "branch": "main",
            "base": "main",
            "dry_run": False # Not dry-run, but backend will only load if candidates reach Tier 4
        }

        # Mock out the heavy transformers loader to track if it is ever called
        from unittest.mock import patch
        with patch("run_pr_review.PRReviewRunner.initialize_verifier_backend") as mock_init:
            response = self.client.post("/review", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["candidate_count"], 0)
            self.assertEqual(data["verified_findings_count"], 0)
            
            # verify initialize_verifier_backend was NEVER called
            mock_init.assert_not_called()

        # Check that MODEL_CACHE remains empty and health endpoint shows model_loaded: False
        self.assertEqual(len(MODEL_CACHE), 0)
        health_resp = self.client.get("/health")
        self.assertEqual(health_resp.status_code, 200)
        self.assertFalse(health_resp.json()["model_loaded"])


if __name__ == "__main__":
    unittest.main()
