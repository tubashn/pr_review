"""
Fix Agent V1 Evaluation Runner
Executes Fix Agent on specified dataset split (DEV by default), applying generated
patches cleanly in memory, verifying against expected_after.java, and recording
structured per-scenario evaluation outcomes.
"""

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Local imports
PR_REVIEW_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PR_REVIEW_ROOT))

from fix_agent import run_fix_agent_for_finding
from patch_validator import (
    validate_patch,
    apply_unified_diff_to_text,
    count_changed_lines
)
from semantic_oracle import (
    evaluate_semantic_correctness,
    normalize_source_code,
    check_token_equivalence
)

EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL_DIR / "scenarios.json"
SPLITS_FILE = EVAL_DIR / "splits.json"


def normalize_source_code(code: str) -> str:
    """Normalizes newlines and trailing whitespace for reliable comparison."""
    lines = [line.rstrip() for line in code.strip().splitlines()]
    return "\n".join(lines)


def run_evaluation(
    split: str = "DEV",
    backend: str = "mock",
    model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
    quantization: str = "4bit",
    device: str = "auto",
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    output_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Runs Fix Agent evaluation on selected split."""
    start_time = time.time()
    print("==================================================")
    print("FIX AGENT V1 EVALUATION HARNESS")
    print("==================================================")
    print(f"Split       : {split}")
    print(f"Backend     : {backend}")
    print(f"Model ID    : {model_id}")
    print("==================================================")

    if split == "HOLDOUT":
        print("⚠️ [HOLDOUT WARNING] Running on HOLDOUT split! Results must not be used for tuning.")

    scenarios_data = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))["scenarios"]
    splits_data = json.loads(SPLITS_FILE.read_text(encoding="utf-8"))
    target_ids = set(splits_data.get(split, []))

    selected_scenarios = [s for s in scenarios_data if s["scenario_id"] in target_ids]
    print(f"Loaded {len(selected_scenarios)} scenario(s) for split '{split}'.\n")

    # Singleton model loading for transformers backend if needed
    loaded_model = None
    tokenizer = None
    if backend in ("transformers", "hf"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        print(f"[Model Loader] Loading {model_id} singleton...")
        is_deepseek_v2 = "deepseek-coder-v2" in model_id.lower()
        compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
        bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=compute_dtype) if quantization == "4bit" else None
        trust_flag = False if is_deepseek_v2 else True
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=trust_flag)
        loaded_model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb_config, device_map=device, trust_remote_code=trust_flag)
        print("[Model Loader] Model ready.\n")

    results = []

    for idx, sc in enumerate(selected_scenarios, start=1):
        sid = sc["scenario_id"]
        title = sc["title"]
        role = sc["role"]
        fpath = sc["file_path"]
        is_elig_exp = sc["eligibility_expected"]
        exp_status = sc["expected_fix_status"]

        src_path = EVAL_DIR / sc["source_fixture"]
        before_text = src_path.read_text(encoding="utf-8") if src_path.exists() else ""

        expected_after_text = None
        if sc.get("expected_after_fixture"):
            after_path = EVAL_DIR / sc["expected_after_fixture"]
            if after_path.exists():
                expected_after_text = after_path.read_text(encoding="utf-8")

        # Format finding dictionary for Fix Agent
        finding = {
            "candidate_id": sid,
            "decision": "ACCEPT",
            "source_reviewer": role,
            "file": fpath,
            "file_path": fpath,
            "line": sc["line"],
            "problem": sc["problem"],
            "code_snippet": sc.get("evidence", ""),
            "after_source": before_text
        }

        print(f"[{idx}/{len(selected_scenarios)}] Evaluating {sid}: {title} ({role})...")

        agent_output = run_fix_agent_for_finding(
            finding=finding,
            backend=backend,
            loaded_model=loaded_model,
            tokenizer=tokenizer,
            api_base=api_base,
            api_key=api_key,
            model_id=model_id,
            dry_run=(backend == "mock"),
            pr_changed_files=[fpath]
        )

        actual_status = agent_output.get("fix_status", "skipped")
        validation = agent_output.get("validation", {})
        diff_text = agent_output.get("diff", "")
        old_text = agent_output.get("old_text", "")
        new_text = agent_output.get("new_text", "")
        match_mode = agent_output.get("match_mode")
        skip_reason = agent_output.get("skip_reason")
        rejection_reason = agent_output.get("rejection_reason")
        agent_failure = agent_output.get("failure_type")

        # Eligibility actual assessment
        if actual_status == "skipped" and skip_reason in (
            "security_findings_not_auto_fixed",
            "absence_type_not_auto_fixed",
            "multi_file_not_supported",
            "unsupported_file_type",
            "expected_patch_too_large",
            "unverified_or_rejected_finding"
        ):
            elig_actual = False
        else:
            elig_actual = True

        canonical_source_match = False
        token_equivalent = False
        semantic_oracle_pass = False
        semantic_match = False
        semantic_match_mode = None
        failure_subtype = None
        extra_changed_lines = 0
        failure_type = None

        if not is_elig_exp:
            # Expected skip
            if actual_status == "skipped":
                failure_type = "success"  # Safe skip
                failure_subtype = "success_safe_skip"
            else:
                failure_type = "eligibility_unsafe_generate"
                failure_subtype = "eligibility_unsafe_generate"
        else:
            # Expected generated fix
            if not elig_actual:
                failure_type = "eligibility_false_skip"
                failure_subtype = "eligibility_false_skip"
            elif actual_status == "skipped":
                failure_type = "model_skipped"
                failure_subtype = "model_skipped"
            elif actual_status == "rejected":
                failure_type = agent_failure or rejection_reason or "patch_generation_failed"
                failure_subtype = failure_type
            elif actual_status == "generated":
                # Check patch application and semantic correctness tiers
                if expected_after_text and diff_text:
                    app_ok, patched_code, app_err = apply_unified_diff_to_text(before_text, diff_text)
                    if not app_ok:
                        failure_type = "apply_failed"
                        failure_subtype = "apply_failed"
                    else:
                        sem_res = evaluate_semantic_correctness(
                            patched_code=patched_code,
                            expected_code=expected_after_text,
                            oracle_spec=sc.get("semantic_oracle")
                        )
                        canonical_source_match = sem_res["canonical_source_match"]
                        token_equivalent = sem_res["token_equivalent"]
                        semantic_oracle_pass = sem_res["semantic_oracle_pass"]
                        semantic_match = sem_res["semantic_match"]
                        semantic_match_mode = sem_res["semantic_match_mode"]
                        failure_subtype = sem_res["failure_subtype"]

                        # Compute extra changed lines relative to minimal expected diff
                        diff_lines_gen = sum(1 for l in diff_text.splitlines() if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
                        exp_diff_lines = list(difflib.unified_diff(before_text.splitlines(), expected_after_text.splitlines()))
                        diff_lines_exp = sum(1 for l in exp_diff_lines if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
                        extra_changed_lines = max(0, diff_lines_gen - diff_lines_exp)

                        if semantic_match:
                            if extra_changed_lines > 0:
                                failure_type = "over_edit"
                            else:
                                failure_type = "success"
                        else:
                            failure_type = failure_subtype

        mechanical_success = bool(
            actual_status == "generated" and
            validation.get("unified_diff_valid") and
            validation.get("path_match") and
            validation.get("size_within_limit") and
            validation.get("apply_check") and
            validation.get("structural_sanity")
        )
        semantic_success = bool(mechanical_success and semantic_match)

        res_item = {
            "scenario_id": sid,
            "title": title,
            "split": split,
            "role": role,
            "difficulty": sc["difficulty"],
            "eligibility_expected": is_elig_exp,
            "eligibility_actual": elig_actual,
            "expected_fix_status": exp_status,
            "actual_fix_status": actual_status,
            "old_text": old_text,
            "new_text": new_text,
            "match_mode": match_mode,
            "validation": validation,
            "mechanical_success": mechanical_success,
            "canonical_source_match": canonical_source_match,
            "token_equivalent": token_equivalent,
            "semantic_oracle_pass": semantic_oracle_pass,
            "semantic_match": semantic_match,
            "semantic_match_mode": semantic_match_mode,
            "semantic_success": semantic_success,
            "ground_truth_match": canonical_source_match,  # alias for backward compatibility
            "extra_changed_lines": extra_changed_lines,
            "failure_type": failure_type,
            "failure_subtype": failure_subtype,
            "skip_reason": skip_reason,
            "rejection_reason": rejection_reason,
            "diff": diff_text,
            "explanation": agent_output.get("explanation", "")
        }
        results.append(res_item)

    elapsed = round(time.time() - start_time, 2)
    output_data = {
        "split": split,
        "backend": backend,
        "model_id": model_id,
        "execution_time_seconds": elapsed,
        "total_scenarios": len(results),
        "results": results
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        print(f"\nResults saved to: {output_path}")

    return output_data


def main():
    parser = argparse.ArgumentParser(description="Run Fix Agent V1 Evaluation")
    parser.add_argument("--split", type=str, default="DEV", choices=["DEV", "HOLDOUT"], help="Dataset split")
    parser.add_argument("--backend", type=str, default="mock", choices=["mock", "transformers", "hf", "openai"], help="Model backend")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-Coder-7B-Instruct", help="Model ID")
    parser.add_argument("--quantization", type=str, default="4bit", help="Quantization")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--api-base", type=str, default=None, help="API Base")
    parser.add_argument("--api-key", type=str, default=None, help="API Key")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")

    args = parser.parse_args()
    out_p = Path(args.output) if args.output else EVAL_DIR / "results" / f"{args.backend}_{args.split.lower()}.json"

    run_evaluation(
        split=args.split,
        backend=args.backend,
        model_id=args.model,
        quantization=args.quantization,
        device=args.device,
        api_base=args.api_base,
        api_key=args.api_key,
        output_path=out_p
    )


if __name__ == "__main__":
    main()
