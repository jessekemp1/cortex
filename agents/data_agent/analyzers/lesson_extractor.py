"""Lesson Extraction Tools - Extract lessons from git history."""

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LessonExtractor:
    """Extract lessons learned from git history and project analysis."""

    def __init__(self, root_dir: Path):
        """
        Initialize lesson extractor.

        Args:
            root_dir: Root directory containing projects
        """
        self.root_dir = Path(root_dir)

    def extract_lessons_from_project(
        self, project_path: Path, project_name: str, days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Extract lessons from a project's git history.

        Args:
            project_path: Path to project directory
            project_name: Name of the project
            days: Number of days to look back

        Returns:
            List of lesson dictionaries
        """
        lessons = []

        if not (project_path / ".git").exists():
            return lessons

        # Extract from commit messages
        lessons.extend(self._extract_from_commits(project_path, project_name, days))

        # Extract from common issues patterns
        lessons.extend(self._extract_from_issues(project_path, project_name))

        return lessons

    def _extract_from_commits(
        self, project_path: Path, project_name: str, days: int
    ) -> List[Dict[str, Any]]:
        """Extract lessons from commit messages."""
        lessons = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--since={cutoff_date.isoformat()}",
                    "--format=%H|%s|%b",
                    "--all",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return lessons

            commit_lines = result.stdout.strip().split("\n")
            for line in commit_lines:
                if not line:
                    continue

                parts = line.split("|", 2)
                if len(parts) < 2:
                    continue

                commit_hash = parts[0]
                subject = parts[1]
                body = parts[2] if len(parts) > 2 else ""

                # Look for lesson indicators
                lesson_keywords = [
                    "fix",
                    "bug",
                    "error",
                    "issue",
                    "problem",
                    "refactor",
                    "improve",
                    "optimize",
                    "prevent",
                ]

                if any(keyword in subject.lower() for keyword in lesson_keywords):
                    lesson_text = f"{subject}"
                    if body:
                        lesson_text += f": {body[:200]}"

                    lessons.append(
                        {
                            "lesson": lesson_text,
                            "project": project_name,
                            "category": self._categorize_lesson(subject, body),
                            "source": "git_commit",
                            "commit_hash": commit_hash[:8],
                            "first_seen": datetime.now().isoformat(),
                            "frequency": 1,
                        }
                    )

        except Exception as e:
            logger.warning(f"Failed to extract lessons from commits in {project_path}: {e}")

        return lessons

    def _extract_from_issues(self, project_path: Path, project_name: str) -> List[Dict[str, Any]]:
        """Extract lessons from common issues patterns."""
        lessons = []

        # Look for TODO/FIXME comments
        python_files = list(project_path.rglob("**/*.py"))[:50]
        todos = []
        fixmes = []

        for py_file in python_files:
            try:
                content = py_file.read_text()
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if "TODO:" in line or "FIXME:" in line:
                        todos.append(f"{py_file.name}:{i} - {line.strip()}")
                    if "FIXME:" in line:
                        fixmes.append(f"{py_file.name}:{i} - {line.strip()}")
            except Exception:
                pass

        if todos:
            lessons.append(
                {
                    "lesson": f"Found {len(todos)} TODO items - review and address",
                    "project": project_name,
                    "category": "technical_debt",
                    "source": "code_analysis",
                    "frequency": len(todos),
                }
            )

        if fixmes:
            lessons.append(
                {
                    "lesson": f"Found {len(fixmes)} FIXME items - critical issues to address",
                    "project": project_name,
                    "category": "bug",
                    "source": "code_analysis",
                    "frequency": len(fixmes),
                }
            )

        return lessons

    def _categorize_lesson(self, subject: str, body: str) -> str:
        """Categorize a lesson based on content."""
        text = (subject + " " + body).lower()

        if any(word in text for word in ["bug", "error", "fix", "broken"]):
            return "bug"
        elif any(word in text for word in ["refactor", "cleanup", "improve"]):
            return "refactoring"
        elif any(word in text for word in ["performance", "slow", "optimize"]):
            return "performance"
        elif any(word in text for word in ["security", "vulnerability", "safe"]):
            return "security"
        elif any(word in text for word in ["test", "testing", "coverage"]):
            return "testing"
        else:
            return "general"

    def extract_all_lessons(self, days: int = 90) -> List[Dict[str, Any]]:
        """Extract lessons from all projects."""
        all_lessons = []

        for project_dir in self.root_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith("."):
                try:
                    lessons = self.extract_lessons_from_project(project_dir, project_dir.name, days)
                    all_lessons.extend(lessons)
                except Exception as e:
                    logger.warning(f"Failed to extract lessons from {project_dir}: {e}")

        # Aggregate and deduplicate lessons
        return self._aggregate_lessons(all_lessons)

    def _aggregate_lessons(self, lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregate lessons by content, combining frequency and projects.

        Args:
            lessons: List of lesson dictionaries

        Returns:
            Aggregated lessons with combined frequency and project lists
        """
        lesson_map: Dict[str, Dict[str, Any]] = {}

        for lesson in lessons:
            lesson_text = lesson.get("lesson", "").strip()
            if not lesson_text:
                continue

            # Use first 100 chars as key for deduplication
            lesson_key = lesson_text[:100].lower()

            if lesson_key not in lesson_map:
                lesson_map[lesson_key] = {
                    "lesson": lesson_text,
                    "category": lesson.get("category", "general"),
                    "projects": [],
                    "sources": [],
                    "frequency": 0,
                    "first_seen": lesson.get("first_seen", datetime.now().isoformat()),
                    "last_seen": lesson.get("first_seen", datetime.now().isoformat()),
                }

            # Add project if not already present
            project = lesson.get("project", "")
            if project and project not in lesson_map[lesson_key]["projects"]:
                lesson_map[lesson_key]["projects"].append(project)

            # Add source
            source = lesson.get("source", "")
            if source and source not in lesson_map[lesson_key]["sources"]:
                lesson_map[lesson_key]["sources"].append(source)

            # Aggregate frequency
            lesson_map[lesson_key]["frequency"] += lesson.get("frequency", 1)

            # Update last_seen
            lesson_seen = lesson.get("first_seen", datetime.now().isoformat())
            if lesson_seen > lesson_map[lesson_key]["last_seen"]:
                lesson_map[lesson_key]["last_seen"] = lesson_seen

        # Convert to list and add metadata
        aggregated = []
        for lesson_data in lesson_map.values():
            aggregated.append(
                {
                    **lesson_data,
                    "project_count": len(lesson_data["projects"]),
                    "importance_score": lesson_data["frequency"] * 0.1
                    + len(lesson_data["projects"]) * 0.05,
                }
            )

        # Sort by importance score
        aggregated.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
        return aggregated

    def validate_lesson_quality(self, lesson: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate lesson quality and return quality metrics.

        Args:
            lesson: Lesson dictionary

        Returns:
            Dict with quality assessment
        """
        quality_score = 0.0
        issues = []

        # Check required fields
        if not lesson.get("lesson"):
            issues.append("Missing lesson text")
        else:
            lesson_text = lesson["lesson"]
            if len(lesson_text) < 20:
                issues.append("Lesson text too short")
            else:
                quality_score += 0.3

        # Check category
        category = lesson.get("category", "")
        if category and category != "general":
            quality_score += 0.2
        else:
            issues.append("Missing or generic category")

        # Check project association
        projects = lesson.get("projects", [])
        if len(projects) == 0:
            issues.append("No associated projects")
        else:
            quality_score += 0.2

        # Check frequency (higher frequency = more important)
        frequency = lesson.get("frequency", 0)
        if frequency > 1:
            quality_score += 0.2
        else:
            issues.append("Low frequency (may not be a common issue)")

        # Check source
        sources = lesson.get("sources", [])
        if sources:
            quality_score += 0.1

        return {
            "quality_score": min(quality_score, 1.0),
            "issues": issues,
            "is_high_quality": quality_score >= 0.6,
        }
