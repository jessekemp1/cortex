"""Batch Processing Manager for Claude Message Batches.

Manages the lifecycle of Claude Batches including queue management,
submission, and status tracking.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from anthropic import Anthropic

from cortex.runtime.config import get_config

logger = structlog.get_logger()


class BatchManager:
    """Manages the lifecycle of Claude Batches."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize batch manager.

        Args:
            db_path: Path to SQLite database. If None, uses config default.
        """
        if db_path is None:
            config = get_config()
            db_path = str(config.batch_queue_db)

        self.db_path = db_path
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema for batches."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Batch Queue Table (Pending Items)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                callback_agent_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'pending',
                batch_id TEXT
            )
        """
        )

        # Batch Tracking Table (Submitted Batches)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                result_file_id TEXT
            )
        """
        )

        conn.commit()
        conn.close()
        logger.debug("batch_system_db_initialized", db_path=self.db_path)

    def enqueue(self, prompt: str, callback_agent_id: str) -> int:
        """Add an item to the batch queue.

        Args:
            prompt: The prompt to process
            callback_agent_id: Agent ID to receive results

        Returns:
            The queue item ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO batch_queue (prompt, callback_agent_id, status)
            VALUES (?, ?, 'pending')
        """,
            (prompt, callback_agent_id),
        )

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info("batch_item_enqueued", item_id=item_id, callback=callback_agent_id)
        return item_id

    def get_pending_items(self, limit: int = 100) -> List[Dict]:
        """Get pending items from queue.

        Args:
            limit: Maximum items to return

        Returns:
            List of pending queue items
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM batch_queue
            WHERE status = 'pending'
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def mark_items_processing(self, item_ids: List[int], batch_id: str):
        """Mark items as processing/batched and link to batch_id.

        Args:
            item_ids: List of item IDs to update
            batch_id: The batch ID to link to
        """
        if not item_ids:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        placeholders = ",".join(["?"] * len(item_ids))
        cursor.execute(
            f"""
            UPDATE batch_queue
            SET status = 'batched', batch_id = ?
            WHERE id IN ({placeholders})
        """,
            (batch_id, *item_ids),
        )

        conn.commit()
        conn.close()

    def track_batch(self, batch_id: str, status: str = "in_progress"):
        """Track a submitted batch.

        Args:
            batch_id: The Anthropic batch ID
            status: Initial status (default: in_progress)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO batch_tracking (batch_id, status)
            VALUES (?, ?)
        """,
            (batch_id, status),
        )

        conn.commit()
        conn.close()
        logger.info("batch_tracked", batch_id=batch_id)

    def get_active_batches(self) -> List[Dict]:
        """Get batches that are still in progress.

        Returns:
            List of active batch records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM batch_tracking
            WHERE status = 'in_progress'
        """
        )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_batch_status(self, batch_id: str, status: str, result_file_id: Optional[str] = None):
        """Update status of a batch.

        Args:
            batch_id: The batch ID to update
            status: New status
            result_file_id: Optional result file ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if result_file_id:
            cursor.execute(
                """
                UPDATE batch_tracking
                SET status = ?, result_file_id = ?
                WHERE batch_id = ?
            """,
                (status, result_file_id, batch_id),
            )
        else:
            cursor.execute(
                """
                UPDATE batch_tracking
                SET status = ?
                WHERE batch_id = ?
            """,
                (status, batch_id),
            )

        conn.commit()
        conn.close()
        logger.info("batch_status_updated", batch_id=batch_id, status=status)

    def get_callbacks_for_batch(self, batch_id: str) -> List[Dict]:
        """Get original items and callbacks for a batch.

        Args:
            batch_id: The batch ID to query

        Returns:
            List of queue items for the batch
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM batch_queue
            WHERE batch_id = ?
        """,
            (batch_id,),
        )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def submit_pending_batch(
        self,
        max_items: int = 1000,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 8000,
        dry_run: bool = False,
    ) -> List[str]:
        """Submit pending items to Claude Batch API, intelligently optimizing batches.

        Args:
            max_items: Maximum items to consider
            model: Claude model to use
            max_tokens: Max output tokens per request
            dry_run: If True, do not submit, just return batch plan

        Returns:
            List of batch_ids (or plan details in dry_run)
        """
        # 1. Get pending items
        pending = self.get_pending_items(limit=max_items)

        if not pending:
            logger.info("no_pending_items_to_submit")
            return []

        # 2. Optimize batches using the Intelligence Module
        try:
            from cortex.batch.optimization import BatchOptimizer

            # Using 10,000 items and 200,000 tokens as reasonably safe defaults
            optimizer = BatchOptimizer()
            optimized_batches = optimizer.optimize(
                pending,
                max_batch_size=9000,  # Safety buffer under 10k
                token_budget=180000,  # Safety buffer under 200k rate limits
            )

        except ImportError:
            logger.warning("optimization_module_not_found_falling_back_to_naive")
            optimized_batches = [pending]  # Fallback: Submit all as one batch

        submitted_batch_ids = []
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not dry_run and not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        client = Anthropic(api_key=api_key) if not dry_run else None

        # 3. Submit each optimized batch
        for i, batch_items in enumerate(optimized_batches):
            requests = []
            for item in batch_items:
                requests.append(
                    {
                        "custom_id": str(f"item-{item['id']}"),
                        "params": {
                            "model": model,
                            "max_tokens": max_tokens,
                            "messages": [{"role": "user", "content": item["prompt"]}],
                        },
                    }
                )

            if dry_run:
                logger.info("dry_run_batch_plan", batch_index=i, items=len(requests))
                submitted_batch_ids.append(f"dry_run_batch_{i}")
                continue

            try:
                logger.info("submitting_batch_chunk", batch_index=i, num_items=len(requests))

                batch_response = client.messages.batches.create(requests=requests)

                batch_id = batch_response.id
                logger.info(
                    "batch_submitted_successfully",
                    batch_id=batch_id,
                    num_items=len(requests),
                    status=batch_response.processing_status,
                )

                # 4. Update database
                item_ids = [item["id"] for item in batch_items]
                self.mark_items_processing(item_ids, batch_id)
                self.track_batch(batch_id, status="in_progress")

                submitted_batch_ids.append(batch_id)

            except Exception as e:
                logger.error("batch_submission_failed", error=str(e), num_items=len(requests))
                raise

        return submitted_batch_ids
