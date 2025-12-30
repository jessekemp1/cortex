#!/usr/bin/env python3
"""
Cortex CLI - Command-line interface for strategic orchestrator

Usage:
    cortex next [PROJECT] [--with-context] [--json]
    cortex status
"""

import argparse
import sys
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


def cmd_git(args):
    """Show Git/GitHub status and recommendations."""
    try:
        from integration.git_tracker import GitTracker
    except ImportError:
        print("Error: Git tracker module not available")
        sys.exit(1)

    try:
        tracker = GitTracker(str(args.root))
        state = tracker.get_state()

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
                    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec["priority"], "⚪")
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

    # Batch API status command
    batch_api_status_parser = subparsers.add_parser(
        "batch-api-status", help="Show batch API configuration"
    )
    batch_api_status_parser.set_defaults(func=cmd_batch_status)

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

    # Git command
    git_parser = subparsers.add_parser("git", help="Show Git/GitHub status")
    git_parser.add_argument("--json", action="store_true", help="Output JSON format")
    git_parser.add_argument("--brief", action="store_true", help="Show brief summary")
    git_parser.add_argument("--recommendations", "-r", action="store_true", help="Include actionable recommendations")
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
        print(f"CPU Usage:     {status['cpu_percent']:.1f}% ({status['cpu_available']:.1f}% available)")
        print(f"Memory Usage:  {status['memory_usage_percent']:.1f}% ({status['memory_available_mb']:.0f} MB available)")
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

        if waste_summary['total_waste_items'] == 0:
            print("✅ No resource waste detected!")
            return

        print(f"Total Waste Items: {waste_summary['total_waste_items']}")
        print(f"Auto-actionable:   {waste_summary['auto_actionable']}")
        print(f"Manual Review:     {waste_summary['manual_review']}")
        print("")

        # Group by type
        for waste_type, count in waste_summary['by_type'].items():
            print(f"  {waste_type}: {count}")
        print("")

        # Show details
        print("DETAILS")
        print("────────────────")
        for item in waste_summary['items'][:10]:  # Show top 10
            auto_marker = "🤖" if item['auto_actionable'] else "👁️"
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
        util = insights['utilization']
        print("📊 UTILIZATION PATTERNS")
        print("────────────────")
        print(f"Peak Hours:     {', '.join(f'{h:02d}:00' for h in util['peak_hours'])}")
        print(f"Idle Hours:     {', '.join(f'{h:02d}:00' for h in util['idle_hours'])}")
        print(f"Capacity Headroom: {util['capacity_headroom']:.1f}%")
        print("")

        # AI tools
        if insights['ai_tools']:
            print("🤖 AI TOOL USAGE")
            print("────────────────")
            for tool in insights['ai_tools']:
                print(f"{tool['tool_name']}:")
                print(f"  Usage: {tool['usage_hours']:.1f}h | Idle: {tool['idle_hours']:.1f}h")
                print(f"  Avg CPU: {tool['avg_cpu']:.1f}% | Avg Memory: {tool['avg_memory']:.0f} MB")
            print("")

        # Dev patterns
        dev = insights['dev_patterns']
        print("💻 DEVELOPMENT PATTERNS")
        print("────────────────")
        print(f"Active Coding Hours: {', '.join(f'{h:02d}:00' for h in dev['active_coding_hours'][:5])}")
        print(f"Build Frequency:     {dev['build_frequency']:.1f} builds/day")

    # === Batch Command Functions ===
    def cmd_batch_add(args):
        """Add a task to the batch queue."""
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
            estimated_duration_minutes=args.duration
        )

        print(f"✅ Task added to queue")
        print(f"Task ID: {task.task_id}")
        print(f"Command: {task.command}")
        print(f"Type: {task.task_type}")
        print(f"Priority: {task.priority}")
        print(f"State: {task.state.value}")

    def cmd_batch_list(args):
        """List batch tasks."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor, TaskState
        monitor = ProcessMonitor()

        state_filter = TaskState(args.state) if args.state else None
        tasks = monitor.batch_queue.get_task_history(
            limit=args.limit,
            state=state_filter
        )

        if not tasks:
            print("No tasks found")
            return

        print(f"{'='*70}")
        print(f"BATCH TASKS ({len(tasks)} shown)")
        print(f"{'='*70}")
        print()

        for task in tasks:
            state_icon = {
                'pending': '⏳',
                'scheduled': '📅',
                'running': '▶️ ',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(task.state.value, '•')

            print(f"{state_icon} {task.description}")
            print(f"   ID: {task.task_id}")
            print(f"   Type: {task.task_type} | Priority: {task.priority}")
            print(f"   State: {task.state.value}")

            if task.scheduled_time:
                print(f"   Scheduled: {task.scheduled_time.strftime('%Y-%m-%d %H:%M')}")

            if task.completed_at:
                duration = task.actual_duration_seconds or 0
                print(f"   Duration: {duration:.1f}s | Exit code: {task.exit_code}")

            if task.error_message:
                print(f"   Error: {task.error_message}")

            print()

    def cmd_batch_queue_status(args):
        """Show batch queue status."""
        if not PROCESS_MONITOR_AVAILABLE:
            print("Error: Process Monitor not available")
            sys.exit(1)

        from intelligence.process_monitor import ProcessMonitor
        monitor = ProcessMonitor()

        stats = monitor.batch_queue.get_queue_stats()

        print(f"{'='*70}")
        print("BATCH QUEUE STATUS")
        print(f"{'='*70}")
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
        success_rate = stats.get('success_rate', 0)
        print(f"✅ SUCCESS RATE: {success_rate:.1%}")
        print()

        # Average durations
        if stats.get('avg_duration_by_type'):
            print("⏱️  AVERAGE DURATION BY TYPE")
            print("────────────────")
            for task_type, avg_duration in stats['avg_duration_by_type'].items():
                print(f"{task_type:20} {avg_duration:.1f}s")
            print()

        # Executor status
        executor_status = monitor.batch_executor.get_status()
        print("🔄 EXECUTOR STATUS")
        print("────────────────")
        print(f"Running tasks:     {executor_status['running_tasks']}/{executor_status['max_concurrent']}")
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

        if results['scheduled'] > 0:
            print("Scheduled tasks:")
            for task_info in results['tasks']:
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

        if results['tasks']:
            for task_info in results['tasks']:
                if task_info['status'] == 'executing':
                    print(f"▶️  {task_info['description']}")
                    print(f"   Status: Executing")
                else:
                    print(f"⏸️  {task_info['description']}")
                    print(f"   Status: Deferred")
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

        print(f"{'='*70}")
        print(f"TASK: {task.description}")
        print(f"{'='*70}")
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
            process_monitor=monitor
        )

        result = daemon.start(
            interval_seconds=args.interval,
            foreground=not args.background
        )

        if result['success']:
            if args.background:
                print(f"✓ Daemon started in background")
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

        if result['success']:
            print(f"✓ Daemon stopped")
            print(f"  PID: {result['pid']}")
            if result.get('forced'):
                print(f"  (force killed)")
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

        if status['running']:
            print(f"✓ Daemon is running")
            print(f"  PID: {status['pid']}")
            print(f"  Uptime: {status['uptime']}")
            print(f"  Started: {status['started_at']}")
            if 'cpu_percent' in status:
                print(f"  CPU: {status['cpu_percent']:.1f}%")
            if 'memory_mb' in status:
                print(f"  Memory: {status['memory_mb']:.1f} MB")
            print(f"  Log file: {status['log_file']}")
        else:
            print(f"✗ Daemon is not running")
            if 'pid' in status:
                print(f"  (stale PID: {status['pid']})")

    # Process subcommands
    process_parser = subparsers.add_parser('process', help='Process monitoring and optimization')
    process_subparsers = process_parser.add_subparsers(dest='process_command', help='Process commands')

    # process status
    process_status_parser = process_subparsers.add_parser('status', help='Show current process status')
    process_status_parser.set_defaults(func=cmd_process_status)

    # process waste
    process_waste_parser = process_subparsers.add_parser('waste', help='Show detected resource waste')
    process_waste_parser.set_defaults(func=cmd_process_waste)

    # process optimize
    process_optimize_parser = process_subparsers.add_parser('optimize', help='Show optimization suggestions')
    process_optimize_parser.set_defaults(func=cmd_process_optimize)

    # process insights
    process_insights_parser = process_subparsers.add_parser('insights', help='Show utilization insights')
    process_insights_parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')
    process_insights_parser.set_defaults(func=cmd_process_insights)

    # === Batch Scheduling Commands ===
    batch_parser = subparsers.add_parser('batch', help='Batch task scheduling and execution')
    batch_subparsers = batch_parser.add_subparsers(dest='batch_command', help='Batch commands')

    # batch add
    batch_add_parser = batch_subparsers.add_parser('add', help='Add a task to the batch queue')
    batch_add_parser.add_argument('command', help='Command to execute')
    batch_add_parser.add_argument('--type', dest='task_type', default='general', help='Task type (test, build, deploy, etc.)')
    batch_add_parser.add_argument('--description', default='', help='Task description')
    batch_add_parser.add_argument('--priority', default='normal', choices=['immediate', 'high', 'normal', 'low'], help='Task priority')
    batch_add_parser.add_argument('--duration', type=float, default=10.0, help='Estimated duration in minutes')
    batch_add_parser.set_defaults(func=cmd_batch_add)

    # batch list
    batch_list_parser = batch_subparsers.add_parser('list', help='List batch tasks')
    batch_list_parser.add_argument('--state', choices=['pending', 'scheduled', 'running', 'completed', 'failed', 'cancelled'], help='Filter by state')
    batch_list_parser.add_argument('--limit', type=int, default=20, help='Maximum tasks to show')
    batch_list_parser.set_defaults(func=cmd_batch_list)

    # batch status
    batch_status_parser = batch_subparsers.add_parser('status', help='Show batch queue status')
    batch_status_parser.set_defaults(func=cmd_batch_queue_status)

    # batch schedule
    batch_schedule_parser = batch_subparsers.add_parser('schedule', help='Schedule pending tasks')
    batch_schedule_parser.set_defaults(func=cmd_batch_schedule)

    # batch run
    batch_run_parser = batch_subparsers.add_parser('run', help='Execute scheduled tasks')
    batch_run_parser.set_defaults(func=cmd_batch_run)

    # batch cancel
    batch_cancel_parser = batch_subparsers.add_parser('cancel', help='Cancel a task')
    batch_cancel_parser.add_argument('task_id', help='Task ID to cancel')
    batch_cancel_parser.set_defaults(func=cmd_batch_cancel)

    # batch logs
    batch_logs_parser = batch_subparsers.add_parser('logs', help='Show task execution logs')
    batch_logs_parser.add_argument('task_id', help='Task ID')
    batch_logs_parser.set_defaults(func=cmd_batch_logs)

    # batch daemon - nested subparser
    batch_daemon_parser = batch_subparsers.add_parser('daemon', help='Daemon management')
    daemon_subparsers = batch_daemon_parser.add_subparsers(dest='daemon_command', help='Daemon commands')

    # daemon start
    daemon_start_parser = daemon_subparsers.add_parser('start', help='Start the batch scheduler daemon')
    daemon_start_parser.add_argument('--interval', type=int, default=60, help='Task check interval in seconds (default: 60)')
    daemon_start_parser.add_argument('--background', action='store_true', help='Run in background (default: foreground)')
    daemon_start_parser.set_defaults(func=cmd_batch_daemon_start)

    # daemon stop
    daemon_stop_parser = daemon_subparsers.add_parser('stop', help='Stop the batch scheduler daemon')
    daemon_stop_parser.set_defaults(func=cmd_batch_daemon_stop)

    # daemon status
    daemon_status_parser = daemon_subparsers.add_parser('status', help='Show daemon status')
    daemon_status_parser.set_defaults(func=cmd_batch_daemon_status)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
