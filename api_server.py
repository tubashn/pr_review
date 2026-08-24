"""
FastAPI Server for AI Pull Request Review Agent
Exposes REST endpoints for PR code review orchestration with:
- Model caching (Lazy loading & singleton in-memory reuse)
- Concurrency Lock (GPU collision avoidance)
- Strict Git repository validation & error handling
- Environment-based configuration
- Full OpenAPI / Swagger documentation
- Secure GitHub Webhook Ingestion (/webhook/github) with HMAC SHA-256 verification,
  repo allowlist, PR+SHA idempotency store, and non-blocking background execution.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from run_pr_review import run_review
from webhook_idempotency import WebhookIdempotencyStore
from github_client import GitHubClient

# Configure Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("pr_review_api")

# Environment Configuration Defaults
DEFAULT_MODEL = os.getenv("PR_REVIEW_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
DEFAULT_BACKEND = os.getenv("PR_REVIEW_BACKEND", "transformers")
DEFAULT_QUANTIZATION = os.getenv("PR_REVIEW_QUANTIZATION", "4bit")
DEFAULT_DEVICE = os.getenv("PR_REVIEW_DEVICE", "auto")
DEFAULT_API_BASE = os.getenv("PR_REVIEW_API_BASE", None)
DEFAULT_API_KEY = os.getenv("PR_REVIEW_API_KEY", None)
DEFAULT_FIX_AGENT_ENABLED = os.getenv("PR_REVIEW_FIX_AGENT_ENABLED", "false").lower() in ("true", "1", "yes")

# Webhook Configuration
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", None)
GITHUB_ALLOWED_REPOS = os.getenv("GITHUB_ALLOWED_REPOS", None)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)

app = FastAPI(
    title="PR Review Agent API",
    description="End-to-End AI Pull Request Review Service using static analysis, AST verification, LLM reasoning, and GitHub Webhooks.",
    version="1.1.0"
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Model Cache, GPU Concurrency Lock, and Idempotency Store
MODEL_CACHE: Dict[str, Any] = {}
INFERENCE_LOCK = asyncio.Lock()
IDEMPOTENCY_STORE = WebhookIdempotencyStore()


# Pydantic Request & Response Models
class HealthResponse(BaseModel):
    status: str = Field("ok", description="Service health status")
    service: str = Field("pr-review-agent", description="Service identifier")
    model: str = Field(..., description="Configured LLM verifier model")
    backend: str = Field(..., description="Inference backend engine")
    quantization: str = Field(..., description="Model quantization mode")
    model_loaded: bool = Field(..., description="Whether model is currently loaded in memory")
    webhook_enabled: bool = Field(True, description="Whether GitHub webhook endpoint is active")
    gpu_available: bool = Field(False, description="Whether CUDA GPU is accessible")
    gpu_device: Optional[str] = Field(None, description="Name of accessible CUDA device if available")


class ReviewRequest(BaseModel):
    repo: str = Field(..., description="Absolute or relative path to target Git repository")
    branch: str = Field(..., description="Pull Request branch to review")
    base: str = Field("main", description="Base branch to compare against (default: main)")
    pmd: bool = Field(False, description="Enable Maven PMD static analysis if available")
    dry_run: bool = Field(False, description="Run in mock/dry-run mode without GPU model inference")
    suggest_fixes: Optional[bool] = Field(None, description="Enable automated patch suggestions for eligible findings (defaults to PR_REVIEW_FIX_AGENT_ENABLED)")


class FindingDetail(BaseModel):
    candidate_id: str
    source_reviewer: str
    file: str
    line: Optional[int] = None
    code_snippet: Optional[str] = None
    problem: str
    failure_scenario: Optional[str] = None
    suggested_fix: Optional[str] = None
    decision: str
    verification_tier: str
    verifier_reason: Optional[str] = None
    verifier_evidence: Optional[str] = None


class ReviewResponse(BaseModel):
    target_repo: str
    branch: str
    base_branch: str
    execution_time_seconds: Optional[float] = None
    model_id: str
    backend: str
    changed_files_count: int
    changed_files: List[str]
    candidate_count: int
    verified_findings_count: int
    rejected_findings_count: int
    verified_findings: List[Dict[str, Any]]
    rejected_findings: List[Dict[str, Any]]
    fix_suggestions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Automated patch suggestions for eligible findings")
    status: Optional[str] = None


class WebhookStatusResponse(BaseModel):
    review_key: str
    status: str
    repository: str
    pr_number: int
    head_sha: str
    created_at: float
    updated_at: float
    error: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


def validate_git_repository(repo_path_str: str, branch: str, base: str) -> Path:
    """Validates that the path is a valid Git repository and checks branch validity."""
    repo_path = Path(repo_path_str).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target repository path '{repo_path_str}' does not exist or is not a directory."
        )

    # Validate git repository
    res_git = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo_path),
        capture_output=True,
        text=True
    )
    if res_git.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path '{repo_path_str}' is not a valid Git repository."
        )

    # Check branch existence (local or origin)
    check_branch_local = subprocess.run(["git", "rev-parse", "--verify", branch], cwd=str(repo_path), capture_output=True)
    check_branch_origin = subprocess.run(["git", "rev-parse", "--verify", f"origin/{branch}"], cwd=str(repo_path), capture_output=True)
    if check_branch_local.returncode != 0 and check_branch_origin.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PR branch '{branch}' was not found in repository (neither locally nor on origin)."
        )

    # Check base branch existence (local or origin)
    check_base_local = subprocess.run(["git", "rev-parse", "--verify", base], cwd=str(repo_path), capture_output=True)
    check_base_origin = subprocess.run(["git", "rev-parse", "--verify", f"origin/{base}"], cwd=str(repo_path), capture_output=True)
    if check_base_local.returncode != 0 and check_base_origin.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base branch '{base}' was not found in repository (neither locally nor on origin)."
        )

    return repo_path


def verify_github_signature(raw_body: bytes, signature_header: Optional[str]) -> None:
    """
    Validates GitHub X-Hub-Signature-256 header using constant-time comparison.
    Raises HTTPException(401) on missing/invalid signature when secret is configured.
    """
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", GITHUB_WEBHOOK_SECRET)
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET is not configured. Skipping HMAC signature validation (Development Mode).")
        return

    if not signature_header:
        logger.warning("Webhook request missing X-Hub-Signature-256 header when secret is configured.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header"
        )

    if not signature_header.startswith("sha256="):
        logger.warning("Invalid X-Hub-Signature-256 format.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature format"
        )

    expected_sig = signature_header[7:].strip()
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    computed_sig = mac.hexdigest()

    if not hmac.compare_digest(computed_sig, expected_sig):
        logger.warning("Invalid webhook signature: computed HMAC does not match provided X-Hub-Signature-256.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )


def validate_repo_allowlist(repo_full_name: str) -> None:
    """
    Checks if repository is allowed via GITHUB_ALLOWED_REPOS.
    Raises HTTPException(403) if repository is not in allowlist.
    """
    allowlist_env = os.getenv("GITHUB_ALLOWED_REPOS", GITHUB_ALLOWED_REPOS)
    if not allowlist_env or not allowlist_env.strip():
        logger.warning("GITHUB_ALLOWED_REPOS is not set. All repositories allowed (Development Mode).")
        return

    allowed = [r.strip().lower() for r in allowlist_env.split(",") if r.strip()]
    if repo_full_name.strip().lower() not in allowed:
        logger.warning(f"Repository rejected: '{repo_full_name}' is not in GITHUB_ALLOWED_REPOS allowlist.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Repository '{repo_full_name}' is not authorized for review."
        )


async def execute_webhook_background_review(
    review_key: str,
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    base_ref: str,
    head_ref: str,
    clone_url: str
):
    """
    Background worker for executing PR review for a webhook event:
    1. Acquires INFERENCE_LOCK (GPU Concurrency Protection)
    2. Performs secure clone/fetch in isolated temporary directory
    3. Runs standard run_review(...) pipeline
    4. Updates IDEMPOTENCY_STORE status
    """
    logger.info(f"Review started for {review_key} (PR #{pr_number}, SHA: {head_sha[:8]})")
    temp_dir = tempfile.mkdtemp(prefix="pr_review_git_")
    temp_repo_path = Path(temp_dir).resolve()

    try:
        # Prepare authenticated or public clone URL
        token = os.getenv("GITHUB_TOKEN", GITHUB_TOKEN)
        authenticated_url = clone_url
        if token:
            authenticated_url = clone_url.replace("https://", f"https://x-access-token:{token}@")

        # Step 1: Initialize temporary git repo
        subprocess.run(["git", "init"], cwd=str(temp_repo_path), check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", authenticated_url], cwd=str(temp_repo_path), check=True, capture_output=True)

        # Step 2: Fetch base ref and PR head ref
        subprocess.run(
            ["git", "fetch", "--depth=50", "origin", f"+refs/heads/{base_ref}:refs/remotes/origin/{base_ref}"],
            cwd=str(temp_repo_path),
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "fetch", "--depth=50", "origin", f"+refs/pull/{pr_number}/head:refs/remotes/origin/{head_ref}"],
            cwd=str(temp_repo_path),
            check=True,
            capture_output=True
        )

        # Step 3: Run review within inference lock and threadpool
        async with INFERENCE_LOCK:
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(
                None,
                lambda: run_review(
                    repo=str(temp_repo_path),
                    branch=head_ref,
                    base=base_ref,
                    model_id=os.getenv("PR_REVIEW_MODEL", DEFAULT_MODEL),
                    backend=os.getenv("PR_REVIEW_BACKEND", DEFAULT_BACKEND),
                    quantization=os.getenv("PR_REVIEW_QUANTIZATION", DEFAULT_QUANTIZATION),
                    device=os.getenv("PR_REVIEW_DEVICE", DEFAULT_DEVICE),
                    api_base=os.getenv("PR_REVIEW_API_BASE", DEFAULT_API_BASE),
                    api_key=os.getenv("PR_REVIEW_API_KEY", DEFAULT_API_KEY),
                    pmd=False,
                    dry_run=False,
                    model_cache=MODEL_CACHE,
                    suggest_fixes=DEFAULT_FIX_AGENT_ENABLED
                )
            )

        # Step 4: Publish single summary comment to GitHub PR
        comment_publish_status = "skipped"
        comment_publish_error = None
        try:
            gh_client = GitHubClient(token=token)
            publish_res = gh_client.publish_review_summary(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                head_sha=head_sha,
                verified_findings=report.get("verified_findings", []),
                rejected_findings=report.get("rejected_findings", []),
                fix_suggestions=report.get("fix_suggestions", [])
            )
            comment_publish_status = publish_res.get("status", "unknown")
            logger.info(f"GitHub summary comment {comment_publish_status} for {review_key}")
        except Exception as ce:
            comment_publish_status = "failed"
            comment_publish_error = str(ce)
            logger.warning(f"Failed to publish GitHub comment for {review_key}: {ce}")

        # Step 5: Mark review completed in idempotency store
        summary = {
            "changed_files_count": report.get("changed_files_count", 0),
            "candidate_count": report.get("candidate_count", 0),
            "verified_findings_count": report.get("verified_findings_count", 0),
            "rejected_findings_count": report.get("rejected_findings_count", 0),
            "comment_publish_status": comment_publish_status,
            "comment_publish_error": comment_publish_error,
            "status": report.get("status", "COMPLETED")
        }
        IDEMPOTENCY_STORE.mark_completed(review_key, summary=summary)
        logger.info(f"Review completed successfully for {review_key}: {summary}")

    except Exception as e:
        err_msg = f"Review failed for {review_key}: {str(e)}"
        logger.error(err_msg, exc_info=False)
        IDEMPOTENCY_STORE.mark_failed(review_key, error_message=str(e))
    finally:
        # Safe cleanup of temporary clone directory
        shutil.rmtree(temp_repo_path, ignore_errors=True)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Returns service health, webhook status, GPU availability, and model loading status."""
    is_loaded = "model" in MODEL_CACHE and MODEL_CACHE["model"] is not None
    gpu_available = False
    gpu_device = None
    try:
        import torch
        if torch.cuda.is_available():
            gpu_available = True
            gpu_device = torch.cuda.get_device_name(0)
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        service="pr-review-agent",
        model=os.getenv("PR_REVIEW_MODEL", DEFAULT_MODEL),
        backend=os.getenv("PR_REVIEW_BACKEND", DEFAULT_BACKEND),
        quantization=os.getenv("PR_REVIEW_QUANTIZATION", DEFAULT_QUANTIZATION),
        model_loaded=is_loaded,
        webhook_enabled=True,
        gpu_available=gpu_available,
        gpu_device=gpu_device
    )


