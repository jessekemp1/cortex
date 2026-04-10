#!/usr/bin/env python3
"""
Resilient briefing generator with tiered fallback.

Tier 1: Full BriefingGenerator (local modules, no HTTP)
Tier 2: File-based intelligence (GOALS.md + git + ~/.cortex/ state files)
Tier 3: Minimal git status (absolute floor — never returns 'unavailable')
"""

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_resilient_briefing(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generate briefing with tiered fallback.

    Tier 1: Full BriefingGenerator (imports local modules, no HTTP needed)
    Tier 2: File-based intelligence (GOALS.md + git + ~/.cortex/ state files)
    Tier 3: Minimal git status (absolute floor — never returns 'unavailable')

    Returns dict with keys:
        tier (int): which tier succeeded
        data (dict): briefing data
        warnings (list[str]): what failed / why each tier was skipped
    """
    if root_dir is None:
        root_dir = Path(__file__).parent.parent  # monorepo root

    warnings: List[str] = []

    # --- Tier 1 ---
    try:
        data = _tier1_full_briefing(root_dir)
        return {"tier": 1, "data": data, "warnings": warnings}
    except Exception as exc:
        warnings.append(f"Tier 1 (BriefingGenerator) failed: {exc}")

    # --- Tier 2 ---
    try:
        data = _tier2_file_based(root_dir, warnings)
        return {"tier": 2, "data": data, "warnings": warnings}
    except Exception as exc:
        warnings.append(f"Tier 2 (file-based) failed: {exc}")

    # --- Tier 3 ---
    try:
        data = _tier3_minimal_git(root_dir, warnings)
        return {"tier": 3, "data": data, "warnings": warnings}
    except Exception as exc:
        warnings.append(f"Tier 3 (git status) failed: {exc}")
        return {
            "tier": 3,
            "data": {"git": {"status_lines": [], "recent_commits": [], "branch": "unknown"}},
            "warnings": warnings,
        }


def format_resilient_briefing(result: Dict[str, Any], use_color: bool = True) -> str:
    """Format the resilient briefing output based on tier."""
    tier = result.get("tier", 3)
    data = result.get("data", {})
    warnings = result.get("warnings", [])

    if tier == 1:
        return _format_tier1(data, use_color)
    elif tier == 2:
        return _format_tier2(data, warnings, use_color)
    else:
        return _format_tier3(data, warnings, use_color)


# ---------------------------------------------------------------------------
# Tier 1 — full BriefingGenerator (no HTTP, local imports only)
# ---------------------------------------------------------------------------


def _tier1_full_briefing(root_dir: Path) -> Dict[str, Any]:
    """Import and run BriefingGenerator directly."""
    cortex_dir = Path(__file__).parent
    if str(cortex_dir) not in sys.path:
        sys.path.insert(0, str(cortex_dir))

    from briefing import BriefingGenerator, generate_daily_briefing  # noqa: F401

    briefing = generate_daily_briefing(root_dir=root_dir)
    # Return the briefing object itself; format_tier1 will call format_briefing
    return {"briefing_object": briefing}


# ---------------------------------------------------------------------------
# Tier 2 — file-based intelligence
# ---------------------------------------------------------------------------


def _tier2_file_based(root_dir: Path, warnings: List[str]) -> Dict[str, Any]:
    """Build briefing from GOALS.md, git, and ~/.cortex/ state files."""
    data: Dict[str, Any] = {}

    # GOALS.md parsing
    goals_path = root_dir / "GOALS.md"
    try:
        data.update(_parse_goals_md(goals_path))
    except Exception as exc:
        warnings.append(f"GOALS.md parse failed: {exc}")
        data["immediate_actions"] = []
        data["active_goals"] = []
        data["high_priority"] = []

    # Git info
    try:
        data["git"] = _get_git_info(root_dir)
    except Exception as exc:
        warnings.append(f"git info failed: {exc}")
        data["git"] = {}

    # ~/.cortex/ state
    try:
        data["cortex_state"] = _get_cortex_state()
    except Exception as exc:
        warnings.append(f"cortex state read failed: {exc}")
        data["cortex_state"] = {}

    return data


def _parse_goals_md(goals_path: Path) -> Dict[str, Any]:
    """Parse GOALS.md and extract actions, goals, priorities."""
    if not goals_path.exists():
        raise FileNotFoundError(f"GOALS.md not found at {goals_path}")

    text = goals_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    immediate_actions = _extract_immediate_actions(lines)
    active_goals = _extract_active_goals(lines)
    high_priority = _extract_high_priority(lines)

    return {
        "immediate_actions": immediate_actions,
        "active_goals": active_goals,
        "high_priority": high_priority,
    }


def _extract_immediate_actions(lines: List[str]) -> List[Dict[str, str]]:
    """Extract items from ## Immediate Actions section."""
    # Find the Immediate Actions section
    in_section = False
    actions = []

    status_map = {
        "[ ]": "pending",
        "[x]": "done",
        "[X]": "done",
        "[~]": "on-hold",
        "[!]": "blocked",
    }

    for line in lines:
        stripped = line.strip()

        # Detect section start
        if re.match(r"^##\s+Immediate Actions", stripped):
            in_section = True
            continue

        # Detect section end (next ## section)
        if in_section and re.match(r"^##\s+", stripped) and not re.match(r"^###", stripped):
            break

        if not in_section:
            continue

        # Detect subsections
        if re.match(r"^###\s+This Week", stripped):
            continue
        elif re.match(r"^###\s+", stripped):
            # Other subsections (High Priority, etc.) — still collect from them
            pass  # other subsections
            continue

        # Parse checkbox items
        m = re.match(r"^-\s+(\[[xX~! ]\])\s+(.*)", stripped)
        if m:
            marker = m.group(1)
            text = m.group(2).strip()
            # Strip bold markers
            text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
            status = status_map.get(marker, "pending")
            actions.append({"text": text, "status": status})

    return actions


def _extract_active_goals(lines: List[str]) -> List[Dict[str, str]]:
    """Extract goal entries from ## Active Goals section."""
    in_section = False
    goals = []

    for line in lines:
        stripped = line.strip()

        if re.match(r"^##\s+Active Goals", stripped):
            in_section = True
            continue

        if in_section and re.match(r"^##\s+(?!#)", stripped):
            break

        if not in_section:
            continue

        # Match ### Goal N: Title
        m = re.match(r"^###\s+Goal\s+\d+:\s+(.*)", stripped)
        if m:
            title = m.group(1).strip()
            # Look ahead for priority/status on next lines — handled by reading the next line
            goals.append({"title": title, "priority": "", "status": ""})
            continue

        # Match **Priority:** / **Status:** lines after a goal header
        if goals:
            pm = re.search(r"\*\*Priority:\*\*\s*(\S+)", stripped)
            sm = re.search(r"\*\*Status:\*\*\s*(.+?)(?:\s*\||\s*$)", stripped)
            if pm:
                goals[-1]["priority"] = pm.group(1).strip(" |")
            if sm:
                goals[-1]["status"] = sm.group(1).strip()

    return goals


def _extract_high_priority(lines: List[str]) -> List[str]:
    """Extract ### High Priority items under ## Immediate Actions."""
    in_immediate = False
    in_high_priority = False
    items = []

    for line in lines:
        stripped = line.strip()

        if re.match(r"^##\s+Immediate Actions", stripped):
            in_immediate = True
            continue

        if in_immediate and re.match(r"^##\s+(?!#)", stripped):
            break

        if not in_immediate:
            continue

        if re.match(r"^###\s+High Priority", stripped):
            in_high_priority = True
            continue
        elif re.match(r"^###\s+", stripped):
            in_high_priority = False
            continue

        if in_high_priority:
            # Numbered items: "1. **text** — description"
            m = re.match(r"^\d+\.\s+(.*)", stripped)
            if m:
                text = m.group(1).strip()
                text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
                items.append(text)

    return items


def _get_git_info(root_dir: Path) -> Dict[str, Any]:
    """Get git status, recent commits, branch info."""
    cwd = str(root_dir)

    def run(cmd: List[str]) -> str:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    status_short = run(["git", "status", "--short"])
    log_oneline = run(["git", "log", "-5", "--oneline"])
    last_commit_date = run(["git", "log", "-1", "--format=%ci"])

    # Count uncommitted files
    uncommitted_lines = [l for l in status_short.splitlines() if l.strip()]
    uncommitted_count = len(uncommitted_lines)

    # Parse last commit time
    last_commit_ago = ""
    if last_commit_date:
        try:
            # Format: "2026-04-08 14:32:11 +1000"
            dt = datetime.strptime(last_commit_date[:19], "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            delta = now - dt
            hours = int(delta.total_seconds() // 3600)
            if hours < 1:
                last_commit_ago = "just now"
            elif hours < 24:
                last_commit_ago = f"{hours}h ago"
            else:
                days = hours // 24
                last_commit_ago = f"{days}d ago"
        except Exception:
            last_commit_ago = last_commit_date[:10]

    return {
        "branch": branch,
        "last_commit": last_commit_ago,
        "uncommitted_count": uncommitted_count,
        "uncommitted_files": [l.strip() for l in uncommitted_lines[:10]],
        "recent_log": [l.strip() for l in log_oneline.splitlines()],
    }


def _get_cortex_state() -> Dict[str, Any]:
    """Read ~/.cortex/ state files for outcomes count and recent alerts."""
    cortex_home = Path.home() / ".cortex"
    state: Dict[str, Any] = {}

    # Count outcomes
    outcomes_path = cortex_home / "learning" / "outcomes.jsonl"
    if outcomes_path.exists():
        try:
            count = sum(1 for _ in outcomes_path.open(encoding="utf-8"))
            state["outcomes_count"] = count
        except Exception:
            state["outcomes_count"] = 0
    else:
        state["outcomes_count"] = 0

    # Batch directory
    batch_dir = cortex_home / "batch"
    if batch_dir.exists():
        try:
            batch_files = list(batch_dir.iterdir())
            state["batch_files"] = len(batch_files)
        except Exception:
            state["batch_files"] = 0

    # Recent alerts
    alerts_path = cortex_home / "alerts.jsonl"
    recent_alerts: List[str] = []
    if alerts_path.exists():
        try:
            import json

            lines = alerts_path.read_text(encoding="utf-8").splitlines()
            for raw in reversed(lines[-20:]):
                try:
                    obj = json.loads(raw)
                    msg = obj.get("message") or obj.get("msg") or str(obj)
                    recent_alerts.append(msg[:120])
                    if len(recent_alerts) >= 3:
                        break
                except Exception:
                    pass
        except Exception:
            pass
    state["recent_alerts"] = recent_alerts

    return state


# ---------------------------------------------------------------------------
# Tier 3 — minimal git status (absolute floor)
# ---------------------------------------------------------------------------


def _tier3_minimal_git(root_dir: Path, warnings: List[str]) -> Dict[str, Any]:
    """Run bare minimum git commands — always works in a git repo."""
    cwd = str(root_dir)

    def run(cmd: List[str]) -> List[str]:
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10)
            return result.stdout.strip().splitlines()
        except Exception:
            return []

    status_lines = run(["git", "status", "--short"])
    recent_commits = run(["git", "log", "-3", "--oneline"])

    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        branch = branch_result.stdout.strip() or "unknown"
    except Exception:
        branch = "unknown"

    return {
        "git": {
            "status_lines": [l.strip() for l in status_lines],
            "recent_commits": [l.strip() for l in recent_commits],
            "branch": branch,
        }
    }


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_RED = "\033[31m"
_DIM = "\033[2m"


def _c(text: str, code: str, use_color: bool) -> str:
    return f"{code}{text}{_RESET}" if use_color else text


def _format_tier1(data: Dict[str, Any], use_color: bool) -> str:
    """Delegate to briefing.py's format_briefing."""
    try:
        from briefing import format_briefing  # type: ignore

        briefing = data.get("briefing_object")
        if briefing is not None:
            return format_briefing(briefing, use_color=use_color)
    except Exception:
        pass
    return str(data)


def _format_tier2(data: Dict[str, Any], warnings: List[str], use_color: bool) -> str:
    lines = []

    header = "CORTEX BRIEFING (local mode — bridge unavailable)"
    sep = "─" * len(header)
    lines.append(_c(header, _BOLD, use_color))
    lines.append(sep)
    lines.append("")

    # Git summary
    git = data.get("git", {})
    branch = git.get("branch", "unknown")
    last_commit = git.get("last_commit", "?")
    uncommitted = git.get("uncommitted_count", 0)
    git_line = f"Branch: {branch} | Last commit: {last_commit}"
    if uncommitted:
        files_hint = ""
        files = git.get("uncommitted_files", [])
        if files:
            # Show unique path prefixes
            prefixes = sorted({f.split("/")[0].lstrip("? MAD") for f in files if f})
            files_hint = f" ({', '.join(prefixes[:3])})"
        git_line += f" | Uncommitted: {uncommitted} files{files_hint}"
    lines.append(git_line)
    lines.append("")

    # Immediate Actions
    actions = data.get("immediate_actions", [])
    if actions:
        lines.append(_c("Immediate Actions:", _BOLD, use_color))
        status_symbol = {"pending": "[ ]", "done": "[x]", "on-hold": "[~]", "blocked": "[!]"}
        for a in actions:
            sym = status_symbol.get(a.get("status", "pending"), "[ ]")
            text = a.get("text", "")
            # dim done/on-hold items
            if a.get("status") in ("done", "on-hold"):
                line = f"  {_c(sym + ' ' + text, _DIM, use_color)}"
            elif a.get("status") == "blocked":
                line = f"  {_c(sym + ' ' + text, _RED, use_color)}"
            else:
                line = f"  {sym} {text}"
            lines.append(line)
        lines.append("")

    # High Priority
    high = data.get("high_priority", [])
    if high:
        lines.append(_c("High Priority:", _BOLD, use_color))
        for i, item in enumerate(high, 1):
            lines.append(f"  {i}. {item}")
        lines.append("")

    # Active Goals summary (compact)
    goals = data.get("active_goals", [])
    if goals:
        lines.append(_c("Active Goals:", _BOLD, use_color))
        for g in goals[:5]:
            title = g.get("title", "")
            status = g.get("status", "")
            priority = g.get("priority", "")
            meta = " | ".join(filter(None, [priority, status]))
            if meta:
                lines.append(f"  {title}  [{meta}]")
            else:
                lines.append(f"  {title}")
        if len(goals) > 5:
            lines.append(f"  ... and {len(goals) - 5} more")
        lines.append("")

    # Cortex state
    cs = data.get("cortex_state", {})
    if cs:
        outcomes = cs.get("outcomes_count", 0)
        if outcomes:
            lines.append(f"Cortex outcomes: {outcomes}")
        alerts = cs.get("recent_alerts", [])
        if alerts:
            lines.append("Recent alerts:")
            for a in alerts:
                lines.append(f"  - {a}")
        lines.append("")

    lines.append(_c("Running in local mode. Start bridge: cortex serve", _YELLOW, use_color))

    return "\n".join(lines)


def _format_tier3(data: Dict[str, Any], warnings: List[str], use_color: bool) -> str:
    lines = []

    header = "CORTEX BRIEFING (MINIMAL MODE — local files unavailable)"
    sep = "=" * len(header)
    lines.append(_c(header, _BOLD + _RED, use_color))
    lines.append(sep)
    lines.append("")

    git = data.get("git", {})
    branch = git.get("branch", "unknown")
    lines.append(f"Branch: {branch}")
    lines.append("")

    status_lines = git.get("status_lines", [])
    if status_lines:
        lines.append("Uncommitted changes:")
        for sl in status_lines[:20]:
            lines.append(f"  {sl}")
        lines.append("")

    recent = git.get("recent_commits", [])
    if recent:
        lines.append("Recent commits:")
        for c in recent:
            lines.append(f"  {c}")
        lines.append("")

    if warnings:
        lines.append(_c("Degradation warnings:", _YELLOW, use_color))
        for w in warnings:
            lines.append(f"  - {w}")
        lines.append("")

    lines.append(_c("MINIMAL MODE ACTIVE — bridge and local files unavailable.", _RED, use_color))
    lines.append(
        "To restore full briefing: ensure cortex/ modules are importable and run 'cortex serve'."
    )

    return "\n".join(lines)
