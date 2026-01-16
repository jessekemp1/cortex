"""Anthropic Batch Client Wrapper.

Handles interaction with the Anthropic Message Batches API,
with support for simulation mode for testing.
"""

import os
import time
from typing import Any, Dict, List, Optional

import structlog

# Try to import anthropic
try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = structlog.get_logger()


class AnthropicBatchClient:
    """Wrapper for Anthropic Batch API.

    Handles 'Night Shift' batch submissions with automatic
    fallback to simulation mode when API is unavailable.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the batch client.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        if os.getenv("FORCE_SIMULATION"):
            logger.info("anthropic_client_force_simulation")
            self.client = None
            return

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None

        if self.api_key and ANTHROPIC_AVAILABLE:
            self.client = Anthropic(api_key=self.api_key)
            logger.info("anthropic_client_initialized")
        else:
            logger.warning(
                "anthropic_client_simulation_mode",
                reason="Missing API key or library",
            )

    def create_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a Message Batch from a list of items.

        Args:
            items: List of dicts with 'custom_id' and 'prompt' keys

        Returns:
            Dict with batch_id, status, and simulation flag
        """
        if not self.client:
            return self._simulate_create_batch(items)

        try:
            requests = []
            for item in items:
                requests.append(
                    {
                        "custom_id": item["custom_id"],
                        "params": {
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 1024,
                            "messages": [{"role": "user", "content": item["prompt"]}],
                        },
                    }
                )

            batch = self.client.messages.batches.create(requests=requests)

            logger.info("batch_created_real", batch_id=batch.id)
            return {"batch_id": batch.id, "status": "in_progress", "simulation": False}

        except Exception as e:
            logger.error("batch_creation_failed", error=str(e))
            raise

    def get_batch(self, batch_id: str) -> Dict[str, Any]:
        """Retrieve batch status.

        Args:
            batch_id: The batch ID to query

        Returns:
            Dict with batch status information
        """
        if not self.client or batch_id.startswith("msgbatch_sim_"):
            return self._simulate_get_batch(batch_id)

        try:
            batch = self.client.messages.batches.retrieve(batch_id)
            return {
                "batch_id": batch.id,
                "status": batch.processing_status,
                "request_counts": {
                    "processing": batch.request_counts.processing,
                    "succeeded": batch.request_counts.succeeded,
                    "errored": batch.request_counts.errored,
                },
                "results_url": (batch.results_url if hasattr(batch, "results_url") else None),
                "error": None,
            }
        except Exception as e:
            logger.error("batch_retrieve_failed", batch_id=batch_id, error=str(e))
            raise

    def get_results(self, batch_id: str) -> List[Dict[str, Any]]:
        """Download and parse results for a batch.

        Args:
            batch_id: The batch ID to get results for

        Returns:
            List of result dicts with custom_id, result_text, and status
        """
        if not self.client or batch_id.startswith("msgbatch_sim_"):
            return self._simulate_get_results(batch_id)

        try:
            results = []
            for result in self.client.messages.batches.results(batch_id):
                custom_id = result.custom_id
                content_text = ""
                if result.result.type == "succeeded":
                    for block in result.result.message.content:
                        if block.type == "text":
                            content_text += block.text

                results.append(
                    {
                        "custom_id": custom_id,
                        "result_text": content_text,
                        "status": "succeeded",
                    }
                )

            return results

        except Exception as e:
            logger.error("batch_results_download_failed", batch_id=batch_id, error=str(e))
            raise

    # --- Simulation Methods ---

    def _simulate_create_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate batch creation for testing."""
        batch_id = f"msgbatch_sim_{int(time.time())}"
        logger.info("batch_created_simulated", batch_id=batch_id, count=len(items))
        return {"batch_id": batch_id, "status": "in_progress", "simulation": True}

    def _simulate_get_batch(self, batch_id: str) -> Dict[str, Any]:
        """Simulate batch status retrieval."""
        return {"batch_id": batch_id, "status": "ended", "simulation": True}

    def _simulate_get_results(self, batch_id: str) -> List[Dict[str, Any]]:
        """Simulate batch results retrieval."""
        # Return empty list - caller handles mapping
        return []
