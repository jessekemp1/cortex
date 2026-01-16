"""Priority Calculator - Calculate priority scores for recommendations."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PriorityCalculator:
    """Calculate priority scores considering urgency, importance, and dependencies."""

    def __init__(self):
        """Initialize priority calculator."""
        pass

    def calculate_priority(
        self, recommendation: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate priority score for a recommendation.

        Args:
            recommendation: Recommendation dictionary
            context: Optional context (project health, warnings, etc.)

        Returns:
            Priority score (0.0-1.0, higher = more important)
        """
        # Base priority from recommendation
        base_priority = self._get_base_priority(recommendation)

        # Urgency factor
        urgency = self._calculate_urgency(recommendation, context)

        # Importance factor
        importance = self._calculate_importance(recommendation, context)

        # Dependency factor
        dependency_impact = self._calculate_dependency_impact(recommendation, context)

        # Pattern success factor (if pattern-based)
        pattern_factor = self._calculate_pattern_factor(recommendation, context)

        # Portfolio intelligence factor
        portfolio_factor = self._calculate_portfolio_factor(recommendation, context)

        # Combine factors
        priority = (
            base_priority * 0.2
            + urgency * 0.25
            + importance * 0.25
            + dependency_impact * 0.15
            + pattern_factor * 0.1
            + portfolio_factor * 0.05
        )

        return min(max(priority, 0.0), 1.0)  # Clamp to [0.0, 1.0]

    def _get_base_priority(self, recommendation: Dict[str, Any]) -> float:
        """Get base priority from recommendation."""
        priority = recommendation.get("priority", "medium")
        # Handle enum or string priority
        if hasattr(priority, "value"):
            priority_str = priority.value.lower()
        elif isinstance(priority, str):
            priority_str = priority.lower()
        else:
            priority_str = str(priority).lower()
        priority_map = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.2,
        }
        return priority_map.get(priority_str, 0.5)

    def _calculate_urgency(
        self, recommendation: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate urgency factor."""
        urgency = 0.5  # Default

        # Check if recommendation addresses critical warnings
        if context:
            warnings = context.get("warnings", [])
            critical_warnings = [w for w in warnings if w.get("severity") == "critical"]
            if critical_warnings:
                rec_type = recommendation.get("type", "")
                if any(w.get("metric", "") in rec_type for w in critical_warnings):
                    urgency = 1.0

        # Check if recommendation is time-sensitive
        if recommendation.get("time_sensitive", False):
            urgency = max(urgency, 0.8)

        return urgency

    def _calculate_importance(
        self, recommendation: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate importance factor."""
        importance = 0.5  # Default

        # Check impact level
        impact = recommendation.get("estimated_impact", "medium").lower()
        impact_map = {
            "high": 1.0,
            "medium": 0.6,
            "low": 0.3,
        }
        importance = impact_map.get(impact, 0.5)

        # Boost if affects project health
        if context:
            health_score = context.get("health_score", 100)
            if health_score < 50:
                importance = min(importance * 1.3, 1.0)

        return importance

    def _calculate_dependency_impact(
        self, recommendation: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate dependency impact factor."""
        dependency_impact = 0.5  # Default

        # Check if recommendation unblocks other work
        blocks_others = recommendation.get("blocks_others", False)
        if blocks_others:
            dependency_impact = 0.9

        # Check if recommendation has dependencies
        dependencies = recommendation.get("dependencies", [])
        if dependencies:
            # If dependencies are met, boost priority
            if recommendation.get("dependencies_met", False):
                dependency_impact = 0.8
            else:
                # Lower priority if dependencies not met
                dependency_impact = 0.3

        return dependency_impact

    def _calculate_pattern_factor(
        self, recommendation: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate pattern success factor."""
        pattern_factor = 0.5  # Default

        # Check if recommendation is based on a pattern
        pattern_name = recommendation.get("pattern", "")
        if pattern_name and context:
            patterns = context.get("patterns", [])
            matching_pattern = next((p for p in patterns if p.get("pattern") == pattern_name), None)

            if matching_pattern:
                # Use pattern success rate
                success_rate = matching_pattern.get("success_rate", 0.5)
                pattern_factor = success_rate

        return pattern_factor

    def _calculate_portfolio_factor(
        self, recommendation: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate portfolio intelligence factor."""
        portfolio_factor = 0.5  # Default

        # Check if recommendation uses cross-project insights
        if context:
            cross_project_insights = context.get("cross_project_insights", [])
            if cross_project_insights:
                # Boost if similar work was successful in other projects
                portfolio_factor = 0.8

        return portfolio_factor

    def rank_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank recommendations by priority.

        Args:
            recommendations: List of recommendation dictionaries
            context: Optional context

        Returns:
            Sorted list of recommendations (highest priority first)
        """
        # Calculate priority for each recommendation
        for rec in recommendations:
            rec["calculated_priority"] = self.calculate_priority(rec, context)

        # Sort by calculated priority
        sorted_recs = sorted(
            recommendations,
            key=lambda r: r.get("calculated_priority", 0.0),
            reverse=True,
        )

        return sorted_recs
