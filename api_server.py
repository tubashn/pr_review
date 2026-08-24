"""
FastAPI Server for AI Pull Request Review Agent
Exposes REST endpoints for PR code review orchestration with:
- Model caching (Lazy loading & singleton in-memory reuse)
- Concurrency Lock (GPU collision avoidance)
- Strict Git repository validation & error handling
- Environment-based configuration
- Full OpenAPI / Swagger documentation
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from run_pr_review import run_review

# Environment Configuration Defaults
DEFAULT_MODEL = os.getenv("PR_REVIEW_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
DEFAULT_BACKEND = os.getenv("PR_REVIEW_BACKEND", "transformers")
DEFAULT_QUANTIZATION = os.getenv("PR_REVIEW_QUANTIZATION", "4bit")
DEFAULT_DEVICE = os.getenv("PR_REVIEW_DEVICE", "auto")
DEFAULT_API_BASE = os.getenv("PR_REVIEW_API_BASE", None)
DEFAULT_API_KEY = os.getenv("PR_REVIEW_API_KEY", None)

app = FastAPI(
    title="PR Review Agent API",
    description="End-to-End AI Pull Request Review Service using static analysis, AST verification, and LLM reasoning.",
    version="1.0.0"
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Model Cache & GPU Concurrency Lock
MODEL_CACHE: Dict[str, Any] = {}
INFERENCE_LOCK = asyncio.Lock()


# Pydantic Request & Response Models
class HealthResponse(BaseModel):
    status: str = Field("ok", description="Service health status")
    service: str = Field("pr-review-agent", description="Service identifier")
    model: str = Field(..., description="Configured LLM verifier model")
    backend: str = Field(..., description="Inference backend engine")
    quantization: str = Field(..., description="Model quantization mode")
    model_loaded: bool = Field(..., description="Whether model is currently loaded in memory")


class ReviewRequest(BaseModel):
    repo: str = Field(..., description="Absolute or relative path to target Git repository")
    branch: str = Field(..., description="Pull Request branch to review")
    base: str = Field("main", description="Base branch to compare against (default: main)")
    pmd: bool = Field(False, description="Enable Maven PMD static analysis if available")
    dry_run: bool = Field(False, description="Run in mock/dry-run mode without GPU model inference")


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
    status: Optional[str] = None


def validate_git_repository(repo_path_str: str, branch: str, base: str) -> Path:
    """Validates that the path is a valid Git repository and check branch validity."""
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


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Returns service health and model loading status."""
    is_loaded = "model" in MODEL_CACHE and MODEL_CACHE["model"] is not None
    return HealthResponse(
        status="ok",
        service="pr-review-agent",
        model=DEFAULT_MODEL,
        backend=DEFAULT_BACKEND,
        quantization=DEFAULT_QUANTIZATION,
        model_loaded=is_loaded
    )


@app.post("/review", response_model=ReviewResponse, tags=["Review"])
async def review_pull_request(request: ReviewRequest):
    """
    Executes an end-to-end pull request review on the target Git repository and branch.
    Uses temporary worktree isolation and cached verifier model.
    """
    repo_path = validate_git_repository(request.repo, request.branch, request.base)

    # Execute review with concurrency protection for model inference
    async with INFERENCE_LOCK:
        try:
            # Run orchestration in threadpool to prevent blocking the event loop
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(
                None,
                lambda: run_review(
                    repo=str(repo_path),
                    branch=request.branch,
                    base=request.base,
                    model_id=DEFAULT_MODEL,
                    backend=DEFAULT_BACKEND,
                    quantization=DEFAULT_QUANTIZATION,
                    device=DEFAULT_DEVICE,
                    api_base=DEFAULT_API_BASE,
                    api_key=DEFAULT_API_KEY,
                    pmd=request.pmd,
                    dry_run=request.dry_run,
                    model_cache=MODEL_CACHE
                )
            )
            return report
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected review error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
