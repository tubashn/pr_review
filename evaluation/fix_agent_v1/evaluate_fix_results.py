"""
Evaluation Results Aggregator and Metric Calculator for Fix Agent V2
Computes:
- Eligibility Gate Accuracy
- Safe Skip Rate (on Ineligible)
- Mechanical Success Metrics (Grounded Edit, Valid Diff, In-memory Apply, Java Sanity)
- Semantic Success Metrics (Ground Truth Source Code Match)
- Strict Overall Success Rate (Mechanical Success + Semantic Match)
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

    # Rates with Denominator = Eligible Scenarios (n_elig)
    eligible_diff_valid_rate = diff_valid_count / n_elig if n_elig else 0.0
    eligible_path_safety_rate = path_safe_count / n_elig if n_elig else 0.0
    eligible_size_safety_rate = size_safe_count / n_elig if n_elig else 0.0
    eligible_apply_rate = apply_ok_count / n_elig if n_elig else 0.0
    eligible_mechanical_success_rate = mechanical_success_count / n_elig if n_elig else 0.0

    # Rates with Denominator = Generated Edits (n_gen)
    generated_diff_valid_rate = diff_valid_count / n_gen if n_gen else 0.0
    generated_apply_rate = apply_ok_count / n_gen if n_gen else 0.0

    # 5. Semantic Success (Ground Truth Match on Eligible)
    gt_match_count = sum(1 for r in eligible_results if r.get("ground_truth_match", False))
    eligible_gt_match_rate = gt_match_count / n_elig if n_elig else 0.0

    # 6. Strict Overall Success (Mechanical Success + Ground Truth Match)
    strict_success_count = sum(1 for r in eligible_results if r.get("mechanical_success") and r.get("ground_truth_match"))
    strict_overall_success_rate = strict_success_count / n_elig if n_elig else 0.0

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
            category_breakdown[role] = {"total": 0, "mechanical": 0, "semantic": 0}
        category_breakdown[role]["total"] += 1
        if r.get("mechanical_success"):
            category_breakdown[role]["mechanical"] += 1
        if r.get("ground_truth_match"):
            category_breakdown[role]["semantic"] += 1

    # 10. Difficulty Breakdown
    difficulty_breakdown = {}
    for r in results:
        diff_level = r.get("difficulty", "MEDIUM")
        if diff_level not in difficulty_breakdown:
            difficulty_breakdown[diff_level] = {"total": 0, "mechanical": 0, "semantic": 0}
        difficulty_breakdown[diff_level]["total"] += 1
        if r.get("mechanical_success"):
            difficulty_breakdown[diff_level]["mechanical"] += 1
        if r.get("ground_truth_match"):
            difficulty_breakdown[diff_level]["semantic"] += 1

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
            "generated_diff_valid_rate": round(generated_diff_valid_rate, 4),
            "generated_apply_success_rate": round(generated_apply_rate, 4),
            "eligible_ground_truth_match_rate": round(eligible_gt_match_rate, 4),
            "strict_overall_success_rate": round(strict_overall_success_rate, 4),
            "average_extra_changed_lines": round(avg_extra_lines, 2)
        },
        "taxonomy": taxonomy,
        "category_breakdown": category_breakdown,
        "difficulty_breakdown": difficulty_breakdown
    }


def print_report(metrics: Dict[str, Any], split: str, backend: str):
    sm = metrics["summary"]
    print("==================================================")
    print(f"FIX AGENT V2 EVALUATION REPORT ({split} / {backend})")
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
    print(f"  Model Structured Edit Gen Rate      : {sm['model_edit_generation_rate'] * 100:.1f}%")
    print(f"  Synthesized Diff Valid Rate         : {sm['eligible_diff_valid_rate'] * 100:.1f}%")
    print(f"  Path Safety Rate                    : {sm['eligible_path_safety_rate'] * 100:.1f}%")
    print(f"  Size Safety Rate (<= 20 lines)      : {sm['eligible_size_safety_rate'] * 100:.1f}%")
    print(f"  Patch In-Memory Apply Success Rate  : {sm['eligible_apply_success_rate'] * 100:.1f}%")
    print(f"  [METRIC] Mechanical Success Rate    : {sm['eligible_mechanical_success_rate'] * 100:.1f}%")
    print("--------------------------------------------------")
    print("3. SEMANTIC QUALITY (on Eligible Scenarios):")
    print(f"  Ground Truth Source Match Rate      : {sm['eligible_ground_truth_match_rate'] * 100:.1f}%")
    print(f"  [METRIC] Strict Overall Fix Success : {sm['strict_overall_success_rate'] * 100:.1f}%")
    print(f"  Average Extra Changed Lines         : {sm['average_extra_changed_lines']}")
    print("--------------------------------------------------")
    print("4. FAILURE TAXONOMY BREAKDOWN:")
    for ftype, count in sorted(metrics["taxonomy"].items()):
        print(f"  - {ftype:<32} : {count}")
    print("--------------------------------------------------")
    print("5. CATEGORY BREAKDOWN:")
    for cat, data in metrics["category_breakdown"].items():
        print(f"  - {cat:<24} : {data['mechanical']}/{data['total']} mechanical, {data['semantic']} semantic match")
    print("--------------------------------------------------")
    print("6. DIFFICULTY BREAKDOWN:")
    for diff, data in metrics["difficulty_breakdown"].items():
        print(f"  - {diff:<12} : {data['mechanical']}/{data['total']} mechanical, {data['semantic']} semantic match")
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

