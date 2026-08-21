"""
Semantic Verifier Model Runner for Benchmark V2 Bake-Off
Executes structured semantic verification requests across supported LLM backbones
(Qwen2.5-Coder-7B, Qwen2.5-Coder-14B, DeepSeek-Coder-V2-Lite, OpenAI/Compatible API, Mock Model).

Supports:
- Checkpoint / Resume on candidate_id granularity
- Atomic and safe record append
- Strict JSON output format parsing with Markdown fence stripping
- Hardware and latency metadata tracking
- Windows and Colab execution
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

# Standardized Semantic Verifier System Prompt
SEMANTIC_VERIFIER_SYSTEM_PROMPT = """You are an expert Java/Spring Code Review Verifier.
Your task is to verify whether a proposed code review finding is accurate, valid, and within the scope of the reviewer role.

Input provided for each candidate:
- Candidate Problem: The specific issue reported by the reviewer.
- Failure Scenario: The described runtime or structural breakdown.
- Source Reviewer: The designated reviewer role (correctness_logic, security_validation, or maintainability).
- Git Diff: The changes introduced in the Pull Request.
- After Source Code: Full method context after applying the change.

Verification Rules:
1. 'problem_present': true if and only if the exact problem described by the candidate genuinely exists in the modified code.
2. 'role_match': true if the issue is strictly within the scope of the assigned 'source_reviewer' role:
   - correctness_logic: bugs, NPEs, incorrect conditionals, off-by-one errors, state mutation errors, resource leaks.
   - security_validation: vulnerabilities, hardcoded secrets, authentication/authorization bypasses, injection, PII exposure.
   - maintainability: unused variables, dead code, code duplication, redundant boolean expressions.
3. Be objective and avoid hallucinated defects. If code includes safe guards, defensive checks, or proper resource closures, problem_present must be false.

Output Schema:
You MUST respond with a single, valid JSON object strictly matching this schema:
{
  "candidate_id": "<candidate_id>",
  "problem_present": true | false,
  "role_match": true | false,
  "reason": "<clear explanation of your verification decision>",
  "evidence": "<code quote or explanation of absence>"
}"""


def build_semantic_verifier_user_prompt(request: Dict[str, Any]) -> str:
    """Builds the standardized user prompt for a semantic request."""
    return f"""Candidate ID: {request.get('candidate_id')}
Scenario ID: {request.get('scenario_id')}
File Path: {request.get('file_path')}
Changed Method: {request.get('changed_method')}
Source Reviewer: {request.get('source_reviewer')}

Candidate Problem:
{request.get('problem')}

Failure Scenario:
{request.get('failure_scenario')}

PR Diff:
```diff
{request.get('diff')}
```

Full Changed Method Context:
```java
{request.get('after_source')}
```

