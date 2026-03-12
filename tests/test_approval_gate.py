"""
Tests for approval gates on dispatch (Phase 2).

Validates:
  - AUTO_ALL policy approves everything
  - GATE_HIGH policy auto-approves LOW/MEDIUM, blocks HIGH/CRITICAL
  - GATE_ALL policy blocks everything
  - Explicit approval unblocks items
  - Pending items listed correctly
  - Approval cleans up pending file
"""

import json
from datetime import datetime, timezone

import pytest

from cortex.supervisor.approval import ApprovalGate, ApprovalPolicy
from cortex.supervisor.models import WorkItem, WorkItemPriority


def _make_work_item(
    priority: WorkItemPriority = WorkItemPriority.MEDIUM,
    item_id: str = "test-001",
    task_type: str = "research",
    description: str = "Test work item",
) -> WorkItem:
    return WorkItem(
        id=item_id,
        source="test",
        task_type=task_type,
        description=description,
        priority=priority,
    )


class TestAutoAllPolicy:
    def test_approves_critical(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.AUTO_ALL, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.CRITICAL)
        approved, reason = gate.check(wi)
        assert approved is True
        assert "auto_all" in reason

    def test_approves_low(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.AUTO_ALL, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.LOW)
        approved, _ = gate.check(wi)
        assert approved is True

    def test_no_pending_files_created(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.AUTO_ALL, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.CRITICAL)
        gate.check(wi)
        pending_dir = tmp_path / "pending"
        if pending_dir.exists():
            assert len(list(pending_dir.glob("*.json"))) == 0


class TestGateHighPolicy:
    def test_auto_approves_low(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.LOW)
        approved, reason = gate.check(wi)
        assert approved is True
        assert "auto-approved" in reason

    def test_auto_approves_medium(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.MEDIUM)
        approved, _ = gate.check(wi)
        assert approved is True

    def test_blocks_high(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.HIGH)
        approved, reason = gate.check(wi)
        assert approved is False
        assert "awaiting approval" in reason

    def test_blocks_critical(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.CRITICAL)
        approved, _ = gate.check(wi)
        assert approved is False

    def test_blocked_item_creates_pending_file(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.HIGH, item_id="blocked-001")
        gate.check(wi)
        pending_files = list((tmp_path / "pending").glob("*.json"))
        assert len(pending_files) == 1
        data = json.loads(pending_files[0].read_text())
        assert data["id"] == "blocked-001"
        assert data["priority"] == "high"

    def test_explicit_approval_unblocks(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.HIGH, item_id="approve-me")
        assert gate.check(wi)[0] is False
        gate.approve("approve-me")
        assert gate.check(wi)[0] is True

    def test_approve_cleans_pending(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.HIGH, item_id="cleanup-001")
        gate.check(wi)
        assert (tmp_path / "pending" / "cleanup-001.json").exists()
        gate.approve("cleanup-001")
        assert not (tmp_path / "pending" / "cleanup-001.json").exists()
        assert (tmp_path / "cleanup-001.approved").exists()


class TestGateAllPolicy:
    def test_blocks_low(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_ALL, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.LOW)
        approved, _ = gate.check(wi)
        assert approved is False

    def test_blocks_medium(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_ALL, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.MEDIUM)
        approved, _ = gate.check(wi)
        assert approved is False


class TestPendingList:
    def test_get_pending_lists_blocked_items(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi1 = _make_work_item(priority=WorkItemPriority.HIGH, item_id="pending-001")
        wi2 = _make_work_item(priority=WorkItemPriority.CRITICAL, item_id="pending-002")
        gate.check(wi1)
        gate.check(wi2)
        pending = gate.get_pending()
        assert len(pending) == 2
        ids = {p["id"] for p in pending}
        assert ids == {"pending-001", "pending-002"}

    def test_get_pending_empty_when_none_blocked(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.LOW)
        gate.check(wi)
        assert gate.get_pending() == []

    def test_get_pending_excludes_approved(self, tmp_path):
        gate = ApprovalGate(ApprovalPolicy.GATE_HIGH, tmp_path)
        wi = _make_work_item(priority=WorkItemPriority.HIGH, item_id="will-approve")
        gate.check(wi)
        assert len(gate.get_pending()) == 1
        gate.approve("will-approve")
        assert len(gate.get_pending()) == 0
