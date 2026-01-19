# ~/Dev/cortex/session_manager.py

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List


class SessionManager:
    """
    Git-based automatic session context generation

    Generates context from:
    - Current git repository
    - Recent commits
    - Active branch
    - Git status (modified files)
    - Recent goals (from commit messages and specs)
    """

    def __init__(self, workspace_root: str = "~/Dev"):
        self.workspace_root = Path(workspace_root).expanduser()

    def get_context(self, format: str = "terminal") -> str:
        """
        Get current session context

        Args:
            format: 'terminal' (human-readable) or 'structured' (JSON)
        """
        context = self._build_context()

        if format == "structured":
            return json.dumps(context, indent=2)
        else:
            return self._format_terminal(context)

    def _build_context(self) -> Dict:
        """Build session context from git"""
        current_dir = Path.cwd()

        # Detect current project
        project_info = self._detect_project(current_dir)

        # Get git context if in repo
        git_context = {}
        if project_info["is_git_repo"]:
            git_context = {
                "branch": self._get_current_branch(),
                "recent_commits": self._get_recent_commits(limit=3),
                "status": self._get_git_status(),
                "recent_files": self._get_recently_modified_files(),
            }

        # Extract goals from recent work
        goals = self._extract_goals(git_context)

        # Build context (always fresh - no caching)
        context = {
            "timestamp": datetime.now().isoformat(),
            "current_directory": str(current_dir),
            "project": project_info,
            "git": git_context,
            "goals": goals,
            "focus": self._infer_focus(git_context),
        }

        return context

    def _detect_project(self, path: Path) -> Dict:
        """Detect project from path"""
        # Walk up until we find .git or hit workspace root
        current = path
        while current >= self.workspace_root:
            if (current / ".git").exists():
                return {"name": current.name, "path": str(current), "is_git_repo": True}
            current = current.parent

        return {"name": "unknown", "path": str(path), "is_git_repo": False}

    def _run_git(self, args: List[str], cwd: str = None) -> str:
        """Run git command and return output"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd or Path.cwd(),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_current_branch(self) -> str:
        """Get current git branch"""
        return self._run_git(["branch", "--show-current"])

    def _get_recent_commits(self, limit: int = 3) -> List[Dict]:
        """Get recent commits"""
        log_format = "--pretty=format:%h|%an|%ar|%s"
        output = self._run_git(["log", log_format, f"-{limit}"])

        commits = []
        for line in output.split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "time": parts[2],
                            "message": parts[3],
                        }
                    )
        return commits

    def _get_git_status(self) -> Dict:
        """Get git status summary"""
        status_output = self._run_git(["status", "--porcelain"])

        modified = []
        untracked = []

        for line in status_output.split("\n"):
            if line:
                status = line[:2]
                filepath = line[3:]

                if status == "??":
                    untracked.append(filepath)
                else:
                    modified.append(filepath)

        return {
            "modified": modified,
            "untracked": untracked,
            "is_clean": len(modified) == 0 and len(untracked) == 0,
        }

    def _get_recently_modified_files(self, days: int = 7) -> List[str]:
        """Get files modified in last N days"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        output = self._run_git(
            [
                "log",
                "--since",
                since,
                "--name-only",
                "--pretty=format:",
                "--diff-filter=AM",  # Added or Modified
            ]
        )

        files = set(line for line in output.split("\n") if line)
        return sorted(files)[:10]  # Top 10

    def _extract_goals(self, git_context: Dict) -> List[str]:
        """Extract goals from recent commit messages"""
        goals = []

        if "recent_commits" in git_context:
            for commit in git_context["recent_commits"]:
                msg = commit["message"]

                # Look for goal indicators
                if any(word in msg.lower() for word in ["add", "implement", "build", "create"]):
                    goals.append(f"Continue work on: {msg}")

        return goals[:3]  # Top 3 goals

    def _infer_focus(self, git_context: Dict) -> str:
        """Infer current focus from recent activity"""
        if not git_context:
            return "Unknown"

        # Recent commits indicate focus
        if git_context.get("recent_commits"):
            latest = git_context["recent_commits"][0]["message"]

            # Extract focus from commit message
            if "test" in latest.lower():
                return "Testing"
            elif "fix" in latest.lower() or "bug" in latest.lower():
                return "Bug fixing"
            elif "doc" in latest.lower():
                return "Documentation"
            elif "refactor" in latest.lower():
                return "Refactoring"
            else:
                return "Feature development"

        return "Unknown"

    def _format_terminal(self, context: Dict) -> str:
        """Format context for terminal display"""
        output = []

        output.append("=== Cortex Session Intelligence ===\n")

        # Project
        project = context["project"]
        output.append(f"Project: {project['name']}")
        output.append(f"Path: {project['path']}\n")

        # Git status
        if context["git"]:
            git = context["git"]
            output.append(f"Branch: {git.get('branch', 'unknown')}")
            output.append(f"Focus: {context.get('focus', 'unknown')}\n")

            # Recent work
            if git.get("recent_commits"):
                output.append("Recent commits:")
                for commit in git["recent_commits"][:3]:
                    output.append(f"  [{commit['hash']}] {commit['message']} ({commit['time']})")
                output.append("")

            # Status
            status = git.get("status", {})
            if not status.get("is_clean"):
                output.append(f"Modified files: {len(status.get('modified', []))}")
                output.append(f"Untracked files: {len(status.get('untracked', []))}\n")

        # Goals
        if context.get("goals"):
            output.append("Active goals:")
            for goal in context["goals"]:
                output.append(f"  • {goal}")
            output.append("")

        output.append("===================================")

        return "\n".join(output)

