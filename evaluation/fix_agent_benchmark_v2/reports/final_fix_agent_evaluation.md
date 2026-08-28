# Fix Agent Benchmark V2: Final Evaluation Report

**Evaluation Date:** 2026-08-28  
**Model Under Evaluation:** `Qwen/Qwen2.5-Coder-7B-Instruct` (4-bit NF4 Quantization)  
**Selected Strategy:** Fix Agent V2 (Direct Grounded Structured Edit)  
**Evaluation Scope:** Synthetic Java PR Review Fix Benchmark (80 Scenarios — 56 DEV / 24 HOLDOUT)  
**Status:** Evaluation / Proof-of-Concept (PoC) Assessment

---

## 1. Executive Summary & Evaluation Protocol

This report documents the final evaluation of the automated **Fix Agent** for Java pull request review findings. The primary objective is to evaluate whether verified review findings can be safely converted into actionable, localized patch suggestions (`unified diff`) without compromising repository integrity or applying invalid code modifications.

### Evaluation Protocol & Dataset Governance:
1. **Fully Synthetic Java Dataset:** The benchmark consists of 80 isolated synthetic Java scenarios across three reviewer domains (`maintainability`, `correctness_logic`, `security_validation`), spanning three difficulty tiers (`EASY`, `MEDIUM`, `HARD`) and three complexity levels (`single_line`, `multi_line`, `boundary`).
2. **Strict Split Separation:**
   - **DEV Set (56 scenarios — 38 eligible, 18 ineligible):** Used for baseline characterization, root-cause failure analysis, and controlled ablation testing.
   - **HOLDOUT Set (24 scenarios — 16 eligible, 8 ineligible):** Kept strictly pristine and unread until all models, prompts, validators, and evaluation methodologies were frozen.
3. **One-Shot HOLDOUT Execution:** The final HOLDOUT split was executed exactly once on the frozen V2 strategy. No post-hoc prompt tuning, validator relaxation, or oracle adjustments were performed based on HOLDOUT outcomes.
4. **Multi-Tier Evaluation Hierarchy:**
   - **Tier 1 (Canonical Source Match):** Exact string match with normalized whitespace against ground-truth expected code.
   - **Tier 2 (Token-Equivalent Match):** Structural and semantic equivalence via Java token-stream matching.
   - **Tier 3 (Deterministic Semantic Oracle):** Pre-declared valid alternative implementations.
   - **Fallback (Semantic Review Required / Wrong Fix):** Non-canonical fixes that compile/apply cleanly are flagged for manual review rather than falsely accepted or rejected.

---

## 2. Final Model Architecture & Safety Configuration

The evaluated Fix Agent operates as an advisory layer following verification:

```
[ Verified Finding ] 
        │
        ▼
[ Pre-Model Eligibility Gate ] ──(Ineligible / Unsafe)──► [ Safe Skip ]
        │ (Eligible)
        ▼
[ Fix Agent V2 Formulation (Qwen2.5-Coder-7B) ] ──► [ Structured Edit: old_text -> new_text ]
        │
        ▼
[ Deterministic Multi-Layer Validator ] ──(Invalid)──► [ Validator Rejection ]
  ├── Path Safety & Scope Check
  ├── Exact / Normalized Source Grounding
  ├── Diff Size Constraint (<= 20 changed lines)
  ├── In-Memory Patch Apply Check
  └── Lightweight Java Structural Sanity Check (Brace/Paren balance)
        │ (Valid)
        ▼
[ Synthesized Unified Diff Proposal ] (Advisory Only)
```

- **Inference Strategy (V2):** The model receives single-file source context and verified defect evidence, outputting a localized structured edit (`old_text` $\rightarrow$ `new_text`).
- **Deterministic Diff Synthesis:** Unified diffs are constructed deterministically in memory from grounded replacements, eliminating LLM formatting hallucinations.
- **Safety Guarantee:** The agent operates strictly read-only and never mutates repository files, executes `git apply`, or pushes commits.

---

