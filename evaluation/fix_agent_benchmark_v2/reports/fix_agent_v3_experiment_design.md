# Experiment Design: Fix Agent V3 — Reasoning-Guided Target Statement Grounding

**Experiment Name:** `Fix Agent V3 — Reasoning-Guided Target Statement Grounding`  
**Date:** 2026-08-26  
**Status:** Pre-Registered Experiment Protocol  
**Target Model:** `Qwen/Qwen2.5-Coder-7B-Instruct` (4-bit NF4 Quantization)  
**Target Evaluation Set:** Fix Agent Benchmark V2 (DEV Split: 56 Scenarios)  
**Baseline Reference:** Fix Agent V2 DEV Baseline (`qwen7b_v2_dev_baseline_reevaluated.json`)

---

## 1. Experimental Motivation & AI Failure Justification

A deep diagnostic post-inference analysis of the 5 mechanical failures in the Fix Agent V2 Qwen7B DEV baseline revealed:
- **Problem Understanding:** **5 / 5 PASS (100.0%)**
- **Target Localization:** **5 / 5 PASS (100.0%)**
- **Primary Semantic Miscomprehension:** **0 / 5 (0.0%)**
- **Mechanical Root Causes:**
  - `EXACT_GROUNDING_FAILURE`: **2 / 5** (FB2-027, FB2-034 — paraphrased anchor or slight variable naming drift)
  - `EDIT_PLANNING_FAILURE`: **1 / 5** (FB2-037 — micro-token `"0;"` chosen instead of statement-level anchor)
  - `STRUCTURED_OUTPUT_FAILURE`: **1 / 5** (FB2-036 — unbalanced parentheses during inline arithmetic syntax generation)
  - `OVER_ABSTENTION`: **1 / 5** (FB2-038 — conservative skip on public constant)

### Core Diagnosis:
The model possesses the required domain understanding and localized problem comprehension. The mechanical bottleneck is strictly **anchor precision, anchor granularity selection, and syntax stability during structured replacement synthesis**. 

Rather than changing the underlying foundation model or expanding token context, the most scientifically disciplined and cost-effective intervention is to **re-formulate the AI inference task** to enforce statement-level grounding.

---

## 2. Experimental Hypothesis

> **Hypothesis (V3 Formulation):**
> Constraining the model to first extract the complete, verbatim `target_statement` from the source code, formulate a 1-sentence technical `fix_explanation`, and provide the replacement `new_text` (with `old_text` deterministically assigned as `old_text = target_statement`) will eliminate paraphrased anchors and micro-token anchor ambiguities, reducing mechanical failures on HARD correctness findings while preserving 100% maintainability and safety metrics.

---

## 3. Variables & Controlled Experimental Setup

| Variable Type | Specification | Description |
|---|---|---|
| **Independent Variable** | **Inference Task Formulation** | V2 (Direct Structured Edit) vs. V3 (Reasoning-Guided Target Statement Grounding) |
| **Controlled Variable 1** | **Foundation Model** | `Qwen/Qwen2.5-Coder-7B-Instruct` (Same exact model weights and 4-bit quantization) |
| **Controlled Variable 2** | **Source Context & Prompt Inputs** | Same exact single-file before source code, line numbers, and evidence snippets |
| **Controlled Variable 3** | **Decoding Hyperparameters** | Same exact settings: `do_sample=False`, `temperature=0.0`, `max_new_tokens=512` |
| **Controlled Variable 4** | **Few-Shot Examples** | **0 Few-Shot Examples** (Pure zero-shot prompt formulation to avoid template memorization) |
| **Controlled Variable 5** | **Self-Retry** | **0 Self-Retry Iterations** (Strict single-pass evaluation for clean variable isolation) |
| **Controlled Variable 6** | **Safety & Eligibility Gates** | Exact same pre-model deterministic eligibility check (`check_fix_eligibility`) |
| **Controlled Variable 7** | **Patch Validators** | Exact same deterministic patch validator (`validate_patch`, `validate_and_apply_structured_edit`, <=20 lines, syntax sanity) |
| **Controlled Variable 8** | **Semantic Evaluator Hierarchy** | Exact same frozen multi-tier hierarchy: Canonical $\rightarrow$ Token Equivalent $\rightarrow$ Predetermined Semantic Oracle $\rightarrow$ Review Required |
| **Controlled Variable 9** | **HOLDOUT Split Isolation** | 24 HOLDOUT scenarios remain pristine and untouched (zero inference, zero tuning) |

---

## 4. Output Contract Comparison

### V2 Strategy Schema:
```json
{
  "finding_id": "FB2-037",
  "file_path": "src/main/java/com/example/retry/RetryPolicy.java",
  "fix_status": "generated",
  "old_text": "0;",
  "new_text": "this.remainingAttempts - 1;",
  "explanation": "Decrement attempts"
}
```
*V2 Limitation:* Allows the model to freely pick arbitrary, under-specified micro-anchors (`old_text = "0;"`) or paraphrase existing source code.

