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

try:
    from .formatter import ConverxFormatter
    from .orchestrator import ConverxOrchestrator
except ImportError:
    # Allow standalone execution
    from formatter import ConverxFormatter

    from orchestrator import ConverxOrchestrator


def cmd_next(args):
    """Get next action."""
    orchestrator = ConverxOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(
            project_filter=args.project,
            include_context=args.with_context,
            limit=args.limit,
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
        response = orchestrator.get_next_action(
            limit=0
        )  # Just get state, no recommendations

        state = response.current_state

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
        """,
    )

    parser.add_argument(
        "--root",
        type=str,
        default="/Users/jesse.kemp/Dev",
        help="Root directory to scan (default: /Users/jesse.kemp/Dev)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Next command
    next_parser = subparsers.add_parser("next", help="Get next action")
    next_parser.add_argument(
        "project", nargs="?", help="Filter by project name (optional)"
    )
    next_parser.add_argument(
        "--with-context", action="store_true", help="Include context predictions"
    )
    next_parser.add_argument("--json", action="store_true", help="Output JSON format")
    next_parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of alternative actions to show (default: 3)",
    )
    next_parser.set_defaults(func=cmd_next)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current state")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
