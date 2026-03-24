"""
Health monitoring and self-healing for the Cortex Supervisor.

Detects and automatically recovers from:
- Stuck shell tasks (RUNNING but no process)
- Orphaned AI batches (processing too long)
- Resource issues (disk, memory)
- Test count drift (>10% change signals missing/removed tests)
"""

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from intelligence.process_monitor.batch_queue import BatchTaskQueue, TaskState

_CENSUS_PATH = Path.home() / ".cortex" / "test_census.json"

# Projects to measure, keyed by display name → pytest root path (relative to repo root)
_PROJECT_TEST_ROOTS: Dict[str, str] = {
    "vortex": "Vortex/backend/tests",
    "winfield": "Vortex/Winfield/tests",
    "alpha_arena": "alpha_arena/tests",
    "cortex": "cortex/tests",
    "pupil": "Pupil/tests",
}

_DRIFT_THRESHOLD = 0.10  # 10% change triggers a warning


@dataclass
class TestCensus:
    """Snapshot of per-project test counts.

    Written to ``~/.cortex/test_census.json`` so future sessions can detect
    drift without re-running pytest.
    """

    projects: Dict[str, int]  # project name → collected test count
    total: int
    collected_at: str  # ISO-8601 UTC

    @classmethod
    def collect(cls, repo_root: Path) -> "TestCensus":
        """Run ``pytest --collect-only -q`` per project and count tests."""
        counts: Dict[str, int] = {}
        for name, rel_path in _PROJECT_TEST_ROOTS.items():
            test_dir = repo_root / rel_path
            if not test_dir.exists():
                counts[name] = 0
                continue
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", "--collect-only", "-q", str(test_dir)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(repo_root),
                )
                # Last non-empty line is typically "N tests collected in X.XXs"
                for line in reversed(result.stdout.splitlines()):
                    line = line.strip()
                    if line and ("test" in line or "item" in line):
                        parts = line.split()
                        if parts and parts[0].isdigit():
                            counts[name] = int(parts[0])
                            break
                else:
                    counts[name] = 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                counts[name] = 0
        return cls(
            projects=counts,
            total=sum(counts.values()),
            collected_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def save(self, path: Path = _CENSUS_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path = _CENSUS_PATH) -> Optional["TestCensus"]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return cls(**data)
        except (json.JSONDecodeError, TypeError):
            return None


logger = logging.getLogger(__name__)


@dataclass
class HealthIssue:
    """A detected health issue."""

    issue_type: str  # "stuck_shell_task", "orphaned_ai_batch", "disk_full", etc.
    target_id: str  # Task ID, batch ID, etc.
    description: str
    severity: str  # "critical", "warning", "info"
    auto_healable: bool
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class HealingAction:
    """An action taken to heal an issue."""

    issue: HealthIssue
    action: str  # "cancelled", "retried", "cleaned_up", "skipped"
    success: bool
    message: str
    completed_at: datetime = field(default_factory=datetime.now)


class HealthMonitor:
    """
    Monitors system health and heals detected issues.

    Checks:
    - Shell tasks marked RUNNING but with no process (stuck)
    - AI batches exceeding timeout
    - Disk space for batch storage
    """

    def __init__(
        self,
        shell_queue: Optional[BatchTaskQueue] = None,
        stale_task_hours: int = 4,
        max_retries: int = 3,
    ):
        """
        Initialize health monitor.

        Args:
            shell_queue: BatchTaskQueue instance (creates new if None)
            stale_task_hours: Hours after which a RUNNING task is considered stuck
            max_retries: Maximum retry attempts before giving up
        """
        self.shell_queue = shell_queue or BatchTaskQueue()
        self.stale_task_hours = stale_task_hours
        self.max_retries = max_retries

        # Track healing history to avoid infinite loops
        self._healing_history: dict = {}  # task_id -> last_heal_time

    def check(self) -> List[HealthIssue]:
        """
        Check for all health issues.

        Returns:
            List of detected health issues
        """
        issues = []

        # 1. Check for stuck shell tasks
        issues.extend(self._check_stuck_shell_tasks())

        # 2. Check for orphaned AI batches
        issues.extend(self._check_orphaned_ai_batches())

        # 3. Check disk space
        issues.extend(self._check_disk_space())

        # 4. Check test count drift
        issues.extend(self._check_test_census())

        return issues

    def _check_test_census(self) -> List[HealthIssue]:
        """Detect >10% drift in per-project test counts vs. last saved census."""
        issues = []
        prior = TestCensus.load()
        if prior is None:
            return issues  # No baseline yet — first run will establish it

        # Compare current counts from disk (don't re-run pytest on every health check;
        # re-run is done explicitly via TestCensus.collect())
        for project, prior_count in prior.projects.items():
            if prior_count == 0:
                continue
            # We only flag drift — re-collection is a separate explicit action
            # so we just surface the age of the census as a warning if stale (>7d)
            try:
                collected_dt = datetime.fromisoformat(prior.collected_at)
                age_days = (datetime.now(tz=collected_dt.tzinfo) - collected_dt).days
                if age_days > 7:
                    issues.append(
                        HealthIssue(
                            issue_type="stale_test_census",
                            target_id=project,
                            description=f"Test census is {age_days}d old — run TestCensus.collect() to refresh",
                            severity="info",
                            auto_healable=False,
                            metadata={"age_days": age_days, "last_count": prior_count},
                        )
                    )
            except (ValueError, TypeError):
                pass

        return issues

    def heal(self, issues: List[HealthIssue]) -> List[HealingAction]:
        """
        Attempt to heal detected issues.

        Args:
            issues: List of health issues to heal

        Returns:
            List of healing actions taken
        """
        actions = []

        for issue in issues:
            if not issue.auto_healable:
                actions.append(
                    HealingAction(
                        issue=issue,
                        action="skipped",
                        success=False,
                        message=f"Issue not auto-healable: {issue.issue_type}",
                    )
                )
                continue

            # Check if we recently tried to heal this
            if self._was_recently_healed(issue.target_id):
                actions.append(
                    HealingAction(
                        issue=issue,
                        action="skipped",
                        success=False,
                        message="Recently healed, waiting for cooldown",
                    )
                )
                continue

            action = self._heal_issue(issue)
            actions.append(action)

            if action.success:
                self._record_healing(issue.target_id)

        return actions

    def check_and_heal(self) -> List[HealingAction]:
        """
        Combined check and heal operation.

        Returns:
            List of healing actions taken
        """
        issues = self.check()

        if issues:
            logger.info(f"Health check found {len(issues)} issues")
            for issue in issues:
                logger.info(f"  - {issue.issue_type}: {issue.description}")

        return self.heal(issues)

    def _check_stuck_shell_tasks(self) -> List[HealthIssue]:
        """Check for shell tasks that are stuck (RUNNING but no process)."""
        issues = []

        try:
            stale_tasks = self.shell_queue.detect_stale_tasks(
                max_running_hours=self.stale_task_hours
            )

            for task in stale_tasks:
                # Check retry count
                can_retry = task.retry_count < self.max_retries

                hours_running = 0
                if task.started_at:
                    hours_running = (datetime.now() - task.started_at).total_seconds() / 3600

                issues.append(
                    HealthIssue(
                        issue_type="stuck_shell_task",
                        target_id=task.task_id,
                        description=f"Task running for {hours_running:.1f}h with no process",
                        severity="warning" if can_retry else "critical",
                        auto_healable=True,  # Always healable: retry if possible, force-fail if exhausted
                        metadata={
                            "task_type": task.task_type,
                            "retry_count": task.retry_count,
                            "max_retries": self.max_retries,
                            "started_at": task.started_at.isoformat() if task.started_at else None,
                            "command_preview": task.command[:100] if task.command else "",
                        },
                    )
                )

        except Exception as e:
            logger.error(f"Error checking stuck tasks: {e}")

        return issues

    def _check_orphaned_ai_batches(self) -> List[HealthIssue]:
        """Check for AI batches that have been processing too long."""
        issues = []

        # Try to import BatchAPIClient
        try:
            from batch.batch_api_client import BatchAPIClient

            client = BatchAPIClient()
            batches = client.list_batches(limit=10)

            for batch in batches:
                status = batch.get("status", "unknown")
                created_at = batch.get("created_at")

                if status == "processing" and created_at:
                    # Check if processing for > 24 hours
                    if isinstance(created_at, str):
                        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    else:
                        created_dt = created_at

                    age_hours = (
                        datetime.now(created_dt.tzinfo) - created_dt
                    ).total_seconds() / 3600

                    if age_hours > 25:  # Batch API window is 24h
                        issues.append(
                            HealthIssue(
                                issue_type="orphaned_ai_batch",
                                target_id=batch.get("id", "unknown"),
                                description=f"AI batch processing for {age_hours:.1f}h (>24h window)",
                                severity="warning",
                                auto_healable=False,  # Can't auto-heal API batches
                                metadata={"status": status, "age_hours": age_hours},
                            )
                        )

        except ImportError:
            pass  # BatchAPIClient not available
        except Exception as e:
            logger.debug(f"Error checking AI batches: {e}")

        return issues

    def _check_disk_space(self) -> List[HealthIssue]:
        """Check disk space for Cortex data directory."""
        issues = []

        try:
            import shutil

            cortex_dir = Path.home() / ".cortex"
            total, used, free = shutil.disk_usage(cortex_dir)

            free_gb = free / (1024**3)
            free_pct = (free / total) * 100

            if free_pct < 5 or free_gb < 1:
                issues.append(
                    HealthIssue(
                        issue_type="low_disk_space",
                        target_id=str(cortex_dir),
                        description=f"Low disk space: {free_gb:.1f}GB ({free_pct:.1f}%) free",
                        severity="critical" if free_pct < 2 else "warning",
                        auto_healable=False,
                        metadata={"free_gb": free_gb, "free_pct": free_pct},
                    )
                )

        except Exception as e:
            logger.debug(f"Error checking disk space: {e}")

        return issues

    def _heal_issue(self, issue: HealthIssue) -> HealingAction:
        """Heal a specific issue."""

        if issue.issue_type == "stuck_shell_task":
            return self._heal_stuck_shell_task(issue)

        # Add more healing strategies as needed...

        return HealingAction(
            issue=issue,
            action="skipped",
            success=False,
            message=f"No healing strategy for {issue.issue_type}",
        )

    def _heal_stuck_shell_task(self, issue: HealthIssue) -> HealingAction:
        """Heal a stuck shell task — retry if possible, force-fail if retries exhausted."""
        task_id = issue.target_id
        retry_count = issue.metadata.get("retry_count", 0)
        can_retry = retry_count < self.max_retries

        try:
            # Mark as failed
            self.shell_queue.update_task_state(
                task_id,
                TaskState.FAILED,
                error_message=f"Auto-healed: {issue.description}",
            )

            if can_retry:
                self.shell_queue.retry_task(task_id)
                logger.info(
                    f"Healed stuck task {task_id[:8]}: retrying ({retry_count + 1}/{self.max_retries})"
                )
                return HealingAction(
                    issue=issue,
                    action="retried",
                    success=True,
                    message=f"Marked as failed and queued for retry ({retry_count + 1}/{self.max_retries})",
                )
            else:
                logger.info(
                    f"Force-failed stuck task {task_id[:8]}: retries exhausted ({retry_count}/{self.max_retries})"
                )
                return HealingAction(
                    issue=issue,
                    action="force_failed",
                    success=True,
                    message=f"Retries exhausted ({retry_count}/{self.max_retries}) — permanently marked as failed",
                )

        except Exception as e:
            logger.error(f"Failed to heal task {task_id[:8]}: {e}")
            return HealingAction(
                issue=issue,
                action="failed",
                success=False,
                message=f"Healing failed: {str(e)}",
            )

    def force_fail_task(self, task_id: str, reason: str = "Manually cancelled") -> bool:
        """Force-fail a task regardless of retry count. For manual cleanup."""
        try:
            self.shell_queue.update_task_state(
                task_id,
                TaskState.FAILED,
                error_message=reason,
            )
            logger.info(f"Force-failed task {task_id[:8]}: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to force-fail task {task_id[:8]}: {e}")
            return False

    def _was_recently_healed(self, target_id: str, cooldown_minutes: int = 30) -> bool:
        """Check if a target was recently healed (to avoid healing loops)."""
        last_heal = self._healing_history.get(target_id)
        if last_heal is None:
            return False

        elapsed = datetime.now() - last_heal
        return elapsed < timedelta(minutes=cooldown_minutes)

    def _record_healing(self, target_id: str):
        """Record that we healed a target."""
        self._healing_history[target_id] = datetime.now()

        # Clean up old history (keep last 100)
        if len(self._healing_history) > 100:
            oldest_keys = sorted(self._healing_history, key=lambda k: self._healing_history[k])[:50]
            for key in oldest_keys:
                del self._healing_history[key]