Verify this candidate and output the JSON verdict."""


def parse_model_json_response(raw_text: str, candidate_id: str) -> Dict[str, Any]:
    """
    Robust JSON parser for semantic verifier output.
    Strips markdown code blocks and handles common JSON malformations.
    """
    cleaned = raw_text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return {
                "candidate_id": candidate_id,
                "problem_present": False,
                "role_match": False,
                "reason": "Parsed output is not a JSON object",
                "evidence": "",
                "parse_error": True
            }

        prob_present = data.get("problem_present")
        role_match = data.get("role_match")
        
        # Validate boolean types strictly
        if not isinstance(prob_present, bool) or not isinstance(role_match, bool):
            return {
                "candidate_id": candidate_id,
                "problem_present": bool(prob_present) if prob_present is not None else False,
                "role_match": bool(role_match) if role_match is not None else False,
                "reason": str(data.get("reason", "Non-boolean fields")),
                "evidence": str(data.get("evidence", "")),
                "parse_error": True
            }

        return {
            "candidate_id": data.get("candidate_id", candidate_id),
            "problem_present": prob_present,
            "role_match": role_match,
            "reason": str(data.get("reason", "")),
            "evidence": str(data.get("evidence", "")),
            "parse_error": False
        }
    except Exception as e:
        return {
            "candidate_id": candidate_id,
            "problem_present": False,
            "role_match": False,
            "reason": f"JSON parse error: {str(e)}",
            "evidence": "",
            "parse_error": True
        }


class SemanticBakeoffRunner:
    def __init__(
        self,
        model_id: str,
        backend: str = "mock",
        output_file: Optional[Path] = None,
        quantization: str = "none",
        device: str = "auto",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.model_id = model_id
        self.backend = backend
        self.output_file = output_file
        self.quantization = quantization
        self.device = device
        self.api_base = api_base
        self.api_key = api_key
        self.loaded_model = None
        self.tokenizer = None

    def initialize_backend(self):
        """Initializes backend model if using local transformers/vllm/openai."""
        if self.backend == "mock":
            print(f"Initialized Mock Backend for model: {self.model_id}")
            return

        if self.backend in ("transformers", "hf"):
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
                print(f"Loading {self.model_id} via HuggingFace Transformers...")

                is_deepseek_v2 = "deepseek-coder-v2" in self.model_id.lower()

                # GPU compute dtype automatic selection (T4 capability 7.5 uses float16, Ampere+ uses bfloat16)
                if torch.cuda.is_available():
                    major, minor = torch.cuda.get_device_capability(0)
                    compute_dtype = torch.bfloat16 if major >= 8 else torch.float16
                else:
                    compute_dtype = torch.float32

                bnb_config = None
                if self.quantization == "4bit":
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=compute_dtype,
                        bnb_4bit_use_double_quant=True
                    )

                trust_remote_code_flag = False if is_deepseek_v2 else True
                attn_impl = "eager" if is_deepseek_v2 else None

                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_id,
                    trust_remote_code=trust_remote_code_flag
                )

                model_kwargs = {
                    "quantization_config": bnb_config,
                    "device_map": self.device,
                    "torch_dtype": compute_dtype if self.quantization != "4bit" else None,
                    "trust_remote_code": trust_remote_code_flag
                }
                if attn_impl is not None:
                    model_kwargs["attn_implementation"] = attn_impl

                self.loaded_model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    **model_kwargs
                )

                print("=========================================")
                print("MODEL LOADED SUCCESSFULLY")
                print("=========================================")
                print(f"Model ID              : {self.model_id}")
                print(f"Compute Dtype         : {compute_dtype}")
                print(f"Quantization          : {self.quantization}")
                print(f"Attention Impl        : {attn_impl or 'default'}")
                print(f"Trust Remote Code     : {trust_remote_code_flag}")
                print("=========================================")
            except Exception as e:
                print(f"Error loading model {self.model_id}: {e}", file=sys.stderr)
                raise

    def infer_single(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Runs inference for a single request record."""
        cand_id = request.get("candidate_id", "unknown")
        user_prompt = build_semantic_verifier_user_prompt(request)
        start_time = time.time()

        if self.backend == "mock":
            # Mock predictable responses based on candidate_id metadata for testing
            time.sleep(0.01)
            raw_response = json.dumps({
                "candidate_id": cand_id,
                "problem_present": False,
                "role_match": True,
                "reason": "Mock verifier output",
                "evidence": ""
            })
        elif self.backend in ("transformers", "hf"):
            import torch
            messages = [
                {"role": "system", "content": SEMANTIC_VERIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            prompt_text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.loaded_model.device)
            
            with torch.no_grad():
                outputs = self.loaded_model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                    temperature=0.0
                )
            generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            raw_response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        elif self.backend == "openai":
            import urllib.request
            # Minimal zero-dependency standard library HTTP request for OpenAI-compatible endpoints
            url = f"{self.api_base or 'http://localhost:8000/v1'}/chat/completions"
            payload = {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": SEMANTIC_VERIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 512
            }
            req_data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            req = urllib.request.Request(url, data=req_data, headers=headers)
            with urllib.request.urlopen(req) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                raw_response = resp_json["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

        latency = round(time.time() - start_time, 3)
        parsed = parse_model_json_response(raw_response, cand_id)

        return {
            "candidate_id": cand_id,
            "scenario_id": request.get("scenario_id"),
            "model_id": self.model_id,
            "raw_response": raw_response,
            "parsed_response": parsed,
            "parse_error": parsed.get("parse_error", False),
            "latency_seconds": latency
        }

    def run_batch(self, requests_file: Path, resume: bool = True) -> List[Dict[str, Any]]:
        """Processes all requests with checkpoint/resume safety."""
        with open(requests_file, "r", encoding="utf-8") as f:
            requests = json.load(f)

        existing_results = []
        completed_ids = set()

        if self.output_file and self.output_file.exists() and resume:
            try:
                with open(self.output_file, "r", encoding="utf-8") as f:
                    existing_results = json.load(f)
                    for r in existing_results:
                        completed_ids.add(r.get("candidate_id"))
                print(f"Resuming bake-off: found {len(completed_ids)} completed candidates in {self.output_file.name}")
            except Exception as e:
                print(f"Warning: Could not read existing output file for resume: {e}")

        self.initialize_backend()

        all_results = list(existing_results)
        total = len(requests)

        for idx, req in enumerate(requests, start=1):
            cid = req.get("candidate_id")
            if cid in completed_ids:
                continue

            print(f"[{idx}/{total}] Inferring candidate {cid} with {self.model_id}...")
            try:
                res = self.infer_single(req)
            except Exception as e:
                print(f"Error during inference on {cid}: {e}", file=sys.stderr)
                res = {
                    "candidate_id": cid,
                    "scenario_id": req.get("scenario_id"),
                    "model_id": self.model_id,
                    "raw_response": "",
                    "parsed_response": {
                        "candidate_id": cid,
                        "problem_present": False,
                        "role_match": False,
                        "reason": f"Inference execution error: {str(e)}",
                        "evidence": "",
                        "parse_error": True
                    },
                    "parse_error": True,
                    "latency_seconds": 0.0
                }

            all_results.append(res)
            completed_ids.add(cid)

            # Checkpoint safe write after each candidate
            if self.output_file:
                temp_file = self.output_file.with_suffix(".tmp")
                temp_file.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
                temp_file.replace(self.output_file)

        print(f"Batch completed: {len(all_results)} results saved.")
        return all_results


def main():
    parser = argparse.ArgumentParser(description="Run Semantic Verifier Model Bake-Off")
    parser.add_argument("--requests", type=str, default=str(BASE_DIR / "reports" / "semantic_verifier_requests_DEV.json"), help="Path to semantic requests JSON")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-Coder-7B-Instruct", help="Model ID")
    parser.add_argument("--backend", type=str, default="mock", choices=["mock", "transformers", "hf", "openai"], help="Execution backend")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--quantization", type=str, default="none", choices=["none", "4bit", "8bit"], help="Quantization mode")
    parser.add_argument("--device", type=str, default="auto", help="Device mapping (cuda, cpu, auto)")
    parser.add_argument("--api-base", type=str, default=None, help="OpenAI-compatible API Base URL")
    parser.add_argument("--api-key", type=str, default=None, help="API Key")
    parser.add_argument("--no-resume", action="store_true", help="Disable checkpoint resume")

    args = parser.parse_args()

    requests_p = Path(args.requests)
    if not requests_p.exists():
        print(f"Error: Requests file not found: {requests_p}", file=sys.stderr)
        sys.exit(1)

    out_p = Path(args.output) if args.output else BASE_DIR / "reports" / f"semantic_results_{args.model.replace('/', '_')}_DEV.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)

    runner = SemanticBakeoffRunner(
        model_id=args.model,
        backend=args.backend,
        output_file=out_p,
        quantization=args.quantization,
        device=args.device,
        api_base=args.api_base,
        api_key=args.api_key
    )

    runner.run_batch(requests_p, resume=not args.no_resume)


if __name__ == "__main__":
    main()