### V3 Strategy Schema:
```json
{
  "finding_id": "FB2-037",
  "file_path": "src/main/java/com/example/retry/RetryPolicy.java",
  "fix_status": "generated",
  "target_statement": "this.remainingAttempts = 0;",
  "fix_explanation": "Decrement remaining attempts on failure instead of zeroing.",
  "new_text": "this.remainingAttempts--;"
}
```
*V3 Advantage:* 
1. `target_statement` must be verbatim copied from the source code (preventing paraphrase and micro-anchor drift).
2. `old_text` is deterministically bound: `old_text = target_statement`.
3. `fix_explanation` serves as a lightweight 1-sentence planning anchor before code generation without polluting downstream validation.

---

## 5. Pre-Registered Ablation Comparison Matrix

When Qwen7B V3 DEV inference results are obtained, they will be compared against the frozen V2 baseline using the following schema:

| Evaluation Metric | V2 Baseline (Actual) | V3 Target | V3 Actual (To be populated) |
|---|:---:|:---:|:---:|
| **Total DEV Scenarios** | 56 | 56 | 56 |
| **Eligible Scenarios** | 38 | 38 | 38 |
| **Ineligible Scenarios** | 18 | 18 | 18 |
| **Pre-Model Gate Accuracy** | **92.9%** (52/56) | $\ge$ 92.9% | |
| **End-to-End Unsafe Prevention** | **100.0%** (18/18) | **100.0%** (18/18) | |
| **Critical Gate Escapes** | **0** | **0** | |
| **Mechanical Success Rate** | **86.8%** (33/38) | $\ge \mathbf{94.7\%}$ (36/38) | |
| **Automated Semantic Accepted** | **84.2%** (32/38) | $\ge \mathbf{92.1\%}$ (35/38) | |
| **Semantic Review Required** | 1 | $\le$ 1 | |
| **Confirmed Wrong Fixes** | **0** | **0** | |
| **Maintainability Mechanical** | **100.0%** (19/19) | **100.0%** (19/19) | |
| **Maintainability Semantic** | **94.7%** (18/19) | $\ge$ 94.7% | |
| **Correctness Mechanical** | **73.7%** (14/19) | $\ge \mathbf{89.5\%}$ (17/19) | |
| **Correctness Semantic** | **73.7%** (14/19) | $\ge \mathbf{89.5\%}$ (17/19) | |
| **EASY Mechanical** | **94.1%** (16/17) | **100.0%** (17/17) | |
| **MEDIUM Mechanical** | **100.0%** (16/16) | **100.0%** (16/16) | |
| **HARD Mechanical** | **20.0%** (1/5) | $\ge \mathbf{80.0\%}$ (4/5) | |
| **Single-Line Mechanical** | **86.4%** (19/22) | $\ge$ 95.5% (21/22) | |
| **Multi-Line Mechanical** | **100.0%** (11/11) | **100.0%** (11/11) | |
| **Boundary Mechanical** | **60.0%** (3/5) | $\ge \mathbf{80.0\%}$ (4/5) | |

---

## 6. Post-DEV Decision Rules & Next Steps

1. **If V3 achieves $\ge 92\%$ Semantic Acceptance on DEV and resolves $\ge 3$ HARD failures:**
   - Prompt, model formulation, and evaluator are frozen.
   - V3 is selected as the primary production strategy candidate.
   - Execute the single, one-shot evaluation on the 24-scenario HOLDOUT split.
2. **If V3 performance is neutral or does not improve over V2:**
   - Report the controlled ablation findings objectively.
   - Retain V2 as the production baseline.
   - Avoid iterative prompt hacking (no V3.1 / V3.2 overfitting loops).

---

## 7. Execution Command for GPU / Colab

To execute the controlled V3 experiment on Google Colab or a GPU instance:

```bash
# 1. Ensure latest main branch is pulled
cd /content/pr_review
git pull origin main

# 2. Run Fix Agent V3 DEV Benchmark Harness
python evaluation/fix_agent_benchmark_v2/run_benchmark.py \
    --split DEV \
    --backend transformers \
    --fix-strategy v3 \
    --model-id Qwen/Qwen2.5-Coder-7B-Instruct \
    --quantization 4bit \
    --device auto \
    --output evaluation/fix_agent_benchmark_v2/results/qwen7b_v3_dev.json

# 3. Evaluate results deterministically with frozen multi-tier evaluator
python evaluation/fix_agent_benchmark_v2/evaluate_results.py \
    --results evaluation/fix_agent_benchmark_v2/results/qwen7b_v3_dev.json \
    --output evaluation/fix_agent_benchmark_v2/reports/eval_report_qwen7b_v3_dev.json
```
