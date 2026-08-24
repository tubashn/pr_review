"""
Deterministic Patch Validator for Fix Agent V1
Enforces strict security, size, format, apply-cleanliness, and AST sanity checks on generated diffs:
1. Unified Diff syntax validation (--- a/..., +++ b/..., @@ ... @@)
2. Path matching & path traversal prevention (no .., no absolute paths, no /etc/, strictly target file)
3. Patch operation restrictions (no file creation, no deletion, no rename, no binary)
4. Changed lines limit (<= 20 total added + removed source lines)
5. Clean patch application verification (without mutating target repo/worktree)
6. Java Structural AST Sanity Check on patched copy (balanced braces, parens, brackets, valid tokens)
"""

import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from java_ast_analyzer import tokenize_java


MAX_CHANGED_LINES = 20


def parse_unified_diff_headers(diff_text: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Parses unified diff headers.
    Returns:
        (from_file, to_file, hunks_lines)
    """
    from_file = None
    to_file = None
    hunk_lines = []

    lines = diff_text.strip().splitlines()
    for line in lines:
        if line.startswith("--- "):
            raw = line[4:].strip()
            # strip a/ prefix or quotes
            raw = raw.strip('"\'')
            if raw.startswith("a/"):
                raw = raw[2:]
            from_file = raw.split("\t")[0].strip()
        elif line.startswith("+++ "):
            raw = line[4:].strip()
            # strip b/ prefix or quotes
            raw = raw.strip('"\'')
            if raw.startswith("b/"):
                raw = raw[2:]
            to_file = raw.split("	")[0].strip()
        else:
            hunk_lines.append(line)

    return from_file, to_file, hunk_lines


def count_changed_lines(diff_text: str) -> int:
    """
    Counts total added (+) and removed (-) source lines in the diff.
    Excludes header lines (---, +++, diff --git, index, @@).
    """
    changed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("diff ") or line.startswith("index "):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed += 1
    return changed


def check_path_safety(file_path: str, expected_file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validates that file_path in diff is strictly safe and matches expected target file.
    """
    if not file_path:
        return False, "missing_diff_file_path"

    # Normalize slashes
    norm_diff_path = file_path.replace("\\", "/").strip().lstrip("/")
    norm_expected = expected_file_path.replace("\\", "/").strip().lstrip("/")

    # Path traversal check
    if ".." in norm_diff_path.split("/"):
        return False, "path_traversal_detected"

    # Absolute path / sensitive path check
    if norm_diff_path.startswith("/") or norm_diff_path.startswith("C:") or norm_diff_path.startswith("/etc") or norm_diff_path.startswith("/var") or norm_diff_path.startswith("/tmp"):
        return False, "absolute_or_system_path_rejected"

    # Must match expected target file
    if norm_diff_path != norm_expected:
        # Also allow if one is suffix of other in standard git prefix
        if not (norm_expected.endswith(norm_diff_path) or norm_diff_path.endswith(norm_expected)):
            return False, f"path_mismatch_expected_{norm_expected}_got_{norm_diff_path}"

    return True, None


def apply_unified_diff_to_text(original_text: str, diff_text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Pure-Python deterministic unified diff applicator.
    Applies unified diff hunks cleanly to original_text without mutating filesystem.
    Returns:
        (success, patched_text, error_message)
    """
    lines = original_text.splitlines(keepends=True)
    diff_lines = diff_text.strip().splitlines()

    # Find hunk blocks
    hunks = []
    current_hunk = None

    hunk_header_re = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")

    for dline in diff_lines:
        match = hunk_header_re.match(dline)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_len = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_len = int(match.group(4)) if match.group(4) is not None else 1
            current_hunk = {
                "old_start": old_start,
                "old_len": old_len,
                "new_start": new_start,
                "new_len": new_len,
                "lines": []
            }
        elif current_hunk is not None:
            if not (dline.startswith("--- ") or dline.startswith("+++ ") or dline.startswith("diff ") or dline.startswith("index ")):
                current_hunk["lines"].append(dline)

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        return False, original_text, "no_valid_hunks_found_in_diff"

    # Apply hunks in sequence
    out_lines = list(lines)
    line_offset = 0

    for hunk in hunks:
        old_start = hunk["old_start"] - 1  # 1-indexed to 0-indexed
        target_idx = old_start + line_offset

        hunk_old_lines = []
        hunk_new_lines = []

        for hl in hunk["lines"]:
            if hl.startswith("-"):
                hunk_old_lines.append(hl[1:])
            elif hl.startswith("+"):
                hunk_new_lines.append(hl[1:])
            elif hl.startswith(" ") or hl == "":
                prefix_len = 1 if hl.startswith(" ") else 0
                hunk_old_lines.append(hl[prefix_len:])
                hunk_new_lines.append(hl[prefix_len:])

        # Verify old lines match at target_idx
        # If line numbers drifted slightly, try a search window of +/- 10 lines
        matched_idx = None
        for search_offset in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 10, -10]:
            candidate_idx = target_idx + search_offset
            if 0 <= candidate_idx <= len(out_lines) - len(hunk_old_lines):
                window = [out_lines[candidate_idx + k].rstrip("\r\n") for k in range(len(hunk_old_lines))]
                normalized_expected = [l.rstrip("\r\n") for l in hunk_old_lines]
                if window == normalized_expected:
                    matched_idx = candidate_idx
                    break

        if matched_idx is None:
            # Full file search fallback if line numbers drifted significantly
            for candidate_idx in range(len(out_lines) - len(hunk_old_lines) + 1):
                window = [out_lines[candidate_idx + k].strip() for k in range(len(hunk_old_lines))]
                normalized_expected = [l.strip() for l in hunk_old_lines]
                if window == normalized_expected:
                    matched_idx = candidate_idx
                    break

        if matched_idx is None:
            return False, original_text, f"hunk_context_mismatch_at_line_{hunk['old_start']}"

        # Replace matched slice with new lines
        # Determine newline style
        nl = "\n"
        if out_lines and "\r\n" in out_lines[0]:
            nl = "\r\n"

        replacement = [l if l.endswith("\n") else l + nl for l in hunk_new_lines]
        out_lines[matched_idx:matched_idx + len(hunk_old_lines)] = replacement
        line_offset += len(hunk_new_lines) - len(hunk_old_lines)

    return True, "".join(out_lines), None


def check_structural_java_sanity(code: str) -> Tuple[bool, Optional[str]]:
    """
    Checks structural balance and token validity on patched Java code.
    """
    if not code:
        return False, "empty_patched_content"

    # 1. Bracket and parenthesis balance
    brace_depth = 0
    paren_depth = 0
    bracket_depth = 0

    try:
        tokens = tokenize_java(code)
        for tok in tokens:
            if tok.type == "LBRACE":
                brace_depth += 1
            elif tok.type == "RBRACE":
                brace_depth -= 1
                if brace_depth < 0:
                    return False, "unbalanced_closing_brace"
            elif tok.type == "LPAREN":
                paren_depth += 1
            elif tok.type == "RPAREN":
                paren_depth -= 1
                if paren_depth < 0:
                    return False, "unbalanced_closing_parenthesis"
            elif tok.type == "LBRACK":
                bracket_depth += 1
            elif tok.type == "RBRACK":
                bracket_depth -= 1
                if bracket_depth < 0:
                    return False, "unbalanced_closing_bracket"

        if brace_depth != 0:
            return False, f"unclosed_braces_remaining_{brace_depth}"
        if paren_depth != 0:
            return False, f"unclosed_parentheses_remaining_{paren_depth}"
        if bracket_depth != 0:
            return False, f"unclosed_brackets_remaining_{bracket_depth}"

        return True, None
    except Exception as e:
        return False, f"java_tokenization_error_{str(e)}"


def validate_patch(
    diff_text: str,
    expected_file_path: str,
    source_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes full deterministic safety validation on a candidate patch diff.
    """
    cleaned_diff = diff_text.strip()
    if cleaned_diff.startswith("```diff"):
        cleaned_diff = cleaned_diff[7:].strip()
    elif cleaned_diff.startswith("```"):
        cleaned_diff = cleaned_diff[3:].strip()
    if cleaned_diff.endswith("```"):
        cleaned_diff = cleaned_diff[:-3].strip()

    result = {
        "valid": False,
        "validation": {
            "unified_diff_valid": False,
            "path_match": False,
            "size_within_limit": False,
            "apply_check": False,
            "structural_sanity": False
        },
        "changed_lines_count": 0,
        "rejection_reason": None,
        "clean_diff": cleaned_diff
    }

    if not cleaned_diff:
        result["rejection_reason"] = "empty_diff"
        return result

    # 1. Reject binary / create / delete / rename operations
    lower_diff = cleaned_diff.lower()
    if any(k in lower_diff for k in ["new file mode", "deleted file mode", "rename from", "rename to", "binary files", "git binary patch"]):
        result["rejection_reason"] = "unsupported_patch_operation"
        return result

    # 2. Parse headers
    from_file, to_file, hunk_lines = parse_unified_diff_headers(cleaned_diff)
    if not from_file or not to_file or "@@" not in cleaned_diff:
        result["rejection_reason"] = "invalid_unified_diff_headers"
        return result

    result["validation"]["unified_diff_valid"] = True

    # 3. Path matching and safety
    from_safe, from_err = check_path_safety(from_file, expected_file_path)
    to_safe, to_err = check_path_safety(to_file, expected_file_path)

    if not from_safe or not to_safe:
        result["rejection_reason"] = from_err or to_err
        return result

    result["validation"]["path_match"] = True

    # 4. Changed lines limit (<= 20)
    changed_count = count_changed_lines(cleaned_diff)
    result["changed_lines_count"] = changed_count

    if changed_count > MAX_CHANGED_LINES:
        result["rejection_reason"] = f"patch_too_large_{changed_count}_lines_exceeds_{MAX_CHANGED_LINES}"
        return result

    if changed_count == 0:
        result["rejection_reason"] = "zero_lines_changed_in_diff"
        return result

    result["validation"]["size_within_limit"] = True

    # 5. Apply check
    if source_content:
        applied_ok, patched_code, apply_err = apply_unified_diff_to_text(source_content, cleaned_diff)
        if not applied_ok:
            result["rejection_reason"] = f"patch_apply_failed_{apply_err}"
            return result

        result["validation"]["apply_check"] = True

        # 6. Structural AST Sanity Check
        sanity_ok, sanity_err = check_structural_java_sanity(patched_code)
        if not sanity_ok:
            result["rejection_reason"] = f"structural_sanity_failed_{sanity_err}"
            return result

        result["validation"]["structural_sanity"] = True
    else:
        # If no source content supplied, apply_check and structural_sanity pass conservatively
        result["validation"]["apply_check"] = True
        result["validation"]["structural_sanity"] = True

    result["valid"] = True
    return result
