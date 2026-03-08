"""
Cortex Supervisor - Always-on batch orchestration layer.

Unifies shell task execution and AI batch API calls with:
- Immediate execution (no arbitrary scheduled_time delays)
- Self-healing (detects and retries stuck tasks)
- Proactive work discovery (recommendations, alerts, orphaned work)
- AI batch optimization (50% cost savings via grouping)

Usage:
    from supervisor import CortexSupervisor

    supervisor = CortexSupervisor()
    supervisor.run_once()  # Single tick
    supervisor.start(foreground=True)  # Daemon mode

CLI:
    cortex supervisor start [--foreground]
    cortex supervisor stop
    cortex supervisor status [--json]
    cortex supervisor run-once [--json]
"""

from supervisor.config import SupervisorConfig
from supervisor.core import CortexSupervisor
from supervisor.health import HealingAction, HealthIssue, HealthMonitor
from supervisor.models import RoutedTask, TaskTarget, TickResult, WorkItem

__all__ = [
    "CortexSupervisor",
    "SupervisorConfig",
    "HealthMonitor",
    "HealingAction",
    "HealthIssue",
    "TickResult",
    "WorkItem",
    "TaskTarget",
    "RoutedTask",
]


# Lazy imports for orchestration components (Phase 3-6)
def __getattr__(name):
    if name == "AgentDispatcher":
        from supervisor.dispatch import AgentDispatcher

        return AgentDispatcher
    if name == "ResultCollector":
        from supervisor.collector import ResultCollector

        return ResultCollector
    if name == "ModelRouter":
        from supervisor.router import ModelRouter

        return ModelRouter
    if name == "WorkIntake":
        from supervisor.intake import WorkIntake

        return WorkIntake
    if name == "AgentProfile":
        from supervisor.agents import AgentProfile

        return AgentProfile
    raise AttributeError(f"module 'supervisor' has no attribute {name!r}")
