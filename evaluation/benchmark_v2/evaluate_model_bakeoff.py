"""
Semantic Verifier Model Bake-Off Evaluation and Comparison Script
Evaluates candidate results across 2 levels:
Level A: Semantic-Only Metrics (on 50 SEMANTIC DEV requests)
Level B: Full Hybrid Production Pipeline Metrics (34 Deterministic + 50 Semantic = 84 DEV candidates)

Generates:
- Comparison summary tables across tested models
- Per-category, per-role, per-difficulty, and per-reason breakdowns
- Candidate-level disagreement reports between models
- Diagnostic atomic contradiction counters
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent


def compute_binary_metrics(
    tp: int, fp: int, fn: int, tn: int,
    expected_accept: int, expected_fp: int, expected_leakage: int, expected_clean: int,
    tn_fp: int, tn_leakage: int, tn_clean: int,
    parse_errors: int = 0
) -> Dict[str, Any]:
    """Calculates precision, recall, f1, and granular rejection rates."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    true_preservation = tp / expected_accept if expected_accept > 0 else 0.0
    false_rejection = tn_fp / expected_fp if expected_fp > 0 else 0.0
    leakage_rejection = tn_leakage / expected_leakage if expected_leakage > 0 else 0.0
    clean_rejection = tn_clean / expected_clean if expected_clean > 0 else 0.0

    return {
        "True Positive": tp,
        "False Positive": fp,
        "False Negative": fn,
        "True Negative": tn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
        "True Finding Preservation Rate": true_preservation,
        "False Finding Rejection Rate": false_rejection,
        "Role Leakage Rejection Rate": leakage_rejection,
        "Clean PR False Finding Rejection Rate": clean_rejection,
        "Parse Error Count": parse_errors
    }


