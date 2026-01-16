"""
File Selector for Smart Recommendations

Intelligently selects relevant files for different recommendation types
using heuristics based on coverage, git history, project structure, and patterns.
"""

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class FileInfo:
    """Information about a selected file with context."""

    path: str  # Relative file path
    reason: str  # Why this file was selected
    priority: int  # 1-10 score (10 = highest priority)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Clamp priority to valid range
        self.priority = max(1, min(10, self.priority))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "reason": self.reason,
            "priority": self.priority,
            "metadata": self.metadata,
        }


class FileSelector:
    """
    Selects relevant files for recommendations using multiple heuristics.

    Integrates with:
    - Layer 1: Project profiler for coverage and structure data
    - Layer 2: Pattern memory for similar work files
    - Git: For history and churn analysis
    """

    # Critical file patterns (high importance by default)
    CRITICAL_PATTERNS = [
        "main.py",
        "app.py",
        "config.py",
        "settings.py",
        "__init__.py",
        "cli.py",
        "api.py",
        "models.py",
        "views.py",
        "routes.py",
        "handlers.py",
        "core.py",
    ]

    # Files to always exclude
    EXCLUDE_PATTERNS = [
        "__pycache__/*",
        "*.pyc",
        ".git/*",
        "node_modules/*",
        "venv/*",
        ".venv/*",
        "env/*",
        ".env",
        "*.egg-info/*",
        "dist/*",
        "build/*",
        ".pytest_cache/*",
        ".mypy_cache/*",
        "*.min.js",
        "*.min.css",
        "coverage/*",
        "htmlcov/*",
    ]

    # Minimum lines for a file to be considered substantial
    MIN_SUBSTANTIAL_LINES = 50

    def __init__(self, project_path: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize file selector.

        Args:
            project_path: Path to the project root
            context: Optional context dict with coverage, patterns, etc.
        """
        self.project_path = Path(project_path).resolve()
        self.context = context or {}
        self._file_cache: Dict[str, Dict[str, Any]] = {}
        self._git_available = self._check_git_available()

    def _check_git_available(self) -> bool:
        """Check if git is available and project is a git repo."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _is_excluded(self, path: str) -> bool:
        """Check if a file should be excluded."""
        for pattern in self.EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _get_file_lines(self, file_path: Path) -> int:
        """Get line count for a file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except (IOError, OSError):
            return 0

    def _get_file_info(self, rel_path: str) -> Dict[str, Any]:
        """Get cached file information."""
        if rel_path in self._file_cache:
            return self._file_cache[rel_path]

        full_path = self.project_path / rel_path
        info = {
            "lines": self._get_file_lines(full_path),
            "exists": full_path.exists(),
            "is_critical": any(rel_path.endswith(p) for p in self.CRITICAL_PATTERNS),
            "last_modified": None,
        }

        if info["exists"]:
            try:
                stat = full_path.stat()
                info["last_modified"] = datetime.fromtimestamp(stat.st_mtime)
            except OSError:
                pass

        self._file_cache[rel_path] = info
        return info

    def _get_coverage_data(self) -> Dict[str, float]:
        """
        Get coverage data from context or Layer 1.

        Returns dict mapping file paths to coverage percentages.
        """
        # Try to get from context first
        if "coverage" in self.context:
            coverage = self.context["coverage"]
            if isinstance(coverage, dict) and "files" in coverage:
                return coverage["files"]
            elif isinstance(coverage, dict):
                return coverage

        # Try to load from Layer 1 project profiler
        try:
            from intelligence.analysis.project_profiler import ProjectProfiler

            profiler = ProjectProfiler(str(self.project_path))
            profile = profiler.analyze()
            if profile and "coverage" in profile:
                return profile["coverage"].get("files", {})
        except ImportError:
            pass

        return {}

    def _get_git_files_modified_since(self, days: int) -> List[Dict[str, Any]]:
        """Get files modified in git within the last N days."""
        if not self._git_available:
            return []

        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--since={days}.days",
                    "--name-only",
                    "--pretty=format:",
                    "--diff-filter=ACMR",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            # Count occurrences (more changes = higher churn)
            file_counts: Dict[str, int] = {}
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and not self._is_excluded(line):
                    file_counts[line] = file_counts.get(line, 0) + 1

            return [
                {"path": path, "changes": count}
                for path, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
            ]
        except subprocess.SubprocessError:
            return []

    def _get_high_churn_files(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get files with highest churn (most commits) in last 90 days."""
        return self._get_git_files_modified_since(90)[:limit]

    def _get_pattern_files(self, goal: str) -> List[str]:
        """
        Get relevant files from Layer 2 pattern memory.

        Searches for patterns similar to the goal and returns associated files.
        """
        try:
            from intelligence.memory.pattern_memory import PatternMemory

            memory = PatternMemory(str(self.project_path))

            # Search for similar patterns
            patterns = memory.search(goal, limit=5)

            files = []
            for pattern in patterns:
                if "files" in pattern:
                    files.extend(pattern["files"])
                if "context" in pattern and "files" in pattern["context"]:
                    files.extend(pattern["context"]["files"])

            return list(set(files))  # Deduplicate
        except ImportError:
            return []

    def _score_file_for_coverage(self, path: str, coverage: float, lines: int) -> int:
        """
        Score a file for coverage improvement priority.

        Higher score = higher priority for coverage work.
        """
        score = 5  # Base score

        # Zero coverage is highest priority
        if coverage == 0:
            score += 3
        elif coverage < 30:
            score += 2
        elif coverage < 50:
            score += 1

        # Larger files are more impactful
        if lines > 500:
            score += 2
        elif lines > 200:
            score += 1

        # Critical files get bonus
        if any(path.endswith(p) for p in self.CRITICAL_PATTERNS):
            score += 1

        return min(10, score)

    def select_for_coverage_improvement(self, limit: int = 5) -> List[FileInfo]:
        """
        Select files that need coverage improvement.

        Prioritizes:
        1. Files with 0% coverage and >100 lines
        2. Files with <30% coverage
        3. Critical files with low coverage

        Args:
            limit: Maximum number of files to return

        Returns:
            List of FileInfo objects sorted by priority
        """
        coverage_data = self._get_coverage_data()
        candidates: List[FileInfo] = []

        for path, coverage in coverage_data.items():
            if self._is_excluded(path):
                continue

            file_info = self._get_file_info(path)
            lines = file_info.get("lines", 0)

            # Skip tiny files
            if lines < self.MIN_SUBSTANTIAL_LINES:
                continue

            # Calculate priority score
            priority = self._score_file_for_coverage(path, coverage, lines)

            # Determine reason
            if coverage == 0:
                reason = f"No test coverage ({lines} lines)"
            elif coverage < 30:
                reason = f"Very low coverage ({coverage:.0f}%, {lines} lines)"
            elif coverage < 50:
                reason = f"Below target coverage ({coverage:.0f}%)"
            else:
                continue  # Skip files with decent coverage

            candidates.append(
                FileInfo(
                    path=path,
                    reason=reason,
                    priority=priority,
                    metadata={
                        "coverage": coverage,
                        "lines": lines,
                        "is_critical": file_info.get("is_critical", False),
                    },
                )
            )

        # Sort by priority (descending) and return top N
        candidates.sort(key=lambda x: (-x.priority, x.path))
        return candidates[:limit]

    def select_for_goal_work(self, goal: str, limit: int = 3) -> List[FileInfo]:
        """
        Select files relevant to a specific goal.

        Uses:
        1. Pattern memory for similar past work
        2. Keyword matching in file names
        3. Recently modified files in relevant areas

        Args:
            goal: The goal description
            limit: Maximum number of files to return

        Returns:
            List of FileInfo objects sorted by relevance
        """
        candidates: List[FileInfo] = []
        seen_paths: Set[str] = set()

        # Extract keywords from goal
        keywords = set(re.findall(r"\b\w{3,}\b", goal.lower()))
        keywords -= {"the", "and", "for", "with", "that", "this", "from", "have"}

        # 1. Get files from pattern memory
        pattern_files = self._get_pattern_files(goal)
        for path in pattern_files:
            if path in seen_paths or self._is_excluded(path):
                continue

            full_path = self.project_path / path
            if not full_path.exists():
                continue

            seen_paths.add(path)
            file_info = self._get_file_info(path)

            candidates.append(
                FileInfo(
                    path=path,
                    reason="Similar work done previously",
                    priority=9,
                    metadata={
                        "source": "pattern_memory",
                        "lines": file_info.get("lines", 0),
                    },
                )
            )

        # 2. Find files matching keywords
        for root, dirs, files in os.walk(self.project_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not self._is_excluded(d + "/")]

            for file in files:
                if not file.endswith(".py"):
                    continue

                rel_path = os.path.relpath(os.path.join(root, file), self.project_path)
                if rel_path in seen_paths or self._is_excluded(rel_path):
                    continue

                # Check for keyword matches
                file_lower = file.lower()
                path_lower = rel_path.lower()
                matches = sum(1 for kw in keywords if kw in path_lower)

                if matches > 0:
                    seen_paths.add(rel_path)
                    file_info = self._get_file_info(rel_path)

                    candidates.append(
                        FileInfo(
                            path=rel_path,
                            reason=f"Filename matches goal keywords",
                            priority=6 + min(3, matches),
                            metadata={
                                "source": "keyword_match",
                                "matches": matches,
                                "lines": file_info.get("lines", 0),
                            },
                        )
                    )

        # 3. Add recently modified files if we don't have enough
        if len(candidates) < limit:
            recent = self._get_git_files_modified_since(14)
            for item in recent:
                path = item["path"]
                if path in seen_paths or self._is_excluded(path):
                    continue
                if not path.endswith(".py"):
                    continue

                full_path = self.project_path / path
                if not full_path.exists():
                    continue

                seen_paths.add(path)
                file_info = self._get_file_info(path)

                candidates.append(
                    FileInfo(
                        path=path,
                        reason="Recently modified (active development)",
                        priority=5,
                        metadata={
                            "source": "recent_activity",
                            "changes": item["changes"],
                            "lines": file_info.get("lines", 0),
                        },
                    )
                )

                if len(candidates) >= limit * 2:
                    break

        # Sort by priority and return top N
        candidates.sort(key=lambda x: (-x.priority, x.path))
        return candidates[:limit]

    def select_recently_modified(self, days: int = 7, limit: int = 3) -> List[FileInfo]:
        """
        Select recently modified files.

        Args:
            days: Look back this many days
            limit: Maximum number of files to return

        Returns:
            List of FileInfo objects sorted by recency/activity
        """
        recent_files = self._get_git_files_modified_since(days)
        candidates: List[FileInfo] = []

        for item in recent_files:
            path = item["path"]
            if self._is_excluded(path):
                continue
            if not path.endswith(".py"):
                continue

            full_path = self.project_path / path
            if not full_path.exists():
                continue

            file_info = self._get_file_info(path)
            changes = item["changes"]

            # Higher priority for more changes
            priority = min(10, 5 + changes)

            reason = f"Modified {changes} time(s) in last {days} days"
            if file_info.get("is_critical"):
                reason += " (critical file)"
                priority = min(10, priority + 1)

            candidates.append(
                FileInfo(
                    path=path,
                    reason=reason,
                    priority=priority,
                    metadata={
                        "changes": changes,
                        "lines": file_info.get("lines", 0),
                        "is_critical": file_info.get("is_critical", False),
                    },
                )
            )

            if len(candidates) >= limit:
                break

        return candidates

    def select_critical_files(self, limit: int = 5) -> List[FileInfo]:
        """
        Select critical/important files in the project.

        Prioritizes:
        1. Entry points (main.py, app.py, cli.py)
        2. Configuration files
        3. High-churn files (frequently modified)

        Args:
            limit: Maximum number of files to return

        Returns:
            List of FileInfo objects sorted by criticality
        """
        candidates: List[FileInfo] = []
        seen_paths: Set[str] = set()

        # 1. Find critical pattern files
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if not self._is_excluded(d + "/")]

            for file in files:
                if not file.endswith(".py"):
                    continue

                rel_path = os.path.relpath(os.path.join(root, file), self.project_path)
                if self._is_excluded(rel_path):
                    continue

                # Check if it's a critical file
                is_critical = any(file == p for p in self.CRITICAL_PATTERNS)
                if not is_critical:
                    continue

                seen_paths.add(rel_path)
                file_info = self._get_file_info(rel_path)

                # Determine priority based on file type
                if file in ["main.py", "app.py", "cli.py"]:
                    priority = 10
                    reason = "Application entry point"
                elif file in ["config.py", "settings.py"]:
                    priority = 9
                    reason = "Configuration file"
                elif file == "__init__.py":
                    priority = 6
                    reason = "Package initialization"
                else:
                    priority = 8
                    reason = "Core module"

                candidates.append(
                    FileInfo(
                        path=rel_path,
                        reason=reason,
                        priority=priority,
                        metadata={
                            "lines": file_info.get("lines", 0),
                            "type": "critical_pattern",
                        },
                    )
                )

        # 2. Add high-churn files
        churn_files = self._get_high_churn_files(limit=10)
        for item in churn_files:
            path = item["path"]
            if path in seen_paths or self._is_excluded(path):
                continue
            if not path.endswith(".py"):
                continue

            full_path = self.project_path / path
            if not full_path.exists():
                continue

            seen_paths.add(path)
            file_info = self._get_file_info(path)
            changes = item["changes"]

            # High churn indicates importance
            priority = min(9, 5 + (changes // 3))

            candidates.append(
                FileInfo(
                    path=path,
                    reason=f"High activity ({changes} changes in 90 days)",
                    priority=priority,
                    metadata={
                        "lines": file_info.get("lines", 0),
                        "changes": changes,
                        "type": "high_churn",
                    },
                )
            )

        # Sort by priority and return top N
        candidates.sort(key=lambda x: (-x.priority, x.path))
        return candidates[:limit]

    def select_for_recommendation_type(
        self, rec_type: str, context: Optional[Dict[str, Any]] = None, limit: int = 5
    ) -> List[FileInfo]:
        """
        Select files based on recommendation type.

        This is a convenience method that routes to the appropriate selector.

        Args:
            rec_type: Type of recommendation (coverage, goal, health, etc.)
            context: Additional context (e.g., goal text)
            limit: Maximum number of files

        Returns:
            List of FileInfo objects
        """
        context = context or {}

        if rec_type == "coverage":
            return self.select_for_coverage_improvement(limit)
        elif rec_type == "goal":
            goal = context.get("goal", context.get("text", ""))
            return self.select_for_goal_work(goal, limit)
        elif rec_type == "health":
            # For health, combine critical and recently modified
            critical = self.select_critical_files(limit=3)
            recent = self.select_recently_modified(days=7, limit=2)
            return (critical + recent)[:limit]
        elif rec_type == "alert":
            # For alerts, focus on critical files
            return self.select_critical_files(limit)
        else:
            # Default: mix of critical and recent
            critical = self.select_critical_files(limit=3)
            recent = self.select_recently_modified(days=14, limit=2)
            return (critical + recent)[:limit]
