"""Metrics collection for agent execution statistics.

Provides aggregated metrics and trend analysis for monitoring
agent execution performance.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

import structlog

from cortex.runtime.storage.history import ExecutionHistory

logger = structlog.get_logger()


class MetricsCollector:
    """Collect and aggregate metrics from execution history."""

    def __init__(self, history: ExecutionHistory):
        """Initialize metrics collector.

        Args:
            history: ExecutionHistory instance to query
        """
        self.history = history

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics.

        Returns:
            Dict with total executions, success rates, and activity counts
        """
        # Get all recent executions
        executions = self.history.get_recent_executions(limit=1000)

        if not executions:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "success_rate": 0.0,
                "average_duration_seconds": 0.0,
                "agents_active": 0,
                "last_24_hours": 0,
            }

        total = len(executions)
        successful = sum(1 for e in executions if e.get("success", False))
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0.0

        durations = [
            e.get("duration_seconds", 0)
            for e in executions
            if e.get("duration_seconds")
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Count unique agents
        agent_ids = {e.get("agent_id") for e in executions}
        agents_active = len(agent_ids)

        # Count executions in last 24 hours
        now = datetime.now()
        last_24h = sum(
            1
            for e in executions
            if e.get("created_at")
            and (
                now - datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            ).total_seconds()
            < 86400
        )

        return {
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": round(avg_duration, 3),
            "agents_active": agents_active,
            "last_24_hours": last_24h,
        }

    def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get metrics for a specific agent.

        Args:
            agent_id: The agent ID

        Returns:
            Dict with agent statistics and trend analysis
        """
        stats = self.history.get_agent_statistics(agent_id)

        # Get recent executions for trend analysis
        executions = self.history.get_recent_executions(limit=100, agent_id=agent_id)

        # Calculate trends (last 7 days vs previous 7 days)
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        recent_executions = [
            e
            for e in executions
            if e.get("created_at")
            and datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            >= week_ago
        ]

        older_executions = [
            e
            for e in executions
            if e.get("created_at")
            and two_weeks_ago
            <= datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            < week_ago
        ]

        recent_success_rate = (
            sum(1 for e in recent_executions if e.get("success", False))
            / len(recent_executions)
            * 100
            if recent_executions
            else 0
        )

        older_success_rate = (
            sum(1 for e in older_executions if e.get("success", False))
            / len(older_executions)
            * 100
            if older_executions
            else 0
        )

        success_rate_trend = recent_success_rate - older_success_rate

        return {
            **stats,
            "success_rate_trend": round(success_rate_trend, 2),
            "recent_executions_count": len(recent_executions),
            "older_executions_count": len(older_executions),
        }

    def get_agent_list_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all agents.

        Returns:
            Dict mapping agent_id to metrics dict
        """
        # Get all recent executions
        executions = self.history.get_recent_executions(limit=1000)

        # Group by agent_id
        agent_executions: Dict[str, list] = {}
        for execution in executions:
            agent_id = execution.get("agent_id")
            if agent_id:
                if agent_id not in agent_executions:
                    agent_executions[agent_id] = []
                agent_executions[agent_id].append(execution)

        # Calculate metrics for each agent
        agent_metrics = {}
        for agent_id, agent_execs in agent_executions.items():
            total = len(agent_execs)
            successful = sum(1 for e in agent_execs if e.get("success", False))
            failed = total - successful
            success_rate = (successful / total * 100) if total > 0 else 0.0

            durations = [
                e.get("duration_seconds", 0)
                for e in agent_execs
                if e.get("duration_seconds")
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

            agent_metrics[agent_id] = {
                "total_executions": total,
                "successful_executions": successful,
                "failed_executions": failed,
                "success_rate": round(success_rate, 2),
                "average_duration_seconds": round(avg_duration, 3),
            }

        return agent_metrics
