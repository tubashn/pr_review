"""
Evaluation Metrics Computation & Report Generator for Fix Agent Benchmark V2
Computes:
1. Multi-Tier Semantic Metrics (Canonical, Token-Equivalent, Semantic Oracle on Applicable Denominator)
2. Mechanical Quality Metrics (Diff Valid, Safety, Apply Success, Size Constraint)
3. Safety Metrics (Pre-Model Gate Safe Skips, Critical Gate Escapes, End-to-End Unsafe Fix Prevention Rate)
4. Corrected Category Breakdown with Separate Eligible & Ineligible Denominators
5. Difficulty Breakdown (EASY, MEDIUM, HARD)
6. Fix Complexity Breakdown (single_line, multi_line, boundary)
7. Alternative-Valid Fix Breakdown
8. Raw Numerator/Denominator Statistical Metadata for Exact Binomial CI Analysis
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIX_V1_DIR = REPO_ROOT / "evaluation" / "fix_agent_v1"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(FIX_V1_DIR) not in sys.path:
    sys.path.insert(0, str(FIX_V1_DIR))

from semantic_oracle import (
    evaluate_semantic_correctness,
    normalize_source_code,
    check_token_equivalence
)
from patch_validator import apply_unified_diff_to_text
from fix_eligibility import check_fix_eligibility

BENCHMARK_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BENCHMARK_DIR / "scenarios.json"


def load_scenario_map() -> Dict[str, Any]:
    if SCENARIOS_FILE.exists():
        scs = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8")).get("scenarios", [])
        return {s["scenario_id"]: s for s in scs}
    return {}


def re_evaluate_results(results_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offline re-evaluator for benchmark result records.
    Ensures that pre-model gate decisions, mechanical validation, and semantic correctness
    are cleanly evaluated using read-only scenario fixtures and frozen acceptance hierarchy.
    """
    scenario_map = load_scenario_map()
    results = results_data.get("results", [])
    updated_results = []

    for r in results:
        sid = r.get("scenario_id")
        sc = scenario_map.get(sid, {})
        is_elig_exp = sc.get("eligibility_expected", r.get("eligibility_expected", True))
        oracle_spec = sc.get("semantic_oracle", r.get("semantic_oracle"))

        before_path = BENCHMARK_DIR / sc.get("source_fixture", "") if sc.get("source_fixture") else None
        before_text = before_path.read_text(encoding="utf-8") if before_path and before_path.exists() else ""

        expected_after_path = BENCHMARK_DIR / sc.get("expected_after_fixture", "") if sc.get("expected_after_fixture") else None
        expected_after_text = expected_after_path.read_text(encoding="utf-8") if expected_after_path and expected_after_path.exists() else None

        finding = {
            "candidate_id": sid,
            "decision": "ACCEPT",
            "source_reviewer": sc.get("role", r.get("role")),
            "file": sc.get("file_path", r.get("file_path", "")),
            "file_path": sc.get("file_path", r.get("file_path", "")),
            "line": sc.get("line", r.get("line", 1)),
            "problem": sc.get("problem", r.get("problem", "")),
            "code_snippet": sc.get("evidence", r.get("code_snippet", "")),
            "after_source": before_text,
            "finding_type": sc.get("finding_type", "presence"),
            "context_scope": sc.get("context_scope", "single_method"),
            "scope": sc.get("context_scope", "single_method")
        }

        # 1. Deterministic pre-model gate decision
        gate_eval = check_fix_eligibility(finding, file_content=before_text)
        gate_eligible = gate_eval["eligible"]
        gate_reason = gate_eval["reason"]
        model_invoked = bool(gate_eligible)

        actual_status = r.get("actual_fix_status", "skipped")
        validation = r.get("validation", {})
        diff_text = r.get("diff", "")
        old_text = r.get("old_text", "")
        new_text = r.get("new_text", "")

        is_mechanically_valid = bool(
            actual_status == "generated"
            and validation.get("unified_diff_valid")
            and validation.get("path_match")
            and validation.get("size_within_limit")
            and validation.get("apply_check")
            and validation.get("structural_sanity")
        )

        mechanical_success = bool(is_elig_exp and gate_eligible and is_mechanically_valid)

        canonical_source_match = False
        token_equivalent = False
        oracle_applicable = bool(oracle_spec)
        semantic_oracle_pass = False
        semantic_match = False
        semantic_match_mode = None
        failure_subtype = None
        failure_type = None

        if not is_elig_exp:
            if not gate_eligible:
                failure_type = "success"
                failure_subtype = "success_safe_skip"
            elif actual_status == "rejected":
                failure_type = "success"
                failure_subtype = "success_validator_prevented"
            else:
                failure_type = "eligibility_unsafe_generate"
                failure_subtype = "eligibility_unsafe_generate"
        else:
            if not gate_eligible:
                failure_type = "eligibility_false_skip"
                failure_subtype = f"eligibility_false_skip_{gate_reason}"
            elif not is_mechanically_valid:
                failure_type = r.get("rejection_reason") or r.get("failure_type") or "mechanical_failure"
                failure_subtype = failure_type
            else:
                # Reconstruct patched text
                patched_text = r.get("patched_source")
                if not patched_text and diff_text and before_text:
                    app_ok, app_patched, app_err = apply_unified_diff_to_text(before_text, diff_text)
                    if app_ok:
                        patched_text = app_patched

                if not patched_text and old_text and before_text and old_text in before_text:
                    patched_text = before_text.replace(old_text, new_text, 1)

                if not patched_text:
                    failure_type = "mechanical_failure"
                    failure_subtype = "apply_failed"
                elif expected_after_text is not None:
                    sem_eval = evaluate_semantic_correctness(
                        patched_code=patched_text,
                        expected_code=expected_after_text,
                        oracle_spec=oracle_spec
                    )
                    canonical_source_match = sem_eval["canonical_source_match"]
                    token_equivalent = sem_eval["token_equivalent"]
                    oracle_applicable = sem_eval["oracle_applicable"]
                    semantic_oracle_pass = sem_eval["semantic_oracle_pass"]
                    semantic_match = sem_eval["semantic_match"]
                    semantic_match_mode = sem_eval["semantic_match_mode"]
                    failure_subtype = sem_eval["failure_subtype"]
                    failure_type = "success" if semantic_match else failure_subtype
                else:
                    failure_type = "unknown"
                    failure_subtype = "no_expected_fixture"

        item = dict(r)
        item["eligibility_expected"] = is_elig_exp
        item["eligibility_actual"] = gate_eligible
        item["eligibility_correct"] = (gate_eligible == is_elig_exp)
        item["gate_decision"] = "eligible" if gate_eligible else "skipped"
        item["gate_skip"] = not gate_eligible
        item["gate_reason"] = gate_reason
        item["model_invoked"] = model_invoked
        item["mechanical_success"] = mechanical_success
        item["canonical_source_match"] = canonical_source_match
        item["token_equivalent"] = token_equivalent
        item["oracle_applicable"] = oracle_applicable
        item["semantic_oracle_pass"] = semantic_oracle_pass
        item["semantic_match"] = semantic_match
        item["semantic_match_mode"] = semantic_match_mode
        item["semantic_success"] = semantic_match
        item["failure_type"] = failure_type
        item["failure_subtype"] = failure_subtype
        updated_results.append(item)

    updated_data = dict(results_data)
    updated_data["results"] = updated_results
    return updated_data


