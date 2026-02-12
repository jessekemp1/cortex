#!/usr/bin/env python3
"""
Cortex V1: Branch Lifecycle Manager

State machine for branch health:
  ACTIVE_DEVELOPMENT -> READY_FOR_REVIEW -> PR_OPEN -> MERGEABLE

Transitions based on: age, commits ahead, test status, PR state.
State stored in .git/cortex-lifecycle.json.
Called by: /status command.
"""

import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class BranchState(str, Enum):
    ACTIVE_DEVELOPMENT = "ACTIVE_DEVELOPMENT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    PR_OPEN = "PR_OPEN"
    MERGEABLE = "MERGEABLE"


STATE_FILE = ".git/cortex-lifecycle.json"


def load_state(repo_path: str = ".") -> dict:
    path = Path(repo_path) / STATE_FILE
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict, repo_path: str = "."):
    path = Path(repo_path) / STATE_FILE
    path.write_text(json.dumps(state, indent=2) + "\n")


def get_branch_name(repo_path: str = ".") -> str:
    try:
        return subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return ""


def get_commits_ahead(branch: str, base: str = "main", repo_path: str = ".") -> int:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base}..{branch}"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        return int(result.stdout.strip())
    except Exception:
        return 0


def get_branch_age_days(branch: str, base: str = "main", repo_path: str = ".") -> float:
    try:
        result = subprocess.run(
            ["git", "log", "--format=%aI", "--reverse", f"{base}..{branch}"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return 0.0
        first = datetime.fromisoformat(lines[0])
        return (datetime.now(timezone.utc) - first.astimezone(timezone.utc)).total_seconds() / 86400
    except Exception:
        return 0.0


def check_open_pr(branch: str, repo_path: str = ".") -> dict | None:
    try:
        result = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "number,state,mergeable,title"],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def determine_state(branch: str, commits_ahead: int, age_days: float, pr_info: dict | None) -> BranchState:
    if pr_info:
        if pr_info.get("state") == "OPEN":
            if pr_info.get("mergeable") == "MERGEABLE":
                return BranchState.MERGEABLE
            return BranchState.PR_OPEN
    if age_days >= 1 and commits_ahead >= 3:
        return BranchState.READY_FOR_REVIEW
    return BranchState.ACTIVE_DEVELOPMENT


def get_status_line(repo_path: str = ".") -> str:
    branch = get_branch_name(repo_path)
    if not branch or branch in ("main", "master"):
        return f"Branch: {branch or 'detached'} (main branch)"

    commits = get_commits_ahead(branch, repo_path=repo_path)
    age = get_branch_age_days(branch, repo_path=repo_path)
    pr_info = check_open_pr(branch, repo_path)
    state = determine_state(branch, commits, age, pr_info)

    lifecycle = load_state(repo_path)
    lifecycle[branch] = {
        "state": state.value,
        "commits_ahead": commits,
        "age_days": round(age, 1),
        "has_pr": pr_info is not None,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    save_state(lifecycle, repo_path)

    age_str = f"{age:.1f}d" if age < 1 else f"{age:.0f}d"
    pr_str = f", PR #{pr_info['number']}" if pr_info else ""
    return f"Branch: {state.value} ({age_str}, {commits} commits{pr_str})"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cortex V1 Branch Lifecycle Manager")
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.json:
        branch = get_branch_name(args.repo)
        commits = get_commits_ahead(branch, repo_path=args.repo)
        age = get_branch_age_days(branch, repo_path=args.repo)
        pr_info = check_open_pr(branch, args.repo)
        state = determine_state(branch, commits, age, pr_info)
        print(json.dumps({
            "branch": branch, "state": state.value,
            "commits_ahead": commits, "age_days": round(age, 1), "pr": pr_info,
        }, indent=2))
    else:
        print(get_status_line(args.repo))


if __name__ == "__main__":
    main()
