#!/usr/bin/env python3
"""
Unified Batch Orchestrator

Intelligently routes batch jobs to the correct backend:
- Local execution (shell commands) → ProcessMonitor BatchTaskQueue
- API analysis (LLM prompts) → Anthropic Batch API via QueueManager

Provides unified interface for all batch operations.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobBackend(Enum):
    """Which backend system executes the job."""

    LOCAL = "local"  # ProcessMonitor - shell command execution
    API = "api"  # BatchQueueManager - Anthropic Batch API


class JobState(Enum):
    """Unified job state across both backends."""

    PENDING = "pending"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BaseJob:
    """Base job definition - common fields for all job types."""

    id: str = ""
    description: str = ""
    priority: Literal["immediate", "high", "normal", "low"] = "normal"
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LocalJob(BaseJob):
    """Job for local shell command execution via ProcessMonitor."""

    command: str = ""  # Shell command to execute
    task_type: str = "general"  # test, build, deploy, lint, etc.
    working_dir: Optional[Path] = None
    timeout_seconds: int = 3600
    dependencies: List[str] = field(default_factory=list)
    sprint_id: str = ""
    wave_id: str = ""


@dataclass
class APITask:
    """Single task in an API batch job."""

    task_id: str = ""
    title: str = ""
    prompt: str = ""
    context: str = ""
    files_affected: List[str] = field(default_factory=list)
    estimated_tokens: int = 2000


@dataclass
class APIJob(BaseJob):
    """Job for Anthropic Batch API analysis."""

    tasks: List[APITask] = field(default_factory=list)
    estimated_total_tokens: int = 0
    source: str = "general"  # security, docs, research, pattern, goal
    project: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)


@dataclass
class JobStatus:
    """Unified job status across backends."""

    id: str
    backend: JobBackend
    state: JobState
    description: str
    priority: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_pct: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def status_icon(self) -> str:
        """Visual icon for status."""
        icons = {
            JobState.PENDING: "⏸️",
            JobState.QUEUED: "📋",
            JobState.SCHEDULED: "⏰",
            JobState.RUNNING: "⚙️",
            JobState.COMPLETED: "✅",
            JobState.FAILED: "❌",
            JobState.CANCELLED: "🚫",
        }
        return icons.get(self.state, "❓")


class BatchOrchestrator:
    """
    Unified batch orchestrator that routes jobs to correct backend.

    Routes intelligently based on job characteristics:
    - Shell commands → ProcessMonitor (local execution)
    - LLM prompts → BatchQueueManager (API batch)
    """

    def __init__(self):
        """Initialize orchestrator with access to both backends."""
        self.queue_file = Path.home() / ".cortex" / "batches" / "remediation_queue.json"
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize queue file if it doesn't exist
        if not self.queue_file.exists():
            self._init_queue_file()

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Write JSON atomically: temp file + rename to prevent corruption."""
        import os
        import tempfile

        dir_path = str(path.parent)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.rename(tmp_path, str(path))
        except BaseException:
            # Clean up temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _init_queue_file(self):
        """Initialize empty queue file."""
        initial_queue = {
            "queue_version": "1.0",
            "created": datetime.now().isoformat(),
            "priority_jobs": [],
            "queue_metadata": {
                "total_jobs": 0,
                "total_tasks": 0,
                "estimated_total_tokens": 0,
                "auto_submit": True,
                "check_interval_seconds": 300,
            },
        }
        self._atomic_write_json(self.queue_file, initial_queue)
        logger.info(f"Initialized API batch queue: {self.queue_file}")

    def detect_job_type(self, job_data: Dict[str, Any]) -> JobBackend:
        """
        Detect whether job is local execution or API batch.

        Local indicators:
        - Has "command" field with shell command
        - Has "task_type" in known local types
        - Command starts with known tools

        API indicators:
        - Has "prompt" or "tasks" field
        - Has "description" but no "command"
        - Has "estimated_tokens" field
        - Has "source" field (security, docs, etc.)

        Args:
            job_data: Job definition dictionary

        Returns:
            JobBackend.LOCAL or JobBackend.API
        """
        # Strong LOCAL indicators
        if "command" in job_data:
            logger.debug("Detected LOCAL job: has 'command' field")
            return JobBackend.LOCAL

        local_task_types = {"test", "build", "deploy", "lint", "format", "analyze"}
        if job_data.get("task_type") in local_task_types:
            logger.debug(f"Detected LOCAL job: task_type={job_data['task_type']}")
            return JobBackend.LOCAL

        # Strong API indicators
        if "tasks" in job_data or "prompt" in job_data:
            logger.debug("Detected API job: has 'tasks' or 'prompt' field")
            return JobBackend.API

        if "estimated_tokens" in job_data or "estimated_total_tokens" in job_data:
            logger.debug("Detected API job: has token estimation")
            return JobBackend.API

        api_sources = {"security", "docs", "research", "pattern", "goal"}
        if job_data.get("source") in api_sources:
            logger.debug(f"Detected API job: source={job_data['source']}")
            return JobBackend.API

        # Default to LOCAL for backward compatibility
        logger.warning(
            f"Ambiguous job type, defaulting to LOCAL: {job_data.get('description', 'unknown')}"
        )
        return JobBackend.LOCAL

    def submit_job(
        self, job_data: Union[Dict[str, Any], LocalJob, APIJob], auto_detect: bool = True
    ) -> str:
        """
        Submit a job to appropriate backend.

        Args:
            job_data: Job definition (dict, LocalJob, or APIJob)
            auto_detect: Auto-detect backend from job type (default: True)

        Returns:
            job_id with backend prefix (local_* or api_*)
        """
        # Convert dataclass to dict if needed
        if isinstance(job_data, (LocalJob, APIJob)):
            backend = JobBackend.LOCAL if isinstance(job_data, LocalJob) else JobBackend.API
            job_dict = self._job_to_dict(job_data)
        else:
            job_dict = job_data
            backend = self.detect_job_type(job_dict) if auto_detect else None

        # Route to correct backend
        if backend == JobBackend.LOCAL:
            job_id = self._submit_to_local(job_dict)
            return f"local_{job_id}"
        else:
            job_id = self._submit_to_api(job_dict)
            return f"api_{job_id}"

    def _job_to_dict(self, job: Union[LocalJob, APIJob]) -> Dict[str, Any]:
        """Convert job dataclass to dictionary."""
        if isinstance(job, LocalJob):
            return {
                "id": job.id,
                "command": job.command,
                "description": job.description,
                "priority": job.priority,
                "task_type": job.task_type,
                "working_dir": str(job.working_dir) if job.working_dir else None,
                "timeout_seconds": job.timeout_seconds,
                "dependencies": job.dependencies,
                "sprint_id": job.sprint_id,
                "wave_id": job.wave_id,
                "metadata": job.metadata,
            }
        else:  # APIJob
            return {
                "id": job.id,
                "description": job.description,
                "priority": job.priority,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "title": t.title,
                        "prompt": t.prompt,
                        "context": t.context,
                        "files_affected": t.files_affected,
                        "estimated_tokens": t.estimated_tokens,
                    }
                    for t in job.tasks
                ],
                "estimated_total_tokens": job.estimated_total_tokens,
                "source": job.source,
                "project": job.project,
                "depends_on": job.depends_on,
                "metadata": job.metadata,
            }

    def _submit_to_local(self, job_data: Dict[str, Any]) -> str:
        """
        Submit job to ProcessMonitor BatchTaskQueue.

        Args:
            job_data: Job definition

        Returns:
            task_id (without prefix)
        """
        try:
            from intelligence.process_monitor import ProcessMonitor
        except ImportError:
            try:
                from cortex.intelligence.process_monitor import ProcessMonitor
            except ImportError:
                from process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        task = monitor.batch_queue.add_task(
            command=job_data["command"],
            task_type=job_data.get("task_type", "general"),
            description=job_data.get("description", job_data["command"]),
            priority=job_data.get("priority", "normal"),
            estimated_duration_minutes=job_data.get("estimated_duration_minutes", 10.0),
            metadata=job_data.get("metadata", {}),
            dependencies=job_data.get("dependencies", []),
            sprint_id=job_data.get("sprint_id", ""),
            wave_id=job_data.get("wave_id", ""),
        )

        logger.info(f"✅ Submitted to LOCAL backend: {task.task_id}")
        return task.task_id

    def _submit_to_api(self, job_data: Dict[str, Any]) -> str:
        """
        Submit job to unified SQLite batch queue.

        Each task in the job becomes a separate BatchTask in SQLite,
        which the submitter.py daemon picks up and sends to Anthropic.

        Args:
            job_data: Job definition with tasks list

        Returns:
            job_id (without prefix)
        """
        try:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue
        except ImportError:
            try:
                from cortex.intelligence.process_monitor.batch_queue import BatchTaskQueue
            except ImportError:
                # Fallback: write to JSON queue for backward compatibility
                return self._submit_to_api_json_legacy(job_data)

        queue = BatchTaskQueue()
        job_id = job_data.get("id", f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        tasks = job_data.get("tasks", [])

        # Map source to task_type for AI routing
        source_to_type = {
            "security": "security",
            "docs": "documentation",
            "research": "research",
            "pattern": "pattern",
            "goal": "analysis",
            "general": "ai_inference",
        }
        task_type = source_to_type.get(job_data.get("source", "general"), "ai_inference")

        tasks_added = 0
        for task in tasks:
            prompt = task.get("prompt", "")
            if not prompt:
                continue

            queue.add_task(
                command=prompt,
                task_type=task_type,
                description=task.get("title", job_data.get("description", "")),
                priority=job_data.get("priority", "normal").lower(),
                metadata={
                    "api_job_id": job_id,
                    "source": job_data.get("source", "general"),
                    "project": job_data.get("project"),
                    "title": task.get("title", ""),
                    "files_affected": task.get("files_affected", []),
                    "estimated_tokens": task.get("estimated_tokens", 0),
                    "context": task.get("context", ""),
                },
            )
            tasks_added += 1

        # If job has no tasks but has a description/prompt, add it directly
        if not tasks and job_data.get("description"):
            prompt = job_data.get("prompt", job_data["description"])
            queue.add_task(
                command=prompt,
                task_type=task_type,
                description=job_data["description"],
                priority=job_data.get("priority", "normal").lower(),
                metadata={
                    "api_job_id": job_id,
                    "source": job_data.get("source", "general"),
                    "project": job_data.get("project"),
                },
            )
            tasks_added = 1

        logger.info(f"✅ Submitted to SQLite queue: {job_id} ({tasks_added} tasks)")
        return job_id

    def _submit_to_api_json_legacy(self, job_data: Dict[str, Any]) -> str:
        """Legacy fallback: write to JSON queue if SQLite imports fail."""
        job_id = job_data.get("id", f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        logger.warning(f"Using legacy JSON queue for {job_id} (SQLite unavailable)")

        try:
            with open(self.queue_file) as f:
                queue_data = json.load(f)
        except Exception:
            self._init_queue_file()
            with open(self.queue_file) as f:
                queue_data = json.load(f)

        job_definition = {
            "id": job_id,
            "priority": job_data.get("priority", "normal").upper(),
            "status": "queued",
            "description": job_data["description"],
            "tasks": job_data.get("tasks", []),
            "queued_at": datetime.now().isoformat(),
        }
        queue_data["priority_jobs"].append(job_definition)
        self._atomic_write_json(self.queue_file, queue_data)
        return job_id

    def sync_to_daemon(self) -> int:
        """
        Sync queued jobs to daemon.

        With the unified SQLite pipeline, _submit_to_api() writes directly
        to SQLite so this is a no-op for new jobs. Kept for backward
        compatibility with callers that still invoke it.
        """
        logger.debug("sync_to_daemon called — no-op with unified SQLite pipeline")
        return 0

    def get_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Get status for a job from either backend.

        Args:
            job_id: Job ID (with or without backend prefix)

        Returns:
            JobStatus or None if not found
        """
        # Parse backend from ID
        if job_id.startswith("local_"):
            return self._get_local_status(job_id.replace("local_", ""))
        elif job_id.startswith("api_"):
            return self._get_api_status(job_id.replace("api_", ""))
        else:
            # Try both backends
            status = self._get_local_status(job_id)
            if status:
                return status
            return self._get_api_status(job_id)

    def _get_local_status(self, task_id: str) -> Optional[JobStatus]:
        """Get status from ProcessMonitor."""
        try:
            try:
                from intelligence.process_monitor import ProcessMonitor
            except ImportError:
                try:
                    from cortex.intelligence.process_monitor import ProcessMonitor
                except ImportError:
                    from process_monitor import ProcessMonitor

            monitor = ProcessMonitor()
            task = monitor.batch_queue.get_task(task_id)

            if not task:
                return None

            # Map ProcessMonitor state to JobState
            state_mapping = {
                "pending": JobState.PENDING,
                "scheduled": JobState.SCHEDULED,
                "running": JobState.RUNNING,
                "completed": JobState.COMPLETED,
                "failed": JobState.FAILED,
                "cancelled": JobState.CANCELLED,
            }

            return JobStatus(
                id=f"local_{task.task_id}",
                backend=JobBackend.LOCAL,
                state=state_mapping.get(task.state.value, JobState.PENDING),
                description=task.description,
                priority=task.priority,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                error_message=task.error_message if task.error_message else None,
                metadata={
                    "command": task.command,
                    "task_type": task.task_type,
                    "exit_code": task.exit_code,
                },
            )
        except Exception as e:
            logger.error(f"Error getting local status for {task_id}: {e}")
            return None

    def _get_api_status(self, job_id: str) -> Optional[JobStatus]:
        """Get status from API batch queue."""
        try:
            with open(self.queue_file) as f:
                queue_data = json.load(f)

            for job in queue_data.get("priority_jobs", []):
                if job["id"] == job_id:
                    # Map queue status to JobState
                    state_mapping = {
                        "queued": JobState.QUEUED,
                        "submitted": JobState.RUNNING,
                        "completed": JobState.COMPLETED,
                        "failed": JobState.FAILED,
                    }

                    state = state_mapping.get(job["status"], JobState.QUEUED)

                    # Calculate progress if available
                    progress = 0.0
                    if "final_status" in job:
                        progress = job["final_status"].get("progress_percentage", 0.0)

                    return JobStatus(
                        id=f"api_{job['id']}",
                        backend=JobBackend.API,
                        state=state,
                        description=job["description"],
                        priority=job["priority"].lower(),
                        created_at=datetime.now(),  # Not stored in queue
                        started_at=(
                            datetime.fromisoformat(job["submitted_at"])
                            if "submitted_at" in job
                            else None
                        ),
                        completed_at=(
                            datetime.fromisoformat(job["completed_at"])
                            if "completed_at" in job
                            else None
                        ),
                        progress_pct=progress,
                        metadata={
                            "batch_id": job.get("batch_id"),
                            "tasks": len(job.get("tasks", [])),
                            "tokens": job.get("estimated_total_tokens", 0),
                        },
                    )

            return None
        except Exception as e:
            logger.error(f"Error getting API status for {job_id}: {e}")
            return None

    def list_jobs(
        self, backend: Optional[Literal["local", "api", "both"]] = "both", limit: int = 50
    ) -> List[JobStatus]:
        """
        List jobs from one or both backends.

        Args:
            backend: Which backend to query ("local", "api", or "both")
            limit: Maximum jobs to return per backend

        Returns:
            List of JobStatus objects
        """
        jobs = []

        if backend in ["local", "both"]:
            jobs.extend(self._list_local_jobs(limit))

        if backend in ["api", "both"]:
            jobs.extend(self._list_api_jobs(limit))

        # Sort by created_at desc
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def _list_local_jobs(self, limit: int) -> List[JobStatus]:
        """List jobs from ProcessMonitor."""
        try:
            try:
                from intelligence.process_monitor import ProcessMonitor
            except ImportError:
                try:
                    from cortex.intelligence.process_monitor import ProcessMonitor
                except ImportError:
                    from process_monitor import ProcessMonitor

            monitor = ProcessMonitor()
            tasks = monitor.batch_queue.get_task_history(limit=limit)

            return [self._get_local_status(task.task_id) for task in tasks if task.task_id]
        except Exception as e:
            logger.error(f"Error listing local jobs: {e}")
            return []

    def _list_api_jobs(self, limit: int) -> List[JobStatus]:
        """List jobs from API batch queue."""
        try:
            with open(self.queue_file) as f:
                queue_data = json.load(f)

            jobs = []
            for job in queue_data.get("priority_jobs", [])[:limit]:
                status = self._get_api_status(job["id"])
                if status:
                    jobs.append(status)

            return jobs
        except Exception as e:
            logger.error(f"Error listing API jobs: {e}")
            return []


def main():
    """CLI for testing orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="Unified Batch Orchestrator")
    parser.add_argument("action", choices=["submit", "status", "list"], help="Action to perform")
    parser.add_argument("--job-file", type=Path, help="Job definition JSON file")
    parser.add_argument("--job-id", help="Job ID for status lookup")
    parser.add_argument(
        "--backend", choices=["local", "api", "both"], default="both", help="Backend filter"
    )
    parser.add_argument("--limit", type=int, default=50, help="Max jobs to list")

    args = parser.parse_args()

    orchestrator = BatchOrchestrator()

    if args.action == "submit":
        if not args.job_file:
            print("Error: --job-file required for submit")
            return

        with open(args.job_file) as f:
            job_data = json.load(f)

        job_id = orchestrator.submit_job(job_data, auto_detect=True)
        backend = "LOCAL" if job_id.startswith("local_") else "API"
        print(f"✅ Job submitted to {backend} backend")
        print(f"Job ID: {job_id}")

    elif args.action == "status":
        if not args.job_id:
            print("Error: --job-id required for status")
            return

        status = orchestrator.get_status(args.job_id)
        if status:
            print(f"\n{status.status_icon} {status.description}")
            print(f"Backend: {status.backend.value}")
            print(f"State: {status.state.value}")
            print(f"Priority: {status.priority}")
            if status.progress_pct > 0:
                print(f"Progress: {status.progress_pct:.1f}%")
        else:
            print(f"Job not found: {args.job_id}")

    elif args.action == "list":
        jobs = orchestrator.list_jobs(backend=args.backend, limit=args.limit)

        # Group by backend
        local_jobs = [j for j in jobs if j.backend == JobBackend.LOCAL]
        api_jobs = [j for j in jobs if j.backend == JobBackend.API]

        if local_jobs:
            print("\n" + "=" * 80)
            print("LOCAL EXECUTION QUEUE (ProcessMonitor)")
            print("=" * 80)
            for job in local_jobs:
                print(f"{job.status_icon} [{job.priority.upper():8}] {job.description}")
                print(f"   ID: {job.id} | State: {job.state.value}")

        if api_jobs:
            print("\n" + "=" * 80)
            print("API BATCH QUEUE (Anthropic)")
            print("=" * 80)
            for job in api_jobs:
                print(f"{job.status_icon} [{job.priority.upper():8}] {job.description}")
                print(f"   ID: {job.id} | State: {job.state.value}")
                if job.metadata.get("tokens"):
                    print(
                        f"   Tokens: {job.metadata['tokens']:,} | Tasks: {job.metadata.get('tasks', 0)}"
                    )

        print(f"\nTotal: {len(jobs)} jobs ({len(local_jobs)} local, {len(api_jobs)} api)")


if __name__ == "__main__":
    main()
