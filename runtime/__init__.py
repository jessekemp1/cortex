"""Cortex Runtime - Task execution and scheduling engine.

This module provides the runtime infrastructure for executing agents,
managing schedules, and tracking execution history. Migrated from
local-orchestrator project.

Usage:
    from cortex.runtime import RuntimeExecutor, RuntimeConfig
    from cortex.runtime.agents import BaseAgent
    from cortex.runtime.storage import ExecutionHistory
"""

from cortex.runtime.config import RuntimeConfig

# Lazy imports to avoid circular dependencies
__all__ = [
    "RuntimeConfig",
    "RuntimeExecutor",
    "BaseAgent",
    "AgentResult",
    "AgentStatus",
]


def __getattr__(name: str):
    """Lazy load heavy modules."""
    if name == "RuntimeExecutor":
        from cortex.runtime.executor import RuntimeExecutor

        return RuntimeExecutor
    if name == "BaseAgent":
        from cortex.runtime.agents.base import BaseAgent

        return BaseAgent
    if name == "AgentResult":
        from cortex.runtime.models import AgentResult

        return AgentResult
    if name == "AgentStatus":
        from cortex.runtime.models import AgentStatus

        return AgentStatus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
