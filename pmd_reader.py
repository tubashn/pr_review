import json
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PMD_REPORT = PROJECT_ROOT / "target" / "pmd.xml"
OUTPUT_FILE = Path(__file__).resolve().parent / "pmd_findings.json"


def parse_pmd_report(report_path: Path) -> list[dict]:
    if not report_path.exists():
        raise FileNotFoundError(
            f"PMD raporu bulunamadı: {report_path}\n"
            "Önce PMD analizini çalıştır."
        )

    tree = ET.parse(report_path)
    root = tree.getroot()

    findings = []

    for file_element in root.findall(".//{*}file"):
        absolute_file = file_element.attrib.get("name", "")

        try:
            file_name = str(
                Path(absolute_file)
                .resolve()
                .relative_to(PROJECT_ROOT.resolve())
            )
        except ValueError:
            file_name = absolute_file

        for violation in file_element.findall("{*}violation"):
            findings.append(
                {
                    "tool": "PMD",
                    "file": file_name,
                    "line": int(violation.attrib.get("beginline", 0)),
                    "end_line": int(violation.attrib.get("endline", 0)),
                    "rule": violation.attrib.get("rule", ""),
                    "ruleset": violation.attrib.get("ruleset", ""),
                    "priority": int(violation.attrib.get("priority", 5)),
                    "message": (violation.text or "").strip(),
                }
            )

    return findings


def main() -> None:
    findings = parse_pmd_report(PMD_REPORT)

    OUTPUT_FILE.write_text(
        json.dumps(findings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"{len(findings)} PMD bulgusu okundu.")
    print(f"JSON dosyası oluşturuldu: {OUTPUT_FILE}")

    print(
        json.dumps(
            findings,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()