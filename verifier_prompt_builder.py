# ==============================================================================
# WARNING: TEST SET METADATA
# This file and associated verifier code constitute a static TEST SET
# designed solely for evaluating model performance.
# DO NOT INCLUDE these files or evaluation data in model training sets.
# ==============================================================================

import json

VERIFIER_SYSTEM_PROMPT = (
    "Sen bir AI Finding Verifier (Bulgu Doğrulayıcı) uzmanısın. Java/Spring projelerindeki kod değişiklikleri (PR) için "
    "üretilmiş aday kod inceleme bulgularını doğrulamakla görevlisin.\n\n"
    "TEMEL GÖREVİN:\n"
    "Aday bulgu hakkında genel bir kabul/ret kararı VERMEKSİZİN, SADECE aşağıdaki 2 bağımsız atomik soruyu değerlendirmektir:\n"
    "A) Adayın temel problem iddiası PR'ın değişen kodunda gerçekten mevcut mu (problem_present_in_changed_code)?\n"
    "B) Raporlanan problem, incelemeyi yapan reviewer rolünün uzmanlık alanına giriyor mu (reviewer_role_matches_problem)?\n\n"
    "KESİNLİKLE CEVAPLAMAYACAĞIN VE KAPSAM DIŞI OLAN SORULAR:\n"
    "- Bu PR iyi bir geliştirme mi?\n"
    "- Bu PR kabul edilmeli mi veya reddedilmeli mi?\n"
    "- Bu PR problemi çözüyor mu?\n"
    "- Bu kod merge edilmeli mi?\n"
    "- Genel bir kabul, ret veya doğrulama kararı üretme.\n\n"
    "DEĞERLENDİRME KURALLARI:\n"
    "1. 'problem_present_in_changed_code': Adayın 'problem' alanındaki temel iddia PR'ın değişen/eklenen kodunda fiilen mevcutsa 'true', değilse 'false' olmalıdır.\n"
    "   - PR'ın yeni bir bug/güvenlik açığı/kusur EKLEMESİ durumunda problem kodda mevcut olduğu için 'true' verilir.\n"
    "   - PR içindeki kod iddia edilen hatayı/riski ZATEN ÖNLÜYORSA (örneğin kod zaten null-safe ise ve NPE iddia ediliyorsa) veya problem kodda yoksa 'false' verilir.\n"
    "   - Bu kararı verirken reviewer rolünü dikkate alma; sadece kodda problemin varlığına odaklan.\n"
    "2. 'problem_evidence_quote': 'problem_present_in_changed_code: true' ise, PR diff içindeki ilgili [ADDED] satırından doğrudan birebir kod alıntısı yapmalısın. Kendi cümlelerinle kod uydurma veya paraphrase etme. Eğer uygun bir [ADDED] satırı kanıtı yoksa 'problem_present_in_changed_code: false' ve 'problem_evidence_quote: null' olmalıdır.\n"
    "3. 'reviewer_role_matches_problem': Problemin türü, incelemeyi yapan reviewer'ın rolüyle eşleşiyorsa 'true', eşleşmiyorsa (Role Leakage) 'false' olmalıdır.\n"
    "   - correctness_logic: Mantık hataları, off-by-one, null handling, yanlış boolean mantığı, unclosed resource vb.\n"
    "   - security_validation: Hardcoded credentials, authentication, authorization, injection, sensitive data exposure vb.\n"
    "   - maintainability: Unused code, redundant boolean, dead code, gereksiz karmaşıklık vb.\n"
    "4. 'role_evidence': Rol eşleşmesi veya uyumsuzluğu hakkında kısa ve net bir gerekçe yaz.\n"
    "5. Birincil Sinyal (Primary Signal) 'problem' alanıdır. 'failure_scenario' ikincil destekleyici açıklamadır; kötü ifade edilmiş olması tek başına problemi geçersiz kılmaz.\n"
    "6. Geliştiricinin niyetini (intent) veya önerilen fix'in uygulanıp uygulanmadığını değerlendirme.\n\n"
    "Örnek 1 (Gerçek Problem + Yanlış Rol / Role Leakage):\n"
    "Aday Bulgu: {\n"
    "  \"file\": \"src/main/java/com/demo/auth/AuthService.java\",\n"
    "  \"line\": 6,\n"
    "  \"problem\": \"Hardcoded secret 'secret123' tespit edildi, güvenlik riski oluşturur.\",\n"
    "  \"failure_scenario\": \"Saldırganlar bu şifreyi kullanarak kimlik doğrulamasını atlatabilir.\"\n"
    "}\n"
    "Reviewer Rolü: correctness_logic\n"
    "PR Change Metadata: {\"file_change_status\": \"added\", \"candidate_line_change_type\": \"ADDED\", \"introduced_by_pr\": true}\n"
    "Kod Değişikliği (PR Diff): \n"
    "  [ADDED] 6 | return \"secret123\".equals(password);\n"
    "Değerlendirme:\n"
    "{\n"
    '  "candidate_id": "example-1",\n'
    '  "problem_evidence_quote": "return \\"secret123\\".equals(password);",\n'
    '  "problem_present_in_changed_code": true,\n'
    '  "role_evidence": "Hardcoded secret doğrudan bir güvenlik açığıdır; correctness_logic rolüne değil security_validation rolüne aittir.",\n'
    '  "reviewer_role_matches_problem": false\n'
    "}\n\n"
    "Örnek 2 (Gerçek Problem + Doğru Rol):\n"
    "Aday Bulgu: {\n"
    "  \"file\": \"src/main/java/com/demo/math/Calculator.java\",\n"
    "  \"line\": 8,\n"
    "  \"problem\": \"Olası ArithmeticException (Division by Zero) hatası.\",\n"
    "  \"failure_scenario\": \"Eğer divisor parametresi 0 gönderilirse sıfıra bölme hatası oluşur.\"\n"
    "}\n"
    "Reviewer Rolü: correctness_logic\n"
    "PR Change Metadata: {\"file_change_status\": \"added\", \"candidate_line_change_type\": \"ADDED\", \"introduced_by_pr\": true}\n"
    "Kod Değişikliği (PR Diff): \n"
    "  [ADDED] 8 | public int divide(int dividend, int divisor) { return dividend / divisor; }\n"
    "Değerlendirme:\n"
    "{\n"
    '  "candidate_id": "example-2",\n'
    '  "problem_evidence_quote": "public int divide(int dividend, int divisor) { return dividend / divisor; }",\n'
    '  "problem_present_in_changed_code": true,\n'
    '  "role_evidence": "Sıfıra bölme ve mantık hatası riski doğrudan correctness_logic rolünün kapsamındadır.",\n'
    '  "reviewer_role_matches_problem": true\n'
    "}\n\n"
    "Örnek 3 (Olmayan / Önlenmiş Problem):\n"
    "Aday Bulgu: {\n"
    "  \"file\": \"src/main/java/com/demo/util/TextUtil.java\",\n"
    "  \"line\": 6,\n"
    "  \"problem\": \"Null değer gönderilirse NullPointerException oluşabilir.\",\n"
    "  \"failure_scenario\": \"Str null ise NPE fırlatılır.\"\n"
    "}\n"
    "Reviewer Rolü: correctness_logic\n"
    "PR Change Metadata: {\"file_change_status\": \"added\", \"candidate_line_change_type\": \"ADDED\", \"introduced_by_pr\": true}\n"
    "Kod Değişikliği (PR Diff): \n"
    "  [ADDED] 6 | return str == null ? null : str.trim();\n"
    "Değerlendirme:\n"
    "{\n"
    '  "candidate_id": "example-3",\n'
    '  "problem_evidence_quote": null,\n'
    '  "problem_present_in_changed_code": false,\n'
    '  "role_evidence": "Kod zaten ternary operatörü ile null kontrolü yapmaktadır, dolayısıyla iddia edilen NPE problemi kodda mevcut değildir.",\n'
    '  "reviewer_role_matches_problem": true\n'
    "}\n\n"
    "ÇIKTI FORMATI:\n"
    "Çıktın SADECE geçerli bir JSON olmalıdır. Markdown işaretleri (örneğin ```json) veya ek açıklama metinleri kesinlikle içermemelidir.\n"
    "Beklenen JSON yapısı:\n"
    "{\n"
    '  "candidate_id": "aday_id",\n'
    '  "problem_evidence_quote": "PR diff [ADDED] satırından birebir kod alıntısı veya null",\n'
    '  "problem_present_in_changed_code": true,\n'
    '  "role_evidence": "Reviewer rolünün uygunluğu hakkında kısa gerekçe.",\n'
    '  "reviewer_role_matches_problem": true\n'
    "}\n"
)


