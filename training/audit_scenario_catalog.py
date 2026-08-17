import json
import sys
import re
from pathlib import Path


def check_speculative(text: str) -> bool:
    if not text:
        return False
    # Look for speculative words: could potentially, might possibly, etc.
    pattern = r"\b(could potentially|might possibly|may potentially|possibly|might|could)\b"
    return bool(re.search(pattern, text.lower()))


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    catalog_path = script_dir / "scenario_catalog.json"
    report_path = script_dir / "scenario_audit_report.json"

    if not catalog_path.exists():
        print(f"Error: scenario_catalog.json not found at {catalog_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            scenarios = json.load(f)
    except Exception as e:
        print(f"Error reading scenario catalog: {e}", file=sys.stderr)
        sys.exit(1)

    audit_reports = []
    fail_count = 0
    review_count = 0
    pass_count = 0

    for sc in scenarios:
        sc_id = sc.get("source_scenario_id")
        intended = sc.get("intended_reviewer")
        category = sc.get("scenario_category")
        gt = sc.get("ground_truth_finding")
        pr_diff = sc.get("pr_diff", "")
        context = sc.get("context", "")

        status = "PASS"
        evidence_sufficient = "YES"
        changed_code_relevant = "YES"
        role_pure = "YES"
        ground_truth_valid = "YES"
        clean_valid = "YES"
        notes = []

        if intended == "none":
            # Clean scenario check
            if gt is not None:
                status = "FAIL"
                clean_valid = "NO"
                notes.append("Clean scenario has ground truth finding.")
            # Verify clean categories
            if category != "clean_change":
                status = "FAIL"
                clean_valid = "NO"
                notes.append("Clean scenario category is not clean_change.")
        else:
            if gt is None:
                status = "FAIL"
                ground_truth_valid = "NO"
                notes.append("Bug scenario missing ground truth finding.")
            else:
                # Check for speculative language
                prob = gt.get("problem", "")
                fail_sc = gt.get("failure_scenario", "")
                if check_speculative(prob) or check_speculative(fail_sc):
                    status = "REVIEW"
                    ground_truth_valid = "REVIEW"
                    notes.append("Ground truth uses speculative language (could/might/possibly).")

                # Verify file name match
                if Path(gt.get("file", "")).name.lower() != Path(sc.get("file", "")).name.lower():
                    status = "FAIL"
                    ground_truth_valid = "NO"
                    notes.append("Ground truth file name does not match scenario file name.")

                # Reviewer role check
                if intended == "correctness_logic":
                    # Check if correctness logic is indeed correctness-focused
                    correctness_categories = [
                        "null_handling", "incorrect_condition", "wrong_comparison", "incorrect_return_value",
                        "off_by_one", "missing_edge_case", "wrong_state_mutation", "incorrect_collection_handling",
                        "exception_handling", "transaction_logic", "repository_result_handling", "resource_management"
                    ]
                    if category not in correctness_categories:
                        status = "REVIEW"
                        role_pure = "REVIEW"
                        notes.append(f"Correctness scenario category '{category}' is unusual.")

                elif intended == "security_validation":
                    security_categories = [
                        "hardcoded_secret", "missing_input_validation", "injection", "path_traversal",
                        "authentication", "authorization", "sensitive_data_exposure", "insecure_configuration",
                        "unsafe_deserialization", "weak_token_validation", "missing_ownership_check", "untrusted_redirect_or_url"
                    ]
                    if category not in security_categories:
                        status = "REVIEW"
                        role_pure = "REVIEW"
                        notes.append(f"Security scenario category '{category}' is unusual.")

                elif intended == "maintainability":
                    maintainability_categories = [
                        "unused_code", "dead_code", "redundant_expression", "redundant_boolean",
                        "unnecessary_complexity", "duplicated_logic", "misleading_code", "poor_exception_structure",
                        "unnecessary_conversion", "unreachable_branch", "confusing_control_flow", "unnecessary_mutability"
                    ]
                    if category not in maintainability_categories:
                        status = "REVIEW"
                        role_pure = "REVIEW"
                        notes.append(f"Maintainability scenario category '{category}' is unusual.")

                # Evidence Sufficiency heuristics
                # 1. Unused code should be private
                if category == "unused_code" and "private" not in context:
                    status = "REVIEW"
                    evidence_sufficient = "REVIEW"
                    notes.append("Unused code is not private; difficult to verify usage outside class context.")

        if status == "FAIL":
            fail_count += 1
        elif status == "REVIEW":
            review_count += 1
        else:
            pass_count += 1

        audit_reports.append({
            "source_scenario_id": sc_id,
            "status": status,
            "evidence_sufficient": evidence_sufficient,
            "changed_code_relevant": changed_code_relevant,
            "role_pure": role_pure,
            "ground_truth_valid": ground_truth_valid,
            "clean_valid": clean_valid,
            "notes": " ".join(notes) if notes else "Looks good."
        })

    # Save report
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(audit_reports, f, indent=2, ensure_ascii=False)

    print("\n=========================================")
    print("SEMANTIC DATASET AUDIT SUMMARY")
    print("=========================================")
    print(f"Total Scenarios audited: {len(scenarios)}")
    print(f"  PASS   : {pass_count}")
    print(f"  REVIEW : {review_count}")
    print(f"  FAIL   : {fail_count}")

    if review_count > 0 or fail_count > 0:
        print("\nItems requiring review/fixes:")
        for rep in audit_reports:
            if rep["status"] != "PASS":
                print(f"  - {rep['source_scenario_id']} [{rep['status']}]: {rep['notes']}")


if __name__ == "__main__":
    main()
