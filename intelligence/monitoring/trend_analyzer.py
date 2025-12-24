"""
Trend Analyzer for Cortex Intelligence Stack Layer 3.

Analyzes metric trends over time to detect degradation, improvements,
and anomalies in project health metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .metric_tracker import MetricTracker, MetricRecord


class TrendDirection(Enum):
    """Direction of a metric trend."""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


class AlertLevel(Enum):
    """Alert severity level."""
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Trend:
    """
    Represents a trend analysis result for a metric.
    
    Attributes:
        direction: Whether the metric is improving, stable, or degrading
        delta: Absolute change from start to end value
        rate: Change per day (slope from linear regression)
        alert_level: Severity of any alert triggered
        start_value: First recorded value in the period
        end_value: Last recorded value in the period
        start_timestamp: Timestamp of first value
        end_timestamp: Timestamp of last value
        data_points: Number of data points analyzed
        confidence: Confidence score (0-1) based on data quality
        message: Human-readable description of the trend
    """
    direction: TrendDirection
    delta: float
    rate: float
    alert_level: AlertLevel
    start_value: float
    end_value: float
    start_timestamp: datetime
    end_timestamp: datetime
    data_points: int = 0
    confidence: float = 0.0
    message: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "direction": self.direction.value,
            "delta": round(self.delta, 2),
            "rate": round(self.rate, 4),
            "alert_level": self.alert_level.value,
            "start_value": round(self.start_value, 2),
            "end_value": round(self.end_value, 2),
            "start_timestamp": self.start_timestamp.isoformat(),
            "end_timestamp": self.end_timestamp.isoformat(),
            "data_points": self.data_points,
            "confidence": round(self.confidence, 2),
            "message": self.message
        }


@dataclass
class Anomaly:
    """
    Represents an anomalous data point in a metric series.
    
    Attributes:
        timestamp: When the anomaly occurred
        value: The anomalous value
        expected_value: What the value should have been (based on trend)
        deviation: How many standard deviations from the mean
        metric_type: Type of metric (coverage, violations, etc.)
        severity: How severe the anomaly is
        message: Human-readable description
    """
    timestamp: datetime
    value: float
    expected_value: float
    deviation: float
    metric_type: str
    severity: AlertLevel
    message: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": round(self.value, 2),
            "expected_value": round(self.expected_value, 2),
            "deviation": round(self.deviation, 2),
            "metric_type": self.metric_type,
            "severity": self.severity.value,
            "message": self.message
        }


def linear_regression(x_values: List[float], y_values: List[float]) -> Tuple[float, float]:
    """
    Perform simple linear regression without external dependencies.
    
    Uses the least squares method to find the best-fit line y = mx + b.
    
    Args:
        x_values: Independent variable values (e.g., days since start)
        y_values: Dependent variable values (e.g., coverage percentages)
    
    Returns:
        Tuple of (slope, intercept)
    
    Raises:
        ValueError: If input lists are empty or have different lengths
    """
    n = len(x_values)
    if n == 0:
        raise ValueError("Cannot perform regression on empty data")
    if n != len(y_values):
        raise ValueError("x and y must have the same length")
    if n == 1:
        return (0.0, y_values[0])
    
    # Calculate means
    x_mean = sum(x_values) / n
    y_mean = sum(y_values) / n
    
    # Calculate slope (m) and intercept (b)
    # m = Σ((xi - x_mean)(yi - y_mean)) / Σ((xi - x_mean)²)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    
    if denominator == 0:
        # All x values are the same, no slope
        return (0.0, y_mean)
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    return (slope, intercept)


def calculate_mean(values: List[float]) -> float:
    """Calculate the arithmetic mean of a list of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def calculate_std_dev(values: List[float], mean: Optional[float] = None) -> float:
    """
    Calculate the standard deviation of a list of values.
    
    Uses population standard deviation (N divisor, not N-1).
    
    Args:
        values: List of numeric values
        mean: Pre-calculated mean (optional, will calculate if not provided)
    
    Returns:
        Standard deviation
    """
    if not values or len(values) < 2:
        return 0.0
    
    if mean is None:
        mean = calculate_mean(values)
    
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