@app.post("/review", response_model=ReviewResponse, tags=["Review"])
async def review_pull_request(request: ReviewRequest):
    """
    Executes an end-to-end pull request review on a local Git repository and branch.
    Uses temporary worktree isolation and cached verifier model.
    """
    repo_path = validate_git_repository(request.repo, request.branch, request.base)
    effective_suggest_fixes = request.suggest_fixes if request.suggest_fixes is not None else DEFAULT_FIX_AGENT_ENABLED

    # Execute review with concurrency protection for model inference
    async with INFERENCE_LOCK:
        try:
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(
                None,
                lambda: run_review(
                    repo=str(repo_path),
                    branch=request.branch,
                    base=request.base,
                    model_id=os.getenv("PR_REVIEW_MODEL", DEFAULT_MODEL),
                    backend=os.getenv("PR_REVIEW_BACKEND", DEFAULT_BACKEND),
                    quantization=os.getenv("PR_REVIEW_QUANTIZATION", DEFAULT_QUANTIZATION),
                    device=os.getenv("PR_REVIEW_DEVICE", DEFAULT_DEVICE),
                    api_base=os.getenv("PR_REVIEW_API_BASE", DEFAULT_API_BASE),
                    api_key=os.getenv("PR_REVIEW_API_KEY", DEFAULT_API_KEY),
                    pmd=request.pmd,
                    dry_run=request.dry_run,
                    model_cache=MODEL_CACHE,
                    suggest_fixes=effective_suggest_fixes
                )
            )
            return report
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected review error: {str(e)}")


