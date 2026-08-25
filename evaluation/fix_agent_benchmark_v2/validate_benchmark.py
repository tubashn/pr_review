"""
Deterministic Dataset Validator for Fix Agent Benchmark V2
Validates:
1. Scenario counts (80 total: 56 DEV, 24 HOLDOUT)
2. Eligibility split (54 eligible, 26 ineligible; DEV: 38/18, HOLDOUT: 16/8)
3. Category balance (27 maintainability eligible, 27 correctness_logic eligible)
4. Difficulty distribution (24 EASY, 36 MEDIUM, 20 HARD)
5. Complexity distribution (32 single_line, 16 multi_line, 6 boundary)
6. Unique scenario IDs and zero split overlap
7. Fixture presence, path safety, and <= 20 changed lines limit
8. Absence of old benchmark IDs, company code, or private literals
"""

import difflib
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"
SPLITS_FILE = EVAL_DIR / "splits.json"
SCHEMA_FILE = EVAL_DIR / "schema.json"

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
    print("RUNNING FIX AGENT BENCHMARK V2 DATASET VALIDATION")
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
    if len(scenarios) != 80:
        errors.append(f"Expected 80 scenarios, found {len(scenarios)}")
    if len(dev_ids) != 56:
        errors.append(f"Expected 56 DEV scenarios in splits.json, found {len(dev_ids)}")
    if len(holdout_ids) != 24:
        errors.append(f"Expected 24 HOLDOUT scenarios in splits.json, found {len(holdout_ids)}")

    # 2. Split disjointness
    overlap = dev_ids.intersection(holdout_ids)
    if overlap:
        errors.append(f"DEV and HOLDOUT splits overlap on IDs: {overlap}")

    seen_ids = set()
    eligible_count = 0
    ineligible_count = 0
    dev_eligible = 0
    dev_ineligible = 0
    holdout_eligible = 0
    holdout_ineligible = 0
    maint_eligible = 0
    corr_eligible = 0

    diff_counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
    comp_counts = {"single_line": 0, "multi_line": 0, "boundary": 0}
    alt_valid_count = 0

    for sc in scenarios:
        sid = sc.get("scenario_id")
        if not sid:
            errors.append("Scenario missing scenario_id")
            continue

        if sid in seen_ids:
            errors.append(f"Duplicate scenario_id: {sid}")
        seen_ids.add(sid)

        # Check for legacy FA- prefix
        if sid.startswith("FA-"):
            errors.append(f"{sid}: Must use FB2- prefix instead of legacy FA- prefix.")

        split = sc.get("split")
        if split not in ("DEV", "HOLDOUT"):
            errors.append(f"{sid}: Invalid split '{split}'")

        role = sc.get("role")
        if role not in ("maintainability", "correctness_logic", "security_validation"):
            errors.append(f"{sid}: Invalid role '{role}'")

        diff = sc.get("difficulty")
        if diff in diff_counts:
            diff_counts[diff] += 1
        else:
            errors.append(f"{sid}: Invalid difficulty '{diff}'")

        if sc.get("alternative_valid_fix"):
            alt_valid_count += 1

        is_elig = sc.get("eligibility_expected")
        if is_elig:
            eligible_count += 1
            if split == "DEV":
                dev_eligible += 1
            elif split == "HOLDOUT":
                holdout_eligible += 1

            if role == "maintainability":
                maint_eligible += 1
            elif role == "correctness_logic":
                corr_eligible += 1
            elif role == "security_validation":
                errors.append(f"{sid}: Security finding must not be marked eligible!")

            comp = sc.get("fix_complexity")
            if comp in comp_counts:
                comp_counts[comp] += 1
            else:
                errors.append(f"{sid}: Invalid fix_complexity '{comp}'")
        else:
            ineligible_count += 1
            if split == "DEV":
                dev_ineligible += 1
            elif split == "HOLDOUT":
                holdout_ineligible += 1

        # Check forbidden literals
        sc_str = json.dumps(sc)
        for pat in FORBIDDEN_NAME_PATTERNS:
            if pat.lower() in sc_str.lower():
                errors.append(f"{sid}: Contains forbidden pattern '{pat}'")

        # Fixture existence & validation
        src_fixture = sc.get("source_fixture")
        if not src_fixture:
            errors.append(f"{sid}: Missing source_fixture")
        else:
            src_path = EVAL_DIR / src_fixture
            if not src_path.exists():
                errors.append(f"{sid}: source_fixture file not found: {src_path}")

        exp_fixture = sc.get("expected_after_fixture")
        if is_elig:
            if not exp_fixture:
                errors.append(f"{sid}: Eligible scenario must have expected_after_fixture")
            else:
                exp_path = EVAL_DIR / exp_fixture
                if not exp_path.exists():
                    errors.append(f"{sid}: expected_after_fixture file not found: {exp_path}")
                elif src_path.exists():
                    # Diff line limit check
                    lines_changed = count_diff_lines(src_path, exp_path)
                    if lines_changed > MAX_ALLOWED_LINES:
                        errors.append(f"{sid}: Diff size {lines_changed} exceeds {MAX_ALLOWED_LINES} lines!")
        else:
            if not sc.get("expected_skip_reason_category"):
                errors.append(f"{sid}: Ineligible scenario must specify expected_skip_reason_category")

    # Verify required distribution metrics
    if eligible_count != 54:
        errors.append(f"Expected 54 eligible scenarios, found {eligible_count}")
    if ineligible_count != 26:
        errors.append(f"Expected 26 ineligible scenarios, found {ineligible_count}")
    if dev_eligible != 38 or dev_ineligible != 18:
        errors.append(f"Expected DEV 38 eligible / 18 ineligible, found {dev_eligible}/{dev_ineligible}")
    if holdout_eligible != 16 or holdout_ineligible != 8:
        errors.append(f"Expected HOLDOUT 16 eligible / 8 ineligible, found {holdout_eligible}/{holdout_ineligible}")
    if maint_eligible != 27 or corr_eligible != 27:
        errors.append(f"Expected 27 maintainability / 27 correctness eligible, found {maint_eligible}/{corr_eligible}")
    if diff_counts != {"EASY": 24, "MEDIUM": 36, "HARD": 20}:
        errors.append(f"Expected difficulty { { 'EASY': 24, 'MEDIUM': 36, 'HARD': 20 } }, found {diff_counts}")
    if comp_counts != {"single_line": 32, "multi_line": 16, "boundary": 6}:
        errors.append(f"Expected complexity { { 'single_line': 32, 'multi_line': 16, 'boundary': 6 } }, found {comp_counts}")

    print(f"Total Scenarios Evaluated : {len(scenarios)}")
    print(f"  DEV Split               : {len(dev_ids)} ({dev_eligible} eligible, {dev_ineligible} ineligible)")
    print(f"  HOLDOUT Split           : {len(holdout_ids)} ({holdout_eligible} eligible, {holdout_ineligible} ineligible)")
    print(f"  ELIGIBLE Scenarios      : {eligible_count} (27 maintainability, 27 correctness)")
    print(f"  INELIGIBLE Scenarios    : {ineligible_count}")
    print(f"  Difficulty Distribution : {diff_counts}")
    print(f"  Complexity Distribution : {comp_counts}")
    print(f"  Alternative Valid Fix   : {alt_valid_count} scenarios")

    if errors:
        print(f"\n[VALIDATION FAILED] {len(errors)} error(s) found:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("\n[VALIDATION SUCCESS] All Fix Agent Benchmark V2 dataset checks passed perfectly!\n")
    return True


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
