#!/usr/bin/env python3
"""
Cortex Weekly Planner — Proactive "This Week" proposal engine.

Reads GOALS.md, scores all pending items by priority × deadline urgency,
and proposes an optimal 5-7 item "This Week" list. Can also update GOALS.md
directly.

Usage:
    python cortex/weekly_planner.py              # print proposal
    python cortex/weekly_planner.py --update     # update GOALS.md This Week section
    python cortex/weekly_planner.py --json       # machine-readable output
    python cortex/weekly_planner.py --capacity   # show velocity/capacity breakdown only

Item state legend (five-state model):
    - [ ]  pending    — in scope
    - [>]  in-progress
    - [~]  on-hold    — skip
    - [!]  blocked    — skip until blocker resolved
    - [x]  done       — skip
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import os

REPO_ROOT = Path(os.environ.get("CORTEX_DEV_ROOT", str(Path.home() / "Dev")))
GOALS_FILE = REPO_ROOT / "GOALS.md"

MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

PRIORITY_WEIGHT = {"P1": 3.0, "P2": 2.0, "P3": 1.0}

# Project dirs for velocity lookup (monorepo-relative)
VELOCITY_PROJECTS = {
    "vortex": "Vortex/backend",
    "vortex_frontend": "Vortex/frontend",
    "cortex": "cortex",
    "alpha_arena": "alpha_arena",
    "pupil": "pupil",
    "ore": "ore",
    "from_within": "from-within",
}

# Map goal name keywords → project for capacity matching
GOAL_PROJECT_MAP = {
    "vortex": "vortex",
    "hetzner": "vortex",
    "navigator": "vortex_frontend",
    "cortex": "cortex",
    "alpha arena": "alpha_arena",
    "arena": "alpha_arena",
    "pupil": "pupil",
    "ore": "ore",
    "from(within)": "from_within",
    "kempion": "vortex",  # site work counted against general capacity
}


@dataclass
class GoalItem:
    goal_num: int
    goal_name: str
    priority: str  # P1, P2, P3
    deadline: date | None
    item_text: str
    state: str  # pending, in_progress, on_hold, blocked, done
    project: str  # inferred project
    score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)
    days_until_deadline: int | None = None


def _run_cmd(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(REPO_ROOT),
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _parse_goals(goals_text: str) -> list[GoalItem]:
    """Parse all goals and their items from GOALS.md."""
    items: list[GoalItem] = []
    today = date.today()

    # Split into goal blocks
    goal_blocks = re.split(r"(?=###\s+Goal\s+\d+:)", goals_text)

    for block in goal_blocks:
        goal_match = re.match(r"###\s+Goal\s+(\d+):\s*(.+?)$", block, re.MULTILINE)
        if not goal_match:
            continue

        goal_num = int(goal_match.group(1))
        goal_name = goal_match.group(2).strip()

        # Extract priority
        priority_match = re.search(r"\*\*Priority:\*\*\s*(P\d)", block)
        priority = priority_match.group(1) if priority_match else "P3"

        # Extract deadline
        deadline: date | None = None
        days_until: int | None = None
        target_match = re.search(r"\*\*Target:\*\*\s*([^|]+?)(?:\||$)", block)
        if target_match:
            target_str = target_match.group(1)
            date_match = re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})",
                target_str,
            )
            if date_match:
                try:
                    deadline = date(2026, MONTH_MAP[date_match.group(1)], int(date_match.group(2)))
                    days_until = (deadline - today).days
                except ValueError:
                    pass

        # Skip goals that are DONE/ARCHIVED
        status_match = re.search(r"\*\*Status:\*\*\s*(.+?)(?:\||$|\n)", block)
        status_val = status_match.group(1).upper().strip() if status_match else ""
        if any(w in status_val for w in ("DONE", "COMPLETE", "ARCHIVED", "ON HOLD")):
            continue

        # Infer project from goal name
        project = "general"
        for keyword, proj in GOAL_PROJECT_MAP.items():
            if keyword.lower() in goal_name.lower():
                project = proj
                break

        # Parse items
        for m in re.finditer(r"^- (\[[ x>~!]\]) (.+)$", block, re.MULTILINE):
            marker = m.group(1)
            text = m.group(2).strip()

            state = {
                "[ ]": "pending",
                "[x]": "done",
                "[>]": "in_progress",
                "[~]": "on_hold",
                "[!]": "blocked",
            }.get(marker, "pending")

            items.append(
                GoalItem(
                    goal_num=goal_num,
                    goal_name=goal_name,
                    priority=priority,
                    deadline=deadline,
                    item_text=text,
                    state=state,
                    project=project,
                    days_until_deadline=days_until,
                )
            )

    return items


def _get_current_week_items(goals_text: str) -> set[str]:
    """Return set of item texts already in the This Week section."""
    imm_start = goals_text.find("## Immediate Actions")
    if imm_start < 0:
        return set()
    imm_end = goals_text.find("\n## ", imm_start + 1)
    immediate_body = goals_text[imm_start : imm_end if imm_end > 0 else len(goals_text)]

    # Find most recent "This Week" subsection
    week_match = None
    for m in re.finditer(r"###\s+(This Week|Current Week)", immediate_body):
        week_match = m
    if not week_match:
        return set()

    next_sub = re.search(r"\n###", immediate_body[week_match.start() + 1 :])
    week_end = week_match.start() + 1 + next_sub.start() if next_sub else len(immediate_body)
    week_body = immediate_body[week_match.start() : week_end]

    return {m.group(1).strip()[:80] for m in re.finditer(r"- \[[ >]\] (.+)", week_body)}


def _get_goal_done_count(block: str) -> int:
    return len(re.findall(r"- \[x\]", block))


def _score_item(item: GoalItem, today: date) -> tuple[float, dict]:
    """
    Score = priority_weight × urgency_multiplier + new_goal_bonus

    urgency_multiplier:
        overdue      → 5.0
        ≤1 day       → 4.0
        ≤3 days      → 3.0
        ≤7 days      → 2.0
        ≤14 days     → 1.5
        >14 days     → 1.0
        no deadline  → 0.8
    """
    priority_w = PRIORITY_WEIGHT.get(item.priority, 1.0)

    if item.deadline is None:
        urgency = 0.8
        urgency_label = "no deadline"
    elif item.days_until_deadline is not None:
        d = item.days_until_deadline
        if d < 0:
            urgency, urgency_label = 5.0, "OVERDUE"
        elif d == 0:
            urgency, urgency_label = 4.5, "due today"
        elif d <= 1:
            urgency, urgency_label = 4.0, f"due in {d}d"
        elif d <= 3:
            urgency, urgency_label = 3.0, f"due in {d}d"
        elif d <= 7:
            urgency, urgency_label = 2.0, f"due in {d}d"
        elif d <= 14:
            urgency, urgency_label = 1.5, f"due in {d}d"
        else:
            urgency, urgency_label = 1.0, f"due in {d}d"
    else:
        urgency, urgency_label = 0.8, "no deadline"

    score = priority_w * urgency
    breakdown = {
        "priority": item.priority,
        "priority_weight": priority_w,
        "urgency_multiplier": urgency,
        "urgency_label": urgency_label,
        "base_score": round(score, 2),
    }
    return round(score, 2), breakdown


def _get_velocity(project: str) -> int:
    """Commits in last 7 days for a project path."""
    proj_path = VELOCITY_PROJECTS.get(project)
    if not proj_path:
        return 0
    raw = _run_cmd(f"git log --oneline --after='7 days ago' -- {proj_path} | wc -l")
    try:
        return int(raw.strip())
    except ValueError:
        return 0


def _velocity_to_capacity(commits_7d: int) -> int:
    """Rough heuristic: ~5 commits per meaningful task."""
    return max(1, commits_7d // 5)


def propose_week(
    goals_text: str | None = None,
    max_items: int = 7,
) -> dict:
    """
    Core planning function. Returns:
    {
        "proposed": [GoalItem, ...],    # top scored items
        "on_hold": int,
        "blocked": int,
        "already_scheduled": int,
        "capacity": {project: n},
        "explanation": str,
    }
    """
    if goals_text is None:
        goals_text = GOALS_FILE.read_text()

    today = date.today()
    all_items = _parse_goals(goals_text)
    current_week = _get_current_week_items(goals_text)

    # Separate by state
    candidates: list[GoalItem] = []
    on_hold_count = 0
    blocked_count = 0
    in_progress_count = 0
    already_scheduled = 0

    for item in all_items:
        if item.state in ("done", "on_hold"):
            if item.state == "on_hold":
                on_hold_count += 1
            continue
        if item.state == "blocked":
            blocked_count += 1
            continue
        if item.state == "in_progress":
            in_progress_count += 1
            continue
        # Check if already in This Week
        item_key = item.item_text[:80]
        if any(item_key[:40] in existing for existing in current_week):
            already_scheduled += 1
            continue
        # Score
        score, breakdown = _score_item(item, today)
        item.score = score
        item.score_breakdown = breakdown
        candidates.append(item)

    # Sort by score descending, break ties by goal_num
    candidates.sort(key=lambda x: (-x.score, x.goal_num))

    # Dedupe: take only first item per goal to avoid monopolising the list
    # (subsequent items from same goal go lower)
    seen_goals: set[int] = set()
    proposed: list[GoalItem] = []
    deferred: list[GoalItem] = []
    for item in candidates:
        if item.goal_num not in seen_goals:
            proposed.append(item)
            seen_goals.add(item.goal_num)
        else:
            deferred.append(item)
        if len(proposed) >= max_items:
            break

    # If we have fewer than max_items, backfill from deferred
    remaining = max_items - len(proposed)
    if remaining > 0:
        proposed.extend(deferred[:remaining])
        proposed.sort(key=lambda x: (-x.score, x.goal_num))

    # Capacity breakdown
    capacity = {}
    for proj in VELOCITY_PROJECTS:
        commits = _get_velocity(proj)
        if commits > 0:
            capacity[proj] = {"commits_7d": commits, "est_items": _velocity_to_capacity(commits)}

    return {
        "proposed": proposed[:max_items],
        "on_hold_count": on_hold_count,
        "blocked_count": blocked_count,
        "in_progress_count": in_progress_count,
        "already_scheduled": already_scheduled,
        "total_candidates": len(candidates),
        "capacity": capacity,
        "generated": today.isoformat(),
    }


def format_proposal(result: dict) -> str:
    """Terminal-formatted output of the weekly plan proposal."""
    proposed = result["proposed"]
    capacity = result["capacity"]
    today_str = result["generated"]

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  CORTEX WEEKLY PLANNER  —  This Week Proposal           ║",
        f"║  {today_str}  │  scoring: priority × urgency             ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  Candidates: {result['total_candidates']} open items  │  "
        f"On hold: {result['on_hold_count']}  │  "
        f"Blocked: {result['blocked_count']}  │  "
        f"Already scheduled: {result['already_scheduled']}",
        "",
        "  ── Proposed This Week (" + f"{len(proposed)} items) " + "─" * 28,
        "",
    ]

    for i, item in enumerate(proposed, 1):
        bd = item.score_breakdown
        deadline_tag = f"  [{bd['urgency_label']}]" if bd.get("urgency_label") else ""
        priority_tag = f"[{item.priority}]"

        # Truncate long item text
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", item.item_text)  # strip bold
        text = text[:72] + "…" if len(text) > 72 else text

        lines.append(f"  {i}. {priority_tag} {text}")
        lines.append(
            f"       Goal {item.goal_num}: {item.goal_name[:50]}  "
            f"score={item.score:.1f}{deadline_tag}"
        )
        lines.append("")

    # Capacity section
    if capacity:
        lines.append("  ── Velocity & Capacity (last 7d) " + "─" * 25)
        lines.append("")
        for proj, stats in sorted(capacity.items(), key=lambda x: -x[1]["commits_7d"]):
            bar_width = min(stats["commits_7d"] // 2, 20)
            bar = "█" * bar_width
            lines.append(
                f"  {proj:20s}  {stats['commits_7d']:3d} commits  "
                f"{bar}  ~{stats['est_items']} items capacity"
            )
        lines.append("")

    # Items not yet proposed (deferred)
    lines += [
        "  ── Status ──────────────────────────────────────────",
        f"  In-progress [>]: {result['in_progress_count']}",
        f"  On hold     [~]: {result['on_hold_count']}",
        f"  Blocked     [!]: {result['blocked_count']}",
        "  ════════════════════════════════════════════════════",
    ]

    return "\n".join(lines)


def update_goals_this_week(result: dict, goals_text: str) -> str:
    """
    Replace the content of the '### This Week' subsection in GOALS.md
    with the proposed items, preserving in-progress [>] items already there.

    Returns updated goals_text.
    """
    proposed = result["proposed"]
    today = date.today()
    week_end = today + timedelta(days=(6 - today.weekday()))  # next Sunday
    header = f"### This Week ({today.strftime('%b %-d')}–{week_end.strftime('%b %-d')})"

    # Build new section content
    new_lines = [header, ""]
    for item in proposed:
        text = item.item_text
        # Preserve any bold markers for readability
        new_lines.append(f"- [ ] {text}")
    new_lines.append("")
    new_section = "\n".join(new_lines)

    # Find and replace existing This Week section
    imm_start = goals_text.find("## Immediate Actions")
    if imm_start < 0:
        return goals_text

    imm_end = goals_text.find("\n## ", imm_start + 1)
    immediate_body = goals_text[imm_start : imm_end if imm_end > 0 else len(goals_text)]

    # Find existing This Week header
    week_match = None
    for m in re.finditer(r"###\s+(This Week|Current Week)[^\n]*\n", immediate_body):
        week_match = m

    if week_match:
        # Find end of existing This Week section (next ### or end of immediate body)
        next_sub = re.search(r"\n###", immediate_body[week_match.end() :])
        section_end = week_match.end() + (next_sub.start() + 1 if next_sub else len(immediate_body))
        # Replace
        updated_imm = (
            immediate_body[: week_match.start()] + new_section + immediate_body[section_end:]
        )
    else:
        # Append at end of immediate body
        updated_imm = immediate_body.rstrip() + "\n\n" + new_section

    if imm_end > 0:
        return goals_text[:imm_start] + updated_imm + goals_text[imm_end:]
    return goals_text[:imm_start] + updated_imm


def main() -> None:
    args = sys.argv[1:]
    do_update = "--update" in args
    json_only = "--json" in args
    capacity_only = "--capacity" in args

    goals_text = GOALS_FILE.read_text()
    result = propose_week(goals_text)

    if capacity_only:
        for proj, stats in result["capacity"].items():
            print(f"{proj}: {stats['commits_7d']} commits → ~{stats['est_items']} items")
        return

    if json_only:
        # Serialise GoalItem objects
        out = {k: v for k, v in result.items() if k != "proposed"}
        out["proposed"] = [
            {
                "goal_num": i.goal_num,
                "goal_name": i.goal_name,
                "priority": i.priority,
                "item_text": i.item_text,
                "score": i.score,
                "score_breakdown": i.score_breakdown,
                "days_until_deadline": i.days_until_deadline,
            }
            for i in result["proposed"]
        ]
        print(json.dumps(out, indent=2))
        return

    print(format_proposal(result))

    if do_update:
        updated = update_goals_this_week(result, goals_text)
        GOALS_FILE.write_text(updated)
        print("\n  GOALS.md updated — 'This Week' section replaced.")
        print("  Review: grep -A 30 'This Week' GOALS.md")


if __name__ == "__main__":
    main()