@app.post("/webhook/github", tags=["Webhook"])
async def handle_github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
):
    """
    Ingests GitHub Pull Request webhooks with HMAC SHA-256 authentication,
    repository allowlisting, idempotency check, and non-blocking background review.
    """
    logger.info("Webhook received from GitHub.")
    raw_body = await request.body()

    # 1. HMAC Signature Verification
    verify_github_signature(raw_body, x_hub_signature_256)

    # 2. Filter Event Type
    if x_github_event != "pull_request":
        logger.info(f"Ignored non-pull_request GitHub event: '{x_github_event}'")
        return {"status": "ignored", "reason": f"Unsupported event type: '{x_github_event}'"}

    # 3. Parse JSON Body
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.warning(f"Webhook payload JSON decode failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # 4. Validate Action
    action = payload.get("action")
    supported_actions = ("opened", "reopened", "synchronize")
    if action not in supported_actions:
        logger.info(f"Ignored unsupported pull_request action: '{action}'")
        return {"status": "ignored", "reason": f"Unsupported action: '{action}'"}

    # 5. Extract & Validate Required Payload Fields
    try:
        repo_data = payload["repository"]
        repo_full_name = repo_data["full_name"]
        clone_url = repo_data.get("clone_url") or f"https://github.com/{repo_full_name}.git"

        pr_data = payload["pull_request"]
        pr_number = pr_data["number"]
        head_sha = pr_data["head"]["sha"]
        base_ref = pr_data["base"]["ref"]
        head_ref = pr_data["head"]["ref"]
        html_url = pr_data.get("html_url", "")
    except (KeyError, TypeError) as e:
        logger.warning(f"Missing required webhook payload fields: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing required field: {e}")

    # 6. Check Repository Allowlist
    validate_repo_allowlist(repo_full_name)

    # 7. Idempotency Check
    should_proceed, review_key, current_status = IDEMPOTENCY_STORE.acquire_review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha
    )

    if not should_proceed:
        logger.info(f"Duplicate delivery/review ignored for {review_key} (current status: {current_status})")
        return {
            "status": "duplicate",
            "review_key": review_key,
            "current_status": current_status,
            "message": "Review is already processing or completed for this PR commit."
        }

    # 8. Trigger Non-blocking Background Review Execution
    asyncio.create_task(
        execute_webhook_background_review(
            review_key=review_key,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            head_sha=head_sha,
            base_ref=base_ref,
            head_ref=head_ref,
            clone_url=clone_url
        )
    )

    # 9. Immediate 202 Accepted Response
    return Response(
        content=json.dumps({
            "status": "accepted",
            "review_key": review_key,
            "action": action,
            "repository": repo_full_name,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "message": "Review scheduled for background execution."
        }),
        status_code=status.HTTP_202_ACCEPTED,
        media_type="application/json"
    )


@app.get("/webhook/status", response_model=WebhookStatusResponse, tags=["Webhook"])
@app.get("/webhook/reviews/{review_key:path}", response_model=WebhookStatusResponse, tags=["Webhook"])
async def get_webhook_review_status(review_key: Optional[str] = None):
    """Returns the review execution status and report summary for a given review key."""
    if not review_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="review_key parameter is required."
        )
    status_data = IDEMPOTENCY_STORE.get_status(review_key)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review key '{review_key}' not found."
        )
    return status_data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
