import os
"""Base coordination agent for managing integration phases"""

import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add local-orchestrator to path for AgentResult import
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "local-orchestrator"))

try:
    from orchestrator_models import AgentResult
except ImportError:
    # Fallback if local-orchestrator not available
    from dataclasses import dataclass
    from typing import Optional as Opt

    @dataclass
    class AgentResult:
        success: bool
        message: str
        data: Opt[Dict[str, Any]] = None
        execution_time: Opt[float] = None
        timestamp: datetime = None


class BaseCoordinationAgent(ABC):
    """Base class for coordination agents that manage integration phases"""

    def __init__(self, phase_name: str, phase_number: int, root_dir: Optional[Path] = None):
        """
        Initialize coordination agent.

        Args:
            phase_name: Name of the phase (e.g., "Fix Local-Orchestrator")
            phase_number: Phase number (1, 2, or 3)
            root_dir: Root directory of the workspace
        """
        self.phase_name = phase_name
        self.phase_number = phase_number
        self.root_dir = root_dir or Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
        self.progress: Dict[str, Any] = {
            "phase": phase_number,
            "phase_name": phase_name,
            "status": "pending",
            "tasks_completed": 0,
            "tasks_total": 0,
            "start_time": None,
            "end_time": None,
            "errors": [],
        }

    @abstractmethod
    def execute_phase(self) -> AgentResult:
        """
        Execute the phase managed by this agent.

        Returns:
            AgentResult with execution outcome
        """
        pass

    def check_dependencies(self) -> bool:
        """
        Check if dependencies are met for this phase.

        Returns:
            True if dependencies are met, False otherwise
        """
        if self.phase_number == 1:
            # Phase 1 has no dependencies
            return True
        elif self.phase_number == 2:
            # Phase 2 depends on Phase 1 completion
            return self._check_phase_completion(1)
        elif self.phase_number == 3:
            # Phase 3 depends on Phase 2 completion
            return self._check_phase_completion(2)
        return False

    def _check_phase_completion(self, phase_number: int) -> bool:
        """Check if a previous phase is complete"""
        # Check for completion marker file
        marker_file = (
            self.root_dir
            / "cortex"
            / "agents"
            / "integration"
            / f"phase{phase_number}_complete.marker"
        )
        return marker_file.exists()

    def _mark_phase_complete(self):
        """Mark this phase as complete"""
        marker_file = (
            self.root_dir
            / "cortex"
            / "agents"
            / "integration"
            / f"phase{self.phase_number}_complete.marker"
        )
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.write_text(
            f"Phase {self.phase_number} completed at {datetime.now().isoformat()}\n"
        )

    def report_progress(self) -> Dict[str, Any]:
        """
        Report current progress of this phase.

        Returns:
            Dictionary with progress information
        """
        return self.progress.copy()

    def update_progress(self, task_name: str, status: str, error: Optional[str] = None):
        """Update progress for a specific task"""
        if status == "completed":
            self.progress["tasks_completed"] += 1
        if error:
            self.progress["errors"].append(
                {
                    "task": task_name,
                    "error": error,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    def start_phase(self):
        """Mark phase as started"""
        self.progress["status"] = "in_progress"
        self.progress["start_time"] = datetime.now().isoformat()

    def complete_phase(self, success: bool, message: str):
        """Mark phase as complete"""
        self.progress["status"] = "completed" if success else "failed"
        self.progress["end_time"] = datetime.now().isoformat()
        if success:
            self._mark_phase_complete()
