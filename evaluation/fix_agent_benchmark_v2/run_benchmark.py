"""
Evaluation Execution Runner for Fix Agent Benchmark V2
Executes production Fix Agent across synthetic benchmark scenarios.

Supports:
- DEV split (default, 56 scenarios)
- HOLDOUT split (24 scenarios, with prominent one-shot warning)
- mock backend (for CI/testing, GPU-free)
- transformers backend (Qwen/Qwen2.5-Coder-7B-Instruct)
"""

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIX_V1_DIR = REPO_ROOT / "evaluation" / "fix_agent_v1"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(FIX_V1_DIR) not in sys.path:
    sys.path.insert(0, str(FIX_V1_DIR))

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

BENCHMARK_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BENCHMARK_DIR / "scenarios.json"
SPLITS_FILE = BENCHMARK_DIR / "splits.json"


def load_benchmark_scenarios(split: str) -> List[Dict[str, Any]]:
    if not SCENARIOS_FILE.exists() or not SPLITS_FILE.exists():
        raise FileNotFoundError(f"Benchmark files missing in {BENCHMARK_DIR}")

    scenarios_data = json.loads(SCENARIOS_FILE.read_text(encoding="utf-8")).get("scenarios", [])
    splits_data = json.loads(SPLITS_FILE.read_text(encoding="utf-8"))

    allowed_ids = set(splits_data.get(split, []))
    if not allowed_ids:
        raise ValueError(f"No scenario IDs found for split '{split}' in {SPLITS_FILE}")

    filtered = [s for s in scenarios_data if s["scenario_id"] in allowed_ids]
    filtered.sort(key=lambda x: x["scenario_id"])
    return filtered


