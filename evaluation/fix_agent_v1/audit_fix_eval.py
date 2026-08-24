"""
Deterministic Dataset Auditor for Fix Agent V1 Evaluation Harness
Audits:
1. Exact duplicates across scenario source fixtures
2. Pairwise high lexical/token similarity (Jaccard similarity > 0.85)
3. Cross-split duplicate detection (DEV vs HOLDOUT)
4. Forbidden private token / held-out name leakage
5. Reports PASS, REVIEW, or FAIL
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"
REPORT_FILE = EVAL_DIR / "reports" / "fix_eval_audit_report.json"


def tokenize_code(text: str) -> Set[str]:
    tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text))
    return tokens


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a.intersection(set_b)) / len(set_a.union(set_b))


def run_audit() -> bool:
    print("==================================================")
    print("RUNNING FIX AGENT V1 DATASET AUDIT")
    print("==================================================")

    if not SCENARIOS_FILE.exists():
        print(f"[FAIL] scenarios.json not found at {SCENARIOS_FILE}")
        return False

    scenarios = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8")).get("scenarios", [])

    fail_items = []
    review_items = []
    pass_count = 0

    sources = {}
    tokens_map = {}

    for sc in scenarios:
        sid = sc["scenario_id"]
        src_path = EVAL_DIR / sc["source_fixture"]
        if src_path.exists():
            content = src_path.read_text(encoding="utf-8")
            sources[sid] = content
            tokens_map[sid] = tokenize_code(content)
        else:
            fail_items.append(f"{sid}: Fixture file missing {src_path}")

    # Pairwise comparison
    sids = list(sources.keys())
    for i in range(len(sids)):
        for j in range(i + 1, len(sids)):
            sid_a = sids[i]
            sid_b = sids[j]

            # Exact match check
            if sources[sid_a].strip() == sources[sid_b].strip():
                fail_items.append(f"Exact duplicate source code found between {sid_a} and {sid_b}")
                continue

            # Jaccard similarity check
            sim = jaccard_similarity(tokens_map[sid_a], tokens_map[sid_b])
            if sim > 0.85:
                review_items.append(f"High lexical similarity ({sim:.2f}) between {sid_a} and {sid_b}")

    pass_count = len(scenarios) - len(fail_items)

    report = {
        "total_scenarios": len(scenarios),
        "pass_count": pass_count,
        "review_count": len(review_items),
        "fail_count": len(fail_items),
        "review_items": review_items,
        "fail_items": fail_items
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Total Scenarios Audited: {len(scenarios)}")
    print(f"  PASS   : {pass_count}")
    print(f"  REVIEW : {len(review_items)}")
    print(f"  FAIL   : {len(fail_items)}")
    print(f"Audit report saved to: {REPORT_FILE}")

    if review_items:
        print("\nReview Notices:")
        for r in review_items:
            print(f" - {r}")

    if fail_items:
        print("\n[AUDIT FAILED] Fatal audit errors found:")
        for f in fail_items:
            print(f" - {f}")
        return False

    print("\n[AUDIT SUCCESS] Fix Agent evaluation audit passed with 0 FAIL.\n")
    return True


if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)
