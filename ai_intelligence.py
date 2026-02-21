import os
#!/usr/bin/env python3
"""
AI Intelligence - Project Scanner for Cortex

Scans git repositories to detect project activity, status, and blockers.
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


@dataclass
class ProjectActivity:
    """Project activity data from git analysis."""

    name: str
    path: Path
    status: str  # "active", "recent", "dormant"
    commits_7d: int
    commits_30d: int
    files_changed_7d: int
    uncommitted_changes: int
    blockers: List[str] = field(default_factory=list)
    current_branch: str = ""
    last_commit_date: Optional[datetime] = None
    last_commit_msg: str = ""


class ProjectScanner:
    """Scan and analyze projects (git and non-git)."""

    def __init__(self, root_dir: str = os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))):
        self.root_dir = Path(root_dir)

    def find_git_repos(self) -> List[Path]:
        """Compatibility alias for find_projects."""
        return self.find_projects()

    def find_projects(self, max_depth: int = 3) -> List[Path]:
        """
        Find project directories recursively.

        Identifies projects by:
        1. .git directory
        2. Project markers (pyproject.toml, package.json, etc.)
        3. Known structure
        """
        projects = set()
        scan_queue = [(self.root_dir, 0)]

        # Common dirs to ignore during scan
        ignore_dirs = {
            "venv",
            "node_modules",
            "__pycache__",
            "archive",
            "dist",
            "build",
            "egg-info",
            ".git",
            ".idea",
            ".vscode",
            "databricks-docs-extractor",
            "logs",
            "reports",
            "scripts",  # Reduce noise
        }

        # Project markers
        markers = {
            "pyproject.toml",
            "package.json",
            "setup.py",
            "requirements.txt",
            "Makefile",
            "Gemfile",
            "composer.json",
            "cargo.toml",
            "go.mod",
            "mix.exs",
        }

        while scan_queue:
            current_path, depth = scan_queue.pop(0)

            if depth > max_depth:
                continue

            try:
                # Get all subdirectories
                subdirs = [
                    p
                    for p in current_path.iterdir()
                    if p.is_dir() and not p.name.startswith(".") and p.name not in ignore_dirs
                ]
            except PermissionError:
                continue

            for subdir in subdirs:
                is_project = False

                # Crytiera 1: Has .git
                if (subdir / ".git").exists():
                    is_project = True

                # Criteria 2: Has project markers
                elif any((subdir / m).exists() for m in markers):
                    # Filter out dirs that just have requirements.txt but are inside another project
                    # Simple heuristic: if parent is already a project, be stricter?
                    # For now, accept it to maximize awareness.
                    is_project = True

                if is_project:
                    projects.add(subdir)
                    # Don't recurse into projects (assume monorepo sub-projects are handled if we want flat list)
                    # But actually, lets verify if we should recurse.
                    # If we stop here, we can't find nested projects.
                    # Best approach: Add to projects, but ALSO recurse if depth allows,
                    # to catch monorepo structures like Vortex/backend
                    scan_queue.append((subdir, depth + 1))
                else:
                    scan_queue.append((subdir, depth + 1))

        return sorted(projects, key=lambda x: x.name)

    def get_git_output(self, repo_path: Path, command: List[str]) -> str:
        """Run git command and return output."""
        if not (repo_path / ".git").exists():
            return ""

        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return ""

    def analyze_project(self, repo_path: Path) -> ProjectActivity:
        """Analyze a single project."""
        project = ProjectActivity(
            name=repo_path.name,
            path=repo_path,
            status="unknown",
            commits_7d=0,
            commits_30d=0,
            files_changed_7d=0,
            uncommitted_changes=0,
        )

        is_git = (repo_path / ".git").exists()

        if is_git:
            # Get current branch
            project.current_branch = self.get_git_output(repo_path, ["branch", "--show-current"])

            # Get last commit info
            last_commit_info = self.get_git_output(repo_path, ["log", "-1", "--format=%ct|%s"])
            if last_commit_info:
                try:
                    timestamp, msg = last_commit_info.split("|", 1)
                    project.last_commit_date = datetime.fromtimestamp(int(timestamp))
                    project.last_commit_msg = msg
                except (ValueError, OSError):
                    pass

            # Count commits in last 7 and 30 days
            now = datetime.now()
            seven_days_ago = now - timedelta(days=7)
            thirty_days_ago = now - timedelta(days=30)

            commits_7d = self.get_git_output(
                repo_path, ["log", "--since", seven_days_ago.isoformat(), "--oneline"]
            )
            project.commits_7d = len(commits_7d.split("\n")) if commits_7d else 0

            commits_30d = self.get_git_output(
                repo_path, ["log", "--since", thirty_days_ago.isoformat(), "--oneline"]
            )
            project.commits_30d = len(commits_30d.split("\n")) if commits_30d else 0

            # Count files changed in last 7 days
            files_7d = self.get_git_output(
                repo_path, ["diff", "--name-only", "@{7.days.ago}..HEAD"]
            )
            project.files_changed_7d = len(files_7d.split("\n")) if files_7d else 0

            # Check for uncommitted changes
            status = self.get_git_output(repo_path, ["status", "--porcelain"])
            project.uncommitted_changes = len(status.split("\n")) if status else 0

        else:
            # Non-git fallback: Use file system stats through simple walk
            # Limit file count to avoid hanging on huge dirs
            mtime_7d = datetime.now().timestamp() - 7 * 24 * 3600
            mtime_30d = datetime.now().timestamp() - 30 * 24 * 3600

            recent_files = 0
            active_files = 0

            try:
                # Quick scan of top-level files + 1 level deep
                # using rglob takes too long on node_modules, so manual strict walk
                candidates = list(repo_path.glob("*")) + list(repo_path.glob("*/*"))
                for p in candidates:
                    if p.is_file() and not p.name.startswith("."):
                        try:
                            mtime = p.stat().st_mtime
                            if mtime > mtime_7d:
                                active_files += 1
                                if (
                                    not project.last_commit_date
                                    or datetime.fromtimestamp(mtime) > project.last_commit_date
                                ):
                                    project.last_commit_date = datetime.fromtimestamp(mtime)
                                    project.last_commit_msg = f"Modified {p.name}"
                            if mtime > mtime_30d:
                                recent_files += 1
                        except OSError:
                            pass
            except Exception:
                pass

            # Heuristic mapping
            project.commits_7d = (
                active_files  # Treat file mods as commits equivalent for checking activity
            )
            project.commits_30d = recent_files
            project.files_changed_7d = active_files
            project.current_branch = "no-git"

        # Determine status
        project.status = self._determine_status(project)

        # Detect blockers (simple heuristics)
        project.blockers = self._detect_blockers(repo_path, project)

        return project

    def _determine_status(self, project: ProjectActivity) -> str:
        """Determine project status based on activity."""
        # More aggressive active status: 1 commit/file mod in 7 days is usually "Active" enough for individuals
        if project.commits_7d >= 1:
            return "active"
        elif project.commits_30d > 0:
            return "recent"
        elif project.last_commit_date and (datetime.now() - project.last_commit_date).days < 90:
            return "dormant"
        else:
            return "inactive"

    def _detect_blockers(self, repo_path: Path, project: ProjectActivity) -> List[str]:
        """Detect potential blockers."""
        blockers = []

        is_git = (repo_path / ".git").exists()

        if is_git:
            # Check for TODO/FIXME in recent commits
            recent_todos = self.get_git_output(
                repo_path,
                [
                    "log",
                    "-10",
                    "--all",
                    "--grep=TODO",
                    "--grep=FIXME",
                    "--grep=BLOCKED",
                    "-i",
                ],
            )
            if recent_todos:
                blockers.append("TODO/FIXME comments in recent commits")

        # Check for .env.example without .env (common blocker)
        if (repo_path / ".env.example").exists() and not (repo_path / ".env").exists():
            blockers.append("Missing .env file")

        # Check for requirements.txt without venv
        if (repo_path / "requirements.txt").exists():
            # Check standard venv names
            has_venv = any((repo_path / d).exists() for d in ["venv", ".venv", "env", ".env"])
            if not has_venv:
                blockers.append("No virtualenv detected")

        return blockers
