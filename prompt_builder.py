import json
import sys
from pathlib import Path


def format_code_block(context_before: list, flagged_code: list, context_after: list) -> str:
    lines = []
    
    # Process context_before
    for item in context_before:
        line_num = item.get("line")
        code = item.get("code", "")
        lines.append(f"{line_num} | {code}")
        
    # Process flagged_code
    for item in flagged_code:
        line_num = item.get("line")
        code = item.get("code", "")
        lines.append(f"[FLAGGED] {line_num} | {code}")
        
    # Process context_after
    for item in context_after:
        line_num = item.get("line")
        code = item.get("code", "")
        lines.append(f"{line_num} | {code}")
        
    return "\n".join(lines)


def main() -> None:
    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "pmd_new_findings.json"
    output_path = script_dir / "qwen_requests.json"
    
    # 1. Read input
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                print(f"Error: Input file '{input_path}' is empty.", file=sys.stderr)
                sys.exit(1)
            findings = json.loads(content)
    except Exception as e:
        print(f"Error: Failed to read or parse '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)
        
    if not isinstance(findings, list) or len(findings) == 0:
        print("Error: No findings found in the input file.", file=sys.stderr)
        sys.exit(1)
        
    requests = []
    
    for idx, finding in enumerate(findings, start=1):
        tool = finding.get("tool", "")
        rule = finding.get("rule", "")
        ruleset = finding.get("ruleset", "")
        priority = finding.get("priority", 5)
        file_path = finding.get("file", "")
        line = finding.get("line", 0)
        message = finding.get("message", "")
        
        context_before = finding.get("context_before", [])
        flagged_code = finding.get("flagged_code", [])
        context_after = finding.get("context_after", [])
        
        # Format the code context block
        code_context_str = format_code_block(context_before, flagged_code, context_after)
        
        # Build System Prompt
        system_prompt = (
            "Sen Java kod düzeltme ajanısın.\n"
            "Statik analiz aracı problemi zaten tespit etti.\n"
            "Sadece verilen bulguyu değerlendir.\n"
            "Başka hata arama veya uydurma.\n"
            "İlgisiz kodu değiştirme.\n"
            "Problemi teknik olarak açıkla.\n"
            "Minimum gerekli düzeltmeyi üret.\n"
            "Otomatik düzeltmenin güvenli olup olmadığını değerlendir.\n"
            "Girdi olarak verilen statik analiz bulgusuna ve kod bağlamına (CODE CONTEXT) dayanarak, problemi düzeltecek en küçük değişikliği öner.\n"
            "Geçerli JSON dışında hiçbir şey döndürme. JSON çıktısında başka hiçbir açıklama, markdown işareti veya ek metin olmamalıdır.\n\n"
            "Beklenen JSON formatı:\n"
            "{\n"
            '  "explanation": "Problemin teknik açıklaması.",\n'
            '  "suggested_fix": "Hatalı kodun düzeltilmiş hali veya yapılacak düzeltme tarifi.",\n'
            '  "fixed_code": "Dosyanın düzeltilmiş satır veya satırları (tam dosya değil, sadece düzeltilen kısım).",\n'
            '  "auto_fix_safe": true/false\n'
            "}"
        )
        
        # Build User Prompt
        user_prompt = (
            "STATIC ANALYSIS FINDING\n"
            f"- Tool: {tool}\n"
            f"- Rule: {rule}\n"
            f"- Ruleset: {ruleset}\n"
            f"- Priority: {priority}\n"
            f"- File: {file_path}\n"
            f"- Line: {line}\n"
            f"- Message: {message}\n\n"
            "CODE CONTEXT\n"
            f"{code_context_str}"
        )
        
        requests.append({
            "finding_id": idx,
            "metadata": {
                "tool": tool,
                "rule": rule,
                "priority": priority,
                "file": file_path,
                "line": line
            },
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        })
        
    # Write requests to output file
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(requests, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to write to '{output_path}': {e}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Generated prompt count: {len(requests)}")
    if requests:
        print("\n--- FIRST GENERATED PROMPT ---")
        print(json.dumps(requests[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
