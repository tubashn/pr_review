"""
Comprehensive Unit and Integration Tests for Fix Agent V1
Tests:
1. Eligibility Gate (Role, Security, Absence, File Types, Line Limits)
2. Deterministic Patch Validator (Syntax, Path Safety, Traversal, Ops, 20-line Limit, Apply, AST Sanity)
3. Fix Agent Prompt Builder (Omits candidate suggested_fix, JSON-only schema)
4. Deterministic Mock Fix Agent (Schema conformity, predictable patches)
5. Orchestration & Lazy Loading (No model load for ineligible/empty findings)
6. GitHub Summary Comment Markdown Rendering with Suggested Fixes
7. API Server Integration with suggest_fixes request flag
"""

import json
import unittest
from pathlib import Path
from typing import Any, Dict

from fix_eligibility import check_fix_eligibility, is_security_finding, is_absence_type_finding
from patch_validator import (
    validate_patch,
    count_changed_lines,
    parse_unified_diff_headers,
    check_path_safety,
    apply_unified_diff_to_text,
    check_structural_java_sanity
)
from fix_agent_prompt_builder import build_fix_agent_prompt
from mock_fix_agent import run_deterministic_mock_fix
from fix_agent import generate_fix_suggestions, run_fix_agent_for_finding
from github_client import format_review_summary_markdown


class TestFixEligibilityGate(unittest.TestCase):
    """Unit tests for deterministic eligibility filtering."""

    def test_eligible_correctness_finding(self):
        finding = {
            "candidate_id": "c-1",
            "decision": "ACCEPT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/OrderService.java",
            "problem": "Incorrect discount calculation when customer is VIP.",
            "code_snippet": "double total = price - (price * discount);",
            "after_source": "public double calculate(double price, double discount) { return price - (price * discount); }"
        }
        res = check_fix_eligibility(finding)
        self.assertTrue(res["eligible"])
        self.assertEqual(res["reason"], "eligible_for_fix")

    def test_eligible_maintainability_finding(self):
        finding = {
            "candidate_id": "c-2",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/Util.java",
            "problem": "Redundant boolean comparison in expression: `isValid == true`.",
            "code_snippet": "if (isValid == true) {",
            "after_source": "if (isValid == true) { doSomething(); }"
        }
        res = check_fix_eligibility(finding)
        self.assertTrue(res["eligible"])

    def test_reject_unverified_finding(self):
        finding = {
            "candidate_id": "c-3",
            "decision": "REJECT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/OrderService.java",
            "problem": "Potential bug"
        }
        res = check_fix_eligibility(finding)
        self.assertFalse(res["eligible"])
        self.assertEqual(res["reason"], "unverified_or_rejected_finding")

    def test_reject_security_finding(self):
        finding = {
            "candidate_id": "c-4",
            "decision": "ACCEPT",
            "source_reviewer": "security_validation",
            "file": "src/main/java/com/example/AuthService.java",
            "problem": "Hardcoded JWT secret token literal in source code.",
            "code_snippet": "String secret = 'whsec_1234567890';"
        }
        res = check_fix_eligibility(finding)
        self.assertFalse(res["eligible"])
        self.assertEqual(res["reason"], "security_findings_not_auto_fixed")

    def test_reject_absence_type_finding(self):
        finding = {
            "candidate_id": "c-5",
            "decision": "ACCEPT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/FileService.java",
            "problem": "Unclosed resource: `new FileInputStream()` opened without try-with-resources.",
            "code_snippet": "FileInputStream fis = new FileInputStream(file);"
        }
        res = check_fix_eligibility(finding)
        self.assertFalse(res["eligible"])
        self.assertEqual(res["reason"], "absence_type_not_auto_fixed")

    def test_reject_unsupported_file_type(self):
        finding = {
            "candidate_id": "c-6",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "pom.xml",
            "problem": "Unused dependency in build config."
        }
        res = check_fix_eligibility(finding)
        self.assertFalse(res["eligible"])
        self.assertEqual(res["reason"], "unsupported_file_type")

    def test_reject_multi_file_finding(self):
        finding = {
            "candidate_id": "c-7",
            "decision": "ACCEPT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/OrderService.java",
            "problem": "State inconsistency across files: OrderService and PaymentService mismatch."
        }
        res = check_fix_eligibility(finding)
        self.assertFalse(res["eligible"])
        self.assertEqual(res["reason"], "multi_file_not_supported")


