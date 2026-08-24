"""
Comprehensive Tests for GitHub Webhook Ingestion in PR Review FastAPI Server
Tests:
1. Valid HMAC signature verification (202 Accepted)
2. Invalid HMAC signature (401 Unauthorized)
3. Missing HMAC signature when secret configured (401 Unauthorized)
4. Unsupported event type (ignored - 200 OK)
5. Unsupported pull_request action (ignored - 200 OK)
6. Allowlisted repo accepted (202 Accepted)
7. Non-allowlisted repo rejected (403 Forbidden)
8. Malformed or missing payload fields (400 Bad Request)
9. Idempotency: Duplicate review key ignored (status: duplicate)
10. Idempotency: Different SHA produces new review
11. Idempotency: Failed review can be retried
12. Fast response time (background task execution without blocking HTTP response)
13. Webhook status endpoint (/webhook/reviews/{key})
"""

import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api_server import app, IDEMPOTENCY_STORE


def compute_signature(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


class TestGitHubWebhook(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        IDEMPOTENCY_STORE.clear()

    def get_sample_payload(self, repo="acme/orderapp-server", pr_number=42, sha="abc123456789", action="opened"):
        return {
            "action": action,
            "repository": {
                "full_name": repo,
                "clone_url": f"https://github.com/{repo}.git"
            },
            "pull_request": {
                "number": pr_number,
                "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                "head": {
                    "sha": sha,
                    "ref": "feature-auth"
                },
                "base": {
                    "ref": "main"
                }
            }
        }

    @patch("api_server.execute_webhook_background_review")
    def test_valid_hmac_signature_accepted(self, mock_bg):
        secret = "super_secret_webhook_token"
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret, "GITHUB_ALLOWED_REPOS": ""}):
            payload = self.get_sample_payload()
            raw_body = json.dumps(payload).encode("utf-8")
            sig = compute_signature(secret, raw_body)

            headers = {
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 202)
            data = response.json()
            self.assertEqual(data["status"], "accepted")
            self.assertEqual(data["repository"], "acme/orderapp-server")
            self.assertEqual(data["pr_number"], 42)

    def test_invalid_hmac_signature_unauthorized(self):
        secret = "super_secret_webhook_token"
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            payload = self.get_sample_payload()
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=invalid_hex_signature_here",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertIn("Invalid webhook signature", response.json()["detail"])

    def test_missing_hmac_signature_when_secret_configured(self):
        secret = "super_secret_webhook_token"
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            payload = self.get_sample_payload()
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertIn("Missing X-Hub-Signature-256", response.json()["detail"])

    def test_unsupported_event_ignored(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": ""}):
            payload = {"action": "created", "issue": {"number": 1}}
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ignored")

    def test_unsupported_pull_request_action_ignored(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": ""}):
            payload = self.get_sample_payload(action="closed")
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ignored")
            self.assertIn("Unsupported action", response.json()["reason"])

    @patch("api_server.execute_webhook_background_review")
    def test_allowlisted_repo_accepted(self, mock_bg):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": "org/repo1,acme/orderapp-server,org/repo2"}):
            payload = self.get_sample_payload(repo="acme/orderapp-server")
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["status"], "accepted")

    def test_non_allowlisted_repo_forbidden(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": "org/repo1,org/repo2"}):
            payload = self.get_sample_payload(repo="malicious/target-repo")
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 403)
            self.assertIn("not authorized for review", response.json()["detail"])

    def test_missing_critical_payload_fields(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": ""}):
            # Missing pull_request object
            payload = {"action": "opened", "repository": {"full_name": "acme/repo"}}
            raw_body = json.dumps(payload).encode("utf-8")

            headers = {
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json"
            }
            response = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(response.status_code, 400)

    @patch("api_server.execute_webhook_background_review")
    def test_idempotency_duplicate_and_sha_evolution(self, mock_bg):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": ""}):
            payload_sha1 = self.get_sample_payload(sha="sha_first_commit_111")
            raw_body_1 = json.dumps(payload_sha1).encode("utf-8")
            headers = {"X-GitHub-Event": "pull_request", "Content-Type": "application/json"}

            # 1. First Delivery -> 202 Accepted
            resp1 = self.client.post("/webhook/github", data=raw_body_1, headers=headers)
            self.assertEqual(resp1.status_code, 202)
            review_key_1 = resp1.json()["review_key"]

            # 2. Duplicate Delivery with same SHA -> 200 Duplicate (pipeline not triggered again)
            resp2 = self.client.post("/webhook/github", data=raw_body_1, headers=headers)
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["status"], "duplicate")

            # 3. New commit pushed (synchronize with new SHA) -> 202 Accepted (new review)
            payload_sha2 = self.get_sample_payload(sha="sha_second_commit_222", action="synchronize")
            raw_body_2 = json.dumps(payload_sha2).encode("utf-8")
            resp3 = self.client.post("/webhook/github", data=raw_body_2, headers=headers)
            self.assertEqual(resp3.status_code, 202)
            self.assertEqual(resp3.json()["status"], "accepted")
            self.assertNotEqual(resp3.json()["review_key"], review_key_1)

    @patch("api_server.execute_webhook_background_review")
    def test_idempotency_failed_review_can_be_retried(self, mock_bg):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": ""}):
            payload = self.get_sample_payload(sha="failed_commit_sha")
            raw_body = json.dumps(payload).encode("utf-8")
            headers = {"X-GitHub-Event": "pull_request", "Content-Type": "application/json"}

            # 1. First delivery
            resp1 = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(resp1.status_code, 202)
            key = resp1.json()["review_key"]

            # Mark key as failed in store
            IDEMPOTENCY_STORE.mark_failed(key, "Git clone timeout")
            self.assertEqual(IDEMPOTENCY_STORE.get_status(key)["status"], "failed")

            # 2. Retry delivery with same key -> accepted for re-processing
            resp2 = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(resp2.status_code, 202)
            self.assertEqual(resp2.json()["status"], "accepted")
            self.assertEqual(IDEMPOTENCY_STORE.get_status(key)["status"], "processing")

    def test_status_endpoint(self):
        import urllib.parse
        key = "acme/repo#10@sha123"
        IDEMPOTENCY_STORE.acquire_review("acme/repo", 10, "sha123")
        IDEMPOTENCY_STORE.mark_completed(key, summary={"verified_findings_count": 2, "candidate_count": 5})

        # Test path parameter
        quoted_key = urllib.parse.quote(key, safe="")
        response = self.client.get(f"/webhook/reviews/{quoted_key}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["review_key"], key)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["summary"]["verified_findings_count"], 2)

        # Test query parameter endpoint
        response_query = self.client.get("/webhook/status", params={"review_key": key})
        self.assertEqual(response_query.status_code, 200)
        self.assertEqual(response_query.json()["review_key"], key)

    @patch("api_server.execute_webhook_background_review")
    def test_duplicate_webhook_does_not_trigger_second_review_task(self, mock_bg):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "", "GITHUB_ALLOWED_REPOS": ""}):
            payload = self.get_sample_payload(sha="duplicate_check_sha")
            raw_body = json.dumps(payload).encode("utf-8")
            headers = {"X-GitHub-Event": "pull_request", "Content-Type": "application/json"}

            # First delivery triggers background task
            resp1 = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(resp1.status_code, 202)
            self.assertEqual(mock_bg.call_count, 1)

            # Duplicate delivery does NOT trigger background task
            resp2 = self.client.post("/webhook/github", data=raw_body, headers=headers)
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["status"], "duplicate")
            self.assertEqual(mock_bg.call_count, 1) # Still 1

    @patch("api_server.run_review")
    @patch("api_server.subprocess.run")
    @patch("api_server.GitHubClient.publish_review_summary")
    def test_github_comment_failure_preserves_completed_review_status(self, mock_publish, mock_subp, mock_review):
        import asyncio
        from api_server import execute_webhook_background_review

        # Mock run_review to return valid findings
        mock_review.return_value = {
            "status": "COMPLETED",
            "changed_files_count": 1,
            "candidate_count": 2,
            "verified_findings_count": 1,
            "rejected_findings_count": 1,
            "verified_findings": [{"candidate_id": "c1"}],
            "rejected_findings": [{"candidate_id": "c2"}]
        }
        # Mock GitHub comment publishing to raise an HTTP exception
        mock_publish.side_effect = RuntimeError("GitHub API 403 Forbidden")

        review_key = "org/repo#99@sha_test_comment_err"
        IDEMPOTENCY_STORE.acquire_review("org/repo", 99, "sha_test_comment_err")

        # Run background execution directly
        asyncio.run(execute_webhook_background_review(
            review_key=review_key,
            repo_full_name="org/repo",
            pr_number=99,
            head_sha="sha_test_comment_err",
            base_ref="main",
            head_ref="feature",
            clone_url="https://github.com/org/repo.git"
        ))

        # Check status is COMPLETED and comment_publish_status is failed
        status_record = IDEMPOTENCY_STORE.get_status(review_key)
        self.assertIsNotNone(status_record)
        self.assertEqual(status_record["status"], "completed")
        summary = status_record["summary"]
        self.assertEqual(summary["verified_findings_count"], 1)
        self.assertEqual(summary["comment_publish_status"], "failed")
        self.assertIn("GitHub API 403 Forbidden", summary["comment_publish_error"])


if __name__ == "__main__":
    unittest.main()
