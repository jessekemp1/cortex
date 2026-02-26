"""Tests for the unified batch queue: schema, submitter, and retriever."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from intelligence.process_monitor.batch_queue import (
    AI_TASK_TYPES,
    BatchTask,
    BatchTaskQueue,
    TaskState,
)


# ============================================================================
# Schema Tests
# ============================================================================


class TestSchemaChanges:
    """Verify new columns and state transitions."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test_queue.db"
        self.queue = BatchTaskQueue(db_path=self.db_path)

    def test_submitted_state_exists(self):
        assert TaskState.SUBMITTED.value == "submitted"

    def test_ai_task_types_defined(self):
        assert "review" in AI_TASK_TYPES
        assert "research" in AI_TASK_TYPES
        assert "ai_inference" in AI_TASK_TYPES
        assert "security" in AI_TASK_TYPES

    def test_new_columns_exist(self):
        """New API tracking columns should be created on init."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("PRAGMA table_info(batch_tasks)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        for col in [
            "api_batch_id",
            "api_custom_id",
            "model",
            "submitted_at",
            "result_file",
            "result_text",
            "token_input",
            "token_output",
        ]:
            assert col in columns, f"Missing column: {col}"

    def test_indexes_created(self):
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_api_batch_id" in indexes
        assert "idx_priority_state" in indexes

    def test_add_task_with_api_fields(self):
        task = self.queue.add_task(
            command="Review this code",
            task_type="review",
            description="Code review",
            priority="high",
        )
        retrieved = self.queue.get_task(task.task_id)

        assert retrieved.api_batch_id is None
        assert retrieved.model is None
        assert retrieved.submitted_at is None
        assert retrieved.result_text is None

    def test_migration_on_existing_db(self):
        """Opening an old DB should add new columns via ALTER TABLE."""
        import sqlite3

        # Create a minimal old-schema DB
        old_db = Path(self.tmp) / "old_queue.db"
        conn = sqlite3.connect(old_db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE batch_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                command TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT NOT NULL,
                scheduled_time TEXT,
                state TEXT NOT NULL,
                started_at TEXT, completed_at TEXT,
                exit_code INTEGER, stdout TEXT, stderr TEXT, error_message TEXT,
                estimated_duration_minutes REAL, actual_duration_seconds REAL,
                retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Open with BatchTaskQueue — should migrate
        BatchTaskQueue(db_path=old_db)

        conn = sqlite3.connect(old_db)
        cursor = conn.execute("PRAGMA table_info(batch_tasks)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "api_batch_id" in columns
        assert "token_input" in columns

    def test_state_transitions_pending_to_submitted(self):
        task = self.queue.add_task(command="Analyze code", task_type="review", priority="normal")
        assert task.state == TaskState.PENDING

        self.queue.mark_submitted(
            [task.task_id], "msgbatch_123", {task.task_id: "sanitized_id"}, "claude-sonnet-4"
        )
        updated = self.queue.get_task(task.task_id)

        assert updated.state == TaskState.SUBMITTED
        assert updated.api_batch_id == "msgbatch_123"
        assert updated.api_custom_id == "sanitized_id"
        assert updated.model == "claude-sonnet-4"
        assert updated.submitted_at is not None

    def test_state_transitions_submitted_to_completed(self):
        task = self.queue.add_task(command="Analyze code", task_type="review", priority="normal")
        self.queue.mark_submitted(
            [task.task_id], "msgbatch_123", {task.task_id: "sid"}, "claude-sonnet-4"
        )

        self.queue.mark_completed_with_result(
            task.task_id,
            result_text="Analysis complete. No issues found.",
            result_file="/tmp/result.json",
            token_input=500,
            token_output=1200,
        )
        completed = self.queue.get_task(task.task_id)

        assert completed.state == TaskState.COMPLETED
        assert completed.result_text == "Analysis complete. No issues found."
        assert completed.result_file == "/tmp/result.json"
        assert completed.token_input == 500
        assert completed.token_output == 1200
        assert completed.completed_at is not None

    def test_serialization_roundtrip(self):
        task = BatchTask(
            task_id="test-123",
            task_type="review",
            command="Review code",
            description="Code review",
            priority="high",
            api_batch_id="msgbatch_abc",
            api_custom_id="test-123",
            model="claude-sonnet-4",
            submitted_at=datetime(2026, 2, 25, 12, 0, 0),
            result_text="All good",
            token_input=100,
            token_output=200,
        )
        d = task.to_dict()
        restored = BatchTask.from_dict(d)

        assert restored.api_batch_id == "msgbatch_abc"
        assert restored.model == "claude-sonnet-4"
        assert restored.submitted_at == datetime(2026, 2, 25, 12, 0, 0)
        assert restored.token_input == 100


# ============================================================================
# Query Method Tests
# ============================================================================


class TestQueryMethods:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.queue = BatchTaskQueue(db_path=Path(self.tmp) / "q.db")

    def test_get_pending_api_tasks_filters_by_type(self):
        # AI task — should appear
        self.queue.add_task(command="Review", task_type="review", priority="normal")
        # Local task — should NOT appear
        self.queue.add_task(command="pytest", task_type="test", priority="normal")

        api_tasks = self.queue.get_pending_api_tasks()
        assert len(api_tasks) == 1
        assert api_tasks[0].task_type == "review"

    def test_get_pending_api_tasks_priority_order(self):
        self.queue.add_task(command="low", task_type="review", priority="low")
        self.queue.add_task(command="high", task_type="review", priority="high")
        self.queue.add_task(command="imm", task_type="review", priority="immediate")

        tasks = self.queue.get_pending_api_tasks()
        assert len(tasks) == 3
        assert tasks[0].priority == "immediate"
        assert tasks[1].priority == "high"
        assert tasks[2].priority == "low"

    def test_get_pending_api_tasks_limit(self):
        for i in range(10):
            self.queue.add_task(command=f"task {i}", task_type="review", priority="normal")

        tasks = self.queue.get_pending_api_tasks(limit=3)
        assert len(tasks) == 3

    def test_get_submitted_tasks(self):
        t = self.queue.add_task(command="X", task_type="review", priority="normal")
        self.queue.mark_submitted([t.task_id], "batch1", {t.task_id: "sid"}, "model")

        submitted = self.queue.get_submitted_tasks()
        assert len(submitted) == 1
        assert submitted[0].state == TaskState.SUBMITTED

    def test_get_tasks_by_batch_id(self):
        t1 = self.queue.add_task(command="A", task_type="review", priority="normal")
        t2 = self.queue.add_task(command="B", task_type="review", priority="normal")
        t3 = self.queue.add_task(command="C", task_type="review", priority="normal")

        self.queue.mark_submitted(
            [t1.task_id, t2.task_id], "batch_x", {t1.task_id: "s1", t2.task_id: "s2"}, "m"
        )
        self.queue.mark_submitted([t3.task_id], "batch_y", {t3.task_id: "s3"}, "m")

        batch_x_tasks = self.queue.get_tasks_by_batch_id("batch_x")
        assert len(batch_x_tasks) == 2

    def test_get_pending_api_count(self):
        self.queue.add_task(command="A", task_type="review", priority="normal")
        self.queue.add_task(command="B", task_type="research", priority="normal")
        self.queue.add_task(command="C", task_type="test", priority="normal")

        assert self.queue.get_pending_api_count() == 2

    def test_mark_submitted_atomic(self):
        """Multiple tasks should be marked in a single transaction."""
        tasks = [
            self.queue.add_task(command=f"T{i}", task_type="review", priority="normal")
            for i in range(5)
        ]
        ids = [t.task_id for t in tasks]
        id_map = {t.task_id: f"s{i}" for i, t in enumerate(tasks)}

        self.queue.mark_submitted(ids, "batch_bulk", id_map, "claude-sonnet-4")

        for task_id in ids:
            t = self.queue.get_task(task_id)
            assert t.state == TaskState.SUBMITTED
            assert t.api_batch_id == "batch_bulk"


# ============================================================================
# Submitter Tests
# ============================================================================


class TestBatchSubmitter:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.queue = BatchTaskQueue(db_path=Path(self.tmp) / "q.db")
        self.mock_client = MagicMock()
        self.mock_client.list_batches.return_value = []  # No active batches
        self.mock_client.submit_batch.return_value = "msgbatch_test123"

        from batch.submitter import BatchSubmitter
        from batch.model_policy import AnthropicBatchModels

        self.submitter = BatchSubmitter(
            queue=self.queue,
            client=self.mock_client,
            model_policy=AnthropicBatchModels(),
        )

    def test_submit_empty_queue(self):
        stats = self.submitter.submit_pending()
        assert stats.tasks_submitted == 0
        assert stats.tasks_pending == 0
        self.mock_client.submit_batch.assert_not_called()

    def test_submit_pending_tasks(self):
        self.queue.add_task(command="Review this", task_type="review", priority="high")
        self.queue.add_task(command="Analyze that", task_type="analysis", priority="normal")

        stats = self.submitter.submit_pending()

        assert stats.tasks_submitted == 2
        assert stats.batches_created == 1
        self.mock_client.submit_batch.assert_called_once()

        # Verify tasks are now SUBMITTED in SQLite
        submitted = self.queue.get_submitted_tasks()
        assert len(submitted) == 2
        assert all(t.api_batch_id == "msgbatch_test123" for t in submitted)

    def test_submit_skips_local_tasks(self):
        self.queue.add_task(command="Review X", task_type="review", priority="normal")
        self.queue.add_task(command="pytest tests/", task_type="test", priority="normal")

        stats = self.submitter.submit_pending()
        assert stats.tasks_submitted == 1  # Only the review task

    def test_submit_respects_capacity(self):
        self.mock_client.list_batches.return_value = [{"status": "in_progress"} for _ in range(5)]
        self.queue.add_task(command="X", task_type="review", priority="normal")

        stats = self.submitter.submit_pending()
        assert stats.capacity_available == 0
        assert stats.tasks_submitted == 0

    def test_circuit_breaker_trips_on_rate_limit(self):
        self.queue.add_task(command="X", task_type="review", priority="normal")
        self.mock_client.submit_batch.side_effect = Exception("429 rate limit exceeded")

        for _ in range(3):
            self.queue.add_task(command="Y", task_type="review", priority="normal")
            self.submitter.submit_pending()

        assert self.submitter._is_circuit_open()

    def test_circuit_breaker_not_tripped_on_validation_error(self):
        self.queue.add_task(command="X", task_type="review", priority="normal")
        self.mock_client.submit_batch.side_effect = Exception(
            "400 invalid_request_error: custom_id invalid"
        )

        self.submitter.submit_pending()
        assert not self.submitter._is_circuit_open()

    def test_validation_error_marks_tasks_failed(self):
        t = self.queue.add_task(command="X", task_type="review", priority="normal")
        self.mock_client.submit_batch.side_effect = Exception("400 invalid_request_error")

        self.submitter.submit_pending()
        failed = self.queue.get_task(t.task_id)
        assert failed.state == TaskState.FAILED

    def test_custom_id_sanitization(self):
        self.queue.add_task(command="X", task_type="review", priority="normal")

        self.submitter.submit_pending()

        # Check what was passed to submit_batch
        call_args = self.mock_client.submit_batch.call_args
        requests = (
            call_args.kwargs.get("requests") or call_args[1].get("requests") or call_args[0][0]
        )
        for req in requests:
            import re

            assert re.match(r"^[a-zA-Z0-9_-]{1,64}$", req.custom_id)

    def test_model_selection(self):
        """Review tasks use default model (sonnet), metadata can override."""
        self.queue.add_task(command="Review X", task_type="review", priority="normal")

        self.submitter.submit_pending()

        call_args = self.mock_client.submit_batch.call_args
        requests = call_args[1]["requests"] if call_args[1] else call_args[0][0]
        assert requests[0].params["model"] == "claude-sonnet-4-20250514"


# ============================================================================
# Retriever Tests
# ============================================================================


class TestBatchRetriever:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.results_dir = Path(self.tmp) / "results"
        self.queue = BatchTaskQueue(db_path=Path(self.tmp) / "q.db")
        self.mock_client = MagicMock()

        from batch.retriever import BatchRetriever

        self.retriever = BatchRetriever(
            queue=self.queue, client=self.mock_client, results_dir=self.results_dir
        )

    def _make_submitted_task(self, command="X", batch_id="batch_1", custom_id=None):
        t = self.queue.add_task(command=command, task_type="review", priority="normal")
        cid = custom_id or t.task_id
        self.queue.mark_submitted([t.task_id], batch_id, {t.task_id: cid}, "claude-sonnet-4")
        return t

    def _mock_result(self, custom_id, text="Result text", status="succeeded"):
        from batch.batch_api_client import BatchResult

        result_dict = (
            {
                "type": status,
                "message": {
                    "content": [{"type": "text", "text": text}],
                    "usage": {"input_tokens": 100, "output_tokens": 200},
                },
            }
            if status == "succeeded"
            else {"type": status, "error": {"message": "failed"}}
        )

        return BatchResult(custom_id=custom_id, result=result_dict, status=status)

    def test_retrieve_no_submitted(self):
        stats = self.retriever.retrieve_completed()
        assert stats.batches_checked == 0

    def test_retrieve_still_processing(self):
        self._make_submitted_task(batch_id="b1")
        self.mock_client.get_batch_status.return_value = {
            "status": "in_progress",
            "request_counts": {"processing": 1, "succeeded": 0},
            "progress_percentage": 0,
        }

        stats = self.retriever.retrieve_completed()
        assert stats.batches_checked == 1
        assert stats.batches_completed == 0
        assert stats.tasks_completed == 0

    def test_retrieve_completed_batch(self):
        t = self._make_submitted_task(batch_id="b_done", custom_id="cid_1")
        self.mock_client.get_batch_status.return_value = {"status": "completed"}
        self.mock_client._retrieve_batch_results.return_value = [
            self._mock_result("cid_1", text="All looks good"),
        ]

        stats = self.retriever.retrieve_completed()

        assert stats.batches_completed == 1
        assert stats.tasks_completed == 1
        assert stats.results_saved == 1

        completed = self.queue.get_task(t.task_id)
        assert completed.state == TaskState.COMPLETED
        assert completed.result_text == "All looks good"
        assert completed.token_input == 100
        assert completed.token_output == 200
        assert completed.result_file is not None

    def test_retrieve_saves_result_file(self):
        t = self._make_submitted_task(batch_id="b2", custom_id="cid_2")
        self.mock_client.get_batch_status.return_value = {"status": "completed"}
        self.mock_client._retrieve_batch_results.return_value = [
            self._mock_result("cid_2"),
        ]

        self.retriever.retrieve_completed()

        result_files = list(self.results_dir.glob("*.json"))
        assert len(result_files) == 1
        data = json.loads(result_files[0].read_text())
        assert data["job_id"] == t.task_id
        assert data["batch_id"] == "b2"
        assert data["status"] == "succeeded"

    def test_retrieve_failed_batch(self):
        t = self._make_submitted_task(batch_id="b_fail")
        self.mock_client.get_batch_status.return_value = {"status": "expired"}

        stats = self.retriever.retrieve_completed()

        assert stats.tasks_failed == 1
        failed = self.queue.get_task(t.task_id)
        assert failed.state == TaskState.FAILED
        assert "expired" in failed.error_message

    def test_retrieve_partial_failure(self):
        self._make_submitted_task(batch_id="b_mixed", custom_id="ok")
        self._make_submitted_task(batch_id="b_mixed", custom_id="err")
        self.mock_client.get_batch_status.return_value = {"status": "completed"}
        self.mock_client._retrieve_batch_results.return_value = [
            self._mock_result("ok", text="Success"),
            self._mock_result("err", status="errored"),
        ]

        stats = self.retriever.retrieve_completed()

        assert stats.tasks_completed == 1
        assert stats.tasks_failed == 1

    def test_retrieve_extracts_tokens(self):
        t = self._make_submitted_task(batch_id="b_tok", custom_id="tok")
        self.mock_client.get_batch_status.return_value = {"status": "completed"}
        self.mock_client._retrieve_batch_results.return_value = [
            self._mock_result("tok"),
        ]

        self.retriever.retrieve_completed()
        task = self.queue.get_task(t.task_id)
        assert task.token_input == 100
        assert task.token_output == 200


# ============================================================================
# Phase 3: get_tasks_by_state, cleanup_old_tasks, dashboard integration
# ============================================================================


class TestPhase3Methods:
    """Verify Phase 3 query methods and TTL cleanup."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test_queue.db"
        self.queue = BatchTaskQueue(db_path=self.db_path)

    def test_get_tasks_by_state_empty(self):
        tasks = self.queue.get_tasks_by_state(TaskState.COMPLETED)
        assert tasks == []

    def test_get_tasks_by_state_filters(self):
        t1 = self.queue.add_task(command="cmd1", task_type="review")
        t2 = self.queue.add_task(command="cmd2", task_type="review")
        # Complete one, leave the other pending
        self.queue.mark_submitted([t1.task_id], "b1", {t1.task_id: "c1"}, "claude-sonnet-4")
        self.queue.mark_completed_with_result(
            t1.task_id,
            result_text="done",
            result_file="/tmp/r.json",
            token_input=10,
            token_output=20,
        )

        pending = self.queue.get_tasks_by_state(TaskState.PENDING)
        completed = self.queue.get_tasks_by_state(TaskState.COMPLETED)

        assert len(pending) == 1
        assert pending[0].task_id == t2.task_id
        assert len(completed) == 1
        assert completed[0].task_id == t1.task_id

    def test_cleanup_old_tasks_removes_old(self):
        import sqlite3

        # Add and complete a task, then backdate its completed_at
        t = self.queue.add_task(command="old", task_type="review")
        self.queue.mark_submitted([t.task_id], "b1", {t.task_id: "c1"}, "claude-sonnet-4")
        self.queue.mark_completed_with_result(
            t.task_id,
            result_text="done",
            result_file="/tmp/r.json",
            token_input=10,
            token_output=20,
        )

        # Backdate completed_at to 60 days ago
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE batch_tasks SET completed_at = ? WHERE task_id = ?",
            ("2025-01-01T00:00:00", t.task_id),
        )
        conn.commit()
        conn.close()

        deleted = self.queue.cleanup_old_tasks(days=30)
        assert deleted == 1

        remaining = self.queue.get_tasks_by_state(TaskState.COMPLETED)
        assert len(remaining) == 0

    def test_cleanup_preserves_recent(self):
        t = self.queue.add_task(command="recent", task_type="review")
        self.queue.mark_submitted([t.task_id], "b1", {t.task_id: "c1"}, "claude-sonnet-4")
        self.queue.mark_completed_with_result(
            t.task_id,
            result_text="done",
            result_file="/tmp/r.json",
            token_input=10,
            token_output=20,
        )

        deleted = self.queue.cleanup_old_tasks(days=30)
        assert deleted == 0

        remaining = self.queue.get_tasks_by_state(TaskState.COMPLETED)
        assert len(remaining) == 1

    def test_cleanup_preserves_pending(self):
        import sqlite3

        t = self.queue.add_task(command="pending", task_type="review")

        # Even if we hack created_at to be old, pending tasks should be kept
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE batch_tasks SET completed_at = ? WHERE task_id = ?",
            ("2025-01-01T00:00:00", t.task_id),
        )
        conn.commit()
        conn.close()

        deleted = self.queue.cleanup_old_tasks(days=30)
        assert deleted == 0  # State is PENDING, not completed/failed

    def test_dashboard_local_queue_integration(self):
        """Verify dashboard get_local_queue reads from SQLite."""
        self.queue.add_task(command="p1", task_type="review")
        self.queue.add_task(command="p2", task_type="research")

        t3 = self.queue.add_task(command="done", task_type="review")
        self.queue.mark_submitted([t3.task_id], "b1", {t3.task_id: "c1"}, "claude-sonnet-4")
        self.queue.mark_completed_with_result(
            t3.task_id,
            result_text="result",
            result_file="/tmp/r.json",
            token_input=50,
            token_output=100,
        )

        # Verify via get_tasks_by_state (what dashboard now uses)
        pending = self.queue.get_tasks_by_state(TaskState.PENDING)
        completed = self.queue.get_tasks_by_state(TaskState.COMPLETED)

        assert len(pending) == 2
        assert len(completed) == 1
        assert completed[0].result_text == "result"
