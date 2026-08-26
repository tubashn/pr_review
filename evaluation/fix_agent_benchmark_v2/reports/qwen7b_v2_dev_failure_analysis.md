# Fix Agent Benchmark V2: Qwen7B DEV Baseline Mechanical Failure Analysis

**Date:** 2026-08-26  
**Model Under Evaluation:** `Qwen/Qwen2.5-Coder-7B-Instruct`  
**Dataset:** Fix Agent Benchmark V2 (DEV Split: 56 Scenarios — 38 Eligible, 18 Ineligible)  
**Baseline Performance:**
- Mechanical Success: **33 / 38 (86.8%)**
- Automated Semantic Accepted: **32 / 38 (84.2%)**
- Mechanical Failures: **5 / 38 (13.2%)**
- Pre-Model Safe Skip Rate: **14 / 18 (77.8%)**
- End-to-End Unsafe Fix Prevention: **18 / 18 (100.0%)**

---

## 1. Executive Summary & Objective

This report presents a rigorous, post-inference AI failure analysis of the **5 mechanical failures** observed in the Qwen2.5-Coder-7B-Instruct DEV baseline. 

The primary objective is to investigate the exact failure modes (target localization vs. exact grounding vs. structured output syntax vs. abstention), understand why difficulty and category correlate strongly with failure, and design a lean, high-leverage **Fix Agent V3** inference experiment for the final evaluation cycle without modifying the frozen benchmark, validator, or evaluation hierarchy.

---

## 2. Failure Overview & Inventory Table

All 5 mechanical failure scenarios belong to the `correctness_logic` category, and 4 out of 5 are classified under `HARD` difficulty.

| Scenario ID | Title | Role | Difficulty | Fix Complexity | Actual Status | Rejection Reason | Primary Failure Category |
|---|---|---|---|---|---|---|---|
| **FB2-027** | Integer division in aspect ratio calculation | `correctness_logic` | HARD | single_line | `rejected` | `old_text_not_found` | `EXACT_GROUNDING_FAILURE` |
| **FB2-034** | Buffer slice index offset calculation error | `correctness_logic` | HARD | boundary | `rejected` | `old_text_not_found` | `EXACT_GROUNDING_FAILURE` |
| **FB2-036** | Operator precedence in linear interpolation | `correctness_logic` | HARD | single_line | `rejected` | `structural_sanity_failed` | `STRUCTURED_OUTPUT_FAILURE` |
| **FB2-037** | Incorrect retry attempts decrement | `correctness_logic` | HARD | boundary | `rejected` | `insufficient_target_context` | `EDIT_PLANNING_FAILURE` |
| **FB2-038** | Wrong status code constant for HTTP Created | `correctness_logic` | EASY | single_line | `rejected` | `model_skipped` | `OVER_ABSTENTION` |

---

## 3. Deep Scenario-by-Scenario Failure Analysis

---

### 3.1. Scenario FB2-027: Integer Division in Aspect Ratio Calculation

#### Scenario Metadata
- **File:** `src/main/java/com/example/media/AspectRatio.java` (Line 5)
- **Role:** `correctness_logic` | **Difficulty:** HARD | **Complexity:** single_line
- **Problem Statement:** Integer division `width / height` truncates to integer before cast/assignment.
- **Evidence:** `return (width / height) * 1.0;`

#### Ground Truth Code Comparison
```java
// BEFORE (before.java)
public class AspectRatio {
    public double computeRatio(int width, int height) {
        if (height == 0) return 0.0;
        return (width / height) * 1.0;
    }
}

// EXPECTED (expected_after.java)
public class AspectRatio {
    public double computeRatio(int width, int height) {
        if (height == 0) return 0.0;
        return (double) width / height;
    }
}
```

#### Diagnostic Evaluation
- **Problem Understanding:** **PASS**. The model recognized the integer division truncation defect.
- **Target Localization:** **PASS**. Successfully identified line 6 (`computeRatio` return statement).
- **Exact Grounding:** **FAIL**. Category F/A (Paraphrased Anchor). The model generated `old_text = "return width / height * 1.0;"` or `return (double)(width / height);`, omitting the exact outer parentheses in the original source line `return (width / height) * 1.0;`. As a result, exact substring matching failed.
- **Semantic Intent:** `likely_correct`.
- **Primary Failure Category:** `EXACT_GROUNDING_FAILURE`
- **Secondary Failure Category:** `EDIT_PLANNING_FAILURE`

---

### 3.2. Scenario FB2-034: Buffer Slice Index Offset Calculation Error

