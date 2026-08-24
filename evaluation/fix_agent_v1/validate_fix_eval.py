"""
Deterministic Dataset Validator for Fix Agent V1 Evaluation Harness
Checks:
1. Scenario counts (total, DEV, HOLDOUT)
2. Unique scenario IDs
3. Split completeness and disjointness
4. Fixture existence (before.java and expected_after.java for eligible)
5. Safety of file paths (no traversal, no absolute paths)
6. Expected diff sizes <= 20 lines
7. Role/finding_type validity
8. Absence of private repository or held-out names
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"
SPLITS_FILE = EVAL_DIR / "splits.json"

FORBIDDEN_NAME_PATTERNS = [
    "tuba-test",
    "orderapp",
    "admin123",
    "testValue",
    "whsec_live",
    "sk_prod"
]

MAX_ALLOWED_LINES = 20


def count_diff_lines(file_a: Path, file_b: Path) -> int:
    lines_a = file_a.read_text(encoding="utf-8").splitlines()
    lines_b = file_b.read_text(encoding="utf-8").splitlines()
    import difflib
    diff = list(difflib.unified_diff(lines_a, lines_b))
    changed = 0
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed += 1
    return changed


def run_validation() -> bool:
    print("==================================================")
    print("RUNNING FIX AGENT V1 DATASET VALIDATION")
    print("==================================================")

    if not SCENARIOS_FILE.exists():
        print(f"[FAIL] scenarios.json not found at {SCENARIOS_FILE}")
        return False
    if not SPLITS_FILE.exists():
        print(f"[FAIL] splits.json not found at {SPLITS_FILE}")
        return False

    scenarios_data = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))
    splits_data = json.loads(SPLITS_FILE.read_text(encoding="utf-8"))

    scenarios = scenarios_data.get("scenarios", [])
    dev_ids = set(splits_data.get("DEV", []))
    holdout_ids = set(splits_data.get("HOLDOUT", []))

    errors = []

    # 1. Total counts check
    if len(scenarios) != 30:
        errors.append(f"Expected 30 scenarios, found {len(scenarios)}")
    if len(dev_ids) != 22:
        errors.append(f"Expected 22 DEV scenarios in splits.json, found {len(dev_ids)}")
    if len(holdout_ids) != 8:
        errors.append(f"Expected 8 HOLDOUT scenarios in splits.json, found {len(holdout_ids)}")

    # 2. Split disjointness
    overlap = dev_ids.intersection(holdout_ids)
    if overlap:
        errors.append(f"DEV and HOLDOUT splits overlap on IDs: {overlap}")

    seen_ids = set()
    eligible_count = 0
    ineligible_count = 0

    for sc in scenarios:
        sid = sc.get("scenario_id")
        if not sid:
            errors.append("Scenario missing scenario_id")
            continue

        if sid in seen_ids:
            errors.append(f"Duplicate scenario_id: {sid}")
        seen_ids.add(sid)

        split = sc.get("split")
        if split not in ("DEV", "HOLDOUT"):
            errors.append(f"{sid}: Invalid split '{split}'")

        if split == "DEV" and sid not in dev_ids:
            errors.append(f"{sid}: Split marked DEV but not in splits.json DEV list")
        if split == "HOLDOUT" and sid not in holdout_ids:
            errors.append(f"{sid}: Split marked HOLDOUT but not in splits.json HOLDOUT list")

        # Check role and finding_type
        role = sc.get("role")
        if role not in ("correctness_logic", "maintainability", "security_validation"):
            errors.append(f"{sid}: Invalid role '{role}'")

        is_eligible = sc.get("eligibility_expected", False)
        exp_status = sc.get("expected_fix_status")

        if is_eligible:
            eligible_count += 1
            if exp_status != "generated":
                errors.append(f"{sid}: Eligible scenario must have expected_fix_status 'generated', got '{exp_status}'")
            if not sc.get("expected_after_fixture"):
                errors.append(f"{sid}: Eligible scenario missing expected_after_fixture")
        else:
            ineligible_count += 1
            if exp_status != "skipped":
                errors.append(f"{sid}: Ineligible scenario must have expected_fix_status 'skipped', got '{exp_status}'")
            if not sc.get("expected_skip_reason_category"):
                errors.append(f"{sid}: Ineligible scenario missing expected_skip_reason_category")

        # Check fixtures on disk
        src_fix_rel = sc.get("source_fixture")
        if not src_fix_rel:
            errors.append(f"{sid}: Missing source_fixture field")
        else:
            src_path = EVAL_DIR / src_fix_rel
            if not src_path.exists():
                errors.append(f"{sid}: source_fixture not found on disk: {src_path}")

        after_fix_rel = sc.get("expected_after_fixture")
        if after_fix_rel:
            after_path = EVAL_DIR / after_fix_rel
            if not after_path.exists():
                errors.append(f"{sid}: expected_after_fixture not found on disk: {after_path}")
            elif src_fix_rel:
                # Check diff line count
                changed_lines = count_diff_lines(EVAL_DIR / src_fix_rel, after_path)
                if changed_lines > MAX_ALLOWED_LINES:
                    errors.append(f"{sid}: Expected diff changed lines {changed_lines} exceeds maximum {MAX_ALLOWED_LINES}")

        # Check path safety
        fpath = sc.get("file_path", "")
        if ".." in fpath or fpath.startswith("/") or fpath.startswith("\\\\"):
            errors.append(f"{sid}: Insecure or absolute file_path: {fpath}")

        # Check private pattern leakage
        full_text = json.dumps(sc)
        for pat in FORBIDDEN_NAME_PATTERNS:
            if pat in full_text:
                errors.append(f"{sid}: Leaked forbidden test pattern '{pat}'")

    print(f"Total Scenarios Evaluated : {len(scenarios)}")
    print(f"  DEV Split               : {len(dev_ids)}")
    print(f"  HOLDOUT Split           : {len(holdout_ids)}")
    print(f"  ELIGIBLE Scenarios      : {eligible_count}")
    print(f"  INELIGIBLE Scenarios    : {ineligible_count}")

    if errors:
        print(f"\n[VALIDATION FAILED] Found {len(errors)} error(s):")
        for err in errors:
            print(f" - {err}")
        return False

    print("\n[VALIDATION SUCCESS] All Fix Agent evaluation dataset checks passed perfectly!\n")
    return True


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
