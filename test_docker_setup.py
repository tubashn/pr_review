"""
Validation and Configuration Audit Tests for Docker Containerization
Tests:
1. Dockerfile existence and configuration sanity:
   - Uses CUDA runtime base image
   - Runs as non-root user
   - Does NOT download model weights during build
   - Does NOT contain hardcoded secrets or tokens
   - Specifies single-worker Uvicorn command
   - Exposes port 8000 and defines HEALTHCHECK
2. docker-compose.yml existence and configuration sanity:
   - Defines pr-review-agent service on port 8000
   - Configures persistent Hugging Face cache volume
   - Configures NVIDIA GPU reservations
   - Passes environment variables dynamically without hardcoded secrets
3. .dockerignore sanity:
   - Excludes .git, .env, models, checkpoints, __pycache__, and temporary logs
4. .env.example exists and contains only placeholders
5. .gitignore excludes .env
6. requirements-runtime.txt specifies transformers==4.54.1
"""

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


class TestDockerConfiguration(unittest.TestCase):

    def test_dockerfile_sanity(self):
        dockerfile_path = REPO_ROOT / "Dockerfile"
        self.assertTrue(dockerfile_path.exists(), "Dockerfile must exist in repo root")

        content = dockerfile_path.read_text(encoding="utf-8")

        # Check CUDA base image
        self.assertIn("nvidia/cuda", content)

        # Check non-root user
        self.assertIn("USER appuser", content)

        # Check port 8000
        self.assertIn("EXPOSE 8000", content)

        # Check healthcheck
        self.assertIn("HEALTHCHECK", content)
        self.assertIn("/health", content)

        # Check single worker constraint
        self.assertIn('"1"', content)
        self.assertIn("--workers", content)

        # Ensure no model download or secrets embedded
        self.assertNotIn("huggingface-cli download", content)
        self.assertNotIn("git clone https://huggingface.co", content)
        self.assertNotIn("ghp_", content)
        self.assertNotIn("github_pat_", content)

    def test_docker_compose_sanity(self):
        compose_path = REPO_ROOT / "docker-compose.yml"
        self.assertTrue(compose_path.exists(), "docker-compose.yml must exist in repo root")

        content = compose_path.read_text(encoding="utf-8")

        # Check service name and port mapping
        self.assertIn("pr-review-agent", content)
        self.assertIn("8000:8000", content)

        # Check GPU configuration
        self.assertIn("driver: nvidia", content)
        self.assertIn("capabilities: [gpu]", content)

        # Check persistent volume for HF cache
        self.assertIn("hf_model_cache", content)
        self.assertIn("/home/appuser/.cache/huggingface", content)

        # Check external environment variable mapping
        self.assertIn("PR_REVIEW_MODEL", content)
        self.assertIn("GITHUB_TOKEN", content)
        self.assertIn("GITHUB_WEBHOOK_SECRET", content)
        self.assertNotIn("ghp_", content)

    def test_dockerignore_sanity(self):
        dockerignore_path = REPO_ROOT / ".dockerignore"
        self.assertTrue(dockerignore_path.exists(), ".dockerignore must exist in repo root")

        content = dockerignore_path.read_text(encoding="utf-8")

        # Check critical exclusions
        self.assertIn(".git", content)
        self.assertIn(".env", content)
        self.assertIn("__pycache__", content)
        self.assertIn("models/", content)
        self.assertIn("checkpoints/", content)

    def test_env_example_and_gitignore(self):
        env_example_path = REPO_ROOT / ".env.example"
        self.assertTrue(env_example_path.exists(), ".env.example must exist in repo root")

        content = env_example_path.read_text(encoding="utf-8")
        self.assertIn("GITHUB_TOKEN=your_github_personal_access_token_here", content)
        self.assertIn("GITHUB_WEBHOOK_SECRET=your_webhook_hmac_secret_here", content)

        # Ensure .env is ignored in .gitignore
        gitignore_path = REPO_ROOT / ".gitignore"
        self.assertTrue(gitignore_path.exists())
        gi_content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn(".env", gi_content)

    def test_requirements_runtime_versions(self):
        req_path = REPO_ROOT / "requirements-runtime.txt"
        self.assertTrue(req_path.exists())

        content = req_path.read_text(encoding="utf-8")
        self.assertIn("transformers==4.54.1", content)
        self.assertIn("fastapi", content)
        self.assertIn("uvicorn", content)
        self.assertIn("accelerate", content)
        self.assertIn("bitsandbytes", content)


if __name__ == "__main__":
    unittest.main()