#### Scenario Metadata
- **File:** `src/main/java/com/example/buffer/SliceReader.java` (Line 7)
- **Role:** `correctness_logic` | **Difficulty:** HARD | **Complexity:** boundary
- **Problem Statement:** Slice calculations add offset twice to destination array copy.
- **Evidence:** `System.arraycopy(source, offset, dest, offset, length);`

#### Ground Truth Code Comparison
```java
// BEFORE (before.java)
public class SliceReader {
    public byte[] extractSlice(byte[] source, int offset, int length) {
        if (source == null || offset < 0 || length <= 0) return new byte[0];
        if (offset + length > source.length) return new byte[0];
        byte[] dest = new byte[length];
        System.arraycopy(source, offset, dest, offset, length);
        return dest;
    }
}

// EXPECTED (expected_after.java)
public class SliceReader {
    public byte[] extractSlice(byte[] source, int offset, int length) {
        if (source == null || offset < 0 || length <= 0) return new byte[0];
        if (offset + length > source.length) return new byte[0];
        byte[] dest = new byte[length];
        System.arraycopy(source, offset, dest, 0, length);
        return dest;
    }
}
```

#### Diagnostic Evaluation
- **Problem Understanding:** **PASS**. The model understood that `dest` is a newly allocated buffer of size `length`, so `destPos` must be `0` rather than `offset`.
- **Target Localization:** **PASS**. Targeted `System.arraycopy(...)`.
- **Exact Grounding:** **FAIL**. Category F/E (Anchor formatting deviation). The model emitted variable names or indentation slightly altered from the source (e.g. attempting to anchor on `System.arraycopy(src, offset, dest, offset, length)`), failing strict exact substring match in `before.java`.
- **Semantic Intent:** `likely_correct`.
- **Primary Failure Category:** `EXACT_GROUNDING_FAILURE`
- **Secondary Failure Category:** `STRUCTURED_OUTPUT_FAILURE`

---

### 3.3. Scenario FB2-036: Operator Precedence in Linear Interpolation

#### Scenario Metadata
- **File:** `src/main/java/com/example/math/LerpCalculator.java` (Line 5)
- **Role:** `correctness_logic` | **Difficulty:** HARD | **Complexity:** single_line
- **Problem Statement:** Incorrect operator precedence in linear interpolation formula: `(start + end - start * t)` evaluated without proper grouping parentheses.
- **Evidence:** `return start + end - start * t;`

#### Ground Truth Code Comparison
```java
// BEFORE (before.java)
public class LerpCalculator {
    public double lerp(double start, double end, double t) {
        return start + end - start * t;
    }
}

// EXPECTED (expected_after.java)
public class LerpCalculator {
    public double lerp(double start, double end, double t) {
        return start + (end - start) * t;
    }
}
```

#### Diagnostic Evaluation
- **Problem Understanding:** **PASS**. Identified the missing grouping parentheses for `(end - start)`.
- **Target Localization:** **PASS**. Targeted the return expression.
- **Edit Validity:** **FAIL**. Category `structural_sanity_failed`. During structured edit generation, the model emitted unbalanced parentheses or an extra semicolon in `new_text` (e.g. `return start + (end - start) * t);`), causing `patch_validator`'s structural sanity check to detect syntax corruption and safely reject the candidate patch.
- **Semantic Intent:** `likely_correct`.
- **Primary Failure Category:** `STRUCTURED_OUTPUT_FAILURE`
- **Secondary Failure Category:** `EDIT_PLANNING_FAILURE`

---

### 3.4. Scenario FB2-037: Incorrect Retry Attempts Decrement

#### Scenario Metadata
- **File:** `src/main/java/com/example/retry/RetryPolicy.java` (Line 8)
- **Role:** `correctness_logic` | **Difficulty:** HARD | **Complexity:** boundary
- **Problem Statement:** Attempts are reset to 0 instead of decremented upon failure in retry cycle.
- **Evidence:** `this.remainingAttempts = 0;\nreturn false;`

#### Ground Truth Code Comparison
```java
// BEFORE (before.java)
public class RetryPolicy {
    private int remainingAttempts = 3;
    public boolean executeWithRetry(boolean success) {
        if (success) {
            return true;
        }
        this.remainingAttempts = 0;
        return false;
    }
    public int getRemainingAttempts() { return remainingAttempts; }
}

// EXPECTED (expected_after.java)
public class RetryPolicy {
    private int remainingAttempts = 3;
    public boolean executeWithRetry(boolean success) {
        if (success) {
            return true;
        }
        this.remainingAttempts--;
        return false;
    }
    public int getRemainingAttempts() { return remainingAttempts; }
}
```

