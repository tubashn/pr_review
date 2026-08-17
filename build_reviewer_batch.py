import sys
import subprocess
import json
from pathlib import Path


def main() -> None:
    branches = [
        "tuba-test",
        "tuba-test-hardcoded-secret",
        "tuba-test-redundant-boolean",
        "tuba-test-unclosed-resource",
        "tuba-test-clean-change"
    ]
    
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    
    batch_requests = []
    branch_summary = {}
    
    python_exe = sys.executable
    
    for branch in branches:
        print(f"Processing branch: {branch}...")
        
        # 1. Run pr_diff_extractor
        extractor_cmd = [python_exe, str(script_dir / "pr_diff_extractor.py"), branch]
        try:
            subprocess.run(
                extractor_cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error: pr_diff_extractor.py failed on branch '{branch}':\n{e.stderr}", file=sys.stderr)
            sys.exit(1)
            
        # 2. Run reviewer_prompt_builder
        builder_cmd = [python_exe, str(script_dir / "reviewer_prompt_builder.py")]
        try:
            subprocess.run(
                builder_cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error: reviewer_prompt_builder.py failed on branch '{branch}':\n{e.stderr}", file=sys.stderr)
            sys.exit(1)
            
        # 3. Read reviewer_requests.json
        req_path = script_dir / "reviewer_requests.json"
        if not req_path.exists():
            print(f"Error: reviewer_requests.json was not created on branch '{branch}'.", file=sys.stderr)
            sys.exit(1)
            
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                requests = json.load(f)
        except Exception as e:
            print(f"Error: Failed to read reviewer_requests.json on branch '{branch}': {e}", file=sys.stderr)
            sys.exit(1)
            
        branch_reviewers = []
        for req in requests:
            reordered_req = {
                "branch": branch,
                "reviewer": req.get("reviewer"),
                "system_prompt": req.get("system_prompt"),
                "user_prompt": req.get("user_prompt")
            }
            batch_requests.append(reordered_req)
            branch_reviewers.append(req.get("reviewer"))
            
        branch_summary[branch] = branch_reviewers

    # Save to reviewer_batch_requests.json
    batch_path = script_dir / "reviewer_batch_requests.json"
    try:
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump(batch_requests, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to write to {batch_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Print results
    print("\n=========================================")
    print("BATCH COMPILATION SUMMARY")
    print("=========================================")
    print(f"Processed branches count: {len(branches)}")
    print(f"Total reviewer requests count: {len(batch_requests)}")
    print("\nReviewers created per branch:")
    for br, reviewers in branch_summary.items():
        print(f"  {br}: {', '.join(reviewers)}")


if __name__ == "__main__":
    main()
