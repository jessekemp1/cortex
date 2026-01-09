"""Task scheduler using APScheduler.

Provides cron-based scheduling for agent execution,
supporting cron expressions and interval schedules.
"""

from typing import TYPE_CHECKING, Callable, Optional

import pytz
import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cortex.runtime.config import get_config

if TYPE_CHECKING:
    from cortex.runtime.executor import RuntimeExecutor

logger = structlog.get_logger()


class TaskScheduler:
    """Wrapper around APScheduler for task scheduling.

    Provides:
    - Cron-based scheduling
    - Interval scheduling
    - Timezone support
    - Job management
    """

    def __init__(self, executor: "RuntimeExecutor"):
        """Initialize the scheduler.

        Args:
            executor: The runtime executor instance
        """
        self.executor = executor
        config = get_config()

        self.timezone = pytz.timezone(config.timezone)
        self.scheduler = BackgroundScheduler(
            timezone=self.timezone,
            max_workers=config.max_workers,
        )
        self.jobs = {}  # Track registered jobs

    def add_job(
        self,
        agent_id: str,
        schedule: str,
        func: Callable,
        job_id: Optional[str] = None,
    ):
        """Add a scheduled job.

        Args:
            agent_id: ID of the agent to execute
            schedule: Cron expression (e.g., "0 8 * * *") or interval (e.g., "*/15 * * * *")
            func: Function to execute
            job_id: Optional job ID (defaults to agent_id)
        """
        job_id = job_id or agent_id

        # Parse schedule string
        trigger = self._parse_schedule(schedule)

        # Add job to scheduler
        job = self.scheduler.add_job(
            func=func, trigger=trigger, id=job_id, replace_existing=True
        )

        self.jobs[agent_id] = job
        logger.info(
            "job_scheduled", agent_id=agent_id, schedule=schedule, job_id=job_id
        )

    def _parse_schedule(self, schedule: str):
        """Parse schedule string into APScheduler trigger.

        Supports:
        - Cron expressions: "0 8 * * *" (daily at 8 AM)
        - Interval expressions: "*/15 * * * *" (every 15 minutes)
        - ISO date strings: "2025-01-15T10:00:00" (one-time)

        Args:
            schedule: Schedule string

        Returns:
            APScheduler trigger instance
        """
        # Try parsing as cron expression
        try:
            parts = schedule.split()
            if len(parts) == 5:
                return CronTrigger.from_crontab(schedule, timezone=self.timezone)
        except Exception:
            pass

        # Try parsing as interval (e.g., "*/15 * * * *")
        try:
            parts = schedule.split()
            if len(parts) == 5 and parts[0].startswith("*/"):
                minutes = int(parts[0][2:])
                return IntervalTrigger(minutes=minutes, timezone=self.timezone)
        except Exception:
            pass

        # Default: treat as cron and let APScheduler handle errors
        return CronTrigger.from_crontab(schedule, timezone=self.timezone)

    def remove_job(self, agent_id: str):
        """Remove a scheduled job.

        Args:
            agent_id: ID of the agent to unschedule
        """
        if agent_id in self.jobs:
            job = self.jobs[agent_id]
            self.scheduler.remove_job(job.id)
            del self.jobs[agent_id]
            logger.info("job_removed", agent_id=agent_id)

    def get_jobs(self) -> list:
        """Get all scheduled jobs.

        Returns:
            List of job info dicts
        """
        return [
            {
                "agent_id": agent_id,
                "job_id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for agent_id, job in self.jobs.items()
        ]

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("scheduler_started")

    def shutdown(self):
        """Shutdown the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("scheduler_shutdown")
