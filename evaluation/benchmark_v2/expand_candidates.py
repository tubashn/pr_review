import json
from pathlib import Path

b_dir = Path(__file__).resolve().parent
candidates_file = b_dir / "candidates.json"
scenarios_file = b_dir / "scenarios.json"

additional_candidates = {
    "BV2-005": {
        "reviewer": "security_validation",
        "problem": "Missing range sanitization allows out-of-bounds latitude GPS spoofing.",
        "failure_scenario": "Unbounded GPS input allows spoofing location coordinates in tracking services.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-006": {
        "reviewer": "security_validation",
        "problem": "Unencrypted communication alert dispatching vulnerability.",
        "failure_scenario": "Email content sent in cleartext without TLS validation.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-008": {
        "reviewer": "security_validation",
        "problem": "Insecure direct country code validation allows tax evasion.",
        "failure_scenario": "Attackers can bypass VAT verification using malformed country codes.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-009": {
        "reviewer": "maintainability",
        "problem": "Extract AWS secret key string into application.yml configuration property.",
        "failure_scenario": "Hardcoded strings decrease maintainability across environments.",
        "expected": "REJECT",
        "reason": "role_leakage",
        "difficulty": "MEDIUM"
    },
    "BV2-010": {
        "reviewer": "security_validation",
        "problem": "Feature flag tampering vulnerability allows unauthorized UI access.",
        "failure_scenario": "Boolean condition can be manipulated via parameter injection.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-013": {
        "reviewer": "security_validation",
        "problem": "Information disclosure vulnerability in execution latency timing.",
        "failure_scenario": "Measuring nanosecond latency differences allows side-channel timing attacks.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-014": {
        "reviewer": "security_validation",
        "problem": "Socket input stream denial of service via unbounded readLine() call.",
        "failure_scenario": "Malicious client sending infinite line without newline character exhausts JVM memory.",
        "expected": "REJECT",
        "reason": "role_leakage",
        "difficulty": "HARD"
    },
    "BV2-015": {
        "reviewer": "security_validation",
        "problem": "CSV injection vulnerability in user export headers.",
        "failure_scenario": "CSV formulas starting with =, +, -, @ can execute arbitrary commands in spreadsheet viewers.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-017": {
        "reviewer": "correctness_logic",
        "problem": "Regex masking fails to mask entire IP address for IPv6 addresses.",
        "failure_scenario": "IPv6 addresses do not contain dots, so masking is skipped entirely.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-018": {
        "reviewer": "security_validation",
        "problem": "Markdown table header formatting allows cross-site scripting (XSS).",
        "failure_scenario": "Unescaped HTML in markdown headers can execute JavaScript in web markdown viewers.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-019": {
        "reviewer": "security_validation",
        "problem": "Arbitrary file disclosure during file checksum hash calculation.",
        "failure_scenario": "Target file path parameter is not validated against a path whitelist.",
        "expected": "REJECT",
        "reason": "role_leakage",
        "difficulty": "HARD"
    },
    "BV2-020": {
        "reviewer": "security_validation",
        "problem": "HTTP header injection / CRLF injection in trace ID forwarding.",
        "failure_scenario": "Timestamp appended to trace header allows header smuggling.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-023": {
        "reviewer": "maintainability",
        "problem": "Replace compareTo chained comparisons with BigDecimal helper method.",
        "failure_scenario": "Chained compareTo expressions decrease code clarity.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-024": {
        "reviewer": "maintainability",
        "problem": "Daily cap subtraction logic should be documented with explanatory comments.",
        "failure_scenario": "Lack of business documentation impairs onboarding.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "EASY"
    },
    "BV2-025": {
        "reviewer": "security_validation",
        "problem": "PII leakage: user email is replaced with phone number without consent verification.",
        "failure_scenario": "Profile update endpoint exposes telephone number in email field.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-026": {
        "reviewer": "maintainability",
        "problem": "Use TenantContextHolder thread-local instead of passing session parameter.",
        "failure_scenario": "Explicit session passing increases method coupling.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-027": {
        "reviewer": "security_validation",
        "problem": "Subscription grace period bypass vulnerability.",
        "failure_scenario": "Users can exploit date parsing to extend unpaid subscription access.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-028": {
        "reviewer": "maintainability",
        "problem": "Rename parameter transactionCount to totalDailyTransactions for clarity.",
        "failure_scenario": "Ambiguous variable naming.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "EASY"
    },
    "BV2-029": {
        "reviewer": "maintainability",
        "problem": "Extract permission evaluation into reusable AuthorizationStrategy interface.",
        "failure_scenario": "Direct boolean logic limits future role extensions.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-030": {
        "reviewer": "security_validation",
        "problem": "Integer overflow vulnerability in earned points multiplication.",
        "failure_scenario": "Multiplying large integer points can wrap around to negative numbers.",
        "expected": "REJECT",
        "reason": "false_positive",
        "difficulty": "HARD"
    },
    "BV2-032": {
        "reviewer": "maintainability",
        "problem": "Use Files.readAllBytes(Path) instead of creating FileInputStream.",
        "failure_scenario": "Files utility method provides cleaner syntax.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-033": {
        "reviewer": "correctness_logic",
        "problem": "formatRoleBadge returns different string format breaking existing frontend badge styling.",
        "failure_scenario": "UI components expecting short role strings may render visual overflow.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-034": {
        "reviewer": "maintainability",
        "problem": "Complex boolean condition in return statement should be split into multiple guard clauses.",
        "failure_scenario": "Chaining four boolean conditions reduces readability.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-035": {
        "reviewer": "security_validation",
        "problem": "Unsafe deserialization risk when returning defensive copy of element list.",
        "failure_scenario": "Elements inside list could contain mutable objects vulnerable to tampering.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "HARD"
    },
    "BV2-036": {
        "reviewer": "maintainability",
        "problem": "Use StandardCharsets.UTF_8 constant directly without re-encoding byte arrays.",
        "failure_scenario": "String encoding can be cached.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-037": {
        "reviewer": "security_validation",
        "problem": "Denial of service through repetitive NumberFormatException throwing.",
        "failure_scenario": "Parsing millions of invalid numeric strings incurs CPU overhead from stack trace generation.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "HARD"
    },
    "BV2-038": {
        "reviewer": "maintainability",
        "problem": "KMS key alias string literal should be declared as a private static final constant.",
        "failure_scenario": "Hardcoded alias string decreases code maintainability.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "MEDIUM"
    },
    "BV2-039": {
        "reviewer": "security_validation",
        "problem": "Deadlock vulnerability due to synchronized block on private lock object.",
        "failure_scenario": "Thread locking can be exploited to cause server denial of service.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "HARD"
    },
    "BV2-040": {
        "reviewer": "maintainability",
        "problem": "Replace chained replace() calls with a single regex or compile a Pattern constant.",
        "failure_scenario": "Chained string replacement incurs extra string allocations.",
        "expected": "REJECT",
        "reason": "clean_pr_false_positive",
        "difficulty": "MEDIUM"
    }
}

candidates = json.load(open(candidates_file, encoding="utf-8"))
cand_by_sc = {}
for c in candidates:
    cand_by_sc.setdefault(c["scenario_id"], []).append(c)

new_candidates = []
for sc_id in [f"BV2-{i:03d}" for i in range(1, 41)]:
    existing = cand_by_sc.get(sc_id, [])
    new_candidates.extend(existing)
    if sc_id in additional_candidates:
        c_add = additional_candidates[sc_id]
        c_id = f"{sc_id}-{c_add['reviewer']}-cand-{len(existing)}"
        new_candidates.append({
            "candidate_id": c_id,
            "scenario_id": sc_id,
            "source_reviewer": c_add["reviewer"],
            "problem": c_add["problem"],
            "failure_scenario": c_add["failure_scenario"],
            "expected": c_add["expected"],
            "expected_finding_supported": (c_add["expected"] == "ACCEPT"),
            "reason_type": c_add["reason"],
            "difficulty": c_add["difficulty"]
        })

print(f"Total new candidates: {len(new_candidates)}")
with open(candidates_file, "w", encoding="utf-8") as f:
    json.dump(new_candidates, f, indent=2, ensure_ascii=False)
print("Saved candidates.json successfully!")
