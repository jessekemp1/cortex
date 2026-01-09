"""Base agent class for Cortex runtime.

Provides the abstract base class that all agents must inherit from,
defining the standard interface for agent execution.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from cortex.runtime.models import AgentResult


class AgentMetadata(BaseModel):
    """Metadata about an agent."""

    version: str = "1.0.0"
    author: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []


class BaseAgent(ABC):
    """Abstract base class for all agents.

    All custom agents must inherit from this class and implement
    the execute() method.

    Example:
        class MyAgent(BaseAgent):
            def execute(self, context: Dict[str, Any]) -> AgentResult:
                # Do work
                return AgentResult(success=True, message="Done")
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        metadata: Optional[AgentMetadata] = None,
    ):
        """Initialize the agent.

        Args:
            agent_id: Unique identifier for the agent
            name: Human-readable name
            description: What the agent does
            metadata: Optional agent metadata
        """
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.metadata = metadata or AgentMetadata()

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> "AgentResult":
        """Execute the agent with given context.

        Args:
            context: Execution context (may include event data, user input, etc.)

        Returns:
            AgentResult with execution outcome
        """
        pass

    def validate(self) -> bool:
        """Validate agent configuration.

        Returns:
            True if agent is valid, False otherwise
        """
        return bool(self.agent_id and self.name)

    def get_metadata(self) -> AgentMetadata:
        """Get agent metadata."""
        return self.metadata

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.agent_id}, name={self.name})>"
