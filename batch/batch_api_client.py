#!/usr/bin/env python3
"""
Anthropic Batch API Client

Provides high-level interface for submitting and monitoring batch requests to Claude.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """A single request in a batch"""

    custom_id: str  # Unique ID for this request
    params: Dict[str, Any]  # Message parameters (messages, system, etc.)


@dataclass
class BatchResult:
    """Result from a completed batch"""

    custom_id: str
    result: Dict[str, Any]  # Either 'message' (success) or 'error'
    status: str  # "succeeded", "errored", "expired"


class BatchAPIError(Exception):
    """Base exception for batch API errors"""

    pass


class BatchSubmissionError(BatchAPIError):
    """Error submitting batch to API"""

    pass


class BatchTimeoutError(BatchAPIError):
    """Batch did not complete within timeout"""

    pass


class BatchResultError(BatchAPIError):
    """Error retrieving batch results"""

    pass


class BatchAPIClient:
    """Wrapper around Anthropic Batch API"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize batch API client"""
        if anthropic is None:
            raise ImportError("anthropic SDK not installed. Install with: pip install anthropic")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.batch_dir = Path.home() / ".cortex" / "batches"
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def submit_batch(
        self, requests: List[BatchRequest], description: str = "Cortex batch request"
    ) -> str:
        """
        Submit a batch of requests to Claude API.

        Args:
            requests: List of BatchRequest objects
            description: Human-readable description

        Returns:
            batch_id (str) for polling results later

        Raises:
            ValueError: If batch is empty or too large
            BatchSubmissionError: If submission fails
        """
        if not requests:
            raise ValueError("Batch must have at least 1 request")

        if len(requests) > 10000:
            raise ValueError("Batch cannot exceed 10,000 requests (API limit)")

        logger.info(f"Submitting batch with {len(requests)} requests")

        try:
            # Convert requests to format expected by Batch API
            batch_requests = []
            for req in requests:
                batch_request = {
                    "custom_id": req.custom_id,
                    "params": {
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 8192,
                        **req.params,  # Merge user params (messages, system, etc.)
                    },
                }
                batch_requests.append(batch_request)

            # Submit to API
            batch = self.client.beta.messages.batches.create(requests=batch_requests)

            batch_id = batch.id

            # Save metadata locally for tracking
            metadata = {
                "batch_id": batch_id,
                "created_at": datetime.now().isoformat(),
                "description": description,
                "request_count": len(requests),
                "status": batch.processing_status,
            }
            self._save_batch_metadata(batch_id, metadata)

            logger.info(f"Batch submitted: {batch_id} ({len(requests)} requests)")
            return batch_id

        except anthropic.APIError as e:
            logger.error(f"API error submitting batch: {e}")
            raise BatchSubmissionError(f"Failed to submit batch: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error submitting batch: {e}")
            raise BatchSubmissionError(f"Failed to submit batch: {e}") from e

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Get current status of a batch with enhanced monitoring.

        Returns:
            {
                "id": batch_id,
                "status": "processing|completed",
                "request_counts": {
                    "processing": int,
                    "succeeded": int,
                    "errored": int,
                    "expired": int
                },
                "progress_percentage": float,
                "estimated_completion": Optional[str],
                "error_rate": float
            }
        """
        try:
            batch = self.client.beta.messages.batches.retrieve(batch_id)
            counts = {
                "processing": batch.request_counts.processing,
                "succeeded": batch.request_counts.succeeded,
                "errored": batch.request_counts.errored,
                "expired": batch.request_counts.expired,
            }

            # Calculate progress metrics
            total = sum(counts.values())
            completed = counts["succeeded"] + counts["errored"] + counts["expired"]
            progress_pct = (completed / total * 100) if total > 0 else 0.0
            error_rate = (counts["errored"] / total * 100) if total > 0 else 0.0

            return {
                "id": batch.id,
                "status": batch.processing_status,
                "request_counts": counts,
                "progress_percentage": round(progress_pct, 2),
                "error_rate": round(error_rate, 2),
                "retrieved_at": datetime.now().isoformat(),
            }
        except anthropic.APIError as e:
            logger.error(f"Error getting batch status: {e}")
            raise BatchResultError(f"Failed to get batch status: {e}") from e

    def poll_results(
        self,
        batch_id: str,
        timeout_minutes: int = 1440,
        poll_interval_seconds: int = 5,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ) -> List[BatchResult]:
        """
        Poll for batch results until complete or timeout with enhanced retry logic.

        Args:
            batch_id: Batch ID from submit_batch
            timeout_minutes: Max wait time (default: 24 hours)
            poll_interval_seconds: How often to check status
            max_retries: Maximum retry attempts for transient errors (default: 3)
            retry_backoff: Exponential backoff multiplier (default: 2.0)

        Returns:
            List of BatchResult objects (one per request)

        Raises:
            BatchTimeoutError: If batch doesn't complete in time
            BatchResultError: If retries exhausted
        """
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        last_log_time = start_time
        log_interval = 60  # Log progress every 60 seconds
        retry_count = 0
        current_poll_interval = poll_interval_seconds

        while True:
            try:
                status = self.get_batch_status(batch_id)
                retry_count = 0  # Reset retry count on successful status check
                current_poll_interval = poll_interval_seconds  # Reset poll interval

                if status["status"] == "completed":
                    # Batch completed, retrieve results
                    logger.info(f"Batch {batch_id} completed")
                    results = self._retrieve_batch_results(batch_id)
                    return results

                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    raise BatchTimeoutError(
                        f"Batch {batch_id} did not complete within " f"{timeout_minutes} minutes"
                    )

                # Log progress periodically
                current_time = time.time()
                if current_time - last_log_time >= log_interval:
                    counts = status["request_counts"]
                    total = sum(counts.values())
                    completed = counts["succeeded"] + counts["errored"] + counts["expired"]
                    progress_pct = (completed / total * 100) if total > 0 else 0

                    logger.info(
                        f"Batch {batch_id} progress: {progress_pct:.1f}% "
                        f"({completed}/{total}) - "
                        f"Succeeded: {counts['succeeded']}, "
                        f"Errored: {counts['errored']}, "
                        f"Processing: {counts['processing']}"
                    )
                    last_log_time = current_time

                time.sleep(current_poll_interval)

            except BatchResultError as e:
                # Enhanced retry logic with exponential backoff
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Exhausted retries ({max_retries}) for batch {batch_id}: {e}")
                    raise BatchResultError(
                        f"Failed to poll batch {batch_id} after {max_retries} retries: {e}"
                    ) from e

                # Exponential backoff
                backoff_time = current_poll_interval * (retry_backoff ** (retry_count - 1))
                logger.warning(
                    f"Error polling batch {batch_id} (attempt {retry_count}/{max_retries}): {e}. "
                    f"Retrying in {backoff_time:.1f}s..."
                )
                time.sleep(backoff_time)
                current_poll_interval = backoff_time
                continue
            except Exception as e:
                # Handle unexpected errors
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Unexpected error polling batch {batch_id}: {e}")
                    raise BatchResultError(f"Unexpected error polling batch {batch_id}: {e}") from e
                backoff_time = current_poll_interval * (retry_backoff ** (retry_count - 1))
                logger.warning(
                    f"Unexpected error polling batch {batch_id} (attempt {retry_count}/{max_retries}): {e}. "
                    f"Retrying in {backoff_time:.1f}s..."
                )
                time.sleep(backoff_time)
                current_poll_interval = backoff_time
                continue

    def _retrieve_batch_results(self, batch_id: str) -> List[BatchResult]:
        """
        Retrieve completed batch results from API.

        Uses direct HTTP GET to the results_url (JSONL endpoint) instead of
        the SDK iterator, which hangs in anthropic SDK v0.75.0.

        Returns:
            List of BatchResult objects
        """
        results = []

        try:
            # Get the results URL from the batch object
            batch = self.client.beta.messages.batches.retrieve(batch_id)
            results_url = getattr(batch, "results_url", None)

            if not results_url:
                raise BatchResultError(f"No results_url for batch {batch_id}")

            # Direct HTTP fetch (SDK iterator hangs in v0.75.0)
            import httpx
            import os

            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            resp = httpx.get(
                results_url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "message-batches-2024-09-24",
                },
                timeout=30.0,
            )
            resp.raise_for_status()

            # Parse JSONL response (one JSON object per line)
            for line in resp.text.strip().split("\n"):
                if not line.strip():
                    continue
                data = json.loads(line)
                custom_id = data.get("custom_id", "unknown")
                result_data = data.get("result", {})
                status = result_data.get("type", "unknown")

                batch_result = BatchResult(
                    custom_id=custom_id,
                    result=result_data,
                    status=status,
                )
                results.append(batch_result)

            logger.info(f"Retrieved {len(results)} results from batch {batch_id}")
            return results

        except anthropic.APIError as e:
            logger.error(f"Error retrieving batch results: {e}")
            raise BatchResultError(f"Failed to retrieve batch results: {e}") from e
        except Exception as e:
            logger.error(f"Error retrieving batch results via HTTP: {e}")
            raise BatchResultError(f"Failed to retrieve batch results: {e}") from e

    def list_batches(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List recent batch jobs from the API.

        Note: The SDK paginator fetches ALL pages if unchecked.
        We break after collecting `limit` items to avoid paginating
        through thousands of historical batches.

        Args:
            limit: Maximum number of batches to retrieve

        Returns:
            List of batch status dicts
        """
        try:
            batches = []
            for batch in self.client.beta.messages.batches.list(limit=limit):
                batches.append(
                    {
                        "id": batch.id,
                        "status": batch.processing_status,
                        "created_at": batch.created_at,
                        "request_counts": {
                            "processing": batch.request_counts.processing,
                            "succeeded": batch.request_counts.succeeded,
                            "errored": batch.request_counts.errored,
                            "expired": batch.request_counts.expired,
                        },
                    }
                )
                if len(batches) >= limit:
                    break
            return batches
        except anthropic.APIError as e:
            logger.error(f"Error listing batches: {e}")
            return []

    def _save_batch_metadata(self, batch_id: str, metadata: Dict[str, Any]):
        """Save batch metadata locally for tracking and recovery"""
        metadata_file = self.batch_dir / f"{batch_id}_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        logger.debug(f"Saved batch metadata: {metadata_file}")

    def _load_batch_metadata(self, batch_id: str) -> Dict[str, Any]:
        """Load batch metadata"""
        metadata_file = self.batch_dir / f"{batch_id}_metadata.json"
        if metadata_file.exists():
            return json.loads(metadata_file.read_text())
        return {}
