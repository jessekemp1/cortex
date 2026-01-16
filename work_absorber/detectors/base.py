"""
Base class for signal detectors.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import WorkSignal


class SignalDetector(ABC):
    """
    Abstract base class for work signal detection.

    Each detector is responsible for extracting signals from a specific
    source (git, docs, batch results, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the detector name for logging/debugging."""
        pass

    @abstractmethod
    def detect(
        self,
        project: str,
        project_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[WorkSignal]:
        """
        Detect work signals for a project.

        Args:
            project: Project name/identifier
            project_path: Path to the project directory
            since: Only detect signals after this time (inclusive)
            until: Only detect signals before this time (inclusive)

        Returns:
            List of detected WorkSignal objects
        """
        pass

    @abstractmethod
    def supports_incremental(self) -> bool:
        """
        Whether this detector supports incremental detection.

        If True, the detector can efficiently detect only new signals
        since the last run. If False, it must scan all sources each time.
        """
        pass

    def get_checkpoint_key(self, project: str) -> str:
        """Get the sync state key for this detector+project."""
        return f"{self.name}_checkpoint_{project}"
