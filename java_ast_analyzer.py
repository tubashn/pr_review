"""
Java AST & Structural Code Analyzer
Provides general-purpose tokenization, structural expression parsing,
and control-flow polarity analysis for Java code and diffs.

Priority hierarchy:
1. Static analysis / compiler corroboration (when tools present)
2. AST / structural expression analysis
3. Narrow deterministic invariants & role gates
4. Regex / text fallback (when unparseable)
5. LLM semantic verifier (if unresolvable)
"""

import re
from typing import Optional, List, Dict, Any, Tuple


class JavaToken:
    def __init__(self, type_: str, value: str, pos: int):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)})"


def tokenize_java(code: str) -> List[JavaToken]:
    """
    General-purpose tokenizer for Java expressions and statements.
    Handles identifiers, keywords, operators, literals, strings, and punctuation.
    """
    token_spec = [
        ("STRING", r'"(?:\\.|[^"\\])*"'),
        ("CHAR", r"'(?:\\.|[^'\\])*'"),
        ("COMMENT_SL", r"//.*"),
        ("COMMENT_ML", r"/\*[\s\S]*?\*/"),
        ("NUMBER", r"\b\d+(?:\.\d+)?(?:[fFdDlL])?\b"),
        ("KEYWORD", r"\b(?:if|else|return|try|catch|finally|throw|new|public|private|protected|static|final|class|interface|enum|void|boolean|int|double|float|long|short|byte|char|var|null|true|false|instanceof)\b"),
        ("IDENTIFIER", r"\b[A-Za-z_$][A-Za-z0-9_$]*\b"),
        ("EQ", r"=="),
        ("NE", r"!="),
        ("LE", r"<="),
        ("GE", r">="),
        ("AND", r"&&"),
        ("OR", r"\|\|"),
        ("QUESTION", r"\?"),
        ("COLON", r":"),
        ("ARROW", r"->"),
        ("DOT", r"\."),
        ("COMMA", r","),
        ("SEMICOLON", r";"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("LBRACE", r"\{"),
        ("RBRACE", r"\}"),
        ("LBRACK", r"\["),
        ("RBRACK", r"\]"),
        ("OP", r"[+\-*/%=!<>~&|^]"),
        ("WS", r"\s+"),
    ]
    tok_regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in token_spec)
    tokens: List[JavaToken] = []
    
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        val = mo.group()
        if kind in ("WS", "COMMENT_SL", "COMMENT_ML"):
            continue
        tokens.append(JavaToken(kind, val, mo.start()))
    return tokens


class TernaryExpr:
    """Represents a Java ternary conditional expression: condition ? then_expr : else_expr"""
    def __init__(self, condition: str, then_expr: str, else_expr: str, full_text: str):
        self.condition = condition.strip()
        self.then_expr = then_expr.strip()
        self.else_expr = else_expr.strip()
        self.full_text = full_text.strip()

    def __repr__(self):
        return f"TernaryExpr({self.condition} ? {self.then_expr} : {self.else_expr})"


