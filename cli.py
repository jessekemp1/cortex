#!/usr/bin/env python3
"""
Cortex CLI - Command-line interface for strategic orchestrator

Usage:
    cortex next [PROJECT] [--with-context] [--json]
    cortex status
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add cortex directory and its parent to path to support both module and direct execution
cortex_dir = Path(__file__).parent
sys.path.insert(0, str(cortex_dir))
sys.path.insert(0, str(cortex_dir.parent))

# Fallback: Add user site-packages if dependencies are missing (e.g. structlog)
site_packages = Path.home() / "Library/Python/3.9/lib/python/site-packages"
if site_packages.exists() and str(site_packages) not in sys.path:
    sys.path.append(str(site_packages))

from formatter import CortexFormatter

from briefing import format_briefing, format_briefing_json, generate_daily_briefing
from feedback import FeedbackLogger

from learning import LearningSystem
from orchestrator import CortexOrchestrator


def cmd_next(args):
    """Get next action."""
    orchestrator = CortexOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(
            project_filter=args.project,
            include_context=args.with_context,
            limit=args.limit,
        )

        formatter = CortexFormatter()
        output = formatter.format_response(response, json_output=args.json)
        print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show current state summary."""
    orchestrator = CortexOrchestrator(root_dir=Path(args.root))

    try:
        response = orchestrator.get_next_action(
            limit=0
        )  # Just get state, no recommendations

        state = response.current_state
        health = response.system_health

        print("╔══════════════════════════════════════════════════════╗")
        print("║              CORTEX - CURRENT STATE                  ║")
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


