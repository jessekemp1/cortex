#!/usr/bin/env python3
"""
Trust Status CLI

Displays trust levels for all domains in a compact, color-coded table.
Designed for the `cxt` shell alias and iTerm2 status bar.

Usage:
    python cortex/scripts/trust_status.py
    python cortex/scripts/trust_status.py --json     # Machine-readable output

No network required — reads from local SQLite only.
"""

import json
import sys
from pathlib import Path

# Allow direct execution from any directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from cortex.engines.workstream_orchestrator import WorkstreamOrchestrator
except ImportError:
    from engines.workstream_orchestrator import WorkstreamOrchestrator

# ANSI color codes
RED = "\033[31m"
ORANGE = "\033[33m"
YELLOW = "\033[93m"
GREEN = "\033[32m"
BRIGHT_GREEN = "\033[92m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

LEVEL_COLORS = [RED, ORANGE, YELLOW, GREEN, BRIGHT_GREEN]
LEVEL_ICONS = ["🔴", "🟠", "🟡", "🟢", "💚"]
LEVEL_NAMES = [
    "VERIFY_ALL",
    "SPOT_CHECK",
    "TRUST_VERIFY",
    "AUTO_GUARDRAILS",
    "FULL_AUTONOMY",
]


def render_trust_table(summary: dict, use_color: bool = True) -> str:
    """Render trust summary as a compact ANSI table."""
    domains = summary.get("domains", {})
    aggregate = summary.get("aggregate", {})

    if not domains:
        return "  ⚠  No trust data yet. Run: python cortex/scripts/seed_trust.py"

    lines = []
    lines.append(f"\n{BOLD}  Trust Levels{RESET}" if use_color else "\n  Trust Levels")
    lines.append("  " + "─" * 58)

    for domain, info in sorted(domains.items()):
        level = info["level"]
        accuracy = info["accuracy"]
        outcomes = info["outcomes"]
        streak = info.get("streak", 0)

        icon = LEVEL_ICONS[level]
        color = LEVEL_COLORS[level] if use_color else ""
        reset = RESET if use_color else ""

        acc_pct = f"{accuracy * 100:.0f}%"
        streak_str = f"  ↑{streak}" if streak >= 5 else ""

        lines.append(
            f"  {icon} {color}{domain:<20}{reset}"
            f"  L{level}  {acc_pct:>5} acc  {outcomes:>3} outcomes{streak_str}"
        )

    lines.append("  " + "─" * 58)

    avg_level = aggregate.get("avg_trust_level", 0)
    avg_acc = aggregate.get("avg_accuracy", 0)
    total = aggregate.get("total_outcomes", 0)
    tracked = aggregate.get("domains_tracked", 0)

    lines.append(
        f"\n  📊 Portfolio trust: L{avg_level:.1f} avg  "
        f"({avg_acc * 100:.0f}% accuracy, {total} outcomes, {tracked} domains)\n"
    )

    return "\n".join(lines)


def main():
    use_json = "--json" in sys.argv
    use_color = not use_json and sys.stdout.isatty()

    try:
        orchestrator = WorkstreamOrchestrator()
        summary = orchestrator.get_trust_summary()
    except Exception as e:
        print(f"  ⚠ Could not load trust data: {e}", file=sys.stderr)
        sys.exit(1)

    if use_json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_trust_table(summary, use_color=use_color))


if __name__ == "__main__":
    main()
