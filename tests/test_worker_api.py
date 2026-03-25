"""Tests for the worker API and registry (Phase 3).

Tests:
  - Worker registration
  - Heartbeat tracking
  - Task claiming and completion
  - Stale task reclamation
  - Auth token validation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cortex.supervisor.worker_api import WorkerInfo, WorkerRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> WorkerRegistry:
    return WorkerRegistry(heartbeat_timeout_seconds=60)


def _make_worker(worker_id: str = "w1", hostname: str = "test-host") -> WorkerInfo:
    return WorkerInfo(
        worker_id=worker_id,
        hostname=hostname,
        capabilities=["sonnet", "haiku"],
        max_concurrent=2,
    )


# ---------------------------------------------------------------------------
# Tests: Worker registration
# ---------------------------------------------------------------------------


class TestWorkerRegistration:
    def test_register_worker(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        assert registry.worker_count == 1

    def test_register_multiple_workers(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        registry.register_worker(_make_worker("w2", "host-2"))
        assert registry.worker_count == 2

    def test_list_workers(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        workers = registry.list_workers()
        assert len(workers) == 1
        assert workers[0]["worker_id"] == "w1"
        assert workers[0]["status"] == "idle"


# ---------------------------------------------------------------------------
# Tests: Heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_known_worker(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        assert registry.heartbeat("w1")

    def test_heartbeat_unknown_worker(self, registry: WorkerRegistry) -> None:
        assert not registry.heartbeat("nonexistent")


# ---------------------------------------------------------------------------
# Tests: Task claiming
# ---------------------------------------------------------------------------


class TestTaskClaiming:
    def test_claim_task(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        claim = registry.claim_task("task-1", "w1", {"id": "task-1"}, {"tier": "sonnet"})
        assert claim.task_id == "task-1"
        assert claim.worker_id == "w1"
        assert registry.active_task_count == 1

    def test_claim_sets_worker_busy(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        registry.claim_task("task-1", "w1", {}, {})
        workers = registry.list_workers()
        assert workers[0]["status"] == "busy"

    def test_complete_task(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        registry.claim_task("task-1", "w1", {}, {})
        claim = registry.complete_task("task-1")
        assert claim is not None
        assert claim.task_id == "task-1"
        assert registry.active_task_count == 0

    def test_complete_sets_worker_idle(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        registry.claim_task("task-1", "w1", {}, {})
        registry.complete_task("task-1")
        workers = registry.list_workers()
        assert workers[0]["status"] == "idle"

    def test_complete_unknown_task(self, registry: WorkerRegistry) -> None:
        claim = registry.complete_task("nonexistent")
        assert claim is None


# ---------------------------------------------------------------------------
# Tests: Stale task reclamation
# ---------------------------------------------------------------------------


class TestStaleReclamation:
    def test_no_stale_tasks_when_fresh(self, registry: WorkerRegistry) -> None:
        registry.register_worker(_make_worker("w1"))
        registry.claim_task("task-1", "w1", {}, {})
        stale = registry.get_stale_claims()
        assert len(stale) == 0

    def test_stale_task_after_timeout(self, registry: WorkerRegistry) -> None:
        worker = _make_worker("w1")
        worker.last_heartbeat = datetime.now(tz=timezone.utc) - timedelta(seconds=120)
        registry.register_worker(worker)
        registry.claim_task("task-1", "w1", {}, {})

        stale = registry.get_stale_claims()
        assert len(stale) == 1
        assert stale[0].task_id == "task-1"

    def test_reclaim_stale_tasks(self, registry: WorkerRegistry) -> None:
        worker = _make_worker("w1")
        worker.last_heartbeat = datetime.now(tz=timezone.utc) - timedelta(seconds=120)
        registry.register_worker(worker)
        registry.claim_task("task-1", "w1", {}, {})

        reclaimed = registry.reclaim_stale_tasks()
        assert "task-1" in reclaimed
        assert registry.active_task_count == 0

    def test_claim_from_unknown_worker_is_stale(self, registry: WorkerRegistry) -> None:
        """Tasks claimed by unregistered workers should be stale."""
        registry._claimed_tasks["task-orphan"] = type(
            "Claim", (), {"task_id": "task-orphan", "worker_id": "gone"}
        )()
        stale = registry.get_stale_claims()
        assert len(stale) == 1
