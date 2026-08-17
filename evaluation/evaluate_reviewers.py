# ==============================================================================
# WARNING: TEST SET METADATA
# This file and the associated ground_truth.json constitute a static TEST SET
# designed solely for evaluating model performance.
# DO NOT INCLUDE these branches or their evaluation data in model training sets.
# ==============================================================================

import sys
import json
import re
from pathlib import Path


def clean_raw_response(raw_response: str) -> str:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    replacements = {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
        'â': 'a', 'î': 'i', 'û': 'u'
    }
    for tr, en in replacements.items():
        text = text.replace(tr, en)
    return text


def file_matches(actual_file: str, expected_file: str) -> bool:
    if not actual_file or not expected_file:
        return False
    actual_base = Path(actual_file).name.lower()
    expected_base = Path(expected_file).name.lower()
    return actual_base == expected_base


def line_matches(actual_line: int, expected_lines: list, tolerance: int) -> bool:
    if actual_line is None:
        return False
    for exp in expected_lines:
        if abs(actual_line - exp) <= tolerance:
            return True
    return False


def concept_matches(problem_text: str, expected_concepts: list) -> bool:
    if not expected_concepts:
        return True
    norm_problem = normalize_text(problem_text)
    for group in expected_concepts:
        group_match = False
        for concept in group:
            norm_concept = normalize_text(concept)
            if norm_concept in norm_problem:
                group_match = True
                break
        if not group_match:
            return False
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: Missing results file path.", file=sys.stderr)
        print("Usage: python agent/evaluation/evaluate_reviewers.py <results-file>", file=sys.stderr)
        sys.exit(1)

    results_file = Path(sys.argv[1]).resolve()
    
    # Requirement 13: Print at the very beginning
    print(f"Evaluating results file: {results_file}")

    if not results_file.exists():
        print(f"Error: Results file '{results_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    gt_file = script_dir / "ground_truth.json"
    report_file = script_dir / "evaluation_report.json"

    # Read ground truth
    try:
        with open(gt_file, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
    except Exception as e:
        print(f"Error reading ground truth file: {e}", file=sys.stderr)
        sys.exit(1)

    branches_gt = gt_data.get("branches", {})

    # Read results
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception as e:
        print(f"Error reading results file: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(results, list):
        print("Error: Results file must be a JSON list.", file=sys.stderr)
        sys.exit(1)

    # Map results and validate keys
    results_map = {}
    for idx, r in enumerate(results):
        if not all(k in r for k in ["branch", "reviewer", "raw_response"]):
            print(f"Error: Record at index {idx} is missing required fields ('branch', 'reviewer', 'raw_response').", file=sys.stderr)
            sys.exit(1)
        branch = r.get("branch")
        reviewer = r.get("reviewer")
        raw = r.get("raw_response")
        results_map[(branch, reviewer)] = raw

    tp = 0
    fp = 0
    fn = 0
    tn = 0
    clean_pr_fp = 0
    role_leakage_count = 0
    parse_error_count = 0

    evaluation_details = []
    leakage_details = []

    all_branches = [
        "tuba-test",
        "tuba-test-hardcoded-secret",
        "tuba-test-redundant-boolean",
        "tuba-test-unclosed-resource",
        "tuba-test-clean-change"
    ]
    all_reviewers = ["correctness_logic", "security_validation", "maintainability"]

    for branch in all_branches:
        for reviewer in all_reviewers:
            gt_finding = branches_gt.get(branch, {}).get(reviewer)
            raw_response = results_map.get((branch, reviewer))

            if raw_response is None:
                parse_error = "No response found in results file."
                findings_list = []
                has_finding = False
                parse_error_count += 1
                print(f"\nParse Error on Branch: {branch}, Reviewer: {reviewer}")
                print("raw_response is missing/None.")
            else:
                parse_error = None
                try:
                    cleaned = clean_raw_response(raw_response)
                    parsed = json.loads(cleaned)
                    findings_list = parsed.get("findings", []) if isinstance(parsed, dict) else []
                    has_finding = len(findings_list) > 0
                except Exception as e:
                    parse_error = str(e)
                    findings_list = []
                    has_finding = False
                    parse_error_count += 1
                    print(f"\nParse Error on Branch: {branch}, Reviewer: {reviewer}")
                    print(f"Error Details: {parse_error}")
                    print("raw_response value:")
                    print(raw_response)

            # Print debug info
            print(f"Branch: {branch}")
            print(f"Reviewer: {reviewer}")
            if parse_error:
                print("Parsed findings count: ERROR")
                print(f"Parsed findings: [PARSE ERROR: {parse_error}]")
            else:
                print(f"Parsed findings count: {len(findings_list)}")
                print(f"Parsed findings: {json.dumps(findings_list, ensure_ascii=False)}")

            status = "TN"
            detail = ""

            if parse_error:
                if gt_finding is not None:
                    status = "FN"
                    fn += 1
                    detail = f"Parse error ({parse_error}) while expecting a finding."
                else:
                    status = "FP"
                    fp += 1
                    detail = f"Parse error ({parse_error}) while expecting no findings."
            else:
                if gt_finding is not None:
                    expected_file = gt_finding.get("expected_file")
                    expected_lines = gt_finding.get("expected_lines", [])
                    tolerance = gt_finding.get("line_tolerance", 0)
                    expected_concepts = gt_finding.get("expected_concepts", [])

                    if not has_finding:
                        status = "FN"
                        fn += 1
                        detail = "No findings generated, but an issue was expected."
                    else:
                        matched = False
                        for f in findings_list:
                            file_name = f.get("file", "")
                            line_num = f.get("line")
                            problem = f.get("problem", "")

                            file_match = file_matches(file_name, expected_file)
                            line_match = line_matches(line_num, expected_lines, tolerance)
                            concept_match = concept_matches(problem, expected_concepts)

                            if file_match and line_match and concept_match:
                                matched = True
                                break

                        if matched:
                            status = "TP"
                            tp += 1
                            detail = "Found expected issue."
                        else:
                            status = "FP+FN"
                            fp += 1
                            fn += 1
                            detail = "Found findings, but did not match expected criteria."
                else:
                    if has_finding:
                        # Check for role leakage using same concept match
                        is_leakage = False
                        matched_role = None
                        for other_reviewer in all_reviewers:
                            if other_reviewer == reviewer:
                                continue
                            other_gt = branches_gt.get(branch, {}).get(other_reviewer)
                            if other_gt is not None:
                                expected_file = other_gt.get("expected_file")
                                expected_lines = other_gt.get("expected_lines", [])
                                tolerance = other_gt.get("line_tolerance", 0)
                                expected_concepts = other_gt.get("expected_concepts", [])

                                for f in findings_list:
                                    file_name = f.get("file", "")
                                    line_num = f.get("line")
                                    problem = f.get("problem", "")

                                    file_match = file_matches(file_name, expected_file)
                                    line_match = line_matches(line_num, expected_lines, tolerance)
                                    concept_match = concept_matches(problem, expected_concepts)

                                    if file_match and line_match and concept_match:
                                        is_leakage = True
                                        matched_role = other_reviewer
                                        break

                        status = "FP"
                        fp += 1
                        if is_leakage:
                            role_leakage_count += 1
                            detail = f"Role Leakage! Found finding expected for {matched_role}."
                            leakage_details.append({
                                "branch": branch,
                                "incorrect_reviewer": reviewer,
                                "expected_reviewer": matched_role
                            })
                        else:
                            detail = "Generated unexpected findings."

                        if branch == "tuba-test-clean-change":
                            clean_pr_fp += 1
                    else:
                        status = "TN"
                        tn += 1
                        detail = "No findings generated, as expected."

            evaluation_details.append({
                "branch": branch,
                "reviewer": reviewer,
                "expected": gt_finding is not None,
                "found": has_finding,
                "status": status,
                "detail": detail,
                "parse_error": parse_error
            })

    # Calculations
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    metrics = {
        "True Positive": tp,
        "False Positive": fp,
        "False Negative": fn,
        "True Negative": tn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
        "Clean PR false positive count": clean_pr_fp,
        "Reviewer role leakage count": role_leakage_count,
        "Parse error count": parse_error_count
    }

    report = {
        "metadata": {
            "purpose": "TEST SET EVALUATION REPORT - DO NOT INCLUDE IN TRAINING DATA",
            "evaluated_results_file": str(results_file)
        },
        "evaluated_results_file": str(results_file),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "clean_pr_false_positive_count": clean_pr_fp,
        "reviewer_role_leakage_count": role_leakage_count,
        "parse_error_count": parse_error_count,
        "detailed_results": evaluation_details,
        "leakage_details": leakage_details
    }

    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing report: {e}", file=sys.stderr)

    # Print role leakage details (Requirement 13)
    if leakage_details:
        print("\n=========================================")
        print("ROLE LEAKAGE DETAILS")
        print("=========================================")
        for ld in leakage_details:
            print(f"Branch '{ld['branch']}': Reviewer '{ld['incorrect_reviewer']}' incorrectly reported a finding expected for '{ld['expected_reviewer']}'.")

    # Print summary metrics to console
    print("\n=========================================")
    print("EVALUATION METRICS SUMMARY")
    print("=========================================")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"{k:<30}: {v:.4f}")
        else:
            print(f"{k:<30}: {v}")

    # Print detailed table to console
    print("\n==========================================================================")
    print(f"{'Branch':<30} | {'Reviewer':<20} | {'Status':<7} | {'Detail'}")
    print("==========================================================================")
    for detail in evaluation_details:
        print(f"{detail['branch']:<30} | {detail['reviewer']:<20} | {detail['status']:<7} | {detail['detail']}")


if __name__ == "__main__":
    main()
