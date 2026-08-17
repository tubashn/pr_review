import json
import sys
from pathlib import Path

# System Prompts copied from reviewer_prompt_builder.py
SYSTEM_PROMPTS = {
    "correctness_logic": (
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
    ),
    "security_validation": (
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
    ),
    "maintainability": (
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
}


def parse_and_format_diff(file_path: str, pr_diff: str, status: str) -> str:
    lines = pr_diff.splitlines()
    formatted = []
    formatted.append(f"FILE: {file_path}")
    formatted.append(f"STATUS: {status}")
    formatted.append("CHANGES:")
    
    old_line_ptr = 0
    new_line_ptr = 0
    in_hunk = False
    
    for line in lines:
        if line.startswith("@@"):
            parts = line.split(" ")
            if len(parts) >= 3:
                old_part = parts[1]
                new_part = parts[2]
                try:
                    old_line_ptr = int(old_part.split(",")[0].replace("-", ""))
                except ValueError:
                    old_line_ptr = 0
                try:
                    new_line_ptr = int(new_part.split(",")[0].replace("+", ""))
                except ValueError:
                    new_line_ptr = 0
            in_hunk = True
        elif in_hunk:
            if line.startswith("+"):
                formatted.append(f"[ADDED] {new_line_ptr} | {line[1:]}")
                new_line_ptr += 1
            elif line.startswith("-"):
                formatted.append(f"[REMOVED] {old_line_ptr} | {line[1:]}")
                old_line_ptr += 1
            else:
                code_content = line[1:] if len(line) > 0 else ""
                formatted.append(f"[CONTEXT] {new_line_ptr} | {code_content}")
                old_line_ptr += 1
                new_line_ptr += 1
                
    return "\n".join(formatted)


def get_file_status(pr_diff: str) -> str:
    lines = pr_diff.splitlines()
    has_removed = False
    for line in lines:
        if line.startswith("-") and not line.startswith("---"):
            has_removed = True
            break
    return "added" if not has_removed else "modified"


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    catalog_path = script_dir / "scenario_catalog.json"
    train_path = script_dir / "lora_train.jsonl"
    val_path = script_dir / "lora_validation.jsonl"

    if not catalog_path.exists():
        print(f"Error: scenario_catalog.json not found at {catalog_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            scenarios = json.load(f)
    except Exception as e:
        print(f"Error reading scenario catalog: {e}", file=sys.stderr)
        sys.exit(1)

    train_samples = []
    val_samples = []

    for sc in scenarios:
        sc_id = sc.get("source_scenario_id")
        category = sc.get("scenario_category")
        intended = sc.get("intended_reviewer")
        file_path = sc.get("file")
        pr_diff = sc.get("pr_diff")
        split = sc.get("split", "train")
        gt_finding = sc.get("ground_truth_finding")

        # Determine status
        status = get_file_status(pr_diff)
        # Format the diff for the user prompt
        formatted_diff = parse_and_format_diff(file_path, pr_diff, status)

        user_prompt = (
            "PR DIFF CHANGES\n"
            "-----------------\n"
            f"{formatted_diff}"
        )

        # Generate sample for each of the 3 reviewers
        for reviewer in ["correctness_logic", "security_validation", "maintainability"]:
            system_prompt = SYSTEM_PROMPTS[reviewer]
            
            # Determine assistant expected output
            if reviewer == intended and gt_finding is not None:
                findings = [gt_finding]
            else:
                findings = []

            assistant_content = json.dumps({"reviewer": reviewer, "findings": findings}, ensure_ascii=False)

            sample = {
                "id": f"{sc_id}-{reviewer}",
                "source_scenario_id": sc_id,
                "scenario_category": category,
                "reviewer": reviewer,
                "split": split,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    },
                    {
                        "role": "assistant",
                        "content": assistant_content
                    }
                ]
            }

            if split == "train":
                train_samples.append(sample)
            else:
                val_samples.append(sample)

    # Write output JSONL files
    try:
        with open(train_path, "w", encoding="utf-8") as f:
            for s in train_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"LoRA train dataset generated: {train_path} ({len(train_samples)} samples)")

        with open(val_path, "w", encoding="utf-8") as f:
            for s in val_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"LoRA validation dataset generated: {val_path} ({len(val_samples)} samples)")

    except Exception as e:
        print(f"Error writing LoRA dataset files: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
