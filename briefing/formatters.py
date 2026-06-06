"""Briefing output formatters.

Pure functions that turn a `BriefingData` instance into the various surface
shapes the rest of the system expects: full text, compact box, single-line
statusbar, JSON variants.

This module is being populated incrementally as part of the Phase 3b split
(see `docs/AUDIT_FINDINGS.md`). Each formatter migrates as its own commit so
the golden-file harness at `tests/test_briefing_golden.py` can verify
byte-for-byte stability between every step.

Migrated so far:
  - `_load_briefing_style`    persistent style-config loader
  - `_build_progress_bar`     ASCII bar helper used by status formatters
  - `format_statusline`       single-line statusbar payload
  - `format_statusline_json`  JSON variant of statusline
  - `get_executive_summary`   one-line headline (Operator Persona)
  - `detect_resume_context`   git-state signal helper
  - `detect_stale_items`      GOALS.md stale-action helper
  - `format_compact`          bordered-box compact view
  - `format_briefing_json`    JSON serialization of the BriefingData payload
  - `format_briefing`         full text briefing (~1075 LOC — biggest
                              single function in the codebase)

All public formatters now live here. `briefing/__init__.py` retains only
`BriefingData`, `BriefingGenerator`, `generate_daily_briefing`, and the
small style/signal helpers (`_sparkline`, `_compute_signal_quality`,
`get_briefing_signal_quality`, …) that the generator and formatters share.
"""

from __future__ import annotations

import getpass
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # BriefingData lives in briefing.__init__ and is imported lazily inside the
    # functions below to avoid a circular import at module-load time. The
    # TYPE_CHECKING guard lets editors + mypy see the annotation without paying
    # the runtime cost.
    from . import BriefingData


# Module-local default — mirrors the DEFAULT_BRIEFING_STYLE dict still in
# briefing.__init__. Both fall back to the same on-disk style file.
_DEFAULT_BRIEFING_STYLE: Dict[str, Any] = {
    "progress_bar": {
        "width": 10,
        "filled_char": "#",
        "empty_char": ".",
        "left_bracket": "[",
        "right_bracket": "]",
    },
    "sparkline_chars": "▁▂▃▄▅▆▇█",
}