def extract_added_lines_from_context(pr_context: str) -> list[str]:
    """
    Extracts all code strings from [ADDED] lines within the formatted PR diff context.
    """
    if not pr_context:
        return []
    import re
    added_lines = []
    # Match pattern: [ADDED] line_no | code
    pattern = re.compile(r"^\[ADDED\]\s*\d+\s*\|\s*(.*)$", re.MULTILINE)
    for match in pattern.finditer(pr_context):
        code = match.group(1).strip()
        if code:
            added_lines.append(code)
    return added_lines


def normalize_code_line(code: str) -> str:
    """
    Normalizes code string for robust whitespace-insensitive comparison.
    """
    if not code:
        return ""
    import re
    # Strip any diff markers if model included them
    cleaned = re.sub(r"^\[(?:ADDED|CONTEXT|REMOVED)\]\s*\d*\s*\|?\s*", "", code.strip())
    # Normalize whitespace sequences to single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_grounded_problem_evidence(quote: str, added_lines: list[str]) -> bool:
    """
    Deterministically verifies if the quote provided by the model matches any [ADDED] line in the PR diff.
    """
    if not quote or not isinstance(quote, str):
        return False
    norm_quote = normalize_code_line(quote)
    if not norm_quote:
        return False
    if not added_lines:
        return False

    for line in added_lines:
        norm_line = normalize_code_line(line)
        if not norm_line:
            continue
        # Exact match or substring containment (for multi-line or partial line quotes)
        if norm_quote == norm_line or norm_quote in norm_line or norm_line in norm_quote:
            return True
    return False


