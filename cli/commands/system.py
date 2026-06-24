"""System commands: config (git/sync/docs/dashboard/bandwidth/watch/batch_fill)."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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

    sync_script = (
        Path(__file__).parent.parent.parent.parent / "_tools" / "doc-sync" / "sync_docs.py"
    )

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


def cmd_dashboard(args):
    """Show Symbiosis Dashboard (Night Shift & Agents)."""
    # Import internal orchestrator components
    try:
        from batch_system import BatchManager
        from config import STORAGE_PATH
        from history import ExecutionHistory
    except ImportError:
        # Fallback: try adding local-orchestrator explicitly if not in path
        root_dir = Path(
            os.environ.get("CORTEX_ROOT_DIR", str(Path(__file__).parent.parent.parent.parent))
        )
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
        if not Path(STORAGE_PATH).is_absolute():
            root_dir = Path(
                os.environ.get("CORTEX_ROOT_DIR", str(Path(__file__).parent.parent.parent.parent))
            )
            lo_dir = root_dir / "local-orchestrator"
            db_path = str(lo_dir / STORAGE_PATH)
        else:
            db_path = STORAGE_PATH

        batch_manager = BatchManager(db_path=db_path)
        history = ExecutionHistory(db_path=db_path)

        # Get stats
        try:
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
                    if "T" in str(ts_str):
                        time_val = str(ts_str).split("T")[1].split(".")[0]
                    else:
                        time_val = str(ts_str)
                except Exception:
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
                watches_dir = Path.home() / ".cortex" / "watches" / "pending"
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
