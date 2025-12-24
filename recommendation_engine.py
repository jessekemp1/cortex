"""
Recommendation Engine - Layer 4 Integration

Complete recommendation system integrating all 4 layers:
- Layer 1: Project Analysis
- Layer 2: Pattern Memory
- Layer 3: Warning System & Metrics
- Layer 4: Smart Recommendations

This is the top-level API for the Cortex Intelligence Stack.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Layer 3: Warning System
from intelligence.monitoring.metric_tracker import MetricTracker
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
from intelligence.monitoring.alert_generator import AlertGenerator

# Layer 4: Smart Recommendations
from intelligence.recommendations.file_selector import FileSelector
from intelligence.recommendations.smart_generator import SmartRecommendationGenerator
from intelligence.recommendations.alert_adapter import adapt_alerts


@dataclass
class Task:
    """Represents a task (placeholder for now)."""
    id: str
    title: str
    status: str
    metadata: Dict[str, Any] = None


@dataclass
class Goal:
    """Represents a project goal (placeholder for now)."""
    id: str
    name: str
    target_value: float
    current_value: float
    metric_type: str


@dataclass
class Recommendation:
    """Recommendation from the engine."""
    type: str
    title: str
    description: str
    priority: int
    confidence: float
    files: List[str] = None
    steps: List[str] = None
    metadata: Dict[str, Any] = None


class RecommendationEngine:
    """
    Top-level recommendation engine integrating all intelligence layers.

    This class provides the main API for generating smart, context-aware
    recommendations based on project health, goals, patterns, and metrics.
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        enable_learning: bool = True,
        enable_patterns: bool = True
    ):
        """
        Initialize the recommendation engine.

        Args:
            project_path: Path to project (defaults to current directory)
            enable_learning: Enable Layer 3 learning system
            enable_patterns: Enable Layer 2 pattern memory
        """
        self.project_path = project_path or Path.cwd()

        # Layer 3: Warning System components
        self.metric_tracker = MetricTracker()
        self.trend_analyzer = TrendAnalyzer(self.metric_tracker)
        self.alert_generator = AlertGenerator(self.trend_analyzer)

        # Layer 4: Smart Recommendations components
        self.file_selector = FileSelector(self.project_path)
        self.smart_generator = SmartRecommendationGenerator(
            file_selector=self.file_selector
        )

        # Optional integrations
        self.learning_system = None
        self.pattern_memory = None

        if enable_learning:
            try:
                # Future: Learning system integration
                pass
            except ImportError:
                pass

        if enable_patterns:
            try:
                # Future: Pattern memory integration
                pass
            except ImportError:
                pass

    def generate_recommendations(
        self,
        tasks: List[Task] = None,
        goals: List[Goal] = None,
        context: Dict[str, Any] = None,
        limit: int = 10
    ) -> List[Recommendation]:
        """
        Generate prioritized recommendations using smart intelligence.

        Args:
            tasks: Current task list
            goals: Active goals
            context: Current work context (files, recent actions, etc.)
            limit: Maximum recommendations to return

        Returns:
            Sorted list of intelligent recommendations
        """
        tasks = tasks or []
        goals = goals or []
        context = context or {}

        recommendations = []

        # Get current project name
        project_name = self.project_path.name

        # Enrich context with alerts from Layer 3
        alerts = self.alert_generator.generate_alerts(project_name, days=7)
        if alerts:
            # Adapt alerts to Layer 4 format
            adapted_alerts = adapt_alerts(alerts)
            context["alerts"] = [
                {
                    "id": a.id,
                    "type": a.type,
                    "severity": a.severity,
                    "message": a.message
                }
                for a in adapted_alerts
            ]

        # 1. Alert-driven recommendations (from Layer 3)
        if alerts:
            alert_recs = self.smart_generator.generate_alert_recommendations(
                alerts=adapted_alerts,
                context=context
            )
            recommendations.extend(alert_recs)

        # 2. Blocker resolution
        if tasks:
            blocker_recs = self.smart_generator.generate_blocker_recommendations(
                tasks=[{"id": t.id, "title": t.title, "status": t.status} for t in tasks],
                context=context
            )
            recommendations.extend(blocker_recs)

        # 3. Goal progress
        if goals:
            goal_recs = self.smart_generator.generate_goal_recommendations(
                goals=[{
                    "id": g.id,
                    "name": g.name,
                    "target_value": g.target_value,
                    "current_value": g.current_value,
                    "metric_type": g.metric_type
                } for g in goals],
                tasks=[{"id": t.id, "title": t.title} for t in tasks],
                context=context
            )
            recommendations.extend(goal_recs)

        # 4. Health recommendations
        health_recs = self.smart_generator.generate_health_recommendations(
            tasks=[{"id": t.id, "title": t.title} for t in tasks],
            context=context
        )
        recommendations.extend(health_recs)

        # 5. Momentum recommendations
        momentum_recs = self.smart_generator.generate_momentum_recommendations(
            tasks=[{"id": t.id, "title": t.title} for t in tasks],
            context=context
        )
        recommendations.extend(momentum_recs)

        # Apply learning adjustments (Layer 3)
        if self.learning_system:
            recommendations = self._apply_learning_adjustments(recommendations)

        # Enrich with patterns (Layer 2)
        if self.pattern_memory:
            recommendations = self._enrich_with_patterns(recommendations)

        # Enrich with Layer 4 intelligence (files, steps, patterns)
        recommendations = self.smart_generator.enrich_with_intelligence(
            recommendations=recommendations,
            context=context
        )

        # Sort by priority score
        recommendations.sort(key=lambda r: self._priority_score(r), reverse=True)

        return recommendations[:limit]

    def get_active_alerts(self, project: Optional[str] = None, days: int = 7):
        """
        Get active alerts for a project.

        Args:
            project: Project name (defaults to current directory name)
            days: Number of days to analyze

        Returns:
            List of active alerts
        """
        project_name = project or self.project_path.name
        return self.alert_generator.generate_alerts(project_name, days=days)

    def get_project_health(self, project: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive project health metrics.

        Args:
            project: Project name (defaults to current directory name)
            days: Number of days to analyze

        Returns:
            Dictionary with health metrics and trends
        """
        project_name = project or self.project_path.name

        # Get all trends
        coverage_trend = self.trend_analyzer.analyze_coverage_trend(project_name, days)
        violations_trend = self.trend_analyzer.analyze_violation_trend(project_name, days)
        activity_trend = self.trend_analyzer.analyze_activity_trend(project_name, days)

        # Get alerts
        alerts = self.alert_generator.generate_alerts(project_name, days)

        return {
            "project": project_name,
            "coverage": {
                "current": coverage_trend.end_value if coverage_trend else 0,
                "trend": coverage_trend.direction.value if coverage_trend else "unknown",
                "delta": coverage_trend.delta if coverage_trend else 0,
            },
            "violations": {
                "current": int(violations_trend.end_value) if violations_trend else 0,
                "trend": violations_trend.direction.value if violations_trend else "unknown",
                "delta": int(violations_trend.delta) if violations_trend else 0,
            },
            "activity": {
                "commits": int(activity_trend.end_value) if activity_trend else 0,
                "trend": activity_trend.direction.value if activity_trend else "unknown",
            },
            "alerts": {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.severity.value == "critical"),
                "warning": sum(1 for a in alerts if a.severity.value == "warning"),
            }
        }

    def _apply_learning_adjustments(self, recommendations):
        """Apply learning-based adjustments to recommendation priorities."""
        # Placeholder for future learning system integration
        return recommendations

    def _enrich_with_patterns(self, recommendations):
        """Enrich recommendations with pattern-based insights."""
        # Placeholder for future pattern memory integration
        return recommendations

    def _priority_score(self, recommendation) -> float:
        """
        Calculate priority score for a recommendation.

        Args:
            recommendation: Recommendation object

        Returns:
            Priority score (higher = more important)
        """
        # Base score from recommendation priority
        score = getattr(recommendation, 'priority_score', 0.5)

        # Boost based on recommendation type
        type_boost = {
            'blocker': 2.0,
            'alert': 1.8,
            'goal': 1.5,
            'health': 1.2,
            'momentum': 1.0,
        }
        rec_type = getattr(recommendation, 'type', 'unknown')
        score *= type_boost.get(rec_type, 1.0)

        # Boost based on confidence
        confidence = getattr(recommendation, 'confidence', 0.5)
        if hasattr(confidence, 'value'):
            # Handle Confidence enum
            confidence_map = {'high': 0.9, 'medium': 0.7, 'low': 0.5}
            confidence = confidence_map.get(confidence.value, 0.5)
        score *= (0.5 + confidence)

        return score
