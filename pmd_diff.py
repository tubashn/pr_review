import json
from collections import Counter
from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parent
BASELINE_FILE = AGENT_DIR / "pmd_baseline.json"
CURRENT_FILE = AGENT_DIR / "pmd_findings.json"
OUTPUT_FILE = AGENT_DIR / "pmd_new_findings.json"


def load_json(file_path: Path) -> list[dict]:
    if not file_path.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

    return json.loads(file_path.read_text(encoding="utf-8"))


def fingerprint(finding: dict) -> tuple:
    return (
        finding.get("file", "").replace("\\", "/"),
        finding.get("rule", ""),
        finding.get("message", ""),
    )


def find_new_findings(
    baseline: list[dict],
    current: list[dict],
) -> list[dict]:
    baseline_counts = Counter(
        fingerprint(finding)
        for finding in baseline
    )

    new_findings = []

    for finding in current:
        key = fingerprint(finding)

        if baseline_counts[key] > 0:
            baseline_counts[key] -= 1
        else:
            new_findings.append(finding)

    return new_findings


def main() -> None:
    baseline = load_json(BASELINE_FILE)
    current = load_json(CURRENT_FILE)

    new_findings = find_new_findings(
        baseline=baseline,
        current=current,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            new_findings,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Baseline bulgu sayısı: {len(baseline)}")
    print(f"Güncel bulgu sayısı: {len(current)}")
    print(f"Yeni bulgu sayısı: {len(new_findings)}")
    print(
        json.dumps(
            new_findings,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()