"""
Compact CLI output — the `git status` of your dev portfolio.

`cortex` (no args) → 4 lines
`cortex --alerts`  → alert detail
`cortex --goals`   → goal progress
`cortex --batch`   → batch health
`cortex --git`     → working tree detail
`cortex --full`    → falls through to full briefing
"""

import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console

# Allow imports from cortex root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tui.data import CortexSnapshot, collect_snapshot

BAR_CHARS = "░▏▎▍▌▊▉█"

console = Console()


def spark_bar(value: int, max_val: int, width: int = 6) -> str:
    if max_val == 0:
        return "░" * width
    ratio = min(value / max_val, 1.0)
    full = int(ratio * width)
    remainder = (ratio * width) - full
    partial_idx = int(remainder * (len(BAR_CHARS) - 1))
    bar = "█" * full
    if full < width:
        bar += BAR_CHARS[partial_idx]
        bar += "░" * (width - full - 1)
    return bar[:width]


def progress_bar(pct: int, width: int = 10) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _color_for_trend(trend: str) -> str:
    return {"hot": "bold red", "active": "bold yellow", "steady": "cyan", "idle": "dim"}.get(
        trend, "white"
    )


def _color_for_severity(sev: str) -> str:
    return {"critical": "bold red", "warning": "yellow", "ok": "green"}.get(sev, "white")


def _color_for_priority(pri: str) -> str:
    return {"P1": "bold red", "P2": "yellow"}.get(pri, "white")


# ── Views ──────────────────────────────────────────────────────────


def render_default(snap: CortexSnapshot):
    """4-line compact summary."""
    now = datetime.now().strftime("%a %b %d")

    # Line 1: header
    console.print(f"\n[bold cyan]cortex[/] — {now}\n")

    # Line 2: project sparklines
    active = [p for p in snap.projects if p.commits_7d > 0]
    if not active:
        active = snap.projects[:3]
    max_c = max((p.commits_7d for p in active), default=1) or 1
    parts = []
    for p in active[:5]:
        bar = spark_bar(p.commits_7d, max_c, 4)
        color = _color_for_trend(p.trend)
        parts.append(f"[{color}]{p.name:<8}[/]{bar} {p.commits_7d:>2}c")
    idle = sum(1 for p in snap.projects if p.commits_7d == 0)
    line = "  ".join(parts)
    if idle:
        line += f"  [dim]+{idle} idle[/]"
    console.print(f"  {line}")

    # Line 3: key metrics
    crit = sum(1 for a in snap.alerts if a.severity == "critical")
    warn = sum(1 for a in snap.alerts if a.severity == "warning")
    alert_str = ""
    if crit:
        alert_str += f"[bold red]{crit} crit[/]"
    if warn:
        alert_str += f" [yellow]{warn} warn[/]"
    if not alert_str:
        alert_str = "[green]clear[/]"

    goals_active = len(snap.goals)
    console.print(
        f"  [white]{snap.git.branch}[/]: {snap.git.modified}M {snap.git.untracked}U  "
        f"|  Learn: [bold cyan]{snap.learning.accuracy_pct:.0f}%[/]  "
        f"|  Alerts: {alert_str}  "
        f"|  Goals: [white]{goals_active}[/] active"
    )

    # Line 4: hint
    console.print("\n  [dim]cortex --alerts  --goals  --batch  --git  --full[/]\n")


def render_alerts(snap: CortexSnapshot):
    """Alert detail view."""
    console.print()
    for a in snap.alerts:
        color = _color_for_severity(a.severity)
        label = a.severity.upper()
        console.print(f"  [{color}]{label:<10}[/] {a.project:<18} {a.message}")
    console.print()


def render_goals(snap: CortexSnapshot):
    """Goal progress view."""
    console.print()
    for g in snap.goals:
        pri_color = _color_for_priority(g.priority)
        bar = progress_bar(g.completion_pct, 10)
        # Truncate for single-line display
        title = g.title[:28].ljust(28)
        # Extract just the first word/phrase of status (before parens or dashes)
        status_raw = g.status.split("(")[0].split("—")[0].strip()
        status = status_raw[:15]
        console.print(
            f"  [dim]G{g.number:<3}[/] {title} [{pri_color}]{g.priority}[/]  "
            f"{bar} {g.completion_pct:>3}%  [dim]{status}[/]"
        )
    if not snap.goals:
        console.print("  [dim]No active goals[/]")
    console.print()


def render_batch(snap: CortexSnapshot):
    """Batch health view."""
    b = snap.batch
    rate_color = "green" if b.success_rate > 0.8 else "yellow" if b.success_rate > 0.5 else "red"

    console.print()
    console.print(
        f"  Queue: [bold]{b.queue_depth}[/] pending  |  "
        f"Success: [{rate_color}]{b.success_rate:.0%}[/]  "
        f"({b.completed:,} ok / {b.failed:,} failed)"
    )
    if b.recent_ok:
        console.print(f"  [green]OK:[/]   {', '.join(b.recent_ok[:3])}")
    if b.recent_fail:
        console.print(f"  [red]FAIL:[/] {', '.join(b.recent_fail[:3])}")
    if not b.completed and not b.failed:
        console.print("  [dim]No batch data available[/]")
    console.print()


def render_git(snap: CortexSnapshot):
    """Git detail view."""
    g = snap.git
    console.print()
    console.print(f"  Branch:    [bold cyan]{g.branch}[/]")
    console.print(f"  Modified:  [yellow]{g.modified}[/]")
    console.print(f"  Untracked: [dim]{g.untracked}[/]")
    console.print(f"  Staged:    [green]{g.staged}[/]")

    pressure = g.modified + g.untracked
    if pressure > 15:
        console.print(f"\n  [bold red]High pressure ({pressure} files) — consider committing[/]")
    elif pressure > 8:
        console.print(f"\n  [yellow]Getting busy ({pressure} files)[/]")
    else:
        console.print(f"\n  [green]Clean ({pressure} files)[/]")
    console.print()


# ── Dispatch ───────────────────────────────────────────────────────


def cmd_compact(args):
    """Main entry point called from cli/__init__.py when no subcommand given."""
    snap = collect_snapshot()

    if getattr(args, "alerts", False):
        render_alerts(snap)
    elif getattr(args, "goals", False):
        render_goals(snap)
    elif getattr(args, "batch", False):
        render_batch(snap)
    elif getattr(args, "git_detail", False):
        render_git(snap)
    elif getattr(args, "full", False):
        # Fall through to full briefing
        cmd_briefing = None
        try:
            from cli.commands import cmd_briefing
        except ImportError:
            pass
        if cmd_briefing:
            cmd_briefing(args)
        else:
            console.print("[red]Full briefing not available[/]")
    else:
        render_default(snap)
