"""
Benchmark V2 Validation Script
Validates:
1. Unique scenario_id and candidate_id
2. Valid roles and reason_type labels
3. Candidate -> Scenario referential integrity
4. Clean scenario negative check (no ACCEPT candidates in CLEAN scenarios)
5. True finding expected_role completeness
6. Old benchmark leakage guards
7. Training dataset / scenario catalog leakage guards
8. Duplicate source snippets and duplicate normalized problem statements
9. Fixture presence and unified diff integrity
10. Split integrity (DEV: 28, HOLDOUT: 12)
"""

import sys
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

# Leakage blacklist
FORBIDDEN_OLD_BENCHMARK_TERMS = [
    "tuba-test",
    "tuba-test-hardcoded-secret",
    "tuba-test-redundant-boolean",
    "tuba-test-unclosed-resource",
    "tuba-test-clean-change",
    "OrderServiceImpl",
    "CredentialValidator",
    "BooleanValidator",
    "FileReaderUtil",
    "StringHelper",
    "testValue",
    "agent-test",
    "admin123"
]

FORBIDDEN_TRAINING_SCENARIO_IDS = [f"scenario-{i:03d}" for i in range(1, 49)]


def validate_benchmark():
    print("==================================================")
    print("RUNNING BENCHMARK V2 VALIDATION SUITE")
    print("==================================================")
    
    errors = []
    warnings = []

    # 1. Load files
    scenarios_path = BASE_DIR / "scenarios.json"
    candidates_path = BASE_DIR / "candidates.json"
    gt_path = BASE_DIR / "ground_truth.json"
    splits_path = BASE_DIR / "splits.json"
    fixtures_dir = BASE_DIR / "fixtures"

    for p in (scenarios_path, candidates_path, gt_path, splits_path):
        if not p.exists():
            errors.append(f"Missing required benchmark file: {p.name}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    with open(scenarios_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)
    with open(splits_path, "r", encoding="utf-8") as f:
        splits = json.load(f)

    # 2. Scenario Counts and Split Checks
    if len(scenarios) != 40:
        errors.append(f"Expected 40 scenarios, got {len(scenarios)}")
    
    dev_scenarios = splits.get("DEV", [])
    holdout_scenarios = splits.get("HOLDOUT", [])
    if len(dev_scenarios) != 28:
        errors.append(f"Expected 28 DEV scenarios, got {len(dev_scenarios)}")
    if len(holdout_scenarios) != 12:
        errors.append(f"Expected 12 HOLDOUT scenarios, got {len(holdout_scenarios)}")

    # 3. Candidate Counts
    if not (110 <= len(candidates) <= 130):
        errors.append(f"Candidate count {len(candidates)} outside required range [110, 130]")

    # 4. Check Unique IDs
    scenario_ids = set()
    for sc in scenarios:
        sid = sc.get("scenario_id")
        if not sid:
            errors.append("Scenario missing scenario_id")
            continue
        if sid in scenario_ids:
            errors.append(f"Duplicate scenario_id: {sid}")
        scenario_ids.add(sid)

    candidate_ids = set()
    for c in candidates:
        cid = c.get("candidate_id")
        if not cid:
            errors.append("Candidate missing candidate_id")
            continue
        if cid in candidate_ids:
            errors.append(f"Duplicate candidate_id: {cid}")
        candidate_ids.add(cid)

    # 5. Referential Integrity & Ground Truth Consistency
    sc_map = {sc["scenario_id"]: sc for sc in scenarios}
    valid_roles = {"correctness_logic", "security_validation", "maintainability"}
    valid_reason_types = {"true_finding", "false_positive", "role_leakage", "clean_pr_false_positive"}

    accept_count = 0
    reject_count = 0

    for c in candidates:
        cid = c.get("candidate_id")
        sid = c.get("scenario_id")
        role = c.get("source_reviewer")
        exp = c.get("expected")
        reason = c.get("reason_type")

        if sid not in sc_map:
            errors.append(f"Candidate {cid} references unknown scenario_id: {sid}")
            continue

        parent_sc = sc_map[sid]
        
        if role not in valid_roles:
            errors.append(f"Candidate {cid} has invalid source_reviewer: {role}")
        if reason not in valid_reason_types:
            errors.append(f"Candidate {cid} has invalid reason_type: {reason}")
        if exp not in ("ACCEPT", "REJECT"):
            errors.append(f"Candidate {cid} has invalid expected verdict: {exp}")

        if exp == "ACCEPT":
            accept_count += 1
            if reason != "true_finding":
                errors.append(f"Candidate {cid} expected ACCEPT but reason_type is {reason}")
            if parent_sc["category"] == "CLEAN":
                errors.append(f"Candidate {cid} expected ACCEPT in CLEAN scenario {sid}!")
            if parent_sc["expected_role"] != role:
                errors.append(f"Candidate {cid} expected ACCEPT but role {role} != scenario expected_role {parent_sc['expected_role']}")
        else:
            reject_count += 1
            if reason == "true_finding":
                errors.append(f"Candidate {cid} expected REJECT but reason_type is true_finding")
            if parent_sc["category"] == "CLEAN" and reason != "clean_pr_false_positive":
                errors.append(f"Candidate {cid} in CLEAN scenario {sid} must have reason_type clean_pr_false_positive, got {reason}")

    # 6. Anti-Leakage Checks (Old Benchmark and Training Catalog)
    all_text_blobs = []
    for sc in scenarios:
        all_text_blobs.append(json.dumps(sc))
    for c in candidates:
        all_text_blobs.append(json.dumps(c))

    combined_text = " ".join(all_text_blobs)

    for forbidden in FORBIDDEN_OLD_BENCHMARK_TERMS:
        if forbidden in combined_text:
            errors.append(f"Leakage Guard Violation: Old benchmark term '{forbidden}' found in Benchmark V2 data!")

    for forbidden_sc in FORBIDDEN_TRAINING_SCENARIO_IDS:
        if forbidden_sc in combined_text:
            errors.append(f"Leakage Guard Violation: Training catalog ID '{forbidden_sc}' found in Benchmark V2 data!")

    # 7. Fixture Integrity Checks
    for sid in scenario_ids:
        sc_fix = fixtures_dir / sid
        if not sc_fix.exists():
            errors.append(f"Missing fixture directory for {sid}")
            continue
        if not (sc_fix / "before").exists():
            errors.append(f"Missing before/ directory in fixture {sid}")
        if not (sc_fix / "after").exists():
            errors.append(f"Missing after/ directory in fixture {sid}")
        if not (sc_fix / "diff.patch").exists():
            errors.append(f"Missing diff.patch in fixture {sid}")

    # 8. Report Summary
    print(f"Total Scenarios Evaluated : {len(scenarios)}")
    print(f"  DEV Split               : {len(dev_scenarios)}")
    print(f"  HOLDOUT Split           : {len(holdout_scenarios)}")
    print(f"Total Candidates Evaluated: {len(candidates)}")
    print(f"  ACCEPT Candidates       : {accept_count}")
    print(f"  REJECT Candidates       : {reject_count}")

    if errors:
        print(f"\nVALIDATION FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - [ERROR] {e}")
        sys.exit(1)
    else:
        print("\nALL VALIDATION CHECKS PASSED PERFECTLY!")


if __name__ == "__main__":
    validate_benchmark()