def extract_ternary_expressions(code: str) -> List[TernaryExpr]:
    """
    Parses Java ternary expressions from code using structural parenthesis and colon balancing.
    """
    tokens = tokenize_java(code)
    ternaries: List[TernaryExpr] = []
    n = len(tokens)
    
    # Scan for '?' that is part of a ternary (not in generics or wildcards)
    for i, tok in enumerate(tokens):
        if tok.type == "QUESTION":
            # Condition tokens before '?'
            cond_tokens = []
            j = i - 1
            paren_depth = 0
            brace_depth = 0
            while j >= 0:
                t = tokens[j]
                if t.type == "RPAREN":
                    paren_depth += 1
                elif t.type == "LPAREN":
                    if paren_depth > 0:
                        paren_depth -= 1
                    else:
                        break
                elif t.type == "RBRACE":
                    brace_depth += 1
                elif t.type == "LBRACE":
                    if brace_depth > 0:
                        brace_depth -= 1
                    else:
                        break
                elif t.type in ("SEMICOLON", "COLON") and paren_depth == 0 and brace_depth == 0:
                    break
                elif t.type == "KEYWORD" and t.value in ("return", "throw", "if", "while") and paren_depth == 0:
                    break
                cond_tokens.insert(0, t.value)
                j -= 1

            # Find matching ':' after '?'
            colon_idx = -1
            q_depth = 1
            paren_depth = 0
            k = i + 1
            then_tokens = []
            while k < n:
                t = tokens[k]
                if t.type == "QUESTION":
                    q_depth += 1
                elif t.type == "COLON":
                    q_depth -= 1
                    if q_depth == 0:
                        colon_idx = k
                        break
                elif t.type == "SEMICOLON" and paren_depth == 0:
                    break
                then_tokens.append(t.value)
                k += 1

            if colon_idx != -1:
                # Find else_tokens until terminating ';' or closing bracket
                else_tokens = []
                m = colon_idx + 1
                paren_depth = 0
                while m < n:
                    t = tokens[m]
                    if t.type == "LPAREN":
                        paren_depth += 1
                    elif t.type == "RPAREN":
                        if paren_depth > 0:
                            paren_depth -= 1
                        else:
                            break
                    elif t.type == "SEMICOLON" and paren_depth == 0:
                        break
                    elif t.type == "RBRACE" and paren_depth == 0:
                        break
                    else_tokens.append(t.value)
                    m += 1

                cond_str = " ".join(cond_tokens)
                then_str = " ".join(then_tokens)
                else_str = " ".join(else_tokens)
                full_str = f"{cond_str} ? {then_str} : {else_str}"
                ternaries.append(TernaryExpr(cond_str, then_str, else_str, full_str))
                
    return ternaries


def extract_method_invocations_on_identifier(expr_code: str, identifier: str) -> List[str]:
    """
    Extracts method names invoked directly on the given identifier within an expression.
    e.g. for `value.trim()` and identifier `value`, returns `['trim']`.
    """
    tokens = tokenize_java(expr_code)
    methods = []
    n = len(tokens)
    for i in range(n - 2):
        if tokens[i].type == "IDENTIFIER" and tokens[i].value == identifier:
            if tokens[i+1].type == "DOT" and tokens[i+2].type == "IDENTIFIER":
                # Check if followed by LPAREN (method call)
                if i + 3 < n and tokens[i+3].type == "LPAREN":
                    methods.append(tokens[i+2].value)
                else:
                    # Field access
                    methods.append(tokens[i+2].value)
    return methods


def check_null_check_condition(condition_code: str, identifier: str) -> Optional[str]:
    """
    Analyzes a boolean condition to determine if it tests `identifier` for null.
    Returns:
    - 'IS_NULL': if condition evaluates to true when identifier is null (e.g. `x == null`, `null == x`, `Objects.isNull(x)`)
    - 'NOT_NULL': if condition evaluates to true when identifier is not null (e.g. `x != null`, `null != x`, `Objects.nonNull(x)`)
    - None: if no null check on identifier found.
    """
    tokens = tokenize_java(condition_code)
    n = len(tokens)
    
    for i in range(n - 2):
        t1, t2, t3 = tokens[i], tokens[i+1], tokens[i+2]
        
        # x == null or null == x
        if (t1.type == "IDENTIFIER" and t1.value == identifier and t2.type == "EQ" and t3.value == "null") or \
           (t1.value == "null" and t2.type == "EQ" and t3.type == "IDENTIFIER" and t3.value == identifier):
            return "IS_NULL"
            
        # x != null or null != x
        if (t1.type == "IDENTIFIER" and t1.value == identifier and t2.type == "NE" and t3.value == "null") or \
           (t1.value == "null" and t2.type == "NE" and t3.type == "IDENTIFIER" and t3.value == identifier):
            return "NOT_NULL"

    return None


