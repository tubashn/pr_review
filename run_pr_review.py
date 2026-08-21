"""
End-to-End Pull Request Review MVP Runner
Orchestrates:
1. Target repo validation and isolated temporary worktree creation
2. Java PR diff & code context extraction
3. Static PMD analysis integration (optional/graceful fallback)
4. Multi-role candidate reviewer generation (correctness, security, maintainability)
5. Hierarchical Verification Pipeline:
   - Tier 1: Deterministic Static / Direct Checks
   - Tier 2: Java AST Null-Safety & Structural Self-Refutation
   - Tier 3: Deterministic Absence & Canonical Role Gate
   - Tier 4: Semantic Verifier (Qwen2.5-Coder-7B-Instruct / OpenAI API / Mock)
6. Deduplication & finding merger
7. Clean summary and comprehensive JSON report generation
8. Guaranteed cleanup of temporary worktree (No persistent side-effects on target repo)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Local imports from pr_review modules
from pr_diff_extractor import parse_diff_hunks
from reviewer_prompt_builder import format_pr_diff
from verifier_prompt_builder import (
    classify_grounding_strategy,
    get_deterministic_canonical_issue_kind,
    is_deterministic_role_compatible,
    STRATEGY_DIRECT,
    STRATEGY_ABSENCE_REFERENCE,
    STRATEGY_ABSENCE_RESOURCE_CLEANUP
)
from java_ast_analyzer import verify_null_safety_self_refutation


# Semantic Verifier Prompt & Parser
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


def parse_verifier_json(raw_text: str, candidate_id: str) -> Dict[str, Any]:
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
                "reason": "Output is not a valid JSON object",
                "evidence": "",
                "parse_error": True
            }

        prob_present = data.get("problem_present")
        role_match = data.get("role_match")
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


class PRReviewRunner:
    def __init__(
        self,
        repo_path: Path,
        branch: str,
        base_branch: str = "main",
        model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
        backend: str = "mock",
        quantization: str = "none",
        device: str = "auto",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        run_pmd: bool = False,
        dry_run: bool = False
    ):
        self.repo_path = repo_path.resolve()
        self.branch = branch
        self.base_branch = base_branch
        self.model_id = model_id
        self.backend = backend
        self.quantization = quantization
        self.device = device
        self.api_base = api_base
        self.api_key = api_key
        self.run_pmd = run_pmd
        self.dry_run = dry_run

        self.temp_worktree_path: Optional[Path] = None
        self.loaded_model = None
        self.tokenizer = None

    def create_worktree(self) -> Path:
        """Creates an isolated temporary worktree for the target branch without modifying target repo."""
        temp_dir = tempfile.mkdtemp(prefix="pr_review_wt_")
        self.temp_worktree_path = Path(temp_dir).resolve()
        print(f"[1/6] Creating isolated temporary git worktree at {self.temp_worktree_path}...")

        # Determine git target ref: check local or origin
        branch_ref = self.branch
        check_local = subprocess.run(["git", "rev-parse", "--verify", self.branch], cwd=str(self.repo_path), capture_output=True)
        if check_local.returncode != 0:
            check_origin = subprocess.run(["git", "rev-parse", "--verify", f"origin/{self.branch}"], cwd=str(self.repo_path), capture_output=True)
            if check_origin.returncode == 0:
                branch_ref = f"origin/{self.branch}"
            else:
                raise ValueError(f"Branch '{self.branch}' not found locally or on origin in {self.repo_path}")

        res = subprocess.run(
            ["git", "worktree", "add", "--detach", str(self.temp_worktree_path), branch_ref],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create git worktree:\n{res.stderr}")

        return self.temp_worktree_path

    def cleanup_worktree(self):
        """Safely removes temporary worktree and purges worktree locks."""
        if self.temp_worktree_path and self.temp_worktree_path.exists():
            print(f"[Cleanup] Removing temporary worktree {self.temp_worktree_path}...")
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(self.temp_worktree_path)],
                    cwd=str(self.repo_path),
                    capture_output=True
                )
            except Exception:
                pass
            try:
                subprocess.run(["git", "worktree", "prune"], cwd=str(self.repo_path), capture_output=True)
            except Exception:
                pass
            if self.temp_worktree_path.exists():
                shutil.rmtree(self.temp_worktree_path, ignore_errors=True)

    def extract_pr_diff(self) -> Tuple[List[Dict[str, Any]], str]:
        """Extracts unified diff for changed Java files between base_branch and PR branch."""
        print(f"[2/6] Extracting Java diff between {self.base_branch} and {self.branch}...")
        
        # Check diff base
        diff_base = self.base_branch
        res_base = subprocess.run(["git", "rev-parse", "--verify", f"origin/{self.base_branch}"], cwd=str(self.repo_path), capture_output=True)
        if res_base.returncode == 0:
            diff_base = f"origin/{self.base_branch}"

        branch_target = self.branch
        res_target = subprocess.run(["git", "rev-parse", "--verify", f"origin/{self.branch}"], cwd=str(self.repo_path), capture_output=True)
        if res_target.returncode == 0:
            branch_target = f"origin/{self.branch}"

        status_res = subprocess.run(
            ["git", "diff", "--name-status", f"{diff_base}...{branch_target}", "--", "*.java"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True
        )

        diff_results = []
        lines = status_res.stdout.splitlines()
        for line in lines:
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                status_char, file_path = parts
                status = "added" if status_char.startswith("A") else ("deleted" if status_char.startswith("D") else "modified")
                
                diff_cmd = subprocess.run(
                    ["git", "diff", "-U15", f"{diff_base}...{branch_target}", "--", file_path],
                    cwd=str(self.repo_path),
                    capture_output=True,
                    text=True
                )
                hunks = parse_diff_hunks(diff_cmd.stdout)
                diff_results.append({
                    "file": file_path,
                    "status": status,
                    "hunks": hunks
                })

        formatted_diff = format_pr_diff(diff_results)
        return diff_results, formatted_diff

    def run_static_pmd_analysis(self, worktree_path: Path) -> List[Dict[str, Any]]:
        """Optional static PMD scan inside worktree if Maven is available."""
        if not self.run_pmd:
            return []
        print("[PMD] Running static PMD analysis...")
        mvn_cmd = "mvn clean compile org.apache.maven.plugins:maven-pmd-plugin:3.28.0:pmd"
        try:
            res = subprocess.run(mvn_cmd, shell=True, cwd=str(worktree_path), capture_output=True, text=True)
            pmd_report_path = worktree_path / "target" / "pmd.xml"
            if pmd_report_path.exists():
                import xml.etree.ElementTree as ET
                tree = ET.parse(pmd_report_path)
                root = tree.getroot()
                findings = []
                for file_element in root.findall(".//{*}file"):
                    absolute_file = file_element.attrib.get("name", "")
                    try:
                        file_name = str(Path(absolute_file).resolve().relative_to(worktree_path.resolve()))
                    except ValueError:
                        file_name = absolute_file
                    for violation in file_element.findall("{*}violation"):
                        findings.append({
                            "tool": "PMD",
                            "file": file_name,
                            "line": int(violation.attrib.get("beginline", 0)),
                            "end_line": int(violation.attrib.get("endline", 0)),
                            "rule": violation.attrib.get("rule", ""),
                            "ruleset": violation.attrib.get("ruleset", ""),
                            "priority": int(violation.attrib.get("priority", 5)),
                            "message": (violation.text or "").strip(),
                        })
                return findings
        except Exception as e:
            print(f"[PMD Warning] PMD scan skipped: {e}")
        return []

    def generate_candidate_findings(self, diff_results: List[Dict[str, Any]], worktree_path: Path, pmd_signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generates candidate findings for 3 specialized roles:
        - correctness_logic
        - security_validation
        - maintainability
        Integrates structural heuristics, AST checks, PMD static signals, and diff inspections.
        """
        print("[3/6] Generating candidate findings across 3 reviewer roles...")
        candidates = []
        cand_id_counter = 0

        for file_data in diff_results:
            file_rel = file_data.get("file", "")
            file_full = worktree_path / file_rel
            file_content = ""
            if file_full.exists():
                try:
                    file_content = file_full.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            for hunk in file_data.get("hunks", []):
                added_lines = [item for item in hunk if item.get("type") == "ADDED"]
                for item in added_lines:
                    line_no = item.get("new_line")
                    code = item.get("code", "")

                    # 1. Maintainability Checks (Unused variables, Redundant booleans)
                    if re.search(r"==\s*true|==\s*false|!=\s*false|!=\s*true", code):
                        cand_id_counter += 1
                        candidates.append({
                            "candidate_id": f"cand-{cand_id_counter}",
                            "source_reviewer": "maintainability",
                            "file": file_rel,
                            "line": line_no,
                            "code_snippet": code,
                            "after_source": file_content,
                            "problem": f"Redundant boolean comparison in expression: `{code.strip()}`.",
                            "failure_scenario": "Simplifying boolean comparison improves readability and maintainability.",
                            "suggested_fix": "Simplify boolean comparison expression directly."
                        })

                    var_decl_match = re.search(r"\b(?:String|int|long|boolean|double|StringBuilder|List<[^>]+>|Map<[^>]+>)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", code)
                    if var_decl_match:
                        var_name = var_decl_match.group(1)
                        if file_content and len(re.findall(r"\b" + re.escape(var_name) + r"\b", file_content)) <= 1:
                            cand_id_counter += 1
                            candidates.append({
                                "candidate_id": f"cand-{cand_id_counter}",
                                "source_reviewer": "maintainability",
                                "file": file_rel,
                                "line": line_no,
                                "code_snippet": code,
                                "after_source": file_content,
                                "problem": f"Unused local variable `{var_name}` is declared and assigned but never used in method scope.",
                                "failure_scenario": "Dead local variable allocation creates code clutter.",
                                "suggested_fix": f"Remove unused variable `{var_name}`."
                            })

                    # 2. Correctness & Resource Checks (Unclosed streams, obvious logic errors)
                    if re.search(r"new\s+(?:FileInputStream|FileReader|BufferedReader|ZipFile|SocketChannel)\b", code):
                        if "try" not in code and file_content and "close()" not in file_content and "try (" not in file_content:
                            cand_id_counter += 1
                            candidates.append({
                                "candidate_id": f"cand-{cand_id_counter}",
                                "source_reviewer": "correctness_logic",
                                "file": file_rel,
                                "line": line_no,
                                "code_snippet": code,
                                "after_source": file_content,
                                "problem": f"Unclosed resource: `{code.strip()}` opened without try-with-resources or close() cleanup.",
                                "failure_scenario": "Unclosed I/O streams cause operating system file descriptor leaks.",
                                "suggested_fix": "Enclose resource allocation in a try-with-resources statement."
                            })

                    # 3. Security Checks (Hardcoded secrets, API keys, password literals)
                    if re.search(r'(?:password|secret|apikey|token|private_key)\s*=\s*"[^"]{6,}"|return\s+"(?:whsec_|sk_|admin|secret)[^"]*"', code, re.IGNORECASE):
                        cand_id_counter += 1
                        candidates.append({
                            "candidate_id": f"cand-{cand_id_counter}",
                            "source_reviewer": "security_validation",
                            "file": file_rel,
                            "line": line_no,
                            "code_snippet": code,
                            "after_source": file_content,
                            "problem": f"Hardcoded credential or secret literal exposed in source code: `{code.strip()}`.",
                            "failure_scenario": "Committing sensitive credentials enables unauthorized privilege escalation.",
                            "suggested_fix": "Extract credential into external environment variables or secrets manager."
                        })

        # Append PMD static signals as candidates if available
        for pmd in pmd_signals:
            cand_id_counter += 1
            rule = pmd.get("rule", "")
            role = "security_validation" if "security" in rule.lower() else ("maintainability" if "unused" in rule.lower() or "style" in rule.lower() else "correctness_logic")
            candidates.append({
                "candidate_id": f"cand-{cand_id_counter}",
                "source_reviewer": role,
                "file": pmd.get("file", ""),
                "line": pmd.get("line", 1),
                "code_snippet": pmd.get("message", ""),
                "after_source": "",
                "problem": f"Static Analysis [{pmd.get('tool')}]: {pmd.get('message')} (Rule: {rule})",
                "failure_scenario": "Static rule violation flagged by PMD.",
                "suggested_fix": f"Resolve {rule} violation."
            })

        return candidates

    def initialize_verifier_backend(self):
        """Initializes backend model if using local transformers or OpenAI API."""
        if self.backend == "mock" or self.dry_run:
            return

        if self.backend in ("transformers", "hf"):
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
                print(f"[Verifier] Loading {self.model_id} via HuggingFace Transformers...")

                is_deepseek_v2 = "deepseek-coder-v2" in self.model_id.lower()
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
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=trust_remote_code_flag)
                model_kwargs = {
                    "quantization_config": bnb_config,
                    "device_map": self.device,
                    "torch_dtype": compute_dtype if self.quantization != "4bit" else None,
                    "trust_remote_code": trust_remote_code_flag
                }
                if is_deepseek_v2:
                    model_kwargs["attn_implementation"] = "eager"

                self.loaded_model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)
                print(f"[Verifier] Model {self.model_id} ready.")
            except Exception as e:
                print(f"[Verifier Error] Failed to load model: {e}", file=sys.stderr)
                raise

    def run_semantic_inference(self, candidate: Dict[str, Any], formatted_diff: str) -> Dict[str, Any]:
        """Runs single semantic verifier inference."""
        cid = candidate["candidate_id"]
        user_prompt = f"""Candidate ID: {cid}
File Path: {candidate.get('file')}
Line: {candidate.get('line')}
Source Reviewer: {candidate.get('source_reviewer')}

Candidate Problem:
{candidate.get('problem')}

Failure Scenario:
{candidate.get('failure_scenario')}

PR Diff:
```diff
{formatted_diff}
```

Full Changed Method Context:
```java
{candidate.get('after_source', '')}
```

Verify this candidate and output the JSON verdict."""

        if self.backend == "mock" or self.dry_run:
            # Deterministic Mock Output
            return {
                "candidate_id": cid,
                "problem_present": True,
                "role_match": True,
                "reason": "Mock verified finding.",
                "evidence": candidate.get("code_snippet", ""),
                "parse_error": False
            }
        elif self.backend in ("transformers", "hf"):
            import torch
            messages = [
                {"role": "system", "content": SEMANTIC_VERIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            prompt_text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.loaded_model.device)
            with torch.no_grad():
                outputs = self.loaded_model.generate(**inputs, max_new_tokens=512, do_sample=False, temperature=0.0)
            gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            raw = self.tokenizer.decode(gen_tokens, skip_special_tokens=True)
            return parse_verifier_json(raw, cid)
        elif self.backend == "openai":
            import urllib.request
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
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                raw = resp_json["choices"][0]["message"]["content"]
                return parse_verifier_json(raw, cid)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    def verify_candidates(self, candidates: List[Dict[str, Any]], formatted_diff: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Executes hierarchical verification pipeline:
        Deterministic AST/Absence checks -> Semantic LLM Verifier.
        """
        print(f"[4/6] Verifying {len(candidates)} candidate findings through hierarchical pipeline...")
        verified_findings = []
        rejected_findings = []

        self.initialize_verifier_backend()

        for cand in candidates:
            cid = cand["candidate_id"]
            role = cand["source_reviewer"]
            problem = cand["problem"]
            after_src = cand.get("after_source", "")

            # Tier 2: AST Null-Safety Guard & Structural Self-Refutation
            is_refuted, refuted_reason = verify_null_safety_self_refutation(problem, after_src)
            if is_refuted:
                rejected_findings.append({
                    **cand,
                    "decision": "REJECT",
                    "verification_tier": "AST_SELF_REFUTED",
                    "rejection_reason": f"AST Analysis proved code safely guards against problem ({refuted_reason})."
                })
                continue

            # Tier 3: Deterministic Absence & Canonical Role Gate
            strategy = classify_grounding_strategy(problem)
            if strategy in (STRATEGY_ABSENCE_REFERENCE, STRATEGY_ABSENCE_RESOURCE_CLEANUP):
                canonical_kind = get_deterministic_canonical_issue_kind(strategy)
                role_compatible = is_deterministic_role_compatible(canonical_kind, role)
                if not role_compatible:
                    rejected_findings.append({
                        **cand,
                        "decision": "REJECT",
                        "verification_tier": "DETERMINISTIC_ROLE_GATE",
                        "rejection_reason": f"Role mismatch: Canonical issue '{canonical_kind}' incompatible with reviewer '{role}'."
                    })
                    continue

            # Tier 4: Semantic Verifier
            verdict = self.run_semantic_inference(cand, formatted_diff)
            is_pe = verdict.get("parse_error", False)
            prob_present = verdict.get("problem_present", False)
            role_match = verdict.get("role_match", False)

            if not is_pe and prob_present and role_match:
                verified_findings.append({
                    **cand,
                    "decision": "ACCEPT",
                    "verification_tier": "SEMANTIC_VERIFIER",
                    "verifier_reason": verdict.get("reason", ""),
                    "verifier_evidence": verdict.get("evidence", "")
                })
            else:
                rej_reason = "Parse Error" if is_pe else (f"problem_present={prob_present}, role_match={role_match} ({verdict.get('reason', '')})")
                rejected_findings.append({
                    **cand,
                    "decision": "REJECT",
                    "verification_tier": "SEMANTIC_VERIFIER",
                    "parse_error": is_pe,
                    "rejection_reason": rej_reason
                })

        return verified_findings, rejected_findings

    def deduplicate_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates findings across overlapping lines and identical problems."""
        print("[5/6] Deduplicating verified findings...")
        seen = set()
        deduped = []
        for f in findings:
            key = (f.get("file", ""), f.get("line", 0), f.get("source_reviewer", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        return deduped

    def run(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Runs the entire end-to-end PR Review pipeline."""
        start_time = time.time()
        print("==================================================")
        print("AI PULL REQUEST REVIEW MVP RUNNER")
        print("==================================================")
        print(f"Target Repo : {self.repo_path}")
        print(f"PR Branch   : {self.branch} (Base: {self.base_branch})")
        print(f"Model ID    : {self.model_id} (Backend: {self.backend})")
        print("==================================================")

        try:
            wt_path = self.create_worktree()
            diff_results, formatted_diff = self.extract_pr_diff()

            if not diff_results:
                print("No changed Java files found in this Pull Request.")
                report = {
                    "target_repo": str(self.repo_path),
                    "branch": self.branch,
                    "base_branch": self.base_branch,
                    "changed_files_count": 0,
                    "candidate_count": 0,
                    "verified_findings_count": 0,
                    "rejected_findings_count": 0,
                    "verified_findings": [],
                    "rejected_findings": [],
                    "status": "CLEAN_PR_NO_JAVA_CHANGES"
                }
                return report

            pmd_signals = self.run_static_pmd_analysis(wt_path)
            candidates = self.generate_candidate_findings(diff_results, wt_path, pmd_signals)
            verified, rejected = self.verify_candidates(candidates, formatted_diff)
            final_verified = self.deduplicate_findings(verified)

            elapsed = round(time.time() - start_time, 2)
            print("[6/6] Compiling final review report...")
            print("==================================================")
            print(f"REVIEW SUMMARY for PR: {self.branch}")
            print("==================================================")
            print(f"Changed Java Files   : {len(diff_results)}")
            print(f"Candidate Findings   : {len(candidates)}")
            print(f"Verified (Accepted)  : {len(final_verified)}")
            print(f"Rejected (Filtered)  : {len(rejected)}")
            print(f"Total Execution Time : {elapsed}s")
            print("==================================================")

            for idx, vf in enumerate(final_verified, start=1):
                print(f"[{idx}] [{vf.get('source_reviewer')}] {vf.get('file')}:{vf.get('line')}")
                print(f"    Problem: {vf.get('problem')}")
                print(f"    Fix: {vf.get('suggested_fix')}")

            report = {
                "target_repo": str(self.repo_path),
                "branch": self.branch,
                "base_branch": self.base_branch,
                "execution_time_seconds": elapsed,
                "model_id": self.model_id,
                "backend": self.backend,
                "changed_files_count": len(diff_results),
                "changed_files": [d.get("file") for d in diff_results],
                "candidate_count": len(candidates),
                "verified_findings_count": len(final_verified),
                "rejected_findings_count": len(rejected),
                "verified_findings": final_verified,
                "rejected_findings": rejected
            }

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"Report saved to: {output_path}")

            return report

        finally:
            self.cleanup_worktree()


def main():
    parser = argparse.ArgumentParser(description="Run End-to-End AI Pull Request Review MVP")
    parser.add_argument("--repo", type=str, default=".", help="Path to target Git repository")
    parser.add_argument("--branch", type=str, required=True, help="PR branch to review")
    parser.add_argument("--base", type=str, default="main", help="Base branch (default: main)")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-Coder-7B-Instruct", help="LLM Verifier model ID")
    parser.add_argument("--backend", type=str, default="mock", choices=["mock", "transformers", "hf", "openai"], help="Model backend")
    parser.add_argument("--quantization", type=str, default="none", choices=["none", "4bit", "8bit"], help="Quantization")
    parser.add_argument("--device", type=str, default="auto", help="Device mapping (auto, cuda, cpu)")
    parser.add_argument("--api-base", type=str, default=None, help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", type=str, default=None, help="API key")
    parser.add_argument("--pmd", action="store_true", help="Enable static PMD analysis")
    parser.add_argument("--dry-run", action="store_true", help="Run in mock/dry-run mode without downloading models")
    parser.add_argument("--output", type=str, default="pr_review_report.json", help="Output report JSON path")

    args = parser.parse_args()

    runner = PRReviewRunner(
        repo_path=Path(args.repo),
        branch=args.branch,
        base_branch=args.base,
        model_id=args.model,
        backend=args.backend,
        quantization=args.quantization,
        device=args.device,
        api_base=args.api_base,
        api_key=args.api_key,
        run_pmd=args.pmd,
        dry_run=args.dry_run
    )

    runner.run(output_path=Path(args.output))


if __name__ == "__main__":
    main()
