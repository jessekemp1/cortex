"""
Layer 3.5: Process Monitor Intelligence

Monitors OS processes, learns system utilization patterns, and provides
intelligence about AI tools, development workflows, and resource optimization.
"""

from .alerts import ProcessAlertGenerator, ProcessAlertType
from .analyzer import ProcessAnalyzer
from .batch_executor import BatchExecutor
from .batch_queue import BatchTask, BatchTaskQueue, TaskState
from .collector import ProcessCollector
from .daemon import BatchDaemon
from .models import (
    AIToolInsights,
    Anomaly,
    AnomalyType,
    CapacityForecast,
    DevPatterns,
    Optimization,
    ProcessCategory,
    ProcessSnapshot,
    ProcessStatus,
    ResourceMetric,
    UtilizationInsights,
    WasteItem,
    WasteType,
)
from .optimizer import ResourceOptimizer
from .scheduler import CapacityScheduler, ScheduledTask, SchedulingPriority, TaskType
from .tracker import ProcessTracker


class ProcessMonitor:
    """
    Unified interface for process monitoring intelligence.

    This is the main entry point for all process monitoring functionality.
    """

    def __init__(self):
        """Initialize the process monitor."""
        self.collector = ProcessCollector()
        self.tracker = ProcessTracker()
        self.analyzer = ProcessAnalyzer(tracker=self.tracker, collector=self.collector)
        self.optimizer = ResourceOptimizer(
            collector=self.collector, tracker=self.tracker, analyzer=self.analyzer
        )
        self.alert_generator = ProcessAlertGenerator(
            collector=self.collector,
            tracker=self.tracker,
            analyzer=self.analyzer,
            optimizer=self.optimizer,
        )
        self.scheduler = CapacityScheduler(process_monitor=self)
        self.batch_queue = BatchTaskQueue()
        self.batch_executor = BatchExecutor(queue=self.batch_queue, process_monitor=self)

    def collect_and_store(self):
        """Collect current snapshot and store in database."""
        resource_metric = self.collector.get_resource_summary()
        processes = self.collector.collect_snapshot()
        self.tracker.record_snapshot(resource_metric, processes)
        return resource_metric, processes

    def get_status(self) -> dict:
        """
        Get current system status.

        Returns:
            Dictionary with current status including resources, alerts, and waste
        """
        resource_metric = self.collector.get_resource_summary()
        alerts = self.alert_generator.generate_alerts(hours=24)
        waste_summary = self.optimizer.get_waste_summary()
        optimizations = self.optimizer.suggest_optimizations()

        return {
            "timestamp": resource_metric.timestamp.isoformat(),
            "cpu_percent": resource_metric.total_cpu_percent,
            "cpu_available": resource_metric.cpu_available_percent,
            "memory_usage_percent": resource_metric.memory_usage_percent,
            "memory_available_mb": resource_metric.available_memory_mb,
            "process_count": resource_metric.process_count,
            "ai_tool_cpu": resource_metric.ai_tool_cpu,
            "dev_service_cpu": resource_metric.dev_service_cpu,
            "alerts_count": len(alerts),
            "critical_alerts": sum(1 for a in alerts if a.severity.value == "critical"),
            "waste_items": waste_summary["total_waste_items"],
            "optimization_opportunities": len(optimizations),
        }

    def get_insights(self, days: int = 7) -> dict:
        """
        Get utilization insights and patterns.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with insights
        """
        utilization = self.analyzer.analyze_utilization_patterns(days=days)
        ai_tools = self.analyzer.get_ai_tool_insights(hours=days * 24)
        dev_patterns = self.analyzer.get_development_patterns(days=days)

        return {
            "utilization": utilization.to_dict(),
            "ai_tools": [tool.to_dict() for tool in ai_tools],
            "dev_patterns": dev_patterns.to_dict(),
        }

    def get_context_for_injection(self) -> str:
        """
        Get compact context for Claude Code injection.

        Returns:
            Compact string (max 200 chars) with key insights
        """
        parts = []

        # Resource status
        resource = self.collector.get_resource_summary()
        parts.append(f"CPU:{resource.cpu_available_percent:.0f}% avail")
        parts.append(f"Mem:{resource.memory_usage_percent:.0f}% used")

        # Top alert
        alerts = self.alert_generator.generate_alerts(hours=1)
        if alerts and alerts[0].severity.value in ("critical", "warning"):
            alert = alerts[0]
            parts.append(f"Alert: {alert.title}")

        # Top waste
        waste = self.optimizer.detect_waste()
        if waste:
            top_waste = waste[0]
            parts.append(f"Waste: {top_waste.process_name}")

        return " | ".join(parts)[:200]  # Limit to 200 chars

    def cleanup(self, days: int = 90):
        """
        Clean up old data.

        Args:
            days: Number of days to retain
        """
        self.tracker.cleanup_old_data(days=days)


__all__ = [
    # Main interface
    "ProcessMonitor",
    # Models
    "ProcessCategory",
    "ProcessStatus",
    "AnomalyType",
    "WasteType",
    "ProcessSnapshot",
    "ResourceMetric",
    "Anomaly",
    "WasteItem",
    "UtilizationInsights",
    "AIToolInsights",
    "DevPatterns",
    "Optimization",
    "CapacityForecast",
    # Components
    "ProcessCollector",
    "ProcessTracker",
    "ProcessAnalyzer",
    "ResourceOptimizer",
    "ProcessAlertGenerator",
    "ProcessAlertType",
    # Scheduling
    "CapacityScheduler",
    "TaskType",
    "SchedulingPriority",
    "ScheduledTask",
    # Batch Processing
    "BatchTaskQueue",
    "BatchTask",
    "TaskState",
    "BatchExecutor",
    "BatchDaemon",
]