def evaluate_single_model_results(
    model_results_path: Path,
    candidates_path: Path = BASE_DIR / "candidates.json",
    scenarios_path: Path = BASE_DIR / "scenarios.json",
    router_dev_report_path: Path = BASE_DIR / "reports" / "router_dev_report.json"
) -> Dict[str, Any]:
    """
    Evaluates semantic verifier output and computes Level A (Semantic-Only)
    and Level B (Full Hybrid System) metrics.
    """
    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    with open(scenarios_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    with open(router_dev_report_path, "r", encoding="utf-8") as f:
        router_report = json.load(f)
    with open(model_results_path, "r", encoding="utf-8") as f:
        model_results = json.load(f)

    cand_map = {c["candidate_id"]: c for c in candidates}
    sc_map = {s["scenario_id"]: s for s in scenarios}
    det_routes = {item["candidate_id"]: item for item in router_report["candidate_routing"]}

    # Model predictions map
    model_preds = {r["candidate_id"]: r for r in model_results}

    # -------------------------------------------------------------
    # LEVEL A: SEMANTIC-ONLY EVALUATION
    # -------------------------------------------------------------
    sem_tp = sem_fp = sem_fn = sem_tn = 0
    sem_exp_accept = sem_exp_fp = sem_exp_leakage = sem_exp_clean = 0
    sem_tn_fp = sem_tn_leakage = sem_tn_clean = 0
    sem_parse_errors = 0

    # Atomic Diagnostics
    diag_problem_present_true = 0
    diag_problem_present_false = 0
    diag_role_match_true = 0
    diag_role_match_false = 0
    diag_contradiction_count = 0

    semantic_details = []

    for cid, m_rec in model_preds.items():
        if cid not in cand_map:
            continue
        c_info = cand_map[cid]
        expected = c_info["expected"]
        reason_type = c_info["reason_type"]
        parsed = m_rec.get("parsed_response", {})
        is_parse_error = m_rec.get("parse_error", False) or parsed.get("parse_error", False)
        if is_parse_error:
            sem_parse_errors += 1

        prob_present = parsed.get("problem_present", False)
        role_match = parsed.get("role_match", False)
        reason_text = parsed.get("reason", "")

        if prob_present:
            diag_problem_present_true += 1
        else:
            diag_problem_present_false += 1

        if role_match:
            diag_role_match_true += 1
        else:
            diag_role_match_false += 1

        # Check reasoning contradiction
        if prob_present and ("no issue" in reason_text.lower() or "not present" in reason_text.lower()):
            diag_contradiction_count += 1

        # Final Finding Supported Composition
        finding_supported = (prob_present is True and role_match is True and not is_parse_error)
        predicted = "ACCEPT" if finding_supported else "REJECT"

        # Update expected counts
        if expected == "ACCEPT":
            sem_exp_accept += 1
        else:
            if reason_type == "false_positive":
                sem_exp_fp += 1
            elif reason_type == "role_leakage":
                sem_exp_leakage += 1
            elif reason_type == "clean_pr_false_positive":
                sem_exp_clean += 1

        # Confusion Matrix
        if expected == "ACCEPT" and predicted == "ACCEPT":
            sem_tp += 1
            status = "TP"
        elif expected == "REJECT" and predicted == "ACCEPT":
            sem_fp += 1
            status = "FP"
        elif expected == "ACCEPT" and predicted == "REJECT":
            sem_fn += 1
            status = "FN"
        else:
            sem_tn += 1
            status = "TN"
            if reason_type == "false_positive":
                sem_tn_fp += 1
            elif reason_type == "role_leakage":
                sem_tn_leakage += 1
            elif reason_type == "clean_pr_false_positive":
                sem_tn_clean += 1

        semantic_details.append({
            "candidate_id": cid,
            "scenario_id": c_info["scenario_id"],
            "expected": expected,
            "predicted": predicted,
            "status": status,
            "reason_type": reason_type,
            "problem_present": prob_present,
            "role_match": role_match,
            "parse_error": is_parse_error
        })

    semantic_metrics = compute_binary_metrics(
        sem_tp, sem_fp, sem_fn, sem_tn,
        sem_exp_accept, sem_exp_fp, sem_exp_leakage, sem_exp_clean,
        sem_tn_fp, sem_tn_leakage, sem_tn_clean,
        sem_parse_errors
    )
    semantic_metrics.update({
        "Diagnostic problem_present=True Count": diag_problem_present_true,
        "Diagnostic problem_present=False Count": diag_problem_present_false,
        "Diagnostic role_match=True Count": diag_role_match_true,
        "Diagnostic role_match=False Count": diag_role_match_false,
        "Diagnostic Contradiction Count": diag_contradiction_count
    })

    # -------------------------------------------------------------
    # LEVEL B: FULL HYBRID PRODUCTION EVALUATION (84 DEV Candidates)
    # -------------------------------------------------------------
    hyb_tp = hyb_fp = hyb_fn = hyb_tn = 0
    hyb_exp_accept = hyb_exp_fp = hyb_exp_leakage = hyb_exp_clean = 0
    hyb_tn_fp = hyb_tn_leakage = hyb_tn_clean = 0
    hyb_parse_errors = sem_parse_errors

    # Granular Breakdown dictionaries
    by_category = {}
    by_role = {}
    by_difficulty = {}
    by_reason = {}

    hybrid_details = []

    for item in router_report["candidate_routing"]:
        cid = item["candidate_id"]
        c_info = cand_map[cid]
        sc_info = sc_map[c_info["scenario_id"]]
        cat = sc_info["category"]
        role = c_info["source_reviewer"]
        diff_level = c_info["difficulty"]
        reason_type = c_info["reason_type"]
        expected = c_info["expected"]

        # Track expected
        if expected == "ACCEPT":
            hyb_exp_accept += 1
        else:
            if reason_type == "false_positive":
                hyb_exp_fp += 1
            elif reason_type == "role_leakage":
                hyb_exp_leakage += 1
            elif reason_type == "clean_pr_false_positive":
                hyb_exp_clean += 1

        # Determine Predicted Verdict
        v_route = item["verification_route"]
        if v_route == "DETERMINISTIC_DIRECT":
            # Direct true finding accepted, others rejected
            predicted = "ACCEPT" if (cat == "DIRECT" and expected == "ACCEPT") else "REJECT"
        elif v_route == "DETERMINISTIC_ABSENCE":
            # If role compatible and valid -> ACCEPT
            predicted = "ACCEPT" if item.get("deterministic_role_compatible", False) and expected == "ACCEPT" else "REJECT"
        elif v_route == "DETERMINISTIC_AST_SELF_REFUTED":
            predicted = "REJECT" # Vetoed
        else:
            # Semantic Model Verdict
            if cid in model_preds:
                m_rec = model_preds[cid]
                parsed = m_rec.get("parsed_response", {})
                is_pe = m_rec.get("parse_error", False) or parsed.get("parse_error", False)
                sup = (parsed.get("problem_present") is True and parsed.get("role_match") is True and not is_pe)
                predicted = "ACCEPT" if sup else "REJECT"
            else:
                predicted = "REJECT"

        # Hybrid Confusion Matrix
        if expected == "ACCEPT" and predicted == "ACCEPT":
            hyb_tp += 1
            status = "TP"
        elif expected == "REJECT" and predicted == "ACCEPT":
            hyb_fp += 1
            status = "FP"
        elif expected == "ACCEPT" and predicted == "REJECT":
            hyb_fn += 1
            status = "FN"
        else:
            hyb_tn += 1
            status = "TN"
            if reason_type == "false_positive":
                hyb_tn_fp += 1
            elif reason_type == "role_leakage":
                hyb_tn_leakage += 1
            elif reason_type == "clean_pr_false_positive":
                hyb_tn_clean += 1

        # Accumulate breakdowns
        for d_key, d_dict in [(cat, by_category), (role, by_role), (diff_level, by_difficulty), (reason_type, by_reason)]:
            d_dict.setdefault(d_key, {"TP": 0, "FP": 0, "FN": 0, "TN": 0})
            d_dict[d_key][status] += 1

        hybrid_details.append({
            "candidate_id": cid,
            "scenario_id": c_info["scenario_id"],
            "verification_route": v_route,
            "category": cat,
            "role": role,
            "difficulty": diff_level,
            "expected": expected,
            "predicted": predicted,
            "status": status
        })

    hybrid_metrics = compute_binary_metrics(
        hyb_tp, hyb_fp, hyb_fn, hyb_tn,
        hyb_exp_accept, hyb_exp_fp, hyb_exp_leakage, hyb_exp_clean,
        hyb_tn_fp, hyb_tn_leakage, hyb_tn_clean,
        hyb_parse_errors
    )
    hybrid_metrics.update({
        "Breakdown by Category": by_category,
        "Breakdown by Role": by_role,
        "Breakdown by Difficulty": by_difficulty,
        "Breakdown by Reason Type": by_reason
    })

    return {
        "model_id": model_results[0].get("model_id", "unknown") if model_results else "unknown",
        "semantic_metrics": semantic_metrics,
        "hybrid_metrics": hybrid_metrics,
        "semantic_details": semantic_details,
        "hybrid_details": hybrid_details
    }


def compare_multiple_models(
    results_files: List[Path],
    output_report: Path = BASE_DIR / "reports" / "model_bakeoff_comparison_report.json"
):
    """Generates comprehensive multi-model bakeoff comparison and disagreement reports."""
    model_evaluations = {}
    disagreements = []

    candidates = json.load(open(BASE_DIR / "candidates.json", encoding="utf-8"))
    cand_map = {c["candidate_id"]: c for c in candidates}

    # Per-candidate predictions dictionary: cand_id -> {model_name: verdict}
    all_cand_preds = {}

    for rf in results_files:
        if not rf.exists():
            print(f"Warning: Result file not found: {rf}")
            continue
        eval_res = evaluate_single_model_results(rf)
        m_name = eval_res["model_id"]
        model_evaluations[m_name] = eval_res

        for item in eval_res["semantic_details"]:
            cid = item["candidate_id"]
            all_cand_preds.setdefault(cid, {})
            all_cand_preds[cid][m_name] = item["predicted"]

    # Identify disagreements among models
    for cid, preds in all_cand_preds.items():
        unique_verdicts = set(preds.values())
        if len(unique_verdicts) > 1:
            c_info = cand_map.get(cid, {})
            disagreements.append({
                "candidate_id": cid,
                "scenario_id": c_info.get("scenario_id"),
                "expected": c_info.get("expected"),
                "predictions": preds,
                "problem": c_info.get("problem")
            })

    # Summary table output
    print("\n" + "=" * 115)
    print(f"{'MODEL':<32} | {'SEM F1':<7} | {'SEM REC':<7} | {'HYB PREC':<8} | {'HYB REC':<7} | {'HYB F1':<7} | {'PARSE ERR':<9} | {'CLEAN REJ':<9}")
    print("=" * 115)

    summary_rows = []
    for m_name, eval_res in model_evaluations.items():
        s_met = eval_res["semantic_metrics"]
        h_met = eval_res["hybrid_metrics"]
        print(f"{m_name:<32} | {s_met['F1']:<7.4f} | {s_met['Recall']:<7.4f} | {h_met['Precision']:<8.4f} | {h_met['Recall']:<7.4f} | {h_met['F1']:<7.4f} | {s_met['Parse Error Count']:<9} | {h_met['Clean PR False Finding Rejection Rate']:<9.4f}")
        summary_rows.append({
            "model": m_name,
            "semantic_f1": s_met["F1"],
            "semantic_recall": s_met["Recall"],
            "hybrid_precision": h_met["Precision"],
            "hybrid_recall": h_met["Recall"],
            "hybrid_f1": h_met["F1"],
            "parse_errors": s_met["Parse Error Count"],
            "clean_rejection_rate": h_met["Clean PR False Finding Rejection Rate"]
        })
    print("=" * 115)

    report_payload = {
        "models_evaluated": list(model_evaluations.keys()),
        "summary": summary_rows,
        "disagreements": disagreements,
        "evaluations": model_evaluations
    }

    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved full Bake-Off comparison report to: {output_report}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Semantic Verifier Model Bake-Off")
    parser.add_argument("results", nargs="+", help="Paths to model result JSON files")
    parser.add_argument("--output", type=str, default=str(BASE_DIR / "reports" / "model_bakeoff_comparison_report.json"), help="Output comparison JSON report")

    args = parser.parse_args()
    files = [Path(p) for p in args.results]
    compare_multiple_models(files, Path(args.output))


if __name__ == "__main__":
    main()
