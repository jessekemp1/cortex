"""CLI entry point: python -m supervisor (from cortex directory)."""

import argparse
import json
from pathlib import Path


def cmd_orchestrate(args):
    """Run one orchestration cycle."""
    from supervisor.config import SupervisorConfig
    from supervisor.core import CortexSupervisor

    config = SupervisorConfig(dry_run=args.dry_run)
    supervisor = CortexSupervisor(config=config)

    work_items = None
    if args.project:
        from supervisor.intake import WorkIntake

        intake = WorkIntake()
        work_items = [wi for wi in intake.discover_all() if wi.project == args.project]

    if args.max_items and work_items is not None:
        work_items = work_items[: args.max_items]

    result = supervisor.orchestrate(work_items)
    print(json.dumps(result, indent=2))


def cmd_status(_args):
    """Show recent orchestration runs."""
    runs_dir = Path.home() / ".cortex" / "orchestration" / "runs"
    if not runs_dir.exists():
        print("No orchestration runs found.")
        return

    run_dirs = sorted(runs_dir.iterdir(), reverse=True)[:10]
    if not run_dirs:
        print("No orchestration runs found.")
        return

    print(f"Recent runs ({len(run_dirs)} of {len(list(runs_dir.iterdir()))}):\n")
    for run_dir in run_dirs:
        summary_file = run_dir / "summary.json"
        if summary_file.exists():
            data = json.loads(summary_file.read_text(encoding="utf-8"))
            total = data.get("total", 0)
            ok = data.get("succeeded", 0)
            fail = data.get("failed", 0)
            tokens = data.get("total_tokens", 0)
            dur = data.get("total_duration_seconds", 0)
            models = data.get("model_breakdown", {})
            model_str = ", ".join(f"{k}:{v}" for k, v in models.items()) or "-"
            print(
                f"  {run_dir.name}  {ok}/{total} ok  {fail} fail  {tokens} tok  {dur:.1f}s  [{model_str}]"
            )
        else:
            print(f"  {run_dir.name}  (no summary)")


def cmd_daemon(args):
    """Run supervisor in daemon mode."""
    from supervisor.core import CortexSupervisor

    supervisor = CortexSupervisor()
    print(f"Starting supervisor daemon (interval={args.interval}s, Ctrl+C to stop)")
    supervisor.start(foreground=True, interval_seconds=args.interval)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m supervisor", description="Cortex Supervisor CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # orchestrate
    p_orch = sub.add_parser("orchestrate", help="Run one orchestration cycle")
    p_orch.add_argument("--dry-run", action="store_true", help="Route but don't dispatch")
    p_orch.add_argument("--max-items", type=int, default=None, help="Max items to process")
    p_orch.add_argument("--project", type=str, default="", help="Filter by project")

    # status
    sub.add_parser("status", help="Show recent orchestration runs")

    # daemon
    p_daemon = sub.add_parser("daemon", help="Run in daemon mode")
    p_daemon.add_argument("--interval", type=int, default=30, help="Tick interval in seconds")

    args = parser.parse_args()

    if args.command == "orchestrate":
        cmd_orchestrate(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "daemon":
        cmd_daemon(args)


if __name__ == "__main__":
    main()
