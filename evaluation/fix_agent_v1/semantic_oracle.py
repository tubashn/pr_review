"""
Semantic Oracle and Multi-Tier Correctness Evaluator for Fix Agent Evaluation Harness.
Distinguishes between:
1. Canonical Source Match (Exact / Whitespace Normalized Match with expected_after.java)
2. Java Token Equivalence (Java lexical stream equality, ignoring whitespace/blank lines but preserving literals)
3. Deterministic Semantic Oracle (Alternative valid semantic implementations)
4. Semantic Review Required vs Confirmed Wrong Fix
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add repo root to import java_ast_analyzer
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from java_ast_analyzer import tokenize_java, JavaToken


def normalize_source_code(code: str) -> str:
    """Normalizes CRLF to LF, strips trailing spaces per line, and strips overall whitespace."""
    if not code:
        return ""
    lines = [line.rstrip() for line in code.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def check_token_equivalence(code_a: str, code_b: str) -> bool:
    """
    Checks if two Java code strings produce the exact same sequence of Java tokens.
    Whitespace, indentation, blank lines, and comments are ignored by tokenizer,
    while string literals, numeric literals, identifiers, and operators are preserved verbatim.
    """
    if not code_a or not code_b:
        return False

    try:
        toks_a = [(t.type, t.value) for t in tokenize_java(code_a)]
        toks_b = [(t.type, t.value) for t in tokenize_java(code_b)]
        return toks_a == toks_b
    except Exception:
        return False


def evaluate_semantic_correctness(
    patched_code: str,
    expected_code: Optional[str],
    oracle_spec: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates semantic correctness across 3 tiers:
    Tier 1: Canonical source match
    Tier 2: Java token equivalence
    Tier 3: Deterministic semantic oracle (e.g. alternative token variants)
    """
    if not patched_code:
        return {
            "canonical_source_match": False,
            "token_equivalent": False,
            "semantic_oracle_pass": False,
            "semantic_match": False,
            "semantic_match_mode": None,
            "failure_subtype": "wrong_fix"
        }

    # Tier 1: Canonical Source Match
    if expected_code:
        norm_patched = normalize_source_code(patched_code)
        norm_expected = normalize_source_code(expected_code)
        if norm_patched == norm_expected:
            return {
                "canonical_source_match": True,
                "token_equivalent": True,
                "semantic_oracle_pass": True,
                "semantic_match": True,
                "semantic_match_mode": "canonical",
                "failure_subtype": "success_canonical"
            }

    # Tier 2: Java Token Equivalence
    if expected_code:
        if check_token_equivalence(patched_code, expected_code):
            return {
                "canonical_source_match": False,
                "token_equivalent": True,
                "semantic_oracle_pass": True,
                "semantic_match": True,
                "semantic_match_mode": "token_equivalent",
                "failure_subtype": "success_token_equivalent"
            }

    # Tier 3: Deterministic Semantic Oracle
    if oracle_spec and isinstance(oracle_spec, dict):
        oracle_type = oracle_spec.get("oracle_type")
        if oracle_type == "alternative_token_variants":
            variants = oracle_spec.get("variants", [])
            for var_code in variants:
                if check_token_equivalence(patched_code, var_code):
                    return {
                        "canonical_source_match": False,
                        "token_equivalent": False,
                        "semantic_oracle_pass": True,
                        "semantic_match": True,
                        "semantic_match_mode": "semantic_oracle",
                        "failure_subtype": "success_semantic_oracle"
                    }

    # Fallback Classification: If unconfirmed by oracle, differentiate between review-required and wrong
    # If no oracle exists for this scenario, flag as semantic_review_required
    failure_subtype = "semantic_review_required" if not oracle_spec else "wrong_fix"

    return {
        "canonical_source_match": False,
        "token_equivalent": False,
        "semantic_oracle_pass": False,
        "semantic_match": False,
        "semantic_match_mode": None,
        "failure_subtype": failure_subtype
    }
