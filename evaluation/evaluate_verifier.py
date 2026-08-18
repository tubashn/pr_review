# ==============================================================================
# WARNING: TEST SET METADATA
# This file and associated verifier code constitute a static TEST SET
# designed solely for evaluating model performance.
# DO NOT INCLUDE these files or evaluation data in model training sets.
# ==============================================================================

import sys
import json
import re
from pathlib import Path

# Ensure repo root is on sys.path for direct invocations
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def clean_raw_response(raw_response: str) -> str:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: Missing verifier results file path.", file=sys.stderr)
        print("Usage: python agent/evaluation/evaluate_verifier.py <verifier-results-json>", file=sys.stderr)
        sys.exit(1)

    results_file = Path(sys.argv[1]).resolve()
    print(f"Evaluating verifier results file: {results_file}")

    if not results_file.exists():
        print(f"Error: Results file '{results_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    benchmark_file = script_dir / "verifier_benchmark.json"
    report_file = script_dir / "verifier_evaluation_report.json"

    if not benchmark_file.exists():
        print(f"Error: Benchmark file '{benchmark_file}' not found. Please run build_verifier_benchmark.py first.", file=sys.stderr)
        sys.exit(1)

    # Load benchmark and results
    with open(benchmark_file, "r", encoding="utf-8") as f:
        benchmark = json.load(f)
    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Map benchmark expected values
    benchmark_map = {c["candidate_id"]: c for c in benchmark}

    tp = 0
    fp = 0
    fn = 0
    tn = 0
    tn_fp = 0
    tn_leakage = 0
    tn_clean = 0
    parse_error_count = 0

    expected_accept = 0
    expected_fp = 0
    expected_leakage = 0
    expected_clean = 0

    evaluation_details = []
    role_leakage_candidates = []

    # Map results by candidate_id
    results_map = {r["candidate_id"]: r for r in results}

    # Track V5 diagnostic metrics
    diag_problem_present_true = 0
    diag_problem_present_false = 0
    diag_role_match_true = 0
    diag_role_match_false = 0
    diag_grounding_valid = 0
    diag_grounding_invalid = 0
    diag_strategy_direct = 0
    diag_strategy_absence_ref = 0
    diag_strategy_absence_resource = 0
    diag_problem_present_bypassed_count = 0
    is_v5_evaluation = False

    for candidate in benchmark:
        candidate_id = candidate["candidate_id"]
        branch = candidate["branch"]
        source_reviewer = candidate["source_reviewer"]
        expected_verdict = candidate["expected_verdict"]
        reason_type = candidate["expected_reason_type"]
        added_lines = candidate.get("added_lines_for_grounding", [])
        pr_context = candidate.get("pr_context", "")
        cand_finding = candidate.get("candidate_finding", {})
        cand_problem = cand_finding.get("problem", "")

        grounding_strategy_used = None
        grounding_valid_res = None
        prob_present_val = None
        role_match_val = None
        prob_present_bypassed_val = None

        # Track expected categories
        if expected_verdict == "ACCEPT":
            expected_accept += 1
        else:
            if reason_type == "false_positive":
                expected_fp += 1
            elif reason_type == "role_leakage":
                expected_leakage += 1
            elif reason_type == "clean_pr_false_positive":
                expected_clean += 1

        result_record = results_map.get(candidate_id)
        if not result_record:
            # Missing result counted as parse error
            parse_error_count += 1
            predicted_verdict = "PARSE_ERROR"
            status = "FN" if expected_verdict == "ACCEPT" else "FP"
            print(f"\nMissing Result Error for Candidate: {candidate_id}")
        else:
            raw_response = result_record.get("raw_response", "")
            cleaned = clean_raw_response(raw_response)
            try:
                parsed = json.loads(cleaned)
                if not isinstance(parsed, dict):
                    raise ValueError("Parsed JSON response must be an object/dict")

                predicted_verdict = None

                # Check V5 Decomposed format
                if "problem_present_in_changed_code" in parsed or "reviewer_role_matches_problem" in parsed:
                    is_v5_evaluation = True
                    prob_present = parsed.get("problem_present_in_changed_code")
                    role_match = parsed.get("reviewer_role_matches_problem")
                    quote = parsed.get("problem_evidence_quote")

                    if not isinstance(prob_present, bool):
                        raise ValueError(f"problem_present_in_changed_code must be strict boolean, got: {repr(prob_present)} ({type(prob_present).__name__})")
                    if not isinstance(role_match, bool):
                        raise ValueError(f"reviewer_role_matches_problem must be strict boolean, got: {repr(role_match)} ({type(role_match).__name__})")

                    prob_present_val = prob_present
                    role_match_val = role_match

                    if prob_present:
                        diag_problem_present_true += 1
                    else:
                        diag_problem_present_false += 1

                    if role_match:
                        diag_role_match_true += 1
                    else:
                        diag_role_match_false += 1

                    # Deterministic absence-aware grounding verification
                    from verifier_prompt_builder import (
                        verify_grounding_for_candidate,
                        compute_v5_finding_supported,
                        STRATEGY_DIRECT,
                        STRATEGY_ABSENCE_REFERENCE,
                        STRATEGY_ABSENCE_RESOURCE_CLEANUP
                    )
                    grounded, strategy = verify_grounding_for_candidate(cand_problem, quote, added_lines, pr_context)
                    grounding_strategy_used = strategy
                    grounding_valid_res = grounded

                    if strategy == STRATEGY_DIRECT:
                        diag_strategy_direct += 1
                    elif strategy == STRATEGY_ABSENCE_REFERENCE:
                        diag_strategy_absence_ref += 1
                    elif strategy == STRATEGY_ABSENCE_RESOURCE_CLEANUP:
                        diag_strategy_absence_resource += 1

                    if grounded:
                        diag_grounding_valid += 1
                    else:
                        diag_grounding_invalid += 1

                    # V5.3 Deterministic Strategy-Aware Composition
                    final_finding_supported, prob_present_bypassed = compute_v5_finding_supported(
                        strategy, prob_present, grounded, role_match
                    )
                    prob_present_bypassed_val = prob_present_bypassed
                    if prob_present_bypassed:
                        diag_problem_present_bypassed_count += 1

                    predicted_verdict = "ACCEPT" if final_finding_supported else "REJECT"

                # Check boolean finding_supported (V4 format)
                elif "finding_supported" in parsed:
                    fs = parsed.get("finding_supported")
                    if not isinstance(fs, bool):
                        raise ValueError(f"finding_supported must be a strict boolean (True/False), got: {repr(fs)} ({type(fs).__name__})")
                    predicted_verdict = "ACCEPT" if fs is True else "REJECT"

                # Check legacy verdict string (V1-V3, V4.1 format)
                elif "verdict" in parsed:
                    raw_v = parsed.get("verdict")
                    if not isinstance(raw_v, str):
                        raise ValueError(f"verdict must be a string, got: {repr(raw_v)}")
                    v_str = raw_v.strip().upper()
                    if v_str not in ["ACCEPT", "REJECT"]:
                        raise ValueError(f"Invalid verdict value: {v_str}")
                    predicted_verdict = v_str

                if predicted_verdict is None:
                    raise ValueError("Could not extract verdict: Neither V5 atomic fields, finding_supported, nor verdict found")

            except Exception as e:
                parse_error_count += 1
                predicted_verdict = "PARSE_ERROR"
                print(f"\nParse Error on Candidate: {candidate_id}, Branch: {branch}")
                print(f"Error Details: {e}")
                print("raw_response value:")
                print(raw_response)

        # Classification logic
        if predicted_verdict == "PARSE_ERROR":
            status = "PARSE_ERROR"
            if expected_verdict == "ACCEPT":
                fn += 1
            else:
                fp += 1
        elif expected_verdict == "ACCEPT":
            if predicted_verdict == "ACCEPT":
                status = "TP"
                tp += 1
            else:
                status = "FN"
                fn += 1
        else:  # expected_verdict == "REJECT"
            if predicted_verdict == "ACCEPT":
                status = "FP"
                fp += 1
            else:
                status = "TN"
                tn += 1
                if reason_type == "false_positive":
                    tn_fp += 1
                elif reason_type == "role_leakage":
                    tn_leakage += 1
                elif reason_type == "clean_pr_false_positive":
                    tn_clean += 1

        detail_item = {
            "candidate_id": candidate_id,
            "branch": branch,
            "source_reviewer": source_reviewer,
            "expected_verdict": expected_verdict,
            "predicted_verdict": predicted_verdict,
            "status": status,
            "reason_type": reason_type
        }
        if is_v5_evaluation:
            detail_item.update({
                "grounding_strategy": grounding_strategy_used,
                "grounding_valid": grounding_valid_res,
                "problem_present": prob_present_val,
                "role_match": role_match_val,
                "problem_present_bypassed": prob_present_bypassed_val
            })
        evaluation_details.append(detail_item)

        if reason_type == "role_leakage":
            role_leakage_candidates.append({
                "candidate_id": candidate_id,
                "expected": expected_verdict,
                "predicted": predicted_verdict,
                "status": status
            })

    # Metric calculations
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    true_preservation_rate = tp / expected_accept if expected_accept > 0 else 0.0
    false_rejection_rate = tn_fp / expected_fp if expected_fp > 0 else 0.0
    leakage_rejection_rate = tn_leakage / expected_leakage if expected_leakage > 0 else 0.0
    clean_rejection_rate = tn_clean / expected_clean if expected_clean > 0 else 0.0

    metrics = {
        "True Positive": tp,
        "False Positive": fp,
        "False Negative": fn,
        "True Negative": tn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
        "True Finding Preservation Rate": true_preservation_rate,
        "False Finding Rejection Rate": false_rejection_rate,
        "Role Leakage Rejection Rate": leakage_rejection_rate,
        "Clean PR False Finding Rejection Rate": clean_rejection_rate,
        "Parse Error Count": parse_error_count
    }

    if is_v5_evaluation:
        metrics.update({
            "Diagnostic problem_present=True Count": diag_problem_present_true,
            "Diagnostic problem_present=False Count": diag_problem_present_false,
            "Diagnostic role_match=True Count": diag_role_match_true,
            "Diagnostic role_match=False Count": diag_role_match_false,
            "Diagnostic Grounding Valid Count": diag_grounding_valid,
            "Diagnostic Grounding Invalid Count": diag_grounding_invalid,
            "Diagnostic Strategy DIRECT Count": diag_strategy_direct,
            "Diagnostic Strategy ABSENCE_REFERENCE Count": diag_strategy_absence_ref,
            "Diagnostic Strategy ABSENCE_RESOURCE_CLEANUP Count": diag_strategy_absence_resource,
            "Diagnostic Problem Present Bypass Count": diag_problem_present_bypassed_count
        })

    # Write report
    report = {
        "metadata": {
            "purpose": "VERIFIER EVALUATION REPORT",
            "evaluated_results_file": str(results_file)
        },
        "metrics": metrics,
        "detailed_results": evaluation_details
    }
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary metrics to console
    print("\n=========================================")
    print("VERIFIER EVALUATION SUMMARY")
    print("=========================================")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"{k:<40}: {v:.4f}")
        else:
            print(f"{k:<40}: {v}")

    # Print role leakage candidates
    if role_leakage_candidates:
        print("\n=========================================")
        print("ROLE LEAKAGE CANDIDATES")
        print("=========================================")
        for rlc in role_leakage_candidates:
            print(f"  {rlc['candidate_id']:<60} | Expected: {rlc['expected']} | Predicted: {rlc['predicted']} | Status: {rlc['status']}")

    # Print detailed table to console
    print("\n==========================================================================================")
    print(f"{'Candidate ID':<55} | {'Branch':<28} | {'Expected':<8} | {'Predicted':<12} | {'Status'}")
    print("==========================================================================================")
    for d in evaluation_details:
        # short candidate ID for readability
        print(f"{d['candidate_id']:<55} | {d['branch']:<28} | {d['expected_verdict']:<8} | {d['predicted_verdict']:<12} | {d['status']}")


if __name__ == "__main__":
    main()
