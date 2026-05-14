"""
Cortex TUI — Rich-based terminal dashboard.

Usage:
    python -m cortex.tui              # from ~/Dev
    python cortex/tui/app.py          # direct

Keyboard:
    1-5     Switch tabs (Projects/Alerts/Goals/Batch/Git)
    r       Refresh data
    q       Quit
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Allow running from ~/Dev or ~/Dev/cortex
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tui.data import CortexSnapshot, collect_snapshot


# ── Theme ──────────────────────────────────────────────────────────

COLORS = {
    "hot": "bold red",
    "active": "bold yellow",
    "steady": "cyan",
    "idle": "dim",
    "critical": "bold red",
    "warning": "yellow",
    "ok": "green",
    "P1": "bold red",
    "P2": "yellow",
    "accent": "bold cyan",
    "muted": "dim white",
    "header": "bold white on rgb(30,30,30)",
}

TREND_ICONS = {"hot": "🔥", "active": "📈", "steady": "➡️ ", "idle": "💤"}

BAR_CHARS = "░▏▎▍▌▋▊▉█"


def spark_bar(value: int, max_val: int, width: int = 8) -> str:
    """Render a compact sparkline bar."""
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


# ── Widgets ────────────────────────────────────────────────────────


def make_header(snap: CortexSnapshot) -> Panel:
    """Top bar: portfolio pulse + key metrics on two lines."""
    # Line 1: top projects — only show active ones (commits > 0)
    active = [p for p in snap.projects if p.commits_7d > 0]
    if not active:
        active = snap.projects[:3]
    max_commits = max((p.commits_7d for p in active), default=1) or 1
    project_parts = []
    for p in active[:5]:
        bar = spark_bar(p.commits_7d, max_commits, 5)
        color = COLORS.get(p.trend, "white")
        project_parts.append(f"[{color}]{p.name:<8}[/]{bar} {p.commits_7d:>2}c")

    idle_count = sum(1 for p in snap.projects if p.commits_7d == 0)
    projects_line = "  ".join(project_parts)
    if idle_count:
        projects_line += f"  [dim]+{idle_count} idle[/]"

    # Line 2: key metrics
    crit_count = sum(1 for a in snap.alerts if a.severity == "critical")
    warn_count = sum(1 for a in snap.alerts if a.severity == "warning")

    alert_text = ""
    if crit_count:
        alert_text += f"[bold red]{crit_count} crit[/]"
    if warn_count:
        alert_text += f" [yellow]{warn_count} warn[/]"
    if not alert_text:
        alert_text = "[green]all clear[/]"

    goals_active = len(snap.goals)
    metrics_line = (
        f"Learn: [{COLORS['accent']}]{snap.learning.accuracy_pct:.0f}%[/]  "
        f"Alerts: {alert_text}  "
        f"Goals: [white]{goals_active} active[/]  "
        f"Git: [white]{snap.git.branch}[/] {snap.git.modified}M {snap.git.untracked}U"
    )

    content = Text.from_markup(f"{projects_line}\n{metrics_line}")
    now = snap.timestamp.strftime("%a %b %d, %I:%M %p")
    return Panel(content, title=f"[bold]cortex[/] — {now}", border_style="cyan", padding=(0, 1))


def make_projects_panel(snap: CortexSnapshot) -> Panel:
    """Detailed project view."""
    table = Table(show_header=True, header_style="bold cyan", expand=True, box=None, padding=(0, 1))
    table.add_column("Project", style="bold", min_width=12)
    table.add_column("7d", justify="right", min_width=4)
    table.add_column("Trend", min_width=6)
    table.add_column("Bar", min_width=10)

    max_c = max((p.commits_7d for p in snap.projects), default=1) or 1
    for p in snap.projects:
        color = COLORS.get(p.trend, "white")
        icon = TREND_ICONS.get(p.trend, "")
        bar = spark_bar(p.commits_7d, max_c, 12)
        table.add_row(
            f"[{color}]{p.name}[/]",
            str(p.commits_7d),
            f"{icon} {p.trend}",
            f"[{color}]{bar}[/]",
        )

    return Panel(table, title="[1] Projects", border_style="cyan", padding=(0, 1))


def make_alerts_panel(snap: CortexSnapshot) -> Panel:
    """Alert severity list."""
    table = Table(show_header=True, header_style="bold cyan", expand=True, box=None, padding=(0, 1))
    table.add_column("Sev", min_width=8)
    table.add_column("Project", style="bold", min_width=14)
    table.add_column("Status", min_width=30)

    for a in snap.alerts:
        color = COLORS.get(a.severity, "white")
        sev_label = a.severity.upper()
        table.add_row(
            f"[{color}]{sev_label}[/]",
            a.project,
            a.message,
        )

    if not snap.alerts:
        table.add_row("[green]OK[/]", "all projects", "no alerts")

    return Panel(table, title="[2] Alerts", border_style="cyan", padding=(0, 1))


def make_goals_panel(snap: CortexSnapshot) -> Panel:
    """Active goals with progress bars."""
    table = Table(show_header=True, header_style="bold cyan", expand=True, box=None, padding=(0, 1))
    table.add_column("#", justify="right", min_width=3)
    table.add_column("Goal", min_width=25)
    table.add_column("Pri", min_width=3)
    table.add_column("Progress", min_width=14)
    table.add_column("Status", min_width=20)

    for g in snap.goals:
        pri_color = COLORS.get(g.priority, "white")
        bar = spark_bar(g.completion_pct, 100, 8)
        pct = f"{g.completion_pct}%"
        table.add_row(
            f"G{g.number}",
            g.title,
            f"[{pri_color}]{g.priority}[/]",
            f"{bar} {pct}",
            f"[dim]{g.status}[/]",
        )

    if not snap.goals:
        table.add_row("-", "No active goals found", "-", "-", "-")

    return Panel(table, title="[3] Goals", border_style="cyan", padding=(0, 1))


def make_batch_panel(snap: CortexSnapshot) -> Panel:
    """Batch queue health."""
    b = snap.batch
    lines = []

    rate_color = "green" if b.success_rate > 0.8 else "yellow" if b.success_rate > 0.5 else "red"
    lines.append(
        f"Queue: [bold]{b.queue_depth}[/] pending  |  "
        f"Success: [{rate_color}]{b.success_rate:.0%}[/]  "
        f"({b.completed:,} ok / {b.failed:,} failed)"
    )

    if b.recent_ok:
        ok_str = ", ".join(b.recent_ok[:3])
        lines.append(f"\n[green]Recent OK:[/]  {ok_str}")
    if b.recent_fail:
        fail_str = ", ".join(b.recent_fail[:3])
        lines.append(f"[red]Recent FAIL:[/] {fail_str}")

    if not lines:
        lines.append("[dim]No batch data available[/]")

    content = Text.from_markup("\n".join(lines))
    return Panel(content, title="[4] Batch", border_style="cyan", padding=(0, 1))


def make_git_panel(snap: CortexSnapshot) -> Panel:
    """Git working tree status."""
    g = snap.git
    lines = [
        f"Branch: [bold cyan]{g.branch}[/]",
        f"Modified: [yellow]{g.modified}[/] files",
        f"Untracked: [dim]{g.untracked}[/] files",
        f"Staged: [green]{g.staged}[/] files",
    ]

    pressure = g.modified + g.untracked
    if pressure > 15:
        lines.append("\n[bold red]⚠ High working tree pressure — consider committing[/]")
    elif pressure > 8:
        lines.append("\n[yellow]Working tree getting busy[/]")
    else:
        lines.append("\n[green]Working tree clean[/]")

    content = Text.from_markup("\n".join(lines))
    return Panel(content, title="[5] Git", border_style="cyan", padding=(0, 1))


def make_footer(tab: int, errors: list[str]) -> Panel:
    """Bottom bar with keybindings and errors."""
    tabs = ["Projects", "Alerts", "Goals", "Batch", "Git"]
    tab_parts = []
    for i, name in enumerate(tabs):
        if i == tab:
            tab_parts.append(f"[bold cyan]\\[{i + 1}]{name}[/]")
        else:
            tab_parts.append(f"[dim]\\[{i + 1}]{name}[/]")

    tab_line = "  ".join(tab_parts)
    keys = "[dim]\\[r]efresh  \\[q]uit[/]"

    error_line = ""
    if errors:
        error_line = f"\n[dim red]Errors: {', '.join(errors)}[/]"

    content = Text.from_markup(f"{tab_line}    {keys}{error_line}")
    return Panel(content, border_style="dim", padding=(0, 1))


# ── Main Layout ────────────────────────────────────────────────────

DETAIL_PANELS = [
    make_projects_panel,
    make_alerts_panel,
    make_goals_panel,
    make_batch_panel,
    make_git_panel,
]


def build_layout(snap: CortexSnapshot, active_tab: int = 0) -> Layout:
    """Compose the full dashboard layout."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )

    layout["header"].update(make_header(snap))
    layout["body"].update(DETAIL_PANELS[active_tab](snap))
    layout["footer"].update(make_footer(active_tab, snap.errors))

    return layout


