"""Batch commands: batch_status, v2a_batch, schedule, execute, orchestrate, notify."""

import os
import sys
from pathlib import Path

from feedback import FeedbackLogger
from orchestrator import CortexOrchestrator


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


def cmd_v2a_batch(args):
    """Manage V2a sprint batch jobs."""
    from batch.v2a_sprint_orchestrator import V2aSprintOrchestrator

    orchestrator = V2aSprintOrchestrator()

    if args.action == "submit":
        print("🚀 Submitting V2a sprint batch jobs...")
        print("")

        wave_task_ids = orchestrator.submit_all_sprints()

        print("✓ All tasks submitted to batch queue!")
        print("")

        for wave_id in sorted(wave_task_ids.keys()):
            task_ids = wave_task_ids[wave_id]
            print(f"  {wave_id}: {len(task_ids)} tasks")

        print("")
        print("Use 'cortex v2a-batch --action status' to monitor progress")

    elif args.action == "status":
        print("📊 V2a Sprint Batch Status")
        print("=" * 60)

        status_data = orchestrator.get_overall_status()

        print(f"Total Tasks: {status_data['total_tasks']}")
        print(f"Completed: {status_data['completed']}")
        print(f"Running: {status_data['running']}")
        print(f"Failed: {status_data['failed']}")
        print(f"Pending: {status_data['pending']}")
        print(f"Progress: {status_data['progress_pct']:.1f}%")
        print(f"Current Wave: {status_data['current_wave']}")
        print("")

        # Per-wave breakdown
        print("Per-Wave Status:")
        for wave_id in ["wave_1", "wave_2", "wave_3", "wave_4"]:
            wave_status = status_data["waves"].get(wave_id, {})
            progress = wave_status.get("progress_pct", 0)
            running = wave_status.get("running", 0)

            if progress == 100:
                emoji = "✅"
            elif running > 0:
                emoji = "🔄"
            else:
                emoji = "📋"

            print(
                f"  {emoji} {wave_id}: {wave_status.get('completed', 0)}/{wave_status.get('total', 0)} complete ({progress:.0f}%)"
            )

    elif args.action == "retry":
        print("🔄 Retrying failed tasks...")
        retried = orchestrator.retry_failed_tasks(wave_id=args.wave)

        if retried:
            print(f"✓ Retried {len(retried)} tasks")
        else:
            print("No failed tasks to retry")

    else:
        print(f"Unknown action: {args.action}")
        sys.exit(1)


def cmd_schedule(args):
    """Schedule a recommendation or intent as a local-orchestrator agent."""
    from agent_factory import AgentFactory

    # Add cortex dir to path for internal imports
    cortex_dir = Path(__file__).parent.parent.parent

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
            import re

            yaml_content = AgentFactory.create_team_config(intent=intent)

            # Write to Drop Zone
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(cortex_dir.parent)))
            drop_zone = root_dir / "local-orchestrator" / "agents" / "dynamic"
            drop_zone.mkdir(parents=True, exist_ok=True)

            # Generate filename
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
        from cortex.execution.engine import Orchestrator as ExecutionEngine
        from cortex.execution.adapter import RecommendationToAgentAdapter

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
    from cortex.execution.adapter import RecommendationToAgentAdapter
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


def cmd_notify(args):
    """Send notifications via Chief of Staff persona."""
    from cortex.notify import Notifier
    from briefing import generate_daily_briefing

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
