"""
Cortex CLI package - main() entry point with dispatcher to cli/commands/.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

# Add cortex directory and its parent to path to support both module and direct execution
# Note: __file__ is cli/__init__.py, so parent.parent is the cortex root
cortex_dir = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_dir))
sys.path.insert(0, str(cortex_dir.parent))

# Fallback: Add user site-packages if dependencies are missing (e.g. structlog)
site_packages = Path.home() / "Library/Python/3.9/lib/python/site-packages"
if site_packages.exists() and str(site_packages) not in sys.path:
    sys.path.append(str(site_packages))


from formatter import CortexFormatter

from briefing import (
    format_briefing,
    format_briefing_json,
    format_statusline,
    format_statusline_json,
    generate_daily_briefing,
    get_briefing_signal_quality,
    get_briefing_style,
    get_briefing_style_path,
    validate_briefing_style,
)
from feedback import FeedbackLogger
from goal_parser import GoalParser
from learning import LearningSystem
from orchestrator import CortexOrchestrator

try:
    from ai_intelligence import ProjectScanner
except ImportError:
    ProjectScanner = None

logger = logging.getLogger(__name__)

# Deep mode intelligence (Phase 1 Integration)
try:
    from bridge import CortexBridge
    from intelligence.adaptive_latency import DEEP_MODE, FAST_MODE, AnalysisMode
    from intelligence.cli_display import (
        display_deep_intelligence,
        display_error,
        display_quick_intelligence,
        format_mode_info,
    )

    DEEP_MODE_AVAILABLE = True
except ImportError:
    DEEP_MODE_AVAILABLE = False

# Model selection intelligence (Week 1)
try:
    from datetime import datetime, timedelta

    from intelligence.model_selection import (
        ContextAwareModelRecommender,
        OrchestrationContext,
    )

    MODEL_SELECTION_AVAILABLE = True
except ImportError:
    MODEL_SELECTION_AVAILABLE = False


# Import command implementations from submodules
from cli.commands import (
    cmd_next,
    cmd_init,
    cmd_status,
    cmd_health,
    cmd_briefing,
    cmd_briefing_style,
    cmd_statusline,
    cmd_reflect,
    cmd_deep,
    cmd_quick,
    cmd_auto,
    cmd_config,
    cmd_intelligence,
    cmd_portfolio,
    cmd_deps,
    cmd_tooling,
    cmd_feedback,
    cmd_learn,
    cmd_interactions,
    cmd_batch_status,
    cmd_v2a_batch,
    cmd_schedule,
    cmd_execute,
    cmd_orchestrate,
    cmd_notify,
    cmd_git,
    cmd_sync,
    cmd_docs,
    cmd_dashboard,
    cmd_bandwidth,
    cmd_watch,
    cmd_batch_fill,
)

# Re-export helper functions for backward compatibility (tests import these from cli)
from cli.commands._helpers import (
    _goal_counts_from_parser,
    _compute_signal_quality,
    _get_root_signal_quality,
    _portfolio_counts_from_scanner,
    _apply_signal_gate_to_briefing,
    get_model_recommendation,
)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cortex - Strategic Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cortex next                    # Get next action
  cortex next vortex-backend    # Get next action for Vortex backend
  cortex next --with-context    # Include context predictions
  cortex next --json            # JSON output
  cortex execute                # Execute top recommendation
  cortex execute 2              # Execute 2nd recommendation
  cortex execute --id blocker_1 # Execute specific recommendation by ID
  cortex status                 # Show current state
  cortex health                 # Show system health
  cortex briefing               # Generate daily briefing
  cortex briefing --format=json # Daily briefing in JSON
  cortex statusline             # Compact line for Claude statusLine
  cortex feedback --stats       # Show feedback statistics
  cortex feedback --log "Note"  # Quick log entry

Deep Mode (Phase 1):
  cortex deep                   # Comprehensive analysis (2-5s)
  cortex deep --verbose         # Full details
  cortex deep --json            # JSON output
  cortex quick                  # Fast analysis (<1s)
  cortex auto                   # Adaptive mode selection
  cortex config --show          # Show configuration
  cortex config --set-default deep  # Set default mode
        """,
    )

    parser.add_argument(
        "--root",
        type=str,
        default=os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())),
        help="Root directory to scan (default: ~/projects)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Next command
    next_parser = subparsers.add_parser("next", help="Get next action")
    next_parser.add_argument("project", nargs="?", help="Filter by project name (optional)")
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

    # Init command
    init_parser = subparsers.add_parser(
        "init", help="Initialize Cortex configuration and directories"
    )
    init_parser.add_argument(
        "--root-dir", type=str, default="", help="Set workspace root directory in config"
    )
    init_parser.set_defaults(func=cmd_init)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current state")
    status_parser.set_defaults(func=cmd_status)

    # Health command
    health_parser = subparsers.add_parser("health", help="Show system health check")
    health_parser.add_argument(
        "--providers", action="store_true", help="Show AI provider status and pricing"
    )
    health_parser.set_defaults(func=cmd_health)

    # Feedback command
    feedback_parser = subparsers.add_parser("feedback", help="Log feedback for recommendations")
    feedback_parser.add_argument(
        "--action-title", type=str, help="Title of the action/recommendation"
    )
    feedback_parser.add_argument("--action-id", type=str, help="ID of the action (if available)")
    feedback_parser.add_argument(
        "--useful", type=str, required=False, help="Was it useful? (yes/no)"
    )
    feedback_parser.add_argument("--notes", type=str, help="Optional notes")
    feedback_parser.add_argument("--outcome", type=str, help="What actually happened?")
    feedback_parser.add_argument(
        "--stats",
        type=str,
        nargs="?",
        const="summary",
        help="Show feedback statistics (use 'recent' for recent entries)",
    )
    feedback_parser.add_argument("--log", type=str, help="Quick log entry (general note)")
    feedback_parser.set_defaults(func=cmd_feedback)

    # Notify command
    notify_parser = subparsers.add_parser("notify", help="Send notifications")
    notify_parser.add_argument(
        "--type",
        choices=["morning", "evening", "custom"],
        default="custom",
        help="Type of notification",
    )
    notify_parser.add_argument(
        "--channel",
        action="append",
        choices=["terminal", "email", "all"],
        help="Notification channels (can specify multiple)",
    )
    notify_parser.add_argument("--message", type=str, help="Custom message content")
    notify_parser.add_argument("--title", type=str, help="Custom notification title")
    notify_parser.set_defaults(func=cmd_notify)

    # Check command (Golden Spec Validator)
    def cmd_check(args):
        """Check project alignment with Golden Spec."""
        from golden_spec_validator import GoldenSpecValidator

        validator = GoldenSpecValidator(Path(args.root))

        target_projects = (
            [args.project]
            if args.project
            else [
                p.name
                for p in Path(args.root).iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ]
        )

        print("╔══════════════════════════════════════════════════════╗")
        print("║          CORTEX - GOLDEN SPEC VALIDATOR              ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        for proj in target_projects:
            # Skip non-project dirs in bulk scan
            if not args.project and (
                proj in ["logs", "scripts", "reports", "archive"]
                or not (Path(args.root) / proj).is_dir()
            ):
                continue

            status = validator.validate_project(proj)
            if not status.has_spec_file and not args.project:
                # In bulk mode, skip projects without specs to reduce noise, unless they look active
                continue

            print(f"Project: {status.project_name}")
            print(f"Spec File: {status.spec_path or '❌ Missing'}")

            # Draw score bar
            bar_len = int(status.compliance_score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"Compliance: {bar} {status.compliance_score:.0%}")

            if status.has_spec_file:
                print("\n  Phases:")
                for phase in status.phases:
                    icon = "✅" if phase.completed else "⭕"
                    print(f"  {icon} {phase.name}")

            if status.recommendations:
                print("\n  Recommendations:")
                for rec in status.recommendations:
                    print(f"  • {rec}")
            print("\n" + "─" * 40 + "\n")

    check_parser = subparsers.add_parser("check", help="Check project compliance with Golden Spec")
    check_parser.add_argument("project", nargs="?", help="Project to check")
    check_parser.set_defaults(func=cmd_check)

    # Draft command (Spec Generator)
    def cmd_draft(args):
        """Draft a new Golden Spec from intent."""
        from spec_generator import SpecGenerator

        generator = SpecGenerator(Path(args.root))

        # Determine project name: explicitly provided or current dir name
        project_name = args.project
        if not project_name:
            project_name = Path.cwd().name

        try:
            file_path = generator.generate(
                intent=args.intent, project_name=project_name, target_dir=Path.cwd()
            )
            print(f"✨ Golden Spec drafted: {file_path}")
            print(f"   Project: {project_name}")
            print(f"   Intent: {args.intent}")
            print("\nNext: Open the file and refine Phase 1 (Deep Understanding).")

        except Exception as e:
            print(f"Error drafting spec: {e}", file=sys.stderr)
            sys.exit(1)

    draft_parser = subparsers.add_parser("draft", help="Draft a new Golden Spec from intent")
    draft_parser.add_argument("intent", help="The intent or goal of the project")
    draft_parser.add_argument("--project", help="Project name (optional, defaults to current dir)")
    draft_parser.set_defaults(func=cmd_draft)

    # Learn command
    learn_parser = subparsers.add_parser("learn", help="Show learning metrics and patterns")
    learn_parser.add_argument(
        "--pipeline", action="store_true", help="Show learning pipeline run visualization"
    )
    learn_parser.set_defaults(func=cmd_learn)

    # Deep mode commands (Phase 1 Integration)
    deep_parser = subparsers.add_parser("deep", help="Run comprehensive deep analysis (2-5s)")
    deep_parser.add_argument("project", nargs="?", help="Project name (optional, auto-detected)")
    deep_parser.add_argument("--verbose", "-v", action="store_true", help="Show full analysis")
    deep_parser.add_argument("--json", "-j", action="store_true", help="Output JSON format")
    deep_parser.set_defaults(func=cmd_deep)

    quick_parser = subparsers.add_parser("quick", help="Run minimal fast analysis (<1s)")
    quick_parser.add_argument("project", nargs="?", help="Project name (optional, auto-detected)")
    quick_parser.set_defaults(func=cmd_quick)

    auto_parser = subparsers.add_parser(
        "auto", help="Run adaptive analysis (intelligent mode selection)"
    )
    auto_parser.add_argument("project", nargs="?", help="Project name (optional, auto-detected)")
    auto_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full analysis if deep mode selected"
    )
    auto_parser.set_defaults(func=cmd_auto)

    config_parser = subparsers.add_parser("config", help="Manage deep mode configuration")
    config_parser.add_argument("--show", action="store_true", help="Show current configuration")
    config_parser.add_argument("--set-default", type=str, help="Set default mode (deep/fast/auto)")
    config_parser.set_defaults(func=cmd_config)

    # Interactions command (Real-time feedback loop)
    interactions_parser = subparsers.add_parser(
        "interactions", help="Manage interaction learning (real-time feedback loop)"
    )
    interactions_parser.add_argument(
        "--process",
        action="store_true",
        help="Process queued interactions from Claude Code sessions",
    )
    interactions_parser.add_argument(
        "--patterns", action="store_true", help="Show detected interaction patterns"
    )
    interactions_parser.add_argument(
        "--tools", action="store_true", help="Show tool success rates from interactions"
    )
    interactions_parser.add_argument(
        "--setup",
        action="store_true",
        help="Show instructions to set up interaction capture hooks",
    )
    interactions_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to analyze (default: 7)"
    )
    interactions_parser.set_defaults(func=cmd_interactions)

    # Batch API status command
    batch_api_status_parser = subparsers.add_parser(
        "batch-api-status", help="Show batch API configuration"
    )
    batch_api_status_parser.set_defaults(func=cmd_batch_status)

    # V2a Batch command
    v2a_batch_parser = subparsers.add_parser("v2a-batch", help="Manage V2a sprint batch jobs")
    v2a_batch_parser.add_argument(
        "action",
        choices=["submit", "status", "retry", "cancel", "task"],
        help="Action to perform",
    )
    v2a_batch_parser.add_argument(
        "--wave", type=str, help="Wave ID (wave_1, wave_2, wave_3, wave_4)"
    )
    v2a_batch_parser.add_argument("--task-id", type=str, help="Task ID for task action")
    v2a_batch_parser.set_defaults(func=cmd_v2a_batch)

    # Dashboard command (Symbiosis Engine)
    dashboard_parser = subparsers.add_parser("dashboard", help="Show Symbiosis Engine Dashboard")
    dashboard_parser.set_defaults(func=cmd_dashboard)

    # Bandwidth command (Human-AI Bandwidth Research)
    bandwidth_parser = subparsers.add_parser(
        "bandwidth", help="Human-AI bandwidth metrics and experiments"
    )
    bandwidth_parser.add_argument(
        "action",
        nargs="?",
        choices=[
            "dashboard",
            "experiment",
            "record-prediction",
            "record-outcome",
            "calibration",
            "capture",
            "queue-slo",
            "baseline",
        ],
        default="dashboard",
        help="Action to perform (default: dashboard)",
    )
    bandwidth_parser.add_argument("--json", action="store_true", help="Output JSON format")
    bandwidth_parser.add_argument("--project", type=str, help="Filter by project")
    bandwidth_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to show (default: 7)"
    )
    bandwidth_parser.add_argument(
        "--dry-run", action="store_true", help="Preview experiments without running"
    )
    bandwidth_parser.add_argument("--status", action="store_true", help="Show experiment status")
    bandwidth_parser.add_argument("--experiment-name", type=str, help="Specific experiment to run")
    bandwidth_parser.add_argument("--prediction-id", type=str, help="Prediction ID for recording")
    bandwidth_parser.add_argument("--confidence", type=float, help="Confidence level (0-1)")
    bandwidth_parser.add_argument(
        "--source",
        type=str,
        choices=["claude", "codex", "cli", "system", "unknown"],
        help="Source tool for prediction identity propagation",
    )
    bandwidth_parser.add_argument(
        "--session-id",
        type=str,
        help="Session ID for cross-tool identity propagation",
    )
    bandwidth_parser.add_argument(
        "--domain",
        type=str,
        choices=["code", "architecture", "testing", "debugging", "planning", "documentation"],
        help="Domain for calibration",
    )
    bandwidth_parser.add_argument("--description", type=str, help="Description for prediction")
    bandwidth_parser.add_argument("--outcome", type=str, help="Outcome (true/false) for prediction")
    bandwidth_parser.add_argument("--task", type=str, help="Task description for handoff")
    bandwidth_parser.add_argument(
        "--workstream",
        type=str,
        choices=["planning", "building", "testing", "shipping", "research"],
        help="Workstream type for handoff",
    )
    bandwidth_parser.add_argument("--next-action", type=str, help="Next action for handoff")
    bandwidth_parser.set_defaults(func=cmd_bandwidth)

    # Briefing command
    briefing_parser = subparsers.add_parser("briefing", help="Generate daily briefing")
    briefing_parser.add_argument(
        "--portfolio", action="store_true", help="Show portfolio health matrix"
    )
    briefing_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    briefing_parser.add_argument("--no-color", action="store_true", help="Disable color output")
    briefing_parser.add_argument(
        "--strict-signal",
        action="store_true",
        help="Exit non-zero when signal quality is LOW",
    )
    briefing_parser.set_defaults(func=cmd_briefing)

    # Briefing style command
    briefing_style_parser = subparsers.add_parser(
        "briefing-style", help="Validate/show persistent briefing style contract"
    )
    briefing_style_parser.add_argument(
        "--validate", action="store_true", help="Validate style file and exit with status"
    )
    briefing_style_parser.add_argument(
        "--show", action="store_true", help="Print effective style JSON"
    )
    briefing_style_parser.set_defaults(func=cmd_briefing_style)

    # Statusline command
    statusline_parser = subparsers.add_parser(
        "statusline", help="Generate compact single-line status output"
    )
    statusline_parser.add_argument("--json", action="store_true", help="Output JSON")
    statusline_parser.add_argument("--no-color", action="store_true", help="Disable color output")
    statusline_parser.add_argument(
        "--max-age",
        type=int,
        default=90,
        help="Use cached output up to N seconds old (default: 90)",
    )
    statusline_parser.add_argument(
        "--refresh", action="store_true", help="Bypass cache and regenerate now"
    )
    statusline_parser.set_defaults(func=cmd_statusline)

    # Reflect command
    reflect_parser = subparsers.add_parser(
        "reflect",
        help="Weekly reflection summary from git commits, batch results, and test outcomes",
    )
    reflect_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to reflect on (default: 7)"
    )
    reflect_parser.add_argument("--json", action="store_true", help="Output JSON format")
    reflect_parser.set_defaults(func=cmd_reflect)

    # Git command
    git_parser = subparsers.add_parser("git", help="Show Git/GitHub status")
    git_parser.add_argument("--json", action="store_true", help="Output JSON format")
    git_parser.add_argument("--brief", action="store_true", help="Show brief summary")
    git_parser.add_argument(
        "--recommendations",
        "-r",
        action="store_true",
        help="Include actionable recommendations",
    )
    git_parser.set_defaults(func=cmd_git)

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Synchronize Git state")
    sync_parser.add_argument("--status", "-s", action="store_true", help="Show sync status")
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview what would happen")
    sync_parser.add_argument("--full", action="store_true", help="Full sync: fetch + pull + rebase")
    sync_parser.add_argument("--fetch", action="store_true", help="Fetch from all remotes")
    sync_parser.add_argument("--pull", action="store_true", help="Pull main branch")
    sync_parser.add_argument("--rebase", action="store_true", help="Rebase current branch on main")
    sync_parser.add_argument("--clean", action="store_true", help="Delete stale branches")
    sync_parser.add_argument("--force", action="store_true", help="Force delete unmerged branches")
    sync_parser.set_defaults(func=cmd_sync)

    # Docs command - sync documentation to Claude Projects for mobile access
    docs_parser = subparsers.add_parser(
        "docs", help="Sync docs to Claude Projects for mobile access"
    )
    docs_parser.add_argument(
        "--init", action="store_true", help="First-time setup (configure session key)"
    )
    docs_parser.add_argument(
        "--status", "-s", action="store_true", help="Show what would be synced"
    )
    docs_parser.add_argument("--add-source", metavar="PATH", help="Add a new doc source directory")
    docs_parser.add_argument("--source-name", metavar="NAME", help="Name for added source")
    docs_parser.add_argument("--force", action="store_true", help="Force full re-upload")
    docs_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    docs_parser.set_defaults(func=cmd_docs)

    # Tooling command - Claude Code tooling intelligence
    tooling_parser = subparsers.add_parser(
        "tooling", help="Claude Code tooling intelligence (hooks, commands, config)"
    )
    tooling_parser.add_argument(
        "action",
        nargs="?",
        choices=["config", "commands", "changes", "summary"],
        default="summary",
        help="Action to perform (default: summary)",
    )
    tooling_parser.add_argument(
        "--query", "-q", type=str, help="Natural language query about tooling"
    )
    tooling_parser.add_argument(
        "--days", type=int, help="Days of history for 'changes' action (default: 7)"
    )
    tooling_parser.set_defaults(func=cmd_tooling)

    # Schedule command
    schedule_parser = subparsers.add_parser(
        "schedule", help="Schedule a recommendation as a local-orchestrator agent"
    )
    schedule_parser.add_argument(
        "intent", nargs="?", help="Optional intent string (requires --team)"
    )
    schedule_parser.add_argument("--project", type=str, help="Filter by project name")
    schedule_parser.add_argument(
        "--schedule",
        type=str,
        default="0 8 * * *",
        help='Cron schedule (default: "0 8 * * *" for daily at 8 AM)',
    )
    schedule_parser.add_argument(
        "--team",
        action="store_true",
        help="Provision a full Agent Team for this intent",
    )
    schedule_parser.set_defaults(func=cmd_schedule)

    # Execute command
    execute_parser = subparsers.add_parser("execute", help="Execute a recommendation immediately")
    execute_parser.add_argument(
        "index",
        nargs="?",
        type=int,
        help="Index of recommendation to execute (1-based, optional)",
    )
    execute_parser.add_argument("--id", type=str, help="Execute recommendation by ID")
    execute_parser.add_argument("--project", type=str, help="Filter by project name")
    execute_parser.add_argument(
        "--no-feedback",
        action="store_true",
        help="Skip logging outcome to feedback system",
    )
    execute_parser.set_defaults(func=cmd_execute)

    # Orchestrate command
    orchestrate_parser = subparsers.add_parser(
        "orchestrate", help="Discover tasks, route to optimal models, and dispatch"
    )
    orchestrate_parser.add_argument(
        "task",
        nargs="?",
        default="",
        help="Task description (if empty, discovers from GOALS/taskboard)",
    )
    orchestrate_parser.add_argument(
        "--project", type=str, default="", help="Filter by project name"
    )
    orchestrate_parser.add_argument(
        "--priority",
        type=str,
        default="medium",
        choices=["critical", "high", "medium", "low"],
        help="Priority level (default: medium)",
    )
    orchestrate_parser.add_argument(
        "--dry-run", action="store_true", help="Show routing plan without dispatching"
    )
    orchestrate_parser.add_argument("--json", action="store_true", help="Output as JSON")
    orchestrate_parser.set_defaults(func=cmd_orchestrate)

    # Goal, Task, Blocker, Progress commands
    try:
        from goal_commands import register_goal_commands

        register_goal_commands(subparsers)
    except Exception as e:
        import sys as _sys

        print(f"Goal command registration failed: {e}", file=_sys.stderr)

    # Skills commands
    import asyncio

    try:
        from skills import registry

        SKILLS_AVAILABLE = True
    except ImportError:
        registry = None
        SKILLS_AVAILABLE = False

    def cmd_skill_list(args):
        """List all available skills."""
        if not SKILLS_AVAILABLE:
            print("Skills module not available.")
            return
        print(registry.list_skills())

    def cmd_skill_run(args):
        """Run a skill by name."""
        if not SKILLS_AVAILABLE:
            print("Skills module not available.")
            return

        async def run():
            result = await registry.execute_skill(args.skill_name, **vars(args))
            if result:
                print("\n" + result.to_markdown())
            else:
                print(f"Error: Skill '{args.skill_name}' not found")
                print("\nAvailable skills:")
                for skill in registry.get_all():
                    print(f"  - {skill.name}")
                sys.exit(1)

        asyncio.run(run())

    def cmd_skill_info(args):
        """Show detailed skill information."""
        if not SKILLS_AVAILABLE:
            print("Skills module not available.")
            return
        skill = registry.get(args.skill_name)
        if skill:
            print(skill.to_markdown())
        else:
            print(f"Error: Skill '{args.skill_name}' not found")
            sys.exit(1)

    def cmd_skill_schedule(args):
        """Run all scheduled skills."""
        if not SKILLS_AVAILABLE:
            print("Skills module not available.")
            return

        async def run():
            results = await registry.execute_scheduled()
            print(f"\nExecuted {len(results)} scheduled skills")
            for result in results:
                print(f"  - {result.summary}")

        asyncio.run(run())

    # Skill subcommands
    skill_parser = subparsers.add_parser("skill", help="Manage and execute skills")
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command", help="Skill commands")

    # skill list
    skill_list_parser = skill_subparsers.add_parser("list", help="List all skills")
    skill_list_parser.set_defaults(func=cmd_skill_list)

    # skill run
    skill_run_parser = skill_subparsers.add_parser("run", help="Run a skill")
    skill_run_parser.add_argument("skill_name", help="Name of skill to run")
    skill_run_parser.add_argument(
        "--scope", type=str, help="Validation scope (for forecasting skill)"
    )
    skill_run_parser.add_argument("--symbol", type=str, help="Symbol (for trading skill)")
    skill_run_parser.add_argument("--days", type=int, help="Days (for trading skill)")
    skill_run_parser.add_argument("--directory", type=str, help="Directory (for audio skill)")
    skill_run_parser.set_defaults(func=cmd_skill_run)

    # skill info
    skill_info_parser = skill_subparsers.add_parser("info", help="Show skill information")
    skill_info_parser.add_argument("skill_name", help="Name of skill")
    skill_info_parser.set_defaults(func=cmd_skill_info)

    # skill schedule
    skill_schedule_parser = skill_subparsers.add_parser("schedule", help="Run scheduled skills")
    skill_schedule_parser.set_defaults(func=cmd_skill_schedule)

    # Process monitoring commands
    try:
        from intelligence.process_monitor import ProcessMonitor

        PROCESS_MONITOR_AVAILABLE = True
    except ImportError:
        PROCESS_MONITOR_AVAILABLE = False

    def cmd_process_status(args):
        """Show current process status."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Process monitoring not available. Run: pip install psutil")
            return

        monitor = ProcessMonitor()
        status = monitor.get_status()

        print("╔══════════════════════════════════════════════════════╗")
        print("║          CORTEX - PROCESS MONITOR STATUS             ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        print("💻 SYSTEM RESOURCES")
        print("────────────────")
        print(
            f"CPU Usage:     {status['cpu_percent']:.1f}% ({status['cpu_available']:.1f}% available)"
        )
        print(
            f"Memory Usage:  {status['memory_usage_percent']:.1f}% ({status['memory_available_mb']:.0f} MB available)"
        )
        print(f"Processes:     {status['process_count']}")
        print("")
        print("🤖 AI TOOLS & SERVICES")
        print("────────────────")
        print(f"AI Tool CPU:   {status['ai_tool_cpu']:.1f}%")
        print(f"Dev Service CPU: {status['dev_service_cpu']:.1f}%")
        print("")
        print("⚠️  ALERTS")
        print("────────────────")
        print(f"Total Alerts:   {status['alerts_count']}")
        print(f"Critical:       {status['critical_alerts']}")
        print("")
        print("♻️  OPTIMIZATION")
        print("────────────────")
        print(f"Waste Items:    {status['waste_items']}")
        print(f"Optimizations:  {status['optimization_opportunities']}")

    def cmd_process_waste(args):
        """Show detected resource waste."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Process monitoring not available. Run: pip install psutil")
            return

        monitor = ProcessMonitor()
        waste_summary = monitor.optimizer.get_waste_summary()

        print("╔══════════════════════════════════════════════════════╗")
        print("║         CORTEX - RESOURCE WASTE DETECTION            ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if waste_summary["total_waste_items"] == 0:
            print("✅ No resource waste detected!")
            return

        print(f"Total Waste Items: {waste_summary['total_waste_items']}")
        print(f"Auto-actionable:   {waste_summary['auto_actionable']}")
        print(f"Manual Review:     {waste_summary['manual_review']}")
        print("")

        # Group by type
        for waste_type, count in waste_summary["by_type"].items():
            print(f"  {waste_type}: {count}")
        print("")

        # Show details
        print("DETAILS")
        print("────────────────")
        for item in waste_summary["items"][:10]:  # Show top 10
            auto_marker = "🤖" if item["auto_actionable"] else "👁️"
            print(f"{auto_marker} {item['process_name']}")
            print(f"   Type: {item['waste_type']}")
            print(f"   Cost: {item['resource_cost']}")
            print(f"   Recommendation: {item['recommendation']}")
            print("")

    def cmd_process_optimize(args):
        """Show optimization suggestions."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Process monitoring not available. Run: pip install psutil")
            return

        monitor = ProcessMonitor()
        optimizations = monitor.optimizer.suggest_optimizations()

        print("╔══════════════════════════════════════════════════════╗")
        print("║       CORTEX - OPTIMIZATION SUGGESTIONS              ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if not optimizations:
            print("✅ No optimization opportunities found!")
            return

        for i, opt in enumerate(optimizations, 1):
            priority_icons = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "🟢",
            }
            icon = priority_icons.get(opt.priority, "⚪")

            print(f"{icon} [{opt.priority}] {opt.title}")
            print(f"   {opt.description}")
            print(f"   Savings: {opt.estimated_savings}")
            if opt.action_command:
                print(f"   Command: {opt.action_command}")
            print("")

    def cmd_process_insights(args):
        """Show utilization insights and patterns."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Process monitoring not available. Run: pip install psutil")
            return

        monitor = ProcessMonitor()
        insights = monitor.get_insights(days=args.days)

        print("╔══════════════════════════════════════════════════════╗")
        print("║        CORTEX - UTILIZATION INSIGHTS                 ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        # Utilization patterns
        util = insights["utilization"]
        print("📊 UTILIZATION PATTERNS")
        print("────────────────")
        print(f"Peak Hours:     {', '.join(f'{h:02d}:00' for h in util['peak_hours'])}")
        print(f"Idle Hours:     {', '.join(f'{h:02d}:00' for h in util['idle_hours'])}")
        print(f"Capacity Headroom: {util['capacity_headroom']:.1f}%")
        print("")

        # AI tools
        if insights["ai_tools"]:
            print("🤖 AI TOOL USAGE")
            print("────────────────")
            for tool in insights["ai_tools"]:
                print(f"{tool['tool_name']}:")
                print(f"  Usage: {tool['usage_hours']:.1f}h | Idle: {tool['idle_hours']:.1f}h")
                print(
                    f"  Avg CPU: {tool['avg_cpu']:.1f}% | Avg Memory: {tool['avg_memory']:.0f} MB"
                )
            print("")

        # Dev patterns
        dev = insights["dev_patterns"]
        print("💻 DEVELOPMENT PATTERNS")
        print("────────────────")
        print(
            f"Active Coding Hours: {', '.join(f'{h:02d}:00' for h in dev['active_coding_hours'][:5])}"
        )
        print(f"Build Frequency:     {dev['build_frequency']:.1f} builds/day")

    # === Batch Command Functions ===
    def cmd_batch_submit(args):
        """Submit job via unified orchestrator (NEW)."""
        import json

        from batch.orchestrator import BatchOrchestrator

        orchestrator = BatchOrchestrator()

        # Load job definition
        with open(args.job_file) as f:
            job_data = json.load(f)

        # Submit with auto-detection
        job_id = orchestrator.submit_job(job_data, auto_detect=True)

        # Print result with backend indicator
        backend = "LOCAL" if job_id.startswith("local_") else "API"
        print(f"✅ Job submitted to {backend} backend")
        print(f"Job ID: {job_id}")
        print(f"Description: {job_data.get('description', 'N/A')}")

    def cmd_batch_add(args):
        """Add a task to the batch queue (legacy - routes to ProcessMonitor)."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        task = monitor.batch_queue.add_task(
            command=args.command,
            task_type=args.task_type,
            description=args.description or args.command,
            priority=args.priority,
            estimated_duration_minutes=args.duration,
        )

        print("✅ Task added to LOCAL queue (ProcessMonitor)")
        print(f"Task ID: {task.task_id}")
        print(f"Command: {task.command}")
        print(f"Type: {task.task_type}")
        print(f"Priority: {task.priority}")
        print(f"State: {task.state.value}")

    def cmd_batch_list(args):
        """List batch tasks from both backends (unified view)."""
        from batch.orchestrator import BatchOrchestrator, JobBackend

        orchestrator = BatchOrchestrator()

        # Map backend arg to orchestrator format
        backend_filter = args.backend if hasattr(args, "backend") else "both"

        jobs = orchestrator.list_jobs(backend=backend_filter, limit=args.limit)

        if not jobs:
            print("No jobs found")
            return

        # Group by backend
        local_jobs = [j for j in jobs if j.backend == JobBackend.LOCAL]
        api_jobs = [j for j in jobs if j.backend == JobBackend.API]

        if local_jobs:
            print(f"\n{'=' * 80}")
            print("LOCAL EXECUTION QUEUE (ProcessMonitor)")
            print(f"{'=' * 80}")
            for job in local_jobs:
                print(f"{job.status_icon} [{job.priority.upper():8}] {job.description}")
                print(f"   ID: {job.id} | State: {job.state.value}")
                if job.error_message:
                    print(f"   Error: {job.error_message[:100]}")
                print()

        if api_jobs:
            print(f"\n{'=' * 80}")
            print("API BATCH QUEUE (Anthropic)")
            print(f"{'=' * 80}")
            for job in api_jobs:
                print(f"{job.status_icon} [{job.priority.upper():8}] {job.description}")
                print(f"   ID: {job.id} | State: {job.state.value}")
                if job.metadata.get("tokens"):
                    print(
                        f"   Tokens: {job.metadata['tokens']:,} | Tasks: {job.metadata.get('tasks', 0)}"
                    )
                if job.progress_pct > 0:
                    print(f"   Progress: {job.progress_pct:.1f}%")
                print()

        print(f"Total: {len(jobs)} jobs ({len(local_jobs)} local, {len(api_jobs)} api)")

    def cmd_batch_queue_status(args):
        """Show batch queue status."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        stats = monitor.batch_queue.get_queue_stats()

        print(f"{'=' * 70}")
        print("BATCH QUEUE STATUS")
        print(f"{'=' * 70}")
        print()

        # Task counts by state
        print("📊 TASK COUNTS")
        print("────────────────")
        print(f"Pending:    {stats.get('pending_count', 0)}")
        print(f"Scheduled:  {stats.get('scheduled_count', 0)}")
        print(f"Running:    {stats.get('running_count', 0)}")
        print(f"Completed:  {stats.get('completed_count', 0)}")
        print(f"Failed:     {stats.get('failed_count', 0)}")
        print(f"Cancelled:  {stats.get('cancelled_count', 0)}")
        print()

        # Success rate
        success_rate = stats.get("success_rate", 0)
        print(f"✅ SUCCESS RATE: {success_rate:.1%}")
        print()

        # Average durations
        if stats.get("avg_duration_by_type"):
            print("⏱️  AVERAGE DURATION BY TYPE")
            print("────────────────")
            for task_type, avg_duration in stats["avg_duration_by_type"].items():
                print(f"{task_type:20} {avg_duration:.1f}s")
            print()

        # Executor status
        executor_status = monitor.batch_executor.get_status()
        print("🔄 EXECUTOR STATUS")
        print("────────────────")
        print(
            f"Running tasks:     {executor_status['running_tasks']}/{executor_status['max_concurrent']}"
        )
        print(f"Shutdown:          {'Yes' if executor_status['shutdown'] else 'No'}")

    def cmd_batch_schedule(args):
        """Schedule pending tasks."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        print("Scheduling pending tasks...")
        results = monitor.batch_executor.schedule_pending_tasks()

        print(f"Total pending: {results['total_pending']}")
        print(f"Scheduled: {results['scheduled']}")
        print()

        if results["scheduled"] > 0:
            print("Scheduled tasks:")
            for task_info in results["tasks"]:
                print(f"✅ {task_info['description']}")
                print(f"   Time: {task_info['scheduled_time']}")
                print(f"   Reason: {task_info['reason']}")
                print()

    def cmd_batch_run(args):
        """Execute scheduled tasks."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        print("Processing scheduled tasks...")
        results = monitor.batch_executor.process_scheduled_tasks()

        print(f"Total ready: {results['total_ready']}")
        print(f"Executed: {results['executed']}")
        print(f"Deferred: {results['deferred']}")
        print()

        if results["tasks"]:
            for task_info in results["tasks"]:
                if task_info["status"] == "executing":
                    print(f"▶️  {task_info['description']}")
                    print("   Status: Executing")
                else:
                    print(f"⏸️  {task_info['description']}")
                    print("   Status: Deferred")
                    print(f"   Reason: {task_info['reason']}")
                print()

    def cmd_batch_cancel(args):
        """Cancel a task."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        success = monitor.batch_queue.cancel_task(args.task_id)

        if success:
            print(f"✅ Task {args.task_id} cancelled")
        else:
            print(f"❌ Failed to cancel task {args.task_id}")
            print("   (Task may not exist or already completed)")

    def cmd_batch_logs(args):
        """Show task execution logs."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor

        monitor = ProcessMonitor()

        task = monitor.batch_queue.get_task(args.task_id)

        if not task:
            print(f"Task {args.task_id} not found")
            sys.exit(1)

        print(f"{'=' * 70}")
        print(f"TASK: {task.description}")
        print(f"{'=' * 70}")
        print()

        print(f"Task ID:     {task.task_id}")
        print(f"Command:     {task.command}")
        print(f"Type:        {task.task_type}")
        print(f"Priority:    {task.priority}")
        print(f"State:       {task.state.value}")
        print()

        print(f"Created:     {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if task.scheduled_time:
            print(f"Scheduled:   {task.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if task.started_at:
            print(f"Started:     {task.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if task.completed_at:
            print(f"Completed:   {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Duration:    {task.actual_duration_seconds:.1f}s")
        print()

        if task.exit_code is not None:
            print(f"Exit Code:   {task.exit_code}")
            print()

        if task.stdout:
            print("STDOUT:")
            print("───────")
            print(task.stdout)
            print()

        if task.stderr:
            print("STDERR:")
            print("───────")
            print(task.stderr)
            print()

        if task.error_message:
            print(f"Error: {task.error_message}")
            print()

        if task.retry_count > 0:
            print(f"Retries: {task.retry_count}/{task.max_retries}")

    def cmd_batch_daemon_start(args):
        """Start the batch scheduler daemon."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import BatchDaemon, ProcessMonitor

        monitor = ProcessMonitor()
        daemon = BatchDaemon(
            queue=monitor.batch_queue,
            executor=monitor.batch_executor,
            process_monitor=monitor,
        )

        result = daemon.start(interval_seconds=args.interval, foreground=not args.background)

        if result["success"]:
            if args.background:
                print("✓ Daemon started in background")
                print(f"  PID: {result['pid']}")
                print(f"  Interval: {result['interval']}s")
                print(f"  Log file: {result['log_file']}")
            else:
                # Foreground mode - execution continues in daemon.start()
                pass
        else:
            print(f"✗ Failed to start daemon: {result['error']}")
            sys.exit(1)

    def cmd_batch_daemon_stop(args):
        """Stop the batch scheduler daemon."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import BatchDaemon

        daemon = BatchDaemon()
        result = daemon.stop()

        if result["success"]:
            print("✓ Daemon stopped")
            print(f"  PID: {result['pid']}")
            if result.get("forced"):
                print("  (force killed)")
        else:
            print(f"✗ {result['error']}")
            sys.exit(1)

    def cmd_batch_daemon_status(args):
        """Show daemon status."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import BatchDaemon

        daemon = BatchDaemon()
        status = daemon.status()

        if status["running"]:
            print("✓ Daemon is running")
            print(f"  PID: {status['pid']}")
            print(f"  Uptime: {status['uptime']}")
            print(f"  Started: {status['started_at']}")
            if "cpu_percent" in status:
                print(f"  CPU: {status['cpu_percent']:.1f}%")
            if "memory_mb" in status:
                print(f"  Memory: {status['memory_mb']:.1f} MB")
            print(f"  Log file: {status['log_file']}")
        else:
            print("✗ Daemon is not running")
            if "pid" in status:
                print(f"  (stale PID: {status['pid']})")

    # Process subcommands
    process_parser = subparsers.add_parser("process", help="Process monitoring and optimization")
    process_subparsers = process_parser.add_subparsers(
        dest="process_command", help="Process commands"
    )

    # process status
    process_status_parser = process_subparsers.add_parser(
        "status", help="Show current process status"
    )
    process_status_parser.set_defaults(func=cmd_process_status)

    # process waste
    process_waste_parser = process_subparsers.add_parser(
        "waste", help="Show detected resource waste"
    )
    process_waste_parser.set_defaults(func=cmd_process_waste)

    # process optimize
    process_optimize_parser = process_subparsers.add_parser(
        "optimize", help="Show optimization suggestions"
    )
    process_optimize_parser.set_defaults(func=cmd_process_optimize)

    # process insights
    process_insights_parser = process_subparsers.add_parser(
        "insights", help="Show utilization insights"
    )
    process_insights_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to analyze (default: 7)"
    )
    process_insights_parser.set_defaults(func=cmd_process_insights)

    # === Batch Scheduling Commands ===
    batch_parser = subparsers.add_parser("batch", help="Batch task scheduling and execution")
    batch_subparsers = batch_parser.add_subparsers(dest="batch_command", help="Batch commands")

    # batch add
    batch_add_parser = batch_subparsers.add_parser("add", help="Add a task to the batch queue")
    batch_add_parser.add_argument("command", help="Command to execute")
    batch_add_parser.add_argument(
        "--type",
        dest="task_type",
        default="general",
        help="Task type (test, build, deploy, etc.)",
    )
    batch_add_parser.add_argument("--description", default="", help="Task description")
    batch_add_parser.add_argument(
        "--priority",
        default="normal",
        choices=["immediate", "high", "normal", "low"],
        help="Task priority",
    )
    batch_add_parser.add_argument(
        "--duration", type=float, default=10.0, help="Estimated duration in minutes"
    )
    batch_add_parser.set_defaults(func=cmd_batch_add)

    # batch submit (NEW - unified submission)
    batch_submit_parser = batch_subparsers.add_parser(
        "submit", help="Submit job (auto-routes to correct backend)"
    )
    batch_submit_parser.add_argument("job_file", type=Path, help="Job definition JSON file")
    batch_submit_parser.set_defaults(func=cmd_batch_submit)

    # batch list
    batch_list_parser = batch_subparsers.add_parser("list", help="List batch tasks (both backends)")
    batch_list_parser.add_argument(
        "--backend",
        choices=["local", "api", "both"],
        default="both",
        help="Which backend to show (default: both)",
    )
    batch_list_parser.add_argument("--limit", type=int, default=20, help="Maximum tasks to show")
    batch_list_parser.set_defaults(func=cmd_batch_list)

    # batch status
    batch_status_parser = batch_subparsers.add_parser("status", help="Show batch queue status")
    batch_status_parser.set_defaults(func=cmd_batch_queue_status)

    # batch schedule
    batch_schedule_parser = batch_subparsers.add_parser("schedule", help="Schedule pending tasks")
    batch_schedule_parser.set_defaults(func=cmd_batch_schedule)

    # batch run
    batch_run_parser = batch_subparsers.add_parser("run", help="Execute scheduled tasks")
    batch_run_parser.set_defaults(func=cmd_batch_run)

    # batch cancel
    batch_cancel_parser = batch_subparsers.add_parser("cancel", help="Cancel a task")
    batch_cancel_parser.add_argument("task_id", help="Task ID to cancel")
    batch_cancel_parser.set_defaults(func=cmd_batch_cancel)

    # batch logs
    batch_logs_parser = batch_subparsers.add_parser("logs", help="Show task execution logs")
    batch_logs_parser.add_argument("task_id", help="Task ID")
    batch_logs_parser.set_defaults(func=cmd_batch_logs)

    # batch fill (intelligent overnight queue)
    batch_fill_parser = batch_subparsers.add_parser(
        "fill", help="Fill overnight batch queue intelligently"
    )
    batch_fill_parser.add_argument(
        "--max-jobs", type=int, default=None, help="Maximum jobs to queue"
    )
    batch_fill_parser.set_defaults(func=cmd_batch_fill)

    # batch daemon - nested subparser
    batch_daemon_parser = batch_subparsers.add_parser("daemon", help="Daemon management")
    daemon_subparsers = batch_daemon_parser.add_subparsers(
        dest="daemon_command", help="Daemon commands"
    )

    # daemon start
    daemon_start_parser = daemon_subparsers.add_parser(
        "start", help="Start the batch scheduler daemon"
    )
    daemon_start_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Task check interval in seconds (default: 60)",
    )
    daemon_start_parser.add_argument(
        "--background",
        action="store_true",
        help="Run in background (default: foreground)",
    )
    daemon_start_parser.set_defaults(func=cmd_batch_daemon_start)

    # daemon stop
    daemon_stop_parser = daemon_subparsers.add_parser(
        "stop", help="Stop the batch scheduler daemon"
    )
    daemon_stop_parser.set_defaults(func=cmd_batch_daemon_stop)

    # daemon status
    daemon_status_parser = daemon_subparsers.add_parser("status", help="Show daemon status")
    daemon_status_parser.set_defaults(func=cmd_batch_daemon_status)

    # batch stats
    def cmd_batch_stats(args):
        """Calculate real batch API savings from actual job data."""
        import json

        batch_results_dir = Path.home() / ".cortex" / "batch" / "results"
        if not batch_results_dir.exists():
            print("  No batch data yet. Run cortex batch fill first.")
            return

        # Conductor pricing per million tokens (input + output)
        INPUT_PRICING = {
            "claude-opus-4-20250514": 15.0,
            "claude-sonnet-4-20250514": 3.0,
            "claude-haiku-4-5-20251001": 0.25,
        }
        OUTPUT_PRICING = {
            "claude-opus-4-20250514": 75.0,
            "claude-sonnet-4-20250514": 15.0,
            "claude-haiku-4-5-20251001": 1.25,
        }
        BATCH_DISCOUNT = 0.50  # Anthropic batch = 50% of interactive

        total_interactive = 0.0
        total_batch = 0.0
        job_count = 0
        request_count = 0
        models_seen = {}

        for f in batch_results_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results = data.get("results", [])
                if not results:
                    continue

                job_counted = False
                for r in results:
                    msg = r.get("result", {}).get("message", {})
                    usage = msg.get("usage", {})
                    model = msg.get("model", "claude-sonnet-4-20250514")

                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)

                    if input_tokens == 0 and output_tokens == 0:
                        # Fallback to top-level tokens_used estimate
                        tokens_used = data.get("tokens_used", 0)
                        if tokens_used > 0:
                            input_tokens = int(tokens_used * 0.3)
                            output_tokens = int(tokens_used * 0.7)
                        else:
                            continue

                    in_price = INPUT_PRICING.get(model, 3.0)
                    out_price = OUTPUT_PRICING.get(model, 15.0)
                    interactive_cost = (input_tokens / 1_000_000) * in_price + (
                        output_tokens / 1_000_000
                    ) * out_price
                    batch_cost = interactive_cost * BATCH_DISCOUNT

                    total_interactive += interactive_cost
                    total_batch += batch_cost
                    request_count += 1

                    models_seen[model] = models_seen.get(model, 0) + 1
                    if not job_counted:
                        job_count += 1
                        job_counted = True
            except (json.JSONDecodeError, OSError):
                continue

        savings = total_interactive - total_batch
        pct = (savings / total_interactive * 100) if total_interactive > 0 else 0

        print("+" + "=" * 54 + "+")
        print("|          CORTEX - BATCH API SAVINGS REPORT           |")
        print("+" + "=" * 54 + "+")
        print("")
        print(f"  Jobs analyzed:      {job_count}")
        print(f"  Requests total:     {request_count}")
        print(f"  Interactive cost:   ${total_interactive:.4f}")
        print(f"  Batch cost:         ${total_batch:.4f}")
        print(f"  Savings:            ${savings:.4f} ({pct:.0f}%)")
        print(f"  Discount applied:   {BATCH_DISCOUNT * 100:.0f}% (Anthropic Batch API pricing)")
        print("")

        if models_seen:
            print("  Models used:")
            for model, count in sorted(models_seen.items(), key=lambda x: -x[1]):
                short = (
                    model.replace("claude-", "").replace("-20250514", "").replace("-20251001", "")
                )
                print(f"    {short:20} {count:>5} requests")
            print("")

        if job_count == 0:
            print("  No completed batch jobs with token data.")
            print("  The 50% savings is from Anthropic's published pricing:")
            print("  https://docs.anthropic.com/en/docs/build-with-claude/batch-processing")
            print("")

    batch_stats_parser = batch_subparsers.add_parser(
        "stats", help="Show batch API cost savings analysis"
    )
    batch_stats_parser.set_defaults(func=cmd_batch_stats)

    # === Work Absorber Commands ===
    def cmd_work_absorb(args):
        """Run work absorption cycle."""
        from datetime import datetime, timedelta

        from work_absorber import WorkAbsorber

        absorber = WorkAbsorber()

        # Parse since date if provided
        since = None
        if args.since:
            try:
                since = datetime.fromisoformat(args.since)
            except ValueError:
                # Try days ago format
                try:
                    days = int(args.since.rstrip("d"))
                    since = datetime.now() - timedelta(days=days)  # noqa: DTZ005
                except ValueError:
                    print(f"Invalid date format: {args.since}")
                    sys.exit(1)

        projects = [args.project] if args.project else None

        print("Starting work absorption...")
        report = absorber.absorb(
            projects=projects,
            since=since,
            incremental=not args.full,
        )

        print(f"\n✓ Absorption complete ({report.duration_seconds:.1f}s)")
        print(f"  Signals detected: {report.signals_detected}")
        print(f"  Signals absorbed: {report.signals_absorbed}")
        print(f"  Work items: {report.work_items_created} new, {report.work_items_updated} updated")
        print(f"  Plan correlations: {report.correlations_made}")
        print(f"  Drifts detected: {report.drifts_detected}")

        if report.by_project:
            print("\nBy project:")
            for project, stats in sorted(report.by_project.items()):
                print(
                    f"  {project}: {stats.get('signals', 0)} signals, {stats.get('work_items', 0)} items"
                )

        if report.errors:
            print(f"\n⚠ Errors ({len(report.errors)}):")
            for error in report.errors[:5]:
                print(f"  - {error}")

    def cmd_work_status(args):
        """Show work absorber status."""
        from work_absorber import WorkAbsorber

        absorber = WorkAbsorber()
        status = absorber.get_status()

        print("╔══════════════════════════════════════════════════════╗")
        print("║            WORK ABSORBER - STATUS                    ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()

        storage = status.get("storage", {})
        print(f"Total signals: {storage.get('total_signals', 0)}")
        print(f"Total work items: {storage.get('total_work_items', 0)}")
        print(f"Unresolved drifts: {storage.get('unresolved_drifts', 0)}")

        last = status.get("last_absorption")
        if last:
            print(f"\nLast absorption: {last.get('time', 'Unknown')}")
            print(f"  Signals: {last.get('signals', 0)}")
            print(f"  Work items: {last.get('items', 0)}")
            print(f"  Drifts: {last.get('drifts', 0)}")
        else:
            print("\nNo absorption run yet")

        by_project = storage.get("by_project", {})
        if by_project:
            print("\nBy project:")
            for project, count in sorted(by_project.items(), key=lambda x: -x[1]):
                print(f"  {project}: {count} work items")

    def cmd_work_items(args):
        """List work items."""
        from work_absorber import WorkAbsorber, WorkStatus

        absorber = WorkAbsorber()

        if args.status == "orphaned":
            items = absorber.get_unplanned_work()
        else:
            items = absorber.get_recent_work(days=args.days, project=args.project)
            if args.status:
                status = WorkStatus(args.status)
                items = [i for i in items if i.status == status]

        if not items:
            print("No work items found")
            return

        print(f"Work items ({len(items)}):\n")

        for item in items[: args.limit]:
            icon = "✓" if item.status.value == "correlated" else "○"
            print(f"{icon} [{item.project}] {item.title}")
            print(
                f"  Status: {item.status.value} | Signals: {item.signal_count} | Files: {len(item.files_touched)}"
            )
            if item.plan_step_id:
                print(f"  Plan: {item.plan_step_id} ({item.correlation_confidence:.0%} confidence)")
            if item.scope:
                print(f"  Scope: {item.scope}")
            print(
                f"  Time: {item.first_seen.strftime('%Y-%m-%d %H:%M')} - {item.last_activity.strftime('%Y-%m-%d %H:%M')}"
            )
            print()

    def cmd_work_drift(args):
        """Show or resolve plan drift."""
        from work_absorber import WorkAbsorber

        absorber = WorkAbsorber()

        if args.resolve:
            notes = args.notes or ""
            absorber.storage.resolve_drift(args.resolve, notes)
            print(f"✓ Drift {args.resolve} resolved")
            return

        summary = absorber.get_drift_summary(project=args.project)

        if summary["total"] == 0:
            print("No unresolved drifts detected")
            return

        print(f"Plan Drift ({summary['total']} unresolved):\n")

        # By type
        by_type = summary["by_type"]
        if by_type:
            print("By type:")
            for drift_type, count in sorted(by_type.items()):
                print(f"  {drift_type}: {count}")
            print()

        # By severity
        by_severity = summary["by_severity"]
        if by_severity:
            print("By severity:")
            for severity, count in sorted(by_severity.items()):
                print(f"  {severity}: {count}")
            print()

        # Show drifts
        print("Drifts:")
        for drift in summary["drifts"]:
            severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                drift.severity, "○"
            )
            print(f"\n{severity_icon} [{drift.drift_type.value}] {drift.description}")
            print(f"  Project: {drift.project} | ID: {drift.id}")
            print(f"  Suggested: {drift.suggested_action}")

    def cmd_work_report(args):
        """Generate work absorption report."""
        from datetime import datetime, timedelta

        from work_absorber import WorkAbsorber

        absorber = WorkAbsorber()
        datetime.now() - timedelta(days=args.days)  # noqa: DTZ005

        items = absorber.get_recent_work(days=args.days)
        drifts = absorber.storage.get_unresolved_drifts()

        print("╔══════════════════════════════════════════════════════╗")
        print(f"║      WORK ABSORPTION REPORT ({args.days} days)              ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()

        # Summary
        print(f"Work items: {len(items)}")
        correlated = sum(1 for i in items if i.plan_step_id)
        orphaned = sum(1 for i in items if not i.plan_step_id)
        print(f"  Correlated to plans: {correlated}")
        print(f"  Unplanned work: {orphaned}")

        print(f"\nDrifts: {len(drifts)} unresolved")
        print()

        # By project
        by_project = {}
        for item in items:
            by_project.setdefault(item.project, []).append(item)

        print("By project:")
        for project in sorted(by_project.keys()):
            project_items = by_project[project]
            print(f"\n  {project}: {len(project_items)} work items")
            for item in project_items[:5]:
                status = "✓" if item.plan_step_id else "○"
                print(f"    {status} {item.title[:50]}")

        # Recent highlights
        if items:
            print("\nRecent highlights:")
            for item in items[:5]:
                print(f"  - {item.title} ({item.project})")

    # Work absorber subparsers
    work_parser = subparsers.add_parser(
        "work", help="Work absorber - track progress across projects"
    )
    work_subparsers = work_parser.add_subparsers(dest="work_command", help="Work commands")

    # work absorb
    work_absorb_parser = work_subparsers.add_parser("absorb", help="Run absorption cycle")
    work_absorb_parser.add_argument("--project", "-p", help="Specific project to absorb")
    work_absorb_parser.add_argument(
        "--since", "-s", help="Start date (YYYY-MM-DD or Nd for N days ago)"
    )
    work_absorb_parser.add_argument(
        "--full", action="store_true", help="Full rescan (ignore checkpoints)"
    )
    work_absorb_parser.set_defaults(func=cmd_work_absorb)

    # work status
    work_status_parser = work_subparsers.add_parser("status", help="Show absorber status")
    work_status_parser.set_defaults(func=cmd_work_status)

    # work items
    work_items_parser = work_subparsers.add_parser("items", help="List work items")
    work_items_parser.add_argument("--project", "-p", help="Filter by project")
    work_items_parser.add_argument(
        "--status",
        "-s",
        choices=["detected", "absorbed", "correlated", "orphaned"],
        help="Filter by status",
    )
    work_items_parser.add_argument(
        "--days", "-d", type=int, default=7, help="Days to look back (default: 7)"
    )
    work_items_parser.add_argument(
        "--limit", "-l", type=int, default=20, help="Max items to show (default: 20)"
    )
    work_items_parser.set_defaults(func=cmd_work_items)

    # work drift
    work_drift_parser = work_subparsers.add_parser("drift", help="Show plan drift")
    work_drift_parser.add_argument("--project", "-p", help="Filter by project")
    work_drift_parser.add_argument("--resolve", "-r", help="Resolve drift by ID")
    work_drift_parser.add_argument("--notes", "-n", help="Resolution notes")
    work_drift_parser.set_defaults(func=cmd_work_drift)

    # work report
    work_report_parser = work_subparsers.add_parser("report", help="Generate absorption report")
    work_report_parser.add_argument(
        "--days", "-d", type=int, default=7, help="Days to include (default: 7)"
    )
    work_report_parser.set_defaults(func=cmd_work_report)

    # === V2 Prime Commands ===

    def cmd_v2_status(args):
        """Show V2 Prime system status."""
        from bridge import CortexBridge

        bridge = CortexBridge()
        status = bridge.get_v2_status()

        print("+" + "=" * 54 + "+")
        print("|          CORTEX V2 PRIME - SYSTEM STATUS             |")
        print("+" + "=" * 54 + "+")
        print()

        # Engine status
        print("3-ENGINE ACTIVE MODEL")
        print("-" * 30)
        engines = [
            ("Engine A: Absorber", status.get("absorber", False), "Signal ingestion"),
            ("Engine B: Synthesis", status.get("synthesis", False), "Graph processing"),
            ("Engine C: Broker", status.get("broker", False), "Interventions"),
            ("IAP Handler", status.get("iap", False), "Agent protocol"),
        ]
        for name, active, desc in engines:
            icon = "[OK]" if active else "[--]"
            print(f"  {icon} {name}: {desc}")
        print()

        # Graph stats
        graph_stats = status.get("graph_stats")
        if graph_stats and "error" not in graph_stats:
            print("CONTEXT GRAPH")
            print("-" * 30)
            print(f"  Nodes: {graph_stats.get('total_nodes', 0)}")
            print(f"  Edges: {graph_stats.get('total_edges', 0)}")
            if graph_stats.get("nodes_by_type"):
                print("  By type:")
                for ntype, count in graph_stats["nodes_by_type"].items():
                    print(f"    {ntype}: {count}")
            print()

        # Broker stats
        broker_status = status.get("broker_status")
        if broker_status and "error" not in broker_status:
            print("ACTION BROKER")
            print("-" * 30)
            print(f"  Total interventions: {broker_status.get('total_interventions', 0)}")
            print(f"  Pending: {broker_status.get('pending_count', 0)}")
            by_sev = broker_status.get("by_severity", {})
            if any(by_sev.values()):
                print("  By severity:")
                for sev in ["critical", "high", "medium", "low", "info"]:
                    if by_sev.get(sev, 0) > 0:
                        print(f"    {sev}: {by_sev[sev]}")
            print()

        v2_status = (
            "[OK] V2 Prime Operational"
            if status.get("v2_available")
            else "[--] V2 Prime Unavailable"
        )
        print(f"{v2_status}")

    def cmd_graph_query(args):
        """Query the context graph."""
        import json

        from bridge import CortexBridge

        bridge = CortexBridge()

        if args.node_type:
            result = bridge.query_graph(args.node_type)
        else:
            result = bridge.get_graph_stats()

        print(json.dumps(result, indent=2, default=str))

    def cmd_graph_add(args):
        """Add a node to the graph."""
        import json

        from bridge import CortexBridge

        bridge = CortexBridge()

        data = {}
        if args.data:
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError:
                data = {"description": args.data}

        result = bridge.add_graph_node(args.node_type, args.name, data)
        if result.get("success"):
            print(f"[OK] Node added: {result['node_id']}")
        else:
            print(f"[FAIL] {result.get('error')}")

    def cmd_graph_related(args):
        """Get related nodes."""
        import json

        from bridge import CortexBridge

        bridge = CortexBridge()

        result = bridge.get_related_nodes(args.node_id, args.edge_type)
        print(json.dumps(result, indent=2, default=str))

    def cmd_graph_import(args):
        """Import portfolio data into graph."""
        from pathlib import Path

        from bridge import CortexBridge

        bridge = CortexBridge()

        if not bridge.synthesis:
            print("[FAIL] V2 Prime Synthesis Core not available")
            return

        portfolio_path = Path.home() / ".claude" / "portfolio"
        print(f"Importing from {portfolio_path}...")

        result = bridge.synthesis.import_portfolio_data(portfolio_path)

        print()
        print("Import complete:")
        for category, count in result.items():
            print(f"  {category}: {count}")

        # Show updated stats
        stats = bridge.get_graph_stats()
        print()
        print(
            f"Graph now has {stats.get('total_nodes', 0)} nodes and {stats.get('total_edges', 0)} edges"
        )

    def cmd_interventions_list(args):
        """List pending interventions."""
        from bridge import CortexBridge

        bridge = CortexBridge()

        interventions = bridge.get_pending_interventions()

        if not interventions or (len(interventions) == 1 and "error" in interventions[0]):
            print("No pending interventions")
            return

        print(f"Pending Interventions ({len(interventions)}):")
        print()

        for i in interventions:
            sev_icon = {
                "critical": "[!]",
                "high": "[*]",
                "medium": "[+]",
                "low": "[-]",
                "info": "[i]",
            }.get(i.get("severity", "info"), "[?]")

            print(f"{sev_icon} {i.get('title', 'Unknown')}")
            print(f"    Type: {i.get('type')}")
            print(f"    ID: {i.get('id')}")
            if i.get("description"):
                desc = (
                    i["description"][:80] + "..."
                    if len(i.get("description", "")) > 80
                    else i.get("description", "")
                )
                print(f"    {desc}")
            print()

    def cmd_interventions_ack(args):
        """Acknowledge an intervention."""
        from bridge import CortexBridge

        bridge = CortexBridge()

        result = bridge.acknowledge_intervention(args.id)
        if result.get("success"):
            print(f"[OK] Intervention {args.id} acknowledged")
        else:
            print(f"[FAIL] {result.get('error')}")

    def cmd_interventions_suppress(args):
        """Suppress an intervention."""
        from bridge import CortexBridge

        bridge = CortexBridge()

        result = bridge.suppress_intervention(args.id, args.hours)
        if result.get("success"):
            print(f"[OK] Intervention {args.id} suppressed for {args.hours} hours")
        else:
            print(f"[FAIL] {result.get('error')}")

    def cmd_iap_send(args):
        """Send an IAP message."""
        import json

        from bridge import CortexBridge

        bridge = CortexBridge()

        message = {
            "message_type": args.type,
            "payload": {
                "query": args.payload,
                "query_type": args.query_type or "context",
            },
        }

        result = bridge.handle_iap_message(message)
        print(json.dumps(result, indent=2, default=str))

    # --- Runtime command handlers ---
    def cmd_runtime_start(args):
        """Start the runtime daemon."""
        try:
            from cortex.runtime import RuntimeExecutor
            from cortex.runtime.config import get_config

            config = get_config()
            print(f"Starting Cortex Runtime on {config.host}:{config.port}...")

            executor = RuntimeExecutor(config)
            executor.start()
        except ImportError as e:
            print(f"Error: Runtime module not available: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error starting runtime: {e}", file=sys.stderr)
            sys.exit(1)

    def cmd_runtime_status(args):
        """Show runtime status."""
        import json as json_mod

        try:
            import urllib.error
            import urllib.request

            from cortex.runtime.config import get_config

            config = get_config()
            url = f"http://{config.host}:{config.port}/api/v1/runtime/health"

            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json_mod.loads(response.read().decode())
                    print("╔══════════════════════════════════════════════════════╗")
                    print("║              CORTEX RUNTIME STATUS                   ║")
                    print("╚══════════════════════════════════════════════════════╝")
                    print(f"Status: {data.get('status', 'unknown')}")
                    print(f"Uptime: {data.get('uptime_seconds', 0):.0f}s")
                    print(f"Agents: {data.get('registered_agents', 0)}")
                    if args.json:
                        print(json_mod.dumps(data, indent=2))
            except urllib.error.URLError:
                print("Runtime is not running.")
                print("Start with: cortex runtime start")
                sys.exit(1)
        except ImportError as e:
            print(f"Error: Runtime module not available: {e}", file=sys.stderr)
            sys.exit(1)

    def cmd_runtime_agents(args):
        """List registered agents."""
        import json as json_mod

        try:
            import urllib.error
            import urllib.request

            from cortex.runtime.config import get_config

            config = get_config()
            url = f"http://{config.host}:{config.port}/api/v1/runtime/agents"

            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json_mod.loads(response.read().decode())
                    agents = data.get("agents", [])

                    if args.json:
                        print(json_mod.dumps(data, indent=2))
                        return

                    print("Registered Agents:")
                    print("─" * 60)
                    if not agents:
                        print("  No agents registered")
                    else:
                        for agent in agents:
                            status_icon = "●" if agent.get("status") == "idle" else "○"
                            schedule = agent.get("schedule", "manual")
                            print(
                                f"  {status_icon} {agent['agent_id']}: {agent.get('name', 'Unnamed')}"
                            )
                            print(f"      Schedule: {schedule}")
            except urllib.error.URLError:
                print("Runtime is not running.")
                sys.exit(1)
        except ImportError as e:
            print(f"Error: Runtime module not available: {e}", file=sys.stderr)
            sys.exit(1)

    def cmd_runtime_trigger(args):
        """Manually trigger an agent."""
        import json as json_mod

        try:
            import urllib.error
            import urllib.request

            from cortex.runtime.config import get_config

            config = get_config()
            url = (
                f"http://{config.host}:{config.port}/api/v1/runtime/agents/{args.agent_id}/trigger"
            )

            req = urllib.request.Request(url, method="POST", data=b"{}")
            req.add_header("Content-Type", "application/json")

            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json_mod.loads(response.read().decode())
                    print(f"Triggered agent: {args.agent_id}")
                    if data.get("success"):
                        print("Result: Success")
                        if data.get("result"):
                            print(f"Output: {json_mod.dumps(data['result'], indent=2)}")
                    else:
                        print(f"Result: Failed - {data.get('error', 'Unknown error')}")
            except urllib.error.HTTPError as e:
                print(f"Error triggering agent: {e.code} {e.reason}")
                sys.exit(1)
            except urllib.error.URLError:
                print("Runtime is not running.")
                sys.exit(1)
        except ImportError as e:
            print(f"Error: Runtime module not available: {e}", file=sys.stderr)
            sys.exit(1)

    def cmd_runtime_history(args):
        """Show execution history."""
        import json as json_mod

        try:
            import urllib.error
            import urllib.request

            from cortex.runtime.config import get_config

            config = get_config()
            limit = args.limit if hasattr(args, "limit") else 20
            url = f"http://{config.host}:{config.port}/api/v1/runtime/history?limit={limit}"

            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json_mod.loads(response.read().decode())
                    executions = data.get("executions", [])

                    if args.json:
                        print(json_mod.dumps(data, indent=2))
                        return

                    print("Execution History:")
                    print("─" * 70)
                    if not executions:
                        print("  No execution history")
                    else:
                        for exec_item in executions:
                            status = "✓" if exec_item.get("success") else "✗"
                            agent_id = exec_item.get("agent_id", "unknown")
                            start_time = exec_item.get("start_time", "")[
                                :19
                            ]  # Truncate to datetime
                            duration = exec_item.get("duration_seconds", 0)
                            print(f"  {status} [{start_time}] {agent_id} ({duration:.1f}s)")
            except urllib.error.URLError:
                # Try direct database access if runtime not running
                print("Runtime not running. Querying history database directly...")
                try:
                    from cortex.runtime.storage.history import ExecutionHistory

                    history = ExecutionHistory()
                    executions = history.get_recent_executions(limit=limit)

                    print("─" * 70)
                    for exec_item in executions:
                        status = "✓" if exec_item.get("success") else "✗"
                        agent_id = exec_item.get("agent_id", "unknown")
                        start_time = exec_item.get("start_time", "")[:19]
                        duration = exec_item.get("duration_seconds", 0)
                        print(f"  {status} [{start_time}] {agent_id} ({duration:.1f}s)")
                except Exception as db_err:
                    print(f"Could not access history: {db_err}")
                    sys.exit(1)
        except ImportError as e:
            print(f"Error: Runtime module not available: {e}", file=sys.stderr)
            sys.exit(1)

    # V2 Prime subparser
    v2_parser = subparsers.add_parser("v2", help="V2 Prime system commands")
    v2_subparsers = v2_parser.add_subparsers(dest="v2_command", help="V2 commands")

    # v2 status
    v2_status_parser = v2_subparsers.add_parser("status", help="Show V2 Prime system status")
    v2_status_parser.set_defaults(func=cmd_v2_status)

    # Graph subparser
    graph_parser = subparsers.add_parser("graph", help="Context graph operations")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", help="Graph commands")

    # graph query
    graph_query_parser = graph_subparsers.add_parser("query", help="Query the context graph")
    graph_query_parser.add_argument(
        "--type",
        "-t",
        dest="node_type",
        help="Node type to query (project, pattern, lesson, goal)",
    )
    graph_query_parser.set_defaults(func=cmd_graph_query)

    # graph add
    graph_add_parser = graph_subparsers.add_parser("add", help="Add a node to the graph")
    graph_add_parser.add_argument("node_type", help="Node type (project, pattern, lesson, goal)")
    graph_add_parser.add_argument("name", help="Node name")
    graph_add_parser.add_argument("--data", "-d", help="Node data as JSON string")
    graph_add_parser.set_defaults(func=cmd_graph_add)

    # graph related
    graph_related_parser = graph_subparsers.add_parser("related", help="Get related nodes")
    graph_related_parser.add_argument("node_id", help="Node ID to find relations for")
    graph_related_parser.add_argument(
        "--edge-type", "-e", dest="edge_type", help="Edge type filter"
    )
    graph_related_parser.set_defaults(func=cmd_graph_related)

    # graph import
    graph_import_parser = graph_subparsers.add_parser(
        "import", help="Import portfolio data into graph"
    )
    graph_import_parser.set_defaults(func=cmd_graph_import)

    # Interventions subparser
    int_parser = subparsers.add_parser("interventions", help="Intervention management")
    int_subparsers = int_parser.add_subparsers(dest="int_command", help="Intervention commands")

    # interventions list
    int_list_parser = int_subparsers.add_parser("list", help="List pending interventions")
    int_list_parser.set_defaults(func=cmd_interventions_list)

    # interventions ack
    int_ack_parser = int_subparsers.add_parser("ack", help="Acknowledge an intervention")
    int_ack_parser.add_argument("id", help="Intervention ID")
    int_ack_parser.set_defaults(func=cmd_interventions_ack)

    # interventions suppress
    int_suppress_parser = int_subparsers.add_parser("suppress", help="Suppress an intervention")
    int_suppress_parser.add_argument("id", help="Intervention ID")
    int_suppress_parser.add_argument(
        "--hours", type=int, default=24, help="Hours to suppress (default: 24)"
    )
    int_suppress_parser.set_defaults(func=cmd_interventions_suppress)

    # IAP subparser
    iap_parser = subparsers.add_parser("iap", help="Inter-Agent Protocol commands")
    iap_subparsers = iap_parser.add_subparsers(dest="iap_command", help="IAP commands")

    # iap send
    iap_send_parser = iap_subparsers.add_parser("send", help="Send an IAP message")
    iap_send_parser.add_argument("type", choices=["query", "handoff", "ack"], help="Message type")
    iap_send_parser.add_argument("payload", help="Message payload")
    iap_send_parser.add_argument(
        "--query-type", "-q", dest="query_type", help="Query type for query messages"
    )
    iap_send_parser.set_defaults(func=cmd_iap_send)

    # Runtime subparser
    runtime_parser = subparsers.add_parser("runtime", help="Runtime executor management")
    runtime_subparsers = runtime_parser.add_subparsers(
        dest="runtime_command", help="Runtime commands"
    )

    # runtime start
    runtime_start_parser = runtime_subparsers.add_parser("start", help="Start the runtime daemon")
    runtime_start_parser.set_defaults(func=cmd_runtime_start)

    # runtime status
    runtime_status_parser = runtime_subparsers.add_parser("status", help="Show runtime status")
    runtime_status_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    runtime_status_parser.set_defaults(func=cmd_runtime_status)

    # runtime agents
    runtime_agents_parser = runtime_subparsers.add_parser("agents", help="List registered agents")
    runtime_agents_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    runtime_agents_parser.set_defaults(func=cmd_runtime_agents)

    # runtime trigger
    runtime_trigger_parser = runtime_subparsers.add_parser(
        "trigger", help="Manually trigger an agent"
    )
    runtime_trigger_parser.add_argument("agent_id", help="Agent ID to trigger")
    runtime_trigger_parser.set_defaults(func=cmd_runtime_trigger)

    # runtime history
    runtime_history_parser = runtime_subparsers.add_parser("history", help="Show execution history")
    runtime_history_parser.add_argument(
        "--limit", "-n", type=int, default=20, help="Number of entries to show"
    )
    runtime_history_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    runtime_history_parser.set_defaults(func=cmd_runtime_history)

    # === Intelligence command ===
    intelligence_parser = subparsers.add_parser(
        "intelligence", help="Query Cortex intelligence for context and patterns"
    )
    intelligence_parser.add_argument("query", help="Natural language query")
    intelligence_parser.add_argument(
        "--project", "-p", type=str, default=None, help="Filter by project name"
    )
    intelligence_parser.add_argument(
        "--type",
        "-t",
        type=str,
        default="spec",
        choices=["spec", "impl", "analysis", "research"],
        help="Query type (default: spec)",
    )
    intelligence_parser.set_defaults(func=cmd_intelligence)

    # === Portfolio command ===
    portfolio_parser = subparsers.add_parser(
        "portfolio", help="Cross-project patterns and switching cost analysis"
    )
    portfolio_parser.add_argument(
        "action",
        nargs="?",
        choices=["patterns"],
        default="patterns",
        help="Action to perform (default: patterns)",
    )
    portfolio_parser.add_argument(
        "--propagate",
        action="store_true",
        help="Show which projects are missing patterns",
    )
    portfolio_parser.add_argument(
        "--switching-cost",
        action="store_true",
        help="Show context-switching cost analysis",
    )
    portfolio_parser.set_defaults(func=cmd_portfolio)

    # === Deps command ===
    deps_parser = subparsers.add_parser("deps", help="Dependency analysis for projects")
    deps_parser.add_argument("project", nargs="?", default=None, help="Project name (optional)")
    deps_parser.add_argument(
        "--cross-project",
        action="store_true",
        help="Show shared dependencies across all projects",
    )
    deps_parser.set_defaults(func=cmd_deps)

    # === Watch command ===
    watch_parser = subparsers.add_parser("watch", help="Scheduled verification tasks")
    watch_parser.add_argument("--run", action="store_true", help="Run pending watches now")
    watch_parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Preview what autonomous mode would do (dry-run)",
    )
    watch_parser.set_defaults(func=cmd_watch)

    # === Sessions command ===
    def cmd_sessions(args):
        """Show Claude Code sessions."""
        from bridge import CortexBridge

        bridge = CortexBridge()
        active_only = getattr(args, "active", False)

        try:
            result = bridge._get(f"/sessions?active_only={'true' if active_only else 'false'}")
        except Exception:
            print("Bridge unavailable. Start with: python api/bridge_endpoint.py")
            sys.exit(1)

        sessions = result.get("sessions", [])
        active = result.get("active_count", 0)
        total = result.get("total", 0)

        print("+" + "=" * 54 + "+")
        print("|          CORTEX - SESSION MONITOR                     |")
        print("+" + "=" * 54 + "+")
        print("")
        print(f"  Sessions: {active} active / {total} total")
        print("")

        for s in sessions[:10]:
            state = s.get("state", "unknown").upper()
            project = s.get("project", "unknown")
            age = s.get("age_display", "?")
            sid = s.get("session_id", "?")[:12]

            icon = "*" if state == "ACTIVE" else "o" if state == "IDLE" else "."
            print(f"  {icon} [{state:7}] {project:30} {age:>10}  {sid}")

        if not sessions:
            print("  No sessions found.")
        print("")

    sessions_parser = subparsers.add_parser("sessions", help="Show Claude Code sessions")
    sessions_parser.add_argument("--active", action="store_true", help="Show only active sessions")
    sessions_parser.set_defaults(func=cmd_sessions)

    # === Signals command ===
    def cmd_signals(args):
        """Run active cross-project signal detection."""
        try:
            from intelligence.signals import SignalDetector
        except ImportError:
            print("Error: Signal detection not available", file=sys.stderr)
            sys.exit(1)

        severity_filter = getattr(args, "severity", None)

        try:
            detector = SignalDetector(root_dir=args.root)
            signals = detector.detect_all()

            print("+" + "=" * 54 + "+")
            print("|      CORTEX - CROSS-PROJECT SIGNAL DETECTION          |")
            print("+" + "=" * 54 + "+")
            print("")

            if not signals:
                print("  No signals detected. All clear.")
                print("")
                return

            by_severity = {}
            for s in signals:
                by_severity.setdefault(s.severity, []).append(s)

            for sev in ["critical", "high", "medium", "low"]:
                if severity_filter and sev != severity_filter:
                    continue
                items = by_severity.get(sev, [])
                if not items:
                    continue
                print(f"  [{sev.upper()}] ({len(items)} signals)")
                for s in items[:5]:
                    print(f"    {s.type.value}: {s.title}")
                    if s.evidence:
                        print(f"      Evidence: {s.evidence[0]}")
                print("")

            displayed = sum(
                len(by_severity.get(sev, []))
                for sev in ["critical", "high", "medium", "low"]
                if not severity_filter or sev == severity_filter
            )
            print(f"  Total: {displayed} signals across {len(by_severity)} severity levels")
            print("")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    signals_parser = subparsers.add_parser(
        "signals", help="Run active cross-project signal detection"
    )
    signals_parser.add_argument(
        "--severity",
        choices=["critical", "high", "medium", "low"],
        default=None,
        help="Filter by severity level",
    )
    signals_parser.set_defaults(func=cmd_signals)

    # === Doctor command ===
    def cmd_doctor(args):
        """Run environment health checks."""
        import socket

        checks = []

        # Python version >= 3.11
        vi = sys.version_info
        py_ok = (vi.major, vi.minor) >= (3, 11)
        checks.append(("Python >= 3.11", py_ok, f"{vi.major}.{vi.minor}.{vi.micro}"))

        # anthropic importable
        try:
            import anthropic as _a

            checks.append(("anthropic importable", True, _a.__version__))
        except ImportError as e:
            checks.append(("anthropic importable", False, str(e)))

        # sklearn importable
        try:
            import sklearn as _sk

            checks.append(("sklearn importable", True, _sk.__version__))
        except ImportError as e:
            checks.append(("sklearn importable", False, str(e)))

        # ANTHROPIC_API_KEY set
        key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
        checks.append(("ANTHROPIC_API_KEY set", key_set, "set" if key_set else "missing"))

        # ~/.cortex/ exists
        cortex_home = Path.home() / ".cortex"
        checks.append(("~/.cortex/ exists", cortex_home.exists(), str(cortex_home)))

        # Bridge server at :8765
        bridge_ok = False
        try:
            s = socket.create_connection(("127.0.0.1", 8765), timeout=1)
            s.close()
            bridge_ok = True
        except OSError:
            pass
        checks.append(("bridge :8765 reachable", bridge_ok, "up" if bridge_ok else "not running"))

        all_pass = all(ok for _, ok, _ in checks)
        width = 44
        print("+" + "=" * width + "+")
        print("|  CORTEX DOCTOR" + " " * (width - 15) + "|")
        print("+" + "=" * width + "+")
        for label, ok, detail in checks:
            status = "PASS" if ok else "FAIL"
            row = f"  [{status}] {label}: {detail}"
            print(row)
        print("+" + "=" * width + "+")
        if all_pass:
            print("  All checks passed.")
        else:
            print("  Some checks FAILED. Fix issues above.")
        sys.exit(0 if all_pass else 1)

    doctor_parser = subparsers.add_parser("doctor", help="Run environment health checks")
    doctor_parser.set_defaults(func=cmd_doctor)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
