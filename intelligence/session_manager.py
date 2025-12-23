"""Session Manager - Creates and manages session context from git history."""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SessionContext


class SessionManager:
    """Manages session context derived from git history and project state."""

    def __init__(self, root_dir: Path = Path("/Users/jesse.kemp/Dev")):
        self.root_dir = Path(root_dir)
        self.cache_dir = Path.home() / ".claude" / "session"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "context.json"

    def load_session_context(self, max_age_hours: int = 1) -> Optional[SessionContext]:
        """
        Load session context from cache or regenerate if stale.

        Args:
            max_age_hours: Regenerate if cache older than this

        Returns:
            SessionContext or None if unavailable
        """
        # Try to load from cache
        if self.cache_file.exists():
            cache_age = datetime.now().timestamp() - self.cache_file.stat().st_mtime
            if cache_age < max_age_hours * 3600:
                try:
                    data = json.loads(self.cache_file.read_text())
                    return SessionContext(**data)
                except Exception:
                    pass  # Fall through to regenerate

        # Regenerate from git history
        return self._generate_session_context()

    def _generate_session_context(self) -> Optional[SessionContext]:
        """Generate session context from git history."""
        try:
            # Detect current project
            cwd = Path.cwd()
            project = self._detect_project(cwd)

            if not project:
                return None

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = cwd

            # Get recent commits
            recent_work = self._get_recent_commits(project_path, limit=5)

            # Extract goals and focus from commits and files
            active_goals = self._extract_goals(project_path)
            current_focus = self._determine_focus(recent_work, project_path)

            context = SessionContext(
                project=project,
                working_directory=str(cwd),
                recent_work=recent_work,
                active_goals=active_goals,
                current_focus=current_focus,
                last_updated=datetime.now().isoformat()
            )

            # Cache for next time
            self.cache_file.write_text(json.dumps({
                "project": context.project,
                "working_directory": context.working_directory,
                "recent_work": context.recent_work,
                "active_goals": context.active_goals,
                "current_focus": context.current_focus,
                "last_updated": context.last_updated
            }, indent=2))

            return context

        except Exception as e:
            print(f"Error generating session context: {e}")
            return None

    def _detect_project(self, cwd: Path) -> Optional[str]:
        """Detect project name from current directory."""
        # Check if we're in a known project directory
        if self.root_dir in cwd.parents or cwd == self.root_dir:
            # Find the immediate child of root_dir
            for parent in [cwd] + list(cwd.parents):
                if parent.parent == self.root_dir:
                    return parent.name

        # Fallback to directory name
        return cwd.name if cwd != Path.home() else None

    def _get_recent_commits(self, project_path: Path, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent git commits."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%h|%s|%ar|%an"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "summary": parts[1],
                        "time": parts[2],
                        "author": parts[3],
                        "commit": parts[1]  # Backward compat
                    })

            return commits

        except Exception:
            return []

    def _extract_goals(self, project_path: Path) -> List[str]:
        """Extract active goals from PLAN.md or TODO files."""
        goals = []

        # Check PLAN.md
        plan_file = project_path / "PLAN.md"
        if plan_file.exists():
            try:
                content = plan_file.read_text()
                # Look for goal-like patterns
                for line in content.split("\n"):
                    if any(marker in line.lower() for marker in ["goal:", "priority", "- [ ]", "TODO"]):
                        # Extract the goal text
                        goal = line.strip().lstrip("-*#").strip()
                        if goal and len(goal) < 100:
                            goals.append(goal)
                            if len(goals) >= 5:
                                break
            except Exception:
                pass

        # If no goals found, use generic project focus
        if not goals:
            goals = ["Continue development", "Address recent changes"]

        return goals[:5]

    def _determine_focus(self, recent_work: List[Dict[str, Any]], project_path: Path) -> str:
        """Determine current focus from recent commits and files."""
        if not recent_work:
            return "Starting new session"

        # Use most recent commit summary as focus
        latest = recent_work[0].get("summary", "")

        # Try to extract meaningful focus from commit message
        # Remove common prefixes
        for prefix in ["feat:", "fix:", "chore:", "docs:", "refactor:", "test:"]:
            if latest.lower().startswith(prefix):
                latest = latest[len(prefix):].strip()

        # Capitalize first letter
        if latest:
            latest = latest[0].upper() + latest[1:]

        return latest or "Recent development work"
