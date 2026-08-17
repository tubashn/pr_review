import json
import sys
from pathlib import Path
from collections import Counter


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    train_path = script_dir / "lora_train.jsonl"
    val_path = script_dir / "lora_validation.jsonl"
    catalog_path = script_dir / "scenario_catalog.json"

    if not train_path.exists() or not val_path.exists() or not catalog_path.exists():
        print("Error: Missing catalog or dataset files. Please run build_lora_dataset.py first.", file=sys.stderr)
        sys.exit(1)

    # Load catalog for scenario configuration verification
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    catalog_map = {sc["source_scenario_id"]: sc for sc in catalog}

    # Load all samples
    samples = []
    for path in [train_path, val_path]:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))

    failed = False
    fail_reasons = []

    def fail(reason: str):
        nonlocal failed
        failed = True
        fail_reasons.append(reason)

    # 1. Tam olarak 48 unique source_scenario_id var mı?
    unique_scids = set(s["source_scenario_id"] for s in samples)
    if len(unique_scids) != 48:
        fail(f"Unique source_scenario_id count is {len(unique_scids)}, expected exactly 48.")

    # 2. Her scenario için tam olarak 3 reviewer sample var mı?
    scid_counts = Counter(s["source_scenario_id"] for s in samples)
    for scid, count in scid_counts.items():
        if count != 3:
            fail(f"Scenario '{scid}' has {count} samples, expected exactly 3.")

    # 3. Toplam tam olarak 144 sample var mı?
    if len(samples) != 144:
        fail(f"Total sample count is {len(samples)}, expected exactly 144.")

    # 4. Reviewer isimleri validation
    valid_reviewers = {"correctness_logic", "security_validation", "maintainability"}
    for s in samples:
        rev = s.get("reviewer")
        if rev not in valid_reviewers:
            fail(f"Invalid reviewer name '{rev}' in sample '{s.get('id')}'")

    # 5, 6, 7, 11, 12. Reviewer outputs, JSON parsing and findings fields validation
    for s in samples:
        scid = s["source_scenario_id"]
        rev = s["reviewer"]
        sc = catalog_map.get(scid)
        
        if not sc:
            fail(f"Sample '{s.get('id')}' references missing catalog scenario '{scid}'")
            continue

        intended = sc.get("intended_reviewer")
        
        # Extract assistant message
        messages = s.get("messages", [])
        assistant_msg = next((m for m in messages if m.get("role") == "assistant"), None)
        if not assistant_msg:
            fail(f"Sample '{s.get('id')}' is missing assistant message.")
            continue

        raw_content = assistant_msg.get("content", "")
        # 11. Parseable JSON check
        try:
            parsed = json.loads(raw_content)
        except Exception as e:
            fail(f"Sample '{s.get('id')}' assistant content is not valid JSON: {e}")
            continue

        if not isinstance(parsed, dict) or "findings" not in parsed:
            fail(f"Sample '{s.get('id')}' assistant output missing 'findings' or not a dict.")
            continue

        findings = parsed.get("findings", [])
        
        # 5, 6. Intended vs other reviewer check
        if intended != "none" and rev == intended:
            if len(findings) == 0:
                fail(f"Intended reviewer '{rev}' has empty findings list on scenario '{scid}'")
        else:
            # 6, 7. Other reviewers or clean scenario must have empty findings list
            if len(findings) > 0:
                fail(f"Reviewer '{rev}' has findings but intended reviewer is '{intended}' on scenario '{scid}'")

        # 12. Verify finding fields if not empty
        for f in findings:
            for field in ["file", "line", "certainty", "problem", "failure_scenario", "suggested_fix"]:
                if field not in f or f[field] is None:
                    fail(f"Finding in sample '{s.get('id')}' is missing required field '{field}'")

    # 8. Aynı source_scenario_id hem train hem validation'da bulunuyor mu?
    train_samples = [s for s in samples if s["split"] == "train"]
    val_samples = [s for s in samples if s["split"] == "validation"]
    train_scids = set(s["source_scenario_id"] for s in train_samples)
    val_scids = set(s["source_scenario_id"] for s in val_samples)
    overlap = train_scids.intersection(val_scids)
    if overlap:
        fail(f"Split leak detected: Scenarios {overlap} are present in both train and validation splits.")

    # 9. Held-out test branch isimleri leak kontrolü
    held_out_branches = [
        "tuba-test",
        "tuba-test-hardcoded-secret",
        "tuba-test-redundant-boolean",
        "tuba-test-unclosed-resource",
        "tuba-test-clean-change"
    ]
    for s in samples:
        raw_str = json.dumps(s)
        for br in held_out_branches:
            if br in raw_str:
                fail(f"Held-out test branch '{br}' leaked into sample '{s.get('id')}'")

    # 10. Held-out test file/class isimleri leak kontrolü
    held_out_files = [
        "OrderServiceImpl.java",
        "CredentialValidator.java",
        "BooleanValidator.java",
        "FileReaderUtil.java",
        "StringHelper.java"
    ]
    for s in samples:
        raw_str = json.dumps(s)
        for filename in held_out_files:
            if filename in raw_str:
                fail(f"Held-out file/class '{filename}' leaked into sample '{s.get('id')}'")

    # 13. Diff ve context boş mu?
    for sc in catalog:
        if not sc.get("pr_diff") or not sc.get("pr_diff").strip():
            fail(f"Scenario '{sc['source_scenario_id']}' has empty 'pr_diff'")
        if not sc.get("context") or not sc.get("context").strip():
            fail(f"Scenario '{sc['source_scenario_id']}' has empty 'context'")

    # Report results
    print("\n=========================================")
    print("DATASET VALIDATION REPORT")
    print("=========================================")
    if failed:
        print("Status: FAILED")
        for reason in fail_reasons:
            print(f"  - {reason}")
        sys.exit(1)
    else:
        print("Status: PASSED")

    # 14. Train/validation split distribution
    print("\nSplit Distribution:")
    print(f"  Train: {len(train_samples)} samples ({len(train_samples) // 3} scenarios)")
    print(f"  Validation: {len(val_samples)} samples ({len(val_samples) // 3} scenarios)")

    # 15. Reviewer-based positive/negative counts
    print("\nReviewer-based Positive/Negative Counts:")
    for rev in sorted(valid_reviewers):
        rev_samples = [s for s in samples if s["reviewer"] == rev]
        pos = sum(1 for s in rev_samples if len(json.loads(s["messages"][-1]["content"])["findings"]) > 0)
        neg = sum(1 for s in rev_samples if len(json.loads(s["messages"][-1]["content"])["findings"]) == 0)
        print(f"  {rev:<25} - Positive: {pos:<3} | Negative: {neg:<3}")

    # Counts from catalog
    clean_count = sum(1 for sc in catalog if sc["intended_reviewer"] == "none")
    print(f"\nClean Scenarios Count: {clean_count}")
    
    total_neg_samples = sum(1 for s in samples if len(json.loads(s["messages"][-1]["content"])["findings"]) == 0)
    print(f"Total Negative (findings: []) samples count: {total_neg_samples}")

    # 16. Category distribution
    categories = Counter(sc["scenario_category"] for sc in catalog)
    print("\nCategory Distribution:")
    for cat, count in categories.items():
        print(f"  {cat:<30}: {count} scenarios")

    # 17. Difficulty distribution
    difficulties = Counter(sc["difficulty"] for sc in catalog)
    print("\nDifficulty Distribution:")
    for diff, count in difficulties.items():
        print(f"  {diff:<10}: {count} scenarios")


if __name__ == "__main__":
    main()
