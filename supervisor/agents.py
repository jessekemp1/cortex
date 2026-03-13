"""
Agent definitions -- profiles for specialized orchestration agents.

Each agent has:
  - A name and description
  - Task types it can handle
  - Preferred model tier (can be overridden by router)
  - System prompt template
  - Max concurrent instances
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class AgentProfile:
    """Definition of a specialized agent for orchestration."""

    name: str
    description: str
    task_types: Set[str]
    preferred_model_tier: str  # "opus", "sonnet", "haiku"
    system_prompt_template: str
    max_concurrent: int = 3
    timeout_seconds: int = 300
    can_decompose: bool = False  # Can this agent act as a team lead?
    max_sub_tasks: int = 5  # Max sub-tasks when decomposing

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.task_types

    def build_system_prompt(self, project: str = "", context: str = "") -> str:
        return self.system_prompt_template.format(
            project=project or "unknown",
            context=context or "No additional context.",
        )


AGENT_REGISTRY: Dict[str, AgentProfile] = {
    "architect": AgentProfile(
        name="architect",
        description="Architecture, design, and planning specialist.",
        task_types={"architecture", "design", "planning", "spec"},
        preferred_model_tier="opus",
        system_prompt_template=(
            "You are a software architect analyzing {project}. {context} "
            "Focus on design decisions, trade-offs, and implementation strategy. "
            "Be specific about file paths and interfaces."
        ),
        can_decompose=True,
    ),
    "code_reviewer": AgentProfile(
        name="code_reviewer",
        description="Code review and quality analysis specialist.",
        task_types={"review", "quality", "analysis", "audit"},
        preferred_model_tier="sonnet",
        system_prompt_template=(
            "You are a code reviewer for {project}. {context} "
            "Focus on correctness, security, performance, and maintainability. "
            "Reference specific lines."
        ),
    ),
    "test_engineer": AgentProfile(
        name="test_engineer",
        description="Test writing and validation specialist.",
        task_types={"test", "coverage", "validation", "qa"},
        preferred_model_tier="sonnet",
        system_prompt_template=(
            "You are a test engineer for {project}. {context} "
            "Write thorough tests with specific assertions. Use pytest. "
            "Never assert status_code in [200, 500]."
        ),
    ),
    "researcher": AgentProfile(
        name="researcher",
        description="Research, investigation, and analysis specialist.",
        task_types={"research", "investigation", "benchmarking", "discovery"},
        preferred_model_tier="sonnet",
        system_prompt_template=(
            "You are a research analyst investigating {project}. {context} "
            "Gather evidence, cite sources, and present findings with confidence levels."
        ),
    ),
    "implementer": AgentProfile(
        name="implementer",
        description="Code implementation specialist.",
        task_types={"implement", "fix", "refactor", "feature"},
        preferred_model_tier="opus",
        system_prompt_template=(
            "You are an implementation specialist for {project}. {context} "
            "Write clean, tested code. Follow existing patterns. Type hints required."
        ),
        can_decompose=True,
    ),
    "classifier": AgentProfile(
        name="classifier",
        description="Quick classification and triage specialist.",
        task_types={"classify", "triage", "categorize", "tag"},
        preferred_model_tier="haiku",
        system_prompt_template=(
            "You are a task classifier. {context} "
            "Categorize quickly and accurately. Output structured JSON."
        ),
        timeout_seconds=60,
    ),
}


def get_agent_for_task(task_type: str) -> Optional[AgentProfile]:
    """Find the best agent for a given task type."""
    for agent in AGENT_REGISTRY.values():
        if agent.can_handle(task_type):
            return agent
    return None


def get_agent_by_name(name: str) -> Optional[AgentProfile]:
    """Look up an agent by name."""
    return AGENT_REGISTRY.get(name)


def list_agents() -> List[AgentProfile]:
    """Return all registered agent profiles."""
    return list(AGENT_REGISTRY.values())
