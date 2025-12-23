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
            raise ImportError(
                "anthropic SDK not installed. Install with: pip install anthropic"
            )

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
                        "model": "claude-opus-4-5-20251101",
                        "max_tokens": 2048,
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
        Get current status of a batch.

        Returns:
            {
                "id": batch_id,
                "status": "processing|completed",
                "request_counts": {
                    "processing": int,
                    "succeeded": int,
                    "errored": int,
                    "expired": int
                }
            }
        """
        try:
            batch = self.client.beta.messages.batches.retrieve(batch_id)
            return {
                "id": batch.id,
                "status": batch.processing_status,
                "request_counts": {
                    "processing": batch.request_counts.processing,
                    "succeeded": batch.request_counts.succeeded,
                    "errored": batch.request_counts.errored,
                    "expired": batch.request_counts.expired,
                },
            }
        except anthropic.APIError as e:
            logger.error(f"Error getting batch status: {e}")
            raise BatchResultError(f"Failed to get batch status: {e}") from e

    def poll_results(
        self, batch_id: str, timeout_minutes: int = 1440, poll_interval_seconds: int = 5
    ) -> List[BatchResult]:
        """
        Poll for batch results until complete or timeout.

        Args:
            batch_id: Batch ID from submit_batch
            timeout_minutes: Max wait time (default: 24 hours)
            poll_interval_seconds: How often to check status

        Returns:
            List of BatchResult objects (one per request)

        Raises:
            TimeoutError: If batch doesn't complete in time
        """
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        while True:
            status = self.get_batch_status(batch_id)

            if status["status"] == "completed":
                # Batch completed, retrieve results
                logger.info(f"Batch {batch_id} completed")
                results = self._retrieve_batch_results(batch_id)
                return results

            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise BatchTimeoutError(
                    f"Batch {batch_id} did not complete within "
                    f"{timeout_minutes} minutes"
                )

            # Log progress
            counts = status["request_counts"]
            logger.debug(
                f"Batch {batch_id}: "
                f"Processing: {counts['processing']}, "
                f"Succeeded: {counts['succeeded']}, "
                f"Errored: {counts['errored']}"
            )

            time.sleep(poll_interval_seconds)

    def _retrieve_batch_results(self, batch_id: str) -> List[BatchResult]:
        """
        Retrieve completed batch results from API.

        Returns:
            List of BatchResult objects
        """
        results = []

        try:
            for result in self.client.beta.messages.batches.results(batch_id):
                # Get status from result.result.type
                status = result.result.type if hasattr(result.result, 'type') else 'unknown'

                batch_result = BatchResult(
                    custom_id=result.custom_id,
                    result=result.result,
                    status=status,  # "succeeded", "errored", etc.
                )
                results.append(batch_result)

            logger.info(f"Retrieved {len(results)} results from batch {batch_id}")
            return results

        except anthropic.APIError as e:
            logger.error(f"Error retrieving batch results: {e}")
            raise BatchResultError(f"Failed to retrieve batch results: {e}") from e

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
