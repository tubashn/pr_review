"""
Benchmark V2 Production Router Evaluation
Evaluates DEV split candidates against the existing production verification routing
hierarchy without altering any production rules.
Outputs routing distribution and generates semantic_verifier_requests_DEV.json.
"""

import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from verifier_prompt_builder import (
    classify_grounding_strategy,
    get_deterministic_canonical_issue_kind,
    is_deterministic_role_compatible,
    STRATEGY_DIRECT,
    STRATEGY_ABSENCE_REFERENCE,
    STRATEGY_ABSENCE_RESOURCE_CLEANUP
)
from java_ast_analyzer import verify_null_safety_self_refutation


def run_production_router_eval():
    print("==================================================")
    print("RUNNING BENCHMARK V2 DEV PRODUCTION ROUTER EVAL")
    print("==================================================")

    scenarios = json.load(open(BASE_DIR / "scenarios.json", encoding="utf-8"))
    candidates = json.load(open(BASE_DIR / "candidates.json", encoding="utf-8"))
    splits = json.load(open(BASE_DIR / "splits.json", encoding="utf-8"))
    fixtures_dir = BASE_DIR / "fixtures"

    dev_scenario_ids = set(splits.get("DEV", []))
    dev_scenarios = [s for s in scenarios if s["scenario_id"] in dev_scenario_ids]
    dev_candidates = [c for c in candidates if c["scenario_id"] in dev_scenario_ids]
    sc_map = {s["scenario_id"]: s for s in dev_scenarios}

    results = []
    semantic_requests = []

    # Routing Counters
    route_counts = {
        "DETERMINISTIC_DIRECT": 0,
        "DETERMINISTIC_ABSENCE": 0,
        "DETERMINISTIC_AST_SELF_REFUTED": 0,
        "SEMANTIC_VERIFIER": 0
    }

    category_routes = {}
    role_routes = {}
    difficulty_routes = {}

    det_true_findings = 0
    det_false_findings = 0
    sem_true_findings = 0
    sem_false_findings = 0

    for cand in dev_candidates:
        cid = cand["candidate_id"]
        sid = cand["scenario_id"]
        role = cand["source_reviewer"]
        problem = cand["problem"]
        expected = cand["expected"]
        diff_level = cand["difficulty"]
        sc = sc_map[sid]
        cat = sc["category"]

        fix_dir = fixtures_dir / sid
        diff_text = (fix_dir / "diff.patch").read_text(encoding="utf-8")
        after_text = list((fix_dir / "after").glob("*.java"))[0].read_text(encoding="utf-8")

        # 1. AST Null-Safety Check
        is_refuted, refuted_reason = verify_null_safety_self_refutation(problem, after_text)
        
        # 2. Absence Strategy Classification
        strategy = classify_grounding_strategy(problem)
        canonical_kind = get_deterministic_canonical_issue_kind(strategy)
        role_compatible = is_deterministic_role_compatible(canonical_kind, role)

        verification_route = "SEMANTIC_VERIFIER"
        det_passed = False

        if is_refuted:
            verification_route = "DETERMINISTIC_AST_SELF_REFUTED"
            det_passed = False # Vetoed by AST
        elif strategy in (STRATEGY_ABSENCE_REFERENCE, STRATEGY_ABSENCE_RESOURCE_CLEANUP):
            verification_route = "DETERMINISTIC_ABSENCE"
            det_passed = role_compatible
        else:
            # DIRECT vs SEMANTIC
            if cat == "DIRECT":
                verification_route = "DETERMINISTIC_DIRECT"
                det_passed = True
            else:
                verification_route = "SEMANTIC_VERIFIER"
                det_passed = False

        # Accumulate metrics
        route_counts[verification_route] = route_counts.get(verification_route, 0) + 1
        category_routes.setdefault(cat, {}).setdefault(verification_route, 0)
        category_routes[cat][verification_route] += 1
        role_routes.setdefault(role, {}).setdefault(verification_route, 0)
        role_routes[role][verification_route] += 1
        difficulty_routes.setdefault(diff_level, {}).setdefault(verification_route, 0)
        difficulty_routes[diff_level][verification_route] += 1

        is_det = (verification_route != "SEMANTIC_VERIFIER")
        if is_det:
            if expected == "ACCEPT":
                det_true_findings += 1
            else:
                det_false_findings += 1
        else:
            if expected == "ACCEPT":
                sem_true_findings += 1
            else:
                sem_false_findings += 1

        res_item = {
            "candidate_id": cid,
            "scenario_id": sid,
            "category": cat,
            "difficulty": diff_level,
            "source_reviewer": role,
            "expected": expected,
            "verification_route": verification_route,
            "issue_kind": sc["issue_kind"],
            "grounding_strategy": strategy,
            "canonical_issue_kind": canonical_kind,
            "deterministic_role_compatible": role_compatible,
            "is_self_refuted": is_refuted,
            "semantic_verifier_required": (verification_route == "SEMANTIC_VERIFIER")
        }
        results.append(res_item)

        # Prepare semantic request if route is SEMANTIC_VERIFIER
        if verification_route == "SEMANTIC_VERIFIER":
            req_item = {
                "candidate_id": cid,
                "scenario_id": sid,
                "file_path": sc["file_path"],
                "changed_method": sc["changed_method"],
                "changed_lines": sc["changed_lines"],
                "source_reviewer": role,
                "problem": problem,
                "failure_scenario": cand["failure_scenario"],
                "diff": diff_text,
                "after_source": after_text,
                "context_scope_required": sc["context_scope_required"]
                # Note: suggested_fix is strictly omitted per specification!
            }
            semantic_requests.append(req_item)

    # Save reports
    report_data = {
        "metadata": {
            "purpose": "BENCHMARK V2 DEV PRODUCTION ROUTER EVALUATION",
            "total_dev_scenarios": len(dev_scenarios),
            "total_dev_candidates": len(dev_candidates)
        },
        "metrics": {
            "total_dev_candidates": len(dev_candidates),
            "deterministic_route_total": len(dev_candidates) - len(semantic_requests),
            "semantic_route_total": len(semantic_requests),
            "deterministic_true_findings": det_true_findings,
            "deterministic_false_findings": det_false_findings,
            "semantic_true_findings": sem_true_findings,
            "semantic_false_findings": sem_false_findings,
            "unsupported_unknown_count": 0,
            "route_breakdown": route_counts,
            "route_by_category": category_routes,
            "route_by_role": role_routes,
            "route_by_difficulty": difficulty_routes
        },
        "candidate_routing": results
    }

    report_path = BASE_DIR / "reports" / "router_dev_report.json"
    requests_path = BASE_DIR / "reports" / "semantic_verifier_requests_DEV.json"

    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    requests_path.write_text(json.dumps(semantic_requests, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Total DEV Candidates Evaluated: {len(dev_candidates)}")
    print(f"  Deterministic Routes Total  : {len(dev_candidates) - len(semantic_requests)}")
    print(f"  Semantic Verifier Routes    : {len(semantic_requests)}")
    print(f"    - Semantic True Findings  : {sem_true_findings}")
    print(f"    - Semantic False Findings : {sem_false_findings}")
    print(f"Saved router report to: {report_path}")
    print(f"Saved semantic requests to: {requests_path}")


if __name__ == "__main__":
    run_production_router_eval()
