"""Execution history analyzer for learning from Cortex runtime."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# Use internal cortex.runtime imports (merged from local-orchestrator)
try:
    from cortex.runtime.storage.history import ExecutionHistory

    HISTORY_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    ExecutionHistory = None
    HISTORY_AVAILABLE = False


class ExecutionHistoryAnalyzer:
    """Analyze local-orchestrator execution history for learning"""

    def __init__(self, root_dir: Optional[Path] = None):
        """
        Initialize analyzer.

        Args:
            root_dir: Root directory of workspace
        """
        self.root_dir = root_dir or Path("/Users/jesse.kemp/Dev")
        self.history: Optional[Any] = None

        if HISTORY_AVAILABLE and ExecutionHistory:
            try:
                self.history = ExecutionHistory()
            except Exception:
                self.history = None

    def is_available(self) -> bool:
        """Check if execution history is available"""
        return HISTORY_AVAILABLE and self.history is not None

    def get_success_rate(self, action_type: str, days: int = 30) -> float:
        """
        Get success rate for a specific action type.

        Args:
            action_type: Action type identifier (e.g., "cortex_git_repository_cleanup")
            days: Number of days to analyze

        Returns:
            Success rate as float (0.0 to 1.0)
        """
        if not self.is_available():
            return 0.5  # Default neutral rate

        try:
            # Get recent executions for this action
            executions = self.history.get_recent_executions(
                limit=1000, agent_id=action_type
            )

            if not executions:
                return 0.5  # No data, return neutral

            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_executions = [
                e
                for e in executions
                if datetime.fromisoformat(e.get("start_time", "")) >= cutoff_date
            ]

            if not recent_executions:
                return 0.5

            # Calculate success rate
            successful = sum(1 for e in recent_executions if e.get("success", False))
            total = len(recent_executions)

            return successful / total if total > 0 else 0.5

        except Exception:
            return 0.5

    def get_avg_duration(self, action_type: str, days: int = 30) -> float:
        """
        Get average duration for a specific action type.

        Args:
            action_type: Action type identifier
            days: Number of days to analyze

        Returns:
            Average duration in seconds
        """
        if not self.is_available():
            return 0.0

        try:
            executions = self.history.get_recent_executions(
                limit=1000, agent_id=action_type
            )

            if not executions:
                return 0.0

            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_executions = [
                e
                for e in executions
                if datetime.fromisoformat(e.get("start_time", "")) >= cutoff_date
                and e.get("duration_seconds") is not None
            ]

            if not recent_executions:
                return 0.0

            # Calculate average
            durations = [e.get("duration_seconds", 0) for e in recent_executions]
            return sum(durations) / len(durations) if durations else 0.0

        except Exception:
            return 0.0

    def get_action_statistics(self, action_type: str, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive statistics for an action type.

        Args:
            action_type: Action type identifier
            days: Number of days to analyze

        Returns:
            Dictionary with statistics
        """
        return {
            "success_rate": self.get_success_rate(action_type, days),
            "avg_duration": self.get_avg_duration(action_type, days),
            "total_executions": self._get_total_executions(action_type, days),
            "recent_failures": self._get_recent_failures(action_type, days),
        }

    def _get_total_executions(self, action_type: str, days: int) -> int:
        """Get total number of executions"""
        if not self.is_available():
            return 0

        try:
            executions = self.history.get_recent_executions(
                limit=1000, agent_id=action_type
            )

            cutoff_date = datetime.now() - timedelta(days=days)
            recent = [
                e
                for e in executions
                if datetime.fromisoformat(e.get("start_time", "")) >= cutoff_date
            ]

            return len(recent)
        except Exception:
            return 0

    def _get_recent_failures(self, action_type: str, days: int) -> int:
        """Get number of recent failures"""
        if not self.is_available():
            return 0

        try:
            executions = self.history.get_recent_executions(
                limit=1000, agent_id=action_type
            )

            cutoff_date = datetime.now() - timedelta(days=days)
            recent = [
                e
                for e in executions
                if datetime.fromisoformat(e.get("start_time", "")) >= cutoff_date
                and not e.get("success", True)
            ]

            return len(recent)
        except Exception:
            return 0
