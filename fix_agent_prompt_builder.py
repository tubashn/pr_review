"""
Fix Agent Prompt Builder
Constructs isolated, explicit prompts for generating unified diff patches for verified review findings.
Rules:
- DO NOT pass candidate suggested_fix into Fix Agent prompt (independent generation).
- Target ONLY the provided single file.
- Address ONLY the verified problem and failure scenario.
- Strictly output valid JSON matching schema.
"""

import json
from typing import Any, Dict, Optional


FIX_AGENT_SYSTEM_PROMPT = """You are an expert Java Code Review Fix Agent.
Your task is to generate a minimal, safe, and localized unified diff (git patch) to fix an already verified review finding.

Strict Operating Rules:
1. Target ONLY the specified file path.
2. Address ONLY the verified problem described. Do NOT perform unrelated refactorings or stylistic reformatting.
3. Preserve existing behavior outside the exact scope of the finding.
4. Output must be a standard unified diff starting with '--- a/<file_path>' and '+++ b/<file_path>' followed by standard '@@ -l,s +l,s @@' hunk headers.
5. Keep changes small: total modified lines (added + removed) MUST NOT exceed 20 lines.
6. If a safe, localized fix cannot be confidently produced from the available context, return "fix_status": "skipped".
7. Output strictly a single valid JSON object with NO markdown code fences surrounding the JSON response.

Response Schema:
{
  "finding_id": "<finding_id>",
  "file_path": "<file_path>",
  "fix_status": "generated" | "skipped",
  "diff": "--- a/...
+++ b/...
@@ ... @@
...",
  "explanation": "<brief rationale for the fix>",
  "skip_reason": "<optional reason if skipped, else null>"
}"""


def build_fix_agent_prompt(
    finding: Dict[str, Any],
    file_path: str,
    source_context: str = "",
    diff_hunk: str = ""
) -> str:
    """
    Builds the user prompt for the Fix Agent.
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
        f"Line Number: {line_no if line_no is not None else 'Unknown'}",
        f"Category/Role: {role}",
        "",
        "Verified Problem Statement:",
        problem.strip(),
        ""
    ]

    if evidence:
        sections.extend([
            "Problem Evidence / Code Snippet:",
            f"```java\n{evidence.strip()}\n```",
            ""
        ])

    if diff_hunk:
        sections.extend([
            "Relevant PR Diff Hunk:",
            f"```diff\n{diff_hunk.strip()}\n```",
            ""
        ])

    if source_context:
        sections.extend([
            "Source Code Context:",
            f"```java\n{source_context.strip()}\n```",
            ""
        ])

    sections.append("Generate the minimal unified diff to fix this verified finding and output the JSON response.")
    return "\n".join(sections)
