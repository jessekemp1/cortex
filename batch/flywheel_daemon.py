#!/usr/bin/env python3
"""
Development Flywheel Daemon

Continuously monitors batch queue depth and auto-generates work to maintain
12+ hours of queued jobs. This is the heart of the "always-full queue" strategy.

Key Features:
- Monitors queue depth every 5 minutes
- Auto-fills when below 12-hour threshold
- Three-phase filling: quick fills → standard fills → backlog fills
- Integrates with DynamicWorkGenerator and IntelligentBatchOrchestrator
- Health reporting via ~/.cortex/flywheel/status.json
- Graceful shutdown on SIGTERM/SIGINT

Usage:
    # Start daemon (foreground)
    python flywheel_daemon.py

    # Start daemon (background via launchd)
    launchctl load ~/Library/LaunchAgents/com.cortex.flywheel.plist

    # Check status
    python flywheel_daemon.py --status

    # Stop daemon
    python flywheel_daemon.py --stop
"""

import json
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.intelligent_orchestrator import BatchWorkItem, IntelligentBatchOrchestrator
from batch.optimizer import CapacityAwareQueueFiller, DynamicWorkGenerator


@dataclass
class FlywheelStatus:
    """Current flywheel daemon status"""

    running: bool = False
    last_check: Optional[str] = None
    queue_depth_hours: float = 0.0
    jobs_queued: int = 0
    jobs_added_today: int = 0
    last_fill_action: Optional[str] = None
    health: str = "unknown"  # "healthy", "warning", "critical"
    pid: Optional[int] = None
    uptime_hours: float = 0.0


@dataclass
class FlywheelConfig:
    """Flywheel daemon configuration"""

    # Queue depth thresholds (hours)
    target_depth_hours: float = 12.0
    warning_depth_hours: float = 8.0
    critical_depth_hours: float = 4.0

    # Check interval
    check_interval_seconds: int = 300  # 5 minutes

    # Fill limits per cycle
    max_fills_per_cycle: int = 10

    # Auto-fill control — set False to make daemon monitor-only (no API spend)
    auto_fill_enabled: bool = False

    # Time windows (don't fill during work hours)
    quiet_start_hour: int = 9  # 9 AM
    quiet_end_hour: int = 17  # 5 PM
    aggressive_fill_hours: List[int] = None  # 6 PM - 6 AM

    # Paths
    status_file: Path = Path.home() / ".cortex" / "flywheel" / "status.json"
    log_file: Path = Path.home() / ".cortex" / "flywheel" / "daemon.log"
    pid_file: Path = Path.home() / ".cortex" / "flywheel" / "daemon.pid"

    def __post_init__(self):
        if self.aggressive_fill_hours is None:
            self.aggressive_fill_hours = list(range(18, 24)) + list(range(0, 6))

        # Ensure directories exist
        self.status_file.parent.mkdir(parents=True, exist_ok=True)


