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

    def test_eligible_unused_local_variable_not_false_skipped(self):
        """FA-003 regression: unused localized variable must be eligible."""
        finding = {
            "candidate_id": "FA-003",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/stats/LatencyTracker.java",
            "problem": "Unused local variable `debugCount` should be removed.",
            "code_snippet": "int debugCount = 0;",
            "after_source": "int debugCount = 0;\nrecordLatency(ms);"
        }
        res = check_fix_eligibility(finding)
        self.assertTrue(res["eligible"])
        self.assertEqual(res["reason"], "eligible_for_fix")

    def test_eligible_unused_allocation_not_false_skipped(self):
        """FA-004 regression: unused StringBuilder allocation must be eligible."""
        finding = {
            "candidate_id": "FA-004",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/text/MessageFormatter.java",
            "problem": "Unused StringBuilder allocation `builder` has no effect.",
            "code_snippet": "StringBuilder builder = new StringBuilder();",
            "after_source": "StringBuilder builder = new StringBuilder();\nreturn prefix + body;"
        }
        res = check_fix_eligibility(finding)
        self.assertTrue(res["eligible"])
        self.assertEqual(res["reason"], "eligible_for_fix")

    def test_eligible_dead_local_assignment_not_false_skipped(self):
        """FA-007 regression: unused local error state must be eligible."""
        finding = {
            "candidate_id": "FA-007",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/service/ExecutionService.java",
            "problem": "Unused local variable `lastError` assigned but never read.",
            "code_snippet": "String lastError = null;",
            "after_source": "String lastError = null;\nreturn executeTask();"
        }
        res = check_fix_eligibility(finding)
        self.assertTrue(res["eligible"])
        self.assertEqual(res["reason"], "eligible_for_fix")


class TestStructuredEditValidator(unittest.TestCase):
    """Unit tests for Fix Agent V2 structured edit validation and grounding."""

    def setUp(self):
        self.source = """package com.example.calc;

public class MathUtil {
    public int compute(int a, int b) {
        int debugCount = 0;
        if (a < 10) {
            return 2 * (a - b);
        }
        return a + b;
    }
}
"""
        self.finding = {
            "candidate_id": "f-1",
            "file": "src/main/java/com/example/calc/MathUtil.java",
            "line": 7,
            "problem": "Wrong subtraction in formula: should be addition `a + b`.",
            "evidence": "return 2 * (a - b);"
        }

    def test_exact_grounding_success(self):
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "return 2 * (a - b);",
            "new_text": "return 2 * (a + b);",
            "explanation": "Correct formula to addition."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "generated")
        self.assertEqual(res["match_mode"], "exact")
        self.assertTrue(res["validation"]["unified_diff_valid"])
        self.assertTrue(res["validation"]["structural_sanity"])
        self.assertIn("+            return 2 * (a + b);", res["diff"])
        self.assertIn("-            return 2 * (a - b);", res["diff"])

    def test_whitespace_normalization_fallback(self):
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "return   2 * (a - b);",  # extra interior spaces
            "new_text": "return 2 * (a + b);",
            "explanation": "Whitespace fallback test."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "generated")
        self.assertEqual(res["match_mode"], "normalized_whitespace")
        self.assertTrue(res["validation"]["apply_check"])

    def test_reject_old_text_not_found(self):
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "int nonExistent = 999;",
            "new_text": "int fixed = 1;",
            "explanation": "Missing snippet."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "old_text_not_found")

    def test_reject_ambiguous_old_text(self):
        src_with_duplicates = "public void foo() { int x = 1; int x = 1; }"
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "int x = 1;",
            "new_text": "int x = 2;",
            "explanation": "Ambiguous."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, src_with_duplicates)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "ambiguous_old_text")

    def test_reject_delimiter_only_insufficient_target_context(self):
        for delim in ["}", "{", ";", ")", "true", "false", "   \n } \n "]:
            edit = {
                "finding_id": "f-1",
                "file_path": "src/main/java/com/example/calc/MathUtil.java",
                "old_text": delim,
                "new_text": "int y = 5;",
                "explanation": "Bad target."
            }
            from structured_edit_validator import validate_and_apply_structured_edit
            res = validate_and_apply_structured_edit(edit, self.finding, self.source)
            self.assertEqual(res["fix_status"], "rejected", f"Delimiter {delim} should be rejected")
            self.assertEqual(res["failure_type"], "insufficient_target_context")

    def test_reject_no_op_fix(self):
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "return 2 * (a - b);",
            "new_text": "return 2 * (a - b);",
            "explanation": "Identical."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "no_op_fix")

    def test_reject_target_location_mismatch(self):
        # Finding says line 100, but edit is on line 5
        finding_distant = dict(self.finding, line=100)
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "int debugCount = 0;",
            "new_text": "",
            "explanation": "Distant line test."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, finding_distant, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "target_location_mismatch")

    def test_reject_target_not_modified(self):
        # Defective evidence is return 2 * (a - b); but edit targets int debugCount = 0; with no common tokens
        finding_touch = dict(self.finding, evidence="return 2 * (a - b);")
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "int debugCount = 0;",
            "new_text": "",
            "explanation": "Wrong target line."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, finding_touch, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "target_not_modified")

    def test_reject_structural_invalid(self):
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "return 2 * (a - b);",
            "new_text": "return 2 * (a - b); } } {",
            "explanation": "Broken brackets."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "structural_invalid")

    def test_reject_patch_too_large(self):
        big_new_text = "\n".join([f"int var_{i} = {i};" for i in range(25)])
        edit = {
            "finding_id": "f-1",
            "file_path": "src/main/java/com/example/calc/MathUtil.java",
            "old_text": "return 2 * (a - b);",
            "new_text": big_new_text,
            "explanation": "Too big."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "patch_too_large")

    def test_reject_unsafe_path(self):
        edit = {
            "finding_id": "f-1",
            "file_path": "../etc/passwd",
            "old_text": "foo",
            "new_text": "bar",
            "explanation": "Path traversal."
        }
        from structured_edit_validator import validate_and_apply_structured_edit
        res = validate_and_apply_structured_edit(edit, self.finding, self.source)
        self.assertEqual(res["fix_status"], "rejected")
        self.assertEqual(res["failure_type"], "unsafe_path")


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


