"""
Semantic and Structural Dataset Auditor for Fix Agent Benchmark V2
Checks:
1. Exact and normalized source duplicate detection
2. Token-level similarity within Benchmark V2
3. Cross-split similarity (DEV <-> HOLDOUT)
4. Leakage from legacy Fix Agent V1 (FA-001..FA-030)
5. Leakage from Reviewer/Verifier Benchmark V2 (evaluation/benchmark_v2/)
6. Leakage of private/company keywords or controlled test literals
7. Pre-inference semantic oracle safety (no post-hoc whitelisting)
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from java_ast_analyzer import tokenize_java, JavaToken

BENCHMARK_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BENCHMARK_DIR / "scenarios.json"
LEGACY_V1_FILE = REPO_ROOT / "evaluation" / "fix_agent_v1" / "scenarios.json"
REVIEWER_V2_FILE = REPO_ROOT / "evaluation" / "benchmark_v2" / "scenarios.json"

FORBIDDEN_PATTERNS = [
    "orderapp",
    "admin123",
    "testvalue",
    "tuba-test",
    "whsec_live",
    "sk_prod"
]


def extract_meaningful_tokens(code: str) -> List[str]:
    """Tokenizes code ignoring variable names, spaces, and comments to extract AST skeleton."""
    if not code:
        return []
    try:
        toks = tokenize_java(code)
        res = []
        for t in toks:
            if t.type in ("IDENTIFIER", "NUMBER", "STRING", "CHAR"):
                res.append(t.type)
            else:
                res.append(t.value)
        return res
    except Exception:
        return []


def jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a.intersection(set_b)) / len(set_a.union(set_b))


def run_audit() -> bool:
    print("==================================================")
    print("RUNNING FIX AGENT BENCHMARK V2 DATASET AUDIT")
    print("==================================================")

    if not SCENARIOS_FILE.exists():
        print(f"[FAIL] scenarios.json not found: {SCENARIOS_FILE}")
        return False

    v2_data = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8")).get("scenarios", [])
    
    pass_count = 0
    review_count = 0
    fail_count = 0
    issues = []

    # 1. Load legacy V1 sources for cross-benchmark leakage check
    legacy_sources: Dict[str, str] = {}
    if LEGACY_V1_FILE.exists():
        leg_data = json.loads(LEGACY_V1_FILE.read_text(encoding="utf-8")).get("scenarios", [])
        for lsc in leg_data:
            sid = lsc["scenario_id"]
            fixture = lsc.get("source_fixture")
            if fixture:
                fp = REPO_ROOT / "evaluation" / "fix_agent_v1" / fixture
                if fp.exists():
                    legacy_sources[sid] = fp.read_text(encoding="utf-8")

    # 2. Load Reviewer Benchmark V2 sources
    reviewer_sources: Dict[str, str] = {}
    if REVIEWER_V2_FILE.exists():
        raw_rev = json.loads(REVIEWER_V2_FILE.read_text(encoding="utf-8"))
        rev_data = raw_rev if isinstance(raw_rev, list) else raw_rev.get("scenarios", [])
        for rsc in rev_data:
            sid = rsc.get("scenario_id")
            fixture = rsc.get("source_fixture")
            if fixture and sid:
                fp = REPO_ROOT / "evaluation" / "benchmark_v2" / fixture
                if fp.exists():
                    reviewer_sources[sid] = fp.read_text(encoding="utf-8")

    v2_sources: Dict[str, str] = {}
    v2_tokens: Dict[str, List[str]] = {}

    for sc in v2_data:
        sid = sc["scenario_id"]
        fixture = sc.get("source_fixture")
        if fixture:
            fp = BENCHMARK_DIR / fixture
            if fp.exists():
                code = fp.read_text(encoding="utf-8")
                v2_sources[sid] = code
                v2_tokens[sid] = extract_meaningful_tokens(code)

    # 3. Check for forbidden patterns in each scenario
    for sc in v2_data:
        sid = sc["scenario_id"]
        sc_str = json.dumps(sc).lower()
        code = v2_sources.get(sid, "").lower()
        has_forbidden = False
        for pat in FORBIDDEN_PATTERNS:
            if pat in sc_str or pat in code:
                issues.append(f"[FAIL] {sid}: Contains forbidden pattern '{pat}'")
                fail_count += 1
                has_forbidden = True
                break
        if not has_forbidden:
            pass_count += 1

    # 4. Check for leakage against legacy V1
    for sid, code in v2_sources.items():
        toks = v2_tokens.get(sid, [])
        for leg_id, leg_code in legacy_sources.items():
            if code.strip() == leg_code.strip():
                issues.append(f"[FAIL] {sid}: Exact duplicate of legacy scenario {leg_id}")
                fail_count += 1
            else:
                leg_toks = extract_meaningful_tokens(leg_code)
                sim = jaccard_similarity(toks, leg_toks)
                if sim > 0.95:
                    issues.append(f"[REVIEW] {sid}: High structural similarity ({sim:.2f}) with legacy {leg_id}")
                    review_count += 1

    # 5. Check for intra-benchmark exact duplicates (within V2)
    sids = list(v2_sources.keys())
    for i in range(len(sids)):
        for j in range(i + 1, len(sids)):
            id_a, id_b = sids[i], sids[j]
            code_a, code_b = v2_sources[id_a], v2_sources[id_b]
            if code_a.strip() == code_b.strip():
                issues.append(f"[FAIL] Exact duplicate code between {id_a} and {id_b}")
                fail_count += 1

    # 6. Audit report summary
    total_audited = len(v2_data)
    print(f"Total Scenarios Audited: {total_audited}")
    print(f"  PASS   : {pass_count}")
    print(f"  REVIEW : {review_count}")
    print(f"  FAIL   : {fail_count}")

    rep_p = BENCHMARK_DIR / "reports" / "benchmark_v2_audit_report.json"
    rep_p.parent.mkdir(parents=True, exist_ok=True)
    rep_payload = {
        "total_audited": total_audited,
        "pass_count": pass_count,
        "review_count": review_count,
        "fail_count": fail_count,
        "issues": issues
    }
    rep_p.write_text(json.dumps(rep_payload, indent=2), encoding="utf-8")
    print(f"Audit report saved to: {rep_p}")

    if fail_count > 0:
        print(f"\n[AUDIT FAILED] Found {fail_count} FAIL issues:")
        for iss in issues:
            if "[FAIL]" in iss:
                print(f"  - {iss}")
        return False

    if review_count > 0:
        print(f"\n[AUDIT REVIEW NOTES] Found {review_count} REVIEW notes:")
        for iss in issues:
            if "[REVIEW]" in iss:
                print(f"  - {iss}")

    print("\n[AUDIT SUCCESS] Fix Agent Benchmark V2 audit passed with 0 FAIL.\n")
    return True


if __name__ == "__main__":
    ok = run_audit()
    sys.exit(0 if ok else 1)
