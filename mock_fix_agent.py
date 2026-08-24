"""
Deterministic Mock Fix Agent for Local Development and CI Testing.
Generates predictable, valid unified diff patches for verified, eligible findings
without downloading weights, without transformers, and without GPU.
"""

import re
from typing import Any, Dict, Optional

from patch_validator import validate_patch


def run_deterministic_mock_fix(
    finding: Dict[str, Any],
    file_path: str,
    source_content: str = "",
    diff_hunk: str = ""
) -> Dict[str, Any]:
    """
    Generates a deterministic mock fix for an eligible finding and validates it.
    """
    fid = finding.get("candidate_id") or finding.get("finding_id", "mock-fix")
    problem = str(finding.get("problem", "")).strip()
    code_snippet = str(finding.get("code_snippet", "")).strip()
    line_no = finding.get("line", 1) or 1

    prob_lower = problem.lower()

    # 1. Redundant boolean comparison fix (e.g. `flag == true` -> `flag`, `flag == false` -> `!flag`)
    if "redundant boolean" in prob_lower or "== true" in code_snippet or "== false" in code_snippet:
        target_code = code_snippet or "if (isValid == true) {"
        fixed_code = re.sub(r"\s*==\s*true\b", "", target_code)
        fixed_code = re.sub(r"==\s*false\b", "!=", fixed_code) if "!=" in fixed_code else re.sub(r"([A-Za-z0-9_$.]+)\s*==\s*false\b", r"!\1", fixed_code)

        diff = f"""--- a/{file_path}
+++ b/{file_path}
@@ -{line_no},1 +{line_no},1 @@
-{target_code}
+{fixed_code}"""
        explanation = "Simplified redundant boolean comparison directly."

    # 2. Unused local variable fix (remove declaration)
    elif "unused" in prob_lower and "variable" in prob_lower:
        target_code = code_snippet or "int unusedVar = 0;"
        diff = f"""--- a/{file_path}
+++ b/{file_path}
@@ -{line_no},1 +{line_no},0 @@
-{target_code}"""
        explanation = f"Removed unused local variable."

    # 3. General deterministic replacement
    else:
        target_code = code_snippet or "// problematic code"
        diff = f"""--- a/{file_path}
+++ b/{file_path}
@@ -{line_no},1 +{line_no},1 @@
-{target_code}
+// fixed: {problem[:40]}"""
        explanation = f"Applied minimal corrective patch for {problem[:50]}."

    # Validate the generated patch
    val_res = validate_patch(diff, file_path, source_content if source_content else None)

    if val_res["valid"]:
        return {
            "finding_id": fid,
            "file_path": file_path,
            "fix_status": "generated",
            "diff": val_res["clean_diff"],
            "explanation": explanation,
            "validation": val_res["validation"],
            "skip_reason": None,
            "rejection_reason": None
        }
    else:
        return {
            "finding_id": fid,
            "file_path": file_path,
            "fix_status": "rejected",
            "diff": val_res["clean_diff"],
            "explanation": explanation,
            "validation": val_res["validation"],
            "skip_reason": None,
            "rejection_reason": val_res["rejection_reason"]
        }