## 3. Baseline DEV Characterization (56 Scenarios)

On the 56 DEV scenarios (38 eligible, 18 ineligible), the frozen V2 strategy established the following baseline:

| Metric Category | Metric | DEV Baseline (V2) | Percentage |
|---|---|:---:|:---:|
| **Safety & Gate** | Pre-Model Gate Accuracy | 52 / 56 | 92.9% |
| | Pre-Model Safe Skip Rate | 14 / 18 | 77.8% |
| | Critical Gate Escapes | 0 / 18 | 0.0% |
| | **End-to-End Unsafe Prevention** | **18 / 18** | **100.0%** |
| **Mechanical Quality** | **Mechanical Success Rate** | **33 / 38** | **86.8%** |
| | Mechanical Failures | 5 / 38 | 13.2% |
| **Semantic Quality** | Canonical Source Match | 31 / 38 | 81.6% |
| | Token-Equivalent Match | 31 / 38 | 81.6% |
| | Deterministic Semantic Oracle | 1 / 4 | 25.0% |
| | **Automated Semantic Accepted** | **32 / 38** | **84.2%** |
| | Semantic Review Required | 1 / 38 | 2.6% |
| | Confirmed Wrong Fixes | 0 / 38 | 0.0% |
| **Category Breakdown** | Maintainability Mechanical | 19 / 19 | 100.0% |
| | Maintainability Semantic | 18 / 19 | 94.7% |
| | Correctness Mechanical | 14 / 19 | 73.7% |
| | Correctness Semantic | 14 / 19 | 73.7% |
| **Difficulty Breakdown** | EASY Mechanical | 16 / 17 | 94.1% |
| | MEDIUM Mechanical | 16 / 16 | 100.0% |
| | HARD Mechanical | 1 / 5 | 20.0% |

---

## 4. Root Cause Failure Analysis of DEV Mechanical Failures

Diagnostic post-inference analysis of the 5 mechanical failures in DEV revealed:

1. **FB2-027 (`EXACT_GROUNDING_FAILURE`):** Integer division aspect ratio. The model understood the defect and cast requirement, but paraphrased the anchor line (omitting outer parentheses in `old_text`), causing exact substring search to fail.
2. **FB2-034 (`EXACT_GROUNDING_FAILURE`):** Buffer slice arraycopy offset. The model correctly identified the destination offset error, but emitted slight formatting drift in `old_text`.
3. **FB2-036 (`STRUCTURED_OUTPUT_FAILURE`):** Linear interpolation operator precedence. The model understood the missing parentheses, but produced an unbalanced closing parenthesis during replacement formatting, correctly caught and rejected by structural sanity checks.
4. **FB2-037 (`EDIT_PLANNING_FAILURE`):** Retry attempts decrement. The model understood the decrement logic, but selected a micro-token anchor (`old_text = "0;"`) rather than a statement-level anchor, rejected under ambiguity safety rules.
5. **FB2-038 (`OVER_ABSTENTION`):** HTTP Created status constant. The model recognized that 201 was needed, but returned `skipped` due to conservative prompt warnings regarding public constants.

### Key Finding:
In **5 out of 5 failure cases**, problem understanding and target localization were successful (**100% comprehension**). The failures stemmed from **anchor formulation, micro-token granularity, and replacement syntax formatting**, rather than domain comprehension defects.

---

## 5. Controlled Ablation: Fix Agent V3 Experiment

To address grounding failures without altering model weights or adding external dependencies, a controlled ablation was conducted on DEV:
- **Experiment:** Fix Agent V3 (Reasoning-Guided Target Statement Grounding).
- **Formulation Change:** The model was required to first output `target_statement` (verbatim from code) and a 1-sentence `fix_explanation` before generating `new_text`, with `old_text` deterministically assigned as `old_text = target_statement`.
- **Controlled Invariants:** Same model (`Qwen2.5-Coder-7B`), same DEV scenarios, same context, same decoding (`temp=0.0`), same validators, same evaluator, zero few-shot examples, zero self-retry.

