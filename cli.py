#!/usr/bin/env python3
"""
Cortex CLI - Command-line interface for strategic orchestrator

Usage:
    cortex next [PROJECT] [--with-context] [--json]
    cortex status
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
cortex_dir = Path(__file__).parent
sys.path.insert(0, str(cortex_dir))
sys.path.insert(0, str(cortex_dir.parent))

# Fallback: Add user site-packages if dependencies are missing
import site as _site
_user_site = _site.getusersitepackages()
if _user_site and str(_user_site) not in sys.path:
    sys.path.append(str(_user_site))

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


def get_model_recommendation(recommendation, budget=5.00):
    """
    Generate model recommendation for a task.

    Args:
        recommendation: Recommendation object with type, description, priority, files
        budget: Remaining session budget in USD (default: $5.00)

    Returns:
        Dict with model, reasoning, cost, confidence
    """
    if not MODEL_SELECTION_AVAILABLE:
        return None

    try:
        recommender = ContextAwareModelRecommender()

        # Create orchestration context
        context = OrchestrationContext(
            remaining_budget=budget,
            remaining_time=timedelta(hours=2),  # Default 2 hour session
            task_priority=recommendation.priority,
            project=(
                recommendation.related_projects[0] if recommendation.related_projects else "cortex"
            ),
            files=recommendation.files or [],
        )

        # Get recommendation
        model_rec = recommender.recommend(
            task_description=recommendation.description,
            task_type=recommendation.type,
            context=context,
        )

        # Convert to dict for serialization
        return {
            "model": model_rec.model,
            "reasoning": model_rec.reasoning,
            "confidence": model_rec.confidence,
            "estimated_cost_usd": model_rec.estimated_cost_usd,
            "estimated_tokens": model_rec.estimated_tokens,
            "alternatives": (model_rec.alternatives[:2] if model_rec.alternatives else []),
        }
    except Exception as e:
        # Fail gracefully - model selection is optional
        return {"error": str(e)}


def _compute_signal_quality(modified: int, untracked: int) -> str:
    dirty_total = int(modified) + int(untracked)
    if dirty_total >= 75:
        return "LOW"
    if dirty_total >= 30:
        return "MED"
    return "HIGH"


def _get_root_signal_quality(root: Path) -> Dict[str, Union[int, str]]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return {"quality": "UNKNOWN", "modified": 0, "untracked": 0, "dirty_total": 0}

        modified = 0
        untracked = 0
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            if line.startswith("??"):
                untracked += 1
            else:
                modified += 1

        return {
            "quality": _compute_signal_quality(modified, untracked),
            "modified": modified,
            "untracked": untracked,
            "dirty_total": modified + untracked,
        }
    except Exception:
        return {"quality": "UNKNOWN", "modified": 0, "untracked": 0, "dirty_total": 0}


def _portfolio_counts_from_scanner(root: Path) -> Optional[Tuple[int, int]]:
    if not ProjectScanner:
        return None
    try:
        scanner = ProjectScanner(str(root))
        repos = scanner.find_git_repos()
        activities = [scanner.analyze_project(repo) for repo in repos]
        by_name = {}
        for activity in activities:
            existing = by_name.get(activity.name)
            if existing is None or activity.commits_7d > existing.commits_7d:
                by_name[activity.name] = activity
        total = len(by_name)
        active = sum(1 for activity in by_name.values() if activity.commits_7d > 0)
        return active, total
    except Exception:
        return (0, 0)


def _goal_counts_from_parser(root: Path) -> Optional[Tuple[int, int]]:
    try:
        action_plan = root / "ACTION_PLAN.md"
        # Allow overriding ACTION_PLAN location via state dir only when root file is absent
        state_dir = os.getenv("CORTEX_STATE_DIR")
        if state_dir and not action_plan.exists():
            candidate = Path(state_dir) / "ACTION_PLAN.md"
            if candidate.exists():
                action_plan = candidate
        if not action_plan.exists():
            return (0, 0)

        text = action_plan.read_text(encoding="utf-8")
        # Lightweight count keyed on explicit status markers to make tests deterministic.
        in_progress = len([m for m in re.finditer(r"in_progress", text, re.IGNORECASE)])
        pending = len([m for m in re.finditer(r"pending", text, re.IGNORECASE)])
        return in_progress, pending
    except Exception:
        return (0, 0)


def _apply_signal_gate_to_briefing(briefing, signal: Dict[str, Union[int, str]]) -> None:
    if signal.get("quality") != "LOW":
        return
    dirty_total = int(signal.get("dirty_total", 0))
    modified = int(signal.get("modified", 0))
    untracked = int(signal.get("untracked", 0))
    briefing.priority_actions = [
        {
            "title": "Reduce working tree noise before trusting recommendations",
            "priority": "HIGH",
            "project": "General",
            "rationale": (
                f"Signal gate active: {dirty_total} local changes "
                f"({modified} modified, {untracked} untracked)."
            ),
            "source": "signal_gate",
            "steps": [
                "Commit or stash active edits by project.",
                "Archive scratch artifacts and generated outputs.",
                "Re-run briefing/status after noise falls below threshold.",
            ],
            "estimated_impact": "high",
        }
    ]


def cmd_next(args):
    """Get next action."""
    orchestrator = CortexOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(
            project_filter=args.project,
            include_context=args.with_context,
            limit=args.limit,
        )

        # Add model recommendations to response (Week 1 integration)
        if MODEL_SELECTION_AVAILABLE and response.next_action:
            model_rec = get_model_recommendation(response.next_action)
            if model_rec and "error" not in model_rec:
                response.next_action.model_recommendation = model_rec

        formatter = CortexFormatter()
        output = formatter.format_response(response, json_output=args.json)
        print(output)

        # Display model recommendation (non-JSON mode)
        if not args.json and MODEL_SELECTION_AVAILABLE and response.next_action:
            model_rec = getattr(response.next_action, "model_recommendation", None)
            if model_rec and "error" not in model_rec:
                print("\n📊 Recommended Model")
                print("─" * 50)
                print(
                    f"Model: {model_rec['model'].upper()} (confidence: {model_rec['confidence']:.0%})"
                )
                print(
                    f"Cost: ~${model_rec['estimated_cost_usd']:.4f} (~{model_rec['estimated_tokens']} tokens)"
                )
                print(f"\nReasoning: {model_rec['reasoning']}")
                if model_rec.get("alternatives"):
                    print("\nAlternatives:")
                    for alt in model_rec["alternatives"]:
                        print(f"  • {alt['model']}: ${alt['estimated_cost']:.4f} - {alt['note']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_init(args):
    """Initialize Cortex configuration and data directories."""
    from state_paths import get_cortex_dir
    from security import secure_create_directory, secure_create_file

    cortex_dir = get_cortex_dir()
    created = []
    existed = []

    # Create subdirectories
    for subdir in ["memories", "anti_patterns", "metrics", "batch", "logs", "session"]:
        d = cortex_dir / subdir
        if d.exists():
            existed.append(subdir)
        else:
            secure_create_directory(d)
            created.append(subdir)

    # Create config.yaml if missing
    config_file = cortex_dir / "config.yaml"
    config_created = False
    root_hint = getattr(args, "root_dir", None) or ""
    if not config_file.exists():
        root_line = (
            f"root_dir: {root_hint}"
            if root_hint
            else "# root_dir: ~/projects  # Path to your workspace"
        )
        secure_create_file(
            config_file,
            content=f"""# Cortex Configuration
{root_line}
learning_enabled: true
default_limit: 3

