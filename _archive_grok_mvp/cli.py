#!/usr/bin/env python3
"""
Converx CLI - Command-line interface for strategic orchestrator

Usage:
    converx next [PROJECT] [--with-context] [--json]
    converx status
"""

import argparse
import sys
from pathlib import Path

from orchestrator import ConverxOrchestrator
from formatter import ConverxFormatter
from feedback import FeedbackLogger


def cmd_next(args):
    """Get next action."""
    orchestrator = ConverxOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(
            project_filter=args.project,
            include_context=args.with_context,
            limit=args.limit
        )

        formatter = ConverxFormatter()
        output = formatter.format_response(response, json_output=args.json)
        print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show current state summary."""
    orchestrator = ConverxOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(limit=0)  # Just get state, no recommendations

        state = response.current_state
        health = response.system_health

        print("╔══════════════════════════════════════════════════════╗")
        print("║              CONVERX - CURRENT STATE                  ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        print("📊 PROJECTS")
        print("────────────────")
        total = state.get("total_projects", 0)
        active = state.get("active_projects", 0)
        recent = state.get("recent_projects", 0)
        dormant = state.get("dormant_projects", 0)

        print(f"Total: {total}")
        print(f"  Active (3+ commits in 7d): {active}")
        print(f"  Recent (commits in 7d): {recent}")
        print(f"  Dormant (only 30d commits): {dormant}")
        print("")

        print("🎯 GOALS")
        print("────────────────")
        priority_a = state.get("priority_a_goals", 0)
        priority_b = state.get("priority_b_goals", 0)
        priority_c = state.get("priority_c_goals", 0)
        pending = state.get("goals_pending", 0)
        in_progress = state.get("goals_in_progress", 0)

        if priority_a > 0:
            print(f"Priority A: {priority_a}")
        if priority_b > 0:
            print(f"Priority B: {priority_b}")
        if priority_c > 0:
            print(f"Priority C: {priority_c}")
        print(f"Status: {in_progress} in progress, {pending} pending")
        print("")

        blockers = state.get("blockers", [])
        if blockers:
            print("⚠️  BLOCKERS")
            print("────────────────")
            for blocker in blockers:
                print(f"  • {blocker['project']}: {blocker['blocker']}")
            print("")

        # System Health
        print("🔧 SYSTEM HEALTH")
        print("────────────────")
        status_icon = "✅" if health.all_active else "⚠️"
        print(f"{status_icon} Integrations: {health.active_count}/4 active")
        if not health.all_active:
            missing = []
            if not health.project_scanner:
                missing.append("Project Scanner")
            if not health.goal_parser:
                missing.append("Goal Parser")
            if not health.recommendation_engine:
                missing.append("Recommendation Engine")
            if not health.context_intelligence:
                missing.append("Context Intelligence")
            if missing:
                print(f"   Missing: {', '.join(missing)}")
        print("")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_feedback(args):
    """Log feedback for a recommendation (Golden Spec: Verification Loop)."""
    logger = FeedbackLogger()
    
    if args.stats:
        # Show feedback statistics
        stats = logger.get_stats()
        print("╔══════════════════════════════════════════════════════╗")
        print("║              CONVERX - FEEDBACK STATS                 ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        print(f"Total Entries: {stats['total_entries']}")
        print(f"Useful: {stats['useful_count']}")
        print(f"Not Useful: {stats['not_useful_count']}")
        if stats['total_entries'] > 0:
            print(f"Useful Rate: {stats['useful_rate']:.1%}")
        print(f"Log File: {stats['log_file']}")
        print("")
        
        if args.stats == "recent":
            recent = logger.get_recent(limit=5)
            if recent:
                print("Recent Feedback:")
                for entry in recent:
                    useful_icon = "✅" if entry.get("useful") else "❌"
                    print(f"  {useful_icon} {entry.get('action_title', 'Unknown')}")
                    if entry.get("notes"):
                        print(f"     {entry['notes']}")
    elif args.log:
        # Quick log entry
        logger.log_quick(args.log)
        print(f"✓ Logged: {args.log}")
    else:
        # Interactive feedback
        action_title = args.action_title or "Last Recommendation"
        useful = args.useful.lower() in ["yes", "y", "true", "1"]
        
        logger.log_feedback(
            action_title=action_title,
            useful=useful,
            action_id=args.action_id,
            notes=args.notes,
            actual_outcome=args.outcome
        )
        
        print(f"✓ Feedback logged: {action_title} - {'Useful' if useful else 'Not Useful'}")


def cmd_health(args):
    """Show system health check (Golden Spec: Dependency Transparency)."""
    orchestrator = ConverxOrchestrator(root_dir=Path(args.root))
    
    try:
        response = orchestrator.get_next_action(limit=0)
        health = response.system_health
        
        print("╔══════════════════════════════════════════════════════╗")
        print("║              CONVERX - SYSTEM HEALTH                  ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        
        integrations = [
            ("Project Scanner", health.project_scanner, "Scans git repos for activity"),
            ("Goal Parser", health.goal_parser, "Parses goals from ACTION_PLAN.md"),
            ("Recommendation Engine", health.recommendation_engine, "Generates strategic recommendations"),
            ("Context Intelligence", health.context_intelligence, "Predicts needed context")
        ]
        
        for name, active, description in integrations:
            status = "✅ Active" if active else "❌ Missing"
            print(f"{status:12} {name}")
            print(f"             {description}")
            print("")
        
        print("──────────────────────────────────────────────────────")
        overall = "✅ All Systems Operational" if health.all_active else "⚠️  Degraded Mode"
        print(f"{overall}")
        print(f"Active: {health.active_count}/4 integrations")
        print("")
        
        if not health.all_active:
            print("Note: System will work with reduced capability.")
            print("      Some features may be unavailable.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Converx - Strategic Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  converx next                    # Get next action
  converx next vortexv2          # Get next action for VortexV2
  converx next --with-context    # Include context predictions
  converx next --json            # JSON output
  converx status                 # Show current state
  converx health                 # Show system health
  converx feedback --stats       # Show feedback statistics
  converx feedback --log "Note"  # Quick log entry
        """
    )

    parser.add_argument(
        "--root",
        type=str,
        default="/Users/jesse.kemp/Dev",
        help="Root directory to scan (default: /Users/jesse.kemp/Dev)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Next command
    next_parser = subparsers.add_parser("next", help="Get next action")
    next_parser.add_argument(
        "project",
        nargs="?",
        help="Filter by project name (optional)"
    )
    next_parser.add_argument(
        "--with-context",
        action="store_true",
        help="Include context predictions"
    )
    next_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON format"
    )
    next_parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of alternative actions to show (default: 3)"
    )
    next_parser.set_defaults(func=cmd_next)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current state")
    status_parser.set_defaults(func=cmd_status)

    # Health command
    health_parser = subparsers.add_parser("health", help="Show system health check")
    health_parser.set_defaults(func=cmd_health)

    # Feedback command
    feedback_parser = subparsers.add_parser("feedback", help="Log feedback for recommendations")
    feedback_parser.add_argument(
        "--action-title",
        type=str,
        help="Title of the action/recommendation"
    )
    feedback_parser.add_argument(
        "--action-id",
        type=str,
        help="ID of the action (if available)"
    )
    feedback_parser.add_argument(
        "--useful",
        type=str,
        required=False,
        help="Was it useful? (yes/no)"
    )
    feedback_parser.add_argument(
        "--notes",
        type=str,
        help="Optional notes"
    )
    feedback_parser.add_argument(
        "--outcome",
        type=str,
        help="What actually happened?"
    )
    feedback_parser.add_argument(
        "--stats",
        type=str,
        nargs="?",
        const="summary",
        help="Show feedback statistics (use 'recent' for recent entries)"
    )
    feedback_parser.add_argument(
        "--log",
        type=str,
        help="Quick log entry (general note)"
    )
    feedback_parser.set_defaults(func=cmd_feedback)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