### V2 vs. V3 Ablation Results (DEV Set):

| Evaluation Metric | V2 Baseline (Direct Structured Edit) | V3 Formulation (Target Statement Grounding) | Delta |
|---|:---:|:---:|:---:|
| **Mechanical Success** | **33 / 38 (86.8%)** | 31 / 38 (81.6%) | -5.2% |
| **Automated Semantic Accepted** | **32 / 38 (84.2%)** | 22 / 38 (57.9%) | -26.3% |
| **Confirmed Wrong Fixes** | **0 / 38** | 1 / 38 | +1 |
| **Maintainability Mechanical** | **19 / 19 (100.0%)** | 13 / 19 (68.4%) | -31.6% |
| **Correctness Mechanical** | 14 / 19 (73.7%) | **18 / 19 (94.7%)** | **+21.0%** |
| **HARD Mechanical Success** | 1 / 5 (20.0%) | **5 / 5 (100.0%)** | **+80.0%** |
| **End-to-End Unsafe Prevention** | **18 / 18 (100.0%)** | **18 / 18 (100.0%)** | 0.0% |

### Ablation Interpretation & Decision:
While V3 successfully resolved the targeted HARD correctness and grounding issues (improving HARD mechanical success from 20% to 100% and Correctness mechanical from 73.7% to 94.7%), the mandatory statement-level constraint degraded maintainability edits (where simple expression deletions were over-constrained, causing 6 regressions) and overall automated semantic acceptance dropped to 57.9%.

**Decision:** In accordance with disciplined scientific methodology, **Fix Agent V2 was selected as the final candidate strategy** for the final evaluation. No post-hoc prompt iterations (e.g., V3.1) were attempted.

---

## 6. Final Pristine HOLDOUT Evaluation Results (24 Scenarios)

The final evaluation was conducted on the previously untouched 24-scenario HOLDOUT split using the frozen Fix Agent V2 configuration.

### 6.1. Aggregate Performance Metrics

| Metric Group | Evaluation Metric | HOLDOUT Result (V2) | Percentage |
|---|---|:---:|:---:|
| **Scope & Counts** | Total Scenarios | 24 | 100.0% |
| | Eligible Scenarios | 16 | 66.7% |
| | Ineligible (Expected Skip) | 8 | 33.3% |
| **Safety & Filtering** | Pre-Model Gate Accuracy | 23 / 24 | 95.8% |
| | Pre-Model Safe Skip Rate | 7 / 8 | 87.5% |
| | Critical Gate Escapes | 0 / 8 | 0.0% |
| | **End-to-End Unsafe Prevention** | **8 / 8** | **100.0%** |
| **Mechanical Quality** | **Mechanical Success Rate** | **13 / 16** | **81.2%** |
| | Mechanical Failures | 3 / 16 | 18.8% |
| **Semantic Quality** | Canonical Source Match | 9 / 16 | 56.2% |
| | Token-Equivalent Match | 11 / 16 | 68.8% |
| | Deterministic Semantic Oracle | 0 / 1 applicable | 0.0% |
| | **Automated Semantic Accepted** | **11 / 16** | **68.8%** |
| | Semantic Review Required | 2 / 16 | 12.5% |
| | Confirmed Wrong Fixes | 0 / 16 | 0.0% |

---

### 6.2. Detailed Breakdowns on HOLDOUT

#### A. Category Breakdown
- **Maintainability (8 Eligible, 4 Ineligible):**
  - Mechanical Success: **7 / 8 (87.5%)**
  - Automated Semantic Accepted: **5 / 8 (62.5%)** (3 canonical, 2 token-equivalent)
  - Semantic Review Required: **2 / 8 (25.0%)** (Valid multi-line refactorings requiring human review)
  - Ineligible Safe Skips: **3 / 4 (75.0%)** pre-model | **4 / 4 (100.0%)** end-to-end prevented.
