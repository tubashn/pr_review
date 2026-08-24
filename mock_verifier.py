"""
Deterministic Mock Semantic Verifier for Local Development and CI Testing.
Implements identical contract and output schema as production LLM verifier:
- problem_present (bool)
- role_match (bool)
- reason (str)
- evidence (str)
- parse_error (bool)
Without downloading models, without importing transformers/bitsandbytes, and without CUDA GPU.
"""

import os
from typing import Any, Dict, Optional


def run_deterministic_mock_verification(
    candidate: Dict[str, Any],
    formatted_diff: str = "",
    mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates a candidate finding deterministically without calling any LLM.
    Supports mode overrides via PR_REVIEW_MOCK_MODE environment variable:
    - 'deterministic' (default): Evaluates problem/role heuristics deterministically.
    - 'accept_all': Forces problem_present=True, role_match=True.
    - 'reject_all': Forces problem_present=False, role_match=True.
    """
    cid = candidate.get("candidate_id", "mock-cand")
    role = str(candidate.get("source_reviewer", "")).strip().lower()
    problem = str(candidate.get("problem", "")).strip()
    evidence_snippet = str(candidate.get("code_snippet", "")).strip()

    active_mode = mode or os.getenv("PR_REVIEW_MOCK_MODE", "deterministic").lower()

    if active_mode == "accept_all":
        return {
            "candidate_id": cid,
            "problem_present": True,
            "role_match": True,
            "reason": "Mock verifier (mode=accept_all): Finding verified successfully.",
            "evidence": evidence_snippet,
            "parse_error": False
        }

    if active_mode == "reject_all":
        return {
            "candidate_id": cid,
            "problem_present": False,
            "role_match": True,
            "reason": "Mock verifier (mode=reject_all): Finding refuted by mock verifier.",
            "evidence": "",
            "parse_error": False
        }

    # Deterministic heuristic verification based on canonical issue heuristics
    prob_lower = problem.lower()

    # 1. Role match checks (Role Leakage detection)
    is_security_issue = any(k in prob_lower for k in ("secret", "password", "apikey", "credential", "token", "injection", "vulnerability"))
    is_maintainability_issue = any(k in prob_lower for k in ("unused", "redundant boolean", "dead code", "duplicate code", "complexity"))

    role_match = True
    role_reason = "Role aligns with reported issue domain."

    if is_security_issue and role != "security_validation":
        role_match = False
        role_reason = f"Security issue reported under incompatible reviewer role '{role}'."
    elif is_maintainability_issue and role != "maintainability":
        role_match = False
        role_reason = f"Maintainability issue reported under incompatible reviewer role '{role}'."

    # 2. Problem presence check
    # Check if problem is an obvious mock negative marker
    if "[reject]" in prob_lower or "guarded" in prob_lower and "null" in prob_lower and "potential" in prob_lower:
        problem_present = False
        prob_reason = "Code includes safe defensive guards preventing the reported issue."
    else:
        problem_present = True
        prob_reason = f"Confirmed issue: {problem}"

    final_reason = f"Mock verifier: {prob_reason} ({role_reason})" if role_match else f"Mock verifier role mismatch: {role_reason}"

    return {
        "candidate_id": cid,
        "problem_present": problem_present,
        "role_match": role_match,
        "reason": final_reason,
        "evidence": evidence_snippet,
        "parse_error": False
    }
