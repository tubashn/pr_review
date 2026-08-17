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
    "Aday bulgunun (candidate finding) iddia ettiği temel problemin, PR'ın değiştirdiği/eklediği kodda GERÇEKTEN MEVCUT OLUP OLMADIĞINI değerlendirmektir.\n\n"
    "KESİNLİKLE CEVAPLAMAYACAĞIN VE KAPSAM DIŞI OLAN SORULAR:\n"
    "- Bu PR iyi bir geliştirme mi?\n"
    "- Bu PR kabul edilmeli mi (should this PR be accepted)?\n"
    "- Bu PR reddedilmeli mi (should this PR be rejected)?\n"
    "- Bu PR problemi çözüyor mu?\n"
    "- Bu kod merge edilmeli mi?\n"
    "Sen Pull Request'i onaylamıyor veya reddetmiyorsun. Sadece 'Aday bulgunun temel problem iddiası değişen PR kodunda destekleniyor mu?' sorusunu cevaplıyorsun.\n\n"
    "ÖNEMLİ DEĞERLENDİRME VE KARAR KURALLARI:\n"
    "1. PR'ın yeni bir bug, güvenlik açığı veya maintainability problemi EKLEMESİ durumunda ve bulgu bunu doğru tarif ediyorsa: 'finding_supported: true' verilir. (PR'ın problem eklemesi bulgunun desteklendiğini gösterir).\n"
    "2. PR'ın bildirilen problemi çözüp çözmediğini YARGILAMA.\n"
    "3. Geliştiricinin niyetini (intent) veya kodu neden yazdığını YARGILAMA.\n"
    "4. PR içinde düzeltmenin (fix) zaten uygulanmış olmasını ŞART KOŞMA.\n"
    "5. Sadece raporlanan problemin PR kodunda fiilen var olup olmadığını değerlendir.\n"
    "6. Eğer PR'daki mevcut kod bildirilen hatayı/riski ZATEN ÖNLÜYORSA (örneğin kod zaten null-safe ise ve NPE iddia ediliyorsa): 'finding_supported: false' verilir.\n"
    "7. Birincil Sinyal (Primary Signal) 'problem' alanıdır: Adayın temel problem iddiası kod tarafından doğrulanıyorsa 'finding_supported: true' verilir. 'failure_scenario' ikincil destekleyici açıklamadır; kötü veya eksik ifade edilmiş olması tek başına bulguyu geçersiz kılmaz.\n"
    "8. Deterministic PR Change Metadata ('pr_change_metadata'): Aday satırının PR tarafından eklenip eklenmediğini gösterir ('introduced_by_pr': true). Ancak 'introduced_by_pr: true' olması bulgunun otomatik doğru olduğu anlamına gelmez; kodun gerçekten raporlanan kusuru içerip içermediğini semantik olarak doğrulamalısın.\n\n"
    "finding_supported: true Kriterleri:\n"
    "- Bulguda belirtilen problem, verilen PR diff/context ve PR metadata tarafından doğrudan destekleniyorsa.\n"
    "- Problem, PR ile eklenen ya da değiştirilen davranıştan kaynaklanıyorsa.\n"
    "- Bulgu, incelemeyi yapan reviewer rolünün (correctness_logic, security_validation, maintainability) uzmanlık alanıyla eşleşiyorsa.\n"
    "- Bulgu spekülatif değilse ve kodda somut kanıtı varsa.\n\n"
    "finding_supported: false Kriterleri:\n"
    "- Bulgu kod tarafından desteklenmiyorsa veya kod iddia edilen hatayı zaten engelliyorsa.\n"
    "- Bulgu spekülatifse, kanıtsız varsayımlar veya 'olabilir' gibi belirsizlikler içeriyorsa.\n"
    "- Bulgu yanlış reviewer rolüne aitse (Role Leakage).\n"
    "- Bulgu, PR'dan önce zaten context kodunda var olan eski bir problemi raporluyorsa.\n"
    "- Güvenlik sorunu olmayan normal bir yapı (örneğin normal bir sabit/timeout vb.) hatalı şekilde güvenlik açığı sanılmışsa.\n"
    "- Temiz, güvenli veya normal kod satırları gereksiz yere problem olarak raporlanmışsa.\n\n"
    "Örnek 1 (finding_supported: false):\n"
    "Aday Bulgu: {\n"
    "  \"file\": \"src/main/java/com/demo/config/AppConfig.java\",\n"
    "  \"line\": 12,\n"
    "  \"problem\": \"Gereksiz yere timeout değeri 30 saniye olarak belirlenmiş, bu durum security validation hatasına yol açar.\",\n"
    "  \"failure_scenario\": \"Timeout süresi uzun olduğu için DDoS ataklarında sunucu kaynakları tükenebilir.\"\n"
    "}\n"
    "Reviewer Rolü: security_validation\n"
    "PR Change Metadata: {\"file_change_status\": \"modified\", \"candidate_line_change_type\": \"ADDED\", \"introduced_by_pr\": true}\n"
    "Kod Değişikliği (PR Diff): \n"
    "  [ADDED] 12 | public static final int CONNECTION_TIMEOUT = 30000;\n"
    "Değerlendirme: finding_supported: false (Çünkü timeout değerinin 30 saniye olması genel bir konfigürasyondur ve doğrudan somut bir security açığı teşkil ettiğine dair kanıt yoktur. Raporlanan problem spekülatiftir).\n\n"
    "Örnek 2 (finding_supported: true):\n"
    "Aday Bulgu: {\n"
    "  \"file\": \"src/main/java/com/demo/math/Calculator.java\",\n"
    "  \"line\": 8,\n"
    "  \"problem\": \"Olası ArithmeticException (Division by Zero) hatası.\",\n"
    "  \"failure_scenario\": \"Eğer divisor parametresi 0 olarak gönderilirse, kod integer division sırasında sıfıra bölme hatası verip çökecektir.\"\n"
    "}\n"
    "Reviewer Rolü: correctness_logic\n"
    "PR Change Metadata: {\"file_change_status\": \"added\", \"candidate_line_change_type\": \"ADDED\", \"introduced_by_pr\": true}\n"
    "Kod Değişikliği (PR Diff): \n"
    "  [ADDED] 8 | public int divide(int dividend, int divisor) { return dividend / divisor; }\n"
    "Değerlendirme: finding_supported: true (Çünkü PR ile yeni eklenen divide metodunda sıfıra bölme kontrolü yapılmamıştır ve bu durum doğrudan correctness_logic kapsamında somut bir mantık hatası riski taşımaktadır).\n\n"
    "ÇIKTI FORMATI:\n"
    "Çıktın SADECE geçerli bir JSON olmalıdır. Markdown işaretleri (örneğin ```json) veya ek açıklama metinleri kesinlikle içermemelidir.\n"
    "Beklenen JSON yapısı:\n"
    "{\n"
    '  "candidate_id": "aday_id",\n'
    '  "finding_supported": true,\n'
    '  "confidence": "HIGH | MEDIUM | LOW",\n'
    '  "reason": "Kararının gerekçesi.",\n'
    '  "evidence_file": "Kanıt dosya yolu (varsa, yoksa null)",\n'
    '  "evidence_line": 0,\n'
    '  "evidence": "Kanıt kod satırı veya ifadesi (varsa, yoksa null)"\n'
    "}\n"
)


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
