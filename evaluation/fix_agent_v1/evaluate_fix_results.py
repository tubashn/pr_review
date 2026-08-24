"""
Evaluation Results Aggregator and Metric Calculator for Fix Agent V1
Computes:
- Eligibility Accuracy
- Generation Rate
- Safe Skip Rate
- Unified Diff Valid Rate
- Path Safety Rate
- Size Safety Rate (<= 20 lines)
- Apply Success Rate
- Ground Truth Match Rate
- Strict Overall Fix Success Rate
- Average Extra Changed Lines
- Category & Difficulty breakdowns
- Failure taxonomy distributions
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

EVAL_DIR = Path(__file__).resolve().parent


def compute_metrics(results_data: Dict[str, Any]) -> Dict[str, Any]:
    results = results_data.get("results", [])
    total = len(results)
    if total == 0:
        return {"error": "No results to evaluate"}

    eligible_results = [r for r in results if r["eligibility_expected"]]
    ineligible_results = [r for r in results if not r["eligibility_expected"]]

    n_elig = len(eligible_results)
    n_inelig = len(ineligible_results)

    # 1. Eligibility Accuracy
    correct_elig = sum(1 for r in results if r["eligibility_expected"] == r["eligibility_actual"])
    eligibility_accuracy = correct_elig / total if total else 0.0

    # 2. Generation Rate (on eligible)
    generated_count = sum(1 for r in eligible_results if r["actual_fix_status"] == "generated")
    generation_rate = generated_count / n_elig if n_elig else 0.0

    # 3. Safe Skip Rate (on ineligible)
    safe_skip_count = sum(1 for r in ineligible_results if r["actual_fix_status"] == "skipped")
    safe_skip_rate = safe_skip_count / n_inelig if n_inelig else 0.0

    # 4. Validation Metrics (on eligible where patch was generated)
    gen_items = [r for r in eligible_results if r["actual_fix_status"] == "generated"]
    n_gen = len(gen_items)

    diff_valid_count = sum(1 for r in gen_items if r.get("validation", {}).get("unified_diff_valid", False))
    path_safe_count = sum(1 for r in gen_items if r.get("validation", {}).get("path_match", False))
    size_safe_count = sum(1 for r in gen_items if r.get("validation", {}).get("size_within_limit", False))
    apply_ok_count = sum(1 for r in gen_items if r.get("validation", {}).get("apply_check", False))

    diff_valid_rate = diff_valid_count / n_gen if n_gen else 0.0
    path_safe_rate = path_safe_count / n_gen if n_gen else 0.0
    size_safe_rate = size_safe_count / n_gen if n_gen else 0.0
    apply_rate = apply_ok_count / n_gen if n_gen else 0.0

    # 5. Ground Truth Match Rate (on eligible)
    gt_match_count = sum(1 for r in eligible_results if r.get("ground_truth_match", False))
    gt_match_rate = gt_match_count / n_elig if n_elig else 0.0

    # 6. Strict Overall Success Rate (on eligible: all checks pass + gt match)
    strict_success_count = sum(1 for r in eligible_results if r.get("failure_type") in ("success", "over_edit") and r.get("ground_truth_match", False))
    strict_success_rate = strict_success_count / n_elig if n_elig else 0.0

    # 7. Extra Changed Lines
    total_extra_lines = sum(r.get("extra_changed_lines", 0) for r in gen_items)
    avg_extra_lines = total_extra_lines / n_gen if n_gen else 0.0

    # 8. Failure Taxonomy
    taxonomy = {}
    for r in results:
        ftype = r.get("failure_type", "unknown")
        taxonomy[ftype] = taxonomy.get(ftype, 0) + 1

    # 9. Role / Category Breakdown
    category_breakdown = {}
    for r in results:
        role = r.get("role", "other")
        if role not in category_breakdown:
            category_breakdown[role] = {"total": 0, "success": 0, "gt_match": 0}
        category_breakdown[role]["total"] += 1
        if r.get("failure_type") in ("success", "over_edit"):
            category_breakdown[role]["success"] += 1
        if r.get("ground_truth_match"):
            category_breakdown[role]["gt_match"] += 1

    # 10. Difficulty Breakdown
    difficulty_breakdown = {}
    for r in results:
        diff_level = r.get("difficulty", "MEDIUM")
        if diff_level not in difficulty_breakdown:
            difficulty_breakdown[diff_level] = {"total": 0, "success": 0, "gt_match": 0}
        difficulty_breakdown[diff_level]["total"] += 1
        if r.get("failure_type") in ("success", "over_edit"):
            difficulty_breakdown[diff_level]["success"] += 1
        if r.get("ground_truth_match"):
            difficulty_breakdown[diff_level]["gt_match"] += 1

    return {
        "summary": {
            "total_scenarios": total,
            "eligible_count": n_elig,
            "ineligible_count": n_inelig,
            "eligibility_accuracy": round(eligibility_accuracy, 4),
            "generation_rate": round(generation_rate, 4),
            "safe_skip_rate": round(safe_skip_rate, 4),
            "unified_diff_valid_rate": round(diff_valid_rate, 4),
            "path_safety_rate": round(path_safe_rate, 4),
            "size_safety_rate": round(size_safe_rate, 4),
            "apply_success_rate": round(apply_rate, 4),
            "ground_truth_match_rate": round(gt_match_rate, 4),
            "strict_overall_success_rate": round(strict_success_rate, 4),
            "average_extra_changed_lines": round(avg_extra_lines, 2)
        },
        "taxonomy": taxonomy,
        "category_breakdown": category_breakdown,
        "difficulty_breakdown": difficulty_breakdown
    }


def print_report(metrics: Dict[str, Any], split: str, backend: str):
    sm = metrics["summary"]
    print("==================================================")
    print(f"FIX AGENT V1 EVALUATION REPORT ({split} / {backend})")
    print("==================================================")
    print(f"Total Scenarios Evaluated       : {sm['total_scenarios']}")
    print(f"  Eligible Scenarios            : {sm['eligible_count']}")
    print(f"  Ineligible (Expected-Skip)    : {sm['ineligible_count']}")
    print("--------------------------------------------------")
    print(f"Eligibility Gate Accuracy       : {sm['eligibility_accuracy'] * 100:.1f}%")
    print(f"Generation Rate (Eligible)      : {sm['generation_rate'] * 100:.1f}%")
    print(f"Safe Skip Rate (Ineligible)     : {sm['safe_skip_rate'] * 100:.1f}%")
    print(f"Unified Diff Valid Rate         : {sm['unified_diff_valid_rate'] * 100:.1f}%")
    print(f"Path Safety Rate                : {sm['path_safety_rate'] * 100:.1f}%")
    print(f"Size Safety Rate (<= 20 lines)  : {sm['size_safety_rate'] * 100:.1f}%")
    print(f"Patch Apply Success Rate        : {sm['apply_success_rate'] * 100:.1f}%")
    print(f"Ground Truth Match Rate         : {sm['ground_truth_match_rate'] * 100:.1f}%")
    print(f"Strict Overall Fix Success Rate : {sm['strict_overall_success_rate'] * 100:.1f}%")
    print(f"Average Extra Changed Lines     : {sm['average_extra_changed_lines']}")
    print("--------------------------------------------------")
    print("Failure Taxonomy Breakdown:")
    for ftype, count in sorted(metrics["taxonomy"].items()):
        print(f"  - {ftype:<28} : {count}")
    print("--------------------------------------------------")
    print("Category Breakdown:")
    for cat, data in metrics["category_breakdown"].items():
        print(f"  - {cat:<24} : {data['success']}/{data['total']} passed ({data['gt_match']} GT match)")
    print("--------------------------------------------------")
    print("Difficulty Breakdown:")
    for diff, data in metrics["difficulty_breakdown"].items():
        print(f"  - {diff:<12} : {data['success']}/{data['total']} passed ({data['gt_match']} GT match)")
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
