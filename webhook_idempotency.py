"""
Thread-safe in-memory store for GitHub Webhook PR review idempotency.
Tracks status per review key: <repository_full_name>#<pr_number>@<head_sha>
"""

import threading
import time
from typing import Any, Dict, Optional, Tuple


class WebhookIdempotencyStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, Dict[str, Any]] = {}

    def get_review_key(self, repo_full_name: str, pr_number: int, head_sha: str) -> str:
        return f"{repo_full_name.strip()}#{pr_number}@{head_sha.strip()}"

    def get_status(self, review_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._records.get(review_key)
            if record:
                return dict(record)
            return None

    def acquire_review(
        self,
        repo_full_name: str,
        pr_number: int,
        head_sha: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Attempts to acquire execution right for a review_key.
        Returns (should_proceed, review_key, current_status):
        - If not seen before -> sets status="processing", returns (True, key, "new")
        - If status is "failed" -> updates status="processing", returns (True, key, "retry")
        - If status is "processing" or "completed" -> returns (False, key, current_status)
        """
        review_key = self.get_review_key(repo_full_name, pr_number, head_sha)
        with self._lock:
            record = self._records.get(review_key)
            now = time.time()

            if record is None:
                self._records[review_key] = {
                    "review_key": review_key,
                    "repository": repo_full_name,
                    "pr_number": pr_number,
                    "head_sha": head_sha,
                    "status": "processing",
                    "created_at": now,
                    "updated_at": now,
                    "error": None,
                    "summary": None
                }
                return True, review_key, "new"

            current_status = record.get("status")
            if current_status in ("processing", "completed"):
                return False, review_key, current_status

            if current_status == "failed":
                record["status"] = "processing"
                record["updated_at"] = now
                record["error"] = None
                return True, review_key, "retry"

            # Default fallback for any unknown status
            record["status"] = "processing"
            record["updated_at"] = now
            return True, review_key, "retry"

    def mark_completed(self, review_key: str, summary: Optional[Dict[str, Any]] = None):
        with self._lock:
            if review_key in self._records:
                self._records[review_key]["status"] = "completed"
                self._records[review_key]["updated_at"] = time.time()
                self._records[review_key]["summary"] = summary

    def mark_failed(self, review_key: str, error_message: str):
        with self._lock:
            if review_key in self._records:
                self._records[review_key]["status"] = "failed"
                self._records[review_key]["updated_at"] = time.time()
                self._records[review_key]["error"] = error_message

    def clear(self):
        with self._lock:
            self._records.clear()
