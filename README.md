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
* finding merger/deduplication
* fix/patch agent
* Maven build/test verification
* final report
* automatic email delivery