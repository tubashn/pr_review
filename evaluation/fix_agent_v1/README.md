# Fix Agent V1 Evaluation Harness

Independent, synthetic, and deterministic evaluation benchmark for **PR Review Fix Agent V1**.

---

## 🎯 Purpose & Scope

This evaluation harness measures whether Fix Agent V1:
1. **Accurately Filters**: Correctly accepts eligible localized correctness/maintainability findings and safely skips security, absence, multi-file, and large patch issues.
2. **Generates Valid & Safe Patches**: Produces standard unified diffs targeting only the expected file within the <= 20 changed lines safety limit.
3. **Achieves Ground-Truth Correctness**: Produces clean patches that, when applied to the original source code, match the expected ground-truth code state.

### ⚠️ What This Benchmark Does NOT Measure
- Full project compilation (javac/classpath dependencies)
- Maven unit/integration test regressions
- Runtime application execution
*(These will be addressed in future sandboxed build-and-test stages.)*

---

## 📊 Dataset Statistics

* **Total Scenarios**: 30 synthetic Java scenarios
* **DEV Split**: 22 scenarios (15 Eligible, 7 Ineligible)
* **HOLDOUT Split**: 8 scenarios (5 Eligible, 3 Ineligible)

### Category Distribution
* **Maintainability**: 10 scenarios (8 DEV, 2 HOLDOUT)
* **Correctness**: 10 scenarios (7 DEV, 3 HOLDOUT)
* **Ineligible (Expected Skip)**: 10 scenarios (7 DEV, 3 HOLDOUT)

### Difficulty Distribution
* **EASY**: 14 scenarios
* **MEDIUM**: 11 scenarios
* **HARD**: 5 scenarios

---

## 🔒 HOLDOUT Isolation Policy

> ⚠️ **CRITICAL RULE**: The `HOLDOUT` split is strictly reserved for final one-shot evaluation.
>
> **DO NOT USE HOLDOUT FOR:**
> * Prompt engineering or template modifications
> * Eligibility gate heuristic tuning
> * Patch validator rule tuning
> * Mock rule creation
> * Iterative model comparison

All development and tuning must be performed exclusively against the `DEV` split.

---

## 🚀 Running Evaluation

### 1. Dataset Validation & Audit
```bash
# Validate schema, splits, line limits, and fixture existence
python evaluation/fix_agent_v1/validate_fix_eval.py

# Audit for duplicate fixtures and leakage
python evaluation/fix_agent_v1/audit_fix_eval.py
```

### 2. GPU-Free Mock Evaluation (CI / Local)
```bash
python evaluation/fix_agent_v1/run_fix_eval.py   --split DEV   --backend mock   --output evaluation/fix_agent_v1/results/mock_dev.json

python evaluation/fix_agent_v1/evaluate_fix_results.py   evaluation/fix_agent_v1/results/mock_dev.json
```

### 3. Real Model Evaluation on GPU (Tesla T4 / Colab / Server)
```bash
python evaluation/fix_agent_v1/run_fix_eval.py   --split DEV   --backend transformers   --model Qwen/Qwen2.5-Coder-7B-Instruct   --quantization 4bit   --output evaluation/fix_agent_v1/results/qwen7b_dev.json

python evaluation/fix_agent_v1/evaluate_fix_results.py   evaluation/fix_agent_v1/results/qwen7b_dev.json
```

---

## 📐 Evaluation Metrics & Failure Taxonomy

| Metric | Definition |
|---|---|
| **Eligibility Accuracy** | Rate of correct generate vs skip decisions across all scenarios. |
| **Generation Rate** | Percentage of eligible scenarios where a patch was generated. |
| **Safe Skip Rate** | Percentage of ineligible scenarios correctly skipped. |
| **Unified Diff Valid Rate** | Rate of valid unified diff syntax parsing. |
| **Path Safety Rate** | Rate of patches modifying only the designated source file without traversal. |
| **Size Safety Rate** | Rate of patches respecting the <= 20 changed lines constraint. |
| **Patch Apply Rate** | Rate of patches cleanly applying in-memory to the source fixture. |
| **Ground Truth Match Rate** | Rate of patched source matching `expected_after.java` (normalized whitespace). |
| **Strict Overall Fix Success** | Percentage of eligible scenarios passing all validation checks AND matching ground truth. |
| **Average Extra Changed Lines**| Average unnecessary changed lines beyond minimal expected patch. |

### Failure Taxonomy
* `eligibility_false_skip`: Eligible finding erroneously skipped by eligibility gate.
* `eligibility_unsafe_generate`: Ineligible finding (e.g. security) erroneously accepted.
* `model_skipped`: Model explicitly declined to produce a patch.
* `malformed_diff`: Patch failed unified diff syntax parsing.
* `unsafe_path`: Patch targeted wrong file or attempted path traversal.
* `patch_too_large`: Patch exceeded 20 changed lines.
* `apply_failed`: Patch could not be applied cleanly to source context.
* `wrong_fix`: Patch applied cleanly but produced incorrect code.
* `over_edit`: Patch achieved correct fix but modified additional unnecessary lines.
* `success`: Patch cleanly applied and perfectly matched expected ground truth.