def _load_briefing_style() -> Dict[str, Any]:
    """Load the persistent briefing style contract from disk.

    Style file lives at `briefing/config/briefing_style.json` (relative to
    this package). Missing or malformed files silently fall back to
    `_DEFAULT_BRIEFING_STYLE` — never raises.
    """
    style_path = Path(__file__).parent / "config" / "briefing_style.json"
    style = dict(_DEFAULT_BRIEFING_STYLE)

    try:
        if style_path.exists():
            raw = json.loads(style_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                style.update({k: v for k, v in raw.items() if k in style})
                if isinstance(raw.get("progress_bar"), dict):
                    pb = dict(style["progress_bar"])
                    pb.update(raw["progress_bar"])
                    style["progress_bar"] = pb
    except Exception:
        # Keep defaults if style file is malformed.
        pass

    return style


def _build_progress_bar(percent: int, style: Dict[str, Any]) -> str:
    """Build an ASCII progress bar using the loaded style config."""
    pb = style.get("progress_bar", {})
    width = max(1, int(pb.get("width", 10)))
    filled_char = str(pb.get("filled_char", "#"))[:1]
    empty_char = str(pb.get("empty_char", "."))[:1]
    left = str(pb.get("left_bracket", "["))[:1]
    right = str(pb.get("right_bracket", "]"))[:1]

    pct = max(0, min(100, int(percent)))
    filled = min(width, int(round((pct / 100) * width)))
    return f"{left}{filled_char * filled}{empty_char * (width - filled)}{right}"


def format_statusline(
    briefing: "BriefingData", use_color: bool = False, max_width: int = 140
) -> str:
    """Format a compact, single-line status summary for Claude statusLine hooks.

    Composes a token stream:
        [CORTEX] P:<active> C7:<7-day commits> B:<blockers> H:<progress-bar>
                 [G:<branch>+<modified>/?<untracked>] [Q:<running>R/<queued>Q]
                 SIG:<HIGH|MED|LOW>
                 | TOP[<priority>]: <top action title>

    Truncates to `max_width` chars (with `...` suffix on truncation).
    """
    # Lazy import to break the briefing/__init__.py ↔ briefing/formatters.py
    # circular dependency.
    from . import get_briefing_signal_quality

    style = _load_briefing_style()

    active = len(briefing.active_projects)
    commits_7d = int(briefing.total_commits_7d)
    blockers = len(briefing.blockers)

    health_pct = int(max(0, min(100, round((1 - (blockers / max(1, active))) * 100))))
    health_bar = _build_progress_bar(health_pct, style)

    signal_quality = "HIGH"
    tokens = [
        "[CORTEX]",
        f"P:{active}",
        f"C7:{commits_7d}",
        f"B:{blockers}",
        f"H:{health_bar}",
    ]

    if briefing.git_status and briefing.git_status.get("summary"):
        gs = briefing.git_status["summary"]
        modified = int(
            gs.get("uncommitted_changes", gs.get("working_tree", {}).get("modified", 0))
        )
        untracked = int(
            gs.get("untracked_files", gs.get("working_tree", {}).get("untracked", 0))
        )
        branch = gs.get("current_branch", "unknown")
        signal_quality = str(get_briefing_signal_quality(briefing)["quality"])
        tokens.append(f"G:{branch}+{modified}/?{untracked}")

    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status
        running = int(bq.get("running_count", 0))
        queued = int(bq.get("pending_count", 0) + bq.get("scheduled_count", 0))
        if running > 0 or queued > 0:
            tokens.append(f"Q:{running}R/{queued}Q")

    tokens.append(f"SIG:{signal_quality}")

    line = " ".join(tokens)

    if briefing.priority_actions:
        top = briefing.priority_actions[0]
        top_title = top.get("title", "No title")
        top_priority = top.get("priority", "MEDIUM")
        line += f" | TOP[{top_priority}]: {top_title}"

    if len(line) > max_width:
        line = line[: max(0, max_width - 3)].rstrip() + "..."

    # `use_color` is reserved for ANSI styling in a future revision; for now
    # the statusline format is plain-ASCII either way to satisfy hostile
    # statusbar consumers.
    return line


def format_statusline_json(briefing: "BriefingData") -> str:
    """Serialize the statusline payload as a JSON object.

    Convenience wrapper for clients that want a structured view of the
    statusline data instead of the plain-text rendering. Includes the
    plain-text line itself under the `statusline` key for symmetry.
    """
    payload = {
        "generated_at": briefing.generated_at.isoformat(),
        "active_projects": len(briefing.active_projects),
        "commits_7d": briefing.total_commits_7d,
        "blockers": len(briefing.blockers),
        "statusline": format_statusline(briefing, use_color=False),
    }
    return json.dumps(payload, indent=2)


def _resolve_user_name() -> str:
    """Pick a human-readable name for the briefing greeting.

    Precedence:
      1. `CORTEX_USER` env var — explicit override, primary contributor mechanism.
      2. `USER` env var — POSIX standard.
      3. `getpass.getuser()` — falls back to the OS-reported login name.
      4. Literal "there" as a last-resort safe greeting.

    Was previously hardcoded to the maintainer's first name; sanitized here
    as part of the Phase 3b extraction (see docs/AUDIT_FINDINGS.md for the
    earlier personal-path sweep).
    """
    override = os.environ.get("CORTEX_USER")
    if override:
        return override
    posix_user = os.environ.get("USER")
    if posix_user:
        return posix_user
    try:
        return getpass.getuser()
    except Exception:
        return "there"


def get_executive_summary(briefing: "BriefingData") -> str:
    """Generate a concise, high-impact executive summary (Operator Persona).

    Enhanced format with intelligence: greeting, status, priority, prediction,
    day context. The greeted name is derived from `CORTEX_USER` / `USER` /
    `getpass.getuser()` — no longer hardcoded.
    """
    parts = []

    # Greeting based on time with day context
    hour = datetime.now().hour  # noqa: DTZ005
    greeting = "Morning" if 5 <= hour < 12 else "Afternoon" if 12 <= hour < 17 else "Evening"
    day_suffix = ""
    if briefing.temporal_context:
        day = briefing.temporal_context.get("day_of_week", "")
        if day:
            day_suffix = f" ({day})"
    parts.append(f"{greeting}, {_resolve_user_name()}{day_suffix}.")

    # Pulse with velocity
    active_count = len(briefing.active_projects)
    velocity_suffix = ""
    if briefing.strategic_alignment:
        velocity = briefing.strategic_alignment.get("velocity_status", "")
        if velocity == "healthy":
            velocity_suffix = " ✓"
        elif velocity == "blocked":
            velocity_suffix = " ⚠"
    parts.append(f"{active_count} Active Projects{velocity_suffix}.")

    # Blockers or strategic drift warning
    blocker_count = len(briefing.blockers)
    has_drift = briefing.strategic_alignment and briefing.strategic_alignment.get(
        "has_strategic_drift"
    )
    if blocker_count > 0:
        parts.append(f"{blocker_count} Blockers.")
    elif has_drift:
        parts.append("Strategic Drift Detected.")
    else:
        parts.append("Systems Nominal.")

    # Top Priority with prediction context
    if briefing.priority_actions:
        top_action = briefing.priority_actions[0]
        parts.append(f"Priority: {top_action['title'][:40]}.")
    elif briefing.predictive_insights:
        predictions = briefing.predictive_insights.get("predictions", [])
        if predictions:
            parts.append(f"Suggested: {predictions[0]['prediction'][:40]}.")
    else:
        parts.append("No immediate actions.")

    # Day intelligence suggestion (if available and relevant)
    if briefing.temporal_context:
        day_pattern = briefing.temporal_context.get("day_pattern", {})
        energy = day_pattern.get("energy", "")
        if energy in ["fresh_start", "high"]:
            parts.append("High energy day.")
        elif energy == "winding_down":
            parts.append("Wrap-up day.")

    # Recommendation accuracy insight (if sufficient data)
    if briefing.intelligence_metrics:
        im = briefing.intelligence_metrics
        if im.get("has_sufficient_data"):
            accuracy = im.get("recommendation_accuracy", 0) * 100
            if accuracy >= 70:
                parts.append(f"Cortex: {accuracy:.0f}% accurate.")

    return " ".join(parts)


def detect_resume_context(repo_root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Detect the current work unit from git diff/status.

    Runs git diff --stat HEAD and git status --short, clusters changed files
    by parent directory, and returns the dominant work unit.

    Returns:
        dict with keys: summary, files, directory
        or None if workspace is clean.
    """
    import re as _re
    import subprocess as _sp

    root = str(repo_root) if repo_root else None
    cwd = root or str(Path.cwd())

    try:
        stat_result = _sp.run(
            ["git", "diff", "--stat", "HEAD"], capture_output=True, text=True, cwd=cwd, timeout=10
        )
        status_result = _sp.run(
            ["git", "status", "--short"], capture_output=True, text=True, cwd=cwd, timeout=10
        )
    except Exception:
        return None

    stat_out = stat_result.stdout.strip()
    status_out = status_result.stdout.strip()

    if not stat_out and not status_out:
        return None

    # Parse `git diff --stat HEAD` lines like: "  path/to/file.py | 43 +++---"
    file_entries: List[Dict[str, Any]] = []
    for line in stat_out.splitlines():
        m = _re.match(r"^\s*(.+?)\s*\|\s*(\d+)", line)
        if m:
            fname = m.group(1).strip()
            insertions = int(m.group(2))
            file_entries.append({"name": fname, "insertions": insertions})

    # Also capture untracked/modified from status if diff --stat gave nothing
    if not file_entries:
        for line in status_out.splitlines():
            if len(line) >= 3:
                fname = line[3:].strip()
                file_entries.append({"name": fname, "insertions": 0})

    if not file_entries:
        return None

    # Cluster by parent directory
    dir_counts: Dict[str, int] = {}
    for entry in file_entries:
        parent = str(Path(entry["name"]).parent)
        dir_counts[parent] = dir_counts.get(parent, 0) + 1

    dominant_dir = max(dir_counts, key=lambda d: dir_counts[d])

    # Pick files from dominant dir (or all if single-dir)
    dominant_files = [e for e in file_entries if str(Path(e["name"]).parent) == dominant_dir]
    if not dominant_files:
        dominant_files = file_entries

    # Build summary label from directory name
    dir_label = Path(dominant_dir).name if dominant_dir not in (".", "") else "root"
    file_count = len(dominant_files)
    summary = f"{dir_label} ({file_count} file{'s' if file_count != 1 else ''})"

    return {
        "summary": summary,
        "files": dominant_files[:4],  # cap at 4 for display
        "directory": dominant_dir,
    }


def detect_stale_items(
    goals_path: Optional[Path] = None, threshold_days: int = 7
) -> List[Dict[str, Any]]:
    """Find unchecked GOALS.md items that haven't been touched in >threshold_days.

    Uses `git blame --line-porcelain GOALS.md` to get per-line timestamps,
    then returns `- [ ]` lines whose blame timestamp is older than threshold.

    Returns:
        List of dicts: [{"text": "...", "age_days": N}, ...]
    """
    import subprocess as _sp
    import time as _time

    if goals_path is None:
        # Default: monorepo root GOALS.md (briefing/ is a package now;
        # parent.parent is the repo root).
        goals_path = Path(__file__).parent.parent / "GOALS.md"

    if not goals_path.exists():
        return []

    try:
        result = _sp.run(
            ["git", "blame", "--line-porcelain", str(goals_path.name)],
            capture_output=True,
            text=True,
            cwd=str(goals_path.parent),
            timeout=15,
        )
        if result.returncode != 0:
            return []
        blame_out = result.stdout
    except Exception:
        return []

    now = _time.time()
    stale: List[Dict[str, Any]] = []

    # Parse porcelain format: each hunk starts with a 40-char SHA line,
    # then key-value pairs, then a line starting with \t which is the content.
    # We accumulate timestamp per line.
    current_ts: Optional[int] = None
    for line in blame_out.splitlines():
        if line.startswith("author-time "):
            try:
                current_ts = int(line.split(" ", 1)[1])
            except ValueError:
                current_ts = None
        elif line.startswith("\t"):
            content = line[1:]  # strip leading tab
            if current_ts is not None and content.lstrip().startswith("- [ ]"):
                age_days = int((now - current_ts) / 86400)
                if age_days >= threshold_days:
                    # Extract the item text after "- [ ] "
                    text = content.lstrip()[len("- [ ] ") :].strip()
                    if len(text) > 40:
                        text = text[:37] + "..."
                    stale.append({"text": text, "age_days": age_days})
            current_ts = None

    return stale


def format_compact(briefing: "BriefingData", use_color: bool = True) -> str:
    """Format a fixed ~42-char ANSI box briefing, action-first.

    This is the compact session-startup view: resume context, blockers,
    Vortex status, stale items, and drill-down commands.

    `detect_resume_context` and `detect_stale_items` are looked up via the
    `briefing` package namespace (not local references) so test fixtures
    that `patch("briefing.detect_resume_context", ...)` and
    `patch("briefing.detect_stale_items", ...)` continue to intercept the
    calls after this migration.
    """
    # Color setup
    BOLD = RESET = YELLOW = GREEN = CYAN = ""
    if use_color:
        try:
            from colorama import Fore, Style, init as _cinit

            _cinit(autoreset=False)
            BOLD = Style.BRIGHT
            RESET = Style.RESET_ALL
            YELLOW = Fore.YELLOW
            GREEN = Fore.GREEN
            CYAN = Fore.CYAN
        except ImportError:
            pass

    WIDTH = 42  # inner content width (between │ and │)

    def pad(text: str, width: int = WIDTH) -> str:
        """Pad plain text (without ANSI) to width, then wrap with borders."""
        import re as _re

        ansi_escape = _re.compile(r"\x1b\[[0-9;]*m")
        plain_len = len(ansi_escape.sub("", text))
        padding = max(0, width - plain_len)
        return f"│ {text}{' ' * padding} │"

    date_str = briefing.generated_at.strftime("%b %-d")
    header_label = "CORTEX"
    header_right = date_str

    inner_plain = f" {header_label} "
    filler_len = WIDTH - len(inner_plain) - len(header_right)
    filler = "─" * max(0, filler_len)
    top_line = (
        f"┌─{BOLD}{header_label}{RESET}─{filler}{header_right}─┐"
        if BOLD
        else f"┌─{header_label}─{filler}{header_right}─┐"
    )

    lines = [top_line]

    # Resume context — lazy lookup through the briefing namespace so the
    # test harness's `patch("briefing.detect_resume_context", …)` still
    # intercepts here (the patch target is the briefing module's attribute,
    # which is the re-export pointing back at this function — we have to go
    # through the briefing namespace to see the Mock).
    import briefing as _briefing

    resume = _briefing.detect_resume_context()
    if resume:
        summary = resume["summary"]
        lines.append(pad(f"▸ RESUME: {BOLD}{summary}{RESET}" if BOLD else f"▸ RESUME: {summary}"))
        file_parts = []
        for f in resume["files"][:3]:
            name = Path(f["name"]).name
            ins = f["insertions"]
            file_parts.append(f"{name} +{ins}" if ins else name)
        files_str = "  " + "  ".join(file_parts)
        lines.append(pad(files_str))
    else:
        # No resume context — show top priority action if available
        if briefing.priority_actions:
            top = briefing.priority_actions[0]
            action_text = top.get("title", top.get("action", "Review priorities"))[:36]
            lines.append(pad(f"▸ {action_text}"))
        else:
            lines.append(pad("▸ No pending actions"))
        lines.append(pad(""))

    lines.append(pad(""))

    # Blockers line
    if briefing.blockers:
        blocker_texts = []
        for b in briefing.blockers[:3]:
            label = b.get("title", b.get("description", ""))[:20]
            blocker_texts.append(label)
        blocker_str = f"{YELLOW}⚠{RESET} " if YELLOW else "⚠ "
        blocker_str += " · ".join(blocker_texts)
        lines.append(pad(blocker_str))
    else:
        lines.append(pad(f"{GREEN}✓{RESET} No blockers" if GREEN else "✓ No blockers"))

    # Vortex health line (EMOS is a Vortex concern, not Cortex)
    vortex_str = "Vortex: "
    if briefing.resource_status and isinstance(briefing.resource_status, dict):
        rs = briefing.resource_status
        health = rs.get("health") or rs.get("status") or rs.get("vortex")
        if health:
            vortex_str += str(health)[:30]
        else:
            vortex_str += "check localhost:8000"
    else:
        vortex_str += "check localhost:8000"
    lines.append(pad(vortex_str))

    lines.append(pad(""))

    # Stale items — same lazy-lookup pattern as detect_resume_context.
    stale = _briefing.detect_stale_items()
    if stale:
        item = stale[0]
        age = item["age_days"]
        text = item["text"][:28]
        stale_line = (
            f"{YELLOW}STALE:{RESET} {text} ({age}d)" if YELLOW else f"STALE: {text} ({age}d)"
        )
        lines.append(pad(stale_line))
    # else: skip the STALE line entirely

    # Drill-down commands
    lines.append(
        pad(f"▸ {CYAN}cortex briefing --detail{RESET}" if CYAN else "▸ cortex briefing --detail")
    )
    lines.append(
        pad(
            f"▸ {CYAN}http://localhost:3001/briefing{RESET}"
            if CYAN
            else "▸ http://localhost:3001/briefing"
        )
    )

    # Bottom border
    lines.append("└" + "─" * (WIDTH + 2) + "┘")

    return "\n".join(lines)


def format_briefing_json(briefing: "BriefingData") -> str:
    """Format briefing as JSON.

    Args:
        briefing: BriefingData to format

    Returns:
        JSON string
    """
    data = {
        "generated_at": briefing.generated_at.isoformat(),
        "period": briefing.period,
        "portfolio_pulse": {
            "active_projects": briefing.active_projects,
            "recent_commits_24h": briefing.recent_commits_24h,
            "total_commits_7d": briefing.total_commits_7d,
            "blockers": briefing.blockers,
        },
        "priority_actions": briefing.priority_actions,
        "patterns_noticed": briefing.patterns,
        "waiting_on": briefing.waiting_on,
        # Enhanced intelligence fields
        "intelligence_metrics": briefing.intelligence_metrics,
        "strategic_alignment": briefing.strategic_alignment,
        "temporal_context": briefing.temporal_context,
        "cross_project_insights": briefing.cross_project_insights,
        "predictive_insights": briefing.predictive_insights,
        "bandwidth_contract_metrics": briefing.bandwidth_contract_metrics,
        "queue_slo": briefing.queue_slo,
    }

    return json.dumps(data, indent=2, default=str)


def format_briefing(briefing: "BriefingData", use_color: bool = True) -> str:
    """
    Format briefing data into readable text output.

    Args:
        briefing: BriefingData to format
        use_color: Use terminal colors (if available)

    Returns:
        Formatted briefing string
    """

    # Lazy alias to the briefing namespace so test harnesses that patch
    # `briefing.get_briefing_signal_quality` / `briefing._sparkline` are still
    # honored after the migration to briefing/formatters.py.
    import briefing as _briefing
    lines = []
    style = _load_briefing_style()
    sep_width = int(style.get("separator_width", 64))
    show_ascii = bool(style.get("show_ascii_graphics", True))
    show_infographics = bool(style.get("show_infographics", True))
    show_sparklines = bool(style.get("show_sparklines", True))

    # Try to use rich/colorama for colors, fallback to plain text
    try:
        if use_color:
            from colorama import Fore, Style, init

            init(autoreset=True)
            BOLD = Style.BRIGHT
            RESET = Style.RESET_ALL
            BLUE = Fore.BLUE
            GREEN = Fore.GREEN
            YELLOW = Fore.YELLOW
        else:
            raise ImportError
    except ImportError:
        BOLD = RESET = BLUE = GREEN = YELLOW = RED = ""

    # Header
    date_title = f"CORTEX DAILY BRIEFING - {briefing.generated_at.strftime('%B %d, %Y')}"
    if show_ascii:
        inner_width = max(sep_width - 4, len(date_title) + 2)
        lines.append("+" + "-" * (inner_width + 2) + "+")
        lines.append(f"| {BOLD}{date_title:^{inner_width}}{RESET} |")
        lines.append("+" + "-" * (inner_width + 2) + "+")
    else:
        lines.append("=" * sep_width)
        lines.append(f"{BOLD}DAILY BRIEFING - {briefing.generated_at.strftime('%B %d, %Y')}{RESET}")
        lines.append("=" * sep_width)
    lines.append("")

    # Hard warning when workspace noise degrades briefing confidence.
    if briefing.git_status and briefing.git_status.get("summary"):
        signal = _briefing.get_briefing_signal_quality(briefing)
        signal_quality = str(signal["quality"])
        modified = int(signal["modified"])
        untracked = int(signal["untracked"])
        if signal_quality == "LOW":
            lines.append(
                f"{RED}[SIGNAL QUALITY: LOW] {modified + untracked} local changes distort recommendations{RESET}"
            )
            lines.append(
                f"{RED}Action: commit/stash or reduce working tree noise before trusting priorities{RESET}"
            )
            lines.append("")
        elif signal_quality == "MED":
            lines.append(
                f"{YELLOW}[SIGNAL QUALITY: MED] moderate working tree noise detected ({modified + untracked} files){RESET}"
            )
            lines.append("")

    # ==================== TL;DR SECTION ====================
    lines.append(f"{BOLD}TL;DR{RESET}")
    if show_ascii:
        lines.append("  " + "-" * 8)
    lines.append("")

    # Portfolio status bullet
    active_count = len(briefing.active_projects)
    blocker_count = len(briefing.blockers)
    blocker_status = (
        f"{RED}{blocker_count} blockers{RESET}"
        if blocker_count > 0
        else f"{GREEN}no blockers{RESET}"
    )
    lines.append(
        f"  • {BOLD}Portfolio:{RESET} {active_count} active projects, {briefing.total_commits_7d} commits this week, {blocker_status}"
    )
    if show_infographics:
        blocker_pct = int((blocker_count / max(1, active_count)) * 100)
        lines.append(
            f"    Health ratio: {_build_progress_bar(100 - blocker_pct, style)} {100 - blocker_pct}% clear"
        )

    # Top priority bullet
    if briefing.priority_actions:
        top = briefing.priority_actions[0]
        priority_color = (
            RED if top["priority"] == "HIGH" else YELLOW if top["priority"] == "MEDIUM" else GREEN
        )
        lines.append(
            f"  • {BOLD}Top Priority:{RESET} [{priority_color}{top['priority']}{RESET}] {top['title']}"
        )

    # Git status bullet
    if briefing.git_status and briefing.git_status.get("summary"):
        gs = briefing.git_status["summary"]
        branch = gs.get("current_branch", "unknown")
        modified = gs.get("uncommitted_changes", gs.get("working_tree", {}).get("modified", 0))
        untracked = gs.get("untracked_files", gs.get("working_tree", {}).get("untracked", 0))
        pr_count = gs.get("open_prs")
        if pr_count is None:
            pr_count = len(gs.get("pull_requests", []))
        pr_text = f", {pr_count} open PR{'s' if pr_count != 1 else ''}" if pr_count > 0 else ""
        lines.append(
            f"  • {BOLD}Git:{RESET} on `{branch}`, {modified} modified, {untracked} untracked{pr_text}"
        )

    # Work progress bullet
    if briefing.work_progress:
        wp = briefing.work_progress
        items_24h = wp.get("items_24h", 0)
        orphaned = wp.get("orphaned_24h", 0)
        drifts = wp.get("drifts_total", 0)
        orphan_text = f", {YELLOW}{orphaned} unplanned{RESET}" if orphaned > 0 else ""
        drift_text = f", {YELLOW}{drifts} drift items{RESET}" if drifts > 0 else ""
        lines.append(f"  • {BOLD}Work:{RESET} {items_24h} items today{orphan_text}{drift_text}")

    # Resource status bullet
    if briefing.resource_status:
        rs = briefing.resource_status
        cpu_avail = rs.get("cpu_available", 0)
        mem_used = rs.get("memory_usage_percent", 0)
        cpu_color = RED if cpu_avail < 30 else YELLOW if cpu_avail < 60 else GREEN
        mem_color = RED if mem_used > 80 else YELLOW if mem_used > 60 else GREEN
        waste = rs.get("waste_items", 0)
        waste_text = f", {YELLOW}{waste} waste items{RESET}" if waste > 10 else ""
        lines.append(
            f"  • {BOLD}System:{RESET} {cpu_color}{cpu_avail:.0f}% CPU free{RESET}, {mem_color}{mem_used:.0f}% mem used{RESET}{waste_text}"
        )

    # Batch queue bullet
    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status
        running = bq.get("running_count", 0)
        pending = bq.get("pending_count", 0) + bq.get("scheduled_count", 0)
        failed = bq.get("failed_count", 0)
        if running > 0 or pending > 0 or failed > 0:
            parts = []
            if running > 0:
                parts.append(f"{running} running")
            if pending > 0:
                parts.append(f"{pending} queued")
            if failed > 0:
                parts.append(f"{RED}{failed} failed{RESET}")
            lines.append(f"  • {BOLD}Batch:{RESET} {', '.join(parts)}")

    # V2a Batch orchestration status
    try:
        from batch.v2a_sprint_orchestrator import V2aSprintOrchestrator

        orchestrator = V2aSprintOrchestrator()
        v2a_status = orchestrator.get_overall_status()

        if v2a_status["total_tasks"] > 0:
            completed = v2a_status["completed"]
            total = v2a_status["total_tasks"]
            current_wave = v2a_status["current_wave"]
            progress_pct = v2a_status["progress_pct"]

            if progress_pct >= 100:
                lines.append(f"  • {BOLD}V2a Batch:{RESET} {GREEN}All complete ✓{RESET}")
            elif v2a_status["running"] > 0:
                lines.append(
                    f"  • {BOLD}V2a Batch:{RESET} {current_wave} in progress ({completed}/{total} complete, {progress_pct:.0f}%)"
                )
            elif v2a_status["failed"] > 0:
                lines.append(
                    f"  • {BOLD}V2a Batch:{RESET} {RED}{v2a_status['failed']} failed{RESET} ({completed}/{total} complete)"
                )
            else:
                lines.append(
                    f"  • {BOLD}V2a Batch:{RESET} {completed}/{total} complete ({progress_pct:.0f}%), ready for {current_wave}"
                )
    except Exception:
        # V2a batch orchestration may not be active
        pass

    # Temporal context bullet (day intelligence)
    if briefing.temporal_context:
        tc = briefing.temporal_context
        day = tc.get("day_of_week", "")
        day_pattern = tc.get("day_pattern", {})
        suggestion = day_pattern.get("suggestion", "")
        if suggestion:
            lines.append(f"  • {BOLD}Today:{RESET} {day} - {suggestion[:50]}")

    # Strategic alignment bullet (drift warning)
    if briefing.strategic_alignment:
        sa = briefing.strategic_alignment
        if sa.get("has_strategic_drift"):
            drift_count = len(sa.get("drift_indicators", []))
            lines.append(
                f"  • {BOLD}Strategy:{RESET} {YELLOW}⚠ {drift_count} drift indicator{'s' if drift_count != 1 else ''} detected{RESET}"
            )
        else:
            velocity = sa.get("velocity_status", "unknown")
            if velocity == "healthy":
                lines.append(f"  • {BOLD}Strategy:{RESET} {GREEN}On track{RESET}")

    # Predictive insight bullet
    if briefing.predictive_insights:
        pi = briefing.predictive_insights
        predictions = pi.get("predictions", [])
        if predictions:
            top_pred = predictions[0]
            conf = top_pred.get("confidence", "medium")
            conf_color = GREEN if conf == "high" else YELLOW
            lines.append(
                f"  • {BOLD}Predicted:{RESET} [{conf_color}{conf.upper()}{RESET}] {top_pred['prediction'][:45]}"
            )

    lines.append("")
    lines.append("-" * sep_width)
    lines.append("")

    # ==================== RESOURCE INTELLIGENCE (HIGH-VALUE) ====================

    if briefing.resource_intelligence:
        ri = briefing.resource_intelligence
        pacing = ri.get("pacing", {})
        weekly = ri.get("weekly", {})
        batch_opt = ri.get("batch_optimization", {})

        if show_ascii:
            lines.append(f"{BOLD}/== RESOURCE INTELLIGENCE ==/{RESET}")
        else:
            lines.append(f"{BOLD}⚡ RESOURCE INTELLIGENCE{RESET}")
        lines.append("")

        # Pacing status - THE most important metric
        emoji = pacing.get("emoji", "🟡")
        status = pacing.get("status", "unknown").replace("_", " ").title()
        daily_hrs = pacing.get("daily_hours", 0)
        target_hrs = pacing.get("target_hours", 8.6)
        advice = pacing.get("advice", "")

        status_color = (
            GREEN
            if pacing.get("status") == "under_budget"
            else YELLOW
            if pacing.get("status") in ["on_track", "elevated"]
            else RED
        )
        lines.append(
            f"  {emoji} {BOLD}Pacing:{RESET} {status_color}{status}{RESET} ({daily_hrs:.1f}h/day vs {target_hrs:.1f}h target)"
        )
        if advice:
            lines.append(f"     → {advice}")

        # Weekly projection
        used = weekly.get("used_hours", 0)
        limit = weekly.get("limit_hours", 60)
        days_left = weekly.get("days_remaining", 0)
        weekly.get("projected_total", 0)
        will_hit = weekly.get("will_hit_limit", False)

        pct_used = (used / limit * 100) if limit > 0 else 0
        weekly_color = GREEN if pct_used < 70 else YELLOW if pct_used < 90 else RED
        lines.append(
            f"  📊 {BOLD}Weekly:{RESET} {weekly_color}{used:.1f}h/{limit}h used ({pct_used:.0f}%){RESET}, {days_left} days left"
        )
        if will_hit:
            lines.append(f"     {RED}⚠ Projected to hit limit at current pace{RESET}")

        # Batch optimization
        batch_pct = batch_opt.get("current_percentage", 0)
        batch_target = batch_opt.get("target_percentage", 40)
        on_track = batch_opt.get("on_track", False)
        potential_savings = batch_opt.get("potential_savings", 0)

        batch_color = GREEN if on_track else YELLOW
        lines.append(
            f"  🔄 {BOLD}Batch API:{RESET} {batch_color}{batch_pct:.0f}%{RESET} of work (target: {batch_target}%)"
        )
        if not on_track and potential_savings > 0:
            lines.append(f"     → Shift more to batch: save ${potential_savings:.2f}/week")

        lines.append("")

    # ==================== ORCHESTRATION ADVISORY ====================

    if briefing.orchestration_advisory:
        oa = briefing.orchestration_advisory
        mode_rec = oa.get("mode_recommendation")

        if show_ascii:
            lines.append(f"{BOLD}/== ORCHESTRATION ADVISORY ==/{RESET}")
        else:
            lines.append(f"{BOLD}🎮 ORCHESTRATION ADVISORY{RESET}")
        lines.append("")

        # Mode recommendation
        if mode_rec:
            mode = mode_rec.get("mode", "balanced")
            reason = mode_rec.get("reason", "")
            actions = mode_rec.get("actions", [])

            mode_emoji = (
                "🟢" if mode == "interactive_ok" else "🔴" if mode == "batch_priority" else "🟡"
            )
            mode_label = mode.replace("_", " ").title()
            lines.append(f"  {mode_emoji} {BOLD}Recommended Mode:{RESET} {mode_label}")
            lines.append(f"     {reason}")
            if actions:
                lines.append("     Actions:")
                for action in actions[:2]:
                    lines.append(f"       • {action}")

        # Agent recommendations
        agent_recs = oa.get("agent_recommendations", [])
        if agent_recs:
            lines.append(f"  🤖 {BOLD}Deploy Agents:{RESET}")
            for rec in agent_recs[:2]:
                lines.append(f"     • {rec['agent']}: {rec['reason']}")

        # Parallelization opportunities
        parallel = oa.get("parallelization_opportunities", [])
        if parallel:
            lines.append(f"  ⚡ {BOLD}Parallelize:{RESET}")
            for opp in parallel[:1]:
                lines.append(f"     • {opp['opportunity']}")

        lines.append("")

    # ==================== VELOCITY & ROI ====================

    if briefing.velocity_metrics:
        vm = briefing.velocity_metrics
        lines.append(f"{BOLD}📈 VELOCITY & ROI{RESET}")
        total_hrs = vm.get("total_savings_hours", 0)
        tasks = vm.get("total_tasks", 0)
        avg_pct = vm.get("avg_improvement_pct", 0)

        lines.append(
            f"  30-Day Impact: {GREEN}{total_hrs:.1f} hours saved{RESET} across {tasks} tasks ({avg_pct:.0f}% faster)"
        )

        by_project = vm.get("by_project", {})
        if by_project:
            top_projects = sorted(
                by_project.items(), key=lambda x: x[1].get("savings", 0), reverse=True
            )[:3]
            if top_projects:
                lines.append("  Top contributors:")
                for proj, data in top_projects:
                    lines.append(f"    • {proj}: {data.get('savings', 0):.0f} min saved")

        lines.append("")

    lines.append("-" * 64)
    lines.append("")

    # ==================== EXPANDED DETAILS ====================

    # Executive Summary
    lines.append(f"{BOLD}EXECUTIVE SUMMARY{RESET}")
    exec_points = []
    if briefing.priority_actions:
        top = briefing.priority_actions[0]
        exec_points.append(
            f"Top move: [{top.get('priority', 'MEDIUM')}] {top.get('title', 'Action')}"
        )
    if briefing.blockers:
        blocker_names = ", ".join(b["project"] for b in briefing.blockers[:2])
        exec_points.append(f"Blockers concentrated in: {blocker_names}")
    if briefing.batch_insights:
        jobs = briefing.batch_insights.get("total_completed_24h", 0)
        exec_points.append(f"Overnight throughput: {jobs} completed analyses")
    if briefing.git_status and briefing.git_status.get("summary"):
        gs = briefing.git_status["summary"]
        exec_points.append(
            f"Working tree pressure: {gs.get('uncommitted_changes', 0)} modified, {gs.get('untracked_files', 0)} untracked"
        )
    if not exec_points:
        exec_points.append("No exceptional pressure signals detected.")
    for point in exec_points[:4]:
        lines.append(f"  • {point}")
    lines.append("")

    # Project Snapshot (table-style)
    if briefing.project_snapshot:
        lines.append(f"{BOLD}PROJECT SNAPSHOT{RESET}")
        lines.append("  Project                     C7d  WIP  Trend")
        lines.append("  -------------------------  ---  ---  ------")
        for row in briefing.project_snapshot[:6]:
            lines.append(
                f"  {row['project'][:25]:25}  {int(row['commits_7d']):>3}  {int(row['uncommitted']):>3}  {row['trend']}"
            )
        lines.append("")

    # Portfolio Pulse
    lines.append(f"{BOLD}PORTFOLIO PULSE{RESET}")
    lines.append(
        f"  Active projects: {len(briefing.active_projects)} ({', '.join(briefing.active_projects[:5])}{'...' if len(briefing.active_projects) > 5 else ''})"
    )
    lines.append(
        f"  Recent commits: {briefing.recent_commits_24h} in last 24h, {briefing.total_commits_7d} in last 7d"
    )
    if show_ascii and show_sparklines:
        trend = _briefing._sparkline(
            [float(briefing.recent_commits_24h), float(briefing.total_commits_7d)],
            str(style.get("sparkline_chars", "▁▂▃▄▅▆▇█")),
        )
        lines.append(f"  Commit trend (24h→7d): {trend}")
        commit_pct = int(
            min(
                100,
                round((briefing.recent_commits_24h / max(1, briefing.total_commits_7d)) * 100),
            )
        )
        lines.append(
            f"  Commit pulse meter: {_build_progress_bar(commit_pct, style)} {commit_pct}%"
        )

    if briefing.blockers:
        lines.append(f"  {RED}Blockers: {len(briefing.blockers)}{RESET}")
        for blocker in briefing.blockers[:3]:
            lines.append(f"    - {blocker['project']}: {blocker['blocker']}")
    else:
        lines.append(f"  {GREEN}Blockers: None{RESET}")

    lines.append("")

    # Git & GitHub Status
    if briefing.git_status and briefing.git_status.get("formatted"):
        lines.append(briefing.git_status["formatted"])
        lines.append("")

    # Work Progress (from Work Absorber)
    if briefing.work_progress:
        wp = briefing.work_progress
        lines.append(f"{BOLD}WORK PROGRESS{RESET}")

        items_24h = wp.get("items_24h", 0)
        items_7d = wp.get("items_7d", 0)
        correlated = wp.get("correlated_24h", 0)
        orphaned = wp.get("orphaned_24h", 0)

        lines.append(f"  Work items: {items_24h} in 24h, {items_7d} in 7d")

        if items_24h > 0:
            if correlated > 0:
                lines.append(f"  {GREEN}Planned work: {correlated} items{RESET}")
            if orphaned > 0:
                lines.append(f"  {YELLOW}Unplanned work: {orphaned} items{RESET}")

        # Show drifts
        drifts = wp.get("drifts_total", 0)
        if drifts > 0:
            drift_types = wp.get("drifts_by_type", {})
            drift_summary = ", ".join(f"{k}: {v}" for k, v in list(drift_types.items())[:3])
            lines.append(f"  {YELLOW}Plan drift: {drifts} ({drift_summary}){RESET}")

        # Recent work
        recent = wp.get("recent_work", [])
        if recent:
            lines.append("  Recent:")
            for item in recent[:3]:
                scope_badge = f"[{item.get('scope', 'misc')}]" if item.get("scope") else ""
                lines.append(f"    - {item['title'][:45]} {scope_badge}")

        lines.append("")

    # Resource Pulse
    if briefing.resource_status:
        lines.append(f"{BOLD}⚡ RESOURCE PULSE{RESET}")
        rs = briefing.resource_status

        # CPU and Memory
        cpu_color = (
            RED if rs["cpu_available"] < 30 else YELLOW if rs["cpu_available"] < 60 else GREEN
        )
        mem_color = (
            RED
            if rs["memory_usage_percent"] > 80
            else YELLOW
            if rs["memory_usage_percent"] > 60
            else GREEN
        )

        lines.append(
            f"  CPU: {cpu_color}{rs['cpu_available']:.0f}% available{RESET} | Memory: {mem_color}{rs['memory_usage_percent']:.0f}% used{RESET}"
        )
        lines.append(f"  Processes: {rs['process_count']}")

        # AI Tools & Services
        if rs.get("ai_tool_cpu", 0) > 0 or rs.get("dev_service_cpu", 0) > 0:
            lines.append(
                f"  AI Tools: {rs.get('ai_tool_cpu', 0):.1f}% CPU | Dev Services: {rs.get('dev_service_cpu', 0):.1f}% CPU"
            )

        # Alerts and Waste
        alerts_color = (
            RED
            if rs.get("critical_alerts", 0) > 0
            else YELLOW
            if rs.get("alerts_count", 0) > 5
            else ""
        )
        waste_color = YELLOW if rs.get("waste_items", 0) > 10 else ""

        if rs.get("alerts_count", 0) > 0:
            lines.append(
                f"  Alerts: {alerts_color}{rs.get('alerts_count', 0)} ({rs.get('critical_alerts', 0)} critical){RESET}"
            )

        if rs.get("waste_items", 0) > 0:
            lines.append(
                f"  Resource Waste: {waste_color}{rs.get('waste_items', 0)} items detected{RESET}"
            )

        # Optimization opportunities
        if rs.get("optimization_opportunities", 0) > 0:
            lines.append(
                f"  💡 {rs.get('optimization_opportunities', 0)} optimization opportunities"
            )

        lines.append("")

    # Batch Queue Status
    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status

        # Only show if there are tasks in the queue
        total_tasks = (
            bq.get("pending_count", 0) + bq.get("scheduled_count", 0) + bq.get("running_count", 0)
        )

        if total_tasks > 0 or bq.get("completed_count", 0) > 0 or bq.get("failed_count", 0) > 0:
            lines.append(f"{BOLD}📋 BATCH QUEUE{RESET}")

            # Show running tasks with details
            running_tasks = bq.get("running_tasks", [])
            if running_tasks:
                lines.append(f"  {YELLOW}▶️  Running Now:{RESET}")
                for task in running_tasks[:3]:  # Show up to 3
                    desc = (
                        task.description[:50] + "..."
                        if len(task.description) > 50
                        else task.description
                    )
                    elapsed = ""
                    if task.started_at:
                        from datetime import datetime

                        elapsed_sec = (datetime.now() - task.started_at).total_seconds()  # noqa: DTZ005
                        if elapsed_sec < 60:
                            elapsed = f" ({elapsed_sec:.0f}s elapsed)"
                        else:
                            elapsed = f" ({elapsed_sec / 60:.1f}m elapsed)"
                    lines.append(f"     • {desc}{elapsed}")
                if len(running_tasks) > 3:
                    lines.append(f"     ... and {len(running_tasks) - 3} more")
                lines.append("")

            # Show scheduled tasks with times
            scheduled_tasks = bq.get("scheduled_tasks", [])
            if scheduled_tasks:
                lines.append("  📅 Scheduled:")
                for task in scheduled_tasks[:3]:  # Show up to 3
                    desc = (
                        task.description[:45] + "..."
                        if len(task.description) > 45
                        else task.description
                    )
                    when = ""
                    if task.scheduled_time:
                        from datetime import datetime

                        now = datetime.now()  # noqa: DTZ005
                        time_until = (task.scheduled_time - now).total_seconds()

                        if time_until < 0:
                            when = " (ready now)"
                        elif time_until < 60:
                            when = f" (in {time_until:.0f}s)"
                        elif time_until < 3600:
                            when = f" (in {time_until / 60:.0f}m)"
                        elif time_until < 86400:
                            when = f" (at {task.scheduled_time.strftime('%H:%M')})"
                        else:
                            when = f" ({task.scheduled_time.strftime('%b %d %H:%M')})"

                    priority_marker = ""
                    if task.priority == "immediate":
                        priority_marker = f" {RED}[!]{RESET}"
                    elif task.priority == "high":
                        priority_marker = f" {YELLOW}[H]{RESET}"

                    lines.append(f"     • {desc}{when}{priority_marker}")

                if len(scheduled_tasks) > 3:
                    lines.append(f"     ... and {len(scheduled_tasks) - 3} more")
                lines.append("")

            # Show pending tasks
            pending_tasks = bq.get("pending_tasks", [])
            if pending_tasks:
                lines.append("  ⏳ Pending (not yet scheduled):")
                for task in pending_tasks[:3]:  # Show up to 3
                    desc = (
                        task.description[:50] + "..."
                        if len(task.description) > 50
                        else task.description
                    )
                    lines.append(f"     • {desc}")
                if len(pending_tasks) > 3:
                    lines.append(f"     ... and {len(pending_tasks) - 3} more")
                lines.append("")

            # Show recent completions with details
            recent_completed = bq.get("recent_completed", [])
            if recent_completed:
                lines.append(f"  {GREEN}✅ Recently Completed:{RESET}")
                for task in recent_completed:
                    desc = (
                        task.description[:45] + "..."
                        if len(task.description) > 45
                        else task.description
                    )
                    duration = ""
                    if task.actual_duration_seconds is not None:
                        if task.actual_duration_seconds < 1:
                            duration = f" ({task.actual_duration_seconds * 1000:.0f}ms)"
                        elif task.actual_duration_seconds < 60:
                            duration = f" ({task.actual_duration_seconds:.1f}s)"
                        else:
                            duration = f" ({task.actual_duration_seconds / 60:.1f}m)"
                    lines.append(f"     • {desc}{duration}")
                lines.append("")

            # Show recent failures with error details
            recent_failed = bq.get("recent_failed", [])
            if recent_failed:
                lines.append(f"  {RED}❌ Recently Failed:{RESET}")
                for task in recent_failed:
                    desc = (
                        task.description[:45] + "..."
                        if len(task.description) > 45
                        else task.description
                    )
                    lines.append(f"     • {desc}")
                    if task.error_message:
                        error = (
                            task.error_message[:60] + "..."
                            if len(task.error_message) > 60
                            else task.error_message
                        )
                        lines.append(f"       Error: {error}")
                lines.append(f"  💡 View details: {BLUE}cortex batch list --state failed{RESET}")
                lines.append("")

            # Show overall stats summary
            if bq.get("completed_count", 0) > 0 or bq.get("failed_count", 0) > 0:
                completed = bq.get("completed_count", 0)
                failed = bq.get("failed_count", 0)
                total = completed + failed

                if total > 0:
                    success_rate = bq.get("success_rate", 0)
                    success_color = (
                        GREEN if success_rate >= 0.9 else YELLOW if success_rate >= 0.7 else RED
                    )
                    lines.append(
                        f"  Overall: {completed} completed, {failed} failed ({success_color}{success_rate:.0%} success{RESET})"
                    )
                    lines.append("")

            lines.append("")

    # Overnight Batch Insights (AI analysis results from last 24h)
    if briefing.batch_insights:
        bi = briefing.batch_insights
        total_completed = bi.get("total_completed_24h", 0)
        total_output_kb = bi.get("total_output_kb", 0.0)
        avg_duration_s = bi.get("avg_duration_s", 0.0)
        lines.append(f"{BOLD}🔬 OVERNIGHT BATCH INSIGHTS{RESET}")
        lines.append(
            f"  {total_completed} analyses completed "
            f"({total_output_kb:.0f} KB output, "
            f"avg {avg_duration_s:.0f}s each)"
        )
        lines.append("")

        # Show categories with counts
        category_labels = {
            "commit-analysis": "Commit Reviews",
            "security-commit": "Security Scans",
            "test-failure": "Test Failure Analysis",
            "todo-analysis": "TODO/FIXME Scans",
            "strategic-planning": "Strategic Planning",
            "performance-analysis": "Performance Analysis",
            "dependency-audit": "Dependency Audit",
            "docs-completeness": "Documentation Audit",
            "code-quality-scan": "Code Quality",
            "test-coverage-analysis": "Test Coverage Gaps",
            "api-docs-generation": "API Docs",
        }
        categories = bi.get("categories", {})
        if isinstance(categories, dict):
            for cat, info in sorted(
                categories.items(),
                key=lambda x: -(x[1].get("count", 0) if isinstance(x[1], dict) else 0),
            ):
                label = category_labels.get(cat, cat.replace("-", " ").title())
                if isinstance(info, dict):
                    count = info.get("count", 0)
                    output_kb = info.get("total_output_kb", 0.0)
                else:
                    count = 0
                    output_kb = 0.0
                lines.append(f"  • {label}: {count} runs, {output_kb:.0f} KB")

        lines.append("")
        lines.append(
            f"  💡 Query results: {BLUE}sqlite3 ~/.cortex/batch_queue.db "
            f'"SELECT description, substr(stdout,1,500) FROM batch_tasks '
            f"WHERE state='completed' ORDER BY completed_at DESC LIMIT 5;\"{RESET}"
        )
        lines.append("")

    # V2a Sprint Batch Status (if active)
    if briefing.batch_queue_status and "v2a_sprint" in briefing.batch_queue_status:
        v2a = briefing.batch_queue_status["v2a_sprint"]

        # Only show if there are active V2a tasks
        if v2a.get("total_tasks", 0) > 0:
            lines.append(f"{BOLD}🌊 V2A SPRINT BATCH{RESET}")

            progress_pct = v2a.get("progress_pct", 0)
            completed = v2a.get("completed", 0)
            total = v2a.get("total_tasks", 0)
            running = v2a.get("running", 0)
            failed = v2a.get("failed", 0)

            # Progress bar
            progress_color = GREEN if progress_pct >= 75 else YELLOW if progress_pct >= 25 else ""
            lines.append(
                f"  Progress: {progress_color}{completed}/{total} tasks ({progress_pct:.0f}%){RESET}"
            )

            if running > 0:
                lines.append(f"  {YELLOW}▶️  {running} running{RESET}")

            if failed > 0:
                lines.append(f"  {RED}❌ {failed} failed{RESET}")

            # Current wave
            current_wave = v2a.get("current_wave", "unknown")
            lines.append(f"  Current wave: {current_wave}")

            # Wave breakdown
            waves = v2a.get("waves", {})
            if waves:
                lines.append("")
                for wave_id in ["wave_1", "wave_2", "wave_3", "wave_4"]:
                    if wave_id in waves:
                        wave = waves[wave_id]
                        wave_completed = wave.get("completed", 0)
                        wave_total = wave.get("total", 0)
                        wave_progress = wave.get("progress_pct", 0)

                        if wave_completed == wave_total and wave_total > 0:
                            icon = "✅"
                        elif wave.get("running", 0) > 0:
                            icon = "🔄"
                        elif wave.get("ready", 0) > 0:
                            icon = "📋"
                        else:
                            icon = "⏸️"

                        status_text = f"{wave_completed}/{wave_total} ({wave_progress:.0f}%)"

                        if wave.get("ready", 0) > 0:
                            status_text += f" • {GREEN}{wave['ready']} ready{RESET}"
                        elif wave.get("blocked", 0) > 0:
                            status_text += f" • {wave['blocked']} blocked"

                        lines.append(f"    {icon} {wave_id}: {status_text}")

            # Estimated remaining time
            est_remaining = v2a.get("estimated_remaining_minutes", 0)
            if est_remaining > 0:
                if est_remaining < 60:
                    est_text = f"{est_remaining:.0f} minutes"
                else:
                    est_text = f"{est_remaining / 60:.1f} hours"
                lines.append(f"\n  Estimated remaining: {est_text}")

            lines.append(f"  💡 Check status: {BLUE}cortex v2a-batch status{RESET}")
            lines.append("")

    # Priority Actions
    lines.append(f"{BOLD}PRIORITY ACTIONS{RESET}")
    if briefing.priority_actions:
        for i, action in enumerate(briefing.priority_actions, 1):
            priority_color = (
                RED
                if action["priority"] == "HIGH"
                else YELLOW
                if action["priority"] == "MEDIUM"
                else GREEN
            )

            # Title with project inline
            project_suffix = (
                f" ({action['project']})"
                if action.get("project") and action["project"] != "General"
                else ""
            )
            lines.append(
                f"  {i}. [{priority_color}{action['priority']}{RESET}] {action['title']}{project_suffix}"
            )

            # Show progress if available
            if action.get("completion_percentage", 0) > 0:
                pct = action["completion_percentage"]
                progress_bar = _build_progress_bar(pct, style)
                lines.append(f"     Progress: {progress_bar} {pct}%")

            # Show steps/actions if available
            steps = action.get("steps", [])
            if steps:
                lines.append(f"     {YELLOW}Next steps:{RESET}")
                for step in steps[:3]:
                    if isinstance(step, str):
                        step_text = step
                    else:
                        step_text = (
                            getattr(step, "description", None)
                            or getattr(step, "title", None)
                            or str(step)
                        )
                    step_text = step_text[:70] + "..." if len(step_text) > 70 else step_text
                    lines.append(f"       → {step_text}")

            # Show success criteria if available
            if action.get("success_criteria"):
                criteria = action["success_criteria"]
                criteria_text = criteria[:80] + "..." if len(criteria) > 80 else criteria
                lines.append(f"     {GREEN}Done when:{RESET} {criteria_text}")

            # Show effort/impact for recommendations
            if action.get("estimated_effort") or action.get("estimated_impact"):
                meta_parts = []
                if action.get("estimated_effort"):
                    meta_parts.append(f"Effort: {action['estimated_effort']}")
                if action.get("estimated_impact"):
                    meta_parts.append(f"Impact: {action['estimated_impact']}")
                if meta_parts:
                    lines.append(f"     {BLUE}{' | '.join(meta_parts)}{RESET}")

            lines.append("")  # Spacing between actions

    else:
        lines.append("  No priority actions at this time")

    lines.append("")

    # ==================== ENHANCED INTELLIGENCE SECTIONS ====================

    # Temporal Context & Day Intelligence
    if briefing.temporal_context:
        tc = briefing.temporal_context
        lines.append(f"{BOLD}🕐 TODAY'S CONTEXT{RESET}")

        day = tc.get("day_of_week", "")
        time_of_day = tc.get("time_of_day", "")
        day_pattern = tc.get("day_pattern", {})

        lines.append(f"  {day} {time_of_day.title()}")
        if day_pattern.get("suggestion"):
            lines.append(f"  💡 {day_pattern['suggestion']}")

        # Session continuity
        session = tc.get("session_continuity")
        if session and session.get("last_focus"):
            lines.append(f"  📍 Last focus: {session['current_focus'][:60]}")

        lines.append("")

    # Predictive Insights
    if briefing.predictive_insights:
        pi = briefing.predictive_insights
        predictions = pi.get("predictions", [])
        optimal_sequence = pi.get("optimal_sequence", [])

        if predictions or optimal_sequence:
            lines.append(f"{BOLD}🔮 PREDICTIVE INSIGHTS{RESET}")

            if predictions:
                for pred in predictions[:2]:
                    conf_color = GREEN if pred.get("confidence") == "high" else YELLOW
                    lines.append(
                        f"  [{conf_color}{pred.get('confidence', 'medium').upper()}{RESET}] {pred['prediction']}"
                    )
                    if pred.get("reason"):
                        lines.append(f"      ↳ {pred['reason'][:60]}")

            if optimal_sequence:
                lines.append(f"  {BLUE}Suggested sequence for today:{RESET}")
                for i, item in enumerate(optimal_sequence[:3], 1):
                    lines.append(f"    {i}. {item['task'][:50]}")

            lines.append("")

    # Strategic Alignment
    if briefing.strategic_alignment:
        sa = briefing.strategic_alignment
        lines.append(f"{BOLD}🎯 STRATEGIC ALIGNMENT{RESET}")

        # Goal velocity status
        velocity = sa.get("velocity_status", "unknown")
        velocity_color = (
            GREEN if velocity == "healthy" else YELLOW if velocity == "backlog_growing" else RED
        )
        velocity_label = {
            "healthy": "On Track",
            "blocked": "Blocked",
            "backlog_growing": "Backlog Growing",
        }.get(velocity, velocity.title())

        completed = sa.get("completed", 0)
        in_progress = sa.get("in_progress", 0)
        pending = sa.get("pending", 0)
        blocked = sa.get("blocked", 0)

        lines.append(f"  Goal Velocity: [{velocity_color}{velocity_label}{RESET}]")
        lines.append(
            f"  Goals: {completed} done, {in_progress} active, {pending} pending, {blocked} blocked"
        )

        # High priority focus
        hp_total = sa.get("high_priority_total", 0)
        hp_completed = sa.get("high_priority_completed", 0)
        if hp_total > 0:
            hp_rate = hp_completed / hp_total * 100
            hp_color = GREEN if hp_rate >= 50 else YELLOW if hp_rate >= 25 else RED
            lines.append(
                f"  High-Priority: {hp_completed}/{hp_total} ({hp_color}{hp_rate:.0f}%{RESET})"
            )

        # Drift indicators
        drift_indicators = sa.get("drift_indicators", [])
        if drift_indicators:
            lines.append(f"  {YELLOW}⚠ Strategic Drift Detected:{RESET}")
            for drift in drift_indicators[:2]:
                lines.append(f"    - {drift}")

        lines.append("")

    # Intelligence Metrics (Learning System)
    if briefing.intelligence_metrics:
        im = briefing.intelligence_metrics
        if im.get("has_sufficient_data"):
            lines.append(f"{BOLD}🧠 CORTEX LEARNING{RESET}")

            accuracy = im.get("recommendation_accuracy", 0) * 100
            accuracy_color = GREEN if accuracy >= 70 else YELLOW if accuracy >= 50 else RED
            lines.append(
                f"  Recommendation Accuracy: {accuracy_color}{accuracy:.0f}%{RESET} ({im.get('followed_count', 0)} tracked)"
            )

            # Best performing type
            best = im.get("best_performing_type")
            if best:
                lines.append(
                    f"  {GREEN}Best performing:{RESET} {best['type']} ({best['success_rate'] * 100:.0f}% success)"
                )

            # Confidence calibration insight
            calibration = im.get("confidence_calibration", {})
            high_conf = calibration.get("high (0.8-1.0)", 0)
            low_conf = calibration.get("low (0.0-0.5)", 0)
            if high_conf > 0 and low_conf > 0:
                if high_conf > low_conf + 0.2:
                    lines.append("  💡 High-confidence recommendations performing well")
                elif low_conf > high_conf:
                    lines.append(f"  {YELLOW}💡 Confidence calibration needs adjustment{RESET}")

            lines.append("")

    # Phase 1 contract metrics (bandwidth instrumentation)
    if briefing.bandwidth_contract_metrics:
        bcm = briefing.bandwidth_contract_metrics
        sessions = int(bcm.get("sessions", 0))
        if sessions > 0:
            lines.append(f"{BOLD}🧩 BANDWIDTH CONTRACTS{RESET}")
            override_rate = float(bcm.get("override_rate", 0)) * 100
            autonomy_level = float(bcm.get("autonomy_level", 0)) * 100
            novelty_score = float(bcm.get("novelty_score", 0))

            override_color = GREEN if override_rate < 10 else YELLOW if override_rate < 20 else RED
            autonomy_color = (
                GREEN if autonomy_level >= 70 else YELLOW if autonomy_level >= 50 else RED
            )
            novelty_color = GREEN if novelty_score >= 5 else YELLOW if novelty_score >= 3 else RED

            lines.append(
                f"  override_rate: {override_color}{override_rate:.1f}%{RESET} ({sessions} sessions, 7d)"
            )
            lines.append(f"  autonomy_level: {autonomy_color}{autonomy_level:.1f}%{RESET}")
            lines.append(f"  novelty_score: {novelty_color}{novelty_score:.2f}/10{RESET}")
            lines.append("")

    if briefing.queue_slo:
        qs = briefing.queue_slo
        status = str(qs.get("status", "unknown"))
        color = GREEN if status == "healthy" else YELLOW if status == "warning" else RED
        lines.append(f"{BOLD}🚦 INTERACTION QUEUE SLO{RESET}")
        lines.append(
            f"  status: {color}{status.upper()}{RESET} (queue={qs.get('queue_lines', 0)}, processing={qs.get('processing_lines', 0)})"
        )
        lines.append("")

    # Cross-Project Insights
    if briefing.cross_project_insights:
        cpi = briefing.cross_project_insights
        shared_patterns = cpi.get("shared_patterns", [])
        relevant_lessons = cpi.get("relevant_lessons", [])
        health = cpi.get("portfolio_health")

        if shared_patterns or relevant_lessons or health:
            lines.append(f"{BOLD}🔗 CROSS-PROJECT INTELLIGENCE{RESET}")

            # Portfolio health
            if health:
                healthy = health.get("healthy_count", 0)
                at_risk = health.get("at_risk_count", 0)
                critical = health.get("critical_count", 0)
                if at_risk > 0 or critical > 0:
                    lines.append(
                        f"  Portfolio Health: {GREEN}{healthy} healthy{RESET}, {YELLOW}{at_risk} at risk{RESET}, {RED}{critical} critical{RESET}"
                    )
                else:
                    lines.append(
                        f"  Portfolio Health: {GREEN}All {healthy} projects healthy{RESET}"
                    )

            # Shared patterns
            if shared_patterns:
                lines.append("  Shared patterns in active projects:")
                for pattern in shared_patterns[:2]:
                    projects = ", ".join(pattern.get("shared_by", [])[:3])
                    lines.append(f"    - {pattern['pattern']} ({projects})")

            # Relevant lessons
            if relevant_lessons:
                lines.append(f"  {YELLOW}Relevant lessons:{RESET}")
                for lesson in relevant_lessons[:2]:
                    lesson_text = lesson.get("lesson", "")[:60]
                    lines.append(f"    - [{lesson.get('project', 'General')}] {lesson_text}")

            lines.append("")

    # Patterns Noticed
    lines.append(f"{BOLD}PATTERNS NOTICED{RESET}")
    if briefing.patterns:
        for pattern in briefing.patterns:
            lines.append(f"  {pattern}")
    else:
        lines.append("  No significant patterns detected")

    lines.append("=" * 64)

    return "\n".join(lines)