class TestHardenPreModelSafetyGates(unittest.TestCase):
    """Verifies that ineligible findings never invoke model generation (call count = 0)."""

    def test_security_findings_skip_with_zero_model_calls(self):
        from unittest.mock import MagicMock
        from fix_agent import run_fix_agent_for_finding

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()

        finding = {
            "candidate_id": "sec-1",
            "decision": "ACCEPT",
            "source_reviewer": "security_validation",
            "file": "src/main/java/com/example/auth/AuthService.java",
            "line": 10,
            "problem": "SQL injection vulnerability in query builder.",
            "code_snippet": "String q = 'SELECT * FROM users WHERE id=' + id;",
            "after_source": "public class AuthService { public void query(String id) {} }"
        }

        res = run_fix_agent_for_finding(
            finding=finding,
            backend="transformers",
            loaded_model=mock_model,
            tokenizer=mock_tokenizer
        )

        self.assertEqual(res["fix_status"], "skipped")
        self.assertEqual(res["skip_reason"], "security_findings_not_auto_fixed")
        mock_model.generate.assert_not_called()
        mock_tokenizer.encode.assert_not_called()

    def test_absence_findings_skip_with_zero_model_calls(self):
        from unittest.mock import MagicMock
        from fix_agent import run_fix_agent_for_finding

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()

        finding = {
            "candidate_id": "abs-1",
            "decision": "ACCEPT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/io/FileHandler.java",
            "line": 15,
            "problem": "Unclosed InputStream resource leak without try-with-resources.",
            "code_snippet": "InputStream is = new FileInputStream(file);",
            "after_source": "public class FileHandler {}"
        }

        res = run_fix_agent_for_finding(
            finding=finding,
            backend="transformers",
            loaded_model=mock_model,
            tokenizer=mock_tokenizer
        )

        self.assertEqual(res["fix_status"], "skipped")
        self.assertEqual(res["skip_reason"], "absence_type_not_auto_fixed")
        mock_model.generate.assert_not_called()

    def test_structured_multi_file_metadata_skips_with_zero_model_calls(self):
        from unittest.mock import MagicMock
        from fix_agent import run_fix_agent_for_finding

        for meta_key, meta_val in [
            ("finding_type", "multi_file"),
            ("context_scope", "multi_file_rule"),
            ("scope", "cross_file"),
            ("file_count", 2),
            ("affected_files", ["A.java", "B.java"]),
            ("is_multi_file", True)
        ]:
            mock_model = MagicMock()
            finding = {
                "candidate_id": "multi-1",
                "decision": "ACCEPT",
                "source_reviewer": "correctness_logic",
                "file": "src/main/java/com/example/api/Service.java",
                "line": 20,
                "problem": "Interface contract synchronization required.",
                "after_source": "public class Service {}",
                meta_key: meta_val
            }
            res = run_fix_agent_for_finding(
                finding=finding,
                backend="transformers",
                loaded_model=mock_model,
                tokenizer=MagicMock()
            )
            self.assertEqual(res["fix_status"], "skipped", f"Failed for {meta_key}={meta_val}")
            self.assertEqual(res["skip_reason"], "multi_file_not_supported")
            mock_model.generate.assert_not_called()

    def test_cross_file_text_fallback_skips_with_zero_model_calls(self):
        from unittest.mock import MagicMock
        from fix_agent import run_fix_agent_for_finding

        mock_model = MagicMock()
        finding = {
            "candidate_id": "cf-1",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/db/Entity.java",
            "line": 8,
            "problem": "Renaming column requires synchronized update of V2__rename_column.sql migration script across files.",
            "after_source": "public class Entity {}"
        }
        res = run_fix_agent_for_finding(
            finding=finding,
            backend="transformers",
            loaded_model=mock_model,
            tokenizer=MagicMock()
        )
        self.assertEqual(res["fix_status"], "skipped")
        self.assertEqual(res["skip_reason"], "multi_file_not_supported")
        mock_model.generate.assert_not_called()

    def test_generated_source_protobuf_and_antlr_skip_with_zero_model_calls(self):
        from unittest.mock import MagicMock
        from fix_agent import run_fix_agent_for_finding

        # 1. Path-based proto
        mock_model = MagicMock()
        finding_proto_path = {
            "candidate_id": "gen-proto",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/proto/GeneratedUserProto.java",
            "line": 30,
            "problem": "Unused field in proto stub.",
            "after_source": "package com.example.proto;\npublic class GeneratedUserProto {}"
        }
        res1 = run_fix_agent_for_finding(
            finding=finding_proto_path,
            backend="transformers",
            loaded_model=mock_model,
            tokenizer=MagicMock()
        )
        self.assertEqual(res1["fix_status"], "skipped")
        self.assertEqual(res1["skip_reason"], "unsupported_file_type")
        mock_model.generate.assert_not_called()

        # 2. Header-based generated source
        mock_model2 = MagicMock()
        finding_gen_header = {
            "candidate_id": "gen-hdr",
            "decision": "ACCEPT",
            "source_reviewer": "maintainability",
            "file": "src/main/java/com/example/parser/CustomLexer.java",
            "line": 12,
            "problem": "Dead variable in lexer.",
            "after_source": "// Generated from Custom.g4 by ANTLR 4.9.2\npackage com.example.parser;\npublic class CustomLexer {}"
        }
        res2 = run_fix_agent_for_finding(
            finding=finding_gen_header,
            backend="transformers",
            loaded_model=mock_model2,
            tokenizer=MagicMock()
        )
        self.assertEqual(res2["fix_status"], "skipped")
        self.assertEqual(res2["skip_reason"], "unsupported_file_type")
        mock_model2.generate.assert_not_called()

    def test_unsupported_non_java_files_skip_with_zero_model_calls(self):
        from unittest.mock import MagicMock
        from fix_agent import run_fix_agent_for_finding

        for ext in ["docker-compose.yml", "pom.xml", "build.gradle", "schema.sql", "application.properties"]:
            mock_model = MagicMock()
            finding = {
                "candidate_id": f"non-java-{ext}",
                "decision": "ACCEPT",
                "source_reviewer": "maintainability",
                "file": ext,
                "line": 1,
                "problem": "Configuration mismatch.",
                "after_source": "dummy content"
            }
            res = run_fix_agent_for_finding(
                finding=finding,
                backend="transformers",
                loaded_model=mock_model,
                tokenizer=MagicMock()
            )
            self.assertEqual(res["fix_status"], "skipped")
            self.assertEqual(res["skip_reason"], "unsupported_file_type")
            mock_model.generate.assert_not_called()

    def test_normal_java_source_not_falsely_skipped(self):
        from fix_eligibility import check_fix_eligibility

        # 1. Normal protocol handler class (package or class contains 'protocol', but is normal user code)
        finding_normal = {
            "decision": "ACCEPT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/protocol/NetworkProtocolHandler.java",
            "line": 15,
            "problem": "Inverted boolean comparison in packet validator.",
            "after_source": "package com.example.protocol;\npublic class NetworkProtocolHandler {}"
        }
        res1 = check_fix_eligibility(finding_normal, file_content=finding_normal["after_source"])
        self.assertTrue(res1["eligible"])
        self.assertEqual(res1["reason"], "eligible_for_fix")

        # 2. Operator precedence finding with phrasing 'missing parentheses'
        finding_precedence = {
            "decision": "ACCEPT",
            "source_reviewer": "correctness_logic",
            "file": "src/main/java/com/example/math/LerpCalculator.java",
            "line": 5,
            "problem": "Missing parentheses in lerp formula causing wrong arithmetic precedence.",
            "after_source": "package com.example.math;\npublic class LerpCalculator {}"
        }
        res2 = check_fix_eligibility(finding_precedence, file_content=finding_precedence["after_source"])
        self.assertTrue(res2["eligible"])
        self.assertEqual(res2["reason"], "eligible_for_fix")


if __name__ == "__main__":
    unittest.main()

