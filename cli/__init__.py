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
_py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
site_packages = Path.home() / f"Library/Python/{_py_ver}/lib/python/site-packages"
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
    cmd_onboard,
)

# V2 Ops — inline functions extracted to keep main() slim
from cli.commands.v2_ops import (
    cmd_check,
    cmd_draft,
    cmd_sessions,
    cmd_signals,
    cmd_doctor,
    register_process_cmds,
    register_batch_local_cmds,
    register_work_cmds,
    register_v2_cmds,
    register_runtime_cmds,
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


# Tier-4 commands hidden from the default surface (2026-07 usage assessment:
# stub, stale-store, or external-dependency commands). Set CORTEX_EXPERIMENTAL=1
# to register them; the code paths are untouched.
EXPERIMENTAL_COMMANDS = {
    "quick",  # self-labeled "not yet fully implemented"
    "bandwidth",  # A/B experiment suite; store idle since 2026-03
    "tooling",  # tooling_changes.jsonl idle since 2026-02
    "docs",  # shells out to external _tools/doc-sync (may not exist)
    "batch-api-status",  # prints config flags only
    "sessions",  # requires the :8765 bridge; claude_sessions store stale
    "runtime",  # needs the separate runtime HTTP executor
}


def _hide_experimental(subparsers) -> None:
    """Deregister experimental commands so help and dispatch don't see them.

    Post-registration removal keeps a single seam (this function + the set
    above) instead of scattering env checks across every add_parser block.
    """
    for name in EXPERIMENTAL_COMMANDS:
        subparsers._name_parser_map.pop(name, None)  # noqa: SLF001
        subparsers.choices.pop(name, None)
    subparsers._choices_actions = [  # noqa: SLF001
        a for a in subparsers._choices_actions if a.dest not in EXPERIMENTAL_COMMANDS
    ]


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

    # Compact dashboard flags (used when no subcommand is given)
    parser.add_argument("--alerts", action="store_true", help="Show alert detail")
    parser.add_argument("--goals", action="store_true", help="Show goal progress")
    parser.add_argument("--batch", action="store_true", help="Show batch health")
    parser.add_argument("--git-detail", action="store_true", help="Show git detail")
    parser.add_argument("--full", action="store_true", help="Full briefing (legacy)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ── next ──────────────────────────────────────────────────────────────────
    next_parser = subparsers.add_parser("next", help="Get next action")
    next_parser.add_argument("project", nargs="?", help="Filter by project name (optional)")
    next_parser.add_argument(
        "--with-context", action="store_true", help="Include context predictions"
    )
    next_parser.add_argument("--json", action="store_true", help="Output JSON format")
    next_parser.add_argument(
        "--limit", type=int, default=3, help="Number of alternative actions to show (default: 3)"
    )
    next_parser.set_defaults(func=cmd_next)

    # ── init ──────────────────────────────────────────────────────────────────
    init_parser = subparsers.add_parser(
        "init", help="Initialize Cortex configuration and directories"
    )
    init_parser.add_argument(
        "--root-dir", type=str, default="", help="Set workspace root directory in config"
    )
    init_parser.set_defaults(func=cmd_init)

    # ── onboard ──────────────────────────────────────────────────────────────
    onboard_parser = subparsers.add_parser(
        "onboard", help="Auto-detect projects and seed memory for immediate value"
    )
    onboard_parser.add_argument(
        "--root", type=str, default="", help="Project root directory to scan"
    )
    onboard_parser.add_argument(
        "--non-interactive", action="store_true", help="Skip interactive questions"
    )
    onboard_parser.set_defaults(func=cmd_onboard)

    # ── status ────────────────────────────────────────────────────────────────
    subparsers.add_parser("status", help="Show current state").set_defaults(func=cmd_status)

    # ── health ────────────────────────────────────────────────────────────────
    health_parser = subparsers.add_parser("health", help="Show system health check")
    health_parser.add_argument(
        "--providers", action="store_true", help="Show AI provider status and pricing"
    )
    health_parser.set_defaults(func=cmd_health)

    # ── feedback ──────────────────────────────────────────────────────────────
    feedback_parser = subparsers.add_parser("feedback", help="Log feedback for recommendations")
    feedback_parser.add_argument("--action-title", type=str)
    feedback_parser.add_argument("--action-id", type=str)
    feedback_parser.add_argument("--useful", type=str, required=False)
    feedback_parser.add_argument("--notes", type=str)
    feedback_parser.add_argument("--outcome", type=str)
    feedback_parser.add_argument("--stats", type=str, nargs="?", const="summary")
    feedback_parser.add_argument("--log", type=str)
    feedback_parser.set_defaults(func=cmd_feedback)

    # ── notify ────────────────────────────────────────────────────────────────
    notify_parser = subparsers.add_parser("notify", help="Send notifications")
    notify_parser.add_argument("--type", choices=["morning", "evening", "custom"], default="custom")
    notify_parser.add_argument("--channel", action="append", choices=["terminal", "email", "all"])
    notify_parser.add_argument("--message", type=str)
    notify_parser.add_argument("--title", type=str)
    notify_parser.set_defaults(func=cmd_notify)

    # ── check ─────────────────────────────────────────────────────────────────
    check_parser = subparsers.add_parser("check", help="Check project compliance with Golden Spec")
    check_parser.add_argument("project", nargs="?")
    check_parser.set_defaults(func=cmd_check)

    # ── draft ─────────────────────────────────────────────────────────────────
    draft_parser = subparsers.add_parser("draft", help="Draft a new Golden Spec from intent")
    draft_parser.add_argument("intent", help="The intent or goal of the project")
    draft_parser.add_argument("--project")
    draft_parser.set_defaults(func=cmd_draft)

    # ── learn ─────────────────────────────────────────────────────────────────
    learn_parser = subparsers.add_parser("learn", help="Show learning metrics and patterns")
    learn_parser.add_argument("--pipeline", action="store_true")
    learn_parser.set_defaults(func=cmd_learn)

    # ── deep / quick / auto / config ─────────────────────────────────────────
    deep_parser = subparsers.add_parser("deep", help="Run comprehensive deep analysis (2-5s)")
    deep_parser.add_argument("project", nargs="?")
    deep_parser.add_argument("--verbose", "-v", action="store_true")
    deep_parser.add_argument("--json", "-j", action="store_true")
    deep_parser.set_defaults(func=cmd_deep)

    quick_parser = subparsers.add_parser("quick", help="Run minimal fast analysis (<1s)")
    quick_parser.add_argument("project", nargs="?")
    quick_parser.set_defaults(func=cmd_quick)

    auto_parser = subparsers.add_parser(
        "auto", help="Run adaptive analysis (intelligent mode selection)"
    )
    auto_parser.add_argument("project", nargs="?")
    auto_parser.add_argument("--verbose", "-v", action="store_true")
    auto_parser.set_defaults(func=cmd_auto)

    config_parser = subparsers.add_parser("config", help="Manage deep mode configuration")
    config_parser.add_argument("--show", action="store_true")
    config_parser.add_argument("--set-default", type=str)
    config_parser.set_defaults(func=cmd_config)

    # ── interactions ──────────────────────────────────────────────────────────
    interactions_parser = subparsers.add_parser(
        "interactions", help="Manage interaction learning (real-time feedback loop)"
    )
    interactions_parser.add_argument("--process", action="store_true")
    interactions_parser.add_argument("--patterns", action="store_true")
    interactions_parser.add_argument("--tools", action="store_true")
    interactions_parser.add_argument("--setup", action="store_true")
    interactions_parser.add_argument("--days", type=int, default=7)
    interactions_parser.set_defaults(func=cmd_interactions)

    # ── batch-api-status / v2a-batch ──────────────────────────────────────────
    subparsers.add_parser("batch-api-status", help="Show batch API configuration").set_defaults(
        func=cmd_batch_status
    )

    v2a_batch_parser = subparsers.add_parser("v2a-batch", help="Manage V2a sprint batch jobs")
    v2a_batch_parser.add_argument("action", choices=["submit", "status", "retry", "cancel", "task"])
    v2a_batch_parser.add_argument("--wave", type=str)
    v2a_batch_parser.add_argument("--task-id", type=str)
    v2a_batch_parser.set_defaults(func=cmd_v2a_batch)

    # ── dashboard ─────────────────────────────────────────────────────────────
    subparsers.add_parser("dashboard", help="Show Symbiosis Engine Dashboard").set_defaults(
        func=cmd_dashboard
    )

    # ── bandwidth ─────────────────────────────────────────────────────────────
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
    )
    bandwidth_parser.add_argument("--json", action="store_true")
    bandwidth_parser.add_argument("--project", type=str)
    bandwidth_parser.add_argument("--days", type=int, default=7)
    bandwidth_parser.add_argument("--dry-run", action="store_true")
    bandwidth_parser.add_argument("--status", action="store_true")
    bandwidth_parser.add_argument("--experiment-name", type=str)
    bandwidth_parser.add_argument("--prediction-id", type=str)
    bandwidth_parser.add_argument("--confidence", type=float)
    bandwidth_parser.add_argument(
        "--source", type=str, choices=["claude", "codex", "cli", "system", "unknown"]
    )
    bandwidth_parser.add_argument("--session-id", type=str)
    bandwidth_parser.add_argument(
        "--domain",
        type=str,
        choices=["code", "architecture", "testing", "debugging", "planning", "documentation"],
    )
    bandwidth_parser.add_argument("--description", type=str)
    bandwidth_parser.add_argument("--outcome", type=str)
    bandwidth_parser.add_argument("--task", type=str)
    bandwidth_parser.add_argument(
        "--workstream",
        type=str,
        choices=["planning", "building", "testing", "shipping", "research"],
    )
    bandwidth_parser.add_argument("--next-action", type=str)
    bandwidth_parser.set_defaults(func=cmd_bandwidth)

    # ── briefing / briefing-style / statusline / reflect ─────────────────────
    briefing_parser = subparsers.add_parser("briefing", help="Generate daily briefing")
    briefing_parser.add_argument("--portfolio", action="store_true")
    briefing_parser.add_argument("--format", type=str, choices=["text", "json"], default="text")
    briefing_parser.add_argument("--no-color", action="store_true")
    briefing_parser.add_argument("--strict-signal", action="store_true")
    briefing_parser.add_argument(
        "--compact", action="store_true", help="Action-first 12-line terminal briefing"
    )
    briefing_parser.set_defaults(func=cmd_briefing)

    briefing_style_parser = subparsers.add_parser(
        "briefing-style", help="Validate/show persistent briefing style contract"
    )
    briefing_style_parser.add_argument("--validate", action="store_true")
    briefing_style_parser.add_argument("--show", action="store_true")
    briefing_style_parser.set_defaults(func=cmd_briefing_style)

    statusline_parser = subparsers.add_parser(
        "statusline", help="Generate compact single-line status output"
    )
    statusline_parser.add_argument("--json", action="store_true")
    statusline_parser.add_argument("--no-color", action="store_true")
    statusline_parser.add_argument("--max-age", type=int, default=90)
    statusline_parser.add_argument("--refresh", action="store_true")
    statusline_parser.set_defaults(func=cmd_statusline)

    reflect_parser = subparsers.add_parser(
        "reflect",
        help="Weekly reflection summary from git commits, batch results, and test outcomes",
    )
    reflect_parser.add_argument("--days", type=int, default=7)
    reflect_parser.add_argument("--json", action="store_true")
    reflect_parser.set_defaults(func=cmd_reflect)

    # ── git / sync / docs / tooling ───────────────────────────────────────────
    git_parser = subparsers.add_parser("git", help="Show Git/GitHub status")
    git_parser.add_argument("--json", action="store_true")
    git_parser.add_argument("--brief", action="store_true")
    git_parser.add_argument("--recommendations", "-r", action="store_true")
    git_parser.set_defaults(func=cmd_git)

    sync_parser = subparsers.add_parser("sync", help="Synchronize Git state")
    sync_parser.add_argument("--status", "-s", action="store_true")
    sync_parser.add_argument("--dry-run", action="store_true")
    sync_parser.add_argument("--full", action="store_true")
    sync_parser.add_argument("--fetch", action="store_true")
    sync_parser.add_argument("--pull", action="store_true")
    sync_parser.add_argument("--rebase", action="store_true")
    sync_parser.add_argument("--clean", action="store_true")
    sync_parser.add_argument("--force", action="store_true")
    sync_parser.set_defaults(func=cmd_sync)

    docs_parser = subparsers.add_parser(
        "docs", help="Sync docs to Claude Projects for mobile access"
    )
    docs_parser.add_argument("--init", action="store_true")
    docs_parser.add_argument("--status", "-s", action="store_true")
    docs_parser.add_argument("--add-source", metavar="PATH")
    docs_parser.add_argument("--source-name", metavar="NAME")
    docs_parser.add_argument("--force", action="store_true")
    docs_parser.add_argument("-v", "--verbose", action="store_true")
    docs_parser.set_defaults(func=cmd_docs)

    tooling_parser = subparsers.add_parser(
        "tooling", help="Claude Code tooling intelligence (hooks, commands, config)"
    )
    tooling_parser.add_argument(
        "action", nargs="?", choices=["config", "commands", "changes", "summary"], default="summary"
    )
    tooling_parser.add_argument("--query", "-q", type=str)
    tooling_parser.add_argument("--days", type=int)
    tooling_parser.set_defaults(func=cmd_tooling)

    # ── schedule / execute / orchestrate ──────────────────────────────────────
    schedule_parser = subparsers.add_parser(
        "schedule", help="Schedule a recommendation as a local-orchestrator agent"
    )
    schedule_parser.add_argument("intent", nargs="?")
    schedule_parser.add_argument("--project", type=str)
    schedule_parser.add_argument("--schedule", type=str, default="0 8 * * *")
    schedule_parser.add_argument("--team", action="store_true")
    schedule_parser.set_defaults(func=cmd_schedule)

    execute_parser = subparsers.add_parser("execute", help="Execute a recommendation immediately")
    execute_parser.add_argument("index", nargs="?", type=int)
    execute_parser.add_argument("--id", type=str)
    execute_parser.add_argument("--project", type=str)
    execute_parser.add_argument("--no-feedback", action="store_true")
    execute_parser.set_defaults(func=cmd_execute)

    orchestrate_parser = subparsers.add_parser(
        "orchestrate", help="Discover tasks, route to optimal models, and dispatch"
    )
    orchestrate_parser.add_argument("task", nargs="?", default="")
    orchestrate_parser.add_argument("--project", type=str, default="")
    orchestrate_parser.add_argument(
        "--priority", type=str, default="medium", choices=["critical", "high", "medium", "low"]
    )
    orchestrate_parser.add_argument("--dry-run", action="store_true")
    orchestrate_parser.add_argument("--json", action="store_true")
    orchestrate_parser.set_defaults(func=cmd_orchestrate)

    # ── goal/task/blocker commands ────────────────────────────────────────────
    try:
        from goal_commands import register_goal_commands

        register_goal_commands(subparsers)
    except Exception as e:
        print(f"Goal command registration failed: {e}", file=sys.stderr)

    # ── intelligence / portfolio / deps / watch ───────────────────────────────
    intelligence_parser = subparsers.add_parser(
        "intelligence", help="Query Cortex intelligence for context and patterns"
    )
    intelligence_parser.add_argument("query")
    intelligence_parser.add_argument("--project", "-p", type=str, default=None)
    intelligence_parser.add_argument(
        "--type", "-t", type=str, default="spec", choices=["spec", "impl", "analysis", "research"]
    )
    intelligence_parser.set_defaults(func=cmd_intelligence)

    portfolio_parser = subparsers.add_parser(
        "portfolio", help="Cross-project patterns and switching cost analysis"
    )
    portfolio_parser.add_argument("action", nargs="?", choices=["patterns"], default="patterns")
    portfolio_parser.add_argument("--propagate", action="store_true")
    portfolio_parser.add_argument("--switching-cost", action="store_true")
    portfolio_parser.set_defaults(func=cmd_portfolio)

    deps_parser = subparsers.add_parser("deps", help="Dependency analysis for projects")
    deps_parser.add_argument("project", nargs="?", default=None)
    deps_parser.add_argument("--cross-project", action="store_true")
    deps_parser.set_defaults(func=cmd_deps)

    watch_parser = subparsers.add_parser("watch", help="Scheduled verification tasks")
    watch_parser.add_argument("--run", action="store_true")
    watch_parser.add_argument("--autonomous", action="store_true")
    watch_parser.set_defaults(func=cmd_watch)

    # ── sessions / signals / doctor ───────────────────────────────────────────
    sessions_parser = subparsers.add_parser("sessions", help="Show Claude Code sessions")
    sessions_parser.add_argument("--active", action="store_true")
    sessions_parser.set_defaults(func=cmd_sessions)

    signals_parser = subparsers.add_parser(
        "signals", help="Run active cross-project signal detection"
    )
    signals_parser.add_argument(
        "--severity", choices=["critical", "high", "medium", "low"], default=None
    )
    signals_parser.set_defaults(func=cmd_signals)

    doctor_parser = subparsers.add_parser("doctor", help="Run environment health checks")
    doctor_parser.add_argument(
        "--fix",
        action="store_true",
        help="Repair what doctor can: flush spooled decisions into decisions.jsonl",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    # `cortex demo` — self-contained 30s proof of the prompt→outcome FK loop.
    from cli.commands.demo import cmd_demo

    subparsers.add_parser(
        "demo", help="30-second proof of the prompt→outcome FK loop (no API key)"
    ).set_defaults(func=cmd_demo)

    # ── complex nested commands (delegated to register_* helpers) ─────────────
    register_process_cmds(subparsers)
    register_batch_local_cmds(subparsers)
    register_work_cmds(subparsers)
    register_v2_cmds(subparsers)
    register_runtime_cmds(subparsers)

    # ── nightly-reflect ───────────────────────────────────────────────────────
    from cli.commands.v2_ops import cmd_reflect_run, cmd_reflect_status

    nightly_parser = subparsers.add_parser(
        "nightly-reflect", help="Nightly reflection pipeline (Phase 3B)"
    )
    nightly_subs = nightly_parser.add_subparsers(dest="nightly_reflect_command")
    nr_run = nightly_subs.add_parser("run", help="Run nightly reflection now")
    nr_run.add_argument("--dry-run", action="store_true", help="Skip API call and memory seeding")
    nr_run.set_defaults(func=cmd_reflect_run)
    nightly_subs.add_parser("status", help="Show last reflection status").set_defaults(
        func=cmd_reflect_status
    )
    nightly_parser.add_argument("--run", action="store_true")
    nightly_parser.add_argument("--dry-run", action="store_true")
    nightly_parser.add_argument("--status", action="store_true")

    def _nightly_dispatch(args):
        if getattr(args, "status", False):
            cmd_reflect_status(args)
        else:
            cmd_reflect_run(args)

    nightly_parser.set_defaults(func=_nightly_dispatch)

    # ── recall (temporal retrieval) ───────────────────────────────────────────
    from cli.commands.v2_ops import register_recall_cmds

    register_recall_cmds(subparsers)

    # ── providers (local inference status) ───────────────────────────────────
    from cli.commands.v2_ops import register_providers_cmds

    register_providers_cmds(subparsers)

    # ── check-thresholds ──────────────────────────────────────────────────────
    from cli.commands.v2_ops import register_threshold_cmds

    register_threshold_cmds(subparsers)

    # ── MVP surface trim ──────────────────────────────────────────────────────
    if not os.environ.get("CORTEX_EXPERIMENTAL"):
        _hide_experimental(subparsers)

    # ── dispatch ──────────────────────────────────────────────────────────────
    args = parser.parse_args()

    if not hasattr(args, "func"):
        # No subcommand → compact dashboard (Option C)
        from cli.commands.compact import cmd_compact

        cmd_compact(args)
        return

    args.func(args)


if __name__ == "__main__":
    main()
