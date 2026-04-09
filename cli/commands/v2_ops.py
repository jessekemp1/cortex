"""
V2 Ops — command handlers and subparser registration for:
  batch-local, process, work-absorber, v2-prime, graph, interventions, iap, runtime,
  sessions, signals, doctor, check, draft, skills.

All functions were previously defined inline inside cli/__init__.py:main().
Extracted here to keep cli/__init__.py a pure dispatcher.
"""

from __future__ import annotations

import sys
from pathlib import Path


# ── check ─────────────────────────────────────────────────────────────────────


def cmd_check(args):
    """Check project alignment with Golden Spec."""
    from golden_spec_validator import GoldenSpecValidator

    validator = GoldenSpecValidator(Path(args.root))

    target_projects = (
        [args.project]
        if args.project
        else [
            p.name for p in Path(args.root).iterdir() if p.is_dir() and not p.name.startswith(".")
        ]
    )

    print("╔══════════════════════════════════════════════════════╗")
    print("║          CORTEX - GOLDEN SPEC VALIDATOR              ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    for proj in target_projects:
        if not args.project and (
            proj in ["logs", "scripts", "reports", "archive"]
            or not (Path(args.root) / proj).is_dir()
        ):
            continue

        status = validator.validate_project(proj)
        if not status.has_spec_file and not args.project:
            continue

        print(f"Project: {status.project_name}")
        print(f"Spec File: {status.spec_path or '❌ Missing'}")
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


# ── draft ─────────────────────────────────────────────────────────────────────


def cmd_draft(args):
    """Draft a new Golden Spec from intent."""
    from spec_generator import SpecGenerator

    generator = SpecGenerator(Path(args.root))
    project_name = args.project or Path.cwd().name

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


# ── skills ────────────────────────────────────────────────────────────────────


def cmd_skill_list(args):
    try:
        from skills import registry

        print(registry.list_skills())
    except ImportError:
        print("Skills module not available.")


def cmd_skill_run(args):
    import asyncio

    try:
        from skills import registry
    except ImportError:
        print("Skills module not available.")
        return

    async def run():
        result = await registry.execute_skill(args.skill_name, **vars(args))
        if result:
            print("\n" + result.to_markdown())
        else:
            print(f"Error: Skill '{args.skill_name}' not found")
            sys.exit(1)

    asyncio.run(run())


def cmd_skill_info(args):
    try:
        from skills import registry
    except ImportError:
        print("Skills module not available.")
        return
    skill = registry.get(args.skill_name)
    if skill:
        print(skill.to_markdown())
    else:
        print(f"Error: Skill '{args.skill_name}' not found")
        sys.exit(1)


def cmd_skill_schedule(args):
    import asyncio

    try:
        from skills import registry
    except ImportError:
        print("Skills module not available.")
        return

    async def run():
        results = await registry.execute_scheduled()
        print(f"\nExecuted {len(results)} scheduled skills")
        for result in results:
            print(f"  - {result.summary}")

    asyncio.run(run())


# ── process monitor ───────────────────────────────────────────────────────────


def cmd_process_status(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Process monitoring not available. Run: pip install psutil")
        return
    monitor = ProcessMonitor()
    status = monitor.get_status()
    print("╔══════════════════════════════════════════════════════╗")
    print("║          CORTEX - PROCESS MONITOR STATUS             ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    print("💻 SYSTEM RESOURCES\n────────────────")
    print(f"CPU Usage:     {status['cpu_percent']:.1f}% ({status['cpu_available']:.1f}% available)")
    print(
        f"Memory Usage:  {status['memory_usage_percent']:.1f}% ({status['memory_available_mb']:.0f} MB available)"
    )
    print(f"Processes:     {status['process_count']}\n")
    print("🤖 AI TOOLS & SERVICES\n────────────────")
    print(f"AI Tool CPU:   {status['ai_tool_cpu']:.1f}%")
    print(f"Dev Service CPU: {status['dev_service_cpu']:.1f}%\n")
    print("⚠️  ALERTS\n────────────────")
    print(f"Total Alerts:   {status['alerts_count']}")
    print(f"Critical:       {status['critical_alerts']}\n")
    print("♻️  OPTIMIZATION\n────────────────")
    print(f"Waste Items:    {status['waste_items']}")
    print(f"Optimizations:  {status['optimization_opportunities']}")


def cmd_process_waste(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Process monitoring not available. Run: pip install psutil")
        return
    monitor = ProcessMonitor()
    waste_summary = monitor.optimizer.get_waste_summary()
    print("╔══════════════════════════════════════════════════════╗")
    print("║         CORTEX - RESOURCE WASTE DETECTION            ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    if waste_summary["total_waste_items"] == 0:
        print("✅ No resource waste detected!")
        return
    print(f"Total Waste Items: {waste_summary['total_waste_items']}")
    print(f"Auto-actionable:   {waste_summary['auto_actionable']}")
    print(f"Manual Review:     {waste_summary['manual_review']}\n")
    for waste_type, count in waste_summary["by_type"].items():
        print(f"  {waste_type}: {count}")
    print("\nDETAILS\n────────────────")
    for item in waste_summary["items"][:10]:
        auto_marker = "🤖" if item["auto_actionable"] else "👁️"
        print(f"{auto_marker} {item['process_name']}")
        print(f"   Type: {item['waste_type']}")
        print(f"   Cost: {item['resource_cost']}")
        print(f"   Recommendation: {item['recommendation']}\n")


def cmd_process_optimize(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Process monitoring not available. Run: pip install psutil")
        return
    monitor = ProcessMonitor()
    optimizations = monitor.optimizer.suggest_optimizations()
    print("╔══════════════════════════════════════════════════════╗")
    print("║       CORTEX - OPTIMIZATION SUGGESTIONS              ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    if not optimizations:
        print("✅ No optimization opportunities found!")
        return
    icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    for opt in optimizations:
        icon = icons.get(opt.priority, "⚪")
        print(f"{icon} [{opt.priority}] {opt.title}")
        print(f"   {opt.description}")
        print(f"   Savings: {opt.estimated_savings}")
        if opt.action_command:
            print(f"   Command: {opt.action_command}")
        print()


def cmd_process_insights(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Process monitoring not available. Run: pip install psutil")
        return
    monitor = ProcessMonitor()
    insights = monitor.get_insights(days=args.days)
    print("╔══════════════════════════════════════════════════════╗")
    print("║        CORTEX - UTILIZATION INSIGHTS                 ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    util = insights["utilization"]
    print("📊 UTILIZATION PATTERNS\n────────────────")
    print(f"Peak Hours:     {', '.join(f'{h:02d}:00' for h in util['peak_hours'])}")
    print(f"Idle Hours:     {', '.join(f'{h:02d}:00' for h in util['idle_hours'])}")
    print(f"Capacity Headroom: {util['capacity_headroom']:.1f}%\n")
    if insights["ai_tools"]:
        print("🤖 AI TOOL USAGE\n────────────────")
        for tool in insights["ai_tools"]:
            print(f"{tool['tool_name']}:")
            print(f"  Usage: {tool['usage_hours']:.1f}h | Idle: {tool['idle_hours']:.1f}h")
            print(f"  Avg CPU: {tool['avg_cpu']:.1f}% | Avg Memory: {tool['avg_memory']:.0f} MB")
        print()
    dev = insights["dev_patterns"]
    print("💻 DEVELOPMENT PATTERNS\n────────────────")
    print(
        f"Active Coding Hours: {', '.join(f'{h:02d}:00' for h in dev['active_coding_hours'][:5])}"
    )
    print(f"Build Frequency:     {dev['build_frequency']:.1f} builds/day")


# ── batch (local queue) ───────────────────────────────────────────────────────


def cmd_batch_submit(args):
    import json
    from batch.orchestrator import BatchOrchestrator

    orchestrator = BatchOrchestrator()
    with open(args.job_file) as f:
        job_data = json.load(f)
    job_id = orchestrator.submit_job(job_data, auto_detect=True)
    backend = "LOCAL" if job_id.startswith("local_") else "API"
    print(f"✅ Job submitted to {backend} backend")
    print(f"Job ID: {job_id}")
    print(f"Description: {job_data.get('description', 'N/A')}")


def cmd_batch_add(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    task = monitor.batch_queue.add_task(
        command=args.command,
        task_type=args.task_type,
        description=args.description or args.command,
        priority=args.priority,
        estimated_duration_minutes=args.duration,
    )
    print(
        f"✅ Task added to LOCAL queue\nTask ID: {task.task_id}\nCommand: {task.command}\nType: {task.task_type}\nPriority: {task.priority}\nState: {task.state.value}"
    )


def cmd_batch_list(args):
    from batch.orchestrator import BatchOrchestrator, JobBackend

    orchestrator = BatchOrchestrator()
    backend_filter = args.backend if hasattr(args, "backend") else "both"
    jobs = orchestrator.list_jobs(backend=backend_filter, limit=args.limit)
    if not jobs:
        print("No jobs found")
        return
    local_jobs = [j for j in jobs if j.backend == JobBackend.LOCAL]
    api_jobs = [j for j in jobs if j.backend == JobBackend.API]
    if local_jobs:
        print(f"\n{'=' * 80}\nLOCAL EXECUTION QUEUE (ProcessMonitor)\n{'=' * 80}")
        for job in local_jobs:
            print(f"{job.status_icon} [{job.priority.upper():8}] {job.description}")
            print(f"   ID: {job.id} | State: {job.state.value}")
            if job.error_message:
                print(f"   Error: {job.error_message[:100]}")
            print()
    if api_jobs:
        print(f"\n{'=' * 80}\nAPI BATCH QUEUE (Anthropic)\n{'=' * 80}")
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
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    stats = monitor.batch_queue.get_queue_stats()
    print(f"{'=' * 70}\nBATCH QUEUE STATUS\n{'=' * 70}\n")
    print("📊 TASK COUNTS\n────────────────")
    for key in ["pending", "scheduled", "running", "completed", "failed", "cancelled"]:
        print(f"{key.capitalize():11} {stats.get(f'{key}_count', 0)}")
    print(f"\n✅ SUCCESS RATE: {stats.get('success_rate', 0):.1%}\n")
    if stats.get("avg_duration_by_type"):
        print("⏱️  AVERAGE DURATION BY TYPE\n────────────────")
        for task_type, avg in stats["avg_duration_by_type"].items():
            print(f"{task_type:20} {avg:.1f}s")
    executor_status = monitor.batch_executor.get_status()
    print("\n🔄 EXECUTOR STATUS\n────────────────")
    print(
        f"Running tasks:     {executor_status['running_tasks']}/{executor_status['max_concurrent']}"
    )
    print(f"Shutdown:          {'Yes' if executor_status['shutdown'] else 'No'}")


def cmd_batch_schedule(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    print("Scheduling pending tasks...")
    results = monitor.batch_executor.schedule_pending_tasks()
    print(f"Total pending: {results['total_pending']}\nScheduled: {results['scheduled']}\n")
    for task_info in results.get("tasks", []):
        print(
            f"✅ {task_info['description']}\n   Time: {task_info['scheduled_time']}\n   Reason: {task_info['reason']}\n"
        )


def cmd_batch_run(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    print("Processing scheduled tasks...")
    results = monitor.batch_executor.process_scheduled_tasks()
    print(
        f"Total ready: {results['total_ready']}\nExecuted: {results['executed']}\nDeferred: {results['deferred']}\n"
    )
    for task_info in results.get("tasks", []):
        if task_info["status"] == "executing":
            print(f"▶️  {task_info['description']}\n   Status: Executing")
        else:
            print(
                f"⏸️  {task_info['description']}\n   Status: Deferred\n   Reason: {task_info['reason']}"
            )
        print()


def cmd_batch_cancel(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    success = monitor.batch_queue.cancel_task(args.task_id)
    if success:
        print(f"✅ Task {args.task_id} cancelled")
    else:
        print(f"❌ Failed to cancel task {args.task_id}")


def cmd_batch_logs(args):
    try:
        from intelligence.process_monitor import ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    task = monitor.batch_queue.get_task(args.task_id)
    if not task:
        print(f"Task {args.task_id} not found")
        sys.exit(1)
    print(f"{'=' * 70}\nTASK: {task.description}\n{'=' * 70}\n")
    print(
        f"Task ID:     {task.task_id}\nCommand:     {task.command}\nType:        {task.task_type}\nPriority:    {task.priority}\nState:       {task.state.value}\n"
    )
    print(f"Created:     {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if task.scheduled_time:
        print(f"Scheduled:   {task.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if task.started_at:
        print(f"Started:     {task.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if task.completed_at:
        print(
            f"Completed:   {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}\nDuration:    {task.actual_duration_seconds:.1f}s"
        )
    if task.exit_code is not None:
        print(f"\nExit Code:   {task.exit_code}")
    if task.stdout:
        print(f"\nSTDOUT:\n───────\n{task.stdout}")
    if task.stderr:
        print(f"\nSTDERR:\n───────\n{task.stderr}")
    if task.error_message:
        print(f"\nError: {task.error_message}")
    if task.retry_count > 0:
        print(f"\nRetries: {task.retry_count}/{task.max_retries}")


def cmd_batch_daemon_start(args):
    try:
        from intelligence.process_monitor import BatchDaemon, ProcessMonitor
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    monitor = ProcessMonitor()
    daemon = BatchDaemon(
        queue=monitor.batch_queue, executor=monitor.batch_executor, process_monitor=monitor
    )
    result = daemon.start(interval_seconds=args.interval, foreground=not args.background)
    if result["success"]:
        if args.background:
            print(
                f"✓ Daemon started in background\n  PID: {result['pid']}\n  Interval: {result['interval']}s\n  Log file: {result['log_file']}"
            )
    else:
        print(f"✗ Failed to start daemon: {result['error']}")
        sys.exit(1)


def cmd_batch_daemon_stop(args):
    try:
        from intelligence.process_monitor import BatchDaemon
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    result = BatchDaemon().stop()
    if result["success"]:
        print(
            f"✓ Daemon stopped\n  PID: {result['pid']}"
            + ("\n  (force killed)" if result.get("forced") else "")
        )
    else:
        print(f"✗ {result['error']}")
        sys.exit(1)


def cmd_batch_daemon_status(args):
    try:
        from intelligence.process_monitor import BatchDaemon
    except ImportError:
        print("Error: Process Monitor not available")
        sys.exit(1)
    status = BatchDaemon().status()
    if status["running"]:
        print(
            f"✓ Daemon is running\n  PID: {status['pid']}\n  Uptime: {status['uptime']}\n  Started: {status['started_at']}"
        )
        if "cpu_percent" in status:
            print(f"  CPU: {status['cpu_percent']:.1f}%")
        if "memory_mb" in status:
            print(f"  Memory: {status['memory_mb']:.1f} MB")
        print(f"  Log file: {status['log_file']}")
    else:
        print(
            "✗ Daemon is not running"
            + (f"\n  (stale PID: {status['pid']})" if "pid" in status else "")
        )


def cmd_batch_stats(args):
    """Calculate real batch API savings from actual job data."""
    import json

    batch_results_dir = Path.home() / ".cortex" / "batch" / "results"
    if not batch_results_dir.exists():
        print("  No batch data yet. Run cortex batch fill first.")
        return
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
    BATCH_DISCOUNT = 0.50
    total_interactive = total_batch = 0.0
    job_count = request_count = 0
    models_seen: dict = {}
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
                total_interactive += interactive_cost
                total_batch += interactive_cost * BATCH_DISCOUNT
                request_count += 1
                models_seen[model] = models_seen.get(model, 0) + 1
                if not job_counted:
                    job_count += 1
                    job_counted = True
        except (json.JSONDecodeError, OSError):
            continue
    savings = total_interactive - total_batch
    pct = (savings / total_interactive * 100) if total_interactive > 0 else 0
    print(
        "+"
        + "=" * 54
        + "+\n|          CORTEX - BATCH API SAVINGS REPORT           |\n+"
        + "=" * 54
        + "+\n"
    )
    print(
        f"  Jobs analyzed:      {job_count}\n  Requests total:     {request_count}\n  Interactive cost:   ${total_interactive:.4f}\n  Batch cost:         ${total_batch:.4f}\n  Savings:            ${savings:.4f} ({pct:.0f}%)\n  Discount applied:   {BATCH_DISCOUNT * 100:.0f}%\n"
    )
    if models_seen:
        print("  Models used:")
        for model, count in sorted(models_seen.items(), key=lambda x: -x[1]):
            short = model.replace("claude-", "").replace("-20250514", "").replace("-20251001", "")
            print(f"    {short:20} {count:>5} requests")


def cmd_batch_fill(args):
    """Fill overnight batch queue intelligently from GOALS.md and pending work."""
    try:
        from batch.overnight_filler import OvernightFiller

        filler = OvernightFiller()
        result = filler.fill(max_jobs=getattr(args, "max_jobs", None))
        print(f"Queued {result.get('queued', 0)} jobs for overnight batch processing.")
    except ImportError:
        print("Error: overnight batch filler not available.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ── work absorber ─────────────────────────────────────────────────────────────


def cmd_work_absorb(args):
    from datetime import datetime, timedelta
    from work_absorber import WorkAbsorber

    absorber = WorkAbsorber()
    since = None
    if args.since:
        try:
            since = datetime.fromisoformat(args.since)
        except ValueError:
            try:
                days = int(args.since.rstrip("d"))
                since = datetime.now() - timedelta(days=days)  # noqa: DTZ005
            except ValueError:
                print(f"Invalid date format: {args.since}")
                sys.exit(1)
    projects = [args.project] if args.project else None
    print("Starting work absorption...")
    report = absorber.absorb(projects=projects, since=since, incremental=not args.full)
    print(f"\n✓ Absorption complete ({report.duration_seconds:.1f}s)")
    print(
        f"  Signals detected: {report.signals_detected}\n  Signals absorbed: {report.signals_absorbed}"
    )
    print(f"  Work items: {report.work_items_created} new, {report.work_items_updated} updated")
    print(
        f"  Plan correlations: {report.correlations_made}\n  Drifts detected: {report.drifts_detected}"
    )
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
    from work_absorber import WorkAbsorber

    absorber = WorkAbsorber()
    status = absorber.get_status()
    print("╔══════════════════════════════════════════════════════╗")
    print("║            WORK ABSORBER - STATUS                    ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    storage = status.get("storage", {})
    print(f"Total signals: {storage.get('total_signals', 0)}")
    print(f"Total work items: {storage.get('total_work_items', 0)}")
    print(f"Unresolved drifts: {storage.get('unresolved_drifts', 0)}")
    last = status.get("last_absorption")
    if last:
        print(f"\nLast absorption: {last.get('time', 'Unknown')}")
        print(
            f"  Signals: {last.get('signals', 0)}\n  Work items: {last.get('items', 0)}\n  Drifts: {last.get('drifts', 0)}"
        )
    else:
        print("\nNo absorption run yet")
    by_project = storage.get("by_project", {})
    if by_project:
        print("\nBy project:")
        for project, count in sorted(by_project.items(), key=lambda x: -x[1]):
            print(f"  {project}: {count} work items")


def cmd_work_items(args):
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
            f"  Time: {item.first_seen.strftime('%Y-%m-%d %H:%M')} - {item.last_activity.strftime('%Y-%m-%d %H:%M')}\n"
        )


def cmd_work_drift(args):
    from work_absorber import WorkAbsorber

    absorber = WorkAbsorber()
    if args.resolve:
        absorber.storage.resolve_drift(args.resolve, args.notes or "")
        print(f"✓ Drift {args.resolve} resolved")
        return
    summary = absorber.get_drift_summary(project=args.project)
    if summary["total"] == 0:
        print("No unresolved drifts detected")
        return
    print(f"Plan Drift ({summary['total']} unresolved):\n")
    for drift_type, count in sorted(summary.get("by_type", {}).items()):
        print(f"  {drift_type}: {count}")
    print()
    for drift in summary["drifts"]:
        icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(drift.severity, "○")
        print(f"\n{icon} [{drift.drift_type.value}] {drift.description}")
        print(f"  Project: {drift.project} | ID: {drift.id}")
        print(f"  Suggested: {drift.suggested_action}")


def cmd_work_report(args):
    from datetime import datetime, timedelta
    from work_absorber import WorkAbsorber

    absorber = WorkAbsorber()
    items = absorber.get_recent_work(days=args.days)
    drifts = absorber.storage.get_unresolved_drifts()
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║      WORK ABSORPTION REPORT ({args.days} days)              ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    correlated = sum(1 for i in items if i.plan_step_id)
    print(
        f"Work items: {len(items)}\n  Correlated to plans: {correlated}\n  Unplanned work: {len(items) - correlated}"
    )
    print(f"\nDrifts: {len(drifts)} unresolved\n")
    by_project: dict = {}
    for item in items:
        by_project.setdefault(item.project, []).append(item)
    print("By project:")
    for project in sorted(by_project.keys()):
        project_items = by_project[project]
        print(f"\n  {project}: {len(project_items)} work items")
        for item in project_items[:5]:
            status = "✓" if item.plan_step_id else "○"
            print(f"    {status} {item.title[:50]}")
    if items:
        print("\nRecent highlights:")
        for item in items[:5]:
            print(f"  - {item.title} ({item.project})")


# ── V2 Prime / graph / interventions / IAP ────────────────────────────────────


def cmd_v2_status(args):
    from bridge import CortexBridge

    bridge = CortexBridge()
    status = bridge.get_v2_status()
    print(
        "+"
        + "=" * 54
        + "+\n|          CORTEX V2 PRIME - SYSTEM STATUS             |\n+"
        + "=" * 54
        + "+\n"
    )
    print("3-ENGINE ACTIVE MODEL\n" + "-" * 30)
    for name, active, desc in [
        ("Engine A: Absorber", status.get("absorber", False), "Signal ingestion"),
        ("Engine B: Synthesis", status.get("synthesis", False), "Graph processing"),
        ("Engine C: Broker", status.get("broker", False), "Interventions"),
        ("IAP Handler", status.get("iap", False), "Agent protocol"),
    ]:
        print(f"  {'[OK]' if active else '[--]'} {name}: {desc}")
    print()
    graph_stats = status.get("graph_stats")
    if graph_stats and "error" not in graph_stats:
        print(f"CONTEXT GRAPH\n{'-' * 30}")
        print(
            f"  Nodes: {graph_stats.get('total_nodes', 0)}\n  Edges: {graph_stats.get('total_edges', 0)}"
        )
        if graph_stats.get("nodes_by_type"):
            print("  By type:")
            for ntype, count in graph_stats["nodes_by_type"].items():
                print(f"    {ntype}: {count}")
        print()
    broker_status = status.get("broker_status")
    if broker_status and "error" not in broker_status:
        print(f"ACTION BROKER\n{'-' * 30}")
        print(f"  Total interventions: {broker_status.get('total_interventions', 0)}")
        print(f"  Pending: {broker_status.get('pending_count', 0)}")
        by_sev = broker_status.get("by_severity", {})
        if any(by_sev.values()):
            print("  By severity:")
            for sev in ["critical", "high", "medium", "low", "info"]:
                if by_sev.get(sev, 0) > 0:
                    print(f"    {sev}: {by_sev[sev]}")
    v2_ok = (
        "[OK] V2 Prime Operational" if status.get("v2_available") else "[--] V2 Prime Unavailable"
    )
    print(f"\n{v2_ok}")


def cmd_graph_query(args):
    import json
    from bridge import CortexBridge

    bridge = CortexBridge()
    result = bridge.query_graph(args.node_type) if args.node_type else bridge.get_graph_stats()
    print(json.dumps(result, indent=2, default=str))


def cmd_graph_add(args):
    import json
    from bridge import CortexBridge

    bridge = CortexBridge()
    data: dict = {}
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            data = {"description": args.data}
    result = bridge.add_graph_node(args.node_type, args.name, data)
    print(
        f"{'[OK] Node added: ' + result['node_id'] if result.get('success') else '[FAIL] ' + result.get('error', '?')}"
    )


def cmd_graph_related(args):
    import json
    from bridge import CortexBridge

    bridge = CortexBridge()
    print(json.dumps(bridge.get_related_nodes(args.node_id, args.edge_type), indent=2, default=str))


def cmd_graph_import(args):
    from bridge import CortexBridge

    bridge = CortexBridge()
    if not bridge.synthesis:
        print("[FAIL] V2 Prime Synthesis Core not available")
        return
    portfolio_path = Path.home() / ".claude" / "portfolio"
    print(f"Importing from {portfolio_path}...")
    result = bridge.synthesis.import_portfolio_data(portfolio_path)
    print("\nImport complete:")
    for category, count in result.items():
        print(f"  {category}: {count}")
    stats = bridge.get_graph_stats()
    print(
        f"\nGraph now has {stats.get('total_nodes', 0)} nodes and {stats.get('total_edges', 0)} edges"
    )


def cmd_interventions_list(args):
    from bridge import CortexBridge

    bridge = CortexBridge()
    interventions = bridge.get_pending_interventions()
    if not interventions or (len(interventions) == 1 and "error" in interventions[0]):
        print("No pending interventions")
        return
    print(f"Pending Interventions ({len(interventions)}):\n")
    sev_icons = {"critical": "[!]", "high": "[*]", "medium": "[+]", "low": "[-]", "info": "[i]"}
    for i in interventions:
        icon = sev_icons.get(i.get("severity", "info"), "[?]")
        print(
            f"{icon} {i.get('title', 'Unknown')}\n    Type: {i.get('type')}\n    ID: {i.get('id')}"
        )
        if desc := i.get("description"):
            print(f"    {desc[:80] + '...' if len(desc) > 80 else desc}")
        print()


def cmd_interventions_ack(args):
    from bridge import CortexBridge

    bridge = CortexBridge()
    result = bridge.acknowledge_intervention(args.id)
    print(
        f"{'[OK] Intervention ' + args.id + ' acknowledged' if result.get('success') else '[FAIL] ' + result.get('error', '?')}"
    )


def cmd_interventions_suppress(args):
    from bridge import CortexBridge

    bridge = CortexBridge()
    result = bridge.suppress_intervention(args.id, args.hours)
    print(
        f"{'[OK] Intervention ' + args.id + ' suppressed for ' + str(args.hours) + ' hours' if result.get('success') else '[FAIL] ' + result.get('error', '?')}"
    )


def cmd_iap_send(args):
    import json
    from bridge import CortexBridge

    bridge = CortexBridge()
    message = {
        "message_type": args.type,
        "payload": {"query": args.payload, "query_type": args.query_type or "context"},
    }
    print(json.dumps(bridge.handle_iap_message(message), indent=2, default=str))


# ── runtime ───────────────────────────────────────────────────────────────────


def cmd_runtime_start(args):
    try:
        from cortex.runtime import RuntimeExecutor
        from cortex.runtime.config import get_config

        config = get_config()
        print(f"Starting Cortex Runtime on {config.host}:{config.port}...")
        RuntimeExecutor(config).start()
    except ImportError as e:
        print(f"Error: Runtime module not available: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting runtime: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_runtime_status(args):
    import json as json_mod
    import urllib.error
    import urllib.request

    try:
        from cortex.runtime.config import get_config

        config = get_config()
        url = f"http://{config.host}:{config.port}/api/v1/runtime/health"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json_mod.loads(response.read().decode())
                print(
                    "╔══════════════════════════════════════════════════════╗\n║              CORTEX RUNTIME STATUS                   ║\n╚══════════════════════════════════════════════════════╝"
                )
                print(
                    f"Status: {data.get('status', 'unknown')}\nUptime: {data.get('uptime_seconds', 0):.0f}s\nAgents: {data.get('registered_agents', 0)}"
                )
                if args.json:
                    print(json_mod.dumps(data, indent=2))
        except urllib.error.URLError:
            print("Runtime is not running.\nStart with: cortex runtime start")
            sys.exit(1)
    except ImportError as e:
        print(f"Error: Runtime module not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_runtime_agents(args):
    import json as json_mod
    import urllib.error
    import urllib.request

    try:
        from cortex.runtime.config import get_config

        config = get_config()
        url = f"http://{config.host}:{config.port}/api/v1/runtime/agents"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json_mod.loads(response.read().decode())
                if args.json:
                    print(json_mod.dumps(data, indent=2))
                    return
                agents = data.get("agents", [])
                print("Registered Agents:\n" + "─" * 60)
                if not agents:
                    print("  No agents registered")
                else:
                    for agent in agents:
                        icon = "●" if agent.get("status") == "idle" else "○"
                        print(
                            f"  {icon} {agent['agent_id']}: {agent.get('name', 'Unnamed')}\n      Schedule: {agent.get('schedule', 'manual')}"
                        )
        except urllib.error.URLError:
            print("Runtime is not running.")
            sys.exit(1)
    except ImportError as e:
        print(f"Error: Runtime module not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_runtime_trigger(args):
    import json as json_mod
    import urllib.error
    import urllib.request

    try:
        from cortex.runtime.config import get_config

        config = get_config()
        url = f"http://{config.host}:{config.port}/api/v1/runtime/agents/{args.agent_id}/trigger"
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
    import json as json_mod
    import urllib.error
    import urllib.request

    try:
        from cortex.runtime.config import get_config

        config = get_config()
        limit = getattr(args, "limit", 20)
        url = f"http://{config.host}:{config.port}/api/v1/runtime/history?limit={limit}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json_mod.loads(response.read().decode())
                if args.json:
                    print(json_mod.dumps(data, indent=2))
                    return
                print("Execution History:\n" + "─" * 70)
                for e in data.get("executions", []) or [{"_empty": True}]:
                    if "_empty" in e:
                        print("  No execution history")
                        break
                    status = "✓" if e.get("success") else "✗"
                    print(
                        f"  {status} [{e.get('start_time', '')[:19]}] {e.get('agent_id', 'unknown')} ({e.get('duration_seconds', 0):.1f}s)"
                    )
        except urllib.error.URLError:
            print("Runtime not running. Querying history database directly...")
            try:
                from cortex.runtime.storage.history import ExecutionHistory

                for e in ExecutionHistory().get_recent_executions(limit=limit):
                    status = "✓" if e.get("success") else "✗"
                    print(
                        f"  {status} [{e.get('start_time', '')[:19]}] {e.get('agent_id', 'unknown')} ({e.get('duration_seconds', 0):.1f}s)"
                    )
            except Exception as db_err:
                print(f"Could not access history: {db_err}")
                sys.exit(1)
    except ImportError as e:
        print(f"Error: Runtime module not available: {e}", file=sys.stderr)
        sys.exit(1)


# ── sessions / signals / doctor ───────────────────────────────────────────────


def cmd_sessions(args):
    from bridge import CortexBridge

    bridge = CortexBridge()
    active_only = getattr(args, "active", False)
    try:
        result = bridge._get(f"/sessions?active_only={'true' if active_only else 'false'}")
    except Exception:
        print("Bridge unavailable. Start with: python api/bridge_endpoint.py")
        sys.exit(1)
    sessions = result.get("sessions", [])
    print(
        "+"
        + "=" * 54
        + "+\n|          CORTEX - SESSION MONITOR                     |\n+"
        + "=" * 54
        + "+\n"
    )
    print(f"  Sessions: {result.get('active_count', 0)} active / {result.get('total', 0)} total\n")
    for s in sessions[:10]:
        state = s.get("state", "unknown").upper()
        icon = "*" if state == "ACTIVE" else "o" if state == "IDLE" else "."
        print(
            f"  {icon} [{state:7}] {s.get('project', 'unknown'):30} {s.get('age_display', '?'):>10}  {s.get('session_id', '?')[:12]}"
        )
    if not sessions:
        print("  No sessions found.")
    print()


def cmd_signals(args):
    try:
        from intelligence.signals import SignalDetector
    except ImportError:
        print("Error: Signal detection not available", file=sys.stderr)
        sys.exit(1)
    severity_filter = getattr(args, "severity", None)
    try:
        detector = SignalDetector(root_dir=args.root)
        signals = detector.detect_all()
        print(
            "+"
            + "=" * 54
            + "+\n|      CORTEX - CROSS-PROJECT SIGNAL DETECTION          |\n+"
            + "=" * 54
            + "+\n"
        )
        if not signals:
            print("  No signals detected. All clear.\n")
            return
        by_severity: dict = {}
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
            print()
        displayed = sum(
            len(by_severity.get(sev, []))
            for sev in ["critical", "high", "medium", "low"]
            if not severity_filter or sev == severity_filter
        )
        print(f"  Total: {displayed} signals across {len(by_severity)} severity levels\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_doctor(args):
    import socket

    checks = []
    vi = sys.version_info
    checks.append(
        ("Python >= 3.11", (vi.major, vi.minor) >= (3, 11), f"{vi.major}.{vi.minor}.{vi.micro}")
    )
    for pkg, name in [("anthropic", "anthropic"), ("sklearn", "sklearn")]:
        try:
            mod = __import__(pkg)
            checks.append((f"{name} importable", True, mod.__version__))
        except ImportError as e:
            checks.append((f"{name} importable", False, str(e)))
    import os

    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    checks.append(("ANTHROPIC_API_KEY set", key_set, "set" if key_set else "missing"))
    cortex_home = Path.home() / ".cortex"
    checks.append(("~/.cortex/ exists", cortex_home.exists(), str(cortex_home)))
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
    print(
        "+" + "=" * width + "+\n|  CORTEX DOCTOR" + " " * (width - 15) + "|\n+" + "=" * width + "+"
    )
    for label, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    print("+" + "=" * width + "+")
    print("  All checks passed." if all_pass else "  Some checks FAILED. Fix issues above.")
    sys.exit(0 if all_pass else 1)


# ── subparser registration helpers ────────────────────────────────────────────


def register_process_cmds(subparsers) -> None:
    """Register process monitoring subcommands."""
    process_parser = subparsers.add_parser("process", help="Process monitoring and optimization")
    subs = process_parser.add_subparsers(dest="process_command", help="Process commands")
    subs.add_parser("status", help="Show current process status").set_defaults(
        func=cmd_process_status
    )
    subs.add_parser("waste", help="Show detected resource waste").set_defaults(
        func=cmd_process_waste
    )
    subs.add_parser("optimize", help="Show optimization suggestions").set_defaults(
        func=cmd_process_optimize
    )
    ins_p = subs.add_parser("insights", help="Show utilization insights")
    ins_p.add_argument("--days", type=int, default=7)
    ins_p.set_defaults(func=cmd_process_insights)


def register_batch_local_cmds(subparsers) -> None:
    """Register batch local queue subcommands."""
    batch_parser = subparsers.add_parser("batch", help="Batch task scheduling and execution")
    subs = batch_parser.add_subparsers(dest="batch_command", help="Batch commands")

    p = subs.add_parser("add", help="Add a task to the batch queue")
    p.add_argument("command", help="Command to execute")
    p.add_argument("--type", dest="task_type", default="general")
    p.add_argument("--description", default="")
    p.add_argument("--priority", default="normal", choices=["immediate", "high", "normal", "low"])
    p.add_argument("--duration", type=float, default=10.0)
    p.set_defaults(func=cmd_batch_add)

    p = subs.add_parser("submit", help="Submit job (auto-routes to correct backend)")
    p.add_argument("job_file", type=Path)
    p.set_defaults(func=cmd_batch_submit)

    p = subs.add_parser("list", help="List batch tasks (both backends)")
    p.add_argument("--backend", choices=["local", "api", "both"], default="both")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_batch_list)

    subs.add_parser("status", help="Show batch queue status").set_defaults(
        func=cmd_batch_queue_status
    )
    subs.add_parser("schedule", help="Schedule pending tasks").set_defaults(func=cmd_batch_schedule)
    subs.add_parser("run", help="Execute scheduled tasks").set_defaults(func=cmd_batch_run)

    p = subs.add_parser("cancel", help="Cancel a task")
    p.add_argument("task_id")
    p.set_defaults(func=cmd_batch_cancel)

    p = subs.add_parser("logs", help="Show task execution logs")
    p.add_argument("task_id")
    p.set_defaults(func=cmd_batch_logs)

    p = subs.add_parser("fill", help="Fill overnight batch queue intelligently")
    p.add_argument("--max-jobs", type=int, default=None)
    p.set_defaults(func=cmd_batch_fill)

    subs.add_parser("stats", help="Show batch API cost savings").set_defaults(func=cmd_batch_stats)

    daemon_parser = subs.add_parser("daemon", help="Daemon management")
    daemon_subs = daemon_parser.add_subparsers(dest="daemon_command")
    p = daemon_subs.add_parser("start")
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--background", action="store_true")
    p.set_defaults(func=cmd_batch_daemon_start)
    daemon_subs.add_parser("stop").set_defaults(func=cmd_batch_daemon_stop)
    daemon_subs.add_parser("status").set_defaults(func=cmd_batch_daemon_status)


def register_work_cmds(subparsers) -> None:
    """Register work absorber subcommands."""
    work_parser = subparsers.add_parser(
        "work", help="Work absorber - track progress across projects"
    )
    subs = work_parser.add_subparsers(dest="work_command")

    p = subs.add_parser("absorb", help="Run absorption cycle")
    p.add_argument("--project", "-p")
    p.add_argument("--since", "-s")
    p.add_argument("--full", action="store_true")
    p.set_defaults(func=cmd_work_absorb)

    subs.add_parser("status", help="Show absorber status").set_defaults(func=cmd_work_status)

    p = subs.add_parser("items", help="List work items")
    p.add_argument("--project", "-p")
    p.add_argument("--status", "-s", choices=["detected", "absorbed", "correlated", "orphaned"])
    p.add_argument("--days", "-d", type=int, default=7)
    p.add_argument("--limit", "-l", type=int, default=20)
    p.set_defaults(func=cmd_work_items)

    p = subs.add_parser("drift", help="Show plan drift")
    p.add_argument("--project", "-p")
    p.add_argument("--resolve", "-r")
    p.add_argument("--notes", "-n")
    p.set_defaults(func=cmd_work_drift)

    p = subs.add_parser("report", help="Generate absorption report")
    p.add_argument("--days", "-d", type=int, default=7)
    p.set_defaults(func=cmd_work_report)


def register_v2_cmds(subparsers) -> None:
    """Register v2, graph, interventions, iap subcommands."""
    # v2
    v2 = subparsers.add_parser("v2", help="V2 Prime system commands")
    v2_subs = v2.add_subparsers(dest="v2_command")
    v2_subs.add_parser("status").set_defaults(func=cmd_v2_status)

    # graph
    graph = subparsers.add_parser("graph", help="Context graph operations")
    graph_subs = graph.add_subparsers(dest="graph_command")
    p = graph_subs.add_parser("query")
    p.add_argument("--type", "-t", dest="node_type")
    p.set_defaults(func=cmd_graph_query)
    p = graph_subs.add_parser("add")
    p.add_argument("node_type")
    p.add_argument("name")
    p.add_argument("--data", "-d")
    p.set_defaults(func=cmd_graph_add)
    p = graph_subs.add_parser("related")
    p.add_argument("node_id")
    p.add_argument("--edge-type", "-e", dest="edge_type")
    p.set_defaults(func=cmd_graph_related)
    graph_subs.add_parser("import").set_defaults(func=cmd_graph_import)

    # interventions
    int_p = subparsers.add_parser("interventions", help="Intervention management")
    int_subs = int_p.add_subparsers(dest="int_command")
    int_subs.add_parser("list").set_defaults(func=cmd_interventions_list)
    p = int_subs.add_parser("ack")
    p.add_argument("id")
    p.set_defaults(func=cmd_interventions_ack)
    p = int_subs.add_parser("suppress")
    p.add_argument("id")
    p.add_argument("--hours", type=int, default=24)
    p.set_defaults(func=cmd_interventions_suppress)

    # iap
    iap = subparsers.add_parser("iap", help="Inter-Agent Protocol commands")
    iap_subs = iap.add_subparsers(dest="iap_command")
    p = iap_subs.add_parser("send")
    p.add_argument("type", choices=["query", "handoff", "ack"])
    p.add_argument("payload")
    p.add_argument("--query-type", "-q", dest="query_type")
    p.set_defaults(func=cmd_iap_send)


def register_runtime_cmds(subparsers) -> None:
    """Register runtime executor subcommands."""
    runtime = subparsers.add_parser("runtime", help="Runtime executor management")
    subs = runtime.add_subparsers(dest="runtime_command")
    subs.add_parser("start").set_defaults(func=cmd_runtime_start)

    p = subs.add_parser("status")
    p.add_argument("--json", "-j", action="store_true")
    p.set_defaults(func=cmd_runtime_status)

    p = subs.add_parser("agents")
    p.add_argument("--json", "-j", action="store_true")
    p.set_defaults(func=cmd_runtime_agents)

    p = subs.add_parser("trigger")
    p.add_argument("agent_id")
    p.set_defaults(func=cmd_runtime_trigger)

    p = subs.add_parser("history")
    p.add_argument("--limit", "-n", type=int, default=20)
    p.add_argument("--json", "-j", action="store_true")
    p.set_defaults(func=cmd_runtime_history)


# ── reflect ───────────────────────────────────────────────────────────────────


def cmd_reflect_run(args):
    """Run nightly reflection pipeline."""
    dry_run = getattr(args, "dry_run", False)
    try:
        _cortex = Path(__file__).resolve().parent.parent.parent
        if str(_cortex) not in sys.path:
            sys.path.insert(0, str(_cortex))
        if str(_cortex.parent) not in sys.path:
            sys.path.insert(0, str(_cortex.parent))
        from batch.nightly_reflection import NightlyReflection
    except ImportError as exc:
        print(f"Error: could not import NightlyReflection — {exc}")
        return

    nr = NightlyReflection()
    reflection = nr.run(dry_run=dry_run)
    if reflection.get("error"):
        print(f"Warning: {reflection['error']}")
    themes = reflection.get("themes", [])
    print(f"Reflection complete. Themes: {', '.join(themes) if themes else 'none'}")


def cmd_reflect_status(args):
    """Show last reflection date/status."""
    try:
        _cortex = Path(__file__).resolve().parent.parent.parent
        if str(_cortex) not in sys.path:
            sys.path.insert(0, str(_cortex))
        if str(_cortex.parent) not in sys.path:
            sys.path.insert(0, str(_cortex.parent))
        from batch.nightly_reflection import NightlyReflection
    except ImportError as exc:
        print(f"Error: could not import NightlyReflection — {exc}")
        return

    nr = NightlyReflection()
    print(nr.status())


def register_reflect_cmds(subparsers) -> None:
    """Register 'reflect' subcommands."""
    reflect = subparsers.add_parser("reflect", help="Nightly reflection pipeline")
    subs = reflect.add_subparsers(dest="reflect_command")

    p = subs.add_parser("run", help="Run nightly reflection now")
    p.add_argument("--dry-run", action="store_true", help="Skip API call and memory seeding")
    p.set_defaults(func=cmd_reflect_run)

    subs.add_parser("status", help="Show last reflection status").set_defaults(
        func=cmd_reflect_status
    )

    # Top-level flags routed directly from 'cortex reflect --run / --status'
    reflect.add_argument("--run", action="store_true", help="Run nightly reflection")
    reflect.add_argument("--dry-run", action="store_true", help="Dry run (no API call)")
    reflect.add_argument("--status", action="store_true", help="Show last reflection status")

    def _reflect_dispatch(args):
        if getattr(args, "status", False):
            cmd_reflect_status(args)
        else:
            cmd_reflect_run(args)

    reflect.set_defaults(func=_reflect_dispatch)
