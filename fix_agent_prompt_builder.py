"""
Fix Agent Prompt Builder V2
Constructs isolated, explicit prompts for generating grounded structured edits (old_text -> new_text)
for verified code review findings.
Rules:
- DO NOT ask LLM to generate unified diff, hunk headers, or line offsets.
- Ask LLM for exact verbatim `old_text` from source and minimal `new_text`.
- DO NOT pass candidate suggested_fix into Fix Agent prompt (independent generation).
- Target ONLY the provided single file.
- Address ONLY the verified problem.
- Strictly output valid JSON matching schema.
"""

import json
from typing import Any, Dict, Optional


FIX_AGENT_SYSTEM_PROMPT = """You are an expert Java Code Review Fix Agent.
You are provided with an already VERIFIED code review finding.
Your task is to propose ONE minimal, safe, and localized replacement edit (old_text -> new_text) to fix the verified problem.

Strict Operating Rules:
1. Target ONLY the specified file path.
2. Address ONLY the verified problem described. Do NOT perform unrelated refactorings, style reformatting, or large rewrites.
3. Preserve existing behavior outside the exact scope of the finding.
4. Copy `old_text` VERBATIM from the provided source code context. `old_text` must contain the actual defective statement or construct.
5. Do NOT select only a brace, delimiter, or punctuation character (e.g. '}', '{', ';') as `old_text`.
6. Output `new_text` as the exact replacement for `old_text`.
7. Do NOT output a unified diff, git patch, hunk headers (@@), or diff headers.
8. Do NOT wrap your JSON response in markdown code fences. Output strictly a single raw valid JSON object.
9. If a safe, localized fix cannot be confidently produced from the available context, return "fix_status": "skipped".

Response Schema (Generated Fix):
{
  "finding_id": "<finding_id>",
  "file_path": "<file_path>",
  "fix_status": "generated",
  "old_text": "<exact verbatim code snippet from source to replace>",
  "new_text": "<exact localized replacement code>",
  "explanation": "<brief rationale for the fix>"
}

Response Schema (Skipped Fix):
{
  "finding_id": "<finding_id>",
  "file_path": "<file_path>",
  "fix_status": "skipped",
  "skip_reason": "insufficient_context"
}"""


def build_fix_agent_prompt(
    finding: Dict[str, Any],
    file_path: str,
    source_context: str = "",
    diff_hunk: str = ""
) -> str:
    """
    Builds the user prompt for the Fix Agent V2.
    Explicitly omits candidate suggested_fix so the Fix Agent formulates its own solution.
    """
    fid = finding.get("candidate_id") or finding.get("finding_id", "finding-1")
    role = finding.get("source_reviewer", "correctness_logic")
    problem = finding.get("problem", "")
    line_no = finding.get("line")
    evidence = finding.get("evidence") or finding.get("code_snippet") or ""

    sections = [
        f"Finding ID: {fid}",
        f"Target File: {file_path}",
        f"Target Line: {line_no if line_no is not None else 'Unknown'}",
        f"Category/Role: {role}",
        "",
        "Verified Problem Statement:",
        problem.strip(),
        ""
    ]

    if evidence:
        sections.extend([
            "Problem Evidence / Defective Construct:",
            f"```java\n{evidence.strip()}\n```",
            ""
        ])

    if diff_hunk:
        sections.extend([
            "Relevant PR Diff Context:",
            f"```diff\n{diff_hunk.strip()}\n```",
            ""
        ])

    if source_context:
        sections.extend([
            "BEFORE Source Code Context:",
            f"```java\n{source_context.strip()}\n```",
            ""
        ])

    sections.append("Identify the exact `old_text` to replace from the source code and provide the minimal `new_text` in the JSON response.")
    return "\n".join(sections)