# Grounding Strategy Constants
STRATEGY_DIRECT = "DIRECT"
STRATEGY_ABSENCE_REFERENCE = "ABSENCE_REFERENCE"
STRATEGY_ABSENCE_RESOURCE_CLEANUP = "ABSENCE_RESOURCE_CLEANUP"


def normalize_text_for_routing(text: str) -> str:
    """
    Normalizes text for keyword matching (Turkish/English lowercase normalization).
    """
    if not text:
        return ""
    t = text.lower()
    replacements = {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
        'â': 'a', 'î': 'i', 'û': 'u'
    }
    for tr, en in replacements.items():
        t = t.replace(tr, en)
    return t


def classify_grounding_strategy(problem_text: str) -> str:
    """
    Deterministically routes candidate problem to DIRECT, ABSENCE_REFERENCE, or ABSENCE_RESOURCE_CLEANUP.
    Uses generic semantic keyword matching without hardcoding benchmark-specific branch/class/literal names.
    """
    norm_p = normalize_text_for_routing(problem_text)
    if not norm_p:
        return STRATEGY_DIRECT

    # Absence of resource cleanup keywords
    resource_keywords = [
        "unclosed resource", "resource leak", "stream not closed", "missing close",
        "close() not called", "close() method is not called", "try-with-resources missing",
        "try-with-resources", "kaynak kapatilmiyor", "resource kapanmiyor",
        "kapatilmamis", "kapatilmiyor", "fileinputstream", "inputstream.close"
    ]
    for kw in resource_keywords:
        if kw in norm_p:
            return STRATEGY_ABSENCE_RESOURCE_CLEANUP

    # Absence of variable reference / unused variable keywords
    unused_keywords = [
        "unused", "never used", "not used", "unreferenced", "dead variable",
        "dead local", "kullanilmiyor", "kullanilmayan degisken", "kullanilmayan bir degisken",
        "kullanilmamasi", "kullanilmasi gereksiz"
    ]
    for kw in unused_keywords:
        if kw in norm_p:
            return STRATEGY_ABSENCE_REFERENCE

    return STRATEGY_DIRECT


def extract_variable_identifier(line: str) -> str | None:
    """
    Extracts variable identifier from a Java variable declaration line.
    Example: 'String strVal = "example";' -> 'strVal'
             'int count = 0;' -> 'count'
             'FileInputStream in = new FileInputStream(p);' -> 'in'
    """
    if not line:
        return None
    import re
    cleaned = normalize_code_line(line)
    # Match standard Java variable declaration pattern: Type identifier (= value)?;
    # Handles generics (e.g. List<String> list), primitive types, class types
    pattern = re.compile(r"^(?:[\w\<\>\[\]]+)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:=|;)")
    match = pattern.search(cleaned)
    if match:
        ident = match.group(1)
        # Avoid matching keywords like 'public', 'class', 'return', 'if'
        java_keywords = {"public", "private", "protected", "static", "final", "class", "interface", "enum", "return", "if", "else", "while", "for", "switch", "case", "new", "throw", "throws", "try", "catch", "finally", "void", "boolean", "int", "double", "float", "long", "short", "byte", "char"}
        if ident not in java_keywords:
            return ident
    return None


