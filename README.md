# PR Review - AI Pull Request Review Agent

AI ve deterministic static analysis kullanarak Pull Request'leri analiz eden deneysel code review sistemi.

## Current Architecture

```
Pull Request
→ Diff + Code Context
→ Qwen Correctness / Security / Maintainability Reviewers
+ PMD
→ Candidate Findings
→ AI Finding Verifier
→ Merge / Deduplicate
→ Fix / Patch
→ Build & Test
→ Final Report
→ Email
```

## Current Status

### Completed
* PR diff extraction
* code context extraction
* isolated branch/worktree scanning
* PMD baseline + diff analysis
* 3 specialized Qwen reviewers
* held-out PR test set
* automatic precision/recall/F1 evaluation
* Qwen 1.5B / 7B / 14B experiments
* QLoRA dataset pipeline
* 48 scenarios / 144 samples
* QLoRA pilot training
* AI verifier prompt/benchmark/evaluator

### In Progress
* Base Qwen 7B verifier inference

### Planned
* fix/patch agent
* Maven test regression verification in PR pipeline
* automatic email delivery

---

## Run the MVP (End-to-End Execution)

Tam uçtan uca PR review akışını çalıştırmak için `run_pr_review.py` runner'ını kullanabilirsiniz:

### 1. Mock / Dry-Run Modu (Hızlı Test)
```bash
python run_pr_review.py --repo <target-repo-path> --branch <pr-branch> --dry-run
```

### 2. Qwen2.5-Coder-7B (4-Bit NF4 / GPU)
```bash
python run_pr_review.py \
  --repo <target-repo-path> \
  --branch <pr-branch> \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --backend transformers \
  --quantization 4bit \
  --output pr_review_report.json
```

### 3. OpenAI-Compatible API Modu (vLLM / Ollama / Remote Endpoint)
```bash
python run_pr_review.py \
  --repo <target-repo-path> \
  --branch <pr-branch> \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --backend openai \
  --api-base http://localhost:8000/v1 \
  --output pr_review_report.json
```