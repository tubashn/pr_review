import json
import sys
from pathlib import Path


def format_pr_diff(pr_diff: list) -> str:
    formatted_files = []
    for file_data in pr_diff:
        file_path = file_data.get("file", "")
        status = file_data.get("status", "")
        
        file_lines = []
        file_lines.append(f"FILE: {file_path}")
        file_lines.append(f"STATUS: {status}")
        file_lines.append("CHANGES:")
        
        for hunk in file_data.get("hunks", []):
            for item in hunk:
                t = item.get("type", "")
                code = item.get("code", "")
                old_l = item.get("old_line")
                new_l = item.get("new_line")
                
                if t == "ADDED":
                    file_lines.append(f"[ADDED] {new_l} | {code}")
                elif t == "REMOVED":
                    file_lines.append(f"[REMOVED] {old_l} | {code}")
                elif t == "CONTEXT":
                    file_lines.append(f"[CONTEXT] {new_l} | {code}")
                    
        formatted_files.append("\n".join(file_lines))
        
    return "\n\n=========================================\n\n".join(formatted_files)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "pr_diff.json"
    output_path = script_dir / "reviewer_requests.json"

    # Read diff input
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                print(f"Error: Input file '{input_path}' is empty.", file=sys.stderr)
                sys.exit(1)
            pr_diff = json.loads(content)
    except Exception as e:
        print(f"Error: Failed to read or parse '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(pr_diff, list):
        print("Error: Input file must contain a JSON list.", file=sys.stderr)
        sys.exit(1)

    formatted_diff = format_pr_diff(pr_diff)

    # Reviewer 1: correctness_logic
    correctness_system = (
        "Sen Java/Spring kod inceleme (code review) uzmanısın. Rolün correctness_logic incelemesi yapmaktır.\n"
        "Görevlerin:\n"
        "- Java/Spring kodunda correctness ve business logic problemlerini ara.\n"
        "- Yanlış koşullar, yanlış return değerleri, null handling, state değişimleri, transaction davranışı ve edge-case problemlerine odaklan.\n"
        "- Sadece PR tarafından eklenen veya değiştirilen davranıştan kaynaklanan problemleri raporla.\n"
        "- Eski context satırlarında zaten bulunan problemleri PR bulgusu olarak raporlama.\n"
        "- Somut bir failure scenario açıklayamıyorsan finding üretme.\n"
        "- Stil veya maintainability problemleri raporlama.\n"
        "- Security finding raporlama.\n"
        "- Emin olmadığın şeyi uydurma.\n\n"
        "Çıktın SADECE geçerli bir JSON olmalıdır. Markdown işaretleri (örneğin ```json) veya ek açıklama metinleri kesinlikle içermemelidir.\n"
        "Beklenen JSON formatı:\n"
        "{\n"
        '  "reviewer": "correctness_logic",\n'
        '  "findings": [\n'
        "    {\n"
        '      "file": "dosya_yolu",\n'
        '      "line": 64,\n'
        '      "certainty": "DEFINITE | POSSIBLE",\n'
        '      "problem": "Problemin açıklaması.",\n'
        '      "failure_scenario": "Problemin tetiklenebileceği somut senaryo açıklaması.",\n'
        '      "suggested_fix": "Düzeltilmiş kod veya düzeltme önerisi."\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Eğer hiçbir problem yoksa:\n"
        "{\n"
        '  "reviewer": "correctness_logic",\n'
        '  "findings": []\n'
        "}"
    )

    # Reviewer 2: security_validation
    security_system = (
        "Sen Java/Spring kod inceleme (code review) uzmanısın. Rolün security_validation incelemesi yapmaktır.\n"
        "Görevlerin:\n"
        "- Security ve input validation problemlerini ara.\n"
        "- Hardcoded credential/secret, authorization, authentication, unsafe input handling, injection riski, sensitive data exposure gibi problemlere odaklan.\n"
        "- Sadece PR tarafından eklenen veya değiştirilen koddan kaynaklanan problemleri raporla.\n"
        "- Somut risk yoksa finding üretme.\n"
        "- Maintainability veya genel stil problemlerini raporlama.\n\n"
        "Çıktın SADECE geçerli bir JSON olmalıdır. Markdown işaretleri (örneğin ```json) veya ek açıklama metinleri kesinlikle içermemelidir.\n"
        "Beklenen JSON formatı:\n"
        "{\n"
        '  "reviewer": "security_validation",\n'
        '  "findings": [\n'
        "    {\n"
        '      "file": "dosya_yolu",\n'
        '      "line": 64,\n'
        '      "certainty": "DEFINITE | POSSIBLE",\n'
        '      "problem": "Güvenlik açığı/probleminin açıklaması.",\n'
        '      "failure_scenario": "Güvenlik açığının/riskinin tetiklenebileceği senaryo açıklaması.",\n'
        '      "suggested_fix": "Düzeltilmiş kod veya düzeltme önerisi."\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Eğer hiçbir problem yoksa:\n"
        "{\n"
        '  "reviewer": "security_validation",\n'
        '  "findings": []\n'
        "}"
    )

    # Reviewer 3: maintainability
    maintainability_system = (
        "Sen Java/Spring kod inceleme (code review) uzmanısın. Rolün maintainability incelemesi yapmaktır.\n"
        "Görevlerin:\n"
        "- Maintainability ve açık code quality problemlerini ara.\n"
        "- Unused code, redundant expression, gereksiz boolean comparison, dead code, gereksiz karmaşıklık gibi konulara odaklan.\n"
        "- Sadece PR tarafından eklenen veya değiştirilen kodu değerlendir.\n"
        "- Salt kişisel stil tercihlerini finding olarak raporlama.\n"
        "- Correctness veya security problemi raporlama.\n\n"
        "Çıktın SADECE geçerli bir JSON olmalıdır. Markdown işaretleri (örneğin ```json) veya ek açıklama metinleri kesinlikle içermemelidir.\n"
        "Beklenen JSON formatı:\n"
        "{\n"
        '  "reviewer": "maintainability",\n'
        '  "findings": [\n'
        "    {\n"
        '      "file": "dosya_yolu",\n'
        '      "line": 64,\n'
        '      "certainty": "DEFINITE | POSSIBLE",\n'
        '      "problem": "Bakım/kalite probleminin açıklaması.",\n'
        '      "failure_scenario": "Bakım zorluğu veya karmaşıklık senaryosu açıklaması.",\n'
        '      "suggested_fix": "Düzeltilmiş kod veya düzeltme önerisi."\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Eğer hiçbir problem yoksa:\n"
        "{\n"
        '  "reviewer": "maintainability",\n'
        '  "findings": []\n'
        "}"
    )

    user_prompt = (
        "PR DIFF CHANGES\n"
        "-----------------\n"
        f"{formatted_diff}"
    )

    requests = [
        {
            "reviewer": "correctness_logic",
            "system_prompt": correctness_system,
            "user_prompt": user_prompt
        },
        {
            "reviewer": "security_validation",
            "system_prompt": security_system,
            "user_prompt": user_prompt
        },
        {
            "reviewer": "maintainability",
            "system_prompt": maintainability_system,
            "user_prompt": user_prompt
        }
    ]

    # Write output to agent/reviewer_requests.json
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(requests, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to write to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print(f"Created reviewers count: {len(requests)}")
    print(f"Reviewer names: {', '.join([r['reviewer'] for r in requests])}")
    print("\n=========================================")
    print("MAINTAINABILITY SYSTEM PROMPT:")
    print("=========================================")
    print(requests[2]["system_prompt"])
    print("\n=========================================")
    print("MAINTAINABILITY USER PROMPT:")
    print("=========================================")
    print(requests[2]["user_prompt"])


if __name__ == "__main__":
    main()
