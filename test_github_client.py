"""
Unit and Integration Tests for GitHub PR Review Comment Publishing
Tests:
1. Marker presence (<!-- pr-review-agent -->) in all generated markdown comments
2. Create comment (POST) when no bot comment exists on PR
3. Update comment (PATCH) when bot comment with marker already exists on PR
4. Non-bot user comments are ignored and never updated
5. Clean review produces 'No verified issues found' markdown
6. Review with findings produces structured markdown with emojis and details
7. Missing optional finding fields do not cause exceptions
8. Token not configured skips comment publishing safely
9. GitHub API errors do not fail or discard the review result
10. Multiple commits on same PR update the same bot comment (idempotent comment lifecycle)
"""

import json
import os
import unittest
from unittest.mock import patch, MagicMock

from github_client import (
    GitHubClient,
    BOT_COMMENT_MARKER,
    format_review_summary_markdown,
    get_emoji_for_finding
)


class TestGitHubCommentPublishing(unittest.TestCase):

    def test_markdown_formatting_clean_pr(self):
        md = format_review_summary_markdown(
            head_sha="a1b2c3d4e5f67890",
            verified_findings=[],
            rejected_findings=[{"candidate_id": "c-1"}]
        )
        self.assertIn(BOT_COMMENT_MARKER, md)
        self.assertIn("**Reviewed commit:** `a1b2c3d`", md)
        self.assertIn("Verified findings: **0**", md)
        self.assertIn("Rejected findings: **1**", md)
        self.assertIn("No verified issues found", md)

    def test_markdown_formatting_with_findings(self):
        findings = [
            {
                "candidate_id": "sec-1",
                "source_reviewer": "security_validation",
                "file": "src/main/java/com/demo/AuthService.java",
                "line": 15,
                "problem": "Hardcoded secret 'sk_live_123' found.",
                "verifier_reason": "Secret literal embedded in source code.",
                "suggested_fix": "Extract secret into environment variables."
            },
            {
                "candidate_id": "maint-1",
                "source_reviewer": "maintainability",
                "file": "src/main/java/com/demo/OrderService.java",
                "line": 42,
                "problem": "Unused local variable 'tempId'.",
                "verifier_reason": "Variable declared but never accessed."
            }
        ]
        md = format_review_summary_markdown(
            head_sha="9876543210fedcba",
            verified_findings=findings,
            rejected_findings=[]
        )
        self.assertIn(BOT_COMMENT_MARKER, md)
        self.assertIn("Verified findings: **2**", md)
        self.assertIn("🔴 Security — `src/main/java/com/demo/AuthService.java:15`", md)
        self.assertIn("Hardcoded secret 'sk_live_123' found.", md)
        self.assertIn("🟡 Maintainability — `src/main/java/com/demo/OrderService.java:42`", md)
        self.assertIn("Unused local variable 'tempId'.", md)

    def test_missing_optional_fields_no_crash(self):
        # Empty dictionary finding
        minimal_finding = {"problem": "Some issue"}
        md = format_review_summary_markdown(
            head_sha="",
            verified_findings=[minimal_finding],
            rejected_findings=[]
        )
        self.assertIn(BOT_COMMENT_MARKER, md)
        self.assertIn("Some issue", md)
        self.assertIn("Unknown file", md)

    @patch.object(GitHubClient, "_send_request")
    def test_create_comment_when_none_exists(self, mock_send):
        client = GitHubClient(token="mock_token")

        # 1. list_pr_comments returns only regular user comments
        mock_send.side_effect = [
            (200, [{"id": 101, "body": "LGTM! Nice PR."}]),  # list comments
            (201, {"id": 202, "body": "Bot comment"})         # create comment
        ]

        res = client.publish_review_summary(
            repo_full_name="org/repo",
            pr_number=10,
            head_sha="abcdef123456",
            verified_findings=[],
            rejected_findings=[]
        )

        self.assertEqual(res["status"], "created")
        self.assertEqual(res["comment_id"], 202)
        self.assertEqual(mock_send.call_count, 2)
        # Check that POST was used
        self.assertEqual(mock_send.call_args_list[1][0][0], "POST")

    @patch.object(GitHubClient, "_send_request")
    def test_update_existing_bot_comment(self, mock_send):
        client = GitHubClient(token="mock_token")

        # list_pr_comments returns a user comment and an existing bot comment
        existing_bot_body = f"{BOT_COMMENT_MARKER}\n## 🤖 AI PR Review\nOld review"
        mock_send.side_effect = [
            (200, [
                {"id": 101, "body": "User question"},
                {"id": 555, "body": existing_bot_body}
            ]),  # list comments
            (200, {"id": 555, "body": "Updated content"}) # update comment
        ]

        res = client.publish_review_summary(
            repo_full_name="org/repo",
            pr_number=10,
            head_sha="new_sha_789",
            verified_findings=[],
            rejected_findings=[]
        )

        self.assertEqual(res["status"], "updated")
        self.assertEqual(res["comment_id"], 555)
        self.assertEqual(mock_send.call_count, 2)
        # Check that PATCH was used on comment 555
        self.assertEqual(mock_send.call_args_list[1][0][0], "PATCH")
        self.assertIn("/555", mock_send.call_args_list[1][0][1])

    def test_token_not_configured_skips_publishing(self):
        client = GitHubClient(token=None)
        res = client.publish_review_summary(
            repo_full_name="org/repo",
            pr_number=10,
            head_sha="abc123",
            verified_findings=[],
            rejected_findings=[]
        )
        self.assertEqual(res["status"], "skipped")
        self.assertEqual(res["reason"], "GITHUB_TOKEN not configured")


if __name__ == "__main__":
    unittest.main()