def calculate_r_squared(
    x_values: List[float],
    y_values: List[float],
    slope: float,
    intercept: float
) -> float:
    """
    Calculate R-squared (coefficient of determination) for a linear regression.
    
    R² indicates how well the regression line fits the data (0-1).
    
    Args:
        x_values: Independent variable values
        y_values: Dependent variable values
        slope: Slope from linear regression
        intercept: Intercept from linear regression
    
    Returns:
        R-squared value between 0 and 1
    """
    if len(y_values) < 2:
        return 0.0
    
    y_mean = calculate_mean(y_values)
    
    # Total sum of squares
    ss_tot = sum((y - y_mean) ** 2 for y in y_values)
    
    if ss_tot == 0:
        return 1.0  # Perfect fit (all y values are the same)
    
    # Residual sum of squares
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
    
    r_squared = 1 - (ss_res / ss_tot)
    return max(0.0, min(1.0, r_squared))  # Clamp to [0, 1]


class TrendAnalyzer:
    """
    Analyzes metric trends to detect degradation and anomalies.
    
    Uses statistical analysis to identify concerning patterns in
    project health metrics over time.
    """
    
    # Alert thresholds for coverage (percentage points)
    COVERAGE_CRITICAL_DROP = -5.0
    COVERAGE_WARNING_DROP = -2.0
    
    # Alert thresholds for violations (absolute count)
    VIOLATIONS_CRITICAL_INCREASE = 10
    VIOLATIONS_WARNING_INCREASE = 5
    
    # Alert thresholds for activity (days of inactivity)
    ACTIVITY_CRITICAL_DAYS = 3
    ACTIVITY_WARNING_DAYS = 2
    
    # Minimum commits per week to consider a project "active"
    ACTIVE_PROJECT_THRESHOLD = 3
    
    # Anomaly detection threshold (standard deviations)
    ANOMALY_THRESHOLD = 2.0
    SEVERE_ANOMALY_THRESHOLD = 3.0
    
    def __init__(self, metric_tracker: "MetricTracker"):
        """
        Initialize the trend analyzer.
        
        Args:
            metric_tracker: MetricTracker instance for retrieving historical data
        """
        self.metric_tracker = metric_tracker
    
    def _get_metrics_for_period(
        self,
        project: str,
        metric_type: str,
        days: int
    ) -> List["MetricRecord"]:
        """
        Retrieve metrics for a project over a time period.

        Args:
            project: Project name
            metric_type: Type of metric to retrieve
            days: Number of days to look back

        Returns:
            List of MetricRecord objects, sorted by timestamp
        """
        # Use the days parameter directly - MetricTracker API uses days, not start_time/end_time
        return self.metric_tracker.get_metrics(
            project=project,
            metric_type=metric_type,
            days=days
        )
    
    def _prepare_regression_data(
        self,
        metrics: List["MetricRecord"]
    ) -> Tuple[List[float], List[float], datetime]:
        """
        Prepare metric data for linear regression.
        
        Converts timestamps to days since first measurement.
        
        Args:
            metrics: List of MetricRecord objects
        
        Returns:
            Tuple of (x_values, y_values, base_timestamp)
        """
        if not metrics:
            return [], [], datetime.now()
        
        base_time = metrics[0].timestamp
        x_values = []
        y_values = []
        
        for metric in metrics:
            # Convert timestamp to days since first measurement
            delta = metric.timestamp - base_time
            days = delta.total_seconds() / (24 * 3600)
            x_values.append(days)
            # Fix: Use metric_value instead of value (Metric class uses metric_value attribute)
            y_values.append(metric.metric_value)
        
        return x_values, y_values, base_time
    
    def _determine_direction(self, slope: float, delta: float) -> TrendDirection:
        """
        Determine trend direction based on slope and delta.
        
        Args:
            slope: Rate of change per day
            delta: Total change over period
        
        Returns:
            TrendDirection enum value
        """
        # Use a small threshold to account for noise
        threshold = 0.1
        
        if abs(delta) < threshold and abs(slope) < 0.01:
            return TrendDirection.STABLE
        elif slope > 0 or delta > threshold:
            return TrendDirection.IMPROVING
        else:
            return TrendDirection.DEGRADING
    
    def _calculate_confidence(
        self,
        data_points: int,
        r_squared: float,
        days: int
    ) -> float:
        """
        Calculate confidence score for a trend analysis.
        
        Based on:
        - Number of data points (more is better)
        - R-squared value (higher means better fit)
        - Data coverage (points spread across the period)
        
        Args:
            data_points: Number of metric records
            r_squared: R-squared from regression
            days: Period analyzed
        
        Returns:
            Confidence score between 0 and 1
        """
        if data_points < 2:
            return 0.0
        
        # Factor 1: Data point density (ideal: at least 1 per day)
        density_score = min(1.0, data_points / max(days, 1))
        
        # Factor 2: Minimum data points (need at least 3 for meaningful trend)
        min_points_score = min(1.0, (data_points - 1) / 2)
        
        # Factor 3: R-squared (how well the line fits)
        fit_score = r_squared
        
        # Weighted average
        confidence = (density_score * 0.3 + min_points_score * 0.3 + fit_score * 0.4)
        
        return round(confidence, 2)
    
    def analyze_coverage_trend(self, project: str, days: int = 7) -> Trend:
        """
        Analyze test coverage trend for a project.
        
        Detects if coverage is improving, stable, or degrading over time.
        Generates alerts for significant drops.
        
        Args:
            project: Project name to analyze
            days: Number of days to analyze (default: 7)
        
        Returns:
            Trend object with analysis results
        """
        metrics = self._get_metrics_for_period(project, "coverage", days)
        
        if not metrics:
            return Trend(
                direction=TrendDirection.STABLE,
                delta=0.0,
                rate=0.0,
                alert_level=AlertLevel.NONE,
                start_value=0.0,
                end_value=0.0,
                start_timestamp=datetime.now(),
                end_timestamp=datetime.now(),
                data_points=0,
                confidence=0.0,
                message="No coverage data available"
            )
        
        x_values, y_values, base_time = self._prepare_regression_data(metrics)
        
        if len(metrics) == 1:
            return Trend(
                direction=TrendDirection.STABLE,
                delta=0.0,
                rate=0.0,
                alert_level=AlertLevel.NONE,
                start_value=metrics[0].metric_value,
                end_value=metrics[0].metric_value,
                start_timestamp=metrics[0].timestamp,
                end_timestamp=metrics[0].timestamp,
                data_points=1,
                confidence=0.0,
                message="Only one data point available"
            )
        
        slope, intercept = linear_regression(x_values, y_values)
        r_squared = calculate_r_squared(x_values, y_values, slope, intercept)
        
        start_value = metrics[0].metric_value
        end_value = metrics[-1].metric_value
        delta = end_value - start_value
        
        direction = self._determine_direction(slope, delta)
        
        # Determine alert level for coverage
        if delta <= self.COVERAGE_CRITICAL_DROP:
            alert_level = AlertLevel.CRITICAL
        elif delta <= self.COVERAGE_WARNING_DROP:
            alert_level = AlertLevel.WARNING
        else:
            alert_level = AlertLevel.NONE
        
        confidence = self._calculate_confidence(len(metrics), r_squared, days)
        
        # Generate message
        if alert_level == AlertLevel.CRITICAL:
            message = f"Test coverage dropped {abs(delta):.1f}% ({start_value:.1f}% → {end_value:.1f}%) in {days} days"
        elif alert_level == AlertLevel.WARNING:
            message = f"Test coverage declining: {abs(delta):.1f}% drop in {days} days"
        elif direction == TrendDirection.IMPROVING:
            message = f"Test coverage improving: +{delta:.1f}% in {days} days"
        else:
            message = f"Test coverage stable at {end_value:.1f}%"
        
        return Trend(
            direction=direction,
            delta=delta,
            rate=slope,
            alert_level=alert_level,
            start_value=start_value,
            end_value=end_value,
            start_timestamp=metrics[0].timestamp,
            end_timestamp=metrics[-1].timestamp,
            data_points=len(metrics),
            confidence=confidence,
            message=message
        )
    
    def analyze_violation_trend(self, project: str, days: int = 7) -> Trend:
        """
        Analyze lint violation trend for a project.
        
        Detects if violations are increasing, stable, or decreasing.
        Generates alerts for significant increases.
        
        Args:
            project: Project name to analyze
            days: Number of days to analyze (default: 7)
        
        Returns:
            Trend object with analysis results
        """
        metrics = self._get_metrics_for_period(project, "violations", days)
        
        if not metrics:
            return Trend(
                direction=TrendDirection.STABLE,
                delta=0.0,
                rate=0.0,
                alert_level=AlertLevel.NONE,
                start_value=0.0,
                end_value=0.0,
                start_timestamp=datetime.now(),
                end_timestamp=datetime.now(),
                data_points=0,
                confidence=0.0,
                message="No violation data available"
            )
        
        x_values, y_values, base_time = self._prepare_regression_data(metrics)
        
        if len(metrics) == 1:
            return Trend(
                direction=TrendDirection.STABLE,
                delta=0.0,
                rate=0.0,
                alert_level=AlertLevel.NONE,
                start_value=metrics[0].metric_value,
                end_value=metrics[0].metric_value,
                start_timestamp=metrics[0].timestamp,
                end_timestamp=metrics[0].timestamp,
                data_points=1,
                confidence=0.0,
                message=f"Current violations: {int(metrics[0].metric_value)}"
            )
        
        slope, intercept = linear_regression(x_values, y_values)
        r_squared = calculate_r_squared(x_values, y_values, slope, intercept)
        
        start_value = metrics[0].metric_value
        end_value = metrics[-1].metric_value
        delta = end_value - start_value
        
        # For violations, decreasing is improving
        if delta < -0.5:
            direction = TrendDirection.IMPROVING
        elif delta > 0.5:
            direction = TrendDirection.DEGRADING
        else:
            direction = TrendDirection.STABLE
        
        # Determine alert level for violations (increasing is bad)
        if delta >= self.VIOLATIONS_CRITICAL_INCREASE:
            alert_level = AlertLevel.CRITICAL
        elif delta >= self.VIOLATIONS_WARNING_INCREASE:
            alert_level = AlertLevel.WARNING
        else:
            alert_level = AlertLevel.NONE
        
        confidence = self._calculate_confidence(len(metrics), r_squared, days)
        
        # Generate message
        if alert_level == AlertLevel.CRITICAL:
            message = f"Lint violations increased by {int(delta)} ({int(start_value)} → {int(end_value)}) in {days} days"
        elif alert_level == AlertLevel.WARNING:
            message = f"Lint violations rising: +{int(delta)} in {days} days"
        elif direction == TrendDirection.IMPROVING:
            message = f"Lint violations decreasing: {int(abs(delta))} fixed in {days} days"
        else:
            message = f"Lint violations stable at {int(end_value)}"
        
        return Trend(
            direction=direction,
            delta=delta,
            rate=slope,
            alert_level=alert_level,
            start_value=start_value,
            end_value=end_value,
            start_timestamp=metrics[0].timestamp,
            end_timestamp=metrics[-1].timestamp,
            data_points=len(metrics),
            confidence=confidence,
            message=message
        )
    
    def analyze_activity_trend(self, project: str, days: int = 7) -> Trend:
        """
        Analyze commit activity trend for a project.
        
        Detects if an active project is going dormant or if activity
        is increasing/decreasing.
        
        Args:
            project: Project name to analyze
            days: Number of days to analyze (default: 7)
        
        Returns:
            Trend object with analysis results
        """
        metrics = self._get_metrics_for_period(project, "commits", days)
        
        if not metrics:
            return Trend(
                direction=TrendDirection.STABLE,
                delta=0.0,
                rate=0.0,
                alert_level=AlertLevel.NONE,
                start_value=0.0,
                end_value=0.0,
                start_timestamp=datetime.now(),
                end_timestamp=datetime.now(),
                data_points=0,
                confidence=0.0,
                message="No activity data available"
            )
        
        # Calculate total commits and daily average
        total_commits = sum(m.metric_value for m in metrics)
        daily_average = total_commits / days if days > 0 else 0
        
        # Check for recent inactivity
        now = datetime.now()
        last_activity = metrics[-1].timestamp
        days_since_activity = (now - last_activity).total_seconds() / (24 * 3600)
        
        # Determine if project was previously active
        was_active = total_commits >= self.ACTIVE_PROJECT_THRESHOLD
        
        x_values, y_values, base_time = self._prepare_regression_data(metrics)
        
        if len(metrics) >= 2:
            slope, intercept = linear_regression(x_values, y_values)
            r_squared = calculate_r_squared(x_values, y_values, slope, intercept)
        else:
            slope = 0.0
            r_squared = 0.0
        
        start_value = metrics[0].metric_value if metrics else 0.0
        end_value = metrics[-1].metric_value if metrics else 0.0
        delta = end_value - start_value
        
        # Determine direction
        if slope > 0.1:
            direction = TrendDirection.IMPROVING
        elif slope < -0.1:
            direction = TrendDirection.DEGRADING
        else:
            direction = TrendDirection.STABLE
        
        # Determine alert level based on inactivity
        if was_active and days_since_activity >= self.ACTIVITY_CRITICAL_DAYS:
            alert_level = AlertLevel.CRITICAL
        elif was_active and days_since_activity >= self.ACTIVITY_WARNING_DAYS:
            alert_level = AlertLevel.WARNING
        else:
            alert_level = AlertLevel.NONE
        
        confidence = self._calculate_confidence(len(metrics), r_squared, days)
        
        # Generate message
        if alert_level == AlertLevel.CRITICAL:
            message = f"No commits in {days_since_activity:.1f} days (was active: {daily_average:.1f} commits/day avg)"
        elif alert_level == AlertLevel.WARNING:
            message = f"Activity slowing: {days_since_activity:.1f} days since last commit"
        elif direction == TrendDirection.IMPROVING:
            message = f"Activity increasing: {daily_average:.1f} commits/day average"
        elif not was_active:
            message = f"Low activity project: {total_commits:.0f} commits in {days} days"
        else:
            message = f"Steady activity: {daily_average:.1f} commits/day average"
        
        return Trend(
            direction=direction,
            delta=delta,
            rate=slope,
            alert_level=alert_level,
            start_value=start_value,
            end_value=end_value,
            start_timestamp=metrics[0].timestamp if metrics else now,
            end_timestamp=metrics[-1].timestamp if metrics else now,
            data_points=len(metrics),
            confidence=confidence,
            message=message
        )
    
    def detect_anomalies(
        self,
        project: str,
        metric_type: str,
        days: int = 7
    ) -> List[Anomaly]:
        """
        Detect anomalous data points in a metric series.
        
        Uses statistical analysis to find values that deviate significantly
        from the expected trend.
        
        Args:
            project: Project name to analyze
            metric_type: Type of metric (coverage, violations, commits)
            days: Number of days to analyze (default: 7)
        
        Returns:
            List of Anomaly objects for detected anomalies
        """
        metrics = self._get_metrics_for_period(project, metric_type, days)
        
        if len(metrics) < 3:
            return []  # Need at least 3 points for meaningful anomaly detection

        values = [m.metric_value for m in metrics]
        mean = calculate_mean(values)
        std_dev = calculate_std_dev(values, mean)
        
        if std_dev == 0:
            return []  # No variation, no anomalies
        
        anomalies = []
        
        for metric in metrics:
            deviation = abs(metric.metric_value - mean) / std_dev
            
            if deviation >= self.ANOMALY_THRESHOLD:
                # Determine expected value (mean for simplicity)
                expected = mean
                
                # Determine severity
                if deviation >= self.SEVERE_ANOMALY_THRESHOLD:
                    severity = AlertLevel.CRITICAL
                else:
                    severity = AlertLevel.WARNING
                
                # Generate message based on metric type
                if metric_type == "coverage":
                    if metric.metric_value < mean:
                        message = f"Unusual coverage drop to {metric.metric_value:.1f}% (expected ~{expected:.1f}%)"
                    else:
                        message = f"Unusual coverage spike to {metric.metric_value:.1f}% (expected ~{expected:.1f}%)"
                elif metric_type == "violations":
                    if metric.metric_value > mean:
                        message = f"Unusual violation spike to {int(metric.metric_value)} (expected ~{int(expected)})"
                    else:
                        message = f"Unusual violation drop to {int(metric.metric_value)} (expected ~{int(expected)})"
                else:
                    message = f"Anomalous {metric_type} value: {metric.metric_value:.1f} (expected ~{expected:.1f})"
                
                anomalies.append(Anomaly(
                    timestamp=metric.timestamp,
                    value=metric.metric_value,
                    expected_value=expected,
                    deviation=deviation,
                    metric_type=metric_type,
                    severity=severity,
                    message=message
                ))
        
        # Sort by severity (critical first) then by deviation
        anomalies.sort(
            key=lambda a: (0 if a.severity == AlertLevel.CRITICAL else 1, -a.deviation)
        )
        
        return anomalies
    
    def get_all_trends(self, project: str, days: int = 7) -> dict:
        """
        Get all trend analyses for a project.
        
        Convenience method to analyze all metric types at once.
        
        Args:
            project: Project name to analyze
            days: Number of days to analyze (default: 7)
        
        Returns:
            Dictionary with trend analysis for each metric type
        """
        return {
            "coverage": self.analyze_coverage_trend(project, days),
            "violations": self.analyze_violation_trend(project, days),
            "activity": self.analyze_activity_trend(project, days)
        }
    
    def get_critical_alerts(self, project: str, days: int = 7) -> List[Trend]:
        """
        Get only critical and warning level trends for a project.
        
        Args:
            project: Project name to analyze
            days: Number of days to analyze (default: 7)
        
        Returns:
            List of Trend objects with warning or critical alert levels
        """
        all_trends = self.get_all_trends(project, days)
        
        alerts = []
        for metric_type, trend in all_trends.items():
            if trend.alert_level in (AlertLevel.WARNING, AlertLevel.CRITICAL):
                alerts.append(trend)
        
        # Sort by severity (critical first)
        alerts.sort(key=lambda t: 0 if t.alert_level == AlertLevel.CRITICAL else 1)
        
        return alerts
    
    def get_project_health_summary(self, project: str, days: int = 7) -> dict:
        """
        Generate a comprehensive health summary for a project.
        
        Combines trend analysis and anomaly detection into a single report.
        
        Args:
            project: Project name to analyze
            days: Number of days to analyze (default: 7)
        
        Returns:
            Dictionary with health summary including trends, anomalies, and overall status
        """
        trends = self.get_all_trends(project, days)
        
        # Collect anomalies for all metric types
        all_anomalies = []
        for metric_type in ["coverage", "violations", "commits"]:
            anomalies = self.detect_anomalies(project, metric_type, days)
            all_anomalies.extend(anomalies)
        
        # Determine overall health status
        critical_count = sum(
            1 for t in trends.values() if t.alert_level == AlertLevel.CRITICAL
        )
        warning_count = sum(
            1 for t in trends.values() if t.alert_level == AlertLevel.WARNING
        )
        critical_anomalies = sum(
            1 for a in all_anomalies if a.severity == AlertLevel.CRITICAL
        )
        
        if critical_count > 0 or critical_anomalies > 0:
            overall_status = "critical"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "project": project,
            "period_days": days,
            "overall_status": overall_status,
            "trends": {k: v.to_dict() for k, v in trends.items()},
            "anomalies": [a.to_dict() for a in all_anomalies],
            "summary": {
                "critical_alerts": critical_count,
                "warning_alerts": warning_count,
                "anomalies_detected": len(all_anomalies)
            }
        }