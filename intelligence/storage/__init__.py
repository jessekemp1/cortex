#!/usr/bin/env python3
"""
Pluggable storage layer for outcome tracking.

Provides abstract interface and concrete implementations (JSONL, SQLite).
Allows swapping storage backends without changing application code.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from intelligence.model_selection.models import (
    ModelOutcomeEntry,
    SessionOutcomeEntry,
    WorkflowOutcomeEntry,
)


class OutcomeStorage(ABC):
    """
    Abstract storage interface for outcome tracking.

    Implementations: JSONLStorage (default), SQLiteStorage (future).
    """

    @abstractmethod
    def log_model_outcome(self, entry: ModelOutcomeEntry) -> None:
        """Log a model outcome entry."""
        pass

    @abstractmethod
    def load_model_outcomes(
        self, days: int = 30, task_type: Optional[str] = None
    ) -> List[ModelOutcomeEntry]:
        """
        Load model outcomes from the last N days.

        Args:
            days: Number of days to look back
            task_type: Optional filter by task type
        """
        pass

    @abstractmethod
    def log_workflow_outcome(self, entry: WorkflowOutcomeEntry) -> None:
        """Log a workflow outcome entry."""
        pass

    @abstractmethod
    def load_workflow_outcomes(self, days: int = 30) -> List[WorkflowOutcomeEntry]:
        """Load workflow outcomes from the last N days."""
        pass

    @abstractmethod
    def log_session_outcome(self, entry: SessionOutcomeEntry) -> None:
        """Log a session outcome entry."""
        pass

    @abstractmethod
    def load_session_outcomes(self, days: int = 30) -> List[SessionOutcomeEntry]:
        """Load session outcomes from the last N days."""
        pass

    @abstractmethod
    def get_storage_info(self) -> dict:
        """Get storage backend information."""
        pass


# Singleton instance (lazy-loaded)
_storage_instance: Optional[OutcomeStorage] = None


def get_storage() -> OutcomeStorage:
    """
    Get the configured storage instance (singleton).

    Returns the appropriate storage backend based on configuration.
    Defaults to JSONLStorage.
    """
    global _storage_instance

    if _storage_instance is None:
        # Import here to avoid circular dependencies
        from intelligence.storage.jsonl_storage import JSONLStorage

        _storage_instance = JSONLStorage()

    return _storage_instance


def set_storage(storage: OutcomeStorage) -> None:
    """
    Set the storage instance (for testing or custom backends).

    Args:
        storage: Storage implementation to use
    """
    global _storage_instance
    _storage_instance = storage
