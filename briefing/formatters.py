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

Still in `briefing/__init__.py` (pending future commits):
  - `format_briefing`         full text briefing (~1075 LOC — biggest single
                              function; needs its own focused turn)
  - `format_briefing_json`    JSON serialization of format_briefing's payload
  - `format_compact`          bordered-box compact view
  - `detect_resume_context`   git-state signal helper
  - `detect_stale_items`      GOALS.md stale-action helper
"""

from __future__ import annotations

import getpass
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

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
