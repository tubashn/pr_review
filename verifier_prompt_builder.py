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
