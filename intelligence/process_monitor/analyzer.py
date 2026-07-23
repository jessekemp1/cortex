"""
Process analyzer for pattern detection and anomaly analysis.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .collector import ProcessCollector
from .models import (
    AIToolInsights,
    Anomaly,
    AnomalyType,
    DevPatterns,
    ProcessCategory,
    ProcessSnapshot,
    ProcessStatus,
    ResourceMetric,
    UtilizationInsights,
)
from .tracker import ProcessTracker


class ProcessAnalyzer:
    """Analyzes process patterns and detects anomalies."""

    def __init__(
        self,
        tracker: Optional[ProcessTracker] = None,
        collector: Optional[ProcessCollector] = None,
    ):
        """
        Initialize the analyzer.

        Args:
            tracker: ProcessTracker instance (default: create new)
            collector: ProcessCollector instance (default: create new)
        """
        self.tracker = tracker or ProcessTracker()
        self.collector = collector or ProcessCollector()

    def analyze_utilization_patterns(self, days: int = 7) -> UtilizationInsights:
        """
        Analyze system utilization patterns.

        Args:
            days: Number of days to analyze

        Returns:
            UtilizationInsights object
        """
        hourly_stats = self.tracker.get_hourly_stats(days=days)

        if not hourly_stats:
            # No data yet, return defaults
            return UtilizationInsights(
                peak_hours=[],
                idle_hours=[],
                avg_cpu_by_hour={},
                avg_memory_by_hour={},
                capacity_headroom=100.0,
            )

        # Extract CPU and memory by hour
        avg_cpu_by_hour = {hour: stats["avg_cpu"] for hour, stats in hourly_stats.items()}

        avg_memory_by_hour = {
            hour: stats["avg_memory_used"] for hour, stats in hourly_stats.items()
        }

        # Identify peak hours (top 3 highest CPU)
        sorted_by_cpu = sorted(avg_cpu_by_hour.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [hour for hour, _ in sorted_by_cpu[:3]]

        # Identify idle hours (bottom 3 lowest CPU)
        idle_hours = [hour for hour, _ in sorted_by_cpu[-3:]]

        # Calculate capacity headroom
        avg_cpu = sum(avg_cpu_by_hour.values()) / len(avg_cpu_by_hour) if avg_cpu_by_hour else 0
        capacity_headroom = max(0.0, 100.0 - avg_cpu)

        return UtilizationInsights(
            peak_hours=peak_hours,
            idle_hours=idle_hours,
            avg_cpu_by_hour=avg_cpu_by_hour,
            avg_memory_by_hour=avg_memory_by_hour,
            capacity_headroom=capacity_headroom,
        )

    def detect_anomalies(self, current: ResourceMetric) -> List[Anomaly]:
        """
        Detect anomalies in current system state.

        Args:
            current: Current resource metric

        Returns:
            List of detected anomalies
        """
        anomalies = []
        now = datetime.now()

        # Get current processes
        processes = self.collector.collect_snapshot()

        # Check for zombie processes. Zombies are inert (no CPU/memory) and can
        # only be reaped by their parent, so emit one anomaly per leaking parent
        # rather than one per zombie — a single buggy daemon can leak hundreds.
        zombies = [p for p in processes if p.status == ProcessStatus.ZOMBIE]
        by_pid = {p.pid: p for p in processes}
        zombies_by_parent: Dict[Optional[int], List[ProcessSnapshot]] = {}
        for zombie in zombies:
            zombies_by_parent.setdefault(zombie.parent_pid, []).append(zombie)
        for parent_pid, children in zombies_by_parent.items():
            parent = by_pid.get(parent_pid) if parent_pid else None
            parent_label = f"{parent.name} (PID {parent_pid})" if parent else f"PID {parent_pid}"
            sample = children[0]
            anomalies.append(
                Anomaly(
                    timestamp=now,
                    process_name=sample.name,
                    process_pid=sample.pid,
                    anomaly_type=AnomalyType.ZOMBIE_PROCESS,
                    severity="WARNING",
                    description=(
                        f"{len(children)} zombie process(es) parented by {parent_label} — "
                        f"restart the parent to reap them"
                    ),
                    metadata={
                        "command": sample.command,
                        "parent_pid": parent_pid,
                        "zombie_count": len(children),
                        "zombie_pids": [c.pid for c in children[:10]],
                    },
                )
            )

        # Check for sustained high CPU
        high_cpu_procs = [p for p in processes if p.cpu_percent > 80.0]
        for proc in high_cpu_procs:
            anomalies.append(
                Anomaly(
                    timestamp=now,
                    process_name=proc.name,
                    process_pid=proc.pid,
                    anomaly_type=AnomalyType.CPU_SPIKE,
                    severity="WARNING",
                    description=f"High CPU usage: {proc.name} using {proc.cpu_percent:.1f}%",
                    metadata={
                        "cpu_percent": proc.cpu_percent,
                        "category": proc.category.value,
                    },
                )
            )

        # Check for memory leaks (compare with historical data)
        history = self.tracker.get_utilization_history(hours=24)
        if len(history) > 10:
            # Check if memory usage is trending up
            recent_memory = [h.total_memory_mb - h.available_memory_mb for h in history[-10:]]
            early_memory = [h.total_memory_mb - h.available_memory_mb for h in history[:10]]

            recent_avg = sum(recent_memory) / len(recent_memory)
            early_avg = sum(early_memory) / len(early_memory)

            growth_rate = ((recent_avg - early_avg) / early_avg * 100) if early_avg > 0 else 0

            if growth_rate > 20:  # 20% growth
                anomalies.append(
                    Anomaly(
                        timestamp=now,
                        process_name="system",
                        process_pid=0,
                        anomaly_type=AnomalyType.MEMORY_LEAK,
                        severity="WARNING",
                        description=f"Memory usage increased {growth_rate:.1f}% in last 24h",
                        metadata={
                            "growth_rate": growth_rate,
                            "recent_avg_mb": recent_avg,
                        },
                    )
                )

        # Check for idle AI tools
        ai_tools = [p for p in processes if p.category == ProcessCategory.AI_TOOL]
        for tool in ai_tools:
            # Check if CPU is very low (< 1%) for AI tools
            if tool.cpu_percent < 1.0 and tool.memory_mb > 100.0:
                # Calculate uptime
                uptime_hours = (now - tool.start_time).total_seconds() / 3600

                if uptime_hours > 2.0:  # Idle for 2+ hours
                    anomalies.append(
                        Anomaly(
                            timestamp=now,
                            process_name=tool.name,
                            process_pid=tool.pid,
                            anomaly_type=AnomalyType.IDLE_WASTE,
                            severity="INFO",
                            description=f"{tool.name} idle for {uptime_hours:.1f}h, using {tool.memory_mb:.0f}MB",
                            metadata={
                                "idle_hours": uptime_hours,
                                "memory_mb": tool.memory_mb,
                                "category": tool.category.value,
                            },
                        )
                    )

        return anomalies

    def get_ai_tool_insights(self, hours: int = 24) -> List[AIToolInsights]:
        """
        Get insights about AI tool usage.

        Args:
            hours: Number of hours to analyze

        Returns:
            List of AIToolInsights objects
        """
        patterns = self.tracker.get_process_patterns(ProcessCategory.AI_TOOL, hours=hours)

        insights = []
        for tool_name, stats in patterns.items():
            # Estimate usage vs idle hours based on CPU
            # Consider active if avg CPU > 5%
            sample_count = stats["sample_count"]
            avg_cpu = stats["avg_cpu"]

            # Rough estimate: if avg CPU > 5%, consider it active
            if avg_cpu > 5.0:
                usage_ratio = avg_cpu / 100.0
            else:
                usage_ratio = 0.1  # Assume mostly idle

            # Estimate total hours (samples are typically every 30s-5min)
            # Conservative estimate: 1 sample = 2 minutes
            total_hours = (sample_count * 2) / 60
            usage_hours = total_hours * usage_ratio
            idle_hours = total_hours - usage_hours

            insights.append(
                AIToolInsights(
                    tool_name=tool_name,
                    usage_hours=usage_hours,
                    idle_hours=idle_hours,
                    avg_cpu=avg_cpu,
                    avg_memory=stats["avg_memory"],
                    cost_estimate=None,  # Could be enhanced with API usage tracking
                )
            )

        return insights

    def get_development_patterns(self, days: int = 7) -> DevPatterns:
        """
        Analyze development workflow patterns.

        Args:
            days: Number of days to analyze

        Returns:
            DevPatterns object
        """
        hourly_stats = self.tracker.get_hourly_stats(days=days)

        # Analyze build tool patterns
        build_patterns = self.tracker.get_process_patterns(
            ProcessCategory.BUILD_TOOL, hours=days * 24
        )

        # Identify active coding hours (when dev services are running)
        self.tracker.get_process_patterns(ProcessCategory.DEV_SERVICE, hours=days * 24)

        # Active coding hours: hours with above-average dev service activity
        if hourly_stats:
            avg_cpu = sum(stats["avg_cpu"] for stats in hourly_stats.values()) / len(hourly_stats)
            active_coding_hours = [
                hour for hour, stats in hourly_stats.items() if stats["avg_cpu"] > avg_cpu
            ]
        else:
            active_coding_hours = []

        # Testing hours: when build tools (pytest, etc.) are active
        # This is a simplified heuristic
        testing_hours = (
            active_coding_hours[:3] if len(active_coding_hours) >= 3 else active_coding_hours
        )

        # Build frequency
        total_build_samples = sum(stats["sample_count"] for stats in build_patterns.values())
        # Estimate: 1 build sample = 1 build (rough approximation)
        build_frequency = total_build_samples / max(days, 1)

        # Deployment times (placeholder - would need integration with deployment tracking)
        deployment_times = []

        return DevPatterns(
            active_coding_hours=active_coding_hours,
            testing_hours=testing_hours,
            build_frequency=build_frequency,
            deployment_times=deployment_times,
        )

    def get_process_health_score(self, category: ProcessCategory) -> float:
        """
        Calculate a health score (0-100) for a process category.

        Args:
            category: Process category to evaluate

        Returns:
            Health score (0-100)
        """
        score = 100.0

        # Get recent anomalies for this category
        anomalies = self.tracker.get_recent_anomalies(hours=24)
        category_anomalies = [a for a in anomalies if a.metadata.get("category") == category.value]

        # Deduct points for anomalies
        for anomaly in category_anomalies:
            if anomaly.severity == "CRITICAL":
                score -= 20
            elif anomaly.severity == "WARNING":
                score -= 10
            else:
                score -= 5

        # Get current processes
        processes = self.collector.get_processes_by_category(category)

        # Check for zombie processes. Zombies hold no resources, so their
        # presence signals a leaking parent but should not zero the score —
        # cap the penalty regardless of how many a buggy daemon accumulates.
        zombies = [p for p in processes if p.status == ProcessStatus.ZOMBIE]
        score -= min(len(zombies) * 15, 30)

        # Check resource efficiency
        if processes:
            avg_cpu = sum(p.cpu_percent for p in processes) / len(processes)
            avg_memory = sum(p.memory_mb for p in processes) / len(processes)

            # Penalize if resources are very high
            if avg_cpu > 70:
                score -= 10
            if avg_memory > 2000:  # 2GB average
                score -= 10

        return max(0.0, min(100.0, score))

    def get_capacity_recommendation(self, task_type: str = "general") -> Dict[str, Any]:
        """
        Get capacity recommendation for running a task.

        Args:
            task_type: Type of task (test, build, deploy, ai_inference)

        Returns:
            Dictionary with capacity recommendation
        """
        insights = self.analyze_utilization_patterns(days=7)
        current = self.collector.get_resource_summary()

        # Determine best time based on idle hours
        current_hour = datetime.now().hour

        if current_hour in insights.idle_hours:
            best_time = "now"
            availability = insights.capacity_headroom
        else:
            # Suggest next idle hour
            next_idle_hours = [h for h in insights.idle_hours if h > current_hour]
            if next_idle_hours:
                best_hour = min(next_idle_hours)
            else:
                # Wrap around to tomorrow
                best_hour = min(insights.idle_hours) if insights.idle_hours else current_hour

            best_time = f"{best_hour:02d}:00"
            availability = insights.capacity_headroom

        # Estimate duration based on task type
        duration_map = {
            "test": 15.0,  # 15 minutes
            "build": 10.0,  # 10 minutes
            "deploy": 5.0,  # 5 minutes
            "ai_inference": 30.0,  # 30 minutes
            "general": 10.0,
        }
        estimated_duration = duration_map.get(task_type, 10.0)

        return {
            "best_time": best_time,
            "current_availability": current.cpu_available_percent,
            "avg_availability": availability,
            "estimated_duration_minutes": estimated_duration,
            "recommendation": (
                "Good time to run"
                if best_time == "now"
                else f"Consider running at {best_time} for better resource availability"
            ),
        }
