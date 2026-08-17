# ==============================================================================
# WARNING: TEST SET METADATA
# This file and associated verifier code constitute a static TEST SET
# designed solely for evaluating model performance.
# DO NOT INCLUDE these files or evaluation data in model training sets.
# ==============================================================================

import os
import sys
import json
import re
from pathlib import Path

# Add parent directory to sys.path to import verifier_prompt_builder
sys.path.append(str(Path(__file__).resolve().parent.parent))
from verifier_prompt_builder import VERIFIER_SYSTEM_PROMPT, build_verifier_user_prompt


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
    script_dir = Path(__file__).resolve().parent
    results_path = script_dir / "reviewer_batch_results_7b.json"
    requests_path = script_dir.parent / "reviewer_batch_requests.json"
    gt_path = script_dir / "ground_truth.json"

    # Step 1: Verify presence of all required files
    for p in [results_path, requests_path, gt_path]:
        if not p.exists():
            print(f"Error: Required file not found: {p}", file=sys.stderr)
            print("Please make sure all necessary baseline files are in place.", file=sys.stderr)
            sys.exit(1)

    # Load resources
    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    with open(requests_path, "r", encoding="utf-8") as f:
        requests_batch = json.load(f)
    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    branches_gt = gt_data.get("branches", {})

    # Map request prompts for context retrieval
    requests_map = {}
    for req in requests_batch:
        branch = req.get("branch")
        reviewer = req.get("reviewer")
        # In reviewer_batch_requests.json, the key might be "user_prompt"
        user_prompt = req.get("user_prompt", "")
        requests_map[(branch, reviewer)] = user_prompt

    verifier_candidates = []
    verifier_requests = []

    # Count statistics
    stats = {
        "total_candidates": 0,
        "expected_accept": 0,
        "expected_reject": 0,
        "role_leakage_reject": 0,
        "clean_pr_reject": 0,
        "branch_counts": {}
    }

    # Process all reviewer findings
    for record in results:
        branch = record.get("branch")
        reviewer = record.get("reviewer")
        raw_resp = record.get("raw_response", "")

        # Retrieve context user prompt (which holds the diff/context)
        pr_context = requests_map.get((branch, reviewer), "")
        if not pr_context:
            print(f"Warning: Missing context prompt for {branch}/{reviewer}")

        # Clean and parse the findings
        cleaned = clean_raw_response(raw_resp)
        try:
            parsed = json.loads(cleaned)
            findings = parsed.get("findings", []) if isinstance(parsed, dict) else []
        except Exception as e:
            print(f"Warning: Could not parse response for {branch}/{reviewer}: {e}")
            findings = []

        for idx, f in enumerate(findings):
            candidate_id = f"{branch}-{reviewer}-finding-{idx}"
            
            # Ground truth verdict logic
            expected_verdict = "REJECT"
            reason_type = "false_positive"

            if branch == "tuba-test-clean-change":
                expected_verdict = "REJECT"
                reason_type = "clean_pr_false_positive"
                stats["clean_pr_reject"] += 1
            else:
                # Check against ground truth expected findings
                branch_gt = branches_gt.get(branch, {})
                
                matched_expected_reviewer = None
                
                for r_role, expected_f in branch_gt.items():
                    if expected_f is None:
                        continue
                    
                    # Run matching checks
                    exp_file = expected_f.get("expected_file")
                    exp_lines = expected_f.get("expected_lines", [])
                    tolerance = expected_f.get("line_tolerance", 0)
                    exp_concepts = expected_f.get("expected_concepts", [])

                    file_ok = file_matches(f.get("file", ""), exp_file)
                    line_ok = line_matches(f.get("line"), exp_lines, tolerance)
                    concept_ok = concept_matches(f.get("problem", ""), exp_concepts)

                    if file_ok and line_ok and concept_ok:
                        matched_expected_reviewer = r_role
                        break

                if matched_expected_reviewer is not None:
                    if matched_expected_reviewer == reviewer:
                        expected_verdict = "ACCEPT"
                        reason_type = "true_finding"
                        stats["expected_accept"] += 1
                    else:
                        expected_verdict = "REJECT"
                        reason_type = "role_leakage"
                        stats["role_leakage_reject"] += 1
                else:
                    expected_verdict = "REJECT"
                    reason_type = "false_positive"

            if expected_verdict == "REJECT" and reason_type == "false_positive":
                stats["expected_reject"] += 1

            # Build candidate record
            candidate = {
                "candidate_id": candidate_id,
                "branch": branch,
                "source_reviewer": reviewer,
                "candidate_finding": f,
                "pr_context": pr_context,
                "expected_verdict": expected_verdict,
                "expected_reason_type": reason_type
            }
            verifier_candidates.append(candidate)

            # Build verifier request
            user_prompt = build_verifier_user_prompt(candidate_id, reviewer, f, pr_context)
            request = {
                "candidate_id": candidate_id,
                "branch": branch,
                "source_reviewer": reviewer,
                "system_prompt": VERIFIER_SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "expected_verdict": expected_verdict,
                "expected_reason_type": reason_type
            }
            verifier_requests.append(request)

            # Stats updates
            stats["total_candidates"] += 1
            stats["branch_counts"][branch] = stats["branch_counts"].get(branch, 0) + 1

    # Save outputs
    with open(script_dir / "verifier_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(verifier_candidates, f, indent=2, ensure_ascii=False)
    with open(script_dir / "verifier_requests.json", "w", encoding="utf-8") as f:
        json.dump(verifier_requests, f, indent=2, ensure_ascii=False)

    # Print summary reports
    print("\n=========================================")
    print("VERIFIER BENCHMARK GENERATED")
    print("=========================================")
    print(f"Total Individual Candidates : {stats['total_candidates']}")
    print(f"Expected ACCEPT             : {stats['expected_accept']}")
    print(f"Expected REJECT (Total)     : {stats['expected_reject'] + stats['role_leakage_reject'] + stats['clean_pr_reject']}")
    print(f"  - FP Rejection            : {stats['expected_reject']}")
    print(f"  - Role Leakage Rejection  : {stats['role_leakage_reject']}")
    print(f"  - Clean PR Rejection      : {stats['clean_pr_reject']}")
    print("\nBranch-wise Candidates:")
    for br, cnt in stats["branch_counts"].items():
        print(f"  {br:<30}: {cnt}")
    print("=========================================\n")


if __name__ == "__main__":
    main()
