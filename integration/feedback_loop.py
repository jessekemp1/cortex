import os
"""Bidirectional feedback loop between Cortex intelligence and runtime."""

from pathlib import Path
from typing import Any, Dict, Optional

# Use internal cortex imports
try:
    from cortex.integration.history_analyzer import ExecutionHistoryAnalyzer
    from cortex.integration.local_orchestrator import CortexLocalOrchestratorIntegration
except ImportError:
    ExecutionHistoryAnalyzer = None
    CortexLocalOrchestratorIntegration = None

# Recommendation class from cortex
try:
    from cortex.recommendation_engine import Recommendation
except ImportError:
    Recommendation = None

Priority = None  # Deprecated - use string priorities


class FeedbackLoop:
    """Bidirectional feedback loop for learning and adaptation"""

    def __init__(self, root_dir: Optional[Path] = None):
        """
        Initialize feedback loop.

        Args:
            root_dir: Root directory of workspace
        """
        self.root_dir = root_dir or Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
        self.analyzer = ExecutionHistoryAnalyzer(root_dir) if ExecutionHistoryAnalyzer else None
        self.integration = (
            CortexLocalOrchestratorIntegration(root_dir)
            if CortexLocalOrchestratorIntegration
            else None
        )

    def _get_confidence_value(self, confidence) -> float:
        """Convert confidence to float, handling both enum and numeric types."""
        if hasattr(confidence, "value"):
            # Enum (e.g., Confidence.HIGH -> "high")
            conf_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            return conf_map.get(confidence.value.lower(), 0.7)
        elif isinstance(confidence, (int, float)):
            return float(confidence)
        return 0.7

    def adjust_recommendation_priority(
        self, recommendation: Recommendation, base_priority: Optional[Priority] = None
    ) -> Recommendation:
        """
        Adjust recommendation priority based on execution history.

        Args:
            recommendation: Original recommendation
            base_priority: Base priority level

        Returns:
            Recommendation with adjusted priority
        """
        if not self.analyzer or not self.analyzer.is_available():
            return recommendation  # No adjustment if analyzer not available

        # Get action type identifier (Recommendation uses 'title' not 'action_title')
        action_title = getattr(
            recommendation, "title", getattr(recommendation, "action_title", "unknown")
        )
        action_type = f"cortex_{action_title.lower().replace(' ', '_').replace('-', '_')}"

        # Get success rate
        success_rate = self.analyzer.get_success_rate(action_type)

        # Get current priority (handle both string and Priority enum)
        current_priority = getattr(recommendation, "priority", "medium")
        # Convert enum to string if needed
        if hasattr(current_priority, "value"):
            current_priority = current_priority.value
        elif not isinstance(current_priority, str):
            current_priority = str(current_priority)
        priority_values = ["low", "medium", "high"]
        current_idx = (
            priority_values.index(current_priority.lower())
            if current_priority.lower() in priority_values
            else 1
        )

        # Adjust priority based on success rate
        # High success rate -> increase priority
        # Low success rate -> decrease priority
        if success_rate > 0.8:
            # Very successful, increase priority
            if current_idx < len(priority_values) - 1:
                adjusted_priority = priority_values[min(current_idx + 1, len(priority_values) - 1)]
            else:
                adjusted_priority = current_priority
        elif success_rate < 0.3:
            # Low success rate, decrease priority
            if current_idx > 0:
                adjusted_priority = priority_values[max(current_idx - 1, 0)]
            else:
                adjusted_priority = current_priority
        else:
            # Neutral, keep original
            adjusted_priority = current_priority

        # Create adjusted recommendation
        # Note: Recommendation is a dataclass, so we create a new one with updated values
        from recommendation_engine import Recommendation as RecClass

        adjusted = RecClass(
            id=getattr(recommendation, "id", "adjusted"),
            type=getattr(recommendation, "type", "next_action"),
            priority=adjusted_priority,
            title=getattr(
                recommendation,
                "title",
                getattr(recommendation, "action_title", "Unknown"),
            ),
            description=getattr(recommendation, "description", ""),
            rationale=getattr(recommendation, "rationale", "")
            + f" [Adjusted based on {success_rate:.0%} success rate]",
            estimated_effort=getattr(
                recommendation,
                "estimated_effort",
                getattr(recommendation, "effort", "Unknown"),
            ),
            estimated_impact=getattr(
                recommendation,
                "estimated_impact",
                getattr(recommendation, "impact", "Unknown"),
            ),
            prerequisites=getattr(recommendation, "prerequisites", []),
            related_goals=getattr(recommendation, "related_goals", []),
            related_projects=getattr(recommendation, "related_projects", []),
            confidence=self._get_confidence_value(getattr(recommendation, "confidence", 0.8))
            * success_rate,  # Adjust confidence
        )

        return adjusted

    def learn_from_execution(
        self, action_title: str, success: bool, duration: Optional[float] = None
    ):
        """
        Learn from an execution result.

        Args:
            action_title: Title of the action executed
            success: Whether execution was successful
            duration: Execution duration in seconds
        """
        # This would update learning models or metrics
        # For now, execution history is automatically tracked by local-orchestrator
        # Future: Could add explicit learning mechanisms here
        pass

    def get_learning_metrics(self) -> Dict[str, Any]:
        """
        Get learning metrics and insights.

        Returns:
            Dictionary with learning metrics
        """
        if not self.analyzer or not self.analyzer.is_available():
            return {"available": False}

        # Get statistics for all Cortex-scheduled actions
        if not self.integration:
            return {"available": False, "integration": False}

        scheduled_actions = self.integration.list_scheduled_actions()

        metrics = {
            "available": True,
            "scheduled_actions": len(scheduled_actions),
            "action_statistics": {},
        }

        for action in scheduled_actions:
            action_id = action.get("agent_id", "")
            if action_id.startswith("cortex_"):
                stats = self.analyzer.get_action_statistics(action_id)
                metrics["action_statistics"][action_id] = stats

        return metrics