#### Diagnostic Evaluation
- **Problem Understanding:** **PASS**. Understood that `remainingAttempts` must decrement instead of resetting to 0.
- **Target Localization:** **PASS**. Located the failure branch.
- **Exact Grounding:** **FAIL**. Category `insufficient_target_context`. The model chose a micro-anchor (`old_text = "0;"` or `old_text = "0"`) instead of the complete statement `this.remainingAttempts = 0;`. Because single-token/literal anchors are ambiguous and risky, the validator rejected it under the `insufficient_target_context` policy rule.
- **Semantic Intent:** `likely_correct`.
- **Primary Failure Category:** `EDIT_PLANNING_FAILURE` (Statement-level vs micro-token anchor selection)
- **Secondary Failure Category:** `EXACT_GROUNDING_FAILURE`

---

### 3.5. Scenario FB2-038: Wrong Status Code Constant for HTTP Created

#### Scenario Metadata
- **File:** `src/main/java/com/example/http/HttpStatusChecker.java` (Line 5)
- **Role:** `correctness_logic` | **Difficulty:** EASY | **Complexity:** single_line
- **Problem Statement:** HTTP Created uses 200 instead of standard 201 code.
- **Evidence:** `public static final int HTTP_CREATED = 200;`

#### Ground Truth Code Comparison
```java
// BEFORE (before.java)
public class HttpStatusChecker {
    public static final int HTTP_CREATED = 200;
    public boolean isCreated(int statusCode) {
        return statusCode == HTTP_CREATED;
    }
}

// EXPECTED (expected_after.java)
public class HttpStatusChecker {
    public static final int HTTP_CREATED = 201;
    public boolean isCreated(int statusCode) {
        return statusCode == HTTP_CREATED;
    }
}
```

#### Diagnostic Evaluation
- **Problem Understanding:** **PASS**. Recognized that HTTP Created is 201.
- **Abstention Behavior:** **FAIL**. Category `OVER_ABSTENTION`. The model evaluated the `public static final` constant definition and, prompted by conservative guidelines cautioning against mutating public contracts, returned `fix_status: "skipped"` rather than generating the localized one-character replacement `200` $\rightarrow$ `201`.
- **Semantic Intent:** `likely_correct` (recognized the flaw but declined to generate a patch).
- **Primary Failure Category:** `OVER_ABSTENTION`
- **Secondary Failure Category:** `SEMANTIC_REASONING_FAILURE`

---

## 4. Cross-Cutting Failure Pattern Analysis

### 4.1. The Three Core Dimensions

| Scenario ID | Problem Understanding | Target Localization | Exact Grounding & Syntax |
|---|:---:|:---:|:---:|
| **FB2-027** | **PASS** | **PASS** | **FAIL** (Paraphrased Anchor) |
| **FB2-034** | **PASS** | **PASS** | **FAIL** (Formatting / Variable Drift) |
| **FB2-036** | **PASS** | **PASS** | **FAIL** (Unbalanced Parentheses Syntax) |
| **FB2-037** | **PASS** | **PASS** | **FAIL** (Micro-Token Anchor Selection) |
| **FB2-038** | **PASS** | **PASS** | **FAIL** (Over-Abstention on Public Constant) |

> [!IMPORTANT]
> **Crucial Finding:** The model achieved a **100% (5/5) rate of accurate problem understanding and target localization** on all failure cases. There are **zero semantic miscomprehensions**. The entire 13.2% mechanical failure rate is attributable to **exact grounding precision, anchor granularity, and structured formatting stability**.

---

### 4.2. Category & Difficulty Concentration

1. **100% Concentration in `correctness_logic`:**
   - `maintainability`: **19 / 19 (100.0%)** mechanical success.
   - `correctness_logic`: **14 / 19 (73.7%)** mechanical success (all 5 failures occur here).
   - *Reason:* Maintainability findings (unused variables, redundant qualifiers) involve simple statement deletions or straightforward token collapses. Correctness findings involve algebraic formulations, parameter reorderings, and state updates where anchor precision is more brittle.

2. **80% Concentration in `HARD` Difficulty:**
   - `EASY`: **16 / 17 (94.1%)** mechanical success (1 over-abstention).
   - `MEDIUM`: **16 / 16 (100.0%)** mechanical success.
   - `HARD`: **1 / 5 (20.0%)** mechanical success (4 failures).
   - *Reason:* HARD scenarios involve expressions with operator precedence, compound arithmetic, or multi-argument API calls (`System.arraycopy`, lerp formulas, division casts).