def is_candidate_claiming_npe_or_null_dereference(problem_text: str) -> bool:
    """
    Determines whether a candidate finding claims a NullPointerException,
    missing null check, or unsafe method invocation / dereference on null.
    """
    if not problem_text:
        return False
        
    p = problem_text.lower()
    
    npe_keywords = [
        "null pointer exception",
        "nullpointerexception",
        "npe",
        "called on a null",
        "called on null",
        "calling on null",
        "dereference null",
        "dereferencing null",
        "null check",
        "potential for null",
        "null string",
        "null object",
        "null deger",
        "null degeri",
        "null durumunda",
        "null ise",
        "null olabilir"
    ]
    
    return any(kw in p for kw in npe_keywords)


def extract_claimed_dereferenced_identifier_or_method(problem_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to extract the target variable identifier and method name mentioned in the NPE claim.
    e.g. "if `trim()` is called on a null string" -> (None, 'trim')
    e.g. "if `value` is null and `trim()` is called" -> ('value', 'trim')
    """
    method_name = None
    var_name = None

    # 1. Look for backtick quoted tokens like `trim()`, `trim`, `value`
    backtick_tokens = re.findall(r"`([^`]+)`", problem_text)
    for tok in backtick_tokens:
        tok_clean = tok.replace("()", "").strip()
        if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", tok_clean):
            if tok_clean not in ("null", "if", "else", "return", "true", "false", "String", "boolean", "int", "var"):
                if "()" in tok:
                    method_name = tok_clean
                elif not var_name:
                    var_name = tok_clean

    # 2. If method name not found in backticks, check for pattern identifier()
    if not method_name:
        for m in re.finditer(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*\)", problem_text):
            candidate_m = m.group(1)
            if candidate_m not in ("null", "if", "else", "return", "true", "false", "String", "boolean", "int", "var"):
                method_name = candidate_m
                break

    # 3. If variable name not found in backticks, search with regex
    if not var_name:
        var_match = re.search(r"[`']?([A-Za-z_$][A-Za-z0-9_$]*)[`']?\s*(?:is null|değeri|degeri|degiskeni|variable|nesnesi|üzerinde|uzerinde)", problem_text, re.IGNORECASE)
        if var_match:
            candidate_v = var_match.group(1)
            if candidate_v not in ("null", "if", "else", "return", "true", "false", "String", "boolean", "int", "var"):
                var_name = candidate_v
    
    return var_name, method_name


def is_guarded_by_ternary_null_check(code_snippet: str, target_var: Optional[str] = None, target_method: Optional[str] = None) -> bool:
    """
    AST-based verification of ternary null guards.
    Validates patterns such as:
      1. `x == null ? null : x.method()`
      2. `x == null ? defaultValue : x.method()`
      3. `x != null ? x.method() : null`
      4. `x != null ? x.method() : defaultValue`
    """
    ternaries = extract_ternary_expressions(code_snippet)
    
    for t in ternaries:
        # Check all identifiers in condition that are checked for null
        tokens = tokenize_java(t.condition)
        checked_vars = []
        for i in range(len(tokens) - 2):
            t1, t2, t3 = tokens[i], tokens[i+1], tokens[i+2]
            if t1.type == "IDENTIFIER" and t2.type in ("EQ", "NE") and t3.value == "null":
                checked_vars.append((t1.value, t2.type))
            elif t1.value == "null" and t2.type in ("EQ", "NE") and t3.type == "IDENTIFIER":
                checked_vars.append((t3.value, t2.type))
                
        for var_name, op in checked_vars:
            if target_var and target_var != var_name:
                continue
                
            if op == "EQ":  # x == null ? <safe> : <dereference x>
                # The 'else' branch is only reached when x != null
                invocations = extract_method_invocations_on_identifier(t.else_expr, var_name)
                if invocations:
                    if target_method is None or target_method in invocations:
                        # Dereference is safely guarded by ternary condition!
                        return True
                        
            elif op == "NE":  # x != null ? <dereference x> : <safe>
                # The 'then' branch is only reached when x != null
                invocations = extract_method_invocations_on_identifier(t.then_expr, var_name)
                if invocations:
                    if target_method is None or target_method in invocations:
                        # Dereference is safely guarded by ternary condition!
                        return True
                        
    return False


def is_guarded_by_if_null_check(code_snippet: str, target_var: Optional[str] = None, target_method: Optional[str] = None) -> bool:
    """
    AST-based structural verification of `if` null guards:
      - `if (x == null) return ...; x.method();`
      - `if (x != null) { x.method(); }`
    """
    tokens = tokenize_java(code_snippet)
    n = len(tokens)
    
    for i in range(n):
        if tokens[i].type == "KEYWORD" and tokens[i].value == "if":
            # Extract condition inside if (...)
            if i + 1 < n and tokens[i+1].type == "LPAREN":
                paren_depth = 1
                cond_tokens = []
                j = i + 2
                while j < n and paren_depth > 0:
                    if tokens[j].type == "LPAREN":
                        paren_depth += 1
                    elif tokens[j].type == "RPAREN":
                        paren_depth -= 1
                        if paren_depth == 0:
                            break
                    cond_tokens.append(tokens[j].value)
                    j += 1
                    
                cond_str = " ".join(cond_tokens)
                
                # Check condition type
                # Case 1: if (x == null) return ...;
                # Check if body immediately returns or throws
                body_tokens = tokens[j+1:]
                body_str = " ".join(t.value for t in body_tokens[:10])
                
                # Scan for identifier checked in condition
                for k in range(len(cond_tokens) - 2):
                    t1, t2, t3 = cond_tokens[k], cond_tokens[k+1], cond_tokens[k+2]
                    var_candidate = None
                    op = None
                    if t2 in ("==", "!=") and t3 == "null":
                        var_candidate = t1
                        op = t2
                    elif t1 == "null" and t2 in ("==", "!="):
                        var_candidate = t3
                        op = t2
                        
                    if var_candidate:
                        if target_var and target_var != var_candidate:
                            continue
                            
                        # If `x == null` followed by early return/throw
                        if op == "==" and any(kw in body_str for kw in ("return", "throw")):
                            # Remaining code after if statement has guarded x
                            rest_code = " ".join(t.value for t in body_tokens)
                            invocations = extract_method_invocations_on_identifier(rest_code, var_candidate)
                            if invocations and (target_method is None or target_method in invocations):
                                return True
                                
                        # If `x != null` guarding a block
                        elif op == "!=":
                            # Inside block
                            block_code = " ".join(t.value for t in body_tokens)
                            invocations = extract_method_invocations_on_identifier(block_code, var_candidate)
                            if invocations and (target_method is None or target_method in invocations):
                                return True
                                
    return False


def verify_null_safety_self_refutation(problem_text: str, code_snippet: str) -> Tuple[bool, str]:
    """
    Main entry point for AST-based null-safety self-refutation verification.
    
    Returns:
    - (True, "SELF_REFUTED_GUARDED_NPE"): if candidate claims NPE / missing null check,
      but AST structural analysis PROVES the invocation is safely guarded.
    - (False, "NOT_SELF_REFUTED"): if not claiming NPE, or if code does NOT prove guard (fail-open).
    """
    if not is_candidate_claiming_npe_or_null_dereference(problem_text):
        return False, "NOT_SELF_REFUTED"
        
    target_var, target_method = extract_claimed_dereferenced_identifier_or_method(problem_text)
    
    # 1. Structural Ternary Null-Guard Check
    if is_guarded_by_ternary_null_check(code_snippet, target_var, target_method):
        return True, "SELF_REFUTED_GUARDED_NPE"
        
    # 2. Structural If-Statement Null-Guard Check
    if is_guarded_by_if_null_check(code_snippet, target_var, target_method):
        return True, "SELF_REFUTED_GUARDED_NPE"
        
    # Fail-open: cannot structurally prove safe guard
    return False, "NOT_SELF_REFUTED"
