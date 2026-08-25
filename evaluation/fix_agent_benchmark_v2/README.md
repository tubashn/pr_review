# Fix Agent Benchmark V2 (Expanded Evaluation Suite)

An expanded, statistically robust, and structurally diverse evaluation benchmark for automated PR code repair in Java repositories.

---

## 🎯 Motivation & Design Philosophy

The legacy Fix Agent evaluation suite (`evaluation/fix_agent_v1/`) comprised 30 synthetic scenarios (22 DEV, 8 HOLDOUT). While it successfully guided Fix Agent V1 to V2 improvements (achieving 100% safe skip and 100% mechanical success on the legacy holdout), its 5 eligible holdout cases were too small to support strong statistical confidence claims for production readiness.

**Fix Agent Benchmark V2** expands the evaluation suite to **80 brand-new, unseen synthetic Java scenarios**, establishing a hardened, locked, and unbiased **24-scenario pristine HOLDOUT set**.

### Legacy Dataset Status
* The original 30 scenarios in `evaluation/fix_agent_v1/` are permanently retained as **Development History & Regression Suite**.
* None of the legacy scenario IDs (`FA-001`..`FA-030`) or fixtures are reused in Benchmark V2.

---

## 📊 Dataset Structure & Split Distribution

| Split | Total Scenarios | Eligible (Fixable) | Ineligible (Safe Skip) | Maintainability Eligible | Correctness Eligible |
|---|---|---|---|---|---|
| **DEV** | **56** | 38 | 18 | 19 | 19 |
| **HOLDOUT (Pristine)** | **24** | 16 | 8 | 8 | 8 |
| **TOTAL** | **80** | **54** | **26** | **27** | **27** |

### Difficulty Distribution (All 80 Scenarios)
* **EASY** (24): Obvious single statement or localized token replacement.
* **MEDIUM** (36): Requires moderate contextual reasoning, multi-line local logic, or nested conditions.
* **HARD** (20): Complex edge cases, arithmetic precedence, boundary limits, or subtle safety grounding.

### Fix Complexity Distribution (54 Eligible Scenarios)
* **Single-Line** (32 scenarios): Single statement or expression replacement/deletion.
* **Multi-Line** (16 scenarios): 2-5 line localized replacement within the same method.
* **Boundary** (6 scenarios): 6-18 line changes near the Fix Agent size and grounding limits.

### Ineligible Safe-Skip Risk Categories (26 Scenarios)
1. **Security Vulnerabilities** (5): Hardcoded secrets, SQL injection, path traversal, command injection (`security_findings_not_auto_fixed`).
2. **Absence-Type Findings** (5): Missing resource closures, missing guards, concurrency defects (`absence_type_not_auto_fixed`).
3. **Multi-File / Cross-Cutting** (5): Interface signature migrations, database schema sync (`multi_file_not_supported`).
4. **Large Patches** (4): Architectural refactorings exceeding 20 changed lines (`expected_patch_too_large`).
5. **Unsupported Files / Config** (3): YAML, Gradle, Maven POM files (`unsupported_file_type`).
6. **Insufficient Context** (2): Bare delimiters without anchor tokens (`insufficient_target_context`).
7. **Generated Source** (2): Protocol Buffers and ANTLR generated stubs (`unsupported_file_type`).

---

## 🔒 Frozen Multi-Tier Semantic Acceptance Hierarchy

The evaluation harness implements a strict, pre-inference frozen hierarchy:

```
Eligible Finding & Mechanical Success
  │
  ├── [Tier 1] Canonical Source Match == True
  │     └── Mode: canonical (Exact text/whitespace normalized match)
  │
  ├── [Tier 2] Token Equivalent == True
  │     └── Mode: token_equivalent (Identical Java AST token stream, formatting/blank lines ignored)
  │
  ├── [Tier 3] Deterministic Semantic Oracle == PASS (Applicable Scenarios Only)
  │     └── Mode: semantic_oracle (Model-independent deterministic property satisfaction)
  │
  ├── [Unresolved] No Oracle Available / Not Canonical
  │     └── Status: semantic_review_required (Transparently flagged, excluded from automated success)
  │
  └── [Confirmed Failure] Oracle Fail or Proven Erroneous
        └── Status: wrong_fix
```

### Key Statistical Metric Rules
1. **Separate Denominators**: Category and difficulty breakdowns clearly separate eligible and ineligible denominators (e.g. `19/19 mech` for eligible, `3/3 safe-skips` for ineligible).
2. **Oracle Applicable Denominator**: Oracle pass rate is strictly computed over scenarios having a defined oracle (`oracle_pass / oracle_applicable`). If 0 scenarios define an oracle, reports `N/A (0 applicable scenarios)`.
3. **No Post-Hoc Whitelisting**: No model-output strings or post-hoc heuristics are added after observing model runs.

---

## 🚀 Running the Benchmark

### 1. Dataset Validation & Audit
```bash
# Validate schema, counts, splits, and diff bounds
python evaluation/fix_agent_benchmark_v2/validate_benchmark.py

# Audit for duplicates, leakage, and forbidden test literals
python evaluation/fix_agent_benchmark_v2/audit_benchmark.py

# Run comprehensive regression test suite
python evaluation/fix_agent_benchmark_v2/test_benchmark_framework.py
```

### 2. Fast GPU-Free CI / Mock Evaluation
```bash
python evaluation/fix_agent_benchmark_v2/run_benchmark.py   --split DEV   --backend mock   --output evaluation/fix_agent_benchmark_v2/results/mock_dev.json

python evaluation/fix_agent_benchmark_v2/evaluate_results.py   evaluation/fix_agent_benchmark_v2/results/mock_dev.json
```

### 3. GPU / Real Qwen2.5-Coder-7B Evaluation (Colab / Linux Server)
```bash
# Run on DEV split (56 scenarios) using GPU
python evaluation/fix_agent_benchmark_v2/run_benchmark.py   --split DEV   --backend transformers   --model-id Qwen/Qwen2.5-Coder-7B-Instruct   --device cuda   --quantization 4bit   --output evaluation/fix_agent_benchmark_v2/results/qwen7b_dev.json

# Evaluate results
python evaluation/fix_agent_benchmark_v2/evaluate_results.py   evaluation/fix_agent_benchmark_v2/results/qwen7b_dev.json
```

---

## 🛡️ Pristine HOLDOUT Policy

> [!WARNING]
> **HOLDOUT Split is Strictly One-Shot.**
> The 24 scenarios in the `HOLDOUT` split are locked and pristine. Never run inference on HOLDOUT during development, and never use HOLDOUT outcomes to tune prompts, eligibility gates, validators, or semantic rules.