def cmd_context(args):
    """Preview context injection output."""
    import time

    try:
        from intelligence.context_injector import ContextInjector

        # Get root directory
        root_dir = Path(args.root)
        injector = ContextInjector(root_dir)

        # Get current working directory and optional task
        cwd = Path.cwd()
        task = args.task or ""

        # Time the injection
        start = time.time()
        context = injector.inject(cwd, task)
        elapsed = (time.time() - start) * 1000

        # Display results
        print("╔══════════════════════════════════════════════════════╗")
        print("║          CORTEX - CONTEXT PREVIEW                    ║")
        print("╚══════════════════════════════════════════════════════╝")
        print("")
        print("<cortex_context>")
        print(context)
        print("</cortex_context>")
        print("")
        print(f"Length: {len(context)} chars (target: 200-400)")
        print(f"Time: {elapsed:.1f}ms (limit: 500ms)")

        # Status indicators
        if len(context) < 200:
            print("⚠️  Context shorter than target (200 chars)")
        elif len(context) > 400:
            print("⚠️  Context longer than target (400 chars)")
        else:
            print("✅ Context length within target range")

        if elapsed > 500:
            print("⚠️  Injection time exceeded budget (500ms)")
        else:
            print("✅ Injection time within budget")

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
            print(
                "Run 'cortex next' or 'cortex briefing' first to get recommendations."
            )
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
        logger.log_outcome(
            recommendation_id=rec.id,
            recommendation_title=rec.title,
            recommendation_type=rec.type,
            priority=(
                rec.priority.upper()[0] if rec.priority else "B"
            ),  # Convert "high" -> "A", etc.
            confidence=rec.confidence,
            followed=True,  # Assume followed if providing feedback
            outcome=args.outcome,
            notes=args.notes,
            context={"projects": rec.related_projects, "goals": rec.related_goals},
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
        useful = (
            args.useful.lower() in ["yes", "y", "true", "1"] if args.useful else None
        )

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

        print(
            f"✓ Feedback logged: {action_title} - {'Useful' if useful else 'Not Useful'}"
        )


def cmd_health(args):
    """Show system health check (Golden Spec: Dependency Transparency)."""
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
        overall = (
            "✅ All Systems Operational" if health.all_active else "⚠️  Degraded Mode"
        )
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
    try:
        # Generate briefing
        briefing = generate_daily_briefing(root_dir=Path(args.root))

        # Format output
        if args.format == "json":
            output = format_briefing_json(briefing)
        else:
            output = format_briefing(briefing, use_color=not args.no_color)

        print(output)

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
                response = orchestrator.get_next_action(
                    project_filter=args.project, limit=1
                )
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
            # Locate local-orchestrator relative to cortex (assuming sibling directories in Dev)
            # cortex_dir is /Users/jesse.kemp/Dev/cortex
            dev_dir = cortex_dir.parent
            drop_zone = dev_dir / "local-orchestrator" / "agents" / "dynamic"
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
            print(f"✓ Scheduled: {recommendation.action_title}")
            print(f"  Schedule: {schedule}")
            print(f"  Rationale: {recommendation.rationale}")
        else:
            print("✗ Failed to schedule recommendation.")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_execute(args):
    """Execute a recommendation immediately."""
    from orchestrator import CortexOrchestrator
    # Import internal orchestrator components
    from cortex.execution.engine import Orchestrator as ExecutionEngine
    from cortex.execution.adapter import RecommendationToAgentAdapter

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
                print(
                    f"Error: Index {args.index} out of range (1-{len(all_recommendations)})"
                )
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
        print(f"Executing: {recommendation.title}")
        print(f"Type: {recommendation.type}")
        print(f"Priority: {recommendation.priority}")
        print(f"Rationale: {recommendation.rationale}")
        if recommendation.description:
            print(f"\nActions:\n{recommendation.description}")
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
                        "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, "isoformat") else str(result.timestamp),
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


def cmd_learn(args):
    """Show learning metrics and patterns."""
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
                    print(
                        f"    Total: {pattern['total']}, Followed: {pattern['followed']}"
                    )
                    print(f"    Success Rate: {pattern['success_rate']:.1%}")
                    print(f"    Avg Confidence: {pattern['avg_confidence']:.2f}")
                    print("")
        else:
            print("💡 TIP")
            print("────────────────")
            print(
                "No outcome patterns yet. Start tracking outcomes to enable learning!"
            )
            print("")
            print("Log outcomes with:")
            print("  cortex feedback --outcome <success|partial|failed>")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


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
    print(
        f"Any batch enabled: {'✅ Yes' if BatchConfig.is_any_batch_enabled() else '❌ No'}"
    )
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
            from briefing import get_executive_summary, format_briefing
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
            
        else: # custom
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

def cmd_alerts(args):
    """Show active alerts from Layer 3 Warning System."""
    from intelligence.monitoring.alert_generator import AlertGenerator
    from intelligence.monitoring.trend_analyzer import TrendAnalyzer
    from intelligence.monitoring.metric_tracker import MetricTracker

    try:
        # Initialize components
        tracker = MetricTracker()
        analyzer = TrendAnalyzer(tracker)
        alert_gen = AlertGenerator(analyzer)

        # Get all alerts
        # Since AlertGenerator needs a project, we'll scan for projects with metrics
        all_alerts = []

        # If project specified, just get alerts for that project
        if args.project:
            alerts = alert_gen.generate_alerts(args.project, days=7)
            all_alerts.extend(alerts)
        else:
            # For now, just show message that project is required
            print("Note: Specify --project to see alerts for a specific project")
            print("Example: cortex alerts --project cortex")
            return

        # Filter by severity if specified
        if args.severity:
            all_alerts = [a for a in all_alerts if a.severity.value == args.severity]

        if not all_alerts:
            print("✓ No alerts found")
            return

        # Display alerts grouped by severity
        by_severity = {'critical': [], 'warning': [], 'info': []}
        for alert in all_alerts:
            by_severity[alert.severity.value].append(alert)

        for severity in ['critical', 'warning', 'info']:
            alerts_list = by_severity[severity]
            if not alerts_list:
                continue

            print(f"\n{severity.upper()} ({len(alerts_list)} alerts)")
            print("─" * 60)

            for alert in alerts_list:
                print(f"  [{alert.project}] {alert.metric_type}")
                print(f"    {alert.message}")
                print(f"    {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print()

        print(f"\nTotal: {len(all_alerts)} active alerts")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_metrics(args):
    """Show metrics for a project."""
    from intelligence.monitoring.metric_tracker import MetricTracker
    from datetime import timedelta

    try:
        tracker = MetricTracker()

        # Determine project
        project = args.project or "cortex"  # Default to cortex for now

        # Get metrics
        since = datetime.now() - timedelta(days=args.days)

        # Get all metrics for the project
        all_metrics = []
        for metric_type in ['coverage', 'violations', 'commits', 'file_changes']:
            try:
                metrics = tracker.get_metrics(project, metric_type, days=args.days)
                all_metrics.extend(metrics)
            except:
                pass  # Skip if metric type not found

        if not all_metrics:
            print(f"No metrics found for project '{project}'")
            return

        print(f"\nMetrics for: {project}")
        print(f"Period: Last {args.days} days\n")

        # Group by metric type
        by_type = {}
        for metric in all_metrics:
            mtype = metric.metric_type.value
            if mtype not in by_type:
                by_type[mtype] = []
            by_type[mtype].append(metric)

        # Display each metric type
        for metric_type, metrics in by_type.items():
            print(f"{metric_type.upper()}")
            print("─" * 60)

            if metrics:
                latest = metrics[-1]
                print(f"  Current: {latest.metric_value:.2f}")
                print(f"  Updated: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

                values = [m.metric_value for m in metrics]
                print(f"  Min: {min(values):.2f} | Max: {max(values):.2f} | Avg: {sum(values)/len(values):.2f}")
            print()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_track(args):
    """Track metrics for a project."""
    from intelligence.monitoring.metric_tracker import MetricTracker, MetricType
    from pathlib import Path

    try:
        tracker = MetricTracker()

        # Determine project
        project = args.project or "cortex"
        project_path = Path(f"/Users/jesse.kemp/Dev/{project}")

        if not project_path.exists():
            print(f"Error: Project path does not exist: {project_path}")
            sys.exit(1)

        print(f"Tracking metrics for: {project}")

        # Track basic metrics
        metrics_tracked = []

        # For now, just track a simple metric (we can expand this later)
        # Track coverage metric as an example
        try:
            # Simple coverage calculation: count Python files vs test files
            py_files = list(project_path.rglob("*.py"))
            test_files = [f for f in py_files if "test_" in f.name or f.name.startswith("test")]

            if py_files:
                coverage_estimate = len(test_files) / len(py_files)
                tracker.track_coverage(project, coverage_estimate * 100, {"files": len(py_files), "tests": len(test_files)})
                metrics_tracked.append(('Test Coverage Estimate', coverage_estimate))
        except Exception as e:
            print(f"  Warning: Could not track coverage: {e}")

        print("✓ Tracking complete")
        print("\nMetrics updated:")

        for metric_name, value in metrics_tracked:
            print(f"  {metric_name}: {value:.1%}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_projects(args):
    """List projects with AI metadata from .claude/project.yaml files."""
    from project_metadata import ProjectMetadataReader

    reader = ProjectMetadataReader()
    projects = reader.scan_workspace()

    if args.domain:
        projects = [p for p in projects if p.domain == args.domain]
    if args.status:
        projects = [p for p in projects if p.status == args.status]

    if not projects:
        print("No projects with .claude/project.yaml found")
        if args.domain or args.status:
            print(f"Filters applied: domain={args.domain}, status={args.status}")
        return

    print("╔══════════════════════════════════════════════════════╗")
    print(f"║     AI-FIRST WORKSPACE PROJECTS: {len(projects):<3}              ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")

    # Group by domain
    by_domain = {}
    for p in projects:
        by_domain.setdefault(p.domain, []).append(p)

    for domain, domain_projects in sorted(by_domain.items()):
        print(f"📁 {domain.upper()}")
        print("────────────────")
        for p in domain_projects:
            status_icon = "🟢" if p.status == "production" else "🟡" if p.status == "development" else "⚪"
            print(f"  {status_icon} {p.name}")
            print(f"     Status: {p.status} | Priority: {p.priority}")
            if p.tech_stack.get("primary"):
                tech = ", ".join(p.tech_stack["primary"][:3])
                print(f"     Tech: {tech}")
            print(f"     Path: {p.path}")
        print("")


def cmd_project_info(args):
    """Show detailed info for a project."""
    from project_metadata import ProjectMetadataReader

    reader = ProjectMetadataReader()
    projects = {p.name: p for p in reader.scan_workspace()}

    if args.project_name not in projects:
        print(f"Project '{args.project_name}' not found or has no .claude/project.yaml")
        print("\nAvailable projects:")
        for name in sorted(projects.keys()):
            print(f"  - {name}")
        return

    p = projects[args.project_name]

    print("╔══════════════════════════════════════════════════════╗")
    print(f"║  PROJECT: {p.name:<43}║")
    print("╚══════════════════════════════════════════════════════╝")
    print("")

    print(f"Domain: {p.domain}")
    print(f"Status: {p.status}")
    print(f"Priority: {p.priority}")
    print(f"Path: {p.path}")

    if p.description:
        print(f"\nDescription:")
        # Wrap long descriptions
        desc = p.description[:300]
        if len(p.description) > 300:
            desc += "..."
        print(f"  {desc}")

    if p.entry_points:
        print(f"\nEntry Points:")
        for ep, path in p.entry_points.items():
            print(f"  {ep}: {path}")

    if p.tech_stack:
        print(f"\nTech Stack:")
        if p.tech_stack.get("primary"):
            print(f"  Primary: {', '.join(p.tech_stack['primary'])}")
        if p.tech_stack.get("secondary"):
            print(f"  Secondary: {', '.join(p.tech_stack['secondary'])}")

    if p.common_tasks:
        print(f"\nCommon Tasks ({len(p.common_tasks)}):")
        for task in p.common_tasks:
            print(f"  - {task.name} ({task.complexity})")
            if args.verbose:
                for step in task.steps:
                    print(f"    • {step}")

    if p.ai_hints:
        print(f"\nAI Hints ({len(p.ai_hints)}):")
        for hint in p.ai_hints[:5 if not args.verbose else None]:
            print(f"  - {hint}")
        if len(p.ai_hints) > 5 and not args.verbose:
            print(f"  ... and {len(p.ai_hints) - 5} more (use --verbose)")

    if p.known_issues:
        print(f"\nKnown Issues ({len(p.known_issues)}):")
        for issue in p.known_issues[:3 if not args.verbose else None]:
            print(f"  - {issue}")
        if len(p.known_issues) > 3 and not args.verbose:
            print(f"  ... and {len(p.known_issues) - 3} more (use --verbose)")

    if p.related_projects:
        print(f"\nRelated Projects ({len(p.related_projects)}):")
        for rel in p.related_projects:
            rel_name = rel.get("name", "unknown")
            rel_type = rel.get("relationship", "related")
            print(f"  - {rel_name} ({rel_type})")

    print("")


def cmd_sync_portfolio(args):
    """Sync project.yaml files to portfolio index."""
    from project_metadata import ProjectMetadataReader
    import json
    from datetime import datetime

    reader = ProjectMetadataReader()
    projects = reader.scan_workspace()

    portfolio_path = Path.home() / ".claude" / "portfolio" / "project_index.json"

    # Load existing
    existing = {}
    if portfolio_path.exists():
        with open(portfolio_path) as f:
            existing = json.load(f)

    # Update from project.yaml files
    synced_count = 0
    for p in projects:
        existing[p.name] = {
            "path": str(p.path),
            "domain": p.domain,
            "status": p.status,
            "priority": p.priority,
            "tech_stack": p.tech_stack.get("primary", []),
            "description": p.description[:200] if p.description else "",
            "synced_at": datetime.now().isoformat(),
            "source": "project.yaml"
        }
        synced_count += 1

    # Save
    portfolio_path.parent.mkdir(parents=True, exist_ok=True)
    with open(portfolio_path, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"✓ Synced {synced_count} projects to {portfolio_path}")
    print(f"  Total projects in index: {len(existing)}")


def cmd_dashboard(args):
    """Show Symbiosis Dashboard (Night Shift & Agents)."""
    from datetime import datetime
    
    # Import internal orchestrator components
    # Import internal orchestrator components
    # Assuming local-orchestrator is in path from main setup
    try:
        from batch_system import BatchManager
        from history import ExecutionHistory
        from config import STORAGE_PATH
    except ImportError:
        # Fallback: try adding local-orchestrator explicitly if not in path
        import sys
        dev_dir = Path(__file__).parent.parent.parent # .../Dev
        lo_dir = dev_dir / "local-orchestrator"
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
            # We added it to sys.path earlier, or check relative
             lo_dir = Path(__file__).parent.parent / "local-orchestrator"
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
                "batches": active_batches
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
        print(f"{'-'*25} {'-'*10} {'-'*20} {'-'*15}")

        for run in recent:
            agent_id = run.get("agent_id", "unknown")
            # Shorten ID
            name = agent_id.replace("system_", "").replace("agent_", "")[:24]
            status = run.get("status", "unknown")
            status_icon = (
                "✅"
                if status == "completed" or status
                else "❌" if status == "failed" else "⏳"
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
                except:
                    time_val = str(ts_str)[:8]

            msg = (
                run.get("message", "")[:30] + "..."
                if len(run.get("message", "")) > 30
                else run.get("message", "")
            )

            print(f"{name:<25} {status_icon} {status:<8} {time_val:<20} {msg}")
    print("")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cortex - Strategic Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cortex next                    # Get next action
  cortex next vortexv2          # Get next action for VortexV2
  cortex next --with-context    # Include context predictions
  cortex next --json            # JSON output
  cortex execute                # Execute top recommendation
  cortex execute 2              # Execute 2nd recommendation
  cortex execute --id blocker_1 # Execute specific recommendation by ID
  cortex status                 # Show current state
  cortex health                 # Show system health
  cortex briefing               # Generate daily briefing
  cortex briefing --format=json # Daily briefing in JSON
  cortex feedback --stats       # Show feedback statistics
  cortex feedback --log "Note"  # Quick log entry
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

    # Health command
    health_parser = subparsers.add_parser("health", help="Show system health check")
    health_parser.set_defaults(func=cmd_health)

    # Context command
    context_parser = subparsers.add_parser("context", help="Preview context injection")
    context_parser.add_argument(
        "--task", type=str, help="Optional task description to test pattern matching"
    )
    context_parser.set_defaults(func=cmd_context)

    # Feedback command
    feedback_parser = subparsers.add_parser(
        "feedback", help="Log feedback for recommendations"
    )
    feedback_parser.add_argument(
        "--action-title", type=str, help="Title of the action/recommendation"
    )
    feedback_parser.add_argument(
        "--action-id", type=str, help="ID of the action (if available)"
    )
    feedback_parser.add_argument(
        "--useful", type=str, required=False, help="Was it useful? (yes/no)"
    )
    feedback_parser.add_argument("--notes", type=str, help="Optional notes")
    feedback_parser.add_argument(
        "--outcome", type=str, help="What actually happened?")
    feedback_parser.add_argument(
        "--stats",
        type=str,
        nargs="?",
        const="summary",
        help="Show feedback statistics (use 'recent' for recent entries)",
    )
    feedback_parser.add_argument(
        "--log", type=str, help="Quick log entry (general note)"
    )
    feedback_parser.set_defaults(func=cmd_feedback)

    # Notify command
    notify_parser = subparsers.add_parser("notify", help="Send notifications")
    notify_parser.add_argument(
        "--type", 
        choices=["morning", "evening", "custom"], 
        default="custom",
        help="Type of notification"
    )
    notify_parser.add_argument(
        "--channel", 
        action="append", 
        choices=["terminal", "email", "all"],
        help="Notification channels (can specify multiple)"
    )
    notify_parser.add_argument(
        "--message", type=str, help="Custom message content"
    )
    notify_parser.add_argument(
        "--title", type=str, help="Custom notification title"
    )
    notify_parser.set_defaults(func=cmd_notify)

    # Check command (Golden Spec Validator)
    from golden_spec_validator import GoldenSpecValidator

    def cmd_check(args):
        """Check project alignment with Golden Spec."""
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

    check_parser = subparsers.add_parser(
        "check", help="Check project compliance with Golden Spec"
    )
    check_parser.add_argument("project", nargs="?", help="Project to check")
    check_parser.set_defaults(func=cmd_check)

    # Draft command (Spec Generator)
    from spec_generator import SpecGenerator

    def cmd_draft(args):
        """Draft a new Golden Spec from intent."""
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

    draft_parser = subparsers.add_parser(
        "draft", help="Draft a new Golden Spec from intent"
    )
    draft_parser.add_argument("intent", help="The intent or goal of the project")
    draft_parser.add_argument(
        "--project", help="Project name (optional, defaults to current dir)"
    )
    draft_parser.set_defaults(func=cmd_draft)

    # Learn command
    learn_parser = subparsers.add_parser(
        "learn", help="Show learning metrics and patterns"
    )
    learn_parser.set_defaults(func=cmd_learn)

    # Batch status command
    batch_status_parser = subparsers.add_parser(
        "batch-status", help="Show batch API configuration"
    )
    batch_status_parser.set_defaults(func=cmd_batch_status)

    # Dashboard command (Symbiosis Engine)
    dashboard_parser = subparsers.add_parser(
        "dashboard", help="Show Symbiosis Engine Dashboard"
    )
    dashboard_parser.set_defaults(func=cmd_dashboard)

    # Briefing command
    briefing_parser = subparsers.add_parser("briefing", help="Generate daily briefing")
    briefing_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    briefing_parser.add_argument(
        "--no-color", action="store_true", help="Disable color output"
    )
    briefing_parser.set_defaults(func=cmd_briefing)

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
    execute_parser = subparsers.add_parser(
        "execute", help="Execute a recommendation immediately"
    )
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
    skill_parser = subparsers.add_parser('skill', help='Manage and execute skills')
    skill_subparsers = skill_parser.add_subparsers(dest='skill_command', help='Skill commands')

    # skill list
    skill_list_parser = skill_subparsers.add_parser('list', help='List all skills')
    skill_list_parser.set_defaults(func=cmd_skill_list)

    # skill run
    skill_run_parser = skill_subparsers.add_parser('run', help='Run a skill')
    skill_run_parser.add_argument('skill_name', help='Name of skill to run')
    skill_run_parser.add_argument('--scope', type=str, help='Validation scope (for forecasting skill)')
    skill_run_parser.add_argument('--symbol', type=str, help='Symbol (for trading skill)')
    skill_run_parser.add_argument('--days', type=int, help='Days (for trading skill)')
    skill_run_parser.add_argument('--directory', type=str, help='Directory (for audio skill)')
    skill_run_parser.set_defaults(func=cmd_skill_run)

    # skill info
    skill_info_parser = skill_subparsers.add_parser('info', help='Show skill information')
    skill_info_parser.add_argument('skill_name', help='Name of skill')
    skill_info_parser.set_defaults(func=cmd_skill_info)

    # skill schedule
    skill_schedule_parser = skill_subparsers.add_parser('schedule', help='Run scheduled skills')
    skill_schedule_parser.set_defaults(func=cmd_skill_schedule)

    # Projects command
    projects_parser = subparsers.add_parser('projects', help='List AI-first workspace projects')
    projects_parser.add_argument('--domain', type=str, help='Filter by domain')
    projects_parser.add_argument('--status', type=str, help='Filter by status')
    projects_parser.set_defaults(func=cmd_projects)

    # Project-info command
    project_info_parser = subparsers.add_parser('project-info', help='Show detailed project information')
    project_info_parser.add_argument('project_name', help='Name of the project')
    project_info_parser.add_argument('--verbose', '-v', action='store_true', help='Show all details')
    project_info_parser.set_defaults(func=cmd_project_info)

    # Sync-portfolio command
    sync_portfolio_parser = subparsers.add_parser('sync-portfolio', help='Sync project.yaml to portfolio index')
    sync_portfolio_parser.set_defaults(func=cmd_sync_portfolio)

    # Layer 3: Alerts command
    alerts_parser = subparsers.add_parser('alerts', help='Show active alerts from Layer 3 Warning System')
    alerts_parser.add_argument('--severity', choices=['critical', 'warning', 'info'], help='Filter by severity')
    alerts_parser.add_argument('--project', help='Filter by project')
    alerts_parser.set_defaults(func=cmd_alerts)

    # Layer 3: Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Show metrics for a project')
    metrics_parser.add_argument('project', nargs='?', help='Project name (optional, uses current)')
    metrics_parser.add_argument('--days', type=int, default=7, help='Days of history (default: 7)')
    metrics_parser.set_defaults(func=cmd_metrics)

    # Layer 3: Track command
    track_parser = subparsers.add_parser('track', help='Track metrics for a project')
    track_parser.add_argument('--project', help='Project to track (default: current)')
    track_parser.add_argument('--force', action='store_true', help='Force tracking even if recent')
    track_parser.set_defaults(func=cmd_track)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
