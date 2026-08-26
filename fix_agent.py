"""
Fix Agent V1 Orchestration Module
Coordinates:
1. Finding Eligibility Gate
2. Source Context & Diff Extraction
3. Model Inference (reusing existing Qwen/Transformers instance or Mock backend)
4. Deterministic Patch Safety Validation
5. Output Schema Formatting
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fix_eligibility import check_fix_eligibility
from fix_agent_prompt_builder import (
    FIX_AGENT_SYSTEM_PROMPT,
    FIX_AGENT_SYSTEM_PROMPT_V2,
    FIX_AGENT_SYSTEM_PROMPT_V3,
    build_fix_agent_prompt
)
from structured_edit_validator import validate_and_apply_structured_edit
from mock_fix_agent import run_deterministic_mock_fix

logger = logging.getLogger("fix_agent")


def parse_fix_agent_json(raw_text: str, finding_id: str, file_path: str, strategy: str = "v2") -> Dict[str, Any]:
    """
    Parses model JSON response for Fix Agent structured edits.
    Supports both V2 (old_text -> new_text) and V3 (target_statement -> fix_explanation -> new_text).
    In V3, old_text is deterministically derived from target_statement.
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
                "finding_id": finding_id,
                "file_path": file_path,
                "fix_status": "rejected",
                "diff": "",
                "old_text": "",
                "new_text": "",
                "explanation": "Response is not a valid JSON object.",
                "skip_reason": None,
                "rejection_reason": "invalid_json_format",
                "failure_type": "invalid_model_schema"
            }

        status = str(data.get("fix_status", "skipped")).lower()
        if status not in ("generated", "skipped", "rejected"):
            status = "skipped"

        target_stmt = str(data.get("target_statement") or "").strip()
        old_text_raw = str(data.get("old_text") or "")
        new_text = str(data.get("new_text", ""))
        explanation = str(data.get("fix_explanation") or data.get("explanation", ""))

        if strategy.lower() == "v3":
            if status == "generated":
                if target_stmt:
                    old_text = target_stmt
                elif old_text_raw:
                    # Fallback if model provided old_text instead of target_statement
                    old_text = old_text_raw
                    target_stmt = old_text_raw
                else:
                    return {
                        "finding_id": data.get("finding_id", finding_id),
                        "file_path": data.get("file_path", file_path),
                        "fix_status": "rejected",
                        "diff": "",
                        "old_text": "",
                        "new_text": new_text,
                        "explanation": explanation,
                        "skip_reason": None,
                        "rejection_reason": "missing_target_statement",
                        "failure_type": "invalid_model_schema"
                    }
            else:
                old_text = ""
        else:
            old_text = old_text_raw

        res = {
            "finding_id": data.get("finding_id", finding_id),
            "file_path": data.get("file_path", file_path),
            "fix_status": status,
            "old_text": old_text,
            "new_text": new_text,
            "explanation": explanation,
            "skip_reason": data.get("skip_reason"),
            "rejection_reason": data.get("rejection_reason")
        }
        if target_stmt:
            res["target_statement"] = target_stmt
        if "fix_explanation" in data or strategy.lower() == "v3":
            res["fix_explanation"] = explanation
        return res
    except Exception as e:
        return {
            "finding_id": finding_id,
            "file_path": file_path,
            "fix_status": "rejected",
            "diff": "",
            "old_text": "",
            "new_text": "",
            "explanation": f"JSON parse error: {str(e)}",
            "skip_reason": None,
            "rejection_reason": "json_parse_error",
            "failure_type": "invalid_model_schema"
        }


