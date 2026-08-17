import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from collections import Counter
import xml.etree.ElementTree as ET


def normalize_path(p: str) -> str:
    return p.replace("\\", "/").lower().strip()


def extract_context(file_path: Path, begin_line: int, end_line: int) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        
        num_lines = len(lines)
        if num_lines == 0:
            return {
                "context_before": [],
                "flagged_code": [],
                "context_after": []
            }
            
        cleaned_lines = [line.rstrip('\r\n') for line in lines]
        
        b_line = min(num_lines, max(1, begin_line))
        e_line = min(num_lines, max(b_line, end_line))
        
        cb_start = max(1, b_line - 15)
        cb_end = b_line - 1
        
        context_before = []
        for line_num in range(cb_start, cb_end + 1):
            context_before.append({
                "line": line_num,
                "code": cleaned_lines[line_num - 1]
            })
            
        flagged_code = []
        for line_num in range(b_line, e_line + 1):
            flagged_code.append({
                "line": line_num,
                "code": cleaned_lines[line_num - 1]
            })
            
        ca_start = e_line + 1
        ca_end = min(num_lines, e_line + 15)
        
        context_after = []
        for line_num in range(ca_start, ca_end + 1):
            context_after.append({
                "line": line_num,
                "code": cleaned_lines[line_num - 1]
            })
            
        return {
            "context_before": context_before,
            "flagged_code": flagged_code,
            "context_after": context_after
        }
    except Exception as e:
        return {
            "context_error": str(e)
        }



