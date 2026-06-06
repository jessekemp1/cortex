"""Briefing signal-quality helpers.

Pure functions that summarize working-tree noise (modified + untracked
counts) into a HIGH / MED / LOW signal-quality bucket, plus the small
`_sparkline` helper that draws a unicode mini-trend from a list of
floats.

Both the briefing generator (when shaping a `BriefingData` view) and
the formatters (when rendering it) need these helpers, so they live
in their own module instead of belonging to either one.
"""

from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from . import BriefingData


def _sparkline(values: List[float], charset: str) -> str:
    """Render mini trend chart from numeric values."""
    if not values:
        return ""
    chars = charset or "▁▂▃▄▅▆▇█"
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return chars[0] * len(values)
    span = hi - lo
    out = []
    last_idx = len(chars) - 1
    for v in values:
        idx = int(((v - lo) / span) * last_idx)
        out.append(chars[max(0, min(last_idx, idx))])
    return "".join(out)


def _compute_signal_quality(modified: int, untracked: int) -> str:
    """Compute signal quality from working-tree noise."""
    dirty_total = int(modified) + int(untracked)
    if dirty_total >= 75:
        return "LOW"
    if dirty_total >= 30:
        return "MED"
    return "HIGH"


def get_briefing_signal_quality(briefing: "BriefingData") -> Dict[str, int | str]:
    """Return signal quality and dirty-tree counts from briefing git summary."""
    modified = 0
    untracked = 0
    if briefing.git_status and briefing.git_status.get("summary"):
        gs = briefing.git_status["summary"]
        modified = int(gs.get("uncommitted_changes", gs.get("working_tree", {}).get("modified", 0)))
        untracked = int(gs.get("untracked_files", gs.get("working_tree", {}).get("untracked", 0)))
    quality = _compute_signal_quality(modified, untracked)
    return {
        "quality": quality,
        "modified": modified,
        "untracked": untracked,
        "dirty_total": modified + untracked,
    }
