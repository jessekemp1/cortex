#!/usr/bin/env python3
"""
Cortex Batch Queue Manager

Actively monitors batch API capacity and submits queued jobs when slots are available.
Designed to maximize throughput while respecting API limits.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from cortex.batch.batch_api_client import BatchAPIClient, BatchRequest

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BatchQueueManager:
    """Manages batch job queue with automatic submission"""

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
            queue_file
            or Path.home() / ".cortex" / "batches" / "remediation_queue.json"
        )
        self.max_concurrent = max_concurrent_batches
        self.check_interval = check_interval

    def load_queue(self) -> Dict:
        """Load queue from JSON file"""
        if not self.queue_file.exists():
            logger.error(f"Queue file not found: {self.queue_file}")
            return {"priority_jobs": [], "queue_metadata": {}}

        with open(self.queue_file) as f:
            return json.load(f)

    def save_queue(self, queue_data: Dict):
        """Save queue back to JSON file"""
        with open(self.queue_file, "w") as f:
            json.dump(queue_data, f, indent=2)
        logger.debug(f"Queue saved to {self.queue_file}")

    def get_active_batch_count(self) -> int:
        """Get count of currently in-progress batches"""
        batches = self.client.list_batches(limit=50)
        active_count = sum(
            1 for b in batches if b["status"] in ["in_progress", "validating"]
        )
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
            full_prompt = f"""You are helping with a code improvement task as part of {job['description']}.

**Task:** {task['title']}

**Context:**
{task['context']}

**Files Affected:**
{', '.join(task['files_affected']) if task['files_affected'] else 'N/A'}

**Instructions:**
{task['prompt']}

**Important:**
- Provide specific, actionable code changes
- Include file paths and line numbers where relevant
- Show before/after code examples
- Consider edge cases and testing
- Think about backwards compatibility

Please provide a comprehensive implementation plan and any code changes needed."""

            request = BatchRequest(
                custom_id=task["task_id"],
                params={
                    "messages": [{"role": "user", "content": full_prompt}],
                    "max_tokens": 4000,
                },
            )
            requests.append(request)

        return requests

    def submit_job(self, job: Dict) -> Optional[str]:
        """
        Submit a job from the queue as a batch

        Returns:
            batch_id if successful, None otherwise
        """
        logger.info(f"Submitting job: {job['id']} - {job['description']}")

        try:
            # Build batch requests
            requests = self.build_batch_requests(job)

            # Submit to API
            batch_id = self.client.submit_batch(
                requests=requests, description=job["description"]
            )

            logger.info(
                f"✅ Job {job['id']} submitted as batch {batch_id} ({len(requests)} requests)"
            )
            return batch_id

        except Exception as e:
            logger.error(f"❌ Failed to submit job {job['id']}: {e}")
            return None

    def process_queue(self) -> Dict[str, any]:
        """
        Process the queue: submit jobs when capacity is available

        Returns:
            dict with processing stats
        """
        stats = {
            "checked_at": datetime.now().isoformat(),
            "jobs_submitted": 0,
            "jobs_pending": 0,
            "capacity_available": 0,
        }

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
        queued_jobs = [
            job for job in queue_data["priority_jobs"] if job["status"] == "queued"
        ]

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
                    dep_id
                    for dep_id, status in dep_statuses.items()
                    if status != "completed"
                ]

                if incomplete_deps:
                    logger.info(
                        f"Job {job['id']} waiting on dependencies: {incomplete_deps}"
                    )
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

    def monitor_and_update_status(self):
        """Check status of submitted jobs and update queue, write results for morning processor"""
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
                        logger.info(
                            f"✅ Job {job['id']} completed (batch {batch_id})"
                        )

                        # Write result file for morning processor to find
                        result_data = {
                            "job_id": job["id"],
                            "batch_id": batch_id,
                            "title": job.get("description", ""),
                            "status": "completed",
                            "completed_at": job["completed_at"],
                            "source": job.get("source", "other"),
                            "type": job.get("source", "other"),
                            "output": json.dumps(status),
                            "tokens_used": job.get("estimated_total_tokens", 0),
                            "request_counts": status.get("request_counts", {}),
                        }
                        result_file = results_dir / f"{job['id']}_{batch_id}.json"
                        result_file.write_text(json.dumps(result_data, indent=2))
                        logger.info(
                            f"   Result written to: {result_file}"
                        )

                except Exception as e:
                    logger.error(f"Error checking status for {batch_id}: {e}")

        if updated:
            self.save_queue(queue_data)

    def run_continuous(self, duration_hours: Optional[float] = None):
        """
        Run queue manager continuously

        Args:
            duration_hours: How long to run (None = forever)
        """
        logger.info(f"Starting batch queue manager (interval: {self.check_interval}s)")
        logger.info(f"Queue file: {self.queue_file}")
        logger.info(f"Max concurrent batches: {self.max_concurrent}")

        start_time = time.time()
        iteration = 0

        try:
            while True:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Queue check iteration #{iteration}")
                logger.info(f"{'='*60}")

                # Check and update status of submitted jobs
                self.monitor_and_update_status()

                # Process queue and submit new jobs
                stats = self.process_queue()

                logger.info(f"Stats: {stats}")

                # Check if we should stop
                if duration_hours:
                    elapsed = (time.time() - start_time) / 3600
                    if elapsed >= duration_hours:
                        logger.info(
                            f"Duration limit reached ({duration_hours}h), stopping"
                        )
                        break

                # Sleep until next check
                logger.info(f"Sleeping {self.check_interval}s until next check...")
                time.sleep(self.check_interval)

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
    parser.add_argument(
        "--queue-file", type=Path, help="Path to queue JSON file", default=None
    )
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
    parser.add_argument(
        "--status-only", action="store_true", help="Show status and exit"
    )

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
