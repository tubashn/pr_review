"""
CI wrapper for Benchmark V2 Audit.
Verifies that fail_count == 0. (PASS and REVIEW statuses are allowed, FAIL causes non-zero exit code).
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from evaluation.benchmark_v2.audit_benchmark import audit_benchmark, BASE_DIR
import json

if __name__ == "__main__":
    audit_benchmark()
    report_file = BASE_DIR / "reports" / "benchmark_audit_report.json"
    if report_file.exists():
        data = json.loads(report_file.read_text(encoding="utf-8"))
        fail_count = data.get("fail_count", 0)
        if fail_count > 0:
            print(f"[CI AUDIT FAILURE] Benchmark V2 audit reported {fail_count} failed scenarios!", file=sys.stderr)
            sys.exit(1)
        print("[CI AUDIT SUCCESS] Benchmark V2 audit passed with 0 FAIL.")
        sys.exit(0)
    else:
        print("[CI AUDIT ERROR] Audit report file was not generated.", file=sys.stderr)
        sys.exit(1)