def run_benchmark(
    split: str = "DEV",
    backend: str = "mock",
    model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
    quantization: str = "4bit",
    device: str = "auto",
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    if split == "HOLDOUT":
        print("********************************************************************************")
        print("[WARNING] FINAL / ONE-SHOT HOLDOUT SPLIT SELECTED!")
        print("Results from this run must NEVER be used for prompt, eligibility, validator,")
        print("or oracle tuning. This is a one-shot validation test.")
        print("********************************************************************************\n")

    print("==================================================")
    print("FIX AGENT BENCHMARK V2 EXECUTION HARNESS")
    print("==================================================")
    print(f"Split       : {split}")
    print(f"Backend     : {backend}")
    print(f"Model ID    : {model_id}")
    print("==================================================")

    scenarios = load_benchmark_scenarios(split)
    print(f"Loaded {len(scenarios)} scenario(s) for split '{split}'.\n")

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
    start_time = time.time()

    for idx, sc in enumerate(scenarios, 1):
        sid = sc["scenario_id"]
        title = sc["title"]
        role = sc["role"]
        fpath = sc["file_path"]
        is_elig_exp = sc["eligibility_expected"]
        diff_level = sc["difficulty"]
        fix_comp = sc.get("fix_complexity", "single_line")
        alt_valid = sc.get("alternative_valid_fix", False)
        oracle_spec = sc.get("semantic_oracle")

        print(f"[{idx}/{len(scenarios)}] Evaluating {sid}: {title} ({role}, {diff_level})...")

        src_path = BENCHMARK_DIR / sc["source_fixture"]
        before_text = src_path.read_text(encoding="utf-8") if src_path.exists() else ""

        expected_after_text = None
        if sc.get("expected_after_fixture"):
            after_path = BENCHMARK_DIR / sc["expected_after_fixture"]
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
        oracle_applicable = bool(oracle_spec)
        semantic_oracle_pass = False
        semantic_match = False
        semantic_match_mode = None
        failure_subtype = None
        extra_changed_lines = 0
        failure_type = None

        if not is_elig_exp:
            # Expected skip
            if actual_status == "skipped":
                failure_type = "success"
                failure_subtype = "success_safe_skip"
            else:
                failure_type = "eligibility_unsafe_generate"
                failure_subtype = "eligibility_unsafe_generate"
        else:
            # Expected generate
            if actual_status == "skipped":
                failure_type = "eligibility_false_skip"
                failure_subtype = f"eligibility_false_skip_{skip_reason}"
            elif not validation.get("overall_valid", False):
                failure_type = agent_failure or "mechanical_failure"
                failure_subtype = rejection_reason or agent_failure or "mechanical_failure"
            else:
                # Mechanical checks passed -> run frozen semantic evaluation
                app_res = apply_unified_diff_to_text(before_text, diff_text)
                if not app_res["success"]:
                    failure_type = "mechanical_failure"
                    failure_subtype = "apply_failed"
                else:
                    patched_text = app_res["patched_text"]
                    if expected_after_text is not None:
                        sem_eval = evaluate_semantic_correctness(
                            patched_code=patched_text,
                            expected_after=expected_after_text,
                            oracle_spec=oracle_spec
                        )
                        canonical_source_match = sem_eval["canonical_source_match"]
                        token_equivalent = sem_eval["token_equivalent"]
                        oracle_applicable = sem_eval["oracle_applicable"]
                        semantic_oracle_pass = sem_eval["semantic_oracle_pass"]
                        semantic_match = sem_eval["semantic_match"]
                        semantic_match_mode = sem_eval["semantic_match_mode"]
                        failure_subtype = sem_eval["failure_subtype"]
                        failure_type = "success" if semantic_match else failure_subtype
                    else:
                        failure_type = "unknown"
                        failure_subtype = "no_expected_fixture"

        mechanical_success = (
            is_elig_exp
            and elig_actual
            and actual_status == "generated"
            and validation.get("overall_valid", False)
            and validation.get("apply_check", False)
        )

        item_result = {
            "scenario_id": sid,
            "title": title,
            "role": role,
            "difficulty": diff_level,
            "fix_complexity": fix_comp,
            "alternative_valid_fix": alt_valid,
            "eligibility_expected": is_elig_exp,
            "eligibility_actual": elig_actual,
            "eligibility_correct": (elig_actual == is_elig_exp),
            "expected_fix_status": sc.get("expected_fix_status", "generated" if is_elig_exp else "skipped"),
            "actual_fix_status": actual_status,
            "skip_reason": skip_reason,
            "rejection_reason": rejection_reason,
            "diff": diff_text,
            "old_text": old_text,
            "new_text": new_text,
            "match_mode": match_mode,
            "validation": validation,
            "mechanical_success": mechanical_success,
            "canonical_source_match": canonical_source_match,
            "token_equivalent": token_equivalent,
            "oracle_applicable": oracle_applicable,
            "semantic_oracle_pass": semantic_oracle_pass,
            "semantic_match": semantic_match,
            "semantic_match_mode": semantic_match_mode,
            "semantic_success": semantic_match,
            "failure_type": failure_type,
            "failure_subtype": failure_subtype,
            "extra_changed_lines": extra_changed_lines
        }
        results.append(item_result)

    elapsed = time.time() - start_time
    output_data = {
        "benchmark_version": "2.0",
        "split": split,
        "backend": backend,
        "model_id": model_id,
        "total_scenarios": len(scenarios),
        "elapsed_seconds": round(elapsed, 2),
        "results": results
    }

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        print(f"\nResults saved to: {out_p}")

    return output_data


def main():
    parser = argparse.ArgumentParser(description="Run Fix Agent Benchmark V2 Harness")
    parser.add_argument("--split", choices=["DEV", "HOLDOUT"], default="DEV", help="Benchmark split to evaluate (default: DEV)")
    parser.add_argument("--backend", choices=["mock", "transformers"], default="mock", help="Backend type")
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-Coder-7B-Instruct", help="Hugging Face model ID")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    parser.add_argument("--quantization", default="4bit", choices=["4bit", "8bit", "none"])
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--output", default=None, help="Path to output JSON")

    args = parser.parse_args()

    default_out = BENCHMARK_DIR / "results" / f"{args.backend}_{args.split.lower()}.json"
    out_file = args.output or str(default_out)

    run_benchmark(
        split=args.split,
        backend=args.backend,
        model_id=args.model_id,
        quantization=args.quantization,
        device=args.device,
        api_base=args.api_base,
        api_key=args.api_key,
        output_path=out_file
    )


if __name__ == "__main__":
    main()
