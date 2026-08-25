# Fix Agent Evaluation Harness (V2 Benchmark)

Independent, synthetic, and deterministic evaluation benchmark for **PR Review Fix Agent V2**.

---

## 🎯 Purpose & Scope

This evaluation harness measures whether Fix Agent V2:
1. **Accurately Filters**: Correctly accepts eligible localized correctness/maintainability findings and safely skips security, absence, multi-file, and large patch issues.
2. **Generates Grounded Structured Edits**: Identifies exact, localized `old_text` -> `new_text` replacements without requiring the LLM to calculate unified diff headers/offsets.
3. **Validates Mechanical Safety**: Ensures path safety, <= 20 changed lines, non-delimiter target constructs, in-memory patch application, and structural Java sanity (balanced braces/parens).
4. **Achieves Ground-Truth Semantic Correctness**: Produces clean patches that, when applied to the original source code, match the expected ground-truth code state (`expected_after.java`).

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
> * Patch validator / structured edit rule tuning
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

# Framework unit tests
python evaluation/fix_agent_v1/test_fix_eval_framework.py
```

### 2. GPU-Free Mock Evaluation (CI / Local)
```bash
python evaluation/fix_agent_v1/run_fix_eval.py \
  --split DEV \
  --backend mock \
  --output evaluation/fix_agent_v1/results/mock_dev.json

python evaluation/fix_agent_v1/evaluate_fix_results.py \
  evaluation/fix_agent_v1/results/mock_dev.json
```

### 3. Real Model Evaluation on GPU (Tesla T4 / Colab / Server)
```bash
python evaluation/fix_agent_v1/run_fix_eval.py \
  --split DEV \
  --backend transformers \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --quantization 4bit \
  --output evaluation/fix_agent_v1/results/qwen7b_dev.json

python evaluation/fix_agent_v1/evaluate_fix_results.py \
  evaluation/fix_agent_v1/results/qwen7b_dev.json
```

---

## 📐 Evaluation Metrics & Failure Taxonomy

### Multi-Tier Metric Hierarchy

| Tier / Category | Metric | Definition |
|---|---|---|
| **Gate** | **Eligibility Accuracy** | Rate of correct generate vs skip decisions across all scenarios. |
| **Gate** | **Safe Skip Rate** | Percentage of ineligible scenarios correctly skipped. |
| **Mechanical** | **Model Structured Edit Gen Rate** | Percentage of eligible scenarios where model returned a structured edit. |
| **Mechanical** | **Synthesized Diff Valid Rate** | Rate of valid unified diff syntax parsing. |
| **Mechanical** | **Path Safety Rate** | Rate of patches modifying only the designated source file without traversal. |
| **Mechanical** | **Size Safety Rate** | Rate of patches respecting the <= 20 changed lines constraint. |
| **Mechanical** | **Patch In-Memory Apply Rate** | Rate of patches cleanly applying in-memory to the source fixture. |
| **Mechanical** | **Mechanical Success Rate** | All mechanical checks pass: grounded + valid diff + size safe + path safe + applied + structural sanity. |
| **Semantic Tier 1** | **Canonical Source Match Rate** | Patched source matches canonical `expected_after.java` (normalized whitespace). |
| **Semantic Tier 2** | **Token Equivalent Match Rate** | Java lexical token stream matches expected code (ignores formatting/blank lines but preserves literals and operators). |
| **Semantic Tier 3** | **Semantic Oracle Pass Rate** | Satisfies benchmark-defined deterministic semantic oracle (e.g. alternative valid mathematical expressions). |
| **Overall Semantic**| **Semantic Accepted Fix Rate** | Mechanical Success AND (Canonical Match OR Token Equivalent OR Semantic Oracle Pass). |

### Failure & Success Taxonomy
* `success_canonical`: Patch produced exact canonical source form matching `expected_after.java`.
* `success_token_equivalent`: Patch produced identical Java lexical token sequence (e.g., blank-line differences).
* `success_semantic_oracle`: Patch satisfied deterministic semantic postcondition (e.g., equivalent arithmetic expression).
* `semantic_review_required`: Mechanical checks passed but patch is non-canonical, not token-equivalent, and lacks oracle.
* `wrong_fix`: Patch produced confirmed incorrect code or failed semantic oracle.
* `over_edit`: Patch achieved correct fix but modified unnecessary additional lines.
* `apply_failed`: Synthesized patch failed in-memory application check.
* `structural_invalid`: Patched Java source failed structural sanity check (unbalanced braces/parens).
* `patch_too_large`: Generated patch exceeded 20 changed lines limit.
* `unsafe_path`: Patch targeted wrong file or attempted path traversal.
* `insufficient_target_context`: `old_text` consisted solely of delimiters/punctuation (e.g. `}`).
* `target_location_mismatch`: `old_text` location in source was distant from verified finding line.
* `target_not_modified`: `old_text` did not touch or overlap the verified problem evidence.
* `no_op_fix`: `old_text` was identical to `new_text` (or only whitespace changes).
* `eligibility_false_skip`: Eligible finding erroneously skipped by eligibility gate.
* `eligibility_unsafe_generate`: Ineligible finding erroneously accepted by eligibility gate.


