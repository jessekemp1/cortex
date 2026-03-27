"""
Git & GitHub Integration for Cortex

Tracks:
- Local branches and their state
- Open PRs via GitHub CLI (gh)
- Stale work detection
- Development velocity metrics
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Branch:
    """Represents a git branch with metadata."""

    name: str
    is_current: bool
    last_commit_date: Optional[datetime]
    last_commit_msg: str
    ahead_of_main: int
    behind_main: int
    age_days: int
    project: Optional[str] = None  # Extracted from branch name

    @property
    def is_stale(self) -> bool:
        """Branch is stale if >7 days old with no recent commits."""
        return self.age_days > 7

    @property
    def branch_type(self) -> str:
        """Extract type from branch name (feat/fix/refactor)."""
        if self.name.startswith("feat/"):
            return "feature"
        elif self.name.startswith("fix/"):
            return "bugfix"
        elif self.name.startswith("refactor/"):
            return "refactor"
        return "other"


@dataclass
class PullRequest:
    """Represents a GitHub pull request."""

    number: int
    title: str
    branch: str
    state: str  # open, closed, merged
    created_at: datetime
    updated_at: datetime
    url: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    is_draft: bool = False
    review_status: str = ""  # approved, changes_requested, pending

    @property
    def age_days(self) -> int:
        return (datetime.now() - self.created_at).days

    @property
    def is_stale(self) -> bool:
        return self.age_days > 3 and self.state == "open"


@dataclass
class GitState:
    """Complete Git/GitHub state for a repository."""

    repo_path: Path
    current_branch: str
    branches: List[Branch]
    open_prs: List[PullRequest]
    uncommitted_changes: int
    untracked_files: int
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def active_feature_branches(self) -> List[Branch]:
        return [b for b in self.branches if b.name != "main" and not b.is_stale]

    @property
    def stale_branches(self) -> List[Branch]:
        return [b for b in self.branches if b.is_stale and b.name != "main"]

    @property
    def prs_needing_attention(self) -> List[PullRequest]:
        return [
            pr for pr in self.open_prs if pr.is_stale or pr.review_status == "changes_requested"
        ]


class GitTracker:
    """
    Tracks Git and GitHub state for Cortex intelligence.

    Usage:
        tracker = GitTracker("~/projects")
        state = tracker.get_state()
        summary = tracker.get_summary()
    """

    def __init__(self, repo_path: str = None):
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self._state: Optional[GitState] = None
        self._cache_ttl = timedelta(minutes=5)
        self._last_fetch: Optional[datetime] = None

    def _run_git(self, args: List[str], cwd: Path = None) -> Optional[str]:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd or self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.debug(f"Git command failed: {e}")
            return None

    def _run_gh(self, args: List[str]) -> Optional[str]:
        """Run a GitHub CLI command and return output."""
        try:
            result = subprocess.run(
                ["gh"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.debug(f"GitHub CLI command failed: {e}")
            return None

    def _get_branches(self) -> List[Branch]:
        """Get all local branches with metadata."""
        branches = []

        # Get current branch
        current = self._run_git(["branch", "--show-current"]) or "main"

        # Get all branches with last commit info
        branch_output = self._run_git(
            [
                "for-each-ref",
                "--sort=-committerdate",
                "--format=%(refname:short)|%(committerdate:iso)|%(subject)",
                "refs/heads/",
            ]
        )

        if not branch_output:
            return branches

        for line in branch_output.split("\n"):
            if not line:
                continue

            parts = line.split("|", 2)
            if len(parts) < 3:
                continue

            name, date_str, msg = parts

            # Parse commit date
            try:
                commit_date = datetime.fromisoformat(date_str.replace(" ", "T").split("+")[0])
                age_days = (datetime.now() - commit_date).days
            except (ValueError, TypeError):
                commit_date = None
                age_days = 0

            # Get ahead/behind main
            ahead, behind = 0, 0
            if name != "main":
                counts = self._run_git(["rev-list", "--left-right", "--count", f"main...{name}"])
                if counts:
                    parts = counts.split()
                    if len(parts) == 2:
                        behind, ahead = int(parts[0]), int(parts[1])

            # Extract project from branch name
            project = None
            if "/" in name:
                parts = name.split("/")
                if len(parts) >= 2:
                    project = parts[1]

            branches.append(
                Branch(
                    name=name,
                    is_current=(name == current),
                    last_commit_date=commit_date,
                    last_commit_msg=msg[:100],
                    ahead_of_main=ahead,
                    behind_main=behind,
                    age_days=age_days,
                    project=project,
                )
            )

        return branches

    def _get_open_prs(self) -> List[PullRequest]:
        """Get open PRs from GitHub."""
        prs = []

        output = self._run_gh(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,headRefName,state,createdAt,updatedAt,url,additions,deletions,changedFiles,isDraft,reviewDecision",
            ]
        )

        if not output:
            return prs

        try:
            pr_data = json.loads(output)
            for pr in pr_data:
                prs.append(
                    PullRequest(
                        number=pr["number"],
                        title=pr["title"],
                        branch=pr["headRefName"],
                        state=pr["state"].lower(),
                        created_at=datetime.fromisoformat(pr["createdAt"].replace("Z", "")),
                        updated_at=datetime.fromisoformat(pr["updatedAt"].replace("Z", "")),
                        url=pr["url"],
                        additions=pr.get("additions", 0),
                        deletions=pr.get("deletions", 0),
                        changed_files=pr.get("changedFiles", 0),
                        is_draft=pr.get("isDraft", False),
                        review_status=pr.get("reviewDecision", "").lower().replace("_", " "),
                    )
                )
        except json.JSONDecodeError:
            logger.warning("Failed to parse PR data")

        return prs

    def _get_working_tree_status(self) -> tuple[int, int]:
        """Get count of uncommitted changes and untracked files."""
        status = self._run_git(["status", "--porcelain"])
        if not status:
            return 0, 0

        uncommitted = 0
        untracked = 0

        for line in status.split("\n"):
            if line.startswith("??"):
                untracked += 1
            elif line.strip():
                uncommitted += 1

        return uncommitted, untracked

    def get_state(self, force_refresh: bool = False) -> GitState:
        """Get current Git/GitHub state (cached)."""
        now = datetime.now()

        if (
            not force_refresh
            and self._state
            and self._last_fetch
            and (now - self._last_fetch) < self._cache_ttl
        ):
            return self._state

        current_branch = self._run_git(["branch", "--show-current"]) or "main"
        branches = self._get_branches()
        open_prs = self._get_open_prs()
        uncommitted, untracked = self._get_working_tree_status()

        self._state = GitState(
            repo_path=self.repo_path,
            current_branch=current_branch,
            branches=branches,
            open_prs=open_prs,
            uncommitted_changes=uncommitted,
            untracked_files=untracked,
            last_updated=now,
        )
        self._last_fetch = now

        return self._state

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary suitable for briefings and context injection."""
        state = self.get_state()

        return {
            "current_branch": state.current_branch,
            "on_feature_branch": state.current_branch != "main",
            "uncommitted_changes": state.uncommitted_changes,
            "untracked_files": state.untracked_files,
            "active_branches": len(state.active_feature_branches),
            "stale_branches": len(state.stale_branches),
            "stale_branch_names": [b.name for b in state.stale_branches],
            "open_prs": len(state.open_prs),
            "prs_needing_attention": len(state.prs_needing_attention),
            "pr_details": [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "branch": pr.branch,
                    "age_days": pr.age_days,
                    "url": pr.url,
                    "status": pr.review_status or "pending review",
                }
                for pr in state.open_prs
            ],
        }

    def get_recommendations(self) -> List[Dict[str, str]]:
        """Generate actionable recommendations based on Git state."""
        state = self.get_state()
        recommendations = []

        # Stale branches
        for branch in state.stale_branches[:3]:
            recommendations.append(
                {
                    "type": "cleanup",
                    "priority": "low",
                    "message": f"Branch '{branch.name}' is {branch.age_days} days old - review or delete",
                    "action": f"git branch -d {branch.name}",
                }
            )

        # Stale PRs
        for pr in state.prs_needing_attention[:3]:
            if pr.review_status == "changes requested":
                recommendations.append(
                    {
                        "type": "pr_action",
                        "priority": "high",
                        "message": f"PR #{pr.number} has requested changes - address feedback",
                        "action": pr.url,
                    }
                )
            elif pr.is_stale:
                recommendations.append(
                    {
                        "type": "pr_action",
                        "priority": "medium",
                        "message": f"PR #{pr.number} '{pr.title}' is {pr.age_days} days old - merge or close",
                        "action": pr.url,
                    }
                )

        # Uncommitted work
        if state.uncommitted_changes > 10:
            recommendations.append(
                {
                    "type": "commit",
                    "priority": "medium",
                    "message": f"You have {state.uncommitted_changes} uncommitted changes - consider committing",
                    "action": "git status",
                }
            )

        # Behind main
        current_branch = next((b for b in state.branches if b.is_current), None)
        if current_branch and current_branch.behind_main > 5:
            recommendations.append(
                {
                    "type": "sync",
                    "priority": "medium",
                    "message": f"Current branch is {current_branch.behind_main} commits behind main",
                    "action": "git pull origin main",
                }
            )

        return recommendations

    def format_for_briefing(self) -> str:
        """Format Git state for daily briefing."""
        state = self.get_state()
        self.get_summary()
        recommendations = self.get_recommendations()

        lines = ["## Git & GitHub Status\n"]

        # Current state
        lines.append(f"**Current Branch**: `{state.current_branch}`")
        if state.uncommitted_changes or state.untracked_files:
            lines.append(
                f"**Working Tree**: {state.uncommitted_changes} modified, {state.untracked_files} untracked"
            )

        # Open PRs
        if state.open_prs:
            lines.append(f"\n### Open Pull Requests ({len(state.open_prs)})")
            for pr in state.open_prs:
                status = f"[{pr.review_status}]" if pr.review_status else ""
                stale = " (stale)" if pr.is_stale else ""
                lines.append(f"- PR #{pr.number}: {pr.title} {status}{stale}")
                lines.append(f"  {pr.url}")

        # Active branches
        if state.active_feature_branches:
            lines.append(f"\n### Active Branches ({len(state.active_feature_branches)})")
            for branch in state.active_feature_branches[:5]:
                lines.append(
                    f"- `{branch.name}` ({branch.age_days}d old, +{branch.ahead_of_main} commits)"
                )

        # Stale branches warning
        if state.stale_branches:
            lines.append(f"\n### Stale Branches ({len(state.stale_branches)})")
            for branch in state.stale_branches[:3]:
                lines.append(f"- `{branch.name}` - {branch.age_days} days inactive")

        # Recommendations
        if recommendations:
            lines.append("\n### Recommendations")
            for rec in recommendations[:5]:
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    rec["priority"], "⚪"
                )
                lines.append(f"{priority_icon} {rec['message']}")

        return "\n".join(lines)

    def format_for_session_context_fast(self) -> str:
        """
        FAST version for session start - skips expensive operations.

        Uses only direct git commands, no branch scanning or PR fetching.
        Expected time: <0.2s vs 17s for full version.
        """
        lines = []

        # Current branch (fast - single git command)
        current_branch = self._run_git(["branch", "--show-current"]) or "main"
        lines.append(f"Branch: `{current_branch}`")

        # Uncommitted changes count (fast - single git command)
        uncommitted, _ = self._get_working_tree_status()
        if uncommitted:
            lines.append(f"Uncommitted: {uncommitted} files")

        return "\n".join(lines) if lines else "Git: Clean state on main"

    def format_for_session_context(self) -> str:
        """Format Git state for session start context (concise)."""
        state = self.get_state()

        lines = []

        # Branch info
        if state.current_branch != "main":
            current = next((b for b in state.branches if b.is_current), None)
            if current:
                lines.append(
                    f"Branch: `{current.name}` (+{current.ahead_of_main}/-{current.behind_main} vs main)"
                )
        else:
            lines.append("Branch: `main`")

        # Working tree
        if state.uncommitted_changes:
            lines.append(f"Uncommitted: {state.uncommitted_changes} files")

        # PRs
        if state.open_prs:
            lines.append(f"Open PRs: {len(state.open_prs)}")
            for pr in state.prs_needing_attention[:2]:
                lines.append(f"  - #{pr.number} needs attention")

        # Quick recommendations
        recommendations = self.get_recommendations()
        high_priority = [r for r in recommendations if r["priority"] == "high"]
        if high_priority:
            lines.append(f"Action needed: {high_priority[0]['message']}")

        return "\n".join(lines) if lines else "Git: Clean state on main"


# Convenience function for CLI/hooks
def get_git_summary(repo_path: str = None) -> Dict[str, Any]:
    """Get Git summary for a repository."""
    tracker = GitTracker(repo_path)
    return tracker.get_summary()


def get_git_context(repo_path: str = None) -> str:
    """Get formatted Git context for session injection."""
    tracker = GitTracker(repo_path)
    return tracker.format_for_session_context()


def get_git_context_fast(repo_path: str = None) -> str:
    """Get formatted Git context for session injection (FAST - <0.2s)."""
    tracker = GitTracker(repo_path)
    return tracker.format_for_session_context_fast()


def get_git_briefing(repo_path: str = None) -> str:
    """Get formatted Git section for daily briefing."""
    tracker = GitTracker(repo_path)
    return tracker.format_for_briefing()
