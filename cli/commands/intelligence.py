"""Intelligence commands: deep, quick, auto, intelligence, portfolio, deps, config, tooling."""

import sys
from datetime import datetime
from pathlib import Path

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
            print("\n⚠️  Quick mode not yet fully implemented")
            print(f"   Error: {result['error']}\n")
            print("💡 Suggestion: Use 'cortex deep' for comprehensive analysis")
            print("   (Deep mode is only 2-5s and provides much more context)\n")
            sys.exit(0)  # Not a failure - just not implemented yet

        # Display results
        display_quick_intelligence(result)

    except Exception as e:
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


def cmd_intelligence(args):
    """Query Cortex intelligence for context, patterns, and recommendations."""
    from cli.commands._helpers import require_api_key

    require_api_key()

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
