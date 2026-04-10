"""Briefing commands: briefing, briefing_style, statusline, reflect."""

import json
import subprocess
import sys
from pathlib import Path

from briefing import (
    format_briefing,
    format_briefing_json,
    format_compact,
    format_statusline,
    format_statusline_json,
    generate_daily_briefing,
    get_briefing_signal_quality,
    get_briefing_style,
    get_briefing_style_path,
    validate_briefing_style,
)

try:
    from ai_intelligence import ProjectScanner
except ImportError:
    ProjectScanner = None


def cmd_briefing(args):
    """Generate and display daily briefing."""
    from cli.commands._helpers import _apply_signal_gate_to_briefing

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

    # --compact: fast action-first 12-line terminal box
    if getattr(args, "compact", False):
        try:
            root = Path(args.root)
            briefing = generate_daily_briefing(root_dir=root)
            print(format_compact(briefing, use_color=not getattr(args, "no_color", False)))
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

        # Generate briefing — always via resilient path (Tier 1 = normal, graceful fallback)
        try:
            from briefing_resilient import (
                generate_resilient_briefing,
                format_resilient_briefing,
            )

            resilient_result = generate_resilient_briefing(root_dir=root)
            tier = resilient_result.get("tier", 3)
            data = resilient_result.get("data", {})

            if tier == 1:
                briefing = data.get("briefing_object")
                if briefing is None:
                    raise RuntimeError("Tier 1 returned no briefing object")
            else:
                # Degraded mode — print fallback and return early
                for w in resilient_result.get("warnings", []):
                    print(f"[cortex] {w}", file=sys.stderr)
                print(format_resilient_briefing(resilient_result, use_color=not args.no_color))
                if watch_output:
                    print("\n--- Watch Tasks ---")
                    print(watch_output)
                return

        except ImportError:
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
