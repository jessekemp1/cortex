"""Core commands: next, init, status, health."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Union

from formatter import CortexFormatter
from orchestrator import CortexOrchestrator


def cmd_next(args):
    """Get next action."""
    # Import helpers lazily to avoid circular dependency
    from cli.commands._helpers import get_model_recommendation

    # Deep mode imports
    try:
        from intelligence.model_selection import ContextAwareModelRecommender, OrchestrationContext

        MODEL_SELECTION_AVAILABLE = True
    except ImportError:
        MODEL_SELECTION_AVAILABLE = False

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


def cmd_status(args):
    """Show intelligent strategic status."""
    from cli.commands._helpers import (
        _get_root_signal_quality,
        _portfolio_counts_from_scanner,
        _goal_counts_from_parser,
    )
    import logging

    logger = logging.getLogger(__name__)

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
        active = state.get("active_projects", 0)
        total = state.get("total_projects", 0)
        scanner_counts = _portfolio_counts_from_scanner(root)
        if scanner_counts is not None:
            active, total = scanner_counts
        else:
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

            orchestration_anomalies = anomaly_manager.detect_all(
                context={
                    "active_projects": active,
                    "total_projects": total,
                    "goals_in_progress": in_progress,
                    "goals_pending": pending,
                }
            )

            for anomaly in orchestration_anomalies:
                if anomaly.severity.value.lower() in ["critical", "warning"]:
                    severity_icon = "🔴" if anomaly.severity.value.lower() == "critical" else "🟡"
                    anomalies.append(f"{severity_icon} {anomaly.title}")

        except Exception as e:
            logger.debug(f"Anomaly detector failed: {e}")
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