- **Correctness Logic (8 Eligible, 2 Ineligible):**
  - Mechanical Success: **6 / 8 (75.0%)**
  - Automated Semantic Accepted: **6 / 8 (75.0%)** (6 canonical)
  - Ineligible Safe Skips: **2 / 2 (100.0%)** pre-model | **2 / 2 (100.0%)** end-to-end prevented.
- **Security Validation (0 Eligible, 2 Ineligible):**
  - Safe Skips: **2 / 2 (100.0%)** pre-model | **2 / 2 (100.0%)** end-to-end prevented.

#### B. Difficulty Breakdown
- **EASY (7 Eligible, 0 Ineligible):** Mechanical: **6 / 7 (85.7%)** | Semantic Accepted: **6 / 7 (85.7%)**
- **MEDIUM (7 Eligible, 4 Ineligible):** Mechanical: **5 / 7 (71.4%)** | Semantic Accepted: **3 / 7 (42.9%)** | Safe Skips: **4 / 4 (100.0%)**
- **HARD (2 Eligible, 4 Ineligible):** Mechanical: **2 / 2 (100.0%)** | Semantic Accepted: **2 / 2 (100.0%)** | Safe Skips: **3 / 4 (75.0%)**

#### C. Fix Complexity Breakdown (16 Eligible)
- **Single-Line (10 scenarios):** Mechanical: **8 / 10 (80.0%)** | Semantic Accepted: **8 / 10 (80.0%)** | Review Required: **0**
- **Multi-Line (5 scenarios):** Mechanical: **4 / 5 (80.0%)** | Semantic Accepted: **2 / 5 (40.0%)** | Review Required: **2**
- **Boundary (1 scenario):** Mechanical: **1 / 1 (100.0%)** | Semantic Accepted: **1 / 1 (100.0%)** | Review Required: **0**

---

### 6.3. Honest Scientific Interpretation of HOLDOUT Results

1. **Generalization Gap (DEV vs. HOLDOUT):**
   - Automated Semantic Acceptance dropped from **84.2% (32/38)** on DEV to **68.8% (11/16)** on HOLDOUT.
   - Mechanical Success decreased slightly from **86.8% (33/38)** to **81.2% (13/16)**.
   - In small sample sizes ($N=16$ eligible), each scenario represents $6.25\%$. Examining raw counts is essential: among 13 mechanically applicable fixes, **11 were automated semantic accepted, 2 required human review, and 0 produced confirmed wrong fixes**.
2. **Zero Safety Escapes:**
   - On both DEV and HOLDOUT, **100% of ineligible findings (18/18 DEV, 8/8 HOLDOUT) were prevented from generating unsafe patches**, confirming the robustness of the deterministic pre-model eligibility gate and post-model validators.
3. **PoC Evaluation Scope & Known Limitations:**
   - **Synthetic Distribution:** The benchmark utilizes synthetic, isolated Java scenarios. Real-world enterprise pull requests feature broader project context, multi-module Maven/Gradle dependencies, and project-specific conventions.
   - **Semantic Acceptance $\neq$ Full Compilation:** Semantic acceptance verifies exact or token-equivalent code transformations and structural balance, but does not guarantee execution against full javac/Maven test suites.
   - **Advisory PoC Status:** These results demonstrate strong feasibility for an automated advisory fix assistant, but do not represent an unmonitored production deployment.

---

## 7. Final Conclusion & Future Roadmap

1. **Candidate Selection:** Fix Agent V2 represents the most balanced, robust configuration, delivering **81.2% mechanical applicability**, **68.8% automated semantic acceptance**, and **100% safety prevention** on unseen HOLDOUT scenarios without confirmed wrong fixes.
2. **Future Enhancements:**
   - **Execution Sandboxing:** Integrating containerized `javac` / Maven test execution to elevate mechanical verification to full compile-time assurance.
   - **Multi-Language Expansion:** Extending the structured edit formulation and deterministic diff synthesis to TypeScript, Python, and Go.
   - **Context Retrieval:** Incorporating targeted symbol-definition indexing to resolve cross-method and boundary context requirements.