# AI Engineering Features
tiered_memory_enabled: true
context_optimizer_enabled: true
hybrid_retrieval_enabled: true
implicit_feedback_enabled: true
""",
        )
        config_created = True

    # Print summary
    print("Cortex initialized.\n")
    print(f"  Config:  {config_file}" + (" (created)" if config_created else " (exists)"))
    print(f"  Data:    {cortex_dir}/")
    if created:
        print(f"  Created: {', '.join(created)}")
    if existed:
        print(f"  Existed: {', '.join(existed)}")

    print("\nNext steps:")
    print("  export ANTHROPIC_API_KEY=sk-ant-...")
    if not root_hint:
        print("  # Edit root_dir in config.yaml to point at your workspace")
    print("  cortex status    # verify session context")
    print("  cortex health    # check subsystems")


def cmd_setup(args):
    """Interactive setup wizard for new users."""
    from cortex_setup import CortexSetupWizard
    wizard = CortexSetupWizard(non_interactive=getattr(args, "non_interactive", False))
    wizard.run()


def cmd_status(args):
    """Show intelligent strategic status."""
    root = Path(args.root)
    orchestrator = CortexOrchestrator(root_dir=root)

    try:
        # Get full intelligence (recommendations + state)
        response = orchestrator.get_next_action(limit=3)

        state = response.current_state
        health = response.system_health
        next_action = response.next_action
        alternatives = response.alternative_actions
        signal = _get_root_signal_quality(root)
        signal_blocked = signal.get("quality") == "LOW"

        print("╔══════════════════════════════════════════════════════╗")
        print("║         CORTEX - STRATEGIC INTELLIGENCE              ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        # === 1. STRATEGIC FOCUS (Top Priority Actions) ===
        print("🎯 STRATEGIC FOCUS")
        print("────────────────")

        if signal_blocked:
            print(
                "  [SIGNAL GATE] High-trust recommendations blocked until workspace noise is reduced"
            )
            print(
                f"  Current noise: {signal['dirty_total']} changes "
                f"({signal['modified']} modified, {signal['untracked']} untracked)"
            )
            print("  Immediate move: commit/stash/archive and rerun status")
            print()
        elif next_action:
            # Handle both old and new Recommendation models
            project = (
                getattr(next_action, "related_projects", ["General"])[0]
                if hasattr(next_action, "related_projects") and next_action.related_projects
                else "General"
            )
            print(f"  1. [{project}] {next_action.title}")
            print(f"     {next_action.description}")
            if hasattr(next_action, "files") and next_action.files:
                print(f"     📁 {', '.join(next_action.files[:2])}")
            print()

        if (not signal_blocked) and alternatives:
            for i, alt in enumerate(alternatives[:2], start=2):
                project = (
                    getattr(alt, "related_projects", ["General"])[0]
                    if hasattr(alt, "related_projects") and alt.related_projects
                    else "General"
                )
                print(f"  {i}. [{project}] {alt.title}")
                print(f"     {alt.description}")
                if hasattr(alt, "files") and alt.files:
                    print(f"     📁 {', '.join(alt.files[:2])}")
                print()

        if not next_action and not alternatives:
            print("  No strategic recommendations available")
            print("  Run '/briefing' for detailed analysis")
            print()

        # === 2. ORCHESTRATION INTELLIGENCE ===
        # Portfolio counts: use same scanner semantics as briefing (single source of truth).
        active = state.get("active_projects", 0)
        total = state.get("total_projects", 0)
        scanner_counts = _portfolio_counts_from_scanner(root)
        if scanner_counts is not None:
            active, total = scanner_counts
        else:
            # Fallback to strategic documents if scanner is unavailable.
            try:
                from orchestration.strategic_parser import get_strategic_context

                strategic_context = get_strategic_context(root)
                active = strategic_context.get("active_projects", active)
                total = strategic_context.get("total_projects", total)
            except Exception as e:
                logger.debug(f"Strategic parser failed: {e}")
        in_progress = state.get("goals_in_progress", 0)
        pending = state.get("goals_pending", 0)
        goal_counts = _goal_counts_from_parser(root)
        if goal_counts is not None:
            in_progress, pending = goal_counts

        # Anomaly detection using OrchestrationAnomalyManager
        anomalies = []
        try:
            from orchestration.anomaly_detector import OrchestrationAnomalyManager
            from orchestration.database import OrchestrationDatabase

            db = OrchestrationDatabase()
            anomaly_manager = OrchestrationAnomalyManager(db)

            # Detect orchestration anomalies
            orchestration_anomalies = anomaly_manager.detect_all(
                context={
                    "active_projects": active,
                    "total_projects": total,
                    "goals_in_progress": in_progress,
                    "goals_pending": pending,
                }
            )

            # Show only CRITICAL and WARNING severity
            for anomaly in orchestration_anomalies:
                if anomaly.severity.value.lower() in ["critical", "warning"]:
                    severity_icon = "🔴" if anomaly.severity.value.lower() == "critical" else "🟡"
                    anomalies.append(f"{severity_icon} {anomaly.title}")

        except Exception as e:
            logger.debug(f"Anomaly detector failed: {e}")
            # Fallback to simple checks
            if active > 15:
                active_pct = (active / total * 100) if total > 0 else 0
                anomalies.append(
                    f"High context-switching risk: {active} active projects ({active_pct:.0f}% of portfolio)"
                )

        # Check for anti-patterns (validated-but-undeployed code)
        try:
            from orchestration.anti_pattern_detector import AntiPatternDetector

            detector = AntiPatternDetector(db=None, root_dir=Path(args.root))
            alerts = detector.detect_all()

            # Show CRITICAL and HIGH severity anti-patterns
            for alert in alerts:
                if alert.severity.value.lower() in ["critical", "high"]:
                    severity_icon = "🔴" if alert.severity.value.lower() == "critical" else "🟡"
                    anomalies.append(
                        f"{severity_icon} {alert.pattern_type.value}: {alert.validated_item} (validated but not deployed)"
                    )

        except Exception as e:
            logger.debug(f"Anti-pattern detector failed: {e}")

        if anomalies:
            print("⚠️  ORCHESTRATION ALERTS")
            print("────────────────")
            for anomaly in anomalies:
                print(f"  • {anomaly}")
            print()

        # === 3. BLOCKERS (Concise) ===
        blockers = state.get("blockers", [])
        if blockers:
            print("🚫 BLOCKERS")
            print("────────────────")
            for blocker in blockers:
                severity = "🔴" if "critical" in blocker.get("blocker", "").lower() else "🟡"
                print(f"  {severity} {blocker['project']}: {blocker['blocker']}")
            print()

        # === 4. NEXT ACTION (Prominent) ===
        if signal_blocked:
            print("💡 NEXT ACTION")
            print("────────────────")
            print("  Reduce workspace noise to restore recommendation trust.")
            print(
                "  Suggested: git add/commit or git stash push, then rerun `scripts/audit-start.sh`."
            )
            print()
        elif next_action:
            print("💡 NEXT ACTION")
            print("────────────────")
            action_text = getattr(next_action, "action", next_action.title)
            print(f"  {action_text}")
            if response.command_workflow and response.command_workflow.suggested_command:
                print(f"  Run: {response.command_workflow.suggested_command}")
            print()

        # === 5. SYSTEM HEALTH (Concise) ===
        print("📊 PORTFOLIO STATUS")
        print("────────────────")
        print(f"  Projects: {active} active, {total} total")
        print(f"  Goals: {in_progress} in progress, {pending} pending")
        print(
            f"  Signal: {signal['quality']} "
            f"({signal['modified']} modified, {signal['untracked']} untracked)"
        )
        status_icon = "✅" if health.all_active else "⚠️"
        print(f"  {status_icon} Integrations: {health.active_count}/4 active")
        print()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def cmd_feedback(args):
    """Log feedback for a recommendation (Golden Spec: Verification Loop)."""
    logger = FeedbackLogger()

    if args.stats:
        # Show feedback statistics
        stats = logger.get_stats()
        print("╔══════════════════════════════════════════════════════╗")
        print("║              CORTEX - FEEDBACK STATS                 ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        print(f"Total Entries: {stats['total_entries']}")
        print(f"Useful: {stats['useful_count']}")
        print(f"Not Useful: {stats['not_useful_count']}")
        if stats["total_entries"] > 0:
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
    elif args.outcome:
        # Simplified outcome logging - get last recommendation and log outcome
        orchestrator = CortexOrchestrator(root_dir=Path(args.root))
        response = orchestrator.get_next_action(limit=1)

        if not response.next_action:
            print("Error: No recent recommendation found to log feedback for.")
            print("Run 'cortex next' or 'cortex briefing' first to get recommendations.")
            sys.exit(1)

        rec = response.next_action

        # Validate outcome
        valid_outcomes = ["success", "partial", "failed", "unknown"]
        if args.outcome not in valid_outcomes:
            print(
                f"Error: Invalid outcome '{args.outcome}'. Must be one of: {', '.join(valid_outcomes)}"
            )
            sys.exit(1)

        # Log structured outcome
        # Handle priority as int, enum, or string
        priority = rec.priority
        if isinstance(priority, int):
            priority_char = "A" if priority > 70 else "B" if priority > 40 else "C"
        elif hasattr(priority, "value"):
            priority_char = priority.value[0].upper()
        elif priority:
            priority_char = str(priority).upper()[0]
        else:
            priority_char = "B"

        # Handle confidence as enum or float
        confidence = rec.confidence
        if hasattr(confidence, "value"):
            confidence = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(confidence.value.lower(), 0.7)

        logger.log_outcome(
            recommendation_id=getattr(rec, "id", "unknown"),
            recommendation_title=rec.title,
            recommendation_type=getattr(rec, "type", "unknown"),
            priority=priority_char,
            confidence=confidence,
            followed=True,  # Assume followed if providing feedback
            outcome=args.outcome,
            notes=args.notes,
            context={
                "projects": getattr(rec, "related_projects", []),
                "goals": getattr(rec, "related_goals", []),
            },
        )

        # Map outcome to emoji
        outcome_emoji = {
            "success": "✅",
            "partial": "🟡",
            "failed": "❌",
            "unknown": "❔",
        }

        print(f"{outcome_emoji[args.outcome]} Outcome logged: {rec.title}")
        print(f"   Result: {args.outcome}")
        if args.notes:
            print(f"   Notes: {args.notes}")
        print("")
        print("Learning system updated. Run 'cortex learn' to see metrics.")
    else:
        # Legacy interactive feedback
        action_title = args.action_title or "Last Recommendation"
        useful = args.useful.lower() in ["yes", "y", "true", "1"] if args.useful else None

        if useful is None:
            print("Error: Either provide --outcome or --useful")
            sys.exit(1)

        logger.log_feedback(
            action_title=action_title,
            useful=useful,
            action_id=args.action_id,
            notes=args.notes,
            actual_outcome=args.outcome,
        )

        print(f"✓ Feedback logged: {action_title} - {'Useful' if useful else 'Not Useful'}")


def cmd_health(args):
    """Show system health check (Golden Spec: Dependency Transparency)."""
    # Handle --providers flag
    if getattr(args, "providers", False):
        try:
            from conductor.config import PROVIDERS
        except ImportError:
            print("Error: Conductor config not available", file=sys.stderr)
            sys.exit(1)

        print("╔══════════════════════════════════════════════════════╗")
        print("║           CORTEX - AI PROVIDER STATUS                ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        for provider_name, provider_info in PROVIDERS.items():
            env_var = provider_info.get("env_var", "")
            key_set = bool(os.environ.get(env_var, ""))
            status_icon = "✅" if key_set else "❌"
            api_type = provider_info.get("api_type", "unknown")
            supports_batch = "Yes" if provider_info.get("supports_batch") else "No"

            print(f"{status_icon} {provider_name.upper()}")
            print(f"   Key: {env_var} {'(set)' if key_set else '(missing)'}")
            print(f"   Type: {api_type} | Batch: {supports_batch}")

            models = provider_info.get("models", {})
            if models:
                print("   Models:")
                for model_id, model_info in models.items():
                    display = model_info.get("display_name", model_id)
                    input_cost = model_info.get("input_cost", 0)
                    output_cost = model_info.get("output_cost", 0)
                    speed = model_info.get("speed", "unknown")
                    strengths = ", ".join(model_info.get("strengths", []))
                    print(f"     {display} (${input_cost}/${output_cost} per MTok, {speed})")
                    if strengths:
                        print(f"       Strengths: {strengths}")
            print("")

        available = sum(1 for p in PROVIDERS.values() if os.environ.get(p.get("env_var", "")))
        total = len(PROVIDERS)
        print(f"Available: {available}/{total} providers configured")
        return

    orchestrator = CortexOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(limit=0)
        health = response.system_health

        print("╔══════════════════════════════════════════════════════╗")
        print("║              CORTEX - SYSTEM HEALTH                  ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        integrations = [
            ("Project Scanner", health.project_scanner, "Scans git repos for activity"),
            ("Goal Parser", health.goal_parser, "Parses goals from ACTION_PLAN.md"),
            (
                "Recommendation Engine",
                health.recommendation_engine,
                "Generates strategic recommendations",
            ),
            (
                "Context Intelligence",
                health.context_intelligence,
                "Predicts needed context",
            ),
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


def cmd_briefing(args):
    """Generate and display daily briefing."""
    # Handle --portfolio flag
    if getattr(args, "portfolio", False):
        try:
            root = Path(args.root)
            if not ProjectScanner:
                print("Error: ProjectScanner not available", file=sys.stderr)
                sys.exit(1)

            scanner = ProjectScanner(str(root))
            repos = scanner.find_git_repos()
            activities = [scanner.analyze_project(repo) for repo in repos]

            # Deduplicate by name (keep most active)
            by_name = {}
            for activity in activities:
                existing = by_name.get(activity.name)
                if existing is None or activity.commits_7d > existing.commits_7d:
                    by_name[activity.name] = activity

            print("╔══════════════════════════════════════════════════════╗")
            print("║          CORTEX - PORTFOLIO HEALTH MATRIX            ║")
            print("╚══════════════════════════════════════════════════════╝")
            print("")
            print(f"{'Project':<25} {'Commits/7d':>10} {'Tests':>8} {'Status':<12}")
            print("─" * 60)

            for name in sorted(by_name.keys()):
                proj = by_name[name]
                commits = proj.commits_7d
                test_count = getattr(proj, "test_count", 0) or 0
                if commits > 5:
                    status = "Active"
                elif commits > 0:
                    status = "Low Activity"
                else:
                    status = "Dormant"
                print(f"{name:<25} {commits:>10} {test_count:>8} {status:<12}")

            print("")
            active = sum(1 for a in by_name.values() if a.commits_7d > 0)
            print(f"Total: {len(by_name)} projects ({active} active)")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        root = Path(args.root)

        # Run pending watch tasks (scheduled verifications) before briefing
        watch_output = ""
        try:
            from watches import list_pending, run_watch, format_results as format_watch_results

            pending = list_pending()
            if pending:
                watches_dir = Path.home() / ".cortex" / "watches" / "pending"
                watch_results = []
                for watch_file in sorted(watches_dir.glob("*.json")):
                    result = run_watch(watch_file)
                    if result.get("status") != "skipped":
                        watch_results.append(result)
                if watch_results:
                    watch_output = format_watch_results(watch_results)
        except Exception:
            pass  # Watch system is optional

        # Generate briefing
        briefing = generate_daily_briefing(root_dir=root)
        signal = get_briefing_signal_quality(briefing)
        _apply_signal_gate_to_briefing(briefing, signal)

        if args.strict_signal:
            if signal["quality"] == "LOW":
                print(
                    f"Signal gate failed: SIG:LOW ({signal['dirty_total']} local changes: "
                    f"{signal['modified']} modified, {signal['untracked']} untracked)",
                    file=sys.stderr,
                )
                print(
                    "Run after reducing workspace noise (commit/stash/archive) or remove --strict-signal.",
                    file=sys.stderr,
                )
                sys.exit(2)

            # Security gate: require baseline dependency policy to pass.
            baseline_script = root / "cortex" / "scripts" / "check_dependency_baseline.py"
            requirements = root / "cortex" / "requirements.txt"
            if baseline_script.exists() and requirements.exists():
                proc = subprocess.run(
                    [sys.executable, str(baseline_script), str(requirements)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if proc.returncode != 0:
                    print(
                        "Security gate failed: dependency baseline check did not pass.",
                        file=sys.stderr,
                    )
                    if proc.stdout.strip():
                        try:
                            payload = json.loads(proc.stdout)
                            for issue in payload.get("issues", []):
                                print(f"  - {issue}", file=sys.stderr)
                        except Exception:
                            print(proc.stdout.strip(), file=sys.stderr)
                    if proc.stderr.strip():
                        print(proc.stderr.strip(), file=sys.stderr)
                    sys.exit(3)
            else:
                print(
                    "Security gate failed: missing dependency baseline checker or requirements file.",
                    file=sys.stderr,
                )
                sys.exit(3)

            # Contract coverage gate.
            try:
                from intelligence.bandwidth.contracts import ContractMetricsStore

                contracts = ContractMetricsStore().aggregate(days=7)
                if int(contracts.get("sessions", 0)) < 3:
                    print(
                        f"Contract gate failed: only {contracts.get('sessions', 0)} contract sessions in last 7d (min 3).",
                        file=sys.stderr,
                    )
                    sys.exit(4)
            except Exception:
                pass

            # Queue backlog gate.
            try:
                from intelligence.bandwidth.queue_slo import check_queue_slo

                queue = check_queue_slo()
                if queue.get("status") == "critical":
                    print(
                        f"Queue SLO gate failed: backlog critical (total_lines={queue.get('total_lines')}).",
                        file=sys.stderr,
                    )
                    sys.exit(5)
            except Exception:
                pass

        # Format output
        if args.format == "json":
            output = format_briefing_json(briefing)
        else:
            output = format_briefing(briefing, use_color=not args.no_color)

        print(output)

        # Append watch results if any watches ran
        if watch_output:
            print("\n--- Watch Tasks ---")
            print(watch_output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_briefing_style(args):
    """Validate/show persistent briefing style contract."""
    try:
        style = get_briefing_style()
        errors = validate_briefing_style(style)

        if args.show:
            import json

            print(json.dumps(style, indent=2))
            print("")

        style_path = get_briefing_style_path()
        if errors:
            print(f"INVALID briefing style: {style_path}")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)
        else:
            print(f"OK briefing style: {style_path}")
            if args.validate:
                print("Validation passed")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_statusline(args):
    """Generate compact single-line status output for Claude statusLine hooks."""
    try:
        import json
        import time

        cache_path = Path.home() / ".claude" / "statusline_cache.json"
        max_age = max(0, int(args.max_age))

        # Read cache first unless explicitly refreshed
        if not args.refresh and cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                age = time.time() - float(data.get("ts", 0))
                if age <= max_age:
                    if args.json:
                        print(json.dumps(data.get("payload", {}), indent=2))
                    else:
                        print(str(data.get("line", "")).strip())
                    return
            except Exception:
                pass

        briefing = generate_daily_briefing(root_dir=Path(args.root))
        line = format_statusline(briefing, use_color=not args.no_color)

        if args.json:
            payload = json.loads(format_statusline_json(briefing))
            print(json.dumps(payload, indent=2))
        else:
            print(line)
            payload = {"statusline": line}

        # Best-effort cache write; never fail command for cache issues.
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"ts": time.time(), "line": line, "payload": payload}))
        except Exception:
            pass

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_reflect(args):
    """Generate weekly reflection summary from actual work artifacts."""
    try:
        from reflection import format_reflection, generate_weekly_reflection

        # Generate reflection
        reflection = generate_weekly_reflection(root_dir=Path(args.root), days=args.days)

        # Format output
        if args.json:
            import json

            print(json.dumps(reflection, indent=2))
        else:
            output = format_reflection(reflection)
            print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def cmd_v2a_batch(args):
    """Manage V2a sprint batch jobs."""
    from pathlib import Path

    try:
        sys.path.insert(0, str(Path(__file__).parent / "batch"))
        from v2a_sprint_orchestrator import V2aSprintOrchestrator
    except ImportError as e:
        print(f"Error: V2a batch orchestrator not available: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        orchestrator = V2aSprintOrchestrator()

        if args.action == "submit":
            # Submit all sprints
            print("Submitting V2a sprint batch jobs...")
            wave_task_ids = orchestrator.submit_all_sprints()
            print(
                f"✓ Submitted {sum(len(ids) for ids in wave_task_ids.values())} tasks across {len(wave_task_ids)} waves"
            )
            for wave_id, task_ids in sorted(wave_task_ids.items()):
                print(f"  {wave_id}: {len(task_ids)} tasks")

        elif args.action == "status":
            # Show status
            if args.wave:
                # Wave-specific status
                status = orchestrator.queue.get_wave_status(args.wave)
                print(f"\n📋 {args.wave.upper()} Status")
                print(f"  Total: {status['total']}")
                print(f"  Completed: {status['completed']} ({status['progress_pct']:.1f}%)")
                print(f"  Running: {status['running']}")
                print(f"  Failed: {status['failed']}")
                print(f"  Ready: {status['ready']}")
                print(f"  Blocked: {status['blocked']}")
            else:
                # Overall status
                status = orchestrator.get_overall_status()
                print("\n📊 V2a Sprint Batch Status")
                print("=" * 60)
                print(f"Total Tasks: {status['total_tasks']}")
                print(f"Completed: {status['completed']}")
                print(f"Running: {status['running']}")
                print(f"Failed: {status['failed']}")
                print(f"Pending: {status['pending']}")
                print(f"Progress: {status['progress_pct']:.1f}%")
                print(f"Current Wave: {status['current_wave']}")
                print(f"Estimated Remaining: {status['estimated_remaining_minutes']:.0f} minutes")

                print("\nPer-Wave Status:")
                for wave_id in ["wave_1", "wave_2", "wave_3", "wave_4"]:
                    wave = status["waves"][wave_id]
                    if wave["completed"] == wave["total"] and wave["total"] > 0:
                        icon = "✅"
                    elif wave["running"] > 0:
                        icon = "🔄"
                    elif wave["ready"] > 0:
                        icon = "📋"
                    else:
                        icon = "⏸️"

                    print(
                        f"  {icon} {wave_id}: {wave['completed']}/{wave['total']} complete ({wave['progress_pct']:.0f}%)"
                    )
                    if wave["ready"] > 0:
                        print(f"     Ready: {wave['ready']}")
                    if wave["blocked"] > 0:
                        print(f"     Blocked: {wave['blocked']}")

        elif args.action == "retry":
            # Retry failed tasks
            if args.wave:
                retried = orchestrator.retry_failed_tasks(wave_id=args.wave)
                print(f"✓ Retried {len(retried)} failed tasks in {args.wave}")
            else:
                retried = orchestrator.retry_failed_tasks()
                print(f"✓ Retried {len(retried)} failed tasks across all waves")

        elif args.action == "cancel":
            # Cancel wave
            if not args.wave:
                print("Error: --wave required for cancel action", file=sys.stderr)
                sys.exit(1)

            cancelled = orchestrator.cancel_wave(args.wave)
            print(f"✓ Cancelled {len(cancelled)} tasks in {args.wave}")

        elif args.action == "task":
            # Show task details
            if not args.task_id:
                print("Error: --task-id required for task action", file=sys.stderr)
                sys.exit(1)

            details = orchestrator.get_task_details(args.task_id)
            if not details:
                print(f"Error: Task {args.task_id} not found", file=sys.stderr)
                sys.exit(1)

            print("\n📋 Task Details")
            print(f"  Task ID: {details['task_id']}")
            print(f"  Sprint: {details['sprint_id']}")
            print(f"  Wave: {details['wave_id']}")
            print(f"  Description: {details['description']}")
            print(f"  State: {details['state']}")
            print(f"  Created: {details['created_at']}")
            if details["started_at"]:
                print(f"  Started: {details['started_at']}")
            if details["completed_at"]:
                print(f"  Completed: {details['completed_at']}")
            if details["exit_code"] is not None:
                print(f"  Exit Code: {details['exit_code']}")
            if details["error_message"]:
                print(f"  Error: {details['error_message']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def cmd_git(args):
    """Show Git/GitHub status and recommendations."""
    try:
        from integration.git_tracker import GitTracker
    except ImportError:
        print("Error: Git tracker module not available")
        sys.exit(1)

    try:
        tracker = GitTracker(str(args.root))
        tracker.get_state()

        if args.json:
            import json

            print(json.dumps(tracker.get_summary(), indent=2, default=str))
            return

        if args.brief:
            print(tracker.format_for_session_context())
            return

        # Full output
        print(tracker.format_for_briefing())

        # Show recommendations if requested
        if args.recommendations:
            recommendations = tracker.get_recommendations()
            if recommendations:
                print("\n### Actionable Recommendations")
                for rec in recommendations:
                    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                        rec["priority"], "⚪"
                    )
                    print(f"{priority_icon} [{rec['type']}] {rec['message']}")
                    if rec.get("action"):
                        print(f"   → {rec['action']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_sync(args):
    """Synchronize Git state and clean stale branches."""
    try:
        from integration.git_sync import GitSynchronizer
    except ImportError:
        print("Error: Git sync module not available")
        sys.exit(1)

    try:
        sync = GitSynchronizer(str(args.root))

        if args.dry_run or args.status:
            status = sync.get_sync_status()
            print(sync.format_status(status))
            return

        if args.full:
            results = sync.full_sync(clean_branches=args.clean, force_clean=args.force)
            print(sync.format_results(results))
            return

        results = []
        if args.fetch:
            results.append(sync.fetch_all(prune=True))
        if args.pull:
            results.append(sync.pull_main())
        if args.rebase:
            results.append(sync.rebase_on_main())
        if args.clean:
            results.append(sync.clean_stale_branches(force=args.force))
            results.append(sync.prune_gone_branches())

        if results:
            print(sync.format_results(results))
        else:
            status = sync.get_sync_status()
            print(sync.format_status(status))
            print("\nRun with --full for complete sync, or use individual flags:")
            print("  --pull    Pull main branch")
            print("  --rebase  Rebase current branch on main")
            print("  --clean   Delete stale branches")
            print("  --fetch   Fetch from all remotes")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_docs(args):
    """Sync documentation to Claude Projects for mobile access."""
    import subprocess

    sync_script = Path(__file__).parent.parent / "_tools" / "doc-sync" / "sync_docs.py"

    if not sync_script.exists():
        print(f"Error: Doc sync script not found at {sync_script}")
        sys.exit(1)

    # Build command
    cmd = [sys.executable, str(sync_script)]

    if args.init:
        cmd.append("--init")
    if args.status:
        cmd.append("--status")
    if args.add_source:
        cmd.extend(["--add-source", args.add_source])
    if args.source_name:
        cmd.extend(["--source-name", args.source_name])
    if args.force:
        cmd.append("--force")
    if args.verbose:
        cmd.append("-v")

    try:
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_schedule(args):
    """Schedule a recommendation or intent as a local-orchestrator agent."""
    from agent_factory import AgentFactory
    from orchestrator import CortexOrchestrator

    orchestrator = CortexOrchestrator(root_dir=Path(args.root))

    # Check if we are in "Team Provisioning" mode
    if args.team:
        # Determine intent: either explicit argument or from next recommendation
        intent = args.intent
        recommendation = None

        if not intent:
            # Fetch recommendation if no intent provided
            try:
                response = orchestrator.get_next_action(project_filter=args.project, limit=1)
                if response.next_action:
                    recommendation = response.next_action
                    intent = recommendation.action_title
            except Exception as e:
                print(f"Error fetching recommendation: {e}", file=sys.stderr)
                sys.exit(1)

        if not intent:
            print("Error: No intent provided and no active recommendation found.")
            print("Usage: cortex schedule 'Build X' --team")
            sys.exit(1)

        # Generate Team Configuration
        print(f"Provisioning Agent Team for: {intent}")
        try:
            yaml_content = AgentFactory.create_team_config(intent=intent)

            # Write to Drop Zone
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(cortex_dir.parent)))
            drop_zone = root_dir / "local-orchestrator" / "agents" / "dynamic"
            drop_zone.mkdir(parents=True, exist_ok=True)

            # Generate filename
            import re

            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", intent.lower())[:50]
            file_path = drop_zone / f"{safe_name}.json"

            file_path.write_text(yaml_content)
            print(f"✨ Team Configuration written to: {file_path}")
            print("   The Orchestrator should pick this up automatically.")

        except Exception as e:
            print(f"Error provisioning team: {e}", file=sys.stderr)
            sys.exit(1)

        return

    # Standard Schedule Logic (Single Function)
    # Get next recommendation
    try:
        if args.intent:
            print("Error: explicit intent only supported with --team flag currently.")
            sys.exit(1)

        response = orchestrator.get_next_action(project_filter=args.project, limit=1)

        if not response.next_action:
            print("No recommendations available to schedule.")
            return

        recommendation = response.next_action

        # Initialize internal engine
        engine = ExecutionEngine()
        adapter = RecommendationToAgentAdapter(engine)

        # Schedule the recommendation
        schedule = args.schedule or "0 8 * * *"  # Default: daily at 8 AM

        success = adapter.register_recommendation(recommendation, schedule)

        if success:
            title = getattr(
                recommendation,
                "title",
                getattr(recommendation, "action_title", "Unknown"),
            )
            rationale = getattr(recommendation, "rationale", None) or getattr(
                recommendation, "description", ""
            )
            print(f"✓ Scheduled: {title}")
            print(f"  Schedule: {schedule}")
            print(f"  Rationale: {rationale}")
        else:
            print("✗ Failed to schedule recommendation.")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_execute(args):
    """Execute a recommendation immediately."""
    from orchestrator import CortexOrchestrator

    from cortex.execution.adapter import RecommendationToAgentAdapter

    # Import internal orchestrator components
    from cortex.execution.engine import Orchestrator as ExecutionEngine

    orchestrator = CortexOrchestrator(root_dir=Path(args.root))
    feedback_logger = FeedbackLogger()

    try:
        # Get recommendations
        response = orchestrator.get_next_action(
            project_filter=args.project,
            limit=10,  # Get more to allow selection by index
        )

        # Combine next_action and alternatives for indexing
        all_recommendations = []
        if response.next_action:
            all_recommendations.append(response.next_action)
        all_recommendations.extend(response.alternative_actions)

        if not all_recommendations:
            print("No recommendations available to execute.")
            return

        # Determine which recommendation to execute
        if args.index is not None:
            # Execute by index (1-based)
            if args.index < 1 or args.index > len(all_recommendations):
                print(f"Error: Index {args.index} out of range (1-{len(all_recommendations)})")
                sys.exit(1)
            recommendation = all_recommendations[args.index - 1]
        elif args.id:
            # Execute by ID
            matching = [r for r in all_recommendations if r.id == args.id]
            if not matching:
                print(f"Error: No recommendation found with ID '{args.id}'")
                sys.exit(1)
            recommendation = matching[0]
        else:
            # Default: execute the top recommendation
            recommendation = all_recommendations[0]

        # Show what we're executing
        rec_type = getattr(recommendation, "type", "unknown")
        if hasattr(rec_type, "value"):
            rec_type = rec_type.value
        priority = recommendation.priority
        if isinstance(priority, int):
            priority_str = "high" if priority > 70 else "medium" if priority > 40 else "low"
        elif hasattr(priority, "value"):
            priority_str = priority.value
        else:
            priority_str = str(priority)
        rationale = getattr(recommendation, "rationale", None) or getattr(
            recommendation, "description", ""
        )
        print(f"Executing: {recommendation.title}")
        print(f"Type: {rec_type}")
        print(f"Priority: {priority_str}")
        print(f"Rationale: {rationale}")
        description = getattr(recommendation, "description", "")
        if description:
            print(f"\nActions:\n{description}")
        print("")

        # Initialize internal engine
        engine = ExecutionEngine()
        adapter = RecommendationToAgentAdapter(engine)

        print("Executing...")

        # Convert to agent and execute
        agent = adapter.to_agent(recommendation)
        engine.register_agent(agent)
        result = engine.trigger_agent(agent.agent_id, context={})

        # Display results
        if result.success:
            print("✓ Execution completed successfully")
            print(f"  Message: {result.message}")
            if result.data:
                print(f"  Details: {result.data}")

            # Log outcome to feedback system
            if not args.no_feedback:
                feedback_logger.log_outcome(
                    recommendation_id=recommendation.id,
                    recommendation_title=recommendation.title,
                    recommendation_type=recommendation.type,
                    priority=recommendation.priority,
                    confidence=recommendation.confidence,
                    followed=True,
                    outcome="success",
                    notes=result.message,
                    context={
                        "execution_time": result.execution_time,
                        "timestamp": (
                            result.timestamp.isoformat()
                            if hasattr(result.timestamp, "isoformat")
                            else str(result.timestamp)
                        ),
                        "data": result.data,
                    },
                )
                print("\n✓ Outcome logged to feedback system")
        else:
            print("✗ Execution failed")
            print(f"  Message: {result.message}")

            # Log failure to feedback system
            if not args.no_feedback:
                feedback_logger.log_outcome(
                    recommendation_id=recommendation.id,
                    recommendation_title=recommendation.title,
                    recommendation_type=recommendation.type,
                    priority=recommendation.priority,
                    confidence=recommendation.confidence,
                    followed=True,
                    outcome="failed",
                    notes=result.message,
                    context={"error": result.message},
                )
                print("\n✓ Failure logged to feedback system")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def cmd_orchestrate(args):
    """Orchestrate work: discover tasks, route to optimal models, and dispatch."""
    import json as _json

    try:
        from supervisor.intake import WorkIntake
        from supervisor.pipeline import run_pipeline
    except ImportError as e:
        print(f"Error: supervisor module not available: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        # Build work items from CLI task or discovery
        work_items = None
        if args.task:
            intake = WorkIntake()
            work_items = [
                intake.from_cli(args.task, project=args.project or "", priority=args.priority)
            ]

        # Run the full pipeline
        result = run_pipeline(
            work_items=work_items,
            dry_run=args.dry_run,
            project_filter=args.project if not args.task else None,
        )

        if not result.routing_decisions and not result.work_items:
            print("No pending work items found.")
            return

        # Display routing plan
        print("╔══════════════════════════════════════════════════════╗")
        print("║            CORTEX - ORCHESTRATION PLAN               ║")
        print("╚══════════════════════════════════════════════════════╝")
        print(f"\nItems found: {result.items_discovered}\n")

        for i, rd in enumerate(result.routing_decisions, 1):
            print(f"  [{i}] {rd.work_item.description[:80]}")
            proj = rd.work_item.project or "auto"
            pri = (
                rd.work_item.priority.value
                if hasattr(rd.work_item.priority, "value")
                else str(rd.work_item.priority)
            )
            print(f"      Project: {proj}  Priority: {pri}")
            print(
                f"      Model: {rd.model_tier} ({rd.model_id})  "
                f"Complexity: {rd.complexity_score:.2f}  Confidence: {rd.confidence:.2f}"
            )
            print()

        if result.dry_run:
            print("(dry run — routing plan only, no API calls)")

        if not result.dry_run and result.items_dispatched > 0:
            print(
                f"Dispatched: {result.items_dispatched} "
                f"(succeeded={result.items_succeeded}, failed={result.items_failed})"
            )

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for err in result.errors:
                print(f"  - {err}")

        if args.json:
            print(_json.dumps(result.to_dict(), indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def cmd_learn(args):
    """Show learning metrics and patterns."""
    if getattr(args, "pipeline", False):
        from intelligence.learning_telemetry import LearningTelemetry

        telemetry = LearningTelemetry()
        runs = telemetry.get_recent_runs(limit=5)
        print(telemetry.format_pipeline_ascii(runs))
        return

    learning = LearningSystem()

    try:
        metrics = learning.get_learning_metrics()

        print("╔══════════════════════════════════════════════════════╗")
        print("║              CORTEX - LEARNING METRICS               ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        # Overall metrics
        print("📊 OVERALL METRICS")
        print("────────────────")
        print(f"Total Outcomes: {metrics.total_outcomes}")
        print(f"Followed Recommendations: {metrics.followed_count}")
        if metrics.followed_count > 0:
            print(f"Success Rate: {metrics.success_rate:.1%}")
            print(f"Partial Success: {metrics.partial_rate:.1%}")
            print(f"Failed: {metrics.failed_rate:.1%}")
            print(f"Recommendation Accuracy: {metrics.recommendation_accuracy:.1%}")
        else:
            print("No outcomes tracked yet. Use feedback system to log outcomes.")
        print("")

        # Confidence calibration
        if metrics.confidence_calibration:
            print("🎯 CONFIDENCE CALIBRATION")
            print("────────────────")
            print("How well do confidence scores predict success?")
            print("")
            for bucket, success_rate in sorted(
                metrics.confidence_calibration.items(), reverse=True
            ):
                if success_rate > 0:
                    bar_length = int(success_rate * 20)
                    bar = "█" * bar_length + "░" * (20 - bar_length)
                    print(f"  {bucket}: {bar} {success_rate:.1%}")
            print("")

        # Outcome patterns by type
        if metrics.outcome_patterns:
            print("📈 OUTCOME PATTERNS BY TYPE")
            print("────────────────")
            print("Which recommendation types work best?")
            print("")

            # Sort by success rate
            sorted_patterns = sorted(
                metrics.outcome_patterns.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True,
            )

            for rec_type, pattern in sorted_patterns:
                if pattern["followed"] > 0:
                    print(f"  {rec_type}")
                    print(f"    Total: {pattern['total']}, Followed: {pattern['followed']}")
                    print(f"    Success Rate: {pattern['success_rate']:.1%}")
                    print(f"    Avg Confidence: {pattern['avg_confidence']:.2f}")
                    print("")
        else:
            print("💡 TIP")
            print("────────────────")
            print("No outcome patterns yet. Start tracking outcomes to enable learning!")
            print("")
            print("Log outcomes with:")
            print("  cortex feedback --outcome <success|partial|failed>")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_interactions(args):
    """Manage interaction learning system."""
    from engines.claude_session_absorber import ClaudeSessionSource
    from engines.interaction_learner import (
        InteractionLearner,
        process_interaction_queue,
    )

    learner = InteractionLearner()

    if args.process:
        # Process queued interactions
        result = process_interaction_queue()
        try:
            from intelligence.bandwidth.queue_slo import check_queue_slo

            queue_slo = check_queue_slo()
        except Exception:
            queue_slo = None
        print("╔══════════════════════════════════════════════════════╗")
        print("║        CORTEX - INTERACTION QUEUE PROCESSED          ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Interactions processed: {result.get('processed', 0)}")
        print(f"Implicit outcomes derived: {result.get('outcomes_derived', 0)}")
        print(f"Insights generated: {result.get('insights_generated', 0)}")
        print(f"Sessions analyzed: {result.get('sessions_analyzed', 0)}")
        if queue_slo:
            print(
                f"Queue SLO: {queue_slo.get('status')} (queue={queue_slo.get('queue_lines')}, processing={queue_slo.get('processing_lines')})"
            )
        return

    if args.patterns:
        # Show detected patterns
        source = ClaudeSessionSource()
        patterns = source.get_patterns(min_frequency=2)

        print("╔══════════════════════════════════════════════════════╗")
        print("║         CORTEX - INTERACTION PATTERNS                ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if not patterns:
            print("No patterns detected yet. Patterns emerge after repeated interactions.")
            return

        for pattern in patterns[:10]:
            print(f"🔄 {pattern.pattern_type}: {pattern.description}")
            print(f"   Frequency: {pattern.frequency} | Success Rate: {pattern.success_rate:.0%}")
            if pattern.projects:
                print(f"   Projects: {', '.join(pattern.projects[:3])}")
            print("")
        return

    if args.tools:
        # Show tool success rates
        source = ClaudeSessionSource()
        tool_rates = source.get_tool_success_rates()

        print("╔══════════════════════════════════════════════════════╗")
        print("║           CORTEX - TOOL SUCCESS RATES                ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if not tool_rates:
            print("No tool data collected yet.")
            return

        sorted_tools = sorted(tool_rates.items(), key=lambda x: x[1]["frequency"], reverse=True)
        for tool, rates in sorted_tools[:15]:
            bar_len = int(rates["success_rate"] * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {tool:15} {bar} {rates['success_rate']:.0%} ({rates['frequency']} uses)")
        return

    if args.setup:
        # Show hook setup instructions
        print("╔══════════════════════════════════════════════════════╗")
        print("║       CORTEX - INTERACTION CAPTURE SETUP             ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        print("Add the following to your Claude Code settings.json:")
        print("(Usually at ~/.claude/settings.json)")
        print("")
        print(
            """
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "python -m cortex.hooks.interaction_capture prompt"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "python -m cortex.hooks.interaction_capture tool_complete"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python -m cortex.hooks.interaction_capture stop"
      }]
    }],
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "python -m cortex.hooks.interaction_capture session_end"
      }]
    }]
  }
}
"""
        )
        print("After adding hooks, restart Claude Code to activate.")
        return

    # Default: show summary
    summary = learner.get_learning_summary(days=args.days)

    print("╔══════════════════════════════════════════════════════╗")
    print("║       CORTEX - INTERACTION LEARNING SUMMARY          ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")

    if "error" in summary:
        print(f"Error: {summary['error']}")
        return

    # Implicit feedback stats
    fb = summary.get("implicit_feedback", {})
    print(f"📊 IMPLICIT FEEDBACK (last {args.days} days)")
    print("────────────────")
    print(f"  Total prompts analyzed: {fb.get('total_prompts', 0)}")
    print(
        f"  Corrections detected: {fb.get('corrections', 0)} ({fb.get('correction_rate', 0):.1%})"
    )
    print(f"  Approvals detected: {fb.get('approvals', 0)} ({fb.get('approval_rate', 0):.1%})")
    print(f"  Implicit success signal: {fb.get('implicit_success_signal', 0.5):.1%}")
    print("")

    # Patterns
    patterns = summary.get("top_patterns", [])
    if patterns:
        print(f"🔄 TOP PATTERNS ({summary.get('detected_patterns', 0)} total)")
        print("────────────────")
        for p in patterns[:3]:
            print(f"  • {p.get('description', 'Unknown pattern')}")
        print("")

    # Learning state
    state = summary.get("learning_state", {})
    print("📈 LEARNING STATE")
    print("────────────────")
    print(f"  Total interactions processed: {state.get('total_processed', 0)}")
    print(f"  Implicit outcomes derived: {state.get('implicit_outcomes', 0)}")
    print(f"  Insights generated: {state.get('insights_generated', 0)}")
    if state.get("last_processed"):
        print(f"  Last processed: {state['last_processed']}")


def cmd_batch_status(args):
    """Display batch configuration"""
    from cortex.batch import BatchConfig

    print("╔══════════════════════════════════════════════════════╗")
    print("║         CORTEX - BATCH API CONFIGURATION             ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")
    print("Batch Processing Status:")
    print("────────────────")
    print(
        f"  Learning batch: {'✅ Enabled' if BatchConfig.is_batch_enabled('learning') else '❌ Disabled'}"
    )
    print(
        f"  Research batch: {'✅ Enabled' if BatchConfig.is_batch_enabled('research') else '❌ Disabled'}"
    )
    print(
        f"  Recommendations batch: {'✅ Enabled' if BatchConfig.is_batch_enabled('recommendations') else '❌ Disabled'}"
    )
    print("")
    print(f"Any batch enabled: {'✅ Yes' if BatchConfig.is_any_batch_enabled() else '❌ No'}")
    print("")
    print("  export CORTEX_BATCH_RECOMMENDATIONS_ENABLED=true")
    print("")


def cmd_notify(args):
    """Send notifications via Chief of Staff persona."""
    from cortex.notify import Notifier

    try:
        notifier = Notifier()
        channels = args.channel or ["terminal"]
        if "all" in channels:
            channels = ["terminal", "email"]

        message = ""
        title = "Cortex Update"
        context = {}

        # Determine content based on type
        if args.type == "morning":
            title = "Morning Briefing"
            print("Generating morning briefing...")
            briefing_data = generate_daily_briefing(Path(args.root))

            # Get executive summary for terminal/short message
            from briefing import format_briefing, get_executive_summary

            summary = get_executive_summary(briefing_data)

            # Full report for email
            full_report = format_briefing(briefing_data, use_color=False)
            # Convert newlines to HTML breaks for basic email formatting
            html_body = f"<pre>{full_report}</pre>"
            context["html_body"] = html_body

            # Use summary as the main message text
            message = summary
            if args.message:
                message = f"{args.message}\n\n{summary}"

        elif args.type == "evening":
            title = "Evening Status"
            # TODO: specialized evening report
            print("Generating evening status...")
            briefing_data = generate_daily_briefing(Path(args.root))
            from briefing import get_executive_summary

            summary = get_executive_summary(briefing_data)
            message = f"End of day status. {summary}"

        else:  # custom
            if not args.message:
                print("Error: --message required for custom notifications")
                sys.exit(1)
            message = args.message
            title = args.title or "Cortex Notification"

        print(f"Sending notification via {', '.join(channels)}...")
        print(f"Title: {title}")
        print(f"Message: {message}")

        results = notifier.notify(title, message, channels, context)

        # Report results
        for channel, success in results.items():
            icon = "✅" if success else "❌"
            print(f"{icon} {channel}: {'Sent' if success else 'Failed'}")

    except Exception as e:
        print(f"Error sending notification: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_dashboard(args):
    """Show Symbiosis Dashboard (Night Shift & Agents)."""
    from datetime import datetime

    # Import internal orchestrator components
    # Import internal orchestrator components
    # Assuming local-orchestrator is in path from main setup
    try:
        from batch_system import BatchManager
        from config import STORAGE_PATH
        from history import ExecutionHistory
    except ImportError:
        # Fallback: try adding local-orchestrator explicitly if not in path
        import sys

        root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path(__file__).parent.parent)))
        lo_dir = root_dir / "local-orchestrator"
        if str(lo_dir) not in sys.path:
            sys.path.insert(0, str(lo_dir))

        from batch_system import BatchManager
        from storage.history import ExecutionHistory

        # config might be module level in local-orchestrator
        try:
            from config import STORAGE_PATH
        except ImportError:
            # Define fallback or load from module
            STORAGE_PATH = "symbiotic.db"

    try:
        # Initialize directly
        # Fix: Ensure db_path is absolute to local-orchestrator directory
        # If STORAGE_PATH is just a filename, assume it is in local-orchestrator
        if not Path(STORAGE_PATH).is_absolute():
            # Find local-orchestrator dir
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path(__file__).parent.parent)))
            lo_dir = root_dir / "local-orchestrator"
            db_path = str(lo_dir / STORAGE_PATH)
        else:
            db_path = STORAGE_PATH

        batch_manager = BatchManager(db_path=db_path)
        history = ExecutionHistory(db_path=db_path)

        # Get stats
        try:
            # Check queue
            pending_all = batch_manager.get_pending_items(limit=1000)
            active_batches = batch_manager.get_active_batches()

            queue = {
                "pending": len(pending_all),
                "active_batches": len(active_batches),
                "batches": active_batches,
            }
        except Exception as e:
            queue = {"pending": 0, "active_batches": 0, "batches": [], "error": str(e)}

        try:
            recent = history.get_recent_executions(limit=10)
        except Exception as e:
            recent = []
            print(f"Warning: Could not fetch history: {e}")

    except Exception as e:
        print(f"Error initializing dashboard components: {e}")
        sys.exit(1)

    print("╔══════════════════════════════════════════════════════╗")
    print("║           SYMBIOSIS ENGINE STATUS                    ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")

    # 1. Night Shift Status
    print("🌙 NIGHT SHIFT (Batch System)")
    print("─────────────────────────────")
    pending = queue.get("pending", 0)
    active = queue.get("active_batches", 0)

    print(f"Queue Depth: {pending} items")
    print(f"Active Batches: {active}")

    if active > 0:
        print("\n  Active Batches:")
        for batch in queue.get("batches", []):
            batch_id = batch.get("batch_id") or batch.get("id")
            status = batch.get("status")
            print(f"  • {batch_id} ({status})")
    print("")

    # 2. Agent Activity
    print("🤖 AGENT ACTIVITY (Last 10 Runs)")
    print("──────────────────────────────")

    if not recent:
        print("No recent activity.")
    else:
        # Simple table
        print(f"{'AGENT':<25} {'STATUS':<10} {'TIME':<20} {'MESSAGE'}")
        print(f"{'-' * 25} {'-' * 10} {'-' * 20} {'-' * 15}")

        for run in recent:
            agent_id = run.get("agent_id", "unknown")
            # Shorten ID
            name = agent_id.replace("system_", "").replace("agent_", "")[:24]
            status = run.get("status", "unknown")
            status_icon = (
                "✅" if status == "completed" or status else "❌" if status == "failed" else "⏳"
            )

            # Timestamp formatting
            ts_str = run.get("timestamp", "")
            if isinstance(ts_str, datetime):
                time_val = ts_str.strftime("%H:%M:%S")
            else:
                try:
                    # Truncate parsing for simplicity if it is a string
                    if "T" in str(ts_str):
                        time_val = str(ts_str).split("T")[1].split(".")[0]
                    else:
                        time_val = str(ts_str)
                except (ValueError, IndexError, TypeError):
                    time_val = str(ts_str)[:8]

            msg = (
                run.get("message", "")[:30] + "..."
                if len(run.get("message", "")) > 30
                else run.get("message", "")
            )

            print(f"{name:<25} {status_icon} {status:<8} {time_val:<20} {msg}")
    print("")


def cmd_bandwidth(args):
    """Show bandwidth metrics and run experiments."""
    import json

    from intelligence.bandwidth.dashboard import get_dashboard_data, render_dashboard
    from intelligence.bandwidth.handoff_capture import WorkstreamType, capture_handoff
    from intelligence.bandwidth.predictions import (
        PredictionTracker,
        record_outcome,
        record_prediction,
    )

    action = getattr(args, "action", "dashboard")

    try:
        if action == "dashboard" or action is None:
            # Show dashboard
            if args.json:
                data = get_dashboard_data(project=args.project, days=args.days)
                print(json.dumps(data, indent=2))
            else:
                print(render_dashboard(project=args.project, days=args.days))

        elif action == "experiment":
            # Run bandwidth experiments
            from batch.bandwidth_experiments import BandwidthExperimentRunner

            runner = BandwidthExperimentRunner()

            if args.dry_run:
                runner.submit_all_experiments(dry_run=True)
            elif args.status:
                status = runner.get_experiment_status()
                print("╔════════════════════════════════════════════════════════╗")
                print("║          BANDWIDTH EXPERIMENTS STATUS                  ║")
                print("╚════════════════════════════════════════════════════════╝")
                print("")
                print(f"Total Tasks: {status['total_tasks']}")
                print(f"Completed: {status['completed']}")
                print(f"Running: {status['running']}")
                print(f"Failed: {status['failed']}")
                print(f"Pending: {status['pending']}")
                print(f"Progress: {status['progress_pct']:.0f}%")
            elif args.experiment_name:
                task_id = runner.submit_single_experiment(args.experiment_name)
                if task_id:
                    print(f"✓ Submitted experiment: {args.experiment_name}")
                    print(f"  Task ID: {task_id}")
                else:
                    print(f"✗ Unknown experiment: {args.experiment_name}")
            else:
                # Submit all experiments
                wave_tasks = runner.submit_all_experiments()
                print("✓ Submitted all bandwidth experiments")
                for wave_id, task_ids in wave_tasks.items():
                    print(f"  {wave_id}: {len(task_ids)} tasks")

        elif action == "record-prediction":
            # Record a new prediction
            prediction_id = args.prediction_id or f"pred_{int(datetime.now().timestamp())}"  # noqa: DTZ005
            prediction = record_prediction(
                prediction_id=prediction_id,
                confidence=args.confidence,
                domain=args.domain,
                description=args.description or "",
                source=args.source or os.environ.get("CORTEX_SOURCE", "cli"),
                session_id=args.session_id or os.environ.get("CORTEX_SESSION_ID", "unknown"),
            )
            print(f"✓ Recorded prediction: {prediction.prediction_id}")
            print(f"  Domain: {prediction.domain}")
            print(f"  Confidence: {prediction.confidence:.0%}")
            print(f"  Source: {prediction.source}")
            print(f"  Session: {prediction.session_id}")

        elif action == "record-outcome":
            # Record outcome for a prediction
            was_correct = args.outcome.lower() in ["true", "yes", "1", "correct"]
            result = record_outcome(args.prediction_id, was_correct)
            if result:
                print(f"✓ Recorded outcome for: {args.prediction_id}")
                print(f"  Correct: {was_correct}")
            else:
                print(f"✗ Prediction not found: {args.prediction_id}")

        elif action == "calibration":
            # Show calibration data
            tracker = PredictionTracker()
            calibrations = tracker.get_calibration(domain=args.domain)

            print("╔════════════════════════════════════════════════════════╗")
            print("║            TRUST CALIBRATION BY DOMAIN                 ║")
            print("╚════════════════════════════════════════════════════════╝")
            print("")

            for domain, cal in calibrations.items():
                if cal.total == 0:
                    print(f"{domain:15s}: No data yet")
                else:
                    filled = int(cal.calibrated_confidence * 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    print(
                        f"{domain:15s}: {bar} {cal.calibrated_confidence * 100:.0f}% ({cal.total} outcomes)"
                    )

        elif action == "capture":
            # Capture a session handoff
            workstream = (
                WorkstreamType(args.workstream) if args.workstream else WorkstreamType.BUILDING
            )
            handoff = capture_handoff(
                project=args.project or "cortex",
                active_task=args.task or "Unknown task",
                workstream=workstream,
                next_action=args.next_action or "",
            )
            print("✓ Captured session handoff")
            print(f"  Project: {handoff.project}")
            print(f"  Task: {handoff.active_task}")
            print(f"  Workstream: {handoff.workstream.value}")

        elif action == "queue-slo":
            from intelligence.bandwidth.queue_slo import check_queue_slo

            status = check_queue_slo()
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print(f"Queue SLO: {status['status']} (total={status['total_lines']})")

        elif action == "baseline":
            from intelligence.bandwidth.baseline_report import generate_baseline_report

            output_dir = Path.home() / ".cortex" / "research" / "bandwidth" / "reports"
            report = generate_baseline_report(
                output_dir=output_dir, project=args.project, days=args.days
            )
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print("✓ Baseline report generated")
                print(f"  Output: {output_dir / 'baseline_report.json'}")

        else:
            print(f"Unknown action: {action}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Deep Mode Commands (Phase 1 Integration)
# ============================================================================


def cmd_deep(args):
    """Run comprehensive deep analysis."""
    if not DEEP_MODE_AVAILABLE:
        print("❌ Deep mode not available (missing dependencies)")
        print("   Install: pip install -r requirements.txt")
        sys.exit(1)

    try:
        bridge = CortexBridge(root_dir=Path(args.root))

        # Run deep analysis
        result = bridge.analyze_deep(project=args.project, output_json=args.json)

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            display_error(result["error"])
            sys.exit(1)

        # Display results
        display_deep_intelligence(result, verbose=args.verbose, json_output=args.json)

    except Exception as e:
        display_error(f"Deep analysis failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def cmd_quick(args):
    """Run minimal fast analysis."""
    if not DEEP_MODE_AVAILABLE:
        print("❌ Quick mode not available (missing dependencies)")
        sys.exit(1)

    try:
        bridge = CortexBridge(root_dir=Path(args.root))

        # Run quick analysis
        result = bridge.analyze_quick(project=args.project)

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            # Quick mode is opt-in and may not be fully implemented
            # Show friendly message and suggest deep mode instead
            print("\n⚠️  Quick mode not yet fully implemented")
            print(f"   Error: {result['error']}\n")
            print("💡 Suggestion: Use 'cortex deep' for comprehensive analysis")
            print("   (Deep mode is only 2-5s and provides much more context)\n")
            sys.exit(0)  # Not a failure - just not implemented yet

        # Display results
        display_quick_intelligence(result)

    except Exception as e:
        # Catch any unexpected errors
        print("\n⚠️  Quick mode encountered an error")
        print(f"   {e}\n")
        print("💡 Suggestion: Use 'cortex deep' for comprehensive analysis\n")
        sys.exit(0)  # Not a failure - just not implemented yet


def cmd_auto(args):
    """Run adaptive analysis with intelligent mode selection."""
    if not DEEP_MODE_AVAILABLE:
        print("❌ Auto mode not available (missing dependencies)")
        sys.exit(1)

    try:
        bridge = CortexBridge(root_dir=Path(args.root))

        # Run auto analysis
        result = bridge.analyze_auto(project=args.project)

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            display_error(result["error"])
            sys.exit(1)

        # Display results (auto returns either deep or quick result)
        if hasattr(result, "mode"):
            # Deep result
            display_deep_intelligence(result, verbose=args.verbose, json_output=False)
        else:
            # Quick result
            display_quick_intelligence(result)

    except Exception as e:
        display_error(f"Auto analysis failed: {e}")
        sys.exit(1)


def cmd_config(args):
    """Manage deep mode configuration."""
    if not DEEP_MODE_AVAILABLE:
        print("❌ Config not available (missing dependencies)")
        sys.exit(1)

    try:
        bridge = CortexBridge(root_dir=Path(args.root))

        if args.show:
            # Show current configuration
            preferences = bridge.latency_manager.preferences
            print("\n" + "=" * 60)
            print("Cortex Deep Mode Configuration")
            print("=" * 60 + "\n")

            default_mode = preferences.get("default_mode", "deep")
            print(f"Default Mode: {default_mode.upper()}")

            # Project overrides
            overrides = preferences.get("project_overrides", {})
            if overrides:
                print("\nProject Overrides:")
                for proj, mode in overrides.items():
                    print(f"  {proj}: {mode}")

            print("\nDeep Mode Config:")
            print(f"  - Git days: {DEEP_MODE.git_days}")
            print(f"  - Spec search: {'enabled' if DEEP_MODE.spec_search_enabled else 'disabled'}")
            print(
                f"  - Pattern matching: {'semantic' if DEEP_MODE.pattern_semantic else 'keyword'}"
            )
            print(f"  - Model: {DEEP_MODE.model}")
            print(f"  - Expected latency: ~{DEEP_MODE.expected_latency_ms / 1000:.1f}s")

            print("\nFast Mode Config:")
            print(f"  - Git days: {FAST_MODE.git_days}")
            print("  - Spec search: disabled")
            print(f"  - Model: {FAST_MODE.model}")
            print(f"  - Expected latency: ~{FAST_MODE.expected_latency_ms / 1000:.1f}s")
            print()

        elif args.set_default:
            # Set default mode
            mode = args.set_default.lower()
            if mode not in ["deep", "fast", "auto"]:
                print(f"❌ Invalid mode: {mode}")
                print("   Valid options: deep, fast, auto")
                sys.exit(1)

            # Update configuration
            bridge.latency_manager.preferences["default_mode"] = mode
            bridge.latency_manager._save_preferences()
            print(f"✅ Default mode set to: {mode.upper()}")
            print(f"   Saved to: {bridge.latency_manager.preference_file}")

        else:
            # Show help
            print("\nUsage: cortex config [OPTIONS]")
            print("\nOptions:")
            print("  --show           Show current configuration")
            print("  --set-default    Set default analysis mode (deep/fast/auto)")
            print()

    except Exception as e:
        display_error(f"Config failed: {e}")
        sys.exit(1)


def cmd_tooling(args):
    """Show Claude Code tooling intelligence."""
    try:
        from engines.tooling_tracker import get_tracker

        tracker = get_tracker()

        # Handle query argument
        if args.query:
            result = tracker.query(args.query)
            print(result)
            return

        # Handle specific commands
        if args.action == "config":
            config = tracker.get_hook_config()
            print("╔════════════════════════════════════════════════════╗")
            print("║         CLAUDE CODE HOOK CONFIGURATION            ║")
            print("╚════════════════════════════════════════════════════╝")
            print()
            for event_type, hooks in config.items():
                print(f"  {event_type}:")
                if hooks:
                    for hook in hooks:
                        print(f"    • {hook}")
                else:
                    print("    (none)")
                print()

        elif args.action == "commands":
            snapshot = tracker.get_current_snapshot()
            print("╔════════════════════════════════════════════════════╗")
            print("║         AVAILABLE SLASH COMMANDS                   ║")
            print("╚════════════════════════════════════════════════════╝")
            print()
            print(f"Total: {len(snapshot.commands)} commands")
            print()
            for i, cmd in enumerate(snapshot.commands, 1):
                print(f"  {i:2}. /{cmd}")
                if i % 20 == 0 and i < len(snapshot.commands):
                    print()

        elif args.action == "changes":
            days = args.days or 7
            changes = tracker.get_recent_changes(days=days)
            print("╔════════════════════════════════════════════════════╗")
            print(f"║    TOOLING CHANGES (LAST {days} DAYS)                    ║")
            print("╚════════════════════════════════════════════════════╝")
            print()
            if not changes:
                print("  No tooling changes found.")
            else:
                for change in changes[:20]:  # Limit to 20
                    timestamp = datetime.fromisoformat(change.timestamp)
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M")
                    print(
                        f"  [{time_str}] {change.change_type:8} {change.category:10} {change.name}"
                    )

        elif args.action == "summary":
            print(tracker.get_intelligence_summary())

        else:
            # Default: show summary
            print(tracker.get_intelligence_summary())

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def cmd_intelligence(args):
    """Query Cortex intelligence for context, patterns, and recommendations."""
    try:
        from bridge import CortexBridge
    except ImportError:
        print("Error: CortexBridge not available", file=sys.stderr)
        sys.exit(1)

    try:
        bridge = CortexBridge()
        result = bridge.query_intelligence(
            request=args.query,
            project=args.project or "",
            query_type=args.type or "spec",
        )

        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        print("╔══════════════════════════════════════════════════════╗")
        print("║          CORTEX - INTELLIGENCE QUERY                 ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        # Overall confidence
        confidence = result.get("overall_confidence", 0)
        print(f"Confidence: {confidence:.0%}")
        if result.get("reasoning"):
            print(f"Reasoning: {result['reasoning']}")
        print("")

        # Similar work / related patterns
        related = result.get("related_patterns", [])
        if related:
            print("📎 RELATED PATTERNS")
            print("────────────────")
            for pattern in related:
                score = pattern.get("score", 0)
                print(f"  [{score:.0%}] {pattern.get('title', 'Unknown')}")
                if pattern.get("description"):
                    print(f"       {pattern['description'][:80]}")
            print("")

        # Anti-patterns
        anti_patterns = result.get("anti_patterns", [])
        if anti_patterns:
            print("⚠️  ANTI-PATTERNS")
            print("────────────────")
            for ap in anti_patterns:
                if isinstance(ap, dict):
                    print(f"  - {ap.get('pattern', ap.get('title', str(ap)))}")
                else:
                    print(f"  - {ap}")
            print("")

        # Recommendations
        recommendations = result.get("recommendations", [])
        if recommendations:
            print("💡 RECOMMENDATIONS")
            print("────────────────")
            for rec in recommendations:
                if isinstance(rec, dict):
                    print(f"  - {rec.get('title', rec.get('recommendation', str(rec)))}")
                else:
                    print(f"  - {rec}")
            print("")

        # Results
        results = result.get("results", [])
        if results:
            print("📄 RESULTS")
            print("────────────────")
            for r in results[:5]:
                if isinstance(r, dict):
                    title = r.get("title", r.get("source", "Result"))
                    relevance = r.get("relevance", r.get("score", 0))
                    print(f"  [{relevance:.0%}] {title}")
                    content = r.get("content", r.get("snippet", ""))
                    if content:
                        print(f"       {str(content)[:100]}")
                else:
                    print(f"  - {r}")
            print("")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_portfolio(args):
    """Portfolio commands: patterns, switching cost."""
    try:
        from portfolio_memory import PortfolioMemory
    except ImportError:
        print("Error: PortfolioMemory not available", file=sys.stderr)
        sys.exit(1)

    try:
        memory = PortfolioMemory()

        if getattr(args, "switching_cost", False):
            # Show context-switching cost analysis
            print("╔══════════════════════════════════════════════════════╗")
            print("║        CORTEX - CONTEXT SWITCHING COST               ║")
            print("╚══════════════════════════════════════════════════════╝")
            print("")

            # Use session data if available
            try:
                from intelligence.session_manager import SessionManager

                sm = SessionManager()
                ctx = sm.load_session_context()
                if ctx and hasattr(ctx, "project_switches"):
                    switches = ctx.project_switches
                else:
                    switches = 0
            except Exception:
                switches = 0

            from hooks.switch_tracker import SwitchTracker

            tracker = SwitchTracker()
            sstats = tracker.get_stats()

            print("📊 SWITCHING COST METRICS")
            print("────────────────")
            if sstats.enough_data:
                print(f"  Avg tokens/switch (with Cortex):    {sstats.avg_with_cortex:,}")
                print(f"  Avg tokens/switch (without Cortex): {sstats.avg_without_cortex:,}")
                print(f"  Savings per switch:                 {sstats.savings_per_switch:,} tokens")
            else:
                print(f"  Collecting data... {sstats.total_switches}/10 switches recorded")
                print("  Switches are tracked automatically across sessions.")
                if sstats.total_switches > 0:
                    print(
                        f"  Preliminary avg savings: ~{sstats.savings_per_switch:,} tokens/switch"
                    )
            print("")

            if switches > 0:
                print(f"  Session switches detected: {switches}")
                if sstats.enough_data:
                    print(
                        f"  Estimated session savings: {switches * sstats.savings_per_switch:,} tokens"
                    )
            print("")

            # Portfolio stats
            stats = memory.get_stats(include_health=False)
            total = stats.get("total_projects", 0)
            active_val = stats.get("active_projects", [])
            active = len(active_val) if isinstance(active_val, list) else int(active_val)
            if total > 0:
                print(f"  Portfolio: {active} active / {total} total projects")
                print(f"  Estimated daily switches: ~{active * 2}")
                print(
                    f"  Estimated daily savings:  ~{active * 2 * sstats.savings_per_switch:,} tokens"
                )
            print("")
            return

        # Default: show cross-project patterns
        patterns = memory.get_cross_project_patterns()

        print("╔══════════════════════════════════════════════════════╗")
        print("║       CORTEX - CROSS-PROJECT PATTERNS                ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if not patterns:
            print("No cross-project patterns found.")
            print("Patterns are detected from portfolio project_index.json")
            return

        # Get all project names for propagation check
        all_projects = set(memory.portfolio_data.get("projects", {}).keys())

        for pattern in patterns:
            name = pattern.get("pattern", "Unknown")
            count = pattern.get("count", 0)
            used_in = pattern.get("used_in", [])
            project_names = {p.get("project") for p in used_in}

            print(f"  {name} (used in {count} projects)")
            for proj in used_in:
                print(f"    ✅ {proj.get('project')} [{proj.get('priority', 'tier3')}]")

            # Propagation: show which projects DON'T have this pattern
            if getattr(args, "propagate", False):
                missing = all_projects - project_names
                if missing:
                    for m in sorted(missing):
                        print(f"    ❌ {m} (missing)")
            print("")

        print(f"Total patterns: {len(patterns)}")
        if not getattr(args, "propagate", False):
            print("Use --propagate to see which projects are missing patterns")
        print("")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_deps(args):
    """Dependency analysis for projects."""
    try:
        from bridge import CortexBridge
    except ImportError:
        print("Error: CortexBridge not available", file=sys.stderr)
        sys.exit(1)

    try:
        bridge = CortexBridge()

        if getattr(args, "cross_project", False) or not args.project:
            # Portfolio-wide dependency analysis
            result = bridge.analyze_portfolio_dependencies(project_filter=args.project)

            if "error" in result:
                print(f"Error: {result['error']}", file=sys.stderr)
                sys.exit(1)

            print("╔══════════════════════════════════════════════════════╗")
            print("║       CORTEX - PORTFOLIO DEPENDENCY ANALYSIS         ║")
            print("╚══════════════════════════════════════════════════════╝")
            print("")

            projects_analyzed = result.get("projects_analyzed", [])
            print(f"Projects analyzed: {len(projects_analyzed)}")
            print("")

            # Shared dependencies
            shared = result.get("shared_dependencies", [])
            if shared:
                print("📦 SHARED DEPENDENCIES")
                print("────────────────")
                for dep in shared[:15]:
                    if isinstance(dep, dict):
                        name = dep.get("name", str(dep))
                        projects = dep.get("projects", [])
                        print(f"  {name}: {', '.join(projects[:5])}")
                    else:
                        print(f"  {dep}")
                print("")

            # Version drift
            drift = result.get("version_drift", [])
            if drift:
                print("⚠️  VERSION DRIFT")
                print("────────────────")
                for d in drift[:10]:
                    if isinstance(d, dict):
                        print(f"  {d.get('dependency', 'Unknown')}: {d.get('versions', {})}")
                    else:
                        print(f"  {d}")
                print("")

            # Circular dependencies
            circular = result.get("circular_dependencies", [])
            if circular:
                print("🔄 CIRCULAR DEPENDENCIES")
                print("────────────────")
                for c in circular:
                    print(f"  {c}")
                print("")

        else:
            # Single project
            result = bridge.get_dependency_analysis(args.project)

            if "error" in result:
                print(f"Error: {result['error']}", file=sys.stderr)
                sys.exit(1)

            print("╔══════════════════════════════════════════════════════╗")
            print(f"║  CORTEX - DEPS: {args.project:<38}║")
            print("╚══════════════════════════════════════════════════════╝")
            print("")

            # External deps
            external = result.get("external_deps", result.get("dependencies", []))
            if external:
                print("📦 EXTERNAL DEPENDENCIES")
                print("────────────────")
                for dep in external[:20]:
                    if isinstance(dep, dict):
                        print(f"  {dep.get('name', 'Unknown')} {dep.get('version', '')}")
                    else:
                        print(f"  {dep}")
                print("")

            # Internal deps
            internal = result.get("internal_deps", [])
            if internal:
                print("🔗 INTERNAL DEPENDENCIES")
                print("────────────────")
                for dep in internal[:10]:
                    print(f"  {dep}")
                print("")

            # Health score
            health = result.get("health_score")
            if health is not None:
                print(f"Health Score: {health}/100")
                print("")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_watch(args):
    """Watch command - list, run, and manage scheduled verification tasks."""
    try:
        from watches import (
            format_results as format_watch_results,
            list_completed,
            list_pending,
            run_watch,
        )
    except ImportError:
        print("Error: watches module not available", file=sys.stderr)
        sys.exit(1)

    try:
        if getattr(args, "autonomous", False):
            # Dry-run: show what autonomous mode would do
            pending = list_pending()
            print("╔══════════════════════════════════════════════════════╗")
            print("║         CORTEX - WATCH (AUTONOMOUS PREVIEW)          ║")
            print("╚══════════════════════════════════════════════════════╝")
            print("")

            if not pending:
                print("No pending watches. Nothing for autonomous mode to do.")
            else:
                print(f"Autonomous mode would process {len(pending)} watches:")
                print("")
                for w in pending:
                    print(f"  📋 {w.get('name', 'Unknown')}")
                    print(f"     Script: {w.get('script', 'N/A')}")
                    print(f"     Run after: {w.get('run_after', 'N/A')}")
                    print(f"     Context: {w.get('context', '')[:60]}")
                    criteria = w.get("criteria", {})
                    if criteria:
                        print(f"     Criteria: {json.dumps(criteria)}")
                    print("")
            return

        # Default: list pending and recently completed, optionally run
        pending = list_pending()
        completed = list_completed(hours=24)

        print("╔══════════════════════════════════════════════════════╗")
        print("║             CORTEX - WATCH STATUS                    ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if pending:
            print(f"📋 PENDING ({len(pending)})")
            print("────────────────")
            for w in pending:
                print(f"  {w.get('name', 'Unknown')} — {w.get('context', '')[:50]}")
                print(f"    Run after: {w.get('run_after', 'N/A')}")
            print("")

            # Run pending watches if --run flag
            if getattr(args, "run", False):
                from pathlib import Path as WatchPath

                watches_dir = WatchPath.home() / ".cortex" / "watches" / "pending"
                results = []
                for watch_file in sorted(watches_dir.glob("*.json")):
                    result = run_watch(watch_file)
                    if result.get("status") != "skipped":
                        results.append(result)
                if results:
                    print("🔄 RUN RESULTS")
                    print("────────────────")
                    print(format_watch_results(results))
                else:
                    print("No watches were ready to run (check run_after times).")
                print("")
        else:
            print("No pending watches.")
            print("")

        if completed:
            print(f"✅ RECENTLY COMPLETED ({len(completed)})")
            print("────────────────")
            for w in completed:
                status = w.get("status", "unknown")
                icon = "PASS" if status == "pass" else "FAIL"
                print(f"  [{icon}] {w.get('name', 'Unknown')} — {w.get('context', '')[:50]}")
            print("")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_batch_fill(args):
    """Fill overnight batch queue intelligently."""
    try:
        from batch.intelligent_orchestrator import IntelligentBatchOrchestrator
    except ImportError:
        print("Error: IntelligentBatchOrchestrator not available", file=sys.stderr)
        sys.exit(1)

    try:
        orchestrator = IntelligentBatchOrchestrator()
        jobs = orchestrator.fill_overnight_queue(max_jobs=getattr(args, "max_jobs", None))

        print("╔══════════════════════════════════════════════════════╗")
        print("║       CORTEX - OVERNIGHT BATCH QUEUE FILL            ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")

        if not jobs:
            print("No jobs to queue. All work is up to date.")
            return

        total_tokens = 0
        print(f"Queued {len(jobs)} jobs:")
        print("")

        for i, job in enumerate(jobs, 1):
            description = getattr(job, "description", str(job))
            tokens = getattr(job, "total_tokens", 0)
            priority = getattr(job, "priority_score", 0)
            total_tokens += tokens

            print(f"  [{i}] {description}")
            print(f"      Tokens: {tokens:,} | Priority: {priority:.1f}")

        print("")
        print(f"Total tokens: {total_tokens:,}")

        # Estimate savings (batch API is ~50% cheaper)
        estimated_cost = total_tokens * 3.0 / 1_000_000  # ~$3/MTok average
        batch_cost = estimated_cost * 0.5
        savings = estimated_cost - batch_cost
        print(f"Estimated cost: ${batch_cost:.2f} (saving ~${savings:.2f} vs interactive)")
        print("")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


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

    # Setup wizard command
    setup_parser = subparsers.add_parser(
        "setup", help="Interactive setup wizard for new users"
    )
    setup_parser.add_argument(
        "--non-interactive", action="store_true",
        help="Accept defaults, prompt only for essentials"
    )
    setup_parser.set_defaults(func=cmd_setup)

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

    def cmd_import_claude(args):
        """Import learning data from Claude Code (~/.claude/)."""
        try:
            from intelligence.claude_code_importer import ClaudeCodeImporter

            importer = ClaudeCodeImporter()
            print("Importing learning data from Claude Code...")
            results = importer.import_all()

            if "error" in results:
                print(f"Error: {results['error']}")
                sys.exit(1)

            print()
            for source, result in results.items():
                status = result.get("status", "unknown")
                if status == "imported":
                    detail = ", ".join(
                        f"{k}={v}"
                        for k, v in result.items()
                        if k != "status"
                    )
                    print(f"  [OK] {source}: {detail}")
                elif status == "skipped":
                    print(f"  [--] {source}: {result.get('reason', 'skipped')}")
                else:
                    print(f"  [!!] {source}: {result.get('reason', status)}")

            print()
            print("Import complete. Data stored in ~/.cortex/imported/")
        except ImportError:
            print("Error: Claude Code importer not available", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def cmd_optimize_data(args):
        """Consolidate outcome stores, add indices, migrate legacy data."""
        print("Optimizing Cortex data stores...")
        print()

        # 1. Add missing indices to existing databases
        try:
            from intelligence.storage.add_missing_indices import add_missing_indices

            idx_results = add_missing_indices()
            print("[1/3] Adding missing indices:")
            for db, indices in idx_results.items():
                print(f"  {db}: {len(indices)} indices verified")
        except Exception as e:
            print(f"  Error adding indices: {e}")

        print()

        # 2. Initialize consolidated store
        try:
            from intelligence.storage.consolidated_store import get_consolidated_store

            store = get_consolidated_store()
            info = store.get_storage_info()
            print(f"[2/3] Consolidated store initialized: {info['db_path']}")
            print(f"  Schema version: {info['schema_version']}")
        except Exception as e:
            print(f"  Error initializing store: {e}")

        print()

        # 3. Migrate legacy data
        try:
            from intelligence.storage.consolidated_store import get_consolidated_store

            store = get_consolidated_store()
            counts = store.migrate_legacy_data()
            print("[3/3] Legacy data migration:")
            if counts:
                for source, count in counts.items():
                    print(f"  {source}: {count} records migrated")
            else:
                print("  No legacy data to migrate")
        except Exception as e:
            print(f"  Error migrating data: {e}")

        print()
        print("Data optimization complete.")

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

    # Import Claude Code data
    import_claude_parser = subparsers.add_parser(
        "import-claude", help="Import learning data from Claude Code (~/.claude/)"
    )
    import_claude_parser.set_defaults(func=cmd_import_claude)

    # Optimize data stores
    optimize_data_parser = subparsers.add_parser(
        "optimize-data",
        help="Consolidate outcome stores, add indices, migrate legacy data",
    )
    optimize_data_parser.set_defaults(func=cmd_optimize_data)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Wrap command execution with metrics tracking
    _execute_with_metrics(args)


def _execute_with_metrics(args):
    """Execute CLI command with performance tracking and session cleanup."""
    import time

    command_name = getattr(args, "command", "unknown") or "unknown"
    start = time.monotonic()
    success = True
    error_msg = None

    try:
        args.func(args)
    except SystemExit as e:
        if e.code and e.code != 0:
            success = False
            error_msg = f"exit code {e.code}"
        raise
    except Exception as e:
        success = False
        error_msg = str(e)[:200]
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        try:
            from intelligence.storage.consolidated_store import get_consolidated_store

            store = get_consolidated_store()
            store.log_command_metric(
                command=command_name,
                duration_ms=round(duration_ms, 1),
                success=success,
                error_message=error_msg,
            )
        except Exception:
            pass  # Never let metrics break the CLI

        # End session: flush implicit feedback + memory consolidation
        try:
            from bridge import CortexBridge

            bridge = CortexBridge.__dict__.get("_singleton")
            if bridge:
                bridge.end_session()
        except Exception:
            pass


if __name__ == "__main__":
    main()
