"""
Batch result detector - Extract work signals from Batch API results.

Monitors completed batch tasks and converts them to work signals,
capturing analysis and planning work done via batch processing.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import WorkSignal, WorkSignalType
from .base import SignalDetector

logger = logging.getLogger(__name__)


class BatchResultDetector(SignalDetector):
    """
    Detect work signals from Batch API results.

    Monitors:
    - ~/.cortex/batch_schedule/tasks.json - Completed batch tasks
    - ~/.cortex/batches/ - Batch result files

    Extracts:
    - Task title and description
    - Completion timestamp
    - Token usage
    - Result summary
    """

    def __init__(
        self,
        batch_schedule_dir: Optional[Path] = None,
        batches_dir: Optional[Path] = None,
        batch_results_dir: Optional[Path] = None,
    ):
        """
        Initialize batch detector.

        Args:
            batch_schedule_dir: Path to batch schedule directory
            batches_dir: Path to batch results directory
            batch_results_dir: Path to markdown batch results
        """
        self.batch_schedule_dir = batch_schedule_dir or Path.home() / ".cortex" / "batch_schedule"
        self.batches_dir = batches_dir or Path.home() / ".cortex" / "batches"
        self.batch_results_dir = (
            batch_results_dir or Path.home() / "Dev" / "cortex" / "batch" / "results"
        )

    @property
    def name(self) -> str:
        return "batch"

    def supports_incremental(self) -> bool:
        return True  # Can track last processed task ID

    def detect(
        self,
        project: str,
        project_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[WorkSignal]:
        """
        Detect work signals from batch results.

        Note: project_path is ignored - batch results are global.
        We filter by project name in the task metadata.

        Args:
            project: Project name to filter by (or "all" for all projects)
            project_path: Ignored for batch detection
            since: Only tasks completed after this time
            until: Only tasks completed before this time

        Returns:
            List of WorkSignal objects
        """
        signals = []

        # Load completed tasks from schedule
        tasks = self._load_completed_tasks(since, until)

        for task in tasks:
            # Filter by project if specified
            task_project = task.get("project", "unknown")
            if project != "all" and task_project.lower() != project.lower():
                continue

            signal = self._task_to_signal(task)
            if signal:
                signals.append(signal)

        # Also scan for batch result markdown files
        result_signals = self._scan_result_files(project, since, until)
        signals.extend(result_signals)

        logger.info(f"Detected {len(signals)} batch signals")
        return signals

    def _scan_result_files(
        self,
        project: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[WorkSignal]:
        """Scan batch result markdown files for work signals."""
        signals = []

        if not self.batch_results_dir.exists():
            return signals

        # Scan date-based subdirectories
        for date_dir in self.batch_results_dir.iterdir():
            if not date_dir.is_dir():
                continue

            # Parse date from directory name (e.g., 2025-12-26)
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue

            # Apply time filters
            if since and dir_date.date() < since.date():
                continue
            if until and dir_date.date() > until.date():
                continue

            # Scan markdown files in this directory
            for md_file in date_dir.glob("*.md"):
                if md_file.name == "README.md":
                    continue

                signal = self._result_file_to_signal(md_file, dir_date, project)
                if signal:
                    signals.append(signal)

        return signals

    def _result_file_to_signal(
        self,
        md_file: Path,
        file_date: datetime,
        filter_project: str,
    ) -> Optional[WorkSignal]:
        """Convert a batch result markdown file to a WorkSignal."""
        try:
            # Parse project from filename (e.g., VortexV2_Ensemble_Models_FULL.md)
            filename = md_file.stem
            parts = filename.replace("_FULL", "").split("_")

            # Detect project from filename
            project = "unknown"
            title = filename.replace("_", " ").replace(" FULL", "")

            project_keywords = {
                "VortexV2": "VortexV2",
                "Vortex": "VortexV2",
                "Cortex": "cortex",
                "Alpha": "alpha_arena",
                "Arena": "alpha_arena",
            }

            for keyword, proj in project_keywords.items():
                if keyword.lower() in filename.lower():
                    project = proj
                    break

            # Filter by project
            if filter_project != "all" and project.lower() != filter_project.lower():
                # Also check if filter matches part of detected project
                if filter_project.lower() not in project.lower():
                    return None

            # Read first few lines for description
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            # Get title from first heading
            for line in lines[:10]:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Get description from first paragraph
            description = ""
            for i, line in enumerate(lines[:20]):
                if line.strip() and not line.startswith("#"):
                    description = line.strip()[:300]
                    break

            # Use file modification time
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)

            signal_id = WorkSignal.generate_id(
                WorkSignalType.BATCH_RESULT,
                md_file.name,
                mtime,
            )

            return WorkSignal(
                id=signal_id,
                signal_type=WorkSignalType.BATCH_RESULT,
                source_path=str(md_file),
                project=project,
                timestamp=mtime,
                title=title,
                description=description,
                scope="analysis",
                metadata={
                    "file": md_file.name,
                    "date_dir": file_date.strftime("%Y-%m-%d"),
                    "size_bytes": md_file.stat().st_size,
                },
            )

        except Exception as e:
            logger.warning(f"Failed to parse batch result file {md_file}: {e}")
            return None

    def _load_completed_tasks(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Load completed tasks from batch schedule."""
        tasks_file = self.batch_schedule_dir / "tasks.json"

        if not tasks_file.exists():
            return []

        try:
            with open(tasks_file) as f:
                data = json.load(f)

            # Handle both list format and dict format
            if isinstance(data, list):
                tasks = data
            else:
                tasks = data.get("tasks", [])
            completed = []

            for task in tasks:
                # Only completed tasks
                if task.get("status") != "completed":
                    continue

                # Parse completion time
                completed_at_str = task.get("completed_at")
                if not completed_at_str:
                    continue

                try:
                    completed_at = datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
                except ValueError:
                    continue

                # Apply time filters
                if since and completed_at < since:
                    continue
                if until and completed_at > until:
                    continue

                task["_completed_at"] = completed_at
                completed.append(task)

            return completed

        except Exception as e:
            logger.error(f"Failed to load batch tasks: {e}")
            return []

    def _task_to_signal(self, task: Dict[str, Any]) -> Optional[WorkSignal]:
        """Convert a batch task to a WorkSignal."""
        try:
            completed_at = task.get("_completed_at", datetime.now())
            task_id = task.get("id", "unknown")

            # Generate deterministic ID
            signal_id = WorkSignal.generate_id(
                WorkSignalType.BATCH_RESULT,
                task_id,
                completed_at,
            )

            # Extract project from task
            project = task.get("project", "unknown")

            # Build title from task
            title = task.get("title", task.get("name", f"Batch task {task_id}"))

            # Get description from prompt or result summary
            description = task.get("description", "")
            if not description:
                # Try to get first line of result
                result = task.get("result", "")
                if result:
                    first_line = result.split("\n")[0][:200]
                    description = f"Result: {first_line}"

            # Determine scope
            scope = self._determine_scope(task)

            # Extract achievements from result
            achievements = self._extract_achievements_from_result(task.get("result", ""))

            return WorkSignal(
                id=signal_id,
                signal_type=WorkSignalType.BATCH_RESULT,
                source_path=str(self.batch_schedule_dir / "tasks.json"),
                project=project,
                timestamp=completed_at,
                title=title,
                description=description,
                achievements=achievements,
                scope=scope,
                batch_id=task.get("batch_id"),
                tokens_used=task.get("actual_output_tokens", 0)
                + task.get("actual_input_tokens", 0),
                metadata={
                    "task_id": task_id,
                    "priority": task.get("priority", "medium"),
                    "input_tokens": task.get("actual_input_tokens", 0),
                    "output_tokens": task.get("actual_output_tokens", 0),
                },
            )

        except Exception as e:
            logger.warning(f"Failed to convert batch task: {e}")
            return None

    def _determine_scope(self, task: Dict[str, Any]) -> Optional[str]:
        """Determine scope from batch task type."""
        task_type = task.get("type", "").lower()
        title = task.get("title", "").lower()

        scope_map = {
            "analysis": "analysis",
            "review": "review",
            "research": "research",
            "planning": "planning",
            "validation": "validation",
            "test": "test",
        }

        for keyword, scope in scope_map.items():
            if keyword in task_type or keyword in title:
                return scope

        return "analysis"  # Default for batch tasks

    def _extract_achievements_from_result(self, result: str) -> List[str]:
        """Extract key findings/achievements from batch result."""
        if not result:
            return []

        achievements = []

        # Look for numbered lists or bullet points
        import re

        bullets = re.findall(r"^\s*[-*\d.]+\s+(.+)$", result, re.MULTILINE)

        for bullet in bullets[:10]:  # Limit to 10
            cleaned = bullet.strip()
            if len(cleaned) > 20:  # Skip short items
                achievements.append(cleaned[:200])

        return achievements

    def get_latest_task_id(self) -> Optional[str]:
        """Get the latest completed task ID for checkpointing."""
        tasks = self._load_completed_tasks()
        if not tasks:
            return None

        # Sort by completion time and get latest
        tasks.sort(key=lambda t: t.get("_completed_at", datetime.min), reverse=True)
        return tasks[0].get("id")
