#!/usr/bin/env python3
"""
CLI utility for Cortex task queue system.

Usage:
    python orchestration/cli.py add --title "Fix bug" --priority A --description "Fix the login bug"
    python orchestration/cli.py list
    python orchestration/cli.py stats
    python orchestration/cli.py next
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.scheduler import TaskScheduler
from orchestration.task import Task, TaskPriority
from orchestration.task_queue import TaskQueue


def cmd_add(args):
    """Add a new task to the queue"""
    scheduler = TaskScheduler()

    # Parse deadline
    deadline = None
    if args.deadline_hours:
        deadline = datetime.now() + timedelta(hours=args.deadline_hours)

    # Create task (use microseconds to avoid ID collisions)
    task = Task(
        id=f"task-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}",
        title=args.title,
        description=args.description,
        priority=TaskPriority(args.priority),
        deadline=deadline,
        prompt=args.prompt,
        tags=args.tags.split(",") if args.tags else [],
        source=args.source,
        project=args.project,
    )

    # Schedule and enqueue
    decision = scheduler.enqueue_and_schedule(task)

    print(f"✓ Task added: {task.id}")
    print(f"  Title: {task.title}")
    print(f"  Priority: {task.priority.value}")
    print(f"  Routing: {decision.execution_mode.upper()}")
    print(f"  Reason: {decision.reason}")
    if deadline:
        print(
            f"  Deadline: {deadline.strftime('%Y-%m-%d %H:%M')} ({task.hours_until_deadline:.1f}h)"
        )


def cmd_list(args):
    """List tasks in queue"""
    queue = TaskQueue()

    if args.status:
        from orchestration.task import TaskStatus

        tasks = queue.get_all(status=TaskStatus(args.status))
    else:
        tasks = queue.get_ready_tasks(limit=args.limit)

    if not tasks:
        print("No tasks found.")
        return

    print(f"\n{'ID':<20} {'Priority':<8} {'Title':<30} {'Status':<12} {'Mode':<10}")
    print("-" * 90)

    for task in tasks:
        mode = task.execution_mode or "unscheduled"
        print(
            f"{task.id:<20} {task.priority.value:<8} {task.title[:30]:<30} {task.status.value:<12} {mode:<10}"
        )


def cmd_stats(args):
    """Show queue statistics"""
    queue = TaskQueue()
    scheduler = TaskScheduler(queue=queue)

    queue_stats = queue.get_stats()
    sched_stats = scheduler.get_scheduling_stats()
    cost_savings = scheduler.estimate_batch_cost_savings()

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║            CORTEX TASK QUEUE STATISTICS             ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    print("📊 QUEUE STATUS")
    print("──────────────")
    print(f"Total tasks:     {queue_stats['total']}")
    print(f"Pending:         {queue_stats['pending']}")
    print(f"Running:         {queue_stats['running']}")
    print(f"Completed:       {queue_stats['completed']}")
    print(f"Failed:          {queue_stats['failed']}")
    print(f"Blocked:         {queue_stats['blocked']}")
    print(f"Ready to run:    {queue_stats['ready']}")
    print()

    print("🎯 BY PRIORITY")
    print("──────────────")
    for priority, count in queue_stats["by_priority"].items():
        if count > 0:
            print(f"{priority}: {count}")
    print()

    print("🔀 EXECUTION ROUTING")
    print("────────────────────")
    print(f"Realtime:        {sched_stats['realtime']}")
    print(f"Batch:           {sched_stats['batch']}")
    print(f"Unscheduled:     {sched_stats['unscheduled']}")
    print(f"Urgent tasks:    {sched_stats['urgent']}")
    print()

    print("💰 BATCH COST SAVINGS")
    print("─────────────────────")
    print(f"Batch tasks:     {cost_savings['batch_tasks']}")
    print(f"Total tokens:    {cost_savings['total_tokens']:,}")
    print(f"Realtime cost:   ${cost_savings['realtime_cost_usd']:.2f}")
    print(f"Batch cost:      ${cost_savings['batch_cost_usd']:.2f}")
    print(
        f"Savings:         ${cost_savings['savings_usd']:.2f} ({cost_savings['savings_pct']:.0f}%)"
    )
    print()


def cmd_next(args):
    """Get next task for execution"""
    scheduler = TaskScheduler()

    if args.mode == "realtime":
        task = scheduler.get_next_realtime_task()
        mode = "realtime"
    elif args.mode == "batch":
        tasks = scheduler.get_next_batch_tasks(limit=1)
        task = tasks[0] if tasks else None
        mode = "batch"
    else:
        # Get highest priority regardless of mode
        task = scheduler.queue.peek()
        mode = task.execution_mode if task else None

    if not task:
        print(f"No {args.mode or 'available'} tasks ready.")
        return

    print(f"\n🎯 Next {mode.upper()} Task")
    print("─" * 50)
    print(f"ID:          {task.id}")
    print(f"Title:       {task.title}")
    print(f"Priority:    {task.priority.value}")
    print(f"Phase:       {task.phase.value}")
    print(f"Description: {task.description}")
    if task.deadline:
        print(
            f"Deadline:    {task.deadline.strftime('%Y-%m-%d %H:%M')} ({task.hours_until_deadline:.1f}h)"
        )
    print(f"Tokens:      {task.total_estimated_tokens:,}")
    if task.blocked_by:
        print(f"Blocked by:  {', '.join(task.blocked_by)}")
    print()


def cmd_clear(args):
    """Clear all tasks (use with caution)"""
    queue = TaskQueue()

    if not args.force:
        print("⚠️  This will delete ALL tasks from the queue.")
        print("   Use --force to confirm.")
        return

    queue.clear()
    print("✓ Queue cleared.")


def main():
    parser = argparse.ArgumentParser(description="Cortex Task Queue CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add task
    add_parser = subparsers.add_parser("add", help="Add a task to the queue")
    add_parser.add_argument("--title", required=True, help="Task title")
    add_parser.add_argument("--description", required=True, help="Task description")
    add_parser.add_argument(
        "--priority", required=True, choices=["A", "B", "C"], help="Priority level"
    )
    add_parser.add_argument("--deadline-hours", type=float, help="Deadline in hours from now")
    add_parser.add_argument("--prompt", help="Agent prompt (optional)")
    add_parser.add_argument("--tags", help="Comma-separated tags")
    add_parser.add_argument("--source", help="Task source (goal, pattern, security, etc.)")
    add_parser.add_argument("--project", help="Project name")

    # List tasks
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=20, help="Max tasks to show")

    # Stats
    subparsers.add_parser("stats", help="Show queue statistics")

    # Next task
    next_parser = subparsers.add_parser("next", help="Get next task for execution")
    next_parser.add_argument(
        "--mode", choices=["realtime", "batch"], help="Filter by execution mode"
    )

    # Clear queue
    clear_parser = subparsers.add_parser("clear", help="Clear all tasks (use with caution)")
    clear_parser.add_argument("--force", action="store_true", help="Confirm deletion")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Dispatch to command handler
    command_map = {
        "add": cmd_add,
        "list": cmd_list,
        "stats": cmd_stats,
        "next": cmd_next,
        "clear": cmd_clear,
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()


if __name__ == "__main__":
    main()