def main() -> None:
    # Accept a Git branch name and target repository path as command-line arguments
    # Usage: python scan_branch.py [--repo <target-repo-path>] <branch-name>
    target_repo = None
    branch_name = None

    args = sys.argv[1:]
    if "--repo" in args:
        try:
            repo_idx = args.index("--repo")
            target_repo = Path(args[repo_idx + 1]).resolve()
            # Remove --repo <path> from args list
            args.pop(repo_idx + 1)
            args.pop(repo_idx)
        except (ValueError, IndexError):
            print("Error: --repo option requires a path argument.", file=sys.stderr)
            sys.exit(1)

    if len(args) < 1:
        print("Error: Missing branch name argument.", file=sys.stderr)
        print("Usage: python scan_branch.py [--repo <target-repo-path>] <branch-name>", file=sys.stderr)
        sys.exit(1)

    branch_name = args[0]

    # Resolve review agent root (the directory containing this script)
    review_root = Path(__file__).resolve().parent
    baseline_path = review_root / "pmd_baseline.json"
    new_findings_path = review_root / "pmd_new_findings.json"

    # If target_repo is not specified, default to the current directory
    if target_repo is None:
        target_repo = Path.cwd()

    print(f"Target repository: {target_repo}")
    print(f"Review agent root: {review_root}")
    print(f"Scanning branch: {branch_name}")

    # 3. Run git fetch origin inside target repository
    print("Running git fetch origin...")
    try:
        subprocess.run(["git", "fetch", "origin"], cwd=str(target_repo), check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print("Error: Git command not found. Please ensure Git is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: Git fetch origin failed:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

    # 4. Create a temporary detached Git worktree from origin/<branch-name>
    temp_dir = tempfile.mkdtemp(prefix="pmd_scan_")
    temp_worktree_path = Path(temp_dir).resolve()

    print(f"Creating temporary Git worktree at {temp_worktree_path} for origin/{branch_name}...")
    worktree_created = False
    try:
        result_wt = subprocess.run(
            ["git", "worktree", "add", "--detach", str(temp_worktree_path), f"origin/{branch_name}"],
            cwd=str(target_repo),
            capture_output=True,
            text=True
        )
        if result_wt.returncode != 0:
            print(f"Error: Failed to create git worktree for origin/{branch_name}:\n{result_wt.stderr}", file=sys.stderr)
            sys.exit(1)
            
        worktree_created = True

        # 5. Run Maven command inside the temporary worktree
        print("Running Maven PMD scan inside the worktree...")
        mvn_cmd = "mvn clean compile org.apache.maven.plugins:maven-pmd-plugin:3.28.0:pmd"
        
        try:
            result = subprocess.run(
                mvn_cmd,
                shell=True,
                cwd=str(temp_worktree_path),
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                if "is not recognized as an internal or external command" in result.stderr or "not found" in result.stderr or result.returncode == 9009:
                    print("Error: Maven (mvn) was not found in your PATH. Please ensure Maven is installed.", file=sys.stderr)
                else:
                    print(f"Error: Maven command failed with exit code {result.returncode}:\n{result.stderr}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"Error: Maven command failure: {e}", file=sys.stderr)
            sys.exit(1)

        # 6. Read the generated target/pmd.xml
        pmd_report_path = temp_worktree_path / "target" / "pmd.xml"
        if not pmd_report_path.exists():
            print(f"Error: PMD report not created at {pmd_report_path}.", file=sys.stderr)
            sys.exit(1)

        # 7. Parse PMD findings
        findings = []
        try:
            tree = ET.parse(pmd_report_path)
            root = tree.getroot()
            for file_element in root.findall(".//{*}file"):
                absolute_file = file_element.attrib.get("name", "")
                try:
                    file_name = str(
                        Path(absolute_file)
                        .resolve()
                        .relative_to(temp_worktree_path.resolve())
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
        except Exception as e:
            print(f"Error parsing PMD report: {e}", file=sys.stderr)
            sys.exit(1)

        # 8. Load the baseline
        baseline_findings = []
        if baseline_path.exists():
            try:
                with open(baseline_path, "r", encoding="utf-8") as f:
                    baseline_findings = json.load(f)
            except Exception as e:
                print(f"Error: Failed to load baseline from {baseline_path}: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Warning: Baseline file not found at {baseline_path}.", file=sys.stderr)

        # 9. Compare findings using normalized file path, rule, message
        baseline_keys = set()
        for b in baseline_findings:
            file_key = normalize_path(b.get("file", ""))
            rule_key = b.get("rule", "").strip()
            message_key = b.get("message", "").strip()
            baseline_keys.add((file_key, rule_key, message_key))

        new_findings = []
        for f in findings:
            file_key = normalize_path(f.get("file", ""))
            rule_key = f.get("rule", "").strip()
            message_key = f.get("message", "").strip()
            if (file_key, rule_key, message_key) not in baseline_keys:
                new_findings.append(f)

        # Extract code context for each new finding
        for f in new_findings:
            relative_file = f.get("file", "")
            file_path = temp_worktree_path / relative_file
            context = extract_context(file_path, f.get("line", 0), f.get("end_line", 0))
            f.update(context)

        # 10. Save only findings that do not exist in the baseline
        try:
            with open(new_findings_path, "w", encoding="utf-8") as f:
                json.dump(new_findings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error: Failed to write new findings to {new_findings_path}: {e}", file=sys.stderr)
            sys.exit(1)

        # 11. Print statistics and findings
        print(f"Scanned branch: {branch_name}")
        print(f"Baseline findings: {len(baseline_findings)}")
        print(f"Current findings: {len(findings)}")
        print(f"New findings: {len(new_findings)}")
        
        # Use collections.Counter to count new findings by rule
        new_rules_counter = Counter(f["rule"] for f in new_findings)
        if new_rules_counter:
            print("\nNew findings by rule (Counter):")
            for rule, count in new_rules_counter.items():
                print(f"  {rule}: {count}")

        print("\nNew findings details:")
        print(json.dumps(new_findings, indent=2, ensure_ascii=False))

    finally:
        # 12. Always remove the temporary Git worktree, including when an error occurs
        if worktree_created:
            print("Cleaning up temporary Git worktree...")
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(temp_worktree_path)],
                    cwd=str(target_repo),
                    capture_output=True,
                    text=True
                )
            except Exception as e:
                print(f"Warning during worktree cleanup: {e}", file=sys.stderr)

        # Ensure directory is fully removed
        try:
            if temp_worktree_path.exists():
                shutil.rmtree(temp_worktree_path, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