class TestDeterministicPatchValidator(unittest.TestCase):
    """Unit tests for strict patch safety validation."""

    def setUp(self):
        self.java_source = """package com.example;

public class OrderService {
    public boolean processOrder(boolean isValid) {
        if (isValid == true) {
            return true;
        }
        return false;
    }
}
"""

    def test_valid_patch_within_limits(self):
        diff = """--- a/src/main/java/com/example/OrderService.java
+++ b/src/main/java/com/example/OrderService.java
@@ -5,3 +5,3 @@
-        if (isValid == true) {
+        if (isValid) {
"""
        res = validate_patch(diff, "src/main/java/com/example/OrderService.java", self.java_source)
        self.assertTrue(res["valid"])
        self.assertTrue(res["validation"]["unified_diff_valid"])
        self.assertTrue(res["validation"]["path_match"])
        self.assertTrue(res["validation"]["size_within_limit"])
        self.assertTrue(res["validation"]["apply_check"])
        self.assertTrue(res["validation"]["structural_sanity"])
        self.assertEqual(res["changed_lines_count"], 2)

    def test_reject_patch_exceeding_20_lines(self):
        # Generate 22 changed lines
        added_lines = "\n".join([f"+        int x{i} = {i};" for i in range(22)])
        diff = f"""--- a/src/main/java/com/example/OrderService.java
+++ b/src/main/java/com/example/OrderService.java
@@ -5,1 +5,22 @@
{added_lines}"""
        res = validate_patch(diff, "src/main/java/com/example/OrderService.java", self.java_source)
        self.assertFalse(res["valid"])
        self.assertIn("patch_too_large", str(res["rejection_reason"]))

    def test_reject_path_traversal(self):
        diff = """--- a/../etc/passwd
+++ b/../etc/passwd
@@ -1,1 +1,1 @@
-root
+user
"""
        res = validate_patch(diff, "src/main/java/com/example/OrderService.java")
        self.assertFalse(res["valid"])

    def test_reject_unsupported_operations(self):
        diff = """diff --git a/new_file.java b/new_file.java
new file mode 100644
--- /dev/null
+++ b/new_file.java
@@ -0,0 +1,1 @@
+public class NewClass {}
"""
        res = validate_patch(diff, "src/main/java/com/example/OrderService.java")
        self.assertFalse(res["valid"])
        self.assertEqual(res["rejection_reason"], "unsupported_patch_operation")

    def test_reject_unbalanced_braces_structural_sanity(self):
        diff = """--- a/src/main/java/com/example/OrderService.java
+++ b/src/main/java/com/example/OrderService.java
@@ -5,1 +5,1 @@
-        if (isValid == true) {
+        if (isValid == true) { { {
"""
        res = validate_patch(diff, "src/main/java/com/example/OrderService.java", self.java_source)
        self.assertFalse(res["valid"])
        self.assertIn("structural_sanity_failed", str(res["rejection_reason"]))


class TestFixAgentPromptBuilder(unittest.TestCase):
    """Verifies that Fix Agent prompt builder excludes candidate suggested_fix."""

    def test_omits_suggested_fix_from_prompt(self):
        finding = {
            "candidate_id": "cand-99",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/Foo.java",
            "line": 42,
            "problem": "Redundant expression",
            "code_snippet": "boolean x = a == true;",
            "suggested_fix": "SECRET_REVIEWER_SUGGESTION_DO_NOT_LEAK"
        }
        prompt = build_fix_agent_prompt(
            finding=finding,
            file_path="src/main/java/com/example/Foo.java",
            source_context="boolean x = a == true;"
        )
        self.assertNotIn("SECRET_REVIEWER_SUGGESTION_DO_NOT_LEAK", prompt)
        self.assertIn("Redundant expression", prompt)
        self.assertIn("src/main/java/com/example/Foo.java", prompt)


class TestMockFixAgent(unittest.TestCase):
    """Verifies deterministic mock Fix Agent outputs and schema conformity."""

    def test_mock_fix_redundant_boolean(self):
        finding = {
            "candidate_id": "cand-10",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/Bar.java",
            "line": 15,
            "problem": "Redundant boolean comparison in expression: `flag == true`.",
            "code_snippet": "if (flag == true) {",
            "after_source": "public void test() {\n    if (flag == true) {\n        return;\n    }\n}"
        }
        res = run_deterministic_mock_fix(
            finding=finding,
            file_path="src/main/java/com/example/Bar.java",
            source_content=finding["after_source"]
        )
        self.assertEqual(res["finding_id"], "cand-10")
        self.assertEqual(res["file_path"], "src/main/java/com/example/Bar.java")
        self.assertEqual(res["fix_status"], "generated")
        self.assertIn("--- a/src/main/java/com/example/Bar.java", res["diff"])
        self.assertIn("+++ b/src/main/java/com/example/Bar.java", res["diff"])
        self.assertTrue(res["validation"]["unified_diff_valid"])
        self.assertTrue(res["validation"]["path_match"])
        self.assertTrue(res["validation"]["size_within_limit"])
        self.assertIsNone(res["rejection_reason"])

    def test_mock_fix_skipped_on_security(self):
        finding = {
            "candidate_id": "cand-sec",
            "decision": "ACCEPT",
            "source_reviewer": "security_validation",
            "file": "src/main/java/com/example/SecurityConfig.java",
            "problem": "Hardcoded secret token in source.",
            "code_snippet": "String token = 'secret123';"
        }
        res = run_fix_agent_for_finding(finding=finding, backend="mock")
        self.assertEqual(res["fix_status"], "skipped")
        self.assertEqual(res["skip_reason"], "security_findings_not_auto_fixed")


class TestGitHubMarkdownFormatting(unittest.TestCase):
    """Verifies that suggested fixes render cleanly in GitHub PR comment markdown."""

    def test_markdown_with_suggested_fixes(self):
        verified_findings = [{
            "candidate_id": "cand-1",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/Foo.java",
            "line": 10,
            "problem": "Redundant boolean check.",
            "verifier_reason": "Confirmed redundant comparison."
        }]
        fix_suggestions = [{
            "finding_id": "cand-1",
            "file_path": "src/main/java/com/example/Foo.java",
            "fix_status": "generated",
            "diff": "--- a/src/main/java/com/example/Foo.java\n+++ b/src/main/java/com/example/Foo.java\n@@ -10,1 +10,1 @@\n-if (x == true)\n+if (x)",
            "explanation": "Simplified boolean comparison directly."
        }]

        md = format_review_summary_markdown(
            head_sha="abcdef123456",
            verified_findings=verified_findings,
            rejected_findings=[],
            fix_suggestions=fix_suggestions
        )

        self.assertIn("### 💡 Suggested Fixes", md)
        self.assertIn("⚠️ **Unverified suggestion — manual review required.**", md)
        self.assertIn("#### Fix for `cand-1` (`src/main/java/com/example/Foo.java`)", md)
        self.assertIn("```diff", md)
        self.assertIn("-if (x == true)", md)
        self.assertIn("+if (x)", md)
        self.assertIn("*Simplified boolean comparison directly.*", md)


class TestPipelineFixAgentIntegration(unittest.TestCase):
    """Verifies end-to-end orchestration of Fix Agent across multiple finding types."""

    def test_mixed_findings_fix_generation(self):
        findings = [
            {
                "candidate_id": "cand-maintainability",
                "decision": "ACCEPT",
                "source_reviewer": "maintainability",
                "file": "src/main/java/com/example/Service.java",
                "line": 2,
                "problem": "Redundant boolean comparison in expression: `isValid == true`.",
                "code_snippet": "        if (isValid == true) {",
                "after_source": "public class Service {\n    public void run(boolean isValid) {\n        if (isValid == true) {\n            doStuff();\n        }\n    }\n}"
            },
            {
                "candidate_id": "cand-security",
                "decision": "ACCEPT",
                "source_reviewer": "security_validation",
                "file": "src/main/java/com/example/Auth.java",
                "line": 5,
                "problem": "Hardcoded secret password literal.",
                "code_snippet": "String pass = 'admin123';"
            },
            {
                "candidate_id": "cand-absence",
                "decision": "ACCEPT",
                "source_reviewer": "correctness_logic",
                "file": "src/main/java/com/example/Stream.java",
                "line": 12,
                "problem": "Unclosed resource without try-with-resources.",
                "code_snippet": "FileInputStream in = new FileInputStream(f);"
            }
        ]

        suggestions = generate_fix_suggestions(
            verified_findings=findings,
            backend="mock"
        )

        self.assertEqual(len(suggestions), 3)

        # 1. Maintainability -> Generated
        s1 = next(s for s in suggestions if s["finding_id"] == "cand-maintainability")
        self.assertEqual(s1["fix_status"], "generated")
        self.assertIn("--- a/src/main/java/com/example/Service.java", s1["diff"])
        self.assertTrue(s1["validation"]["unified_diff_valid"])
        self.assertTrue(s1["validation"]["path_match"])
        self.assertTrue(s1["validation"]["size_within_limit"])

        # 2. Security -> Skipped
        s2 = next(s for s in suggestions if s["finding_id"] == "cand-security")
        self.assertEqual(s2["fix_status"], "skipped")
        self.assertEqual(s2["skip_reason"], "security_findings_not_auto_fixed")

        # 3. Absence -> Skipped
        s3 = next(s for s in suggestions if s["finding_id"] == "cand-absence")
        self.assertEqual(s3["fix_status"], "skipped")
        self.assertEqual(s3["skip_reason"], "absence_type_not_auto_fixed")


class TestAPIServerFixAgent(unittest.TestCase):
    """Verifies FastAPI /review endpoint handles suggest_fixes flag cleanly."""

    def test_api_review_suggest_fixes_flag(self):
        from fastapi.testclient import TestClient
        from api_server import app

        client = TestClient(app)
        # Test request against current repo on main branch in mock mode
        payload = {
            "repo": ".",
            "branch": "main",
            "base": "main",
            "dry_run": True,
            "suggest_fixes": True
        }
        resp = client.post("/review", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("fix_suggestions", data)
        self.assertIsInstance(data["fix_suggestions"], list)


if __name__ == "__main__":
    unittest.main()
