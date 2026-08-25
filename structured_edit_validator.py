"""
Structured Edit Validator V2
Validates and applies grounded structured edits (old_text -> new_text) in memory,
ensures target grounding, performs lightweight structural Java sanity checks,
and deterministically synthesizes standard unified diffs.
"""

import difflib
import os
import re
from typing import Any, Dict, List, Optional, Tuple

MAX_CHANGED_LINES = 20

PUNCTUATION_OR_DELIMITER_ONLY = {
    "}", "{", ";", ")", "(", "]", "[", ":", ",", ".", "true", "false", "status",
    "true;", "false;", "};", "});", "return;"
}


def normalize_whitespace_line(line: str) -> str:
    """Strips line endings and normalizes interior whitespace."""
    return re.sub(r"\s+", " ", line.strip())


def check_structural_java_sanity(code: str) -> bool:
    """
    Lightweight structural Java sanity check.
    Verifies balanced curly braces and parentheses, ignoring characters inside string literals and comments.
    """
    if not code:
        return True

    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0

    in_str = False
    str_char = ''
    in_line_comment = False
    in_block_comment = False
    escape = False

    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        next_c = code[i + 1] if i + 1 < n else ''

        if in_line_comment:
            if c == '\n':
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if c == '*' and next_c == '/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_str:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == str_char:
                in_str = False
            i += 1
            continue

        # Check comment start
        if c == '/' and next_c == '/':
            in_line_comment = True
            i += 2
            continue
        if c == '/' and next_c == '*':
            in_block_comment = True
            i += 2
            continue

        # Check string / char literal start
        if c in ('"', "'"):
            in_str = True
            str_char = c
            escape = False
            i += 1
            continue

        # Check balance
        if c == '{':
            brace_depth += 1
        elif c == '}':
            brace_depth -= 1
            if brace_depth < 0:
                return False
        elif c == '(':
            paren_depth += 1
        elif c == ')':
            paren_depth -= 1
            if paren_depth < 0:
                return False
        elif c == '[':
            bracket_depth += 1
        elif c == ']':
            bracket_depth -= 1
            if bracket_depth < 0:
                return False

        i += 1

    return (brace_depth == 0 and paren_depth == 0 and bracket_depth == 0)


def is_meaningful_target(old_text: str) -> bool:
    """Checks whether old_text contains a meaningful code construct rather than just a bare delimiter."""
    if not old_text or not isinstance(old_text, str):
        return False

    cleaned = old_text.strip()
    if not cleaned:
        return False

    if cleaned in PUNCTUATION_OR_DELIMITER_ONLY:
        return False

    # Target containing solely whitespace, braces, or semicolons is rejected
    if re.fullmatch(r"[\s{};\(\)\[\],]+", cleaned):
        return False

    return True


def find_normalized_whitespace_match(source: str, old_text: str) -> List[Tuple[int, int]]:
    """
    Attempts deterministic line-by-line whitespace normalization matching.
    Returns list of (start_char_idx, end_char_idx) in source.
    """
    source_lines = source.splitlines(keepends=True)
    old_lines = [l for l in old_text.splitlines() if l.strip()]

    if not old_lines or not source_lines:
        return []

    norm_old = [normalize_whitespace_line(l) for l in old_lines]
    matches = []

    # Window search across source lines
    for i in range(len(source_lines) - len(old_lines) + 1):
        window_lines = [source_lines[i + k] for k in range(len(old_lines))]
        norm_window = [normalize_whitespace_line(l) for l in window_lines]

        if norm_window == norm_old:
            start_pos = sum(len(source_lines[k]) for k in range(i))
            end_pos = sum(len(source_lines[k]) for k in range(i + len(old_lines)))
            matches.append((start_pos, end_pos))

    return matches


def synthesize_unified_diff(file_path: str, source_content: str, patched_source: str) -> str:
    """Deterministically synthesizes standard unified diff between source and patched code."""
    norm_path = file_path.replace("\\", "/")
    src_lines = source_content.splitlines(keepends=True)
    patch_lines = patched_source.splitlines(keepends=True)

    # Ensure ending newline style is consistent
    if src_lines and not src_lines[-1].endswith("\n"):
        src_lines[-1] += "\n"
    if patch_lines and not patch_lines[-1].endswith("\n"):
        patch_lines[-1] += "\n"

    diff_lines = list(difflib.unified_diff(
        src_lines,
        patch_lines,
        fromfile=f"a/{norm_path}",
        tofile=f"b/{norm_path}",
        lineterm=""
    ))

    return "\n".join(l.rstrip("\r\n") for l in diff_lines)