def extract_resource_identifier(line: str) -> str | None:
    """
    Extracts resource variable identifier from a Java resource creation line.
    Example: 'FileInputStream inputStream = new FileInputStream(path);' -> 'inputStream'
             'InputStream in = new FileInputStream(path);' -> 'in'
    """
    if not line:
        return None
    import re
    cleaned = normalize_code_line(line)
    # Check if line instantiates or obtains a closable/stream resource
    resource_indicators = ["stream", "reader", "writer", "channel", "connection", "socket", "client", "resource"]
    is_resource = any(ind in cleaned.lower() for ind in resource_indicators) or "new " in cleaned
    if is_resource:
        return extract_variable_identifier(cleaned)
    return None


def validate_unused_reference_absence(pr_context: str, added_lines: list[str]) -> bool:
    """
    Deterministically validates that an added variable declaration exists in added_lines,
    and its identifier is NOT used anywhere else in the enclosing method context.
    """
    import re
    if not added_lines or not pr_context:
        return False

    # Find variable declaration in added lines
    candidate_identifier = None
    declaration_line = None
    for line in added_lines:
        ident = extract_variable_identifier(line)
        if ident:
            candidate_identifier = ident
            declaration_line = line
            break

    if not candidate_identifier or not declaration_line:
        return False

    # Check for usage in pr_context outside the declaration line
    pattern = re.compile(rf"\b{re.escape(candidate_identifier)}\b")

    # Clean context lines and count occurrences
    norm_decl = normalize_code_line(declaration_line)
    context_lines = [normalize_code_line(l) for l in pr_context.splitlines() if l.strip()]

    usage_found_outside_decl = False
    for cl in context_lines:
        # Ignore diff header lines and STATUS lines
        if cl.startswith("FILE:") or cl.startswith("STATUS:") or cl.startswith("CHANGES:") or cl == "PR DIFF CHANGES":
            continue
        # If this is the declaration line itself, skip it
        if candidate_identifier in cl:
            if cl == norm_decl or (candidate_identifier in norm_decl and ("=" in cl or ";" in cl) and any(kw in cl for kw in ["String", "int", "boolean", "double", "float", "long", "Object", "var", "List", "Map", "Set"])):
                continue
            # Found in another context line
            if pattern.search(cl):
                usage_found_outside_decl = True
                break

    # Grounding is valid if declaration exists and no outside usage exists (absence confirmed)
    return not usage_found_outside_decl


def validate_resource_cleanup_absence(pr_context: str, added_lines: list[str]) -> bool:
    """
    Deterministically validates that a resource creation anchor exists in added_lines,
    and that no corresponding .close() call or try-with-resources pattern exists in the enclosing context.
    """
    import re
    if not added_lines or not pr_context:
        return False

    # Find resource creation in added lines
    resource_ident = None
    for line in added_lines:
        ident = extract_resource_identifier(line)
        if ident:
            resource_ident = ident
            break

    if not resource_ident:
        return False

    # Check 1: Is there a try-with-resources header containing the declaration?
    try_with_resources_pattern = re.compile(r"try\s*\([^)]*" + re.escape(resource_ident) + r"[^)]*\)")
    if try_with_resources_pattern.search(pr_context):
        # Cleaned up via try-with-resources -> absence NOT confirmed
        return False

    # Check 2: Is there a direct .close() call on the resource variable?
    close_pattern = re.compile(rf"\b{re.escape(resource_ident)}\s*\.\s*close\s*\(")
    if close_pattern.search(pr_context):
        # Cleaned up via close() -> absence NOT confirmed
        return False

    # Resource exists, and no cleanup pattern found -> absence of cleanup confirmed
    return True


