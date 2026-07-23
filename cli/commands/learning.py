"""Learning commands: feedback, learn, interactions."""

import sys
from pathlib import Path

from feedback import FeedbackLogger
from learning import LearningSystem
from orchestrator import CortexOrchestrator


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
        print(
            f"  Human-confirmed: {metrics.human_confirmed}"
            f"  |  Auto-confirmed: {metrics.auto_confirmed} (throughput, not validated)"
        )
        print(f"Followed Recommendations: {metrics.followed_count}")
        if metrics.followed_count > 0:
            if metrics.human_confirmed > 0:
                print(f"Human-Confirmed Success Rate: {metrics.human_success_rate:.1%}")
            else:
                print("Human-Confirmed Success Rate: n/a (no human feedback yet)")
            print(f"All-Outcome Success Rate: {metrics.success_rate:.1%} (incl. auto)")
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
