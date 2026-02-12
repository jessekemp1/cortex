"""
Resource optimizer for waste detection and optimization suggestions.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .analyzer import ProcessAnalyzer
from .collector import ProcessCollector
from .models import (
    CapacityForecast,
    Optimization,
    ProcessCategory,
    ProcessStatus,
    WasteItem,
    WasteType,
)
from .tracker import ProcessTracker


class ResourceOptimizer:
    """Detects waste and suggests resource optimizations."""

    # Configuration for auto-actions vs recommendations
    AUTO_ACTIONS = {
        WasteType.ZOMBIE_PROCESS: "kill",
        WasteType.ORPHANED_CONTAINER: "stop",
    }

    RECOMMEND_ONLY = {
        WasteType.IDLE_SERVICE: "suggest_stop",
        WasteType.HIGH_MEMORY_IDLE: "suggest_restart",
        WasteType.DUPLICATE_PROCESS: "suggest_consolidate",
    }

    def __init__(
        self,
        collector: Optional[ProcessCollector] = None,
        tracker: Optional[ProcessTracker] = None,
        analyzer: Optional[ProcessAnalyzer] = None,
    ):
        """
        Initialize the optimizer.

        Args:
            collector: ProcessCollector instance
            tracker: ProcessTracker instance
            analyzer: ProcessAnalyzer instance
        """
        self.collector = collector or ProcessCollector()
        self.tracker = tracker or ProcessTracker()
        self.analyzer = analyzer or ProcessAnalyzer(tracker=self.tracker, collector=self.collector)

    def detect_waste(self) -> List[WasteItem]:
        """
        Detect resource waste in current system state.

        Returns:
            List of WasteItem objects
        """
        waste_items = []
        processes = self.collector.collect_snapshot()
        now = datetime.now()

        # 1. Zombie processes
        zombies = [p for p in processes if p.status == ProcessStatus.ZOMBIE]
        for zombie in zombies:
            waste_items.append(
                WasteItem(
                    process_name=zombie.name,
                    process_pid=zombie.pid,
                    waste_type=WasteType.ZOMBIE_PROCESS,
                    resource_cost=f"{zombie.memory_mb:.1f} MB",
                    recommendation="Auto-kill zombie process",
                    auto_actionable=True,
                    metadata={"command": zombie.command},
                )
            )

        # 2. Idle services (dev services idle for 2+ hours)
        dev_services = [p for p in processes if p.category == ProcessCategory.DEV_SERVICE]
        for service in dev_services:
            uptime = (now - service.start_time).total_seconds() / 3600

            # Check if idle (low CPU and running for 2+ hours)
            if service.cpu_percent < 1.0 and uptime > 2.0:
                waste_items.append(
                    WasteItem(
                        process_name=service.name,
                        process_pid=service.pid,
                        waste_type=WasteType.IDLE_SERVICE,
                        resource_cost=f"{service.memory_mb:.1f} MB, idle {uptime:.1f}h",
                        recommendation=f"Consider stopping {service.name} (idle for {uptime:.1f}h)",
                        auto_actionable=False,
                        metadata={
                            "idle_hours": uptime,
                            "memory_mb": service.memory_mb,
                            "port": service.port,
                        },
                    )
                )

        # 3. Idle AI tools (Ollama, etc. idle for 2+ hours)
        ai_tools = [p for p in processes if p.category == ProcessCategory.AI_TOOL]
        for tool in ai_tools:
            uptime = (now - tool.start_time).total_seconds() / 3600

            if tool.cpu_percent < 1.0 and uptime > 2.0 and tool.memory_mb > 100.0:
                waste_items.append(
                    WasteItem(
                        process_name=tool.name,
                        process_pid=tool.pid,
                        waste_type=WasteType.IDLE_SERVICE,
                        resource_cost=f"{tool.memory_mb:.1f} MB, idle {uptime:.1f}h",
                        recommendation=f"Consider stopping {tool.name} to free memory",
                        auto_actionable=False,
                        metadata={
                            "idle_hours": uptime,
                            "memory_mb": tool.memory_mb,
                            "tool_type": "ai_tool",
                        },
                    )
                )

        # 4. High memory idle processes
        high_mem_idle = [
            p
            for p in processes
            if p.memory_mb > 1000.0
            and p.cpu_percent < 1.0
            and p.category not in (ProcessCategory.SYSTEM, ProcessCategory.OTHER)
        ]
        for proc in high_mem_idle:
            waste_items.append(
                WasteItem(
                    process_name=proc.name,
                    process_pid=proc.pid,
                    waste_type=WasteType.HIGH_MEMORY_IDLE,
                    resource_cost=f"{proc.memory_mb:.1f} MB",
                    recommendation=f"High memory usage while idle - consider restarting {proc.name}",
                    auto_actionable=False,
                    metadata={
                        "memory_mb": proc.memory_mb,
                        "category": proc.category.value,
                    },
                )
            )

        # 5. Duplicate processes (same name, multiple instances)
        process_counts = {}
        for proc in processes:
            if proc.category not in (ProcessCategory.SYSTEM, ProcessCategory.OTHER):
                process_counts[proc.name] = process_counts.get(proc.name, 0) + 1

        for name, count in process_counts.items():
            if count > 1:
                procs = [p for p in processes if p.name == name]
                total_memory = sum(p.memory_mb for p in procs)

                waste_items.append(
                    WasteItem(
                        process_name=name,
                        process_pid=procs[0].pid,  # Use first PID
                        waste_type=WasteType.DUPLICATE_PROCESS,
                        resource_cost=f"{count} instances, {total_memory:.1f} MB total",
                        recommendation=f"Multiple {name} instances detected - consider consolidating",
                        auto_actionable=False,
                        metadata={
                            "instance_count": count,
                            "total_memory_mb": total_memory,
                        },
                    )
                )

        # 6. Orphaned Docker containers
        docker_stats = self.collector.get_docker_stats()
        if docker_stats.get("available"):
            # Check for containers that might be orphaned
            # This is a simplified check - would need more sophisticated logic
            containers = docker_stats.get("containers", [])
            for container in containers:
                if "exited" in container.get("status", "").lower():
                    waste_items.append(
                        WasteItem(
                            process_name=f"docker:{container['name']}",
                            process_pid=0,  # Not a process PID
                            waste_type=WasteType.ORPHANED_CONTAINER,
                            resource_cost="Container stopped but not removed",
                            recommendation=f"Remove exited container: {container['name']}",
                            auto_actionable=True,
                            metadata=container,
                        )
                    )

        return waste_items

    def suggest_optimizations(self) -> List[Optimization]:
        """
        Suggest resource optimizations.

        Returns:
            List of Optimization objects
        """
        optimizations = []
        insights = self.analyzer.analyze_utilization_patterns(days=7)
        current = self.collector.get_resource_summary()

        # 1. Service scheduling based on utilization patterns
        if insights.peak_hours and insights.idle_hours:
            peak_avg = sum(insights.avg_cpu_by_hour.get(h, 0) for h in insights.peak_hours) / len(
                insights.peak_hours
            )
            idle_avg = sum(insights.avg_cpu_by_hour.get(h, 0) for h in insights.idle_hours) / len(
                insights.idle_hours
            )

            if peak_avg - idle_avg > 30:  # Significant difference
                optimizations.append(
                    Optimization(
                        title="Schedule heavy tasks during idle hours",
                        description=(
                            f"Your system is busiest during hours {insights.peak_hours} "
                            f"and idle during {insights.idle_hours}. "
                            f"Schedule tests, builds, and AI inference during idle hours for better performance."
                        ),
                        priority="MEDIUM",
                        estimated_savings="20-30% faster task completion",
                        action_type="SCHEDULE_TASK",
                        metadata={
                            "peak_hours": insights.peak_hours,
                            "idle_hours": insights.idle_hours,
                        },
                    )
                )

        # 2. Memory optimization
        if current.memory_usage_percent > 80:
            optimizations.append(
                Optimization(
                    title="High memory usage detected",
                    description=(
                        f"System memory usage is {current.memory_usage_percent:.1f}%. "
                        f"Consider stopping idle services or restarting memory-heavy processes."
                    ),
                    priority="HIGH",
                    estimated_savings=f"{current.total_memory_mb - current.available_memory_mb:.0f} MB potential recovery",
                    action_type="FREE_MEMORY",
                    metadata={"memory_usage_percent": current.memory_usage_percent},
                )
            )

        # 3. AI tool optimization
        ai_insights = self.analyzer.get_ai_tool_insights(hours=24)
        for ai_tool in ai_insights:
            if ai_tool.idle_hours > 2.0 and ai_tool.avg_memory > 500:
                optimizations.append(
                    Optimization(
                        title=f"Optimize {ai_tool.tool_name} usage",
                        description=(
                            f"{ai_tool.tool_name} has been idle for {ai_tool.idle_hours:.1f}h "
                            f"while consuming {ai_tool.avg_memory:.0f} MB. "
                            f"Consider stopping when not in use."
                        ),
                        priority="LOW",
                        estimated_savings=f"{ai_tool.avg_memory:.0f} MB memory",
                        action_type="STOP_SERVICE",
                        action_command=f"pkill -f {ai_tool.tool_name}",
                        metadata={
                            "tool": ai_tool.tool_name,
                            "idle_hours": ai_tool.idle_hours,
                        },
                    )
                )

        # 4. Docker optimization
        docker_stats = self.collector.get_docker_stats()
        if docker_stats.get("available") and docker_stats.get("container_count", 0) > 5:
            optimizations.append(
                Optimization(
                    title="Review Docker containers",
                    description=(
                        f"You have {docker_stats['container_count']} containers running. "
                        f"Review and stop unnecessary containers to free resources."
                    ),
                    priority="LOW",
                    estimated_savings="Variable memory savings",
                    action_type="REVIEW_CONTAINERS",
                    action_command="docker ps",
                    metadata=docker_stats,
                )
            )

        # 5. CPU optimization
        if current.total_cpu_percent > 70:
            high_cpu_procs = self.collector.get_high_resource_processes(cpu_threshold=30.0)
            if high_cpu_procs:
                top_proc = max(high_cpu_procs, key=lambda p: p.cpu_percent)
                optimizations.append(
                    Optimization(
                        title="High CPU usage detected",
                        description=(
                            f"System CPU usage is {current.total_cpu_percent:.1f}%. "
                            f"Top consumer: {top_proc.name} ({top_proc.cpu_percent:.1f}%)"
                        ),
                        priority="HIGH",
                        estimated_savings=f"{top_proc.cpu_percent:.1f}% CPU if optimized",
                        action_type="OPTIMIZE_CPU",
                        metadata={
                            "top_process": top_proc.name,
                            "cpu_percent": top_proc.cpu_percent,
                        },
                    )
                )

        return sorted(
            optimizations,
            key=lambda o: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(o.priority, 4),
        )

    def get_capacity_forecast(self, task_type: str) -> CapacityForecast:
        """
        Forecast capacity for task scheduling.

        Args:
            task_type: Type of task (TEST, BUILD, DEPLOY, AI_INFERENCE)

        Returns:
            CapacityForecast object
        """
        recommendation = self.analyzer.get_capacity_recommendation(task_type.lower())
        self.analyzer.analyze_utilization_patterns(days=7)

        # Parse best time
        if recommendation["best_time"] == "now":
            best_time = datetime.now()
            confidence = 0.9 if recommendation["current_availability"] > 50 else 0.6
        else:
            # Parse hour from "HH:MM" format
            hour = int(recommendation["best_time"].split(":")[0])
            now = datetime.now()
            best_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)

            # If the hour has passed today, schedule for tomorrow
            if best_time < now:
                best_time += timedelta(days=1)

            confidence = 0.8

        return CapacityForecast(
            task_type=task_type,
            best_time_to_run=best_time,
            expected_duration_minutes=recommendation["estimated_duration_minutes"],
            resource_availability=recommendation["avg_availability"],
            confidence=confidence,
            reasoning=recommendation["recommendation"],
        )

    def get_waste_summary(self) -> Dict[str, Any]:
        """
        Get summary of detected waste.

        Returns:
            Dictionary with waste summary
        """
        waste_items = self.detect_waste()

        # Group by type
        by_type = {}
        for item in waste_items:
            type_name = item.waste_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(item)

        # Calculate total potential savings
        auto_actionable_count = sum(1 for item in waste_items if item.auto_actionable)

        return {
            "total_waste_items": len(waste_items),
            "auto_actionable": auto_actionable_count,
            "manual_review": len(waste_items) - auto_actionable_count,
            "by_type": {type_name: len(items) for type_name, items in by_type.items()},
            "items": [item.to_dict() for item in waste_items],
        }