def verify_grounding_for_candidate(problem_text: str, quote: str, added_lines: list[str], pr_context: str) -> tuple[bool, str]:
    """
    Routes and verifies grounding based on candidate problem nature.
    Returns: (grounding_valid: bool, strategy_used: str)
    """
    strategy = classify_grounding_strategy(problem_text)

    if strategy == STRATEGY_ABSENCE_REFERENCE:
        valid = validate_unused_reference_absence(pr_context, added_lines)
        return valid, strategy

    elif strategy == STRATEGY_ABSENCE_RESOURCE_CLEANUP:
        valid = validate_resource_cleanup_absence(pr_context, added_lines)
        return valid, strategy

    else:  # DIRECT
        valid = is_grounded_problem_evidence(quote, added_lines)
        return valid, STRATEGY_DIRECT


def compute_pr_change_metadata(pr_context: str, candidate_file: str, candidate_line: int) -> dict:
    """
    Computes deterministic PR change metadata from structured PR diff context.
    """
    if not pr_context:
        return {
            "file_change_status": "unknown",
            "candidate_line_change_type": "UNKNOWN",
            "introduced_by_pr": None
        }

    file_blocks = pr_context.split("=========================================")
    target_block = None
    
    clean_cand_file = candidate_file.replace("\\", "/").lower().strip() if candidate_file else ""
    cand_base = clean_cand_file.split("/")[-1] if clean_cand_file else ""

    for block in file_blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        block_file = ""
        block_status = "unknown"
        for l in lines:
            if l.startswith("FILE:"):
                block_file = l.replace("FILE:", "").strip()
            elif l.startswith("STATUS:"):
                block_status = l.replace("STATUS:", "").strip().lower()

        clean_block_file = block_file.replace("\\", "/").lower().strip()
        block_base = clean_block_file.split("/")[-1] if clean_block_file else ""

        if (clean_cand_file and (clean_cand_file == clean_block_file or clean_block_file.endswith(clean_cand_file) or clean_cand_file.endswith(clean_block_file))) or (cand_base and cand_base == block_base):
            target_block = (block, block_status)
            break

    if not target_block:
        return {
            "file_change_status": "unknown",
            "candidate_line_change_type": "UNKNOWN",
            "introduced_by_pr": None
        }

    block_text, file_status = target_block
    line_type = "UNKNOWN"

    import re
    if candidate_line is not None:
        pattern = re.compile(r"^\[(ADDED|REMOVED|CONTEXT)\]\s*(\d+)\s*\|", re.MULTILINE)
        for match in pattern.finditer(block_text):
            tag = match.group(1)
            ln = int(match.group(2))
            if ln == candidate_line:
                line_type = tag
                break

    if file_status == "added":
        if line_type in ("ADDED", "UNKNOWN"):
            introduced = True
        elif line_type == "CONTEXT":
            introduced = False
        else:
            introduced = True
    elif file_status == "modified":
        if line_type == "ADDED":
            introduced = True
        elif line_type == "CONTEXT":
            introduced = False
        else:
            introduced = None
    elif file_status == "deleted":
        introduced = False
    else:
        if line_type == "ADDED":
            introduced = True
        elif line_type == "CONTEXT":
            introduced = False
        else:
            introduced = None

    return {
        "file_change_status": file_status,
        "candidate_line_change_type": line_type,
        "introduced_by_pr": introduced
    }


def build_verifier_user_prompt(candidate_id: str, source_reviewer: str, candidate_finding: dict, pr_context: str) -> str:
    """
    Builds the user prompt for the verifier, providing it with the candidate finding,
    deterministic PR change metadata, source reviewer, and original PR diff / context details.
    Excludes suggested_fix from candidate finding representation.
    """
    cleaned_finding = {k: v for k, v in candidate_finding.items() if k != "suggested_fix"}
    finding_str = json.dumps(cleaned_finding, indent=2, ensure_ascii=False)
    
    cand_file = candidate_finding.get("file", "")
    cand_line = candidate_finding.get("line")
    pr_metadata = compute_pr_change_metadata(pr_context, cand_file, cand_line)
    metadata_str = json.dumps(pr_metadata, indent=2, ensure_ascii=False)

    user_prompt = (
        f"CANDIDATE ID: {candidate_id}\n"
        f"SOURCE REVIEWER ROLE: {source_reviewer}\n\n"
        f"CANDIDATE FINDING TO VERIFY:\n"
        f"-----------------\n"
        f"{finding_str}\n\n"
        f"PR CHANGE METADATA:\n"
        f"-----------------\n"
        f"{metadata_str}\n\n"
        f"PR DIFF AND CONTEXT:\n"
        f"-----------------\n"
        f"{pr_context}\n"
    )
    return user_prompt