def compute_metrics(results_data: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure raw results have clean gate and semantic evaluation fields
    processed_data = re_evaluate_results(results_data)
    results = processed_data.get("results", [])
    split = processed_data.get("split", "DEV")
    backend = processed_data.get("backend", "unknown")
    total_scenarios = len(results)

    # 1. Gate & Scope
    eligible_scenarios = [r for r in results if r.get("eligibility_expected", True)]
    ineligible_scenarios = [r for r in results if not r.get("eligibility_expected", True)]

    eligible_count = len(eligible_scenarios)
    ineligible_count = len(ineligible_scenarios)

    correct_eligibility = sum(1 for r in results if r.get("eligibility_correct", False))
    safe_skips = sum(1 for r in ineligible_scenarios if r.get("gate_skip", False) or r.get("gate_decision") == "skipped")

    # Safety containment: ineligibles prevented from generating a valid patch (either skipped or rejected)
    unsafe_prevention_count = sum(1 for r in ineligible_scenarios if r.get("actual_fix_status") in ("skipped", "rejected"))
    critical_ineligibles = [r for r in ineligible_scenarios if r.get("role") == "security_validation" or "absence" in str(r.get("gate_reason", "")) or "security" in str(r.get("gate_reason", "")) or "unsupported" in str(r.get("gate_reason", ""))]
    critical_escapes = sum(1 for r in critical_ineligibles if r.get("actual_fix_status") == "generated")

    eligibility_accuracy = correct_eligibility / total_scenarios if total_scenarios else 0.0
    safe_skip_rate = safe_skips / ineligible_count if ineligible_count else 1.0
    unsafe_prevention_rate = unsafe_prevention_count / ineligible_count if ineligible_count else 1.0

    # 2. Mechanical Quality (on Eligible Scenarios)
    generated_count = sum(1 for r in eligible_scenarios if r.get("actual_fix_status") == "generated")
    valid_diff_count = sum(1 for r in eligible_scenarios if r.get("validation", {}).get("unified_diff_valid", False))
    path_safe_count = sum(1 for r in eligible_scenarios if r.get("validation", {}).get("path_match", False))
    size_safe_count = sum(1 for r in eligible_scenarios if r.get("validation", {}).get("size_within_limit", False))
    apply_clean_count = sum(1 for r in eligible_scenarios if r.get("validation", {}).get("apply_check", False))
    mechanical_success_count = sum(1 for r in eligible_scenarios if r.get("mechanical_success", False))

    # 3. Multi-Tier Semantic Correctness (on Eligible Scenarios)
    canonical_match_count = sum(1 for r in eligible_scenarios if r.get("canonical_source_match", False))
    token_equiv_match_count = sum(1 for r in eligible_scenarios if r.get("token_equivalent", False))
    
    oracle_applicable_count = sum(1 for r in eligible_scenarios if r.get("oracle_applicable", False))
    oracle_pass_count = sum(1 for r in eligible_scenarios if r.get("semantic_oracle_pass", False))
    
    semantic_accepted_fix_count = sum(1 for r in eligible_scenarios if r.get("semantic_match", False))
    semantic_review_req_count = sum(1 for r in eligible_scenarios if r.get("failure_subtype") == "semantic_review_required")
    confirmed_wrong_fix_count = sum(1 for r in eligible_scenarios if r.get("failure_subtype") == "wrong_fix")

    # Oracle pass rate: denominator is strictly applicable scenarios
    if oracle_applicable_count > 0:
        oracle_pass_rate = oracle_pass_count / oracle_applicable_count
    else:
        oracle_pass_rate = None

    # Success mode breakdown
    success_modes = {
        "canonical": canonical_match_count,
        "token_equivalent": sum(1 for r in eligible_scenarios if r.get("semantic_match_mode") == "token_equivalent"),
        "semantic_oracle": sum(1 for r in eligible_scenarios if r.get("semantic_match_mode") == "semantic_oracle"),
        "semantic_review_required": semantic_review_req_count,
        "wrong_fix": confirmed_wrong_fix_count
    }

    # Taxonomy breakdown
    taxonomy = {}
    for r in results:
        ftype = r.get("failure_subtype", r.get("failure_type", "unknown"))
        taxonomy[ftype] = taxonomy.get(ftype, 0) + 1

    # 4. Category Breakdown with Correct Denominators
    category_breakdown = {}
    for r in results:
        role = r.get("role", "unknown")
        if role not in category_breakdown:
            category_breakdown[role] = {
                "total": 0,
                "eligible": 0,
                "ineligible": 0,
                "mechanical_success": 0,
                "canonical_match": 0,
                "semantic_accepted": 0,
                "safe_skips": 0,
                "unsafe_prevented": 0
            }
        cat = category_breakdown[role]
        cat["total"] += 1
        is_elig = r.get("eligibility_expected", True)
        if is_elig:
            cat["eligible"] += 1
            if r.get("mechanical_success", False):
                cat["mechanical_success"] += 1
            if r.get("canonical_source_match", False):
                cat["canonical_match"] += 1
            if r.get("semantic_match", False):
                cat["semantic_accepted"] += 1
        else:
            cat["ineligible"] += 1
            if r.get("actual_fix_status") == "skipped":
                cat["safe_skips"] += 1
            if r.get("actual_fix_status") in ("skipped", "rejected"):
                cat["unsafe_prevented"] += 1

    # 5. Difficulty Breakdown
    difficulty_breakdown = {}
    for r in results:
        diff = r.get("difficulty", "MEDIUM")
        if diff not in difficulty_breakdown:
            difficulty_breakdown[diff] = {
                "total": 0,
                "eligible": 0,
                "ineligible": 0,
                "mechanical_success": 0,
                "semantic_accepted": 0,
                "safe_skips": 0
            }
        db = difficulty_breakdown[diff]
        db["total"] += 1
        if r.get("eligibility_expected", True):
            db["eligible"] += 1
            if r.get("mechanical_success", False):
                db["mechanical_success"] += 1
            if r.get("semantic_match", False):
                db["semantic_accepted"] += 1
        else:
            db["ineligible"] += 1
            if r.get("actual_fix_status") == "skipped":
                db["safe_skips"] += 1

    # 6. Fix Complexity Breakdown (Eligible only)
    complexity_breakdown = {}
    for r in eligible_scenarios:
        comp = r.get("fix_complexity", "single_line")
        if comp not in complexity_breakdown:
            complexity_breakdown[comp] = {
                "eligible_count": 0,
                "mechanical_success": 0,
                "semantic_accepted": 0,
                "review_required": 0,
                "wrong_fix": 0
            }
        cb = complexity_breakdown[comp]
        cb["eligible_count"] += 1
        if r.get("mechanical_success", False):
            cb["mechanical_success"] += 1
        if r.get("semantic_match", False):
            cb["semantic_accepted"] += 1
        if r.get("failure_subtype") == "semantic_review_required":
            cb["review_required"] += 1
        if r.get("failure_subtype") == "wrong_fix":
            cb["wrong_fix"] += 1

    # 7. Alternative-Valid Breakdown (Eligible only)
    alt_valid_scenarios = [r for r in eligible_scenarios if r.get("alternative_valid_fix", False)]
    alt_valid_breakdown = {
        "total_alt_valid": len(alt_valid_scenarios),
        "canonical_success": sum(1 for r in alt_valid_scenarios if r.get("canonical_source_match", False)),
        "token_success": sum(1 for r in alt_valid_scenarios if r.get("semantic_match_mode") == "token_equivalent"),
        "oracle_success": sum(1 for r in alt_valid_scenarios if r.get("semantic_match_mode") == "semantic_oracle"),
        "review_required": sum(1 for r in alt_valid_scenarios if r.get("failure_subtype") == "semantic_review_required"),
        "wrong_fix": sum(1 for r in alt_valid_scenarios if r.get("failure_subtype") == "wrong_fix")
    }

    # Summary dictionary with statistical raw counts
    summary = {
        "split": split,
        "backend": backend,
        "total_scenarios": total_scenarios,
        "eligible_count": eligible_count,
        "ineligible_count": ineligible_count,
        "eligibility_accuracy": {
            "passed": correct_eligibility,
            "total": total_scenarios,
            "rate": eligibility_accuracy
        },
        "safe_skip_rate": {
            "passed": safe_skips,
            "total": ineligible_count,
            "rate": safe_skip_rate
        },
        "unsafe_prevention_rate": {
            "passed": unsafe_prevention_count,
            "total": ineligible_count,
            "rate": unsafe_prevention_rate
        },
        "critical_gate_escape_count": critical_escapes,
        "mechanical_success": {
            "passed": mechanical_success_count,
            "total": eligible_count,
            "rate": mechanical_success_count / eligible_count if eligible_count else 0.0
        },
        "canonical_source_match": {
            "passed": canonical_match_count,
            "total": eligible_count,
            "rate": canonical_match_count / eligible_count if eligible_count else 0.0
        },
        "token_equivalent_match": {
            "passed": token_equiv_match_count,
            "total": eligible_count,
            "rate": token_equiv_match_count / eligible_count if eligible_count else 0.0
        },
        "deterministic_semantic_oracle": {
            "passed": oracle_pass_count,
            "applicable": oracle_applicable_count,
            "rate": oracle_pass_rate
        },
        "automated_semantic_accepted": {
            "passed": semantic_accepted_fix_count,
            "total": eligible_count,
            "rate": semantic_accepted_fix_count / eligible_count if eligible_count else 0.0
        },
        "semantic_review_required_count": semantic_review_req_count,
        "confirmed_wrong_fix_count": confirmed_wrong_fix_count,
        "success_modes": success_modes
    }

    return {
        "benchmark_version": "2.0",
        "summary": summary,
        "taxonomy": taxonomy,
        "category_breakdown": category_breakdown,
        "difficulty_breakdown": difficulty_breakdown,
        "complexity_breakdown": complexity_breakdown,
        "alternative_valid_breakdown": alt_valid_breakdown
    }


def print_evaluation_report(metrics: Dict[str, Any]):
    sm = metrics["summary"]
    smodes = sm["success_modes"]

    print("==================================================")
    print(f"FIX AGENT BENCHMARK V2 MULTI-TIER EVALUATION REPORT ({sm['split']} / {sm['backend']})")
    print("==================================================")
    print(f"Total Scenarios Evaluated             : {sm['total_scenarios']}")
    print(f"  Eligible Scenarios                  : {sm['eligible_count']}")
    print(f"  Ineligible (Expected-Skip)          : {sm['ineligible_count']}")
    print("--------------------------------------------------")
    print("1. GATE & SAFETY FILTERING:")
    ea = sm["eligibility_accuracy"]
    ssr = sm["safe_skip_rate"]
    upr = sm["unsafe_prevention_rate"]
    print(f"  Pre-Model Gate Accuracy             : {ea['rate'] * 100:.1f}% ({ea['passed']}/{ea['total']})")
    print(f"  Pre-Model Safe Skip Rate            : {ssr['rate'] * 100:.1f}% ({ssr['passed']}/{ssr['total']})")
    print(f"  Critical Pre-Model Gate Escapes     : {sm['critical_gate_escape_count']}")
    print(f"  [METRIC] End-to-End Unsafe Prevent  : {upr['rate'] * 100:.1f}% ({upr['passed']}/{upr['total']})")
    print("--------------------------------------------------")
    print("2. MECHANICAL QUALITY (on Eligible Scenarios):")
    ms = sm["mechanical_success"]
    print(f"  [METRIC] Mechanical Success Rate    : {ms['rate'] * 100:.1f}% ({ms['passed']}/{ms['total']})")
    print("--------------------------------------------------")
    print("3. MULTI-TIER SEMANTIC CORRECTNESS (on Eligible Scenarios):")
    csm = sm["canonical_source_match"]
    tem = sm["token_equivalent_match"]
    dso = sm["deterministic_semantic_oracle"]
    asa = sm["automated_semantic_accepted"]

    print(f"  Tier 1 - Canonical Source Match Rate: {csm['rate'] * 100:.1f}% ({csm['passed']}/{csm['total']})")
    print(f"  Tier 2 - Token Equivalent Match Rate: {tem['rate'] * 100:.1f}% ({tem['passed']}/{tem['total']})")
    if dso["applicable"] > 0:
        print(f"  Tier 3 - Deterministic Semantic Oracle: {dso['rate'] * 100:.1f}% ({dso['passed']}/{dso['applicable']} applicable)")
    else:
        print("  Tier 3 - Deterministic Semantic Oracle: N/A (0 applicable scenarios)")
    print("  ------------------------------------------------")
    print(f"  [METRIC] Automated Semantic Accepted: {asa['rate'] * 100:.1f}% ({asa['passed']}/{asa['total']})")
    print(f"  [STATUS] Semantic Review Required   : {sm['semantic_review_required_count']}")
    print(f"  [STATUS] Confirmed Wrong Fix        : {sm['confirmed_wrong_fix_count']}")
    print("--------------------------------------------------")
    print("4. SUCCESS MODE BREAKDOWN:")
    for mode, count in smodes.items():
        print(f"  - {mode:<35} : {count}")
    print("--------------------------------------------------")
    print("5. CATEGORY BREAKDOWN (Separate Eligible & Ineligible Denominators):")
    for cat, data in metrics["category_breakdown"].items():
        elig_str = f"{data['mechanical_success']}/{data['eligible']} mech, {data['semantic_accepted']}/{data['eligible']} semantic" if data['eligible'] > 0 else "0 eligible"
        inelig_str = f"{data['safe_skips']}/{data['ineligible']} safe-skips, {data['unsafe_prevented']}/{data['ineligible']} prevented" if data['ineligible'] > 0 else "0 inelig"
        print(f"  - {cat:<24} : [Eligible: {elig_str}] [Ineligible: {inelig_str}]")
    print("--------------------------------------------------")
    print("6. DIFFICULTY BREAKDOWN:")
    for diff, data in metrics["difficulty_breakdown"].items():
        print(f"  - {diff:<8} : Total={data['total']} (Eligible={data['eligible']}, Mech={data['mechanical_success']}, SemAccepted={data['semantic_accepted']}, SafeSkips={data['safe_skips']}/{data['ineligible']})")
    print("--------------------------------------------------")
    print("7. FIX COMPLEXITY BREAKDOWN (Eligible Scenarios):")
    for comp, data in metrics["complexity_breakdown"].items():
        print(f"  - {comp:<14} : Total={data['eligible_count']}, Mech={data['mechanical_success']}, SemAccepted={data['semantic_accepted']}, ReviewReq={data['review_required']}, Wrong={data['wrong_fix']}")
    print("--------------------------------------------------")
    print("8. ALTERNATIVE-VALID FIX BREAKDOWN:")
    avb = metrics["alternative_valid_breakdown"]
    print(f"  Total Alternative-Valid Scenarios   : {avb['total_alt_valid']}")
    print(f"  - Canonical Match                   : {avb['canonical_success']}")
    print(f"  - Token Equivalent                  : {avb['token_success']}")
    print(f"  - Semantic Oracle                   : {avb['oracle_success']}")
    print(f"  - Semantic Review Required          : {avb['review_required']}")
    print(f"  - Confirmed Wrong Fix               : {avb['wrong_fix']}")
    print("==================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Fix Agent Benchmark V2 Results")
    parser.add_argument("results_file", type=str, help="Path to results JSON file")
    parser.add_argument("--output", type=str, default=None, help="Path to save evaluation report JSON")
    parser.add_argument("--save-reevaluated", type=str, default=None, help="Path to save re-evaluated results JSON")

    args = parser.parse_args()
    res_path = Path(args.results_file)
    if not res_path.exists():
        print(f"[Error] Results file not found: {res_path}", file=sys.stderr)
        sys.exit(1)

    results_data = json.loads(res_path.read_text(encoding="utf-8"))
    processed_data = re_evaluate_results(results_data)
    metrics = compute_metrics(processed_data)

    print_evaluation_report(metrics)

    if args.save_reevaluated:
        save_p = Path(args.save_reevaluated)
        save_p.parent.mkdir(parents=True, exist_ok=True)
        save_p.write_text(json.dumps(processed_data, indent=2), encoding="utf-8")
        print(f"Re-evaluated results saved to: {save_p}")

    report_p = args.output
    if not report_p:
        rep_dir = BENCHMARK_DIR / "reports"
        rep_dir.mkdir(parents=True, exist_ok=True)
        split_name = results_data.get("split", "DEV").lower()
        backend_name = results_data.get("backend", "mock").lower()
        report_p = rep_dir / f"eval_report_{backend_name}_{split_name}.json"
    else:
        report_p = Path(report_p)

    report_p.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Evaluation report saved to: {report_p}")


if __name__ == "__main__":
    main()

