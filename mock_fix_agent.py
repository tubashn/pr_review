"""
Deterministic Mock Fix Agent V2 for Local Development and CI Testing.
Generates predictable structured edits (old_text -> new_text) for verified findings
and validates them using the deterministic structured edit pipeline.
"""

import re
from typing import Any, Dict, Optional

from structured_edit_validator import validate_and_apply_structured_edit


def run_deterministic_mock_fix(
    finding: Dict[str, Any],
    file_path: str,
    source_content: str = "",
    diff_hunk: str = "",
    pr_changed_files: Optional[list] = None
) -> Dict[str, Any]:
    """
    Generates a deterministic mock structured edit for an eligible finding and validates it.
    """
    fid = finding.get("candidate_id") or finding.get("finding_id", "mock-fix")
    problem = str(finding.get("problem", "")).strip()
    code_snippet = str(finding.get("code_snippet") or finding.get("evidence") or "").strip()
    prob_lower = problem.lower()

    # 1. Determine target old_text from source / snippet
    old_text = ""
    new_text = ""
    explanation = ""

    if "redundant boolean" in prob_lower or "== true" in code_snippet or "== false" in code_snippet:
        # Find exact line in source_content matching snippet
        if code_snippet and code_snippet in source_content:
            old_text = code_snippet
        elif "== true" in source_content:
            for l in source_content.splitlines():
                if "== true" in l:
                    old_text = l.strip()
                    break
        elif "== false" in source_content:
            for l in source_content.splitlines():
                if "== false" in l:
                    old_text = l.strip()
                    break

        if not old_text:
            old_text = code_snippet or "isAuthorized == true"

        fixed = re.sub(r"\s*==\s*true\b", "", old_text)
        fixed = re.sub(r"==\s*false\b", "!=", fixed) if "!=" in fixed else re.sub(r"([A-Za-z0-9_$.]+)\s*==\s*false\b", r"!\1", fixed)
        new_text = fixed
        explanation = "Simplified redundant boolean comparison directly."

    elif "unused" in prob_lower and ("variable" in prob_lower or "allocation" in prob_lower or "builder" in prob_lower or "lasterror" in prob_lower):
        if code_snippet and code_snippet in source_content:
            old_text = code_snippet
        else:
            old_text = code_snippet or "int debugCount = 0;"
        new_text = ""
        explanation = "Removed unused local variable declaration."

    elif "redundant double negation" in prob_lower or "!(!enabled)" in code_snippet or "!(!enabled)" in source_content:
        old_text = code_snippet or "return !(!enabled);"
        new_text = re.sub(r"!\(?!\s*([A-Za-z0-9_$.]+)\)?", r"\1", old_text)
        explanation = "Simplified redundant double negation."

    elif "discount" in prob_lower or "< 10" in code_snippet:
        old_text = code_snippet or "if (itemCount < 10) {"
        new_text = old_text.replace("< 10", ">= 10")
        explanation = "Corrected discount qualification threshold operator."

    elif "off-by-one" in prob_lower and ("buffer" in prob_lower or "> buffer.length" in code_snippet):
        old_text = code_snippet or "if (index < 0 || index > buffer.length) {"
        new_text = old_text.replace("index > buffer.length", "index >= buffer.length")
        explanation = "Corrected off-by-one array index boundary check."

    elif "0.25" in code_snippet or ("tax" in prob_lower and "0.25" in source_content):
        old_text = code_snippet or "return baseAmount * 0.25;"
        new_text = old_text.replace("0.25", "0.20")
        explanation = "Corrected standard tax rate constant."

    elif "inverted" in prob_lower and "available" in prob_lower:
        old_text = code_snippet or "return availableCount < requestedCount;"
        new_text = old_text.replace("availableCount < requestedCount", "availableCount >= requestedCount")
        explanation = "Inverted availability condition."

    elif "perimeter" in prob_lower or "(width - height)" in code_snippet:
        old_text = code_snippet or "return 2 * (width - height);"
        new_text = old_text.replace("width - height", "width + height")
        explanation = "Corrected perimeter calculation formula."

    elif "failed" in code_snippet.lower() or "transactionstatus" in file_path.lower():
        old_text = code_snippet or 'return "FAILED".equalsIgnoreCase(status);'
        new_text = old_text.replace('"FAILED"', '"SUCCESS"')
        explanation = "Corrected positive status confirmation string."

    elif "integer division" in prob_lower or "(part / total)" in code_snippet:
        old_text = code_snippet or "return (part / total) * 100.0;"
        new_text = old_text.replace("(part / total)", "((double) part / total)")
        explanation = "Cast integer division operands to double."

    else:
        old_text = code_snippet or "// target construct"
        new_text = "// fixed: " + old_text
        explanation = f"Applied localized correction for {problem[:40]}."

    # Build raw structured edit
    structured_edit = {
        "finding_id": fid,
        "file_path": file_path,
        "fix_status": "generated",
        "old_text": old_text,
        "new_text": new_text,
        "explanation": explanation
    }

    # Pass through deterministic validation, grounding, and diff synthesis
    res = validate_and_apply_structured_edit(
        structured_edit=structured_edit,
        finding=finding,
        source_content=source_content,
        pr_changed_files=pr_changed_files
    )

    return res
