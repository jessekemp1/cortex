"""
Alert Generator for Layer 3: Warning System

Generates alerts based on trend analysis and project health metrics.
"""

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .trend_analyzer import AlertLevel


class AlertSeverity(Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(Enum):
    """Types of alerts."""

    DEGRADATION = "degradation"
    ACTIVITY = "activity"
    CRITICAL_FILE = "critical_file"


@dataclass
class Alert:
    """Represents a single alert."""

    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    metric_type: str
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    project: str = ""

    def format_compact(self) -> str:
        """Format alert for context injection (single line)."""
        icon = self._get_icon()
        return f"{icon} {self.title}"

    def format_detailed(self) -> str:
        """Format alert for CLI display (multi-line)."""
        icon = self._get_icon()
        severity_label = self.severity.value.upper()
        lines = [
            f"{icon} [{severity_label}] {self.title}",
            f"   {self.message}",
        ]
        if self.metadata:
            details = self._format_metadata()
            if details:
                lines.append(f"   Details: {details}")
        lines.append(f"   Time: {self.created_at.strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(lines)

    def _get_icon(self) -> str:
        """Get emoji icon based on severity."""
        icons = {
            AlertSeverity.CRITICAL: "🔴",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.INFO: "ℹ️",
        }
        return icons.get(self.severity, "•")

    def _format_metadata(self) -> str:
        """Format metadata for display."""
        parts = []
        if "delta" in self.metadata:
            delta = self.metadata["delta"]
            sign = "+" if delta > 0 else ""
            parts.append(f"change: {sign}{delta:.1f}%")
        if "previous" in self.metadata and "current" in self.metadata:
            parts.append(f"{self.metadata['previous']:.1f}% → {self.metadata['current']:.1f}%")
        if "days_inactive" in self.metadata:
            parts.append(f"inactive: {self.metadata['days_inactive']} days")
        if "avg_commits" in self.metadata:
            parts.append(f"avg: {self.metadata['avg_commits']:.1f} commits/day")
        if "file" in self.metadata:
            parts.append(f"file: {self.metadata['file']}")
        if "hours_uncommitted" in self.metadata:
            hours = self.metadata["hours_uncommitted"]
            if hours >= 24:
                parts.append(f"uncommitted: {hours // 24} days")
            else:
                parts.append(f"uncommitted: {hours} hours")
        return ", ".join(parts)


# Alert rule thresholds
class AlertRules:
    """Configuration for alert thresholds."""

    # Coverage degradation thresholds
    COVERAGE_CRITICAL_DROP = -5.0  # Drop > 5% is critical
    COVERAGE_WARNING_DROP = -2.0  # Drop 2-5% is warning

    # Violation thresholds
    VIOLATIONS_CRITICAL_INCREASE = 15  # 15+ new violations is critical
    VIOLATIONS_WARNING_INCREASE = 10  # 10+ new violations is warning

    # Activity thresholds
    ACTIVE_PROJECT_MIN_COMMITS = 3  # 3+ commits/week = active
    DORMANT_DAYS_WARNING = 3  # 3+ days without commits
    DORMANT_DAYS_CRITICAL = 7  # 7+ days without commits

    # Critical file thresholds
    CRITICAL_FILES = {"main.py", "config.py", "app.py", "settings.py", "__init__.py"}
    UNCOMMITTED_HOURS_WARNING = 24  # 24+ hours uncommitted
    UNCOMMITTED_HOURS_CRITICAL = 48  # 48+ hours uncommitted


class AlertGenerator:
    """Generates alerts based on trend analysis and project metrics."""

    def __init__(self, trend_analyzer=None):
        """
        Initialize AlertGenerator.

        Args:
            trend_analyzer: TrendAnalyzer instance for accessing trends
        """
        self.trend_analyzer = trend_analyzer
        self.rules = AlertRules()

    def generate_alerts(self, project: str, days: int = 7) -> list[Alert]:
        """
        Generate all alerts for a project.

        Args:
            project: Project name
            days: Number of days to analyze

        Returns:
            List of Alert objects, sorted by severity
        """
        alerts = []

        # Collect all alert types
        alerts.extend(self.generate_degradation_alerts(project, days))
        alerts.extend(self.generate_activity_alerts(project, days))
        alerts.extend(self.generate_critical_file_alerts(project))

        # Sort by severity (critical first)
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.INFO: 2,
        }
        alerts.sort(key=lambda a: severity_order.get(a.severity, 99))

        return alerts

    def generate_degradation_alerts(self, project: str, days: int = 7) -> list[Alert]:
        """
        Generate alerts for metric degradation (coverage, violations).

        Args:
            project: Project name
            days: Number of days to analyze

        Returns:
            List of degradation alerts
        """
        alerts = []

        if not self.trend_analyzer:
            return alerts

        # Check coverage trend
        coverage_trend = self.trend_analyzer.analyze_coverage_trend(project, days)
        if coverage_trend and coverage_trend.alert_level != AlertLevel.NONE:
            alert = self._create_coverage_alert(project, coverage_trend)
            if alert:
                alerts.append(alert)

        # Check violations trend
        violations_trend = self.trend_analyzer.analyze_violation_trend(project, days)
        if violations_trend and violations_trend.alert_level != AlertLevel.NONE:
            alert = self._create_violations_alert(project, violations_trend)
            if alert:
                alerts.append(alert)

        return alerts

    def _create_coverage_alert(self, project: str, trend) -> Optional[Alert]:
        """Create alert from coverage trend."""
        if trend.delta >= self.rules.COVERAGE_WARNING_DROP:
            return None

        severity = (
            AlertSeverity.CRITICAL
            if trend.delta <= self.rules.COVERAGE_CRITICAL_DROP
            else AlertSeverity.WARNING
        )

        delta_str = f"{abs(trend.delta):.1f}%"

        return Alert(
            alert_type=AlertType.DEGRADATION,
            severity=severity,
            title=f"{project}: Test coverage dropped {delta_str}",
            message=f"Test coverage decreased from {trend.start_value:.1f}% to {trend.end_value:.1f}% over the last {self._calculate_days(trend)} days.",
            metric_type="coverage",
            metadata={
                "delta": trend.delta,
                "previous": trend.start_value,
                "current": trend.end_value,
                "rate": trend.rate,
                "direction": trend.direction.value,
            },
            project=project,
        )

    def _create_violations_alert(self, project: str, trend) -> Optional[Alert]:
        """Create alert from violations trend."""
        if trend.delta <= self.rules.VIOLATIONS_WARNING_INCREASE:
            return None

        severity = (
            AlertSeverity.CRITICAL
            if trend.delta >= self.rules.VIOLATIONS_CRITICAL_INCREASE
            else AlertSeverity.WARNING
        )

        return Alert(
            alert_type=AlertType.DEGRADATION,
            severity=severity,
            title=f"{project}: Lint violations increased by {int(trend.delta)}",
            message=f"Lint violations increased from {int(trend.start_value)} to {int(trend.end_value)} over the last {self._calculate_days(trend)} days.",
            metric_type="violations",
            metadata={
                "delta": trend.delta,
                "previous": trend.start_value,
                "current": trend.end_value,
                "direction": trend.direction.value,
            },
            project=project,
        )

    def generate_activity_alerts(self, project: str, days: int = 7) -> list[Alert]:
        """
        Generate alerts for project activity (dormant projects).

        Args:
            project: Project name
            days: Number of days to analyze

        Returns:
            List of activity alerts
        """
        alerts = []

        if not self.trend_analyzer:
            return alerts

        activity = self.trend_analyzer.analyze_activity_trend(project, days)
        if not activity:
            return alerts

        # Calculate activity metrics from Trend fields
        now = datetime.now()
        days_since_last_commit = int((now - activity.end_timestamp).total_seconds() / 86400)
        trend_days = self._calculate_days(activity)
        avg_commits_per_day = activity.end_value / trend_days if trend_days > 0 else 0
        was_active = (
            avg_commits_per_day >= self.rules.ACTIVE_PROJECT_MIN_COMMITS / 7
        )  # Convert weekly to daily

        # Check if active project is going dormant
        if was_active and days_since_last_commit >= self.rules.DORMANT_DAYS_WARNING:
            severity = (
                AlertSeverity.CRITICAL
                if days_since_last_commit >= self.rules.DORMANT_DAYS_CRITICAL
                else AlertSeverity.WARNING
            )

            alerts.append(
                Alert(
                    alert_type=AlertType.ACTIVITY,
                    severity=severity,
                    title=f"{project}: No commits in {days_since_last_commit} days",
                    message=f"Previously active project (avg {avg_commits_per_day:.1f} commits/day) has been dormant for {days_since_last_commit} days.",
                    metric_type="commits",
                    metadata={
                        "days_inactive": days_since_last_commit,
                        "avg_commits": avg_commits_per_day,
                        "was_active": was_active,
                    },
                    project=project,
                )
            )

        return alerts

    def generate_critical_file_alerts(self, project: str) -> list[Alert]:
        """
        Generate alerts for critical files with uncommitted changes.

        Args:
            project: Project name

        Returns:
            List of critical file alerts
        """
        alerts = []

        # Get uncommitted files and their modification times
        uncommitted_files = self._get_uncommitted_critical_files(project)

        for file_info in uncommitted_files:
            file_name = file_info["file"]
            hours_uncommitted = file_info["hours"]

            if hours_uncommitted < self.rules.UNCOMMITTED_HOURS_WARNING:
                continue

            severity = (
                AlertSeverity.CRITICAL
                if hours_uncommitted >= self.rules.UNCOMMITTED_HOURS_CRITICAL
                else AlertSeverity.WARNING
            )

            time_str = self._format_time_duration(hours_uncommitted)

            alerts.append(
                Alert(
                    alert_type=AlertType.CRITICAL_FILE,
                    severity=severity,
                    title=f"{project}: {file_name} uncommitted for {time_str}",
                    message=f"Critical file '{file_name}' has had uncommitted changes for {time_str}. Consider committing or stashing changes.",
                    metric_type="files",
                    metadata={
                        "file": file_name,
                        "hours_uncommitted": hours_uncommitted,
                    },
                    project=project,
                )
            )

        return alerts

    def _get_uncommitted_critical_files(self, project: str) -> list[dict]:
        """
        Get list of critical files with uncommitted changes.

        Returns list of dicts with 'file' and 'hours' keys.
        """
        result = []

        # Try to find project directory
        project_dir = self._find_project_dir(project)
        if not project_dir:
            return result

        try:
            # Get modified files from git status
            git_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if git_status.returncode != 0:
                return result

            # Parse git status output
            for line in git_status.stdout.strip().split("\n"):
                if not line:
                    continue

                # Extract filename (format: "XY filename" or "XY old -> new")
                parts = line.split()
                if len(parts) < 2:
                    continue

                file_path = parts[-1]
                file_name = os.path.basename(file_path)

                # Check if it's a critical file
                if file_name in self.rules.CRITICAL_FILES:
                    # Get file modification time
                    full_path = os.path.join(project_dir, file_path)
                    if os.path.exists(full_path):
                        mtime = os.path.getmtime(full_path)
                        hours_ago = (datetime.now().timestamp() - mtime) / 3600
                        result.append(
                            {
                                "file": file_name,
                                "hours": int(hours_ago),
                                "path": file_path,
                            }
                        )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass

        return result

    def _find_project_dir(self, project: str) -> Optional[str]:
        """Find the directory for a project."""
        # Common project locations
        search_paths = [
            os.path.expanduser(f"~/Projects/{project}"),
            os.path.expanduser(f"~/Dev/{project}"),
            os.path.expanduser(f"~/{project}"),
            os.path.expanduser(f"~/code/{project}"),
            os.path.expanduser(f"~/dev/{project}"),
        ]

        for path in search_paths:
            if os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git")):
                return path

        return None

    def _calculate_days(self, trend) -> int:
        """Calculate number of days from trend timestamps."""
        if trend.start_timestamp and trend.end_timestamp:
            delta = trend.end_timestamp - trend.start_timestamp
            return max(1, int(delta.total_seconds() / 86400))
        return 7

    def _format_time_duration(self, hours: int) -> str:
        """Format hours into human-readable duration."""
        if hours >= 48:
            days = hours // 24
            return f"{days} days"
        elif hours >= 24:
            return "1 day"
        else:
            return f"{hours} hours"

    def get_most_critical_alert(self, project: str, days: int = 7) -> Optional[Alert]:
        """
        Get the single most critical alert for a project.

        Useful for context injection where space is limited.

        Args:
            project: Project name
            days: Number of days to analyze

        Returns:
            Most critical Alert or None
        """
        alerts = self.generate_alerts(project, days)
        return alerts[0] if alerts else None

    def format_alerts_summary(self, alerts: list[Alert]) -> str:
        """
        Format multiple alerts into a summary string.

        Args:
            alerts: List of alerts

        Returns:
            Formatted summary string
        """
        if not alerts:
            return "No active alerts"

        critical = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
        warning = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)
        info = sum(1 for a in alerts if a.severity == AlertSeverity.INFO)

        parts = []
        if critical:
            parts.append(f"🔴 {critical} critical")
        if warning:
            parts.append(f"⚠️ {warning} warning")
        if info:
            parts.append(f"ℹ️ {info} info")

        return " | ".join(parts)

    def format_alerts_for_cli(self, alerts: list[Alert]) -> str:
        """
        Format all alerts for CLI display.

        Args:
            alerts: List of alerts

        Returns:
            Formatted string for CLI output
        """
        if not alerts:
            return "✅ No active alerts"

        lines = [
            f"Found {len(alerts)} alert(s):",
            "",
        ]

        for alert in alerts:
            lines.append(alert.format_detailed())
            lines.append("")

        return "\n".join(lines)

    def format_alerts_for_context(self, alerts: list[Alert], max_alerts: int = 2) -> str:
        """
        Format alerts for context injection (compact).

        Args:
            alerts: List of alerts
            max_alerts: Maximum number of alerts to include

        Returns:
            Compact formatted string
        """
        if not alerts:
            return ""

        # Take only the most critical alerts
        top_alerts = alerts[:max_alerts]

        return " | ".join(a.format_compact() for a in top_alerts)
