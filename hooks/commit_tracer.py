#!/usr/bin/env python3
"""
Commit Tracer — post-commit hook component.

Links every commit to an active GOALS.md goal via:
  1. Explicit [goal-N] tag in the commit message (opt-in, highest priority)
  2. Conventional commit prefix: feat(project) -> project keyword mapping
  3. Files changed: project directory prefix -> keyword mapping

Appends to ~/.cortex/metrics/goal_velocity.jsonl for portfolio velocity tracking.
Called by .git/hooks/post-commit (non-blocking, fails silently).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
VELOCITY_LOG = Path.home() / ".cortex" / "metrics" / "goal_velocity.jsonl"

# Project prefix → goal keyword mapping
# Update when GOALS.md goals change
PROJECT_TO_GOAL: dict[str, str] = {
    "cortex":           "Cortex Orchestration Platform",
    "vortex-backend":   "Vortex Production Readiness",
    "vortex-frontend":  "Vortex Production Readiness",
    "winfield":         "Winfield Marine Nowcasting Engine",
    "alpha_arena":      "Alpha Arena Strategy Refinement",
    "alpha-arena":      "Alpha Arena Strategy Refinement",
    "pupil":            "Pupil Prediction",
    "emos":             "Vortex Production Readiness",
    "nowcast":          "Winfield Marine Nowcasting Engine",
    "grib":             "Vortex Production Readiness",
    "blend":            "Winfield Marine Nowcasting Engine",
    "arena":            "Alpha Arena Strategy Refinement",
}

# Project directory prefixes
DIR_TO_PROJECT: dict[str, str] = {
    "Vortex/backend/":   "vortex-backend",
    "Vortex/frontend/":  "vortex-frontend",
    "Vortex/Winfield/":  "winfield",
    "alpha_arena/":      "alpha_arena",
    "cortex/":           "cortex",
    "pupil/":            "pupil",
    "scripts/":          "scripts",
}


def _git(*args) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def parse_goals(goals_file: Path) -> dict[int, dict]:
    """Parse GOALS.md into {goal_num: {title, status}} dict."""
    goals = {}
    if not goals_file.exists():
        return goals
    try:
        for line in goals_file.read_text().splitlines():
            m = re.match(r"^### Goal (\d+): (.+?)(?:\s*\[(.+?)\])?\s*$", line)
            if m:
                num = int(m.group(1))
                title = m.group(2).strip()
                bracket = m.group(3) or ""
                if "COMPLETE" in bracket or "DONE" in bracket:
                    status = "complete"
                elif "IN PROGRESS" in bracket:
                    status = "in_progress"
                elif "BLOCKED" in bracket:
                    status = "blocked"
                else:
                    status = "active"
                goals[num] = {"title": title, "status": status}
    except Exception:
        pass
    return goals


def detect_project_from_files(files: list[str]) -> str | None:
    """Determine dominant project from changed file paths."""
    counts: dict[str, int] = {}
    for f in files:
        for prefix, project in DIR_TO_PROJECT.items():
            if f.startswith(prefix):
                counts[project] = counts.get(project, 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def match_goal(commit_msg: str, project: str | None, goals: dict) -> str | None:
    """Match commit to a goal title. Returns goal title or None."""
    # 1. Explicit [goal-N] tag
    m = re.search(r"\[goal-(\d+)\]", commit_msg, re.IGNORECASE)
    if m:
        num = int(m.group(1))
        if num in goals:
            return goals[num]["title"]

    # 2. Commit prefix: feat(keyword) or fix(keyword)
    prefix_m = re.match(r"^\w+\((\w[\w-]*)\)", commit_msg)
    if prefix_m:
        keyword = prefix_m.group(1).lower()
        if keyword in PROJECT_TO_GOAL:
            return PROJECT_TO_GOAL[keyword]

    # 3. Project directory mapping
    if project and project in PROJECT_TO_GOAL:
        return PROJECT_TO_GOAL[project]

    return None


def main():
    try:
        commit = _git("rev-parse", "HEAD")
        if not commit:
            return

        msg = _git("log", "-1", "--pretty=%B", commit).splitlines()[0] if commit else ""
        files_raw = _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
        files = [f for f in files_raw.splitlines() if f]

        lines_raw = _git("diff-tree", "--no-commit-id", "--stat", commit)
        # Parse insertions/deletions from stat summary line
        insertions, deletions = 0, 0
        for line in lines_raw.splitlines():
            ins_m = re.search(r"(\d+) insertion", line)
            del_m = re.search(r"(\d+) deletion", line)
            if ins_m:
                insertions = int(ins_m.group(1))
            if del_m:
                deletions = int(del_m.group(1))

        goals = parse_goals(REPO_ROOT / "GOALS.md")
        project = detect_project_from_files(files)
        goal = match_goal(msg, project, goals)

        # Determine goal status from parsed goals
        goal_status = "unknown"
        if goal:
            for g in goals.values():
                if g["title"] == goal:
                    goal_status = g["status"]
                    break

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "commit": commit[:12],
            "message": msg[:120],
            "goal": goal,
            "goal_status": goal_status,
            "project": project,
            "files_changed": len(files),
            "insertions": insertions,
            "deletions": deletions,
        }

        VELOCITY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(VELOCITY_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    except Exception:
        pass  # Never fail the post-commit hook


if __name__ == "__main__":
    main()
