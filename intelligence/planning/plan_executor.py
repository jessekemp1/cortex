"""
PlanExecutor - Tracks and manages plan execution.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.planning.models import Plan, PlanStatus, PlanStep, StepStatus


class PlanExecutor:
    """
    Manages plan execution and tracks progress.

    Provides methods to start/complete steps, track progress,
    and persist plan state to disk.
    """

    def __init__(self, storage_path: Path = None):
        """
        Initialize the plan executor.

        Args:
            storage_path: Directory to store plan state (defaults to ~/.cortex/plans)
        """
        if storage_path is None:
            storage_path = Path.home() / ".cortex" / "plans"

        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.active_plan: Optional[Plan] = None

    def load_plan(self, plan_id: str) -> Plan:
        """
        Load a plan from storage.

        Args:
            plan_id: Plan identifier

        Returns:
            Plan object

        Raises:
            FileNotFoundError: If plan doesn't exist
        """
        plan_file = self.storage_path / f"{plan_id}.json"

        if not plan_file.exists():
            raise FileNotFoundError(f"Plan not found: {plan_id}")

        with open(plan_file, "r") as f:
            data = json.load(f)

        return self._dict_to_plan(data)

    def save_plan(self, plan: Plan):
        """
        Save a plan to storage.

        Args:
            plan: Plan to save
        """
        plan_file = self.storage_path / f"{plan.id}.json"

        with open(plan_file, "w") as f:
            json.dump(plan.to_dict(), f, indent=2)

    def start_plan(self, plan: Plan):
        """
        Start execution of a plan.

        Args:
            plan: Plan to start
        """
        plan.start()
        self.active_plan = plan
        self.save_plan(plan)

    def start_step(self, step_id: str):
        """
        Start a specific step in the active plan.

        Args:
            step_id: Step identifier

        Raises:
            ValueError: If no active plan or step not found
        """
        if not self.active_plan:
            raise ValueError("No active plan")

        step = self._find_step(step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        # Check dependencies
        completed_ids = [s.id for s in self.active_plan.steps if s.status == StepStatus.COMPLETED]
        if not step.can_start(completed_ids):
            missing_deps = [dep for dep in step.dependencies if dep not in completed_ids]
            raise ValueError(f"Cannot start step {step_id}: dependencies not met: {missing_deps}")

        step.start()
        self.save_plan(self.active_plan)

    def complete_step(self, step_id: str, notes: str = ""):
        """
        Mark a step as completed.

        Args:
            step_id: Step identifier
            notes: Optional completion notes

        Raises:
            ValueError: If no active plan or step not found
        """
        if not self.active_plan:
            raise ValueError("No active plan")

        step = self._find_step(step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        step.complete()
        if notes:
            step.notes += f"\nCompleted: {notes}"

        # Check if all steps are completed
        if all(
            s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for s in self.active_plan.steps
        ):
            self.active_plan.complete()

        self.save_plan(self.active_plan)

    def skip_step(self, step_id: str, reason: str = ""):
        """
        Skip a step.

        Args:
            step_id: Step identifier
            reason: Reason for skipping

        Raises:
            ValueError: If no active plan or step not found
        """
        if not self.active_plan:
            raise ValueError("No active plan")

        step = self._find_step(step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        step.skip(reason)
        self.save_plan(self.active_plan)

    def block_step(self, step_id: str, reason: str):
        """
        Block a step.

        Args:
            step_id: Step identifier
            reason: Reason for blocking

        Raises:
            ValueError: If no active plan or step not found
        """
        if not self.active_plan:
            raise ValueError("No active plan")

        step = self._find_step(step_id)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        step.block(reason)

        # Check if this blocks the entire plan
        if any(s.status == StepStatus.BLOCKED for s in self.active_plan.steps):
            self.active_plan.block(f"Step {step_id} is blocked: {reason}")

        self.save_plan(self.active_plan)

    def get_next_step(self) -> Optional[PlanStep]:
        """
        Get the next step that can be executed.

        Returns:
            Next executable step or None
        """
        if not self.active_plan:
            return None

        return self.active_plan.get_next_step()

    def get_progress(self) -> Dict[str, Any]:
        """
        Get current plan progress.

        Returns:
            Progress dictionary
        """
        if not self.active_plan:
            return {"error": "No active plan"}

        return self.active_plan.get_progress()

    def list_plans(self, status_filter: PlanStatus = None) -> List[Dict[str, Any]]:
        """
        List all stored plans.

        Args:
            status_filter: Optional status filter

        Returns:
            List of plan summaries
        """
        plans = []

        for plan_file in self.storage_path.glob("*.json"):
            try:
                with open(plan_file, "r") as f:
                    data = json.load(f)

                if status_filter is None or data["status"] == status_filter.value:
                    plans.append(
                        {
                            "id": data["id"],
                            "title": data["title"],
                            "status": data["status"],
                            "priority": data["priority"],
                            "created_at": data["created_at"],
                            "progress": data.get("progress", {}),
                        }
                    )
            except Exception:
                # Skip invalid plan files
                continue

        # Sort by creation date (newest first)
        plans.sort(key=lambda p: p["created_at"], reverse=True)

        return plans

    def export_plan_markdown(self, plan_id: str = None) -> str:
        """
        Export plan to markdown format.

        Args:
            plan_id: Plan ID (uses active plan if None)

        Returns:
            Markdown string
        """
        plan = self.active_plan if plan_id is None else self.load_plan(plan_id)

        if not plan:
            raise ValueError("No plan to export")

        return plan.to_markdown()

    def _find_step(self, step_id: str) -> Optional[PlanStep]:
        """Find a step in the active plan."""
        if not self.active_plan:
            return None

        for step in self.active_plan.steps:
            if step.id == step_id:
                return step

        return None

    def _dict_to_plan(self, data: Dict[str, Any]) -> Plan:
        """Convert dictionary to Plan object."""
        from intelligence.planning.models import PlanPriority, PlanStatus, StepStatus

        # Parse steps
        steps = []
        for step_data in data["steps"]:
            step = PlanStep(
                id=step_data["id"],
                title=step_data["title"],
                description=step_data["description"],
                status=StepStatus(step_data["status"]),
                estimated_time=step_data.get("estimated_time"),
                actual_time=step_data.get("actual_time"),
                dependencies=step_data.get("dependencies", []),
                files=step_data.get("files", []),
                validation=step_data.get("validation"),
                notes=step_data.get("notes", ""),
                started_at=(
                    datetime.fromisoformat(step_data["started_at"])
                    if step_data.get("started_at")
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(step_data["completed_at"])
                    if step_data.get("completed_at")
                    else None
                ),
                metadata=step_data.get("metadata", {}),
            )
            steps.append(step)

        # Create plan
        plan = Plan(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            priority=PlanPriority(data["priority"]),
            status=PlanStatus(data["status"]),
            steps=steps,
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            estimated_total_time=data.get("estimated_total_time"),
            actual_total_time=data.get("actual_total_time"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

        return plan