# ── Static mode (single render) ───────────────────────────────────


def render_static():
    """Render once and exit. Good for piping or non-interactive use."""
    console = Console()
    snap = collect_snapshot()
    layout = build_layout(snap, active_tab=0)
    console.print(layout)


# ── Interactive mode ───────────────────────────────────────────────


def run_interactive():
    """Run the interactive TUI with keyboard navigation."""
    console = Console()
    active_tab = 0
    snap = collect_snapshot()

    # Use threading for non-blocking input
    import select
    import termios
    import tty

    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())

        with Live(
            build_layout(snap, active_tab), console=console, screen=True, refresh_per_second=2
        ) as live:
            while True:
                # Check for input (non-blocking)
                if select.select([sys.stdin], [], [], 0.3)[0]:
                    key = sys.stdin.read(1)

                    if key == "q":
                        break
                    elif key == "r":
                        snap = collect_snapshot()
                    elif key in "12345":
                        active_tab = int(key) - 1
                    elif key == "\t":  # Tab cycles
                        active_tab = (active_tab + 1) % 5

                    live.update(build_layout(snap, active_tab))
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        console.print("[dim]cortex tui exited[/]")


# ── Entry point ────────────────────────────────────────────────────


def main():
    """Main entry point."""
    if "--static" in sys.argv or not sys.stdin.isatty():
        render_static()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
