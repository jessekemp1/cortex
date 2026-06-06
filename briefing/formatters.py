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

Still in `briefing/__init__.py` (pending future commits):
  - `format_briefing`         full text briefing (~1075 LOC — biggest single
                              function; needs its own focused turn)
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
