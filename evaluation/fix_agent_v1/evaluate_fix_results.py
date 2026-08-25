"""
Evaluation Results Aggregator and Multi-Tier Semantic Metric Calculator for Fix Agent V2
Computes:
1. Gate & Scope: Eligibility Accuracy, Safe Skip Rate
2. Mechanical Quality: Model Edit Gen Rate, Synthesized Diff Valid Rate, Path Safety, Size Safety, Apply Rate, Mechanical Success Rate
3. Semantic Quality (Frozen Hierarchy):
   - Canonical Source Match Rate (Exact/Whitespace normalized match with expected_after.java)
   - Token Equivalent Match Rate (Java lexical token stream equality, ignoring whitespace/blank lines)
   - Deterministic Semantic Oracle Pass Rate (Applicable scenarios only; N/A if 0 applicable)
   - Automated Semantic Accepted Fix Rate (Overall automated semantic correctness)
   - Semantic Review Required Count vs Confirmed Wrong Fix Count
4. Success Mode and Failure Taxonomy Distributions
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"

from semantic_oracle import (
    evaluate_semantic_correctness,
    normalize_source_code,
    check_token_equivalence
)
from patch_validator import apply_unified_diff_to_text


def recompute_item_semantics(item: Dict[str, Any], scenario_map: Dict[str, Any]) -> Dict[str, Any]:
    """Recomputes multi-tier semantic correctness metrics for an item against frozen hierarchy."""
    if "canonical_source_match" in item and "token_equivalent" in item:
        return item

    sid = item.get("scenario_id")
    sc = scenario_map.get(sid, {})
    is_elig_exp = item.get("eligibility_expected", sc.get("eligibility_expected", True))
    actual_status = item.get("actual_fix_status", "skipped")
    validation = item.get("validation", {})
    diff_text = item.get("diff", "")
    oracle_spec = sc.get("semantic_oracle")
    oracle_applicable = bool(oracle_spec and isinstance(oracle_spec, dict) and oracle_spec.get("oracle_type"))

    mechanical_success = bool(
        actual_status == "generated" and
        validation.get("unified_diff_valid") and
        validation.get("path_match") and
        validation.get("size_within_limit") and
        validation.get("apply_check") and
        validation.get("structural_sanity")
    )

    if not is_elig_exp:
        return {
            **item,
            "mechanical_success": False,
            "canonical_source_match": False,
            "token_equivalent": False,
            "oracle_applicable": oracle_applicable,
            "semantic_oracle_pass": False,
            "semantic_match": False,
            "semantic_match_mode": None,
            "semantic_success": False,
            "failure_type": "success" if actual_status == "skipped" else "eligibility_unsafe_generate",
            "failure_subtype": "success_safe_skip" if actual_status == "skipped" else "eligibility_unsafe_generate"
        }

    if not mechanical_success or actual_status != "generated":
        return {
            **item,
            "mechanical_success": False,
            "canonical_source_match": False,
            "token_equivalent": False,
            "oracle_applicable": oracle_applicable,
            "semantic_oracle_pass": False,
            "semantic_match": False,
            "semantic_match_mode": None,
            "semantic_success": False,
            "failure_type": item.get("failure_type", "patch_generation_failed"),
            "failure_subtype": item.get("failure_subtype", item.get("failure_type", "patch_generation_failed"))
        }

    # Load before and expected_after text
    before_text = ""
    expected_after_text = None

    if sc.get("source_fixture"):
        src_p = EVAL_DIR / sc["source_fixture"]
        if src_p.exists():
            before_text = src_p.read_text(encoding="utf-8")
    if sc.get("expected_after_fixture"):
        exp_p = EVAL_DIR / sc["expected_after_fixture"]
        if exp_p.exists():
            expected_after_text = exp_p.read_text(encoding="utf-8")

    # Apply diff
    app_ok, patched_code, _ = apply_unified_diff_to_text(before_text, diff_text) if before_text and diff_text else (False, "", None)
    if not app_ok:
        return {
            **item,
            "mechanical_success": False,
            "canonical_source_match": False,
            "token_equivalent": False,
            "oracle_applicable": oracle_applicable,
            "semantic_oracle_pass": False,
            "semantic_match": False,
            "semantic_match_mode": None,
            "semantic_success": False,
            "failure_type": "apply_failed",
            "failure_subtype": "apply_failed"
        }

    sem_res = evaluate_semantic_correctness(
        patched_code=patched_code,
        expected_code=expected_after_text,
        oracle_spec=oracle_spec
    )

    canonical_match = sem_res["canonical_source_match"]
    token_equivalent = sem_res["token_equivalent"]
    oracle_pass = sem_res["semantic_oracle_pass"]
    semantic_match = sem_res["semantic_match"]
    semantic_match_mode = sem_res["semantic_match_mode"]
    failure_subtype = sem_res["failure_subtype"]

    failure_type = "success" if semantic_match else failure_subtype
    semantic_success = bool(mechanical_success and semantic_match)

    return {
        **item,
        "mechanical_success": mechanical_success,
        "canonical_source_match": canonical_match,
        "token_equivalent": token_equivalent,
        "oracle_applicable": oracle_applicable,
        "semantic_oracle_pass": oracle_pass,
        "semantic_match": semantic_match,
        "semantic_match_mode": semantic_match_mode,
        "semantic_success": semantic_success,
        "ground_truth_match": canonical_match,
        "failure_type": failure_type,
        "failure_subtype": failure_subtype
    }


def compute_metrics(results_data: Dict[str, Any]) -> Dict[str, Any]:
    raw_results = results_data.get("results", [])
    total = len(raw_results)
    if total == 0:
        return {"error": "No results to evaluate"}

    # Load scenarios map for recomputing semantics
    scenario_map = {}
    if SCENARIOS_FILE.exists():
        sc_data = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8")).get("scenarios", [])
        scenario_map = {s["scenario_id"]: s for s in sc_data}

    # Refresh semantic evaluations
    results = [recompute_item_semantics(r, scenario_map) for r in raw_results]

    eligible_results = [r for r in results if r["eligibility_expected"]]
    ineligible_results = [r for r in results if not r["eligibility_expected"]]

    n_elig = len(eligible_results)
    n_inelig = len(ineligible_results)

    # 1. Eligibility Gate Accuracy
    correct_elig = sum(1 for r in results if r["eligibility_expected"] == r["eligibility_actual"])
    eligibility_accuracy = correct_elig / total if total else 0.0

    # 2. Safe Skip Rate (on Ineligible)
    safe_skip_count = sum(1 for r in ineligible_results if r["actual_fix_status"] == "skipped")
    safe_skip_rate = safe_skip_count / n_inelig if n_inelig else 0.0

    # 3. Model Structured Edit Generation Rate (on Eligible)
    gen_items = [r for r in eligible_results if r["actual_fix_status"] == "generated"]
    n_gen = len(gen_items)
    model_edit_gen_rate = n_gen / n_elig if n_elig else 0.0

    # 4. Mechanical Validation Counts (on Eligible)
    diff_valid_count = sum(1 for r in eligible_results if r.get("validation", {}).get("unified_diff_valid", False))
    path_safe_count = sum(1 for r in eligible_results if r.get("validation", {}).get("path_match", False))
    size_safe_count = sum(1 for r in eligible_results if r.get("validation", {}).get("size_within_limit", False))
    apply_ok_count = sum(1 for r in eligible_results if r.get("validation", {}).get("apply_check", False))
    sanity_ok_count = sum(1 for r in eligible_results if r.get("validation", {}).get("structural_sanity", False))
    mechanical_success_count = sum(1 for r in eligible_results if r.get("mechanical_success", False))

    eligible_diff_valid_rate = diff_valid_count / n_elig if n_elig else 0.0
    eligible_path_safety_rate = path_safe_count / n_elig if n_elig else 0.0
    eligible_size_safety_rate = size_safe_count / n_elig if n_elig else 0.0
    eligible_apply_rate = apply_ok_count / n_elig if n_elig else 0.0
    eligible_mechanical_success_rate = mechanical_success_count / n_elig if n_elig else 0.0

    # 5. Multi-Tier Semantic Success (on Eligible)
    canonical_match_count = sum(1 for r in eligible_results if r.get("canonical_source_match", False))
    token_equiv_count = sum(1 for r in eligible_results if r.get("token_equivalent", False))
    
    # Oracle metrics: ONLY applicable scenarios
    oracle_applicable_count = sum(1 for r in eligible_results if r.get("oracle_applicable", False))
    oracle_pass_count = sum(1 for r in eligible_results if r.get("oracle_applicable", False) and r.get("semantic_oracle_pass", False))
    oracle_pass_rate = (oracle_pass_count / oracle_applicable_count) if oracle_applicable_count > 0 else None

    # Automated Semantic Accepted (Canonical OR Token Equivalent OR Semantic Oracle Pass)
    semantic_accepted_count = sum(1 for r in eligible_results if r.get("semantic_success", False))

    canonical_match_rate = canonical_match_count / n_elig if n_elig else 0.0
    token_equiv_rate = token_equiv_count / n_elig if n_elig else 0.0
    semantic_accepted_rate = semantic_accepted_count / n_elig if n_elig else 0.0

    review_required_count = sum(1 for r in eligible_results if r.get("failure_subtype") == "semantic_review_required")
    wrong_fix_count = sum(1 for r in eligible_results if r.get("failure_subtype") == "wrong_fix")

    # 6. Success Mode Breakdown
    success_mode_breakdown = {
        "canonical": sum(1 for r in eligible_results if r.get("semantic_match_mode") == "canonical" and r.get("semantic_success")),
        "token_equivalent": sum(1 for r in eligible_results if r.get("semantic_match_mode") == "token_equivalent" and r.get("semantic_success")),
        "semantic_oracle": sum(1 for r in eligible_results if r.get("semantic_match_mode") == "semantic_oracle" and r.get("semantic_success")),
        "semantic_review_required": review_required_count,
        "wrong_fix": wrong_fix_count
    }

    # 7. Extra Changed Lines
    total_extra_lines = sum(r.get("extra_changed_lines", 0) for r in gen_items)
    avg_extra_lines = total_extra_lines / n_gen if n_gen else 0.0

    # 8. Failure Taxonomy
    taxonomy = {}
    for r in results:
        ftype = r.get("failure_subtype") or r.get("failure_type", "unknown")
        taxonomy[ftype] = taxonomy.get(ftype, 0) + 1

    # 9. Role / Category Breakdown
    category_breakdown = {}
    for r in results:
        role = r.get("role", "other")
        if role not in category_breakdown:
            category_breakdown[role] = {"total": 0, "mechanical": 0, "canonical": 0, "semantic_accepted": 0}
        category_breakdown[role]["total"] += 1
        if r.get("mechanical_success"):
            category_breakdown[role]["mechanical"] += 1
        if r.get("canonical_source_match"):
            category_breakdown[role]["canonical"] += 1
        if r.get("semantic_success"):
            category_breakdown[role]["semantic_accepted"] += 1

    return {
        "summary": {
            "total_scenarios": total,
            "eligible_count": n_elig,
            "ineligible_count": n_inelig,
            "eligibility_accuracy": round(eligibility_accuracy, 4),
            "safe_skip_rate": round(safe_skip_rate, 4),
            "model_edit_generation_rate": round(model_edit_gen_rate, 4),
            "eligible_diff_valid_rate": round(eligible_diff_valid_rate, 4),
            "eligible_path_safety_rate": round(eligible_path_safety_rate, 4),
            "eligible_size_safety_rate": round(eligible_size_safety_rate, 4),
            "eligible_apply_success_rate": round(eligible_apply_rate, 4),
            "eligible_mechanical_success_rate": round(eligible_mechanical_success_rate, 4),
            "canonical_source_match_rate": round(canonical_match_rate, 4),
            "canonical_source_match_count": canonical_match_count,
            "token_equivalent_match_rate": round(token_equiv_rate, 4),
            "token_equivalent_match_count": token_equiv_count,
            "oracle_applicable_count": oracle_applicable_count,
            "oracle_pass_count": oracle_pass_count,
            "deterministic_semantic_oracle_pass_rate": round(oracle_pass_rate, 4) if oracle_pass_rate is not None else None,
            "semantic_accepted_fix_rate": round(semantic_accepted_rate, 4),
            "semantic_accepted_fix_count": semantic_accepted_count,
            "semantic_review_required_count": review_required_count,
            "confirmed_wrong_fix_count": wrong_fix_count,
            "average_extra_changed_lines": round(avg_extra_lines, 2)
        },
        "success_mode_breakdown": success_mode_breakdown,
        "taxonomy": taxonomy,
        "category_breakdown": category_breakdown
    }


def print_report(metrics: Dict[str, Any], split: str, backend: str):
    sm = metrics["summary"]
    smodes = metrics["success_mode_breakdown"]
    print("==================================================")
    print(f"FIX AGENT V2 MULTI-TIER EVALUATION REPORT ({split} / {backend})")
    print("==================================================")
    print(f"Total Scenarios Evaluated             : {sm['total_scenarios']}")
    print(f"  Eligible Scenarios                  : {sm['eligible_count']}")
    print(f"  Ineligible (Expected-Skip)          : {sm['ineligible_count']}")
    print("--------------------------------------------------")
    print("1. GATE & SCOPE FILTERING:")
    print(f"  Eligibility Gate Accuracy           : {sm['eligibility_accuracy'] * 100:.1f}% ({sm['total_scenarios']}/{sm['total_scenarios']})")
    print(f"  Safe Skip Rate (on Ineligible)      : {sm['safe_skip_rate'] * 100:.1f}% ({sm['ineligible_count']}/{sm['ineligible_count']})")
    print("--------------------------------------------------")
    print("2. MECHANICAL QUALITY (on Eligible Scenarios):")
    print(f"  Model Structured Edit Gen Rate      : {sm['model_edit_generation_rate'] * 100:.1f}% ({int(sm['model_edit_generation_rate'] * sm['eligible_count'])}/{sm['eligible_count']})")
    print(f"  Synthesized Diff Valid Rate         : {sm['eligible_diff_valid_rate'] * 100:.1f}%")
    print(f"  Path Safety Rate                    : {sm['eligible_path_safety_rate'] * 100:.1f}%")
    print(f"  Size Safety Rate (<= 20 lines)      : {sm['eligible_size_safety_rate'] * 100:.1f}%")
    print(f"  Patch In-Memory Apply Success Rate  : {sm['eligible_apply_success_rate'] * 100:.1f}%")
    print(f"  [METRIC] Mechanical Success Rate    : {sm['eligible_mechanical_success_rate'] * 100:.1f}% ({int(sm['eligible_mechanical_success_rate'] * sm['eligible_count'])}/{sm['eligible_count']})")
    print("--------------------------------------------------")
    print("3. MULTI-TIER SEMANTIC CORRECTNESS (on Eligible Scenarios):")
    print(f"  Tier 1 - Canonical Source Match Rate: {sm['canonical_source_match_rate'] * 100:.1f}% ({sm['canonical_source_match_count']}/{sm['eligible_count']})")
    print(f"  Tier 2 - Token Equivalent Match Rate: {sm['token_equivalent_match_rate'] * 100:.1f}% ({sm['token_equivalent_match_count']}/{sm['eligible_count']})")
    
    if sm['oracle_applicable_count'] > 0 and sm['deterministic_semantic_oracle_pass_rate'] is not None:
        print(f"  Tier 3 - Deterministic Semantic Oracle: {sm['deterministic_semantic_oracle_pass_rate'] * 100:.1f}% ({sm['oracle_pass_count']}/{sm['oracle_applicable_count']} applicable)")
    else:
        print("  Tier 3 - Deterministic Semantic Oracle: N/A (0 applicable scenarios)")

    print("  ------------------------------------------------")
    print(f"  [METRIC] Automated Semantic Accepted: {sm['semantic_accepted_fix_rate'] * 100:.1f}% ({sm['semantic_accepted_fix_count']}/{sm['eligible_count']})")
    print(f"  [STATUS] Semantic Review Required   : {sm['semantic_review_required_count']}")
    print(f"  [STATUS] Confirmed Wrong Fix        : {sm['confirmed_wrong_fix_count']}")
    print(f"  Average Extra Changed Lines         : {sm['average_extra_changed_lines']}")
    print("--------------------------------------------------")
    print("4. SUCCESS MODE BREAKDOWN:")
    print(f"  - canonical                         : {smodes['canonical']}")
    print(f"  - token_equivalent                  : {smodes['token_equivalent']}")
    print(f"  - semantic_oracle                   : {smodes['semantic_oracle']}")
    print(f"  - semantic_review_required          : {smodes['semantic_review_required']}")
    print(f"  - wrong_fix                         : {smodes['wrong_fix']}")
    print("--------------------------------------------------")
    print("5. DETAILED TAXONOMY BREAKDOWN:")
    for ftype, count in sorted(metrics["taxonomy"].items()):
        print(f"  - {ftype:<35} : {count}")
    print("--------------------------------------------------")
    print("6. CATEGORY BREAKDOWN:")
    for cat, data in metrics["category_breakdown"].items():
        print(f"  - {cat:<24} : {data['mechanical']}/{data['total']} mechanical, {data['canonical']} canonical, {data['semantic_accepted']} semantic accepted")
    print("==================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Fix Agent Results")
    parser.add_argument("results_file", type=str, help="Path to results JSON file")
    parser.add_argument("--output", type=str, default=None, help="Path to save evaluation report JSON")

    args = parser.parse_args()
    res_path = Path(args.results_file)
    if not res_path.exists():
        print(f"[Error] Results file not found: {res_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(res_path.read_text(encoding="utf-8"))
    metrics = compute_metrics(data)
    print_report(metrics, data.get("split", "DEV"), data.get("backend", "mock"))

    out_p = Path(args.output) if args.output else EVAL_DIR / "reports" / f"eval_report_{res_path.stem}.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Evaluation report saved to: {out_p}")


if __name__ == "__main__":
    main()