class FlywheelDaemon:
    """
    Development Flywheel - keeps batch queue perpetually full.

    The flywheel ensures there's always 12+ hours of batch work queued,
    enabling continuous overnight processing and maximum API utilization.
    """

    def __init__(self, config: Optional[FlywheelConfig] = None):
        self.config = config or FlywheelConfig()
        self.running = False
        self.start_time: Optional[datetime] = None
        self.jobs_added_today = 0
        self.last_fill_date: Optional[str] = None

        # Initialize generators
        self.dynamic_generator = DynamicWorkGenerator()
        self.orchestrator = IntelligentBatchOrchestrator()
        self.queue_filler = CapacityAwareQueueFiller()

        # Status tracking
        self.status = FlywheelStatus()

    def start(self):
        """Start the flywheel daemon"""
        self.running = True
        self.start_time = datetime.now()
        self.status.pid = os.getpid()

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        # Write PID file
        self.config.pid_file.write_text(str(os.getpid()))

        self._log("Flywheel daemon started")
        self._update_status()

        try:
            self._run_loop()
        finally:
            self._cleanup()

    def _run_loop(self):
        """Main daemon loop"""
        while self.running:
            try:
                self._check_and_fill()
            except Exception as e:
                self._log(f"Error in check cycle: {e}", level="error")

            # Sleep until next check
            time.sleep(self.config.check_interval_seconds)

    def _check_and_fill(self):
        """Check queue depth and fill if needed.

        Before checking fill level, runs the unified submit/retrieve cycle
        to push PENDING tasks to Anthropic and pull completed results.
        """
        # Reset daily counter if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_fill_date != today:
            self.jobs_added_today = 0
            self.last_fill_date = today

        # Run unified submit/retrieve cycle before measuring depth
        self._run_batch_cycle()

        # Get current queue depth
        queue_depth = self._get_queue_depth_hours()
        self.status.queue_depth_hours = queue_depth
        self.status.last_check = datetime.now().isoformat()

        # Determine health status
        if queue_depth >= self.config.target_depth_hours:
            self.status.health = "healthy"
        elif queue_depth >= self.config.warning_depth_hours:
            self.status.health = "warning"
        else:
            self.status.health = "critical"

        # Monitor-only mode — skip all fill logic
        if not self.config.auto_fill_enabled:
            self._log(f"Auto-fill disabled (monitor-only). Queue at {queue_depth:.1f}h.")
            self._update_status()
            return

        # Check if we should fill
        current_hour = datetime.now().hour
        is_quiet_hours = self.config.quiet_start_hour <= current_hour < self.config.quiet_end_hour

        # During quiet hours, only fill if critical
        if is_quiet_hours and queue_depth >= self.config.critical_depth_hours:
            self._log(f"Quiet hours, queue at {queue_depth:.1f}h - skipping fill")
            self._update_status()
            return

        # Determine fill strategy
        if queue_depth < self.config.critical_depth_hours:
            self._fill_phase_3_backlog()
            self._fill_phase_2_standard()
            self._fill_phase_1_quick()
        elif queue_depth < self.config.warning_depth_hours:
            self._fill_phase_2_standard()
            self._fill_phase_1_quick()
        elif queue_depth < self.config.target_depth_hours:
            self._fill_phase_1_quick()
        else:
            self._log(f"Queue healthy at {queue_depth:.1f}h - no fill needed")

        self._update_status()

    def _fill_phase_1_quick(self):
        """Phase 1: Quick fills - recent commits, TODOs, test failures"""
        self._log("Phase 1: Quick fills")
        self.status.last_fill_action = "phase_1_quick"

        jobs_added = 0

        # Recent commit analysis
        commit_jobs = self.dynamic_generator.scan_recent_commits(hours=24)
        for job in commit_jobs[:3]:
            if self._submit_job(job):
                jobs_added += 1

        # TODO/FIXME scan
        todo_jobs = self.dynamic_generator.scan_todos_and_fixmes()
        for job in todo_jobs[:2]:
            if self._submit_job(job):
                jobs_added += 1

        # Test failures
        test_jobs = self.dynamic_generator.scan_test_failures()
        for job in test_jobs[:2]:
            if self._submit_job(job):
                jobs_added += 1

        self._log(f"Phase 1 added {jobs_added} jobs")
        self.jobs_added_today += jobs_added

    def _fill_phase_2_standard(self):
        """Phase 2: Standard fills - security, quality, coverage"""
        self._log("Phase 2: Standard fills")
        self.status.last_fill_action = "phase_2_standard"

        jobs_added = 0

        # Get standard work items from orchestrator
        standard_jobs = self.orchestrator.generate_work_items()

        # Filter to security and pattern jobs
        priority_jobs = [
            j
            for j in standard_jobs
            if j.source in ("security", "pattern") and j.priority in ("immediate", "high")
        ]

        for job in priority_jobs[:4]:
            if self._submit_job(job):
                jobs_added += 1

        self._log(f"Phase 2 added {jobs_added} jobs")
        self.jobs_added_today += jobs_added

    def _fill_phase_3_backlog(self):
        """Phase 3: Backlog fills - docs, refactoring, strategic"""
        self._log("Phase 3: Backlog fills")
        self.status.last_fill_action = "phase_3_backlog"

        jobs_added = 0

        # Get all work items
        all_jobs = self.orchestrator.generate_work_items()

        # Filter to lower priority work
        backlog_jobs = [
            j
            for j in all_jobs
            if j.source in ("docs", "research") or j.priority in ("normal", "low")
        ]

        for job in backlog_jobs[:4]:
            if self._submit_job(job):
                jobs_added += 1

        # Add strategic planning if needed
        strategic_job = self._create_strategic_job()
        if strategic_job and self._submit_job(strategic_job):
            jobs_added += 1

        self._log(f"Phase 3 added {jobs_added} jobs")
        self.jobs_added_today += jobs_added

    def _create_strategic_job(self) -> Optional[BatchWorkItem]:
        """Create a strategic planning job for weekly review"""
        # Only on Sundays or if queue is very low
        if datetime.now().weekday() != 6 and self.status.queue_depth_hours > 2:
            return None

        return BatchWorkItem(
            id=f"strategic-planning-{datetime.now().strftime('%Y%m%d')}",
            title="Weekly Strategic Planning",
            description="Comprehensive review of goals, priorities, and project health",
            prompt="""Perform comprehensive weekly strategic review:

1. GOAL PROGRESS
   - Review GOALS.md progress
   - Identify blocked or stalled goals
   - Recommend priority adjustments

2. PROJECT HEALTH
   - Scan all active projects for:
     * Stale branches
     * Unmerged PRs
     * Failing tests
     * Security vulnerabilities

3. TECHNICAL DEBT
   - Catalog new TODOs added this week
   - Identify growing complexity hotspots
   - Flag abandoned WIP code

4. NEXT WEEK PLAN
   - Top 3 priorities
   - Potential blockers
   - Resource needs

Provide actionable recommendations for the week ahead.""",
            priority="high",
            estimated_input_tokens=50_000,
            estimated_output_tokens=8_000,
            source="goal",
            deadline_hours=72,
        )

    def _submit_job(self, job: BatchWorkItem) -> bool:
        """Submit a job to the batch queue"""
        try:
            from batch.orchestrator import BatchOrchestrator

            orchestrator = BatchOrchestrator()

            # Convert to API format
            api_job = {
                "id": job.id,
                "description": job.description,
                "priority": job.priority,
                "tasks": [
                    {
                        "task_id": f"{job.id}_task_1",
                        "title": job.title,
                        "prompt": job.prompt,
                        "context": "",
                        "files_affected": job.files,
                        "estimated_tokens": job.estimated_input_tokens,
                    }
                ],
                "estimated_total_tokens": job.total_tokens,
                "source": job.source,
                "project": job.project,
            }

            job_id = orchestrator.submit_job(api_job, auto_detect=True)
            self._log(f"Submitted job: {job.title} (ID: {job_id})")
            self.status.jobs_queued += 1
            return True

        except Exception as e:
            self._log(f"Failed to submit job {job.id}: {e}", level="error")
            return False

    def _run_batch_cycle(self):
        """Run one submit + retrieve cycle through the unified SQLite pipeline.

        - Submitter picks up PENDING AI tasks and sends to Anthropic Batch API
        - Retriever checks SUBMITTED batches and downloads completed results
        """
        try:
            from batch.submitter import BatchSubmitter

            submitter = BatchSubmitter()
            sub_stats = submitter.submit_pending()
            if sub_stats.tasks_submitted > 0:
                self._log(
                    f"Submitted {sub_stats.tasks_submitted} tasks to Anthropic "
                    f"({sub_stats.batches_created} batches)"
                )
            if sub_stats.circuit_breaker_open:
                self._log("Circuit breaker OPEN — skipping submissions", level="warning")
        except Exception as e:
            self._log(f"Submitter error: {e}", level="error")

        try:
            from batch.retriever import BatchRetriever

            retriever = BatchRetriever()
            ret_stats = retriever.retrieve_completed()
            if ret_stats.tasks_completed > 0:
                self._log(
                    f"Retrieved {ret_stats.tasks_completed} completed tasks "
                    f"({ret_stats.results_saved} results saved)"
                )
            if ret_stats.tasks_failed > 0:
                self._log(f"{ret_stats.tasks_failed} tasks failed", level="warning")
        except Exception as e:
            self._log(f"Retriever error: {e}", level="error")

    def _get_queue_depth_hours(self) -> float:
        """Estimate queue depth in hours based on pending tasks in SQLite.

        Uses the unified BatchTaskQueue as source of truth.
        Fallback: status file on disk.
        """
        try:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue

            queue = BatchTaskQueue()
            pending = queue.get_pending_api_count()

            # Rough estimate: each task takes ~30 minutes of batch processing
            return pending * 0.5

        except ImportError:
            try:
                from cortex.intelligence.process_monitor.batch_queue import BatchTaskQueue

                queue = BatchTaskQueue()
                pending = queue.get_pending_api_count()
                return pending * 0.5
            except ImportError:
                pass
        except Exception:
            pass

        # Fallback: check status file
        try:
            status_path = Path.home() / ".cortex" / "batch" / "queue_status.json"
            if status_path.exists():
                data = json.loads(status_path.read_text())
                return data.get("estimated_hours", 0)
        except Exception:
            pass

        return 0.0

    def _update_status(self):
        """Write current status to file"""
        self.status.running = self.running
        self.status.jobs_added_today = self.jobs_added_today

        if self.start_time:
            self.status.uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600

        try:
            self.config.status_file.write_text(json.dumps(asdict(self.status), indent=2))
        except Exception as e:
            self._log(f"Failed to write status: {e}", level="error")

    def _log(self, message: str, level: str = "info"):
        """Log message to file and stdout"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level.upper()}] {message}"

        print(log_line)

        try:
            with open(self.config.log_file, "a") as f:
                f.write(log_line + "\n")
        except Exception:
            pass

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self._log(f"Received signal {signum}, shutting down...")
        self.running = False

    def _cleanup(self):
        """Cleanup on shutdown"""
        self.status.running = False
        self._update_status()

        try:
            self.config.pid_file.unlink(missing_ok=True)
        except Exception:
            pass

        self._log("Flywheel daemon stopped")


def get_status() -> FlywheelStatus:
    """Get current flywheel status"""
    config = FlywheelConfig()

    if not config.status_file.exists():
        return FlywheelStatus(health="not_running")

    try:
        data = json.loads(config.status_file.read_text())
        return FlywheelStatus(**data)
    except Exception:
        return FlywheelStatus(health="error")


def stop_daemon():
    """Stop running daemon"""
    config = FlywheelConfig()

    if not config.pid_file.exists():
        print("No daemon running (PID file not found)")
        return False

    try:
        pid = int(config.pid_file.read_text())
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to daemon (PID: {pid})")
        return True
    except ProcessLookupError:
        print("Daemon not running (stale PID file)")
        config.pid_file.unlink(missing_ok=True)
        return False
    except Exception as e:
        print(f"Error stopping daemon: {e}")
        return False


def print_status():
    """Print human-readable status"""
    status = get_status()

    print("╔══════════════════════════════════════════════════════╗")
    print("║          DEVELOPMENT FLYWHEEL STATUS                ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    # Running status
    if status.running:
        print(f"🟢 RUNNING (PID: {status.pid})")
        print(f"   Uptime: {status.uptime_hours:.1f} hours")
    else:
        print("🔴 NOT RUNNING")
    print()

    # Queue depth
    health_icons = {
        "healthy": "🟢",
        "warning": "🟡",
        "critical": "🔴",
        "unknown": "⚪",
        "not_running": "⚫",
        "error": "❌",
    }
    icon = health_icons.get(status.health, "⚪")

    print(f"📊 Queue Depth: {status.queue_depth_hours:.1f}h {icon}")
    print(f"   Jobs Queued: {status.jobs_queued}")
    print(f"   Added Today: {status.jobs_added_today}")
    print()

    if status.last_check:
        print(f"⏰ Last Check: {status.last_check}")
    if status.last_fill_action:
        print(f"🔧 Last Action: {status.last_fill_action}")
    print()


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Development Flywheel Daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon")
    parser.add_argument("--once", action="store_true", help="Run one check cycle and exit")

    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.stop:
        stop_daemon()
    elif args.once:
        daemon = FlywheelDaemon()
        daemon._check_and_fill()
        print_status()
    else:
        daemon = FlywheelDaemon()
        daemon.start()


if __name__ == "__main__":
    main()
