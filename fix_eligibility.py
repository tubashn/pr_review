"""
Deterministic Eligibility Gate for Fix Agent V1
Ensures patch generation is attempted ONLY for safe, localized, concrete findings:
- Verifier must have ACCEPTed the candidate
- Role must be correctness_logic or maintainability
- Single-file localization
- Concrete/presence-type problem (rejects absence/missing checks)
- Source file is valid supported Java file (rejects generated/vendor/fixture files)
- Context is sufficient for localized fix
- Security findings are strictly NOT auto-fixed
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from verifier_prompt_builder import (
    classify_grounding_strategy,
    STRATEGY_ABSENCE_REFERENCE,
    STRATEGY_ABSENCE_RESOURCE_CLEANUP
)

# Roles eligible for automated patch generation in V1
ELIGIBLE_ROLES = {"correctness_logic", "correctness", "maintainability"}

# Ineligible file path patterns (generated, vendor, test fixtures, configs)
INELIGIBLE_PATH_PATTERNS = [
    r"(^|/|\\)target(/|\\)",
    r"(^|/|\\)build(/|\\)",
    r"(^|/|\\)out(/|\\)",
    r"(^|/|\\)generated(/|\\)",
    r"(^|/|\\)node_modules(/|\\)",
    r"(^|/|\\)vendor(/|\\)",
    r"(^|/|\\)fixtures?(/|\\)",
    r"\.min\.",
    r"\.(xml|json|ya?ml|properties|md|txt|sh|bat|cmd|gradle|dockerfile)$",
]

# Absence indicators in problem description
ABSENCE_KEYWORDS = [
    "missing",
    "absence",
    "unclosed",
    "not closed",
    "not handled",
    "unhandled exception",
    "missing null check",
    "lacks error handling",
    "missing validation",
    "missing check",
    "no timeout",
    "missing synchronization",
]

# Security indicators that must not be auto-patched (using word boundaries for safety)
SECURITY_KEYWORD_PATTERNS = [
    r"\bsecurity\b",
    r"\bvulnerabilit(?:y|ies)\b",
    r"\bcve-\d+",
    r"\bsecret\b",
    r"\bpasswords?\b",
    r"\btokens?\b",
    r"\bapikeys?\b",
    r"\bapi_key\b",
    r"\bprivate_key\b",
    r"\binjections?\b",
    r"\bxss\b",
    r"\bcsrf\b",
    r"\bdeserialization\b",
    r"\bprivilege escalation\b",
    r"\brce\b",
    r"\bssrf\b",
    r"\bauth(?:entication|orization)?\b",
    r"\bcredentials?\b",
    r"\bhardcoded\b",
]


def is_security_finding(finding: Dict[str, Any]) -> bool:
    """Checks whether the finding is a security issue."""
    role = str(finding.get("source_reviewer", "")).strip().lower()
    if "security" in role:
        return True

    problem = str(finding.get("problem", "")).lower()
    category = str(finding.get("category", "")).lower()
    rule = str(finding.get("rule", "")).lower()

    combined = f"{problem} {category} {rule}"
    for pat in SECURITY_KEYWORD_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            return True
    return False


def is_absence_type_finding(finding: Dict[str, Any]) -> bool:
    """Checks whether the finding describes an absence/missing code issue."""
    problem = str(finding.get("problem", "")).strip()
    
    # 1. Verifier Grounding Strategy check
    strategy = classify_grounding_strategy(problem)
    if strategy in (STRATEGY_ABSENCE_REFERENCE, STRATEGY_ABSENCE_RESOURCE_CLEANUP):
        return True

    # 2. Problem keyword heuristics
    prob_lower = problem.lower()
    for kw in ABSENCE_KEYWORDS:
        if kw in prob_lower:
            return True

    return False


def is_valid_source_file(file_path: str) -> bool:
    """Verifies that the target file is a supported source file and not generated/vendor/fixture."""
    if not file_path or not isinstance(file_path, str):
        return False

    norm_path = file_path.replace("\\", "/")
    
    # Must be a Java file in V1
    if not norm_path.lower().endswith(".java"):
        return False

    # Check against ineligible path patterns
    for pattern in INELIGIBLE_PATH_PATTERNS:
        if re.search(pattern, norm_path, re.IGNORECASE):
            return False

    return True


def check_fix_eligibility(
    finding: Dict[str, Any],
    file_content: Optional[str] = None,
    diff_hunks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Evaluates finding eligibility deterministically against V1 safety rules.
    Returns:
        {
            "eligible": bool,
            "reason": str
        }
    """
    # 1. Verifier Decision Gate
    decision = str(finding.get("decision", "")).strip().upper()
    if decision and decision != "ACCEPT":
        return {
            "eligible": False,
            "reason": "unverified_or_rejected_finding"
        }

    # 2. File Path & Type Gate (must be valid Java source)
    file_path = finding.get("file") or finding.get("file_path") or ""
    if not is_valid_source_file(file_path):
        return {
            "eligible": False,
            "reason": "unsupported_file_type"
        }

    # 3. Security Gate
    if is_security_finding(finding):
        return {
            "eligible": False,
            "reason": "security_findings_not_auto_fixed"
        }

    # 4. Role/Category Gate
    role = str(finding.get("source_reviewer", "")).strip().lower()
    if role not in ELIGIBLE_ROLES:
        return {
            "eligible": False,
            "reason": f"role_{role}_not_supported_for_auto_fix"
        }

    # 5. Absence-Type Gate
    if is_absence_type_finding(finding):
        return {
            "eligible": False,
            "reason": "absence_type_not_auto_fixed"
        }

    # 6. Multi-File / Cross-File Gate
    problem_text = str(finding.get("problem", "")).lower()
    if "across files" in problem_text or "multiple files" in problem_text or "cross-file" in problem_text:
        return {
            "eligible": False,
            "reason": "multi_file_not_supported"
        }

    # 7. Context Sufficiency Gate
    after_source = finding.get("after_source") or file_content or ""
    code_snippet = finding.get("code_snippet") or ""
    if not after_source and not code_snippet and not diff_hunks:
        return {
            "eligible": False,
            "reason": "insufficient_context"
        }

    # 8. Expected Change Size Gate (V1 max 20 lines)
    if "refactor entire class" in problem_text or "rewrite module" in problem_text:
        return {
            "eligible": False,
            "reason": "expected_patch_too_large"
        }

    return {
        "eligible": True,
        "reason": "eligible_for_fix"
    }
