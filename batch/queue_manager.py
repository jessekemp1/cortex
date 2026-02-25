#!/usr/bin/env python3
"""
Cortex Batch Queue Manager

Actively monitors batch API capacity and submits queued jobs when slots are available.
Designed to maximize throughput while respecting API limits.
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from cortex.batch.batch_api_client import BatchAPIClient, BatchRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BatchQueueManager:
    """Manages batch job queue with automatic submission and circuit breaker"""

    def __init__(
        self,
        queue_file: Optional[Path] = None,
        max_concurrent_batches: int = 5,
        check_interval: int = 300,
    ):
        """
        Initialize queue manager

        Args:
            queue_file: Path to queue JSON file
            max_concurrent_batches: Maximum batches to have in-flight at once
            check_interval: Seconds between capacity checks
        """
        self.client = BatchAPIClient()
        self.queue_file = (
            queue_file or Path.home() / ".cortex" / "batches" / "remediation_queue.json"
        )
        self.max_concurrent = max_concurrent_batches
        self.check_interval = check_interval

        # Circuit breaker state
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._circuit_open_until: Optional[datetime] = None
        self._circuit_cooldown_minutes = 60

    def load_queue(self) -> Dict:
        """Load queue from JSON file with corruption recovery.

        If the JSON file is corrupt (e.g., interrupted write), backs up
        the corrupt file and reinitializes an empty queue so the pipeline
        can continue operating.
        """
        empty_queue = {"priority_jobs": [], "queue_metadata": {}}

        if not self.queue_file.exists():
            logger.error(f"Queue file not found: {self.queue_file}")
            return empty_queue

        try:
            with open(self.queue_file) as f:
                data = json.load(f)

            # Validate expected structure
            if not isinstance(data, dict) or "priority_jobs" not in data:
                raise ValueError(
                    f"Invalid queue structure: missing 'priority_jobs' key "
                    f"(got keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__})"
                )

            return data

        except (json.JSONDecodeError, ValueError) as e:
            # Back up corrupt file before reinitializing
            from datetime import datetime

            backup_path = self.queue_file.with_suffix(
                f".corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            try:
                import shutil

                shutil.copy2(self.queue_file, backup_path)
                logger.warning(
                    f"Queue file corrupt ({e}). Backed up to {backup_path} "
                    f"and reinitializing empty queue."
                )
            except OSError as copy_err:
                logger.error(
                    f"Queue file corrupt ({e}) and backup failed ({copy_err}). "
                    f"Reinitializing empty queue."
                )

            # Reinitialize with empty queue (atomic write)
            self.save_queue(empty_queue)
            return empty_queue

    def save_queue(self, queue_data: Dict):
        """Save queue back to JSON file using atomic write to prevent corruption."""
        import os
        import tempfile

        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        dir_path = str(self.queue_file.parent)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(queue_data, f, indent=2)
            os.rename(tmp_path, str(self.queue_file))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        logger.debug(f"Queue saved to {self.queue_file}")

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open (blocking submissions).

        Returns:
            True if circuit is OPEN (submissions blocked), False if closed (OK to submit)
        """
        if self._circuit_open_until is None:
            return False

        if datetime.now() >= self._circuit_open_until:
            # Cooldown expired, half-open the circuit
            logger.info("Circuit breaker cooldown expired, attempting half-open")
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return False

        remaining = (self._circuit_open_until - datetime.now()).total_seconds() / 60
        logger.warning(
            f"Circuit breaker OPEN — {remaining:.0f} min remaining. "
            f"Skipping submissions after {self._max_consecutive_failures} consecutive failures."
        )
        return True

    def _trip_circuit_breaker(self):
        """Trip the circuit breaker after max consecutive failures."""
        from datetime import timedelta

        self._circuit_open_until = datetime.now() + timedelta(
            minutes=self._circuit_cooldown_minutes
        )
        logger.error(
            f"Circuit breaker TRIPPED after {self._consecutive_failures} consecutive failures. "
            f"Pausing submissions for {self._circuit_cooldown_minutes} min until "
            f"{self._circuit_open_until.strftime('%H:%M')}"
        )

    def _check_api_budget(self) -> bool:
        """Check if API budget allows submissions.

        Returns:
            True if budget is exhausted (block submissions), False if OK
        """
        try:
            from cortex.batch.budget_enforcer import BudgetEnforcer

            enforcer = BudgetEnforcer()
            status = enforcer.check_budget()
            if status.over_budget:
                logger.warning(
                    f"API budget exhausted ({status.usage_pct:.0f}% used). "
                    f"Blocking batch submissions."
                )
                return True
            return False
        except Exception as e:
            logger.debug(f"Budget check skipped (not critical): {e}")
            return False

    def get_active_batch_count(self) -> int:
        """Get count of currently in-progress batches.

        Only checks the 20 most recent batches — active ones are always recent.
        This avoids paginating through 1,700+ historical batches.
        """
        batches = self.client.list_batches(limit=20)
        active_count = sum(1 for b in batches if b["status"] in ["in_progress", "validating"])
        return active_count

    def get_available_capacity(self) -> int:
        """Calculate available batch capacity"""
        active = self.get_active_batch_count()
        available = max(0, self.max_concurrent - active)
        logger.info(
            f"Batch capacity: {active}/{self.max_concurrent} active, {available} slots available"
        )
        return available

    def build_batch_requests(self, job: Dict) -> List[BatchRequest]:
        """Convert job tasks into BatchRequest objects"""
        requests = []

        for task in job["tasks"]:
            # Build the full prompt with context
            full_prompt = f"""You are helping with a code improvement task as part of {job["description"]}.

**Task:** {task["title"]}

**Context:**
{task["context"]}

**Files Affected:**
{", ".join(task["files_affected"]) if task["files_affected"] else "N/A"}

**Instructions:**
{task["prompt"]}

**Important:**
- Provide specific, actionable code changes
- Include file paths and line numbers where relevant
- Show before/after code examples
- Consider edge cases and testing
- Think about backwards compatibility

Please provide a comprehensive implementation plan and any code changes needed."""

            # Sanitize custom_id: Anthropic API requires ^[a-zA-Z0-9_-]{1,64}$
            sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "_", task["task_id"])[:64]
            request = BatchRequest(
                custom_id=sanitized_id,
                params={
                    "messages": [{"role": "user", "content": full_prompt}],
                    "max_tokens": 4000,
                },
            )
            requests.append(request)

        return requests

    def submit_job(self, job: Dict) -> Optional[str]:
        """
        Submit a job from the queue as a batch.

        Tracks consecutive failures for circuit breaker logic.
        On success, resets failure counter. On API budget/limit errors,
        increments counter and trips breaker at threshold.

        Returns:
            batch_id if successful, None otherwise
        """
        logger.info(f"Submitting job: {job['id']} - {job['description']}")

        try:
            # Build batch requests
            requests = self.build_batch_requests(job)

            # Submit to API
            batch_id = self.client.submit_batch(requests=requests, description=job["description"])

            logger.info(
                f"✅ Job {job['id']} submitted as batch {batch_id} ({len(requests)} requests)"
            )

            # Success — reset circuit breaker counter
            self._consecutive_failures = 0
            return batch_id

        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"❌ Failed to submit job {job['id']}: {e}")

            # Only trip circuit breaker on systemic issues (rate limits, budget).
            # Do NOT trip on 400 validation errors — those are per-request input
            # issues that won't resolve by waiting. Skipping the bad job and
            # continuing is the correct behavior.
            is_rate_limit = any(
                kw in error_str for kw in ["usage limit", "rate limit", "budget", "429"]
            )
            is_validation_error = "400" in error_str or "invalid_request" in error_str

            if is_rate_limit and not is_validation_error:
                self._consecutive_failures += 1
                logger.warning(
                    f"API rate/budget error ({self._consecutive_failures}/"
                    f"{self._max_consecutive_failures})"
                )
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._trip_circuit_breaker()
            elif is_validation_error:
                logger.warning(
                    f"Validation error for job {job['id']} — skipping (not tripping breaker)"
                )

            return None

    def process_queue(self) -> Dict[str, any]:
        """
        Process the queue: submit jobs when capacity is available.

        Checks circuit breaker and budget before attempting submissions.

        Returns:
            dict with processing stats
        """
        stats = {
            "checked_at": datetime.now().isoformat(),
            "jobs_submitted": 0,
            "jobs_pending": 0,
            "capacity_available": 0,
            "circuit_breaker_open": False,
            "budget_exhausted": False,
        }

        # Circuit breaker check — blocks all submissions if tripped
        if self._check_circuit_breaker():
            stats["circuit_breaker_open"] = True
            return stats

        # Budget check — blocks submissions if API budget exhausted
        if self._check_api_budget():
            stats["budget_exhausted"] = True
            return stats

        # Load current queue
        queue_data = self.load_queue()
        if not queue_data.get("priority_jobs"):
            logger.info("Queue is empty")
            return stats

        # Check capacity
        available = self.get_available_capacity()
        stats["capacity_available"] = available

        if available == 0:
            logger.info("No capacity available, waiting...")
            stats["jobs_pending"] = sum(
                1 for job in queue_data["priority_jobs"] if job["status"] == "queued"
            )
            return stats

        # Get queued jobs sorted by priority
        queued_jobs = [job for job in queue_data["priority_jobs"] if job["status"] == "queued"]

        # Sort by priority (CRITICAL > HIGH > MEDIUM)
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        queued_jobs.sort(key=lambda j: priority_order.get(j.get("priority", "LOW"), 9))

        # Submit jobs up to available capacity
        submitted = 0
        for job in queued_jobs[:available]:
            # Check dependencies
            depends_on = job.get("depends_on", [])
            if depends_on:
                # Check if all dependencies are completed
                dep_statuses = {
                    dep_job["id"]: dep_job["status"]
                    for dep_job in queue_data["priority_jobs"]
                    if dep_job["id"] in depends_on
                }

                incomplete_deps = [
                    dep_id for dep_id, status in dep_statuses.items() if status != "completed"
                ]

                if incomplete_deps:
                    logger.info(f"Job {job['id']} waiting on dependencies: {incomplete_deps}")
                    continue

            # Submit the job
            batch_id = self.submit_job(job)

            if batch_id:
                # Update job status
                job["status"] = "submitted"
                job["batch_id"] = batch_id
                job["submitted_at"] = datetime.now().isoformat()
                submitted += 1

        # Save updated queue
        if submitted > 0:
            self.save_queue(queue_data)
            logger.info(f"✅ Submitted {submitted} jobs, queue updated")

        stats["jobs_submitted"] = submitted
        stats["jobs_pending"] = len(
            [job for job in queue_data["priority_jobs"] if job["status"] == "queued"]
        )

        return stats

    def cleanup_queue(self, max_age_days: int = 7, max_total_jobs: int = 200) -> Dict:
        """
        Remove stale jobs from the queue to prevent unbounded growth.

        Removes completed/synced/expired/failed jobs older than max_age_days.
        Hard caps total jobs at max_total_jobs, keeping active jobs and trimming
        oldest inactive ones.

        Args:
            max_age_days: Remove inactive jobs older than this
            max_total_jobs: Hard cap on total jobs in queue

        Returns:
            Dict with cleanup stats
        """
        queue_data = self.load_queue()
        jobs = queue_data.get("priority_jobs", [])
        original_count = len(jobs)

        if original_count == 0:
            return {"original": 0, "removed": 0, "remaining": 0}

        cutoff = datetime.now() - __import__("datetime").timedelta(days=max_age_days)
        cutoff_str = cutoff.isoformat()

        # Terminal statuses that are safe to clean up
        terminal_statuses = {"completed", "synced", "expired", "failed", "cancelled"}

        # Phase 1: Remove old terminal jobs
        kept_jobs = []
        removed_age = 0
        for job in jobs:
            status = job.get("status", "unknown")
            created = job.get("created_at", job.get("submitted_at", ""))

            if status in terminal_statuses and created and created < cutoff_str:
                removed_age += 1
            else:
                kept_jobs.append(job)

        # Phase 2: Hard cap — if still over limit, remove oldest terminal jobs
        removed_cap = 0
        if len(kept_jobs) > max_total_jobs:
            # Separate active from inactive
            active = [j for j in kept_jobs if j.get("status") in ("queued", "submitted")]
            inactive = [j for j in kept_jobs if j.get("status") not in ("queued", "submitted")]

            # Sort inactive by age (oldest first) and trim
            inactive.sort(key=lambda j: j.get("created_at", j.get("submitted_at", "")))
            trim_count = len(kept_jobs) - max_total_jobs
            if trim_count > 0 and len(inactive) >= trim_count:
                inactive = inactive[trim_count:]
                removed_cap = trim_count
            elif trim_count > 0:
                removed_cap = len(inactive)
                inactive = []

            kept_jobs = active + inactive

        total_removed = removed_age + removed_cap
        if total_removed > 0:
            queue_data["priority_jobs"] = kept_jobs
            self.save_queue(queue_data)
            logger.info(
                f"Queue cleanup: {original_count} → {len(kept_jobs)} jobs "
                f"({removed_age} expired, {removed_cap} capped)"
            )

        return {
            "original": original_count,
            "removed": total_removed,
            "removed_by_age": removed_age,
            "removed_by_cap": removed_cap,
            "remaining": len(kept_jobs),
        }

    def monitor_and_update_status(self):
        """Check status of submitted jobs, retrieve full results, and update queue.

        When a batch completes, retrieves the actual Claude response text
        (not just API metadata) and persists it to the results directory
        for the morning processor.
        """
        queue_data = self.load_queue()
        updated = False

        # Ensure results directory exists for morning processor
        results_dir = Path.home() / ".cortex" / "batch" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        for job in queue_data["priority_jobs"]:
            if job["status"] == "submitted" and "batch_id" in job:
                batch_id = job["batch_id"]

                try:
                    status = self.client.get_batch_status(batch_id)

                    if status["status"] in ("ended", "completed"):
                        # Batch completed
                        job["status"] = "completed"
                        job["completed_at"] = datetime.now().isoformat()
                        job["final_status"] = status
                        updated = True
                        logger.info(f"✅ Job {job['id']} completed (batch {batch_id})")

                        # Retrieve actual Claude response content
                        result_data = {
                            "job_id": job["id"],
                            "batch_id": batch_id,
                            "title": job.get("description", ""),
                            "status": "completed",
                            "completed_at": job["completed_at"],
                            "source": job.get("source", "other"),
                            "type": job.get("source", "other"),
                            "tokens_used": job.get("estimated_total_tokens", 0),
                            "request_counts": status.get("request_counts", {}),
                        }

                        try:
                            batch_results = self.client._retrieve_batch_results(batch_id)
                            result_data["results"] = []
                            for r in batch_results:
                                entry = {
                                    "custom_id": r.custom_id,
                                    "status": r.status,
                                }
                                # Extract full response text from result dict
                                # (results are now dicts from direct HTTP fetch)
                                result_obj = r.result
                                if isinstance(result_obj, dict):
                                    entry["result"] = result_obj
                                    # Also extract text for easy access
                                    if result_obj.get("type") == "succeeded":
                                        msg = result_obj.get("message", {})
                                        content = msg.get("content", [])
                                        text = "".join(
                                            b.get("text", "")
                                            for b in content
                                            if b.get("type") == "text"
                                        )
                                        entry["response_text"] = text
                                elif hasattr(result_obj, "model_dump"):
                                    entry["result"] = result_obj.model_dump()
                                else:
                                    entry["result"] = str(result_obj)
                                result_data["results"].append(entry)
                            logger.info(
                                f"   Retrieved {len(batch_results)} result(s) with full response text"
                            )
                        except Exception as retrieval_err:
                            logger.warning(
                                f"   Could not retrieve full results for {batch_id}: {retrieval_err}"
                            )
                            result_data["retrieval_error"] = str(retrieval_err)
                            result_data["output"] = json.dumps(status)

                        result_file = results_dir / f"{job['id']}_{batch_id}.json"
                        result_file.write_text(json.dumps(result_data, indent=2, default=str))
                        logger.info(f"   Result written to: {result_file}")

                except Exception as e:
                    logger.error(f"Error checking status for {batch_id}: {e}")

        if updated:
            self.save_queue(queue_data)

    def run_continuous(self, duration_hours: Optional[float] = None):
        """
        Run queue manager continuously with adaptive sleep.

        Uses longer sleep interval (1 hour) when circuit breaker is open
        to avoid pointless polling. Runs queue cleanup on startup.

        Args:
            duration_hours: How long to run (None = forever)
        """
        logger.info(f"Starting batch queue manager (interval: {self.check_interval}s)")
        logger.info(f"Queue file: {self.queue_file}")
        logger.info(f"Max concurrent batches: {self.max_concurrent}")

        # Run queue cleanup on startup
        cleanup_stats = self.cleanup_queue()
        if cleanup_stats["removed"] > 0:
            logger.info(f"Startup cleanup: removed {cleanup_stats['removed']} stale jobs")

        start_time = time.time()
        iteration = 0

        try:
            while True:
                iteration += 1
                logger.info(f"\n{'=' * 60}")
                logger.info(f"Queue check iteration #{iteration}")
                logger.info(f"{'=' * 60}")

                # Check and update status of submitted jobs
                self.monitor_and_update_status()

                # Process queue and submit new jobs
                stats = self.process_queue()

                logger.info(f"Stats: {stats}")

                # Check if we should stop
                if duration_hours:
                    elapsed = (time.time() - start_time) / 3600
                    if elapsed >= duration_hours:
                        logger.info(f"Duration limit reached ({duration_hours}h), stopping")
                        break

                # Adaptive sleep: longer when circuit breaker is open
                if stats.get("circuit_breaker_open") or stats.get("budget_exhausted"):
                    sleep_seconds = 3600  # 1 hour when blocked
                    logger.info(f"Circuit/budget blocked — sleeping {sleep_seconds}s (1 hour)")
                else:
                    sleep_seconds = self.check_interval
                    logger.info(f"Sleeping {sleep_seconds}s until next check...")

                time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            logger.info("\n⚠️  Queue manager stopped by user")
        except Exception as e:
            logger.error(f"❌ Queue manager error: {e}")
            raise

    def get_queue_status(self) -> Dict:
        """Get current queue status summary"""
        queue_data = self.load_queue()
        jobs = queue_data.get("priority_jobs", [])

        status_counts = {}
        for job in jobs:
            status = job.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_jobs": len(jobs),
            "status_breakdown": status_counts,
            "jobs": [
                {
                    "id": job["id"],
                    "description": job["description"],
                    "priority": job.get("priority", "N/A"),
                    "status": job.get("status", "unknown"),
                    "batch_id": job.get("batch_id", "N/A"),
                }
                for job in jobs
            ],
        }


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Cortex Batch Queue Manager")
    parser.add_argument("--queue-file", type=Path, help="Path to queue JSON file", default=None)
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent batches (default: 5)",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=300,
        help="Seconds between checks (default: 300)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Hours to run (default: run forever)",
    )
    parser.add_argument("--status-only", action="store_true", help="Show status and exit")

    args = parser.parse_args()

    manager = BatchQueueManager(
        queue_file=args.queue_file,
        max_concurrent_batches=args.max_concurrent,
        check_interval=args.check_interval,
    )

    if args.status_only:
        status = manager.get_queue_status()
        print("\n📊 Queue Status")
        print("=" * 60)
        print(f"Total jobs: {status['total_jobs']}")
        print(f"Status breakdown: {status['status_breakdown']}")
        print("\nJobs:")
        for job in status["jobs"]:
            print(
                f"  [{job['priority']:8}] {job['id']:25} - {job['status']:10} - {job['description']}"
            )
        return

    manager.run_continuous(duration_hours=args.duration)


if __name__ == "__main__":
    main()
