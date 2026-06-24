"""
Approval gate for work item dispatch.

Policy:
  - AUTO_ALL:  No gates (current behavior, for dry_run testing)
  - GATE_HIGH: AUTO: low/medium, GATE: high/critical
  - GATE_ALL:  Everything requires explicit approval

Approval is a file: ~/.cortex/approvals/{work_item_id}.approved
Pending is a file: ~/.cortex/approvals/pending/{work_item_id}.json

CLI to approve: cortex approve <id>  (or approve-all)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cortex.supervisor.models import WorkItem

log = logging.getLogger(__name__)


class ApprovalPolicy(Enum):
    AUTO_ALL = "auto_all"
    GATE_HIGH = "gate_high"
    GATE_ALL = "gate_all"


@dataclass
class ApprovalGate:
    """File-based approval gate for work item dispatch."""

    policy: ApprovalPolicy
    approval_dir: Path

    def check(self, work_item: WorkItem) -> tuple[bool, str]:
        """Return (approved, reason). If not approved, item is written to pending."""
        if self.policy.value == "auto_all":
            return True, "auto_all policy"

        if self.policy.value == "gate_high":
            # Compare by value to avoid dual-import identity issues
            # (cortex.supervisor.models vs supervisor.models)
            if work_item.priority.value in ("low", "medium"):
                return True, f"auto-approved ({work_item.priority.value})"

        # Check if explicitly approved via file
        if self._is_approved(work_item.id):
            return True, "explicitly approved"

        # Write to pending and return False
        self._write_pending(work_item)
        return False, f"awaiting approval ({work_item.priority.value})"

    def approve(self, work_item_id: str) -> None:
        """Approve a pending item (called by CLI)."""
        self.approval_dir.mkdir(parents=True, exist_ok=True)
        (self.approval_dir / f"{work_item_id}.approved").touch()
        # Remove from pending
        pending = self.approval_dir / "pending" / f"{work_item_id}.json"
        if pending.exists():
            pending.unlink()

    def get_pending(self) -> list[dict]:
        """List all pending approvals."""
        pending_dir = self.approval_dir / "pending"
        if not pending_dir.exists():
            return []
        results = []
        for f in sorted(pending_dir.glob("*.json")):
            try:
                results.append(json.loads(f.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def _is_approved(self, work_item_id: str) -> bool:
        return (self.approval_dir / f"{work_item_id}.approved").exists()

    def _write_pending(self, work_item: WorkItem) -> None:
        pending_dir = self.approval_dir / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / f"{work_item.id}.json").write_text(
            json.dumps(
                {
                    "id": work_item.id,
                    "description": work_item.description,
                    "priority": work_item.priority.value,
                    "task_type": work_item.task_type,
                    "project": work_item.project,
                    "created_at": work_item.created_at.isoformat(),
                },
                indent=2,
            )
        )
