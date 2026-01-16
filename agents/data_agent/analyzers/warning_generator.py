"""Warning Generator - Generate warnings based on trends and project health."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .trend_detector import TrendDetector

logger = logging.getLogger(__name__)


class WarningGenerator:
    """Generate warnings based on detected trends."""

    def __init__(self):
        """Initialize warning generator."""
        self.trend_detector = TrendDetector()

    def generate_warnings(
        self,
        project: str,
        trends: List[Dict[str, Any]],
        health_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate warnings based on trends and health data.

        Args:
            project: Project name
            trends: List of trend analysis results
            health_data: Optional project health data

        Returns:
            List of warning dictionaries
        """
        warnings = []

        # Generate warnings from trends
        for trend in trends:
            if trend.get("is_concerning", False):
                warning = self._create_warning_from_trend(project, trend)
                if warning:
                    warnings.append(warning)

        # Generate warnings from health data
        if health_data:
            health_warnings = self._create_warnings_from_health(project, health_data)
            warnings.extend(health_warnings)

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        warnings.sort(key=lambda w: severity_order.get(w.get("severity", "low"), 3))

        return warnings

    def _create_warning_from_trend(
        self, project: str, trend: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a warning from a concerning trend."""
        metric = trend.get("metric", "unknown")
        direction = trend.get("direction", "unknown")
        current_value = trend.get("current_value", 0)
        velocity = trend.get("velocity", 0)
        severity = trend.get("severity", "medium")

        # Generate warning message
        if direction == "decreasing":
            message = f"{metric.replace('_', ' ').title()} is decreasing (current: {current_value:.1f}, trend: {velocity:.2f}/day)"
        elif direction == "increasing" and metric in ["bug_rate", "error_rate"]:
            message = f"{metric.replace('_', ' ').title()} is increasing (current: {current_value:.1f}, trend: {velocity:.2f}/day)"
        else:
            return None  # Not concerning

        # Generate recommendation
        recommendation = self._generate_recommendation(metric, direction, current_value)

        return {
            "id": f"{project}_{metric}_{datetime.now().isoformat()}",
            "project": project,
            "type": "trend",
            "metric": metric,
            "severity": severity,
            "message": message,
            "current_value": current_value,
            "trend": direction,
            "velocity": velocity,
            "recommendation": recommendation,
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }

    def _create_warnings_from_health(
        self, project: str, health_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create warnings from health data."""
        warnings = []

        health_score = health_data.get("total_score", 0)

        if health_score < 40:
            warnings.append(
                {
                    "id": f"{project}_health_critical_{datetime.now().isoformat()}",
                    "project": project,
                    "type": "health",
                    "metric": "project_health",
                    "severity": "critical",
                    "message": f"Project health is critically low ({health_score:.1f}/100)",
                    "current_value": health_score,
                    "recommendation": "Review project status, address critical issues, consider refactoring",
                    "created_at": datetime.now().isoformat(),
                    "status": "active",
                }
            )
        elif health_score < 60:
            warnings.append(
                {
                    "id": f"{project}_health_low_{datetime.now().isoformat()}",
                    "project": project,
                    "type": "health",
                    "metric": "project_health",
                    "severity": "medium",
                    "message": f"Project health is below acceptable threshold ({health_score:.1f}/100)",
                    "current_value": health_score,
                    "recommendation": "Review project metrics, address identified issues",
                    "created_at": datetime.now().isoformat(),
                    "status": "active",
                }
            )

        # Check individual health components
        components = health_data.get("components", {})
        for component, score in components.items():
            if score < 50:
                warnings.append(
                    {
                        "id": f"{project}_{component}_low_{datetime.now().isoformat()}",
                        "project": project,
                        "type": "health_component",
                        "metric": component,
                        "severity": "medium" if score < 30 else "low",
                        "message": f"{component.replace('_', ' ').title()} score is low ({score:.1f}/100)",
                        "current_value": score,
                        "recommendation": f"Focus on improving {component.replace('_', ' ')}",
                        "created_at": datetime.now().isoformat(),
                        "status": "active",
                    }
                )

        return warnings

    def _generate_recommendation(self, metric: str, direction: str, current_value: float) -> str:
        """Generate actionable recommendation based on metric and trend."""
        recommendations = {
            "test_coverage": {
                "decreasing": f"Test coverage is decreasing. Current: {current_value:.1f}%. Add more tests, especially for critical paths.",
                "low": f"Test coverage is below 50% ({current_value:.1f}%). Aim for at least 70% coverage.",
            },
            "bug_rate": {
                "increasing": f"Bug rate is increasing ({current_value:.1f} bugs/period). Review recent changes, add more tests, improve code review process.",
            },
            "project_health": {
                "decreasing": f"Project health is declining ({current_value:.1f}/100). Review metrics, address technical debt, improve documentation.",
            },
            "code_quality": {
                "decreasing": f"Code quality is decreasing. Review code smells, refactor complex code, improve documentation.",
            },
        }

        metric_recs = recommendations.get(metric, {})

        if direction in metric_recs:
            return metric_recs[direction]
        elif "low" in metric_recs:
            return metric_recs["low"]
        else:
            return f"Monitor {metric.replace('_', ' ')} closely and take corrective action if trend continues."

    def categorize_warnings(
        self, warnings: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize warnings by type and severity."""
        categorized = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "by_type": {},
        }

        for warning in warnings:
            severity = warning.get("severity", "low")
            categorized[severity].append(warning)

            warning_type = warning.get("type", "unknown")
            if warning_type not in categorized["by_type"]:
                categorized["by_type"][warning_type] = []
            categorized["by_type"][warning_type].append(warning)

        return categorized
