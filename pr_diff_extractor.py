import sys
import subprocess
import json
from pathlib import Path


def parse_diff_hunks(diff_output: str) -> list:
    hunks = []
    lines = diff_output.splitlines()
    
    current_hunk = None
    old_line_ptr = 0
    new_line_ptr = 0
    
    for line in lines:
        if line.startswith("@@"):
            parts = line.split(" ")
            if len(parts) >= 3:
                # old part format: -start,count or -start
                old_part = parts[1]
                # new part format: +start,count or +start
                new_part = parts[2]
                
                try:
                    old_start = int(old_part.split(",")[0].replace("-", ""))
                except ValueError:
                    old_start = 0
                try:
                    new_start = int(new_part.split(",")[0].replace("+", ""))
                except ValueError:
                    new_start = 0
                
                old_line_ptr = old_start
                new_line_ptr = new_start
            
            if current_hunk is not None:
                hunks.append(current_hunk)
            current_hunk = []
            
        elif current_hunk is not None:
            if line.startswith("+"):
                current_hunk.append({
                    "type": "ADDED",
                    "old_line": None,
                    "new_line": new_line_ptr,
                    "code": line[1:]
                })
                new_line_ptr += 1
            elif line.startswith("-"):
                current_hunk.append({
                    "type": "REMOVED",
                    "old_line": old_line_ptr,
                    "new_line": None,
                    "code": line[1:]
                })
                old_line_ptr += 1
            else:
                code_content = line[1:] if len(line) > 0 else ""
                current_hunk.append({
                    "type": "CONTEXT",
                    "old_line": old_line_ptr,
                    "new_line": new_line_ptr,
                    "code": code_content
                })
                old_line_ptr += 1
                new_line_ptr += 1
                
    if current_hunk is not None and len(current_hunk) > 0:
        hunks.append(current_hunk)
        
    return hunks


def main() -> None:
    # Accept a Git branch name and target repository path as command-line arguments
    # Usage: python pr_diff_extractor.py [--repo <target-repo-path>] <branch-name>
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
        print("Usage: python pr_diff_extractor.py [--repo <target-repo-path>] <branch-name>", file=sys.stderr)
        sys.exit(1)

    branch_name = args[0]

    if target_repo is None:
        target_repo = Path.cwd()

    print(f"Target repository: {target_repo}")

    # 3. Run git fetch origin
    print("Running git fetch origin...")
    try:
        subprocess.run(["git", "fetch", "origin"], cwd=str(target_repo), check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print("Error: Git command not found.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: Git fetch origin failed:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

    # 12. Check if branch exists
    res = subprocess.run(["git", "rev-parse", "--verify", f"origin/{branch_name}"], cwd=str(target_repo), capture_output=True)
    if res.returncode != 0:
        print(f"Error: Branch 'origin/{branch_name}' does not exist on origin.", file=sys.stderr)
        sys.exit(1)

    # 4. Get diff files and status
    try:
        status_res = subprocess.run(
            ["git", "diff", "--name-status", "origin/main...origin/" + branch_name, "--", "*.java"],
            cwd=str(target_repo),
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to compare branches:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

    files_list = []
    lines = status_res.stdout.splitlines()
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            status_char, file_path = parts
            
            # Map status char to status
            if status_char.startswith("A"):
                status = "added"
            elif status_char.startswith("D"):
                status = "deleted"
            else:
                status = "modified"
                
            files_list.append((file_path, status))

    diff_results = []
    total_added = 0
    total_removed = 0

    for file_path, status in files_list:
        # Get diff with 15 lines context (-U15)
        try:
            diff_res = subprocess.run(
                ["git", "diff", "-U15", "origin/main...origin/" + branch_name, "--", file_path],
                cwd=str(target_repo),
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to get diff for {file_path}:\n{e.stderr}", file=sys.stderr)
            continue
            
        hunks = parse_diff_hunks(diff_res.stdout)
        
        # Count total added and removed lines
        for hunk in hunks:
            for item in hunk:
                if item["type"] == "ADDED":
                    total_added += 1
                elif item["type"] == "REMOVED":
                    total_removed += 1
                    
        diff_results.append({
            "file": file_path,
            "status": status,
            "hunks": hunks
        })

    # 10. Write output to agent/pr_diff.json
    script_dir = Path(__file__).resolve().parent
    output_path = script_dir / "pr_diff.json"
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(diff_results, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to write to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # 11. Print summary
    print(f"Branch name: {branch_name}")
    print(f"Changed Java files count: {len(diff_results)}")
    print(f"Total ADDED lines: {total_added}")
    print(f"Total REMOVED lines: {total_removed}")
    print("\n--- GENERATED JSON ---")
    print(json.dumps(diff_results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
