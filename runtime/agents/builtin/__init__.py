"""Cortex Runtime Builtin Agents.

Standard agents for common tasks like briefings, refactoring, and research.
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "BriefingAgent",
    "RefactorAgent",
    "ResearchAgent",
    "TaskAgent",
    "EmailAgent",
]


def __getattr__(name: str):
    """Lazy load agents."""
    if name == "BriefingAgent":
        from cortex.runtime.agents.builtin.briefing import BriefingAgent
        return BriefingAgent
    if name == "RefactorAgent":
        from cortex.runtime.agents.builtin.refactor import RefactorAgent
        return RefactorAgent
    if name == "ResearchAgent":
        from cortex.runtime.agents.builtin.research import ResearchAgent
        return ResearchAgent
    if name == "TaskAgent":
        from cortex.runtime.agents.builtin.task import TaskAgent
        return TaskAgent
    if name == "EmailAgent":
        from cortex.runtime.agents.builtin.email import EmailAgent
        return EmailAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
