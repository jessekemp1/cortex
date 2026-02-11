#!/usr/bin/env python3
"""
Migrate batch tasks from BatchScheduler (JSON) to BatchTaskQueue (SQLite DB).

This bridges the gap between the two batch systems that were running independently.

Root cause:
- quick_batch.py writes to ~/.cortex/batch_schedule/tasks.json (BatchScheduler)
- runtime daemon reads from ~/.cortex/batch/batch_queue.db (BatchTaskQueue)
- They never talk to each other, so jobs submitted via quick_batch.py never execute

This script:
1. Reads tasks from ~/.cortex/batch_schedule/tasks.json
2. Converts BatchTask (scheduler) -> BatchTask (queue)
3. Writes to ~/.cortex/batch/batch_queue.db
4. Preserves task state, priority, and scheduling information
"""

import sys
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.batch_scheduler import BatchScheduler
from intelligence.process_monitor.batch_queue import BatchTaskQueue, TaskState


def migrate_tasks(dry_run: bool = False):
    """
    Migrate tasks from JSON to SQLite database.

    Args:
        dry_run: If True, only print what would be migrated
    """
    # Load from JSON (BatchScheduler)
    scheduler = BatchScheduler()

    # Get all tasks
    all_tasks = scheduler.tasks

    if not all_tasks:
        print("No tasks found in BatchScheduler (~/.cortex/batch_schedule/tasks.json)")
        return

    print(f"\n{'=' * 60}")
    print(f"Found {len(all_tasks)} tasks in BatchScheduler")
    print(f"{'=' * 60}\n")

    # Initialize database queue
    queue = BatchTaskQueue()

    migrated_count = 0
    skipped_count = 0

    for scheduler_task in all_tasks:
        # Map scheduler task status to queue task state
        state_mapping = {
            "pending": TaskState.PENDING,
            "submitted": TaskState.RUNNING,  # Submitted to Anthropic API = running
            "processing": TaskState.RUNNING,
            "completed": TaskState.COMPLETED,
            "failed": TaskState.FAILED,
        }

        state = state_mapping.get(scheduler_task.status, TaskState.PENDING)

        # Convert priority
        priority_mapping = {
            "high": "high",
            "normal": "normal",
            "low": "low",
        }
        priority = priority_mapping.get(scheduler_task.priority, "normal")

        # Print task info
        print(f"Task: {scheduler_task.id}")
        print(f"  Title: {scheduler_task.title[:60]}")
        print(f"  Status: {scheduler_task.status} -> {state.value}")
        print(f"  Priority: {scheduler_task.priority} -> {priority}")
        print(f"  Created: {scheduler_task.created_at}")
        print(f"  Scheduled: {scheduler_task.submit_after}")

        if not dry_run:
            try:
                # Add to database queue using add_task parameters
                queue_task = queue.add_task(
                    command=scheduler_task.prompt,  # Prompt becomes command (AI task)
                    task_type="analysis",  # Most quick_batch tasks are analysis
                    description=scheduler_task.title,
                    priority=priority,
                    scheduled_time=scheduler_task.submit_after,  # Use submit_after as scheduled time
                    estimated_duration_minutes=scheduler_task.estimated_output_tokens
                    / 1000,  # Rough estimate
                )

                # Update the state if not pending (e.g., submitted/completed tasks)
                if state != TaskState.PENDING:
                    queue.update_task_state(
                        queue_task.task_id,
                        state,
                        started_at=scheduler_task.submitted_at,
                        completed_at=scheduler_task.completed_at,
                        stdout=scheduler_task.result or "",
                    )

                migrated_count += 1
                print("  ✅ Migrated")
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                skipped_count += 1
        else:
            print("  [DRY RUN] Would migrate")
            migrated_count += 1

        print()

    print(f"{'=' * 60}")
    if dry_run:
        print(f"DRY RUN: Would migrate {migrated_count} tasks")
    else:
        print(f"✅ Migrated {migrated_count} tasks")

    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} tasks (errors)")
    print(f"{'=' * 60}\n")

    if not dry_run:
        print("Tasks are now in the database. The runtime daemon will process them.")
        print("\nNext steps:")
        print(
            "1. Check database: sqlite3 ~/.cortex/batch/batch_queue.db 'SELECT COUNT(*), state FROM batch_tasks GROUP BY state'"
        )
        print("2. Monitor logs: tail -f ~/.cortex/logs/batch_daemon.stdout.log")
        print("3. The daemon should pick them up on the next cycle (60s)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate batch tasks from JSON to SQLite DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually doing it",
    )
    parser.add_argument("--execute", action="store_true", help="Actually perform the migration")

    args = parser.parse_args()

    if not args.execute and not args.dry_run:
        print("Usage:")
        print("  --dry-run    Show what would be migrated")
        print("  --execute    Actually perform the migration")
        sys.exit(1)

    migrate_tasks(dry_run=args.dry_run)
