"""
Anthropic Model Policy for Batch Operations

Defines model selection for batch API requests.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class AnthropicBatchModels:
    """Model policy for batch operations."""

    # Default model for most batch operations
    default: str = "claude-sonnet-4-20250514"

    # Fast model for simple classification tasks
    fast: str = "claude-haiku-4-5-20251001"

    # High-quality model for complex analysis
    premium: str = "claude-opus-4-6"

    def get_model(self, task_type: str = "default") -> str:
        """Get appropriate model for task type."""
        models: Dict[str, str] = {
            "default": self.default,
            "fast": self.fast,
            "classification": self.fast,
            "simple": self.fast,
            "premium": self.premium,
            "complex": self.premium,
            "analysis": self.default,
            "review": self.default,
            "security": self.default,
            "documentation": self.default,
            "research": self.default,
            "pattern": self.default,
            "recommendation": self.default,
            "learning": self.default,
            "briefing": self.default,
        }
        return models.get(task_type, self.default)

    def for_learning(self) -> str:
        """Model for learning/feedback analysis."""
        return self.default

    def for_briefing(self) -> str:
        """Model for briefing generation."""
        return self.default

    def for_research(self) -> str:
        """Model for research tasks."""
        return self.default
