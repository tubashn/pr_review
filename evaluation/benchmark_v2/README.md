# Java / Spring PR Review Evaluation Benchmark V2

## 1. Overview & Purpose
**Benchmark V2** is an expanded, high-diversity, multi-tiered evaluation dataset designed to rigorously assess the generalization capabilities of Java/Spring pull request reviewers and finding verifiers.

Unlike the initial 16-candidate development/debug benchmark, Benchmark V2 provides:
- **40 Distinct PR Scenarios** (28 DEV / 12 HOLDOUT) across real-world Spring Boot & Java backend architectural patterns.
- **120 Reviewer Candidate Findings** (30 ACCEPT / 90 REJECT).
- **Strict Multi-Tiered Categories**:
  - `DIRECT`: Explicit syntax / literal / constant / unreachable issues.
  - `STRUCTURAL / ABSENCE`: Method-scoped unused variables and unclosed I/O resources (`ZipFile`, `BufferedReader`, `FileInputStream`).
  - `SEMANTIC / BUSINESS LOGIC`: Authorization condition inversions, tenant isolation failures, state machine transition bugs, arithmetic transfer limit bypasses, and DTO field corruptions.
  - `CLEAN / HARD NEGATIVE`: Clean PRs featuring guarded ternary expressions, try-with-resources refactorings, timing-safe equality, and defensive copies where naive reviewers hallucinate false positives.

---

## 2. Dataset Split & Leakage Policy

> [!IMPORTANT]
> - **Evaluation Asset Only**: This benchmark is strictly an evaluation artifact. It is never included in training sets (`train.jsonl`, `validation.jsonl`, `scenario_catalog.json`).
> - **DEV vs. HOLDOUT Isolation**:
>   - **DEV Split (28 Scenarios, 84 Candidates)**: Used for developmental routing analysis, pipeline diagnosis, and model bake-offs.
>   - **HOLDOUT Split (12 Scenarios, 36 Candidates)**: Strictly reserved for blind production benchmark evaluation. No heuristic rules or prompts may be tuned against HOLDOUT scenarios.
> - **Anti-Leakage Guarantee**: Completely decoupled from previous debug sets (`tuba-test`, `OrderServiceImpl`, `testValue`, `admin123`, etc.).

---

## 3. Dataset Distribution & Summary Statistics

### Scenarios Distribution (40 PRs)
- **DEV**: 28 scenarios (70.0%)
- **HOLDOUT**: 12 scenarios (30.0%)
- **Categories**:
  - `DIRECT`: 10 scenarios (25.0%)
  - `STRUCTURAL`: 10 scenarios (25.0%)
  - `SEMANTIC`: 10 scenarios (25.0%)
  - `CLEAN`: 10 scenarios (25.0%)
- **Difficulty**:
  - `HARD`: 17 scenarios (42.5%)
  - `MEDIUM`: 13 scenarios (32.5%)
  - `EASY`: 10 scenarios (25.0%)
- **Framework & Language**:
  - Java Backend (Spring Boot: 26, Plain Java: 14)
- **Provenance**:
  - Synthetic high-fidelity Java backend architectures (100%)

### Candidates Distribution (120 Findings)
- **Total Candidates**: 120
- **Ground Truth Expected Verdicts**:
  - `ACCEPT` (True Findings): 30 candidates (25.0%)
  - `REJECT` (Negative / False Findings): 90 candidates (75.0%)
- **Reviewer Roles (Balanced)**:
  - `correctness_logic`: 40 candidates (33.3%)
  - `security_validation`: 40 candidates (33.3%)
  - `maintainability`: 40 candidates (33.3%)
- **Reason Types**:
  - `true_finding`: 30 candidates (25.0%)
  - `false_positive`: 31 candidates (25.8%)
  - `role_leakage`: 29 candidates (24.2%)
  - `clean_pr_false_positive`: 30 candidates (25.0%)

---

## 4. Directory & Fixture Structure

```
evaluation/benchmark_v2/
├── README.md                               # Benchmark reference documentation
├── schema.json                             # JSON validation schema
├── scenarios.json                          # Full 40 scenario definitions & metadata
├── candidates.json                         # 120 reviewer candidate findings
├── ground_truth.json                       # Ground truth annotations & evidence
├── splits.json                             # DEV (28) / HOLDOUT (12) partition mapping
├── fixtures/                               # Per-scenario before/after files & diffs
│   ├── BV2-001/ ... BV2-040/
│   │   ├── before/                         # Source code before PR
│   │   ├── after/                          # Source code after PR
│   │   └── diff.patch                      # Unified diff patch
├── reports/                                # Diagnostic & routing reports
│   ├── benchmark_audit_report.json         # Near-duplicate & semantic audit results
│   ├── router_dev_report.json              # Production router DEV evaluation report
│   └── semantic_verifier_requests_DEV.json # Prepared requests for model bake-off
├── validate_benchmark.py                   # Automated validation suite
├── audit_benchmark.py                      # Semantic audit & structural skeleton scanner
├── build_benchmark_v2.py                   # Reproducible dataset generator
└── route_benchmark_v2.py                   # Production router evaluation tool
```

---

## 5. Production Router DEV Evaluation Results

Evaluating the DEV split (84 candidates) through the existing tiered production router yields:
- **Deterministic Routes**: 34 candidates (40.5%)
  - *Direct Issues*: 21 candidates
  - *Absence Issues (Unused / Unclosed)*: 12 candidates
  - *AST Self-Refuted (Clean NPE)*: 1 candidate
- **Semantic Verifier Routes**: 50 candidates (59.5%)
  - *Semantic True Findings*: 8 candidates
  - *Semantic False Findings / Role Mismatches*: 42 candidates
- **Unsupported / Unknown**: 0 candidates (100% routed cleanly)

Prepared requests for downstream model verification are saved in `reports/semantic_verifier_requests_DEV.json` with all `suggested_fix` fields strictly excluded.
