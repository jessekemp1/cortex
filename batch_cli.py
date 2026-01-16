#!/usr/bin/env python3
"""
Batch API Scheduler CLI

Schedule work to run via Batch API for 50% cost savings and reduced real-time usage.

Usage:
    python batch_cli.py schedule "Analyze VortexV2 performance" --prompt "..." --priority high
    python batch_cli.py list [--status pending|submitted|completed]
    python batch_cli.py submit  # Submit ready tasks now
    python batch_cli.py check   # Check for completed tasks
    python batch_cli.py stats [--days 7]
    python batch_cli.py plan cortex-enhancements-2025  # Convert Cortex plan to batch tasks
"""

import argparse
import json

# Import batch_scheduler directly to avoid __init__ dependency issues
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "batch"))
from batch_scheduler import BatchScheduler, create_batch_plan_from_cortex_plan


def schedule_task(args):
    """Schedule a new batch task"""
    scheduler = BatchScheduler()

    task = scheduler.schedule_task(
        title=args.title,
        description=args.description or args.title,
        prompt=args.prompt,
        priority=args.priority,
        deadline_hours=args.deadline_hours,
    )

    print(f"✅ Scheduled batch task: {task.id}")
    print(f"   Title: {task.title}")
    print(f"   Estimated tokens: {task.estimated_input_tokens + task.estimated_output_tokens:,}")
    print(f"   Submit after: {task.submit_after.strftime('%Y-%m-%d %I:%M %p')}")
    print(f"   Deadline: {task.deadline.strftime('%Y-%m-%d %I:%M %p')}")
    print()
    print(f"💰 Estimated savings: 50% vs real-time")


def list_tasks(args):
    """List batch tasks"""
    scheduler = BatchScheduler()

    if args.status == "pending":
        tasks = scheduler.get_pending_tasks()
    elif args.status == "submitted":
        tasks = scheduler.get_submitted_tasks()
    elif args.status == "completed":
        tasks = scheduler.get_completed_tasks(days=args.days or 7)
    else:
        tasks = scheduler.tasks

    if not tasks:
        print(f"No {args.status} tasks found")
        return

    print(f"\n{'ID':<25} {'Title':<40} {'Status':<12} {'Tokens':<10}")
    print("=" * 90)

    for task in tasks:
        tokens = (
            task.actual_input_tokens + task.actual_output_tokens
            if task.status == "completed"
            else task.estimated_input_tokens + task.estimated_output_tokens
        )

        print(f"{task.id:<25} {task.title[:38]:<40} {task.status:<12} {tokens:>8,}")

    print(f"\nTotal: {len(tasks)} tasks")


def submit_ready(args):
    """Submit ready tasks"""
    scheduler = BatchScheduler()
    submitted = scheduler.submit_ready_tasks()

    if not submitted:
        pending = scheduler.get_pending_tasks()
        if pending:
            next_task = pending[0]
            print(f"No tasks ready to submit yet.")
            print(f"Next task submits at: {next_task.submit_after.strftime('%Y-%m-%d %I:%M %p')}")
        else:
            print("No pending tasks to submit.")
        return

    print(f"✅ Submitted {len(submitted)} batch tasks:")
    for task in submitted:
        print(f"   • {task.title} (batch_id: {task.batch_id})")


def check_completed(args):
    """Check for completed tasks"""
    scheduler = BatchScheduler()
    completed = scheduler.check_completed_tasks()

    if not completed:
        processing = scheduler.get_submitted_tasks()
        if processing:
            print(f"No new completions. {len(processing)} tasks still processing...")
        else:
            print("No tasks currently processing.")
        return

    print(f"✅ Retrieved {len(completed)} batch results:")
    for task in completed:
        if task.status == "completed":
            print(f"   ✓ {task.title}")
            print(f"     Tokens: {task.actual_input_tokens + task.actual_output_tokens:,}")
            if task.result:
                print(f"     Result: {len(task.result)} characters")
        else:
            print(f"   ✗ {task.title} - FAILED")
            print(f"     Error: {task.result}")


def show_stats(args):
    """Show usage statistics"""
    scheduler = BatchScheduler()
    stats = scheduler.get_usage_stats(days=args.days)

    print(f"\n📊 Batch API Usage Statistics ({stats['days_analyzed']} days)")
    print("=" * 60)
    print(f"Tasks completed:        {stats['tasks_completed']}")
    print(f"Total tokens:           {stats['total_tokens']:,}")
    print(f"  Input tokens:         {stats['total_input_tokens']:,}")
    print(f"  Output tokens:        {stats['total_output_tokens']:,}")
    print()
    print(f"💰 Cost Analysis:")
    print(f"  Real-time cost:       ${stats['estimated_real_time_cost']:.2f}")
    print(f"  Batch cost:           ${stats['estimated_batch_cost']:.2f}")
    print(
        f"  Savings:              ${stats['estimated_savings']:.2f} ({stats['savings_percentage']:.0f}%)"
    )


def convert_plan(args):
    """Convert Cortex plan to batch tasks"""
    scheduler = BatchScheduler()

    try:
        batch_tasks = create_batch_plan_from_cortex_plan(args.plan_id, scheduler)

        print(f"✅ Created {len(batch_tasks)} batch tasks from plan: {args.plan_id}")
        print()

        total_tokens = sum(
            t.estimated_input_tokens + t.estimated_output_tokens for t in batch_tasks
        )
        print(f"Total estimated tokens: {total_tokens:,}")
        print()

        print("Tasks scheduled:")
        for task in batch_tasks:
            print(f"  • {task.title}")
            print(f"    Submit: {task.submit_after.strftime('%Y-%m-%d %I:%M %p')}")
            print(f"    Tokens: ~{task.estimated_input_tokens + task.estimated_output_tokens:,}")

        print()
        print("💡 Tip: Run 'python batch_cli.py submit' at 6 PM to submit these tasks")

    except Exception as e:
        print(f"❌ Error converting plan: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Batch API Scheduler - Optimize Claude usage with 50% cost savings"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Schedule a new batch task")
    schedule_parser.add_argument("title", help="Task title")
    schedule_parser.add_argument("--prompt", required=True, help="Prompt for Claude")
    schedule_parser.add_argument("--description", help="Task description")
    schedule_parser.add_argument("--priority", choices=["low", "normal", "high"], default="normal")
    schedule_parser.add_argument(
        "--deadline-hours",
        type=int,
        default=48,
        help="Hours until results needed (default: 48)",
    )
    schedule_parser.set_defaults(func=schedule_task)

    # List command
    list_parser = subparsers.add_parser("list", help="List batch tasks")
    list_parser.add_argument(
        "--status",
        choices=["pending", "submitted", "completed", "all"],
        default="all",
        help="Filter by status",
    )
    list_parser.add_argument("--days", type=int, help="Days to look back for completed tasks")
    list_parser.set_defaults(func=list_tasks)

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit ready tasks")
    submit_parser.set_defaults(func=submit_ready)

    # Check command
    check_parser = subparsers.add_parser("check", help="Check for completed tasks")
    check_parser.set_defaults(func=check_completed)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show usage statistics")
    stats_parser.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    stats_parser.set_defaults(func=show_stats)

    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Convert Cortex plan to batch tasks")
    plan_parser.add_argument("plan_id", help="Cortex plan ID (e.g., cortex-enhancements-2025)")
    plan_parser.set_defaults(func=convert_plan)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
