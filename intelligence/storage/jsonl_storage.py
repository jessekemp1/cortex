#!/usr/bin/env python3
"""
JSONL (JSON Lines) storage implementation.

Stores outcomes in newline-delimited JSON format.
Simple, portable, good for <10K records per file.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from intelligence.model_selection.models import (
    ModelOutcomeEntry,
    SessionOutcomeEntry,
    WorkflowOutcomeEntry,
)
from intelligence.storage import OutcomeStorage


class JSONLStorage(OutcomeStorage):
    """
    JSONL storage implementation.

    Files:
    - ~/.cortex/model_outcomes.jsonl
    - ~/.cortex/workflow_outcomes.jsonl
    - ~/.cortex/session_outcomes.jsonl
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize JSONL storage.

        Args:
            storage_dir: Directory for storage files (default: ~/.cortex/)
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".cortex"

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.model_outcomes_file = self.storage_dir / "model_outcomes.jsonl"
        self.workflow_outcomes_file = self.storage_dir / "workflow_outcomes.jsonl"
        self.session_outcomes_file = self.storage_dir / "session_outcomes.jsonl"

        # Ensure files exist
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Create storage files if they don't exist."""
        for file in [
            self.model_outcomes_file,
            self.workflow_outcomes_file,
            self.session_outcomes_file,
        ]:
            if not file.exists():
                file.touch()

    def log_model_outcome(self, entry: ModelOutcomeEntry) -> None:
        """Log a model outcome entry."""
        with open(self.model_outcomes_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def load_model_outcomes(
        self, days: int = 30, task_type: Optional[str] = None
    ) -> List[ModelOutcomeEntry]:
        """
        Load model outcomes from the last N days.

        Args:
            days: Number of days to look back
            task_type: Optional filter by task type
        """
        if not self.model_outcomes_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        outcomes = []

        try:
            with open(self.model_outcomes_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)
                    entry_time = datetime.fromisoformat(data["timestamp"])

                    # Filter by date
                    if entry_time < cutoff:
                        continue

                    # Filter by task type if specified
                    if task_type and data.get("task_type") != task_type:
                        continue

                    outcomes.append(ModelOutcomeEntry(**data))

        except (json.JSONDecodeError, IOError, KeyError) as e:
            # Log error but don't crash
            print(f"Warning: Error loading model outcomes: {e}")
            return []

        return outcomes

    def log_workflow_outcome(self, entry: WorkflowOutcomeEntry) -> None:
        """Log a workflow outcome entry."""
        with open(self.workflow_outcomes_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def load_workflow_outcomes(self, days: int = 30) -> List[WorkflowOutcomeEntry]:
        """Load workflow outcomes from the last N days."""
        if not self.workflow_outcomes_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        outcomes = []

        try:
            with open(self.workflow_outcomes_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)
                    entry_time = datetime.fromisoformat(data["timestamp"])

                    if entry_time < cutoff:
                        continue

                    outcomes.append(WorkflowOutcomeEntry(**data))

        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Error loading workflow outcomes: {e}")
            return []

        return outcomes

    def log_session_outcome(self, entry: SessionOutcomeEntry) -> None:
        """Log a session outcome entry."""
        with open(self.session_outcomes_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def load_session_outcomes(self, days: int = 30) -> List[SessionOutcomeEntry]:
        """Load session outcomes from the last N days."""
        if not self.session_outcomes_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        outcomes = []

        try:
            with open(self.session_outcomes_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)
                    entry_time = datetime.fromisoformat(data["timestamp"])

                    if entry_time < cutoff:
                        continue

                    outcomes.append(SessionOutcomeEntry(**data))

        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Error loading session outcomes: {e}")
            return []

        return outcomes

    def get_storage_info(self) -> dict:
        """Get storage backend information."""
        return {
            "backend": "jsonl",
            "storage_dir": str(self.storage_dir),
            "model_outcomes_file": str(self.model_outcomes_file),
            "workflow_outcomes_file": str(self.workflow_outcomes_file),
            "session_outcomes_file": str(self.session_outcomes_file),
            "model_outcomes_count": self._count_lines(self.model_outcomes_file),
            "workflow_outcomes_count": self._count_lines(self.workflow_outcomes_file),
            "session_outcomes_count": self._count_lines(self.session_outcomes_file),
        }

    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        if not file_path.exists():
            return 0

        try:
            with open(file_path, "r") as f:
                return sum(1 for line in f if line.strip())
        except IOError:
            return 0
