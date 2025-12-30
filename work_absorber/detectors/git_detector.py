"""
Git signal detector - Extract work signals from git commits.

This is the primary source of work signals as commits represent
actual completed work with timestamps, authors, and file changes.
"""

import subprocess
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import SignalDetector
from ..models import WorkSignal, WorkSignalType

logger = logging.getLogger(__name__)


class GitSignalDetector(SignalDetector):
    """
    Detect work signals from git commits.

    Extracts commits and converts them to WorkSignal objects with:
    - Title from commit message first line
    - Description from commit body
    - Files changed
    - Author information
    - Scope detection (feat, fix, refactor, etc.)
    """

    @property
    def name(self) -> str:
        return "git"

    def supports_incremental(self) -> bool:
        return True  # Can use commit hash as checkpoint

    def detect(
        self,
        project: str,
        project_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[WorkSignal]:
        """
        Detect work signals from git commits.

        Args:
            project: Project name
            project_path: Path to git repository
            since: Only commits after this time
            until: Only commits before this time

        Returns:
            List of WorkSignal objects, one per commit
        """
        if not self._is_git_repo(project_path):
            logger.warning(f"Not a git repository: {project_path}")
            return []

        commits = self._get_commits(project_path, since, until)
        signals = []

        for commit in commits:
            signal = self._commit_to_signal(project, project_path, commit)
            if signal:
                signals.append(signal)

        logger.info(f"Detected {len(signals)} git signals for {project}")
        return signals

    def _is_git_repo(self, path: Path) -> bool:
        """Check if path is inside a git repository."""
        # Check for .git directory or file (submodule)
        if (path / ".git").exists():
            return True

        # Check if inside a git working tree (for monorepo subdirectories)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
            return False

    def _get_git_root(self, path: Path) -> Optional[Path]:
        """Get the root directory of the git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
        return None

    def _get_commits(
        self,
        repo_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get commits from repository."""
        cmd = [
            "git", "log",
            "--pretty=format:%H|%an|%ae|%at|%s|%b<<<END>>>",
            "--numstat",
        ]

        if since:
            cmd.append(f"--since={since.strftime('%Y-%m-%d %H:%M:%S')}")
        if until:
            cmd.append(f"--until={until.strftime('%Y-%m-%d %H:%M:%S')}")

        # For monorepo subdirectories, filter commits to those touching this path
        # Check if this is a subdirectory by looking for .git in parent
        git_root = self._get_git_root(repo_path)
        if git_root and git_root != repo_path:
            # This is a subdirectory - add path filter
            rel_path = repo_path.relative_to(git_root)
            cmd.append("--")
            cmd.append(str(rel_path))

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(f"Git log failed for {repo_path}: {result.stderr}")
                return []

            return self._parse_git_log(result.stdout)

        except subprocess.TimeoutExpired:
            logger.warning(f"Git log timed out for {repo_path}")
            return []
        except Exception as e:
            logger.error(f"Error getting commits from {repo_path}: {e}")
            return []

    def _parse_git_log(self, log_output: str) -> List[Dict[str, Any]]:
        """Parse git log output into structured commit data."""
        commits = []

        # Split by our custom delimiter
        entries = log_output.split("<<<END>>>")

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            lines = entry.split("\n")
            if not lines:
                continue

            # First line is the commit header
            header = lines[0]
            if "|" not in header:
                continue

            parts = header.split("|", 5)
            if len(parts) < 5:
                continue

            commit_hash = parts[0]
            author = parts[1]
            email = parts[2]
            timestamp = parts[3]
            subject = parts[4]
            body = parts[5] if len(parts) > 5 else ""

            # Parse file stats (numstat format: additions  deletions  file)
            files = []
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                # numstat format: "10\t5\tpath/to/file"
                parts = line.split("\t")
                if len(parts) >= 3:
                    files.append(parts[2])

            try:
                commit_time = datetime.fromtimestamp(int(timestamp))
            except (ValueError, OSError):
                commit_time = datetime.now()

            commits.append({
                "hash": commit_hash,
                "author": author,
                "email": email,
                "timestamp": commit_time,
                "subject": subject,
                "body": body.strip(),
                "files": files,
            })

        return commits

    def _commit_to_signal(
        self,
        project: str,
        project_path: Path,
        commit: Dict[str, Any],
    ) -> Optional[WorkSignal]:
        """Convert a commit to a WorkSignal."""
        try:
            # Generate deterministic ID
            signal_id = WorkSignal.generate_id(
                WorkSignalType.GIT_COMMIT,
                commit["hash"],
                commit["timestamp"],
            )

            # Parse scope from conventional commit format
            scope = self._parse_scope(commit["subject"])

            # Build description from body if present
            description = commit["body"] if commit["body"] else ""

            # Extract tags from commit message
            tags = self._extract_tags(commit["subject"], commit["body"])

            return WorkSignal(
                id=signal_id,
                signal_type=WorkSignalType.GIT_COMMIT,
                source_path=str(project_path),
                project=project,
                timestamp=commit["timestamp"],
                title=commit["subject"],
                description=description,
                commit_hash=commit["hash"],
                author=commit["author"],
                files_changed=commit["files"],
                scope=scope,
                metadata={
                    "email": commit["email"],
                    "short_hash": commit["hash"][:7],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to convert commit {commit.get('hash', 'unknown')}: {e}")
            return None

    def _parse_scope(self, subject: str) -> Optional[str]:
        """
        Parse scope from conventional commit format.

        Examples:
            "feat(auth): add login" -> "feature"
            "fix: resolve crash" -> "bugfix"
            "refactor(api): clean up" -> "refactor"
        """
        # Conventional commit patterns
        patterns = {
            r"^feat(\(.*?\))?:": "feature",
            r"^fix(\(.*?\))?:": "bugfix",
            r"^refactor(\(.*?\))?:": "refactor",
            r"^docs(\(.*?\))?:": "docs",
            r"^test(\(.*?\))?:": "test",
            r"^chore(\(.*?\))?:": "chore",
            r"^style(\(.*?\))?:": "style",
            r"^perf(\(.*?\))?:": "performance",
            r"^ci(\(.*?\))?:": "ci",
            r"^build(\(.*?\))?:": "build",
        }

        subject_lower = subject.lower()
        for pattern, scope in patterns.items():
            if re.match(pattern, subject_lower):
                return scope

        # Fallback: try to infer from keywords
        if any(word in subject_lower for word in ["add", "implement", "create", "new"]):
            return "feature"
        if any(word in subject_lower for word in ["fix", "bug", "patch", "resolve"]):
            return "bugfix"
        if any(word in subject_lower for word in ["refactor", "clean", "reorganize"]):
            return "refactor"
        if any(word in subject_lower for word in ["update", "upgrade", "bump"]):
            return "update"

        return None

    def _extract_tags(self, subject: str, body: str) -> List[str]:
        """Extract tags/keywords from commit message."""
        tags = []
        text = f"{subject} {body}".lower()

        # Common project areas
        areas = [
            "api", "cli", "ui", "database", "auth", "config",
            "test", "docs", "build", "deploy", "security",
        ]
        for area in areas:
            if area in text:
                tags.append(area)

        # Scope from conventional commits
        scope_match = re.match(r"^\w+\((\w+)\):", subject.lower())
        if scope_match:
            tags.append(scope_match.group(1))

        return tags[:5]  # Limit to 5 tags

    def get_latest_commit_hash(self, project_path: Path) -> Optional[str]:
        """Get the latest commit hash for checkpoint."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def detect_since_hash(
        self,
        project: str,
        project_path: Path,
        since_hash: str,
    ) -> List[WorkSignal]:
        """
        Detect commits since a specific commit hash.

        This is more efficient than time-based detection for incremental sync.
        """
        if not self._is_git_repo(project_path):
            return []

        try:
            cmd = [
                "git", "log",
                f"{since_hash}..HEAD",
                "--pretty=format:%H|%an|%ae|%at|%s|%b<<<END>>>",
                "--numstat",
            ]

            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Fallback to time-based if hash not found
                logger.warning(f"Commit {since_hash} not found, falling back to full scan")
                return self.detect(project, project_path)

            commits = self._parse_git_log(result.stdout)
            signals = []

            for commit in commits:
                signal = self._commit_to_signal(project, project_path, commit)
                if signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Error in incremental detection: {e}")
            return self.detect(project, project_path)
