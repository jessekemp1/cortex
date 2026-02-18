"""
Process alert generator extending Layer 3 Alert System.
"""

import subprocess
from typing import Any, Dict, List, Optional

from .analyzer import ProcessAnalyzer
from .collector import ProcessCollector
from .models import Anomaly, WasteItem
from .optimizer import ResourceOptimizer
from .tracker import ProcessTracker

# Import from existing monitoring system
try:
    from ..monitoring.alert_generator import Alert, AlertSeverity
    from ..monitoring.alert_generator import AlertType as BaseAlertType
except ImportError:
    # Fallback if imports don't work
    from dataclasses import dataclass, field
    from datetime import datetime
    from enum import Enum

    class AlertSeverity(Enum):
        CRITICAL = "critical"
        WARNING = "warning"
        INFO = "info"

    class BaseAlertType(Enum):
        DEGRADATION = "degradation"
        ACTIVITY = "activity"
        CRITICAL_FILE = "critical_file"

    @dataclass
    class Alert:
        alert_type: "AlertType"
        severity: AlertSeverity
        title: str
        message: str
        metric_type: str
        metadata: dict = field(default_factory=dict)
        created_at: datetime = field(default_factory=datetime.now)
        project: str = ""


class ProcessAlertType:
    """Extended alert types for process monitoring."""

    HIGH_CPU_SUSTAINED = "high_cpu_sustained"
    MEMORY_LEAK = "memory_leak"
    ZOMBIE_PROCESS = "zombie_process"
    SERVICE_DOWN = "service_down"
    IDLE_WASTE = "idle_waste"
    ANOMALY = "anomaly"
    RESOURCE_CAPACITY = "resource_capacity"


