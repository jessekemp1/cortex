#!/usr/bin/env python3
"""
Base Domain Expert - Abstract base class for project-specific intelligence.

Layer 3 of Cortex Intelligence Stack: Domain Knowledge

Domain experts provide project-specific intelligence beyond generic code analysis:
- Warnings about project-specific issues (stale data, degraded metrics)
- Validation suggestions for specific tasks
- Domain-specific hints (coordinate systems, data formats, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class DomainInsight:
    """Domain-specific insight from an expert."""

    category: str  # "warning", "pattern", "suggestion", "context"
    message: str
    confidence: float  # 0-1
    source: str  # "grib_data", "validation_api", "git_history", etc.

    def to_compact_str(self, max_length: int = 80) -> str:
        """Convert to compact string for display."""
        prefix = "⚠️" if self.category == "warning" else "💡"
        text = f"{prefix} {self.message}"
        if len(text) > max_length:
            text = text[: max_length - 3] + "..."
        return text


class BaseDomainExpert(ABC):
    """Abstract base class for domain-specific intelligence."""

    CACHE_TTL = 300  # 5 minutes

    @property
    @abstractmethod
    def project_name(self) -> str:
        """Project this expert covers."""
        pass

    @abstractmethod
    def get_quick_insight(self, cwd: Path, task: str = "") -> Optional[str]:
        """
        Get quick insight for context injection (under 150ms).

        Args:
            cwd: Current working directory
            task: Optional task description

        Returns:
            Compact insight string (under 100 chars) or None
        """
        pass

    @abstractmethod
    def get_warnings(self, cwd: Path) -> List[DomainInsight]:
        """
        Get current warnings for the project.

        Args:
            cwd: Current working directory

        Returns:
            List of domain-specific warnings
        """
        pass

    @abstractmethod
    def get_validation_suggestions(self, task: str) -> List[str]:
        """
        Suggest validation steps for a task.

        Args:
            task: Task description

        Returns:
            List of validation suggestions
        """
        pass

    def is_relevant(self, cwd: Path, task: str = "") -> bool:
        """
        Check if this expert is relevant for the current context.

        Default implementation checks if cwd contains project name.
        Override for more sophisticated detection.

        Args:
            cwd: Current working directory
            task: Optional task description

        Returns:
            True if expert is relevant
        """
        project_lower = self.project_name.lower()
        return project_lower in str(cwd).lower() or (
            task and any(
                keyword in task.lower()
                for keyword in self._get_domain_keywords()
            )
        )

    def _get_domain_keywords(self) -> List[str]:
        """
        Get list of domain-specific keywords that indicate relevance.

        Override in subclasses to provide domain-specific keywords.

        Returns:
            List of keywords (lowercase)
        """
        return [self.project_name.lower()]
