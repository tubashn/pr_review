"""
Benchmark V2 Semantic Audit and Near-Duplicate Detector
Performs deep structural template analysis and code normalization
to ensure broad diversity and lack of duplicate scenarios.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPORT_FILE = BASE_DIR / "reports" / "benchmark_audit_report.json"


def normalize_code_skeleton(code: str) -> str:
    """
    Strips identifiers, string/number literals, and comments to produce
    a structural code skeleton for near-duplicate detection.
    """
    # Remove comments
    code = re.sub(r"//.*", "", code)
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    # Replace strings and numbers
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
    code = re.sub(r"'(?:\\.|[^'\\])*'", "''", code)
    code = re.sub(r"\b\d+\b", "0", code)
    # Replace Java keywords placeholder vs identifier
    keywords = {"public", "private", "protected", "static", "final", "class", "interface",
                "void", "boolean", "int", "double", "float", "long", "String", "return", "if", "else",
                "try", "catch", "finally", "throw", "throws", "new", "null", "true", "false", "import", "package"}
    
    tokens = re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b|[^\w\s]", code)
    norm_tokens = []
    for t in tokens:
        if t in keywords or not re.match(r"^[A-Za-z_$]", t):
            norm_tokens.append(t)
        else:
            norm_tokens.append("IDENT")
            
    return " ".join(norm_tokens)


def audit_benchmark():
    print("==================================================")
    print("RUNNING BENCHMARK V2 SEMANTIC AUDIT")
    print("==================================================")

    scenarios = json.load(open(BASE_DIR / "scenarios.json", encoding="utf-8"))
    candidates = json.load(open(BASE_DIR / "candidates.json", encoding="utf-8"))
    fixtures_dir = BASE_DIR / "fixtures"

    audit_records = []
    skeletons = {}
    
    pass_count = 0
    review_count = 0
    fail_count = 0

    for sc in scenarios:
        sid = sc["scenario_id"]
        cat = sc["category"]
        issue_kind = sc["issue_kind"]
        fix_dir = fixtures_dir / sid
        
        diff_file = fix_dir / "diff.patch"
        after_files = list((fix_dir / "after").glob("*.java"))
        
        status = "PASS"
        notes = []

        if not diff_file.exists():
            status = "FAIL"
            notes.append("Missing diff.patch file")
        elif not after_files:
            status = "FAIL"
            notes.append("Missing after/ Java source file")
        else:
            code_text = after_files[0].read_text(encoding="utf-8")
            skeleton = normalize_code_skeleton(code_text)
            
            if skeleton in skeletons:
                matching_sid = skeletons[skeleton]
                # If from same category with exact same skeleton
                if matching_sid != sid:
                    status = "REVIEW"
                    notes.append(f"Near-duplicate structural skeleton with {matching_sid}")
            else:
                skeletons[skeleton] = sid

        if status == "PASS":
            pass_count += 1
        elif status == "REVIEW":
            review_count += 1
        else:
            fail_count += 1

        audit_records.append({
            "scenario_id": sid,
            "category": cat,
            "issue_kind": issue_kind,
            "status": status,
            "notes": notes
        })

    report = {
        "total_scenarios": len(scenarios),
        "pass_count": pass_count,
        "review_count": review_count,
        "fail_count": fail_count,
        "audit_records": audit_records
    }

    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Total Scenarios Audited: {len(scenarios)}")
    print(f"  PASS   : {pass_count}")
    print(f"  REVIEW : {review_count}")
    print(f"  FAIL   : {fail_count}")
    print(f"Audit report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    audit_benchmark()