class ProcessAlertGenerator:
    """Generates alerts for process monitoring anomalies and waste."""

    def __init__(
        self,
        collector: Optional[ProcessCollector] = None,
        tracker: Optional[ProcessTracker] = None,
        analyzer: Optional[ProcessAnalyzer] = None,
        optimizer: Optional[ResourceOptimizer] = None,
    ):
        """
        Initialize the alert generator.

        Args:
            collector: ProcessCollector instance
            tracker: ProcessTracker instance
            analyzer: ProcessAnalyzer instance
            optimizer: ResourceOptimizer instance
        """
        self.collector = collector or ProcessCollector()
        self.tracker = tracker or ProcessTracker()
        self.analyzer = analyzer or ProcessAnalyzer(tracker=self.tracker, collector=self.collector)
        self.optimizer = optimizer or ResourceOptimizer(
            collector=self.collector, tracker=self.tracker, analyzer=self.analyzer
        )

    def generate_alerts(self, hours: int = 24) -> List[Alert]:
        """
        Generate all process-related alerts.

        Args:
            hours: Number of hours to look back for patterns

        Returns:
            List of Alert objects sorted by severity
        """
        alerts = []

        # Get current resource metrics
        current_metric = self.collector.get_resource_summary()

        # 1. Anomaly-based alerts
        anomalies = self.analyzer.detect_anomalies(current_metric)
        for anomaly in anomalies:
            alert = self._anomaly_to_alert(anomaly)
            if alert:
                alerts.append(alert)

        # 2. Waste-based alerts
        waste_items = self.optimizer.detect_waste()
        for waste in waste_items:
            alert = self._waste_to_alert(waste)
            if alert:
                alerts.append(alert)

        # 3. Resource capacity alerts
        if current_metric.memory_usage_percent > 90:
            alerts.append(
                Alert(
                    alert_type=ProcessAlertType.RESOURCE_CAPACITY,
                    severity=AlertSeverity.CRITICAL,
                    title="Critical memory usage",
                    message=f"Memory usage at {current_metric.memory_usage_percent:.1f}%",
                    metric_type="memory",
                    metadata={
                        "memory_usage_percent": current_metric.memory_usage_percent,
                        "available_mb": current_metric.available_memory_mb,
                    },
                )
            )
        elif current_metric.memory_usage_percent > 80:
            alerts.append(
                Alert(
                    alert_type=ProcessAlertType.RESOURCE_CAPACITY,
                    severity=AlertSeverity.WARNING,
                    title="High memory usage",
                    message=f"Memory usage at {current_metric.memory_usage_percent:.1f}%",
                    metric_type="memory",
                    metadata={
                        "memory_usage_percent": current_metric.memory_usage_percent,
                        "available_mb": current_metric.available_memory_mb,
                    },
                )
            )

        if current_metric.total_cpu_percent > 90:
            alerts.append(
                Alert(
                    alert_type=ProcessAlertType.HIGH_CPU_SUSTAINED,
                    severity=AlertSeverity.CRITICAL,
                    title="Critical CPU usage",
                    message=f"CPU usage at {current_metric.total_cpu_percent:.1f}%",
                    metric_type="cpu",
                    metadata={"cpu_percent": current_metric.total_cpu_percent},
                )
            )
        elif current_metric.total_cpu_percent > 80:
            alerts.append(
                Alert(
                    alert_type=ProcessAlertType.HIGH_CPU_SUSTAINED,
                    severity=AlertSeverity.WARNING,
                    title="High CPU usage",
                    message=f"CPU usage at {current_metric.total_cpu_percent:.1f}%",
                    metric_type="cpu",
                    metadata={"cpu_percent": current_metric.total_cpu_percent},
                )
            )

        # 4. AI tool health alerts
        ai_insights = self.analyzer.get_ai_tool_insights(hours=hours)
        for insight in ai_insights:
            if insight.idle_hours > 3.0 and insight.avg_memory > 500:
                alerts.append(
                    Alert(
                        alert_type=ProcessAlertType.IDLE_WASTE,
                        severity=AlertSeverity.INFO,
                        title=f"{insight.tool_name} idle",
                        message=f"Idle for {insight.idle_hours:.1f}h, using {insight.avg_memory:.0f}MB",
                        metric_type="ai_tool",
                        metadata={
                            "tool_name": insight.tool_name,
                            "idle_hours": insight.idle_hours,
                            "memory_mb": insight.avg_memory,
                        },
                    )
                )

        # Sort by severity
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.INFO: 2,
        }
        return sorted(alerts, key=lambda a: severity_order.get(a.severity, 3))

    def _anomaly_to_alert(self, anomaly: Anomaly) -> Optional[Alert]:
        """
        Convert an Anomaly to an Alert.

        Args:
            anomaly: Anomaly object

        Returns:
            Alert object or None
        """
        severity_map = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "WARNING": AlertSeverity.WARNING,
            "INFO": AlertSeverity.INFO,
        }

        return Alert(
            alert_type=anomaly.anomaly_type.value,
            severity=severity_map.get(anomaly.severity, AlertSeverity.INFO),
            title=f"{anomaly.process_name}: {anomaly.anomaly_type.value.replace('_', ' ').title()}",
            message=anomaly.description,
            metric_type="process",
            metadata=anomaly.metadata,
        )

    def _waste_to_alert(self, waste: WasteItem) -> Optional[Alert]:
        """
        Convert a WasteItem to an Alert.

        Args:
            waste: WasteItem object

        Returns:
            Alert object or None
        """
        # Determine severity based on waste type and cost
        if waste.auto_actionable:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        return Alert(
            alert_type=ProcessAlertType.IDLE_WASTE,
            severity=severity,
            title=f"Resource waste: {waste.process_name}",
            message=f"{waste.recommendation} ({waste.resource_cost})",
            metric_type="waste",
            metadata={
                "waste_type": waste.waste_type.value,
                "auto_actionable": waste.auto_actionable,
                **waste.metadata,
            },
        )

    def send_macos_notification(self, alert: Alert):
        """
        Send macOS notification for critical/warning alerts.

        Args:
            alert: Alert to send
        """
        if alert.severity not in (AlertSeverity.CRITICAL, AlertSeverity.WARNING):
            return

        try:
            # Use osascript to send notification
            title = f"Cortex: {alert.severity.value.upper()}"
            subtitle = alert.title
            message = alert.message

            script = f"""
                display notification "{message}" with title "{title}" subtitle "{subtitle}"
            """

            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        except Exception:
            # Fail silently - notifications are best-effort
            pass

    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of alerts.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with alert summary
        """
        alerts = self.generate_alerts(hours=hours)

        by_severity = {}
        for alert in alerts:
            severity = alert.severity.value
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(alert)

        return {
            "total_alerts": len(alerts),
            "critical": len(by_severity.get("critical", [])),
            "warning": len(by_severity.get("warning", [])),
            "info": len(by_severity.get("info", [])),
            "by_severity": {
                severity: [a.title for a in alerts_list]
                for severity, alerts_list in by_severity.items()
            },
        }
