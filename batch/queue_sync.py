#!/usr/bin/env python3
"""
Queue Sync Bridge - Syncs JSON remediation queue into SQLite batch queue.

The nightly orchestrator writes API jobs to ~/.cortex/batches/remediation_queue.json.
The batch daemon reads from ~/.cortex/batch_queue.db via BatchTaskQueue.
This bridge ensures jobs flow from one to the other so the daemon can execute them.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# JSON queue path (written by orchestrator._submit_to_api)
JSON_QUEUE = Path.home() / ".cortex" / "batches" / "remediation_queue.json"

# Map JSON source fields to SQLite task_type values the executor understands.
# "ai_inference" is recognized by the CapacityScheduler as an AI workload.
SOURCE_TO_TASK_TYPE = {
    "security": "ai_inference",
    "docs": "ai_inference",
    "research": "ai_inference",
    "pattern": "ai_inference",
    "goal": "ai_inference",
}

# Rough conversion: 1000 tokens ~ 1 minute of API processing
TOKENS_TO_MINUTES = 1000.0


def _sqlite_has_json_job(db_path: str, json_job_id: str) -> bool:
    """
    Check if a task with matching json_job_id already exists in SQLite.

    We can't use btq.get_task(json_job_id) because add_task() generates a
    new UUID as task_id — the JSON job ID is stored in metadata instead.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT 1 FROM batch_tasks WHERE json_extract(metadata, '$.json_job_id') = ? LIMIT 1",
        (json_job_id,),
    )
    found = cursor.fetchone() is not None
    conn.close()
    return found


def sync_json_to_sqlite(queue_path: Path = JSON_QUEUE) -> int:
    """
    Sync queued jobs from the JSON remediation queue into the SQLite batch queue.

    For each JSON job with status "queued":
      - Checks if already synced (by json_job_id in SQLite metadata)
      - Flattens each task's prompt into a separate SQLite task
      - Maps fields conservatively; extras go into metadata
      - Marks the JSON job as "synced" after successful import

    Returns:
        Number of jobs synced
    """
    try:
        from cortex.intelligence.process_monitor.batch_queue import BatchTaskQueue
    except ImportError:
        from intelligence.process_monitor.batch_queue import BatchTaskQueue

    if not queue_path.exists():
        logger.warning(f"JSON queue not found: {queue_path}")
        return 0

    with open(queue_path) as f:
        queue_data = json.load(f)

    btq = BatchTaskQueue()
    synced_count = 0

    for job in queue_data.get("priority_jobs", []):
        if job.get("status") != "queued":
            continue

        job_id = job.get("id", "")

        # Dedup: check SQLite metadata for matching json_job_id
        if _sqlite_has_json_job(btq.db_path, job_id):
            logger.debug(f"Skipping duplicate job: {job_id}")
            job["status"] = "synced"  # Mark as synced to prevent future re-processing
            synced_count += 0  # Don't count as synced since it was already there
            continue

        # Determine task_type from source
        source = job.get("source", "general")
        task_type = SOURCE_TO_TASK_TYPE.get(source, "ai_inference")

        # Normalize priority: JSON uses uppercase, SQLite uses lowercase
        priority = job.get("priority", "NORMAL").lower()

        # Build the command from the job's tasks (prompts) or fall back to description.
        tasks = job.get("tasks", [])
        if tasks:
            prompts = []
            for t in tasks:
                prompt = t.get("prompt", "")
                title = t.get("title", "")
                if prompt:
                    prompts.append(f"[{title}] {prompt}" if title else prompt)
            command = "\n\n---\n\n".join(prompts) if prompts else job.get("description", "")
        else:
            command = job.get("description", "")

        if not command:
            logger.warning(f"Skipping job {job_id}: no prompt or description")
            continue

        # Estimate duration from tokens
        est_tokens = job.get("estimated_total_tokens", 0)
        est_minutes = max(1.0, est_tokens / TOKENS_TO_MINUTES)

        # Build metadata with json_job_id for future dedup lookups
        metadata = {
            "json_job_id": job_id,
            "source": source,
            "sync_origin": "queue_sync",
            "estimated_tokens": est_tokens,
            "request_count": job.get("request_count", 0),
            "project": job.get("project"),
            "tasks": tasks,
        }

        btq.add_task(
            command=command,
            task_type=task_type,
            description=job.get("description", command[:120]),
            priority=priority,
            estimated_duration_minutes=est_minutes,
            metadata=metadata,
            dependencies=[],
        )

        # Mark as synced in the JSON queue
        job["status"] = "synced"
        synced_count += 1
        logger.info(f"Synced job {job_id} -> SQLite ({task_type}, {priority})")

    # Persist the status updates back to JSON (atomic write prevents corruption)
    import os
    import tempfile

    dir_path = str(queue_path.parent)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(queue_data, f, indent=2)
        os.rename(tmp_path, str(queue_path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    if synced_count > 0:
        logger.info(f"Synced {synced_count} jobs from JSON to SQLite")

    return synced_count


def get_sync_status(queue_path: Path = JSON_QUEUE) -> Dict[str, Any]:
    """
    Show counts from both queue systems for diagnostics.

    Returns:
        Dict with json_queue and sqlite_queue stats
    """
    try:
        from cortex.intelligence.process_monitor.batch_queue import BatchTaskQueue
    except ImportError:
        from intelligence.process_monitor.batch_queue import BatchTaskQueue

    # JSON side
    json_stats = {"queued": 0, "synced": 0, "submitted": 0, "completed": 0, "total": 0}
    if queue_path.exists():
        with open(queue_path) as f:
            data = json.load(f)
        for job in data.get("priority_jobs", []):
            status = job.get("status", "unknown")
            json_stats[status] = json_stats.get(status, 0) + 1
            json_stats["total"] += 1

    # SQLite side
    btq = BatchTaskQueue()
    sqlite_stats = btq.get_queue_stats()

    return {
        "json_queue": json_stats,
        "sqlite_queue": sqlite_stats,
        "needs_sync": json_stats["queued"],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = sync_json_to_sqlite()
    print(f"\nSynced {count} jobs")
    print(f"\nStatus: {json.dumps(get_sync_status(), indent=2, default=str)}")