def validate_and_apply_structured_edit(
    structured_edit: Dict[str, Any],
    finding: Dict[str, Any],
    source_content: str,
    pr_changed_files: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validates a structured edit (old_text -> new_text), checks grounding and scope,
    applies the edit in memory, and synthesizes a validated unified diff.
    """
    fid = structured_edit.get("finding_id") or finding.get("candidate_id") or finding.get("finding_id", "fix-1")
    file_path = str(structured_edit.get("file_path") or finding.get("file") or finding.get("file_path") or "").strip()
    explanation = structured_edit.get("explanation", "")
    old_text = structured_edit.get("old_text")
    new_text = structured_edit.get("new_text", "")

    def make_rejection(reason: str, failure_type: Optional[str] = None) -> Dict[str, Any]:
        return {
            "finding_id": fid,
            "file_path": file_path,
            "fix_status": "rejected",
            "diff": "",
            "old_text": old_text,
            "new_text": new_text,
            "explanation": explanation,
            "match_mode": None,
            "validation": {
                "unified_diff_valid": False,
                "path_match": False,
                "size_within_limit": False,
                "apply_check": False,
                "structural_sanity": False
            },
            "skip_reason": None,
            "rejection_reason": reason,
            "failure_type": failure_type or reason
        }

    # 1. Path Safety and PR Scope Checks
    if not file_path:
        return make_rejection("missing_file_path", "unsafe_path")

    norm_file = file_path.replace("\\", "/")
    if ".." in norm_file or norm_file.startswith("/") or norm_file.startswith("\\"):
        return make_rejection("path_traversal_detected", "unsafe_path")

    finding_file = str(finding.get("file") or finding.get("file_path") or "").replace("\\", "/")
    if finding_file and norm_file != finding_file:
        return make_rejection(f"file_path_mismatch_{norm_file}_vs_{finding_file}", "unsafe_path")

    if pr_changed_files:
        norm_changed = [f.replace("\\", "/") for f in pr_changed_files]
        if norm_file not in norm_changed:
            return make_rejection("file_not_in_pr_changed_files", "unsafe_path")

    # 2. old_text Presence & Meaningful Target Check
    if not old_text or not isinstance(old_text, str):
        return make_rejection("empty_old_text", "old_text_not_found")

    if not is_meaningful_target(old_text):
        return make_rejection("insufficient_target_context", "insufficient_target_context")

    # 3. No-Op Fix Check
    if old_text == new_text or normalize_whitespace_line(old_text) == normalize_whitespace_line(new_text):
        return make_rejection("no_op_fix", "no_op_fix")

    if not source_content:
        return make_rejection("missing_source_content", "old_text_not_found")

    # 4. Exact Grounding in Source Content
    match_mode = "exact"
    start_idx = -1
    end_idx = -1

    count_exact = source_content.count(old_text)
    if count_exact == 1:
        start_idx = source_content.find(old_text)
        end_idx = start_idx + len(old_text)
    elif count_exact > 1:
        return make_rejection("ambiguous_old_text", "ambiguous_old_text")
    else:
        # Fallback to controlled whitespace normalization
        norm_matches = find_normalized_whitespace_match(source_content, old_text)
        if len(norm_matches) == 1:
            match_mode = "normalized_whitespace"
            start_idx, end_idx = norm_matches[0]
        elif len(norm_matches) > 1:
            return make_rejection("ambiguous_old_text", "ambiguous_old_text")
        else:
            return make_rejection("old_text_not_found", "old_text_not_found")

    # 5. Finding Location Proximity Check
    target_line = finding.get("line")
    if target_line is not None and isinstance(target_line, int) and target_line > 0:
        match_line = source_content[:start_idx].count("\n") + 1
        if abs(match_line - target_line) > 30:
            return make_rejection(f"target_location_mismatch_line_{match_line}_vs_{target_line}", "target_location_mismatch")

    # 6. Target-Touch Validation
    evidence = str(finding.get("evidence") or finding.get("code_snippet") or "").strip()
    if evidence:
        norm_ev = normalize_whitespace_line(evidence)
        norm_target = normalize_whitespace_line(old_text)
        if norm_ev and norm_target:
            ev_tokens = set(re.findall(r"\b[A-Za-z0-9_]+\b", norm_ev))
            target_tokens = set(re.findall(r"\b[A-Za-z0-9_]+\b", norm_target))
            common_tokens = ev_tokens.intersection(target_tokens)
            if not common_tokens and (norm_ev not in norm_target and norm_target not in norm_ev):
                return make_rejection("target_not_modified", "target_not_modified")

    # 7. Deterministic In-Memory Replacement
    patched_source = source_content[:start_idx] + new_text + source_content[end_idx:]

    # 8. Lightweight Structural Java Sanity Check
    if not check_structural_java_sanity(patched_source):
        return make_rejection("structural_sanity_failed", "structural_invalid")

    # 9. Deterministic Unified Diff Synthesis
    diff_text = synthesize_unified_diff(norm_file, source_content, patched_source)

    # 10. Changed Lines Size Constraint (<= 20 lines)
    diff_lines = diff_text.splitlines()
    changed_count = sum(1 for l in diff_lines if (l.startswith("+") or l.startswith("-")) and not l.startswith("+++") and not l.startswith("---"))
    if changed_count > MAX_CHANGED_LINES:
        return make_rejection(f"patch_too_large_{changed_count}_lines", "patch_too_large")

    return {
        "finding_id": fid,
        "file_path": norm_file,
        "fix_status": "generated",
        "diff": diff_text,
        "old_text": old_text,
        "new_text": new_text,
        "match_mode": match_mode,
        "patched_source": patched_source,
        "validation": {
            "unified_diff_valid": True,
            "path_match": True,
            "size_within_limit": True,
            "apply_check": True,
            "structural_sanity": True
        },
        "skip_reason": None,
        "rejection_reason": None,
        "failure_type": None
    }
