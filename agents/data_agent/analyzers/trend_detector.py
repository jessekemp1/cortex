"""Trend Detector - Detect trends in coverage, bug rates, and project health."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrendDetector:
    """Detect trends in project metrics."""

    def __init__(self):
        """Initialize trend detector."""
        pass

    def detect_trends(
        self, metric_data: List[Dict[str, Any]], metric_name: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        Detect trends in metric data.

        Args:
            metric_data: List of metric data points with 'value' and 'timestamp'
            metric_name: Name of the metric being analyzed
            days: Number of days to analyze

        Returns:
            Dict with trend analysis including direction, velocity, and concern level
        """
        if not metric_data or len(metric_data) < 2:
            return {
                "metric": metric_name,
                "trend": "insufficient_data",
                "direction": "unknown",
                "velocity": 0.0,
                "is_concerning": False,
            }

        # Sort by timestamp
        sorted_data = sorted(metric_data, key=lambda x: x.get("timestamp", ""))

        # Calculate trend direction
        first_value = sorted_data[0].get("value", 0)
        last_value = sorted_data[-1].get("value", 0)

        # Calculate velocity (rate of change)
        time_span = self._calculate_time_span(sorted_data)
        if time_span > 0:
            velocity = (last_value - first_value) / time_span  # Change per day
        else:
            velocity = 0.0

        # Determine direction
        if velocity > 0.01:  # Threshold for "increasing"
            direction = "increasing"
        elif velocity < -0.01:  # Threshold for "decreasing"
            direction = "decreasing"
        else:
            direction = "stable"

        # Determine if concerning based on metric type
        is_concerning = self._is_concerning_trend(metric_name, direction, last_value, velocity)

        # Calculate confidence
        confidence = self._calculate_confidence(sorted_data)

        return {
            "metric": metric_name,
            "trend": direction,
            "direction": direction,
            "velocity": round(velocity, 3),
            "current_value": round(last_value, 2),
            "previous_value": round(first_value, 2),
            "change": round(last_value - first_value, 2),
            "is_concerning": is_concerning,
            "confidence": confidence,
            "data_points": len(sorted_data),
        }

    def detect_coverage_trend(
        self, coverage_data: List[Dict[str, Any]], threshold: float = 50.0
    ) -> Dict[str, Any]:
        """
        Detect coverage trend with specific thresholds.

        Args:
            coverage_data: List of coverage data points
            threshold: Minimum acceptable coverage percentage

        Returns:
            Trend analysis for coverage
        """
        trend = self.detect_trends(coverage_data, "test_coverage", days=30)

        # Coverage-specific concern logic
        current_coverage = trend.get("current_value", 0)
        if trend["direction"] == "decreasing" and current_coverage < threshold:
            trend["is_concerning"] = True
            trend["severity"] = "high" if current_coverage < threshold * 0.7 else "medium"
        elif current_coverage < threshold:
            trend["is_concerning"] = True
            trend["severity"] = "medium"
        else:
            trend["severity"] = "low"

        return trend

    def detect_bug_rate_trend(
        self, bug_data: List[Dict[str, Any]], threshold: float = 5.0
    ) -> Dict[str, Any]:
        """
        Detect bug rate trend.

        Args:
            bug_data: List of bug count data points
            threshold: Maximum acceptable bugs per period

        Returns:
            Trend analysis for bug rate
        """
        trend = self.detect_trends(bug_data, "bug_rate", days=30)

        # Bug rate-specific concern logic
        current_rate = trend.get("current_value", 0)
        if trend["direction"] == "increasing" and current_rate > threshold:
            trend["is_concerning"] = True
            trend["severity"] = "high" if current_rate > threshold * 2 else "medium"
        elif current_rate > threshold:
            trend["is_concerning"] = True
            trend["severity"] = "medium"
        else:
            trend["severity"] = "low"

        return trend

    def detect_health_trend(
        self, health_data: List[Dict[str, Any]], threshold: float = 50.0
    ) -> Dict[str, Any]:
        """
        Detect project health trend.

        Args:
            health_data: List of health score data points
            threshold: Minimum acceptable health score

        Returns:
            Trend analysis for health
        """
        trend = self.detect_trends(health_data, "project_health", days=30)

        # Health-specific concern logic
        current_health = trend.get("current_value", 0)
        if trend["direction"] == "decreasing" and current_health < threshold:
            trend["is_concerning"] = True
            trend["severity"] = "high" if current_health < threshold * 0.7 else "medium"
        elif current_health < threshold:
            trend["is_concerning"] = True
            trend["severity"] = "medium"
        else:
            trend["severity"] = "low"

        return trend

    def _calculate_time_span(self, data: List[Dict[str, Any]]) -> float:
        """Calculate time span in days."""
        if len(data) < 2:
            return 1.0

        first_time = self._parse_timestamp(data[0].get("timestamp", ""))
        last_time = self._parse_timestamp(data[-1].get("timestamp", ""))

        if first_time and last_time:
            delta = last_time - first_time
            return max(delta.days, 1.0)

        return float(len(data))  # Fallback: assume 1 day per data point

    def _parse_timestamp(self, timestamp: str) -> Optional[datetime]:
        """Parse timestamp string to datetime."""
        if not timestamp:
            return None

        try:
            # Try ISO format
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception:
            try:
                # Try common formats
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

    def _is_concerning_trend(
        self, metric_name: str, direction: str, current_value: float, velocity: float
    ) -> bool:
        """Determine if a trend is concerning based on metric type."""
        # For metrics where decreasing is bad
        bad_directions = {
            "test_coverage": "decreasing",
            "project_health": "decreasing",
            "code_quality": "decreasing",
        }

        # For metrics where increasing is bad
        bad_increasing = {
            "bug_rate": True,
            "error_rate": True,
            "technical_debt": True,
        }

        if metric_name in bad_directions:
            return direction == bad_directions[metric_name] and abs(velocity) > 0.1
        elif metric_name in bad_increasing:
            return direction == "increasing" and abs(velocity) > 0.1

        return False

    def _calculate_confidence(self, data: List[Dict[str, Any]]) -> float:
        """Calculate confidence in trend based on data quality."""
        if len(data) < 3:
            return 0.3  # Low confidence with few data points

        # More data points = higher confidence
        data_confidence = min(len(data) / 10.0, 1.0)

        # Check for consistency (variance)
        values = [d.get("value", 0) for d in data]
        if len(values) > 1:
            avg = sum(values) / len(values)
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            consistency = 1.0 / (1.0 + variance)  # Lower variance = higher consistency
        else:
            consistency = 0.5

        # Combined confidence
        return round((data_confidence * 0.6 + consistency * 0.4), 2)