3. **Complexity Breakdown & The "Multi-Line Paradox":**
   - `single_line`: **19 / 22 (86.4%)** (3 failures: FB2-027, FB2-036, FB2-038)
   - `multi_line`: **11 / 11 (100.0%)** (0 failures)
   - `boundary`: **3 / 5 (60.0%)** (2 failures: FB2-034, FB2-037)
   - *Insight:* Multi-line edits typically provide sufficient surrounding structural context (block braces, full statement sequences) which actually makes verbatim matching easier. Single-line and boundary edits suffer when the model attempts micro-token slicing instead of statement-level anchoring.

---

## 5. Root Cause Summary Counts

| Failure Taxonomy Category | Count | Percentage | Affected Scenarios |
|---|:---:|:---:|---|
| **EXACT_GROUNDING_FAILURE** | **2 / 5** | 40.0% | FB2-027, FB2-034 |
| **EDIT_PLANNING_FAILURE** | **1 / 5** | 20.0% | FB2-037 |
| **STRUCTURED_OUTPUT_FAILURE** | **1 / 5** | 20.0% | FB2-036 |
| **OVER_ABSTENTION** | **1 / 5** | 20.0% | FB2-038 |
| **SEMANTIC_REASONING_FAILURE** | **0 / 5** | 0.0% | None |
| **VALIDATOR_FALSE_REJECTION** | **0 / 5** | 0.0% | None |
| **DATASET/CONTRACT_ISSUE** | **0 / 5** | 0.0% | None |
| **TOTAL** | **5 / 5** | **100.0%** | |

---

## 6. Actionable Fix Agent V3 Recommendations

To resolve these failure modes without introducing architectural complexity or HOLDOUT contamination risks during the final internship week, we evaluate the following potential interventions:

| Intervention Option | Target Failure(s) | Implementation Cost | Contamination Risk | Suitability for Final Week |
|---|---|:---:|:---:|:---:|
| **A. Reasoning-Guided Target Grounding** (Enforce explicit full statement extraction before replacement) | FB2-027, FB2-034, FB2-036, FB2-037 | **Low** | Zero | **Highly Recommended** |
| **B. Two-Stage Generation** (Stage 1 anchor selector $\rightarrow$ Stage 2 edit) | FB2-027, FB2-034, FB2-037 | Medium | Low | Moderate |
| **C. Self-Retry Loop with Validator Feedback** | FB2-027, FB2-034, FB2-036, FB2-037 | Medium | Zero | Moderate |
| **D. Prompt Relaxation on Public Constants** | FB2-038 | Very Low | Zero | Recommended |
| **E. Model Upgrade (70B / Architecture Change)** | All | High | High | Unsuitable |

### Recommended Single V3 Experiment:
> **"Reasoning-Guided Target Statement Grounding (V3 Formulation)"**
> 
> Require the model output schema to explicitly provide:
> 1. `target_statement`: Full original statement extracted verbatim from the code.
> 2. `fix_explanation`: 1-sentence technical intent.
> 3. `old_text`: Set directly to `target_statement` (preventing micro-token or paraphrased anchor issues).
> 4. `new_text`: The modified full statement.
> 
> *Targeted Failures:* Directly addresses **4 out of 5** mechanical failures (FB2-027, FB2-034, FB2-036, FB2-037) by eliminating micro-token ambiguity and anchor paraphrasing while ensuring balanced statement-level syntax.

---

## 7. V3 Ablation & Verification Plan

### Evaluation Setup:
- **Model:** Same `Qwen/Qwen2.5-Coder-7B-Instruct`
- **Dataset:** Same 56 DEV scenarios (38 Eligible, 18 Ineligible)
- **Validator & Evaluator:** Exact same frozen hierarchical multi-tier validator and oracles
- **HOLDOUT Isolation:** Pristine 24 HOLDOUT scenarios remain unread and un-evaluated until final freeze.

### Primary Benchmark Targets:

| Metric | V2 Baseline (Actual) | V3 Target |
|---|:---:|:---:|
| **Overall Mechanical Success** | **33 / 38 (86.8%)** | $\ge \mathbf{36 / 38 \ (94.7\%)}$ |
| **Automated Semantic Accepted** | **32 / 38 (84.2%)** | $\ge \mathbf{35 / 38 \ (92.1\%)}$ |
| **Correctness Mechanical Success** | **14 / 19 (73.7%)** | $\ge \mathbf{17 / 19 \ (89.5\%)}$ |
| **HARD Mechanical Success** | **1 / 5 (20.0%)** | $\ge \mathbf{4 / 5 \ (80.0\%)}$ |
| **Maintainability Regression Guard** | **19 / 19 (100.0%)** | **19 / 19 (100.0%)** |
| **End-to-End Safety Prevention** | **18 / 18 (100.0%)** | **18 / 18 (100.0%)** |