def run_fix_agent_for_finding(
    finding: Dict[str, Any],
    worktree_path: Optional[Path] = None,
    backend: str = "mock",
    loaded_model: Any = None,
    tokenizer: Any = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
    dry_run: bool = False,
    pr_changed_files: Optional[List[str]] = None,
    strategy: str = "v2"
) -> Dict[str, Any]:
    """
    Processes a single verified finding through eligibility, generation, and validation.
    Supports strategy='v2' (default) and strategy='v3' (Reasoning-Guided Target Statement Grounding).
    """
    fid = finding.get("candidate_id") or finding.get("finding_id", "cand-1")
    file_rel = finding.get("file") or finding.get("file_path") or ""

    # Load local file content if available in worktree
    file_content = ""
    if worktree_path and file_rel:
        full_file = worktree_path / file_rel
        if full_file.exists():
            try:
                file_content = full_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    if not file_content:
        file_content = finding.get("after_source", "")

    # 1. Eligibility Check
    eligibility = check_fix_eligibility(finding, file_content=file_content)
    if not eligibility["eligible"]:
        return {
            "finding_id": fid,
            "file_path": file_rel,
            "fix_status": "skipped",
            "diff": "",
            "old_text": "",
            "new_text": "",
            "explanation": "Finding not eligible for automated patch generation in V1.",
            "match_mode": None,
            "validation": {
                "unified_diff_valid": False,
                "path_match": False,
                "size_within_limit": False,
                "apply_check": False,
                "structural_sanity": False
            },
            "skip_reason": eligibility["reason"],
            "rejection_reason": None,
            "failure_type": eligibility["reason"]
        }

    # Extract surrounding source context
    source_context = file_content or finding.get("after_source", "")

    # Select system prompt according to strategy
    system_prompt = FIX_AGENT_SYSTEM_PROMPT_V3 if strategy.lower() == "v3" else FIX_AGENT_SYSTEM_PROMPT_V2

    # 2. Mock / Dry-run Backend
    if backend == "mock" or dry_run:
        return run_deterministic_mock_fix(
            finding=finding,
            file_path=file_rel,
            source_content=file_content,
            diff_hunk="",
            pr_changed_files=pr_changed_files,
            strategy=strategy
        )

    # 3. Production Transformers Backend
    elif backend in ("transformers", "hf"):
        if loaded_model is None or tokenizer is None:
            return {
                "finding_id": fid,
                "file_path": file_rel,
                "fix_status": "rejected",
                "diff": "",
                "old_text": "",
                "new_text": "",
                "explanation": "Model backend not initialized.",
                "match_mode": None,
                "validation": {
                    "unified_diff_valid": False,
                    "path_match": False,
                    "size_within_limit": False,
                    "apply_check": False,
                    "structural_sanity": False
                },
                "skip_reason": None,
                "rejection_reason": "model_not_initialized",
                "failure_type": "patch_generation_failed"
            }

        import torch
        user_prompt = build_fix_agent_prompt(
            finding=finding,
            file_path=file_rel,
            source_context=source_context,
            diff_hunk="",
            strategy=strategy
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt_text, return_tensors="pt").to(loaded_model.device)
        with torch.no_grad():
            outputs = loaded_model.generate(**inputs, max_new_tokens=512, do_sample=False, temperature=0.0)
        gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(gen_tokens, skip_special_tokens=True)
        parsed = parse_fix_agent_json(raw, fid, file_rel, strategy=strategy)

        if parsed["fix_status"] == "skipped":
            return {
                **parsed,
                "diff": "",
                "match_mode": None,
                "validation": {
                    "unified_diff_valid": False,
                    "path_match": False,
                    "size_within_limit": False,
                    "apply_check": False,
                    "structural_sanity": False
                },
                "failure_type": "model_skipped"
            }
        elif parsed["fix_status"] == "rejected":
            return {
                **parsed,
                "diff": "",
                "match_mode": None,
                "validation": {
                    "unified_diff_valid": False,
                    "path_match": False,
                    "size_within_limit": False,
                    "apply_check": False,
                    "structural_sanity": False
                },
                "failure_type": parsed.get("failure_type", "invalid_model_schema")
            }

        # 4. Structured Edit Grounding, Replacement & Diff Synthesis
        val_res = validate_and_apply_structured_edit(
            structured_edit=parsed,
            finding=finding,
            source_content=file_content,
            pr_changed_files=pr_changed_files
        )
        return val_res

    # 5. OpenAI API Backend
    elif backend == "openai":
        import urllib.request
        user_prompt = build_fix_agent_prompt(
            finding=finding,
            file_path=file_rel,
            source_context=source_context,
            diff_hunk="",
            strategy=strategy
        )
        url = f"{api_base or 'http://localhost:8000/v1'}/chat/completions"
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 512
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
            raw = resp_json["choices"][0]["message"]["content"]
            parsed = parse_fix_agent_json(raw, fid, file_rel, strategy=strategy)

        if parsed["fix_status"] == "skipped":
            return {
                **parsed,
                "diff": "",
                "match_mode": None,
                "validation": {
                    "unified_diff_valid": False,
                    "path_match": False,
                    "size_within_limit": False,
                    "apply_check": False,
                    "structural_sanity": False
                },
                "failure_type": "model_skipped"
            }
        elif parsed["fix_status"] == "rejected":
            return {
                **parsed,
                "diff": "",
                "match_mode": None,
                "validation": {
                    "unified_diff_valid": False,
                    "path_match": False,
                    "size_within_limit": False,
                    "apply_check": False,
                    "structural_sanity": False
                },
                "failure_type": parsed.get("failure_type", "invalid_model_schema")
            }

        val_res = validate_and_apply_structured_edit(
            structured_edit=parsed,
            finding=finding,
            source_content=file_content,
            pr_changed_files=pr_changed_files
        )
        return val_res

    else:
        raise ValueError(f"Unknown backend: {backend}")


def generate_fix_suggestions(
    verified_findings: List[Dict[str, Any]],
    worktree_path: Optional[Path] = None,
    backend: str = "mock",
    loaded_model: Any = None,
    tokenizer: Any = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Generates fix suggestions for all verified findings.
    Only invokes backend if findings are eligible.
    """
    if not verified_findings:
        return []

    suggestions = []
    for finding in verified_findings:
        res = run_fix_agent_for_finding(
            finding=finding,
            worktree_path=worktree_path,
            backend=backend,
            loaded_model=loaded_model,
            tokenizer=tokenizer,
            api_base=api_base,
            api_key=api_key,
            model_id=model_id,
            dry_run=dry_run
        )
        suggestions.append(res)
    return suggestions
