"""
Reflection Synthesizer - Weekly progress summary from actual work artifacts.

Reads git commits, batch results, and test outcomes to provide concise progress summary.
No monitoring overhead - just synthesizes what already happened.
"""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import re


class ReflectionSynthesizer:
    """Synthesizes recent work into actionable progress summary."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.cortex_dir = root_dir / "cortex"

    def synthesize_week(self, days: int = 7) -> Dict[str, Any]:
        """
        Synthesize last N days of work into progress summary.

        Returns:
            Dictionary with:
            - shipped: List of completed features/fixes from commits
            - blocked_by: Current blockers from failed tests/batch jobs
            - suggested_focus: Recommended next action
            - metrics: Quantitative progress (commits, tests, batch jobs)
        """
        # Gather data from multiple sources
        commits = self._get_recent_commits(days)
        batch_results = self._get_batch_results(days)
        test_status = self._get_test_status()
        goals_progress = self._get_goals_progress()

        # Synthesize into insights
        shipped = self._extract_shipped_work(commits)
        blocked_by = self._extract_blockers(batch_results, test_status)
        suggested_focus = self._suggest_focus(blocked_by, goals_progress)

        return {
            "period_days": days,
            "shipped": shipped,
            "blocked_by": blocked_by,
            "suggested_focus": suggested_focus,
            "metrics": {
                "commits": len(commits),
                "batch_jobs_completed": sum(1 for r in batch_results if r.get("success")),
                "batch_jobs_failed": sum(1 for r in batch_results if not r.get("success")),
                "active_projects": len(self._get_active_projects(commits)),
            },
            "goals_progress": goals_progress,
        }

    def _get_recent_commits(self, days: int) -> List[Dict[str, str]]:
        """Get commits from last N days across all branches."""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--since={since}",
                    "--all",
                    "--pretty=format:%H|%s|%an|%ad",
                    "--date=short",
                ],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0][:8],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                    })

            return commits
        except Exception:
            return []

    def _get_batch_results(self, days: int) -> List[Dict[str, Any]]:
        """Get batch job results from last N days."""
        batch_dir = Path.home() / ".cortex" / "batch"

        if not batch_dir.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        results = []

        # Check for result files
        for result_file in batch_dir.glob("**/*_result.json"):
            try:
                if result_file.stat().st_mtime < cutoff.timestamp():
                    continue

                with open(result_file) as f:
                    data = json.load(f)
                    results.append({
                        "job_id": result_file.stem.replace("_result", ""),
                        "success": data.get("success", False),
                        "error": data.get("error"),
                        "duration": data.get("duration_seconds"),
                    })
            except Exception:
                continue

        return results

    def _get_test_status(self) -> Dict[str, Any]:
        """Get current test status from recent test runs."""
        # Check for pytest cache or recent test output
        test_status = {"failing": [], "passing": None}

        # Look for pytest cache
        pytest_cache = self.root_dir / ".pytest_cache" / "v" / "cache" / "lastfailed"
        if pytest_cache.exists():
            try:
                with open(pytest_cache) as f:
                    failures = json.load(f)
                    test_status["failing"] = list(failures.keys())
            except Exception:
                pass

        return test_status

    def _get_goals_progress(self) -> Dict[str, Any]:
        """Get progress on strategic goals from GOALS.md."""
        goals_file = self.root_dir / "GOALS.md"

        if not goals_file.exists():
            return {"total": 0, "in_progress": 0, "completed": 0}

        try:
            content = goals_file.read_text()

            # Count goals by status
            in_progress = len(re.findall(r'\[IN PROGRESS\]', content, re.IGNORECASE))
            completed = len(re.findall(r'Status:.*?Complete', content, re.IGNORECASE))

            # Extract goal titles
            goals = []
            for match in re.finditer(r'### Goal \d+: ([^\n\[]+)', content):
                title = match.group(1).strip()
                goals.append(title)

            return {
                "total": len(goals),
                "in_progress": in_progress,
                "completed": completed,
                "goals": goals[:3],  # First 3 goals
            }
        except Exception:
            return {"total": 0, "in_progress": 0, "completed": 0}

    def _extract_shipped_work(self, commits: List[Dict[str, str]]) -> List[str]:
        """Extract completed work from commit messages."""
        shipped = []

        # Pattern matching for meaningful commits
        feature_patterns = [
            r'feat\(([^)]+)\):?\s*(.+)',
            r'fix\(([^)]+)\):?\s*(.+)',
            r'docs\(([^)]+)\):?\s*(.+)',
        ]

        for commit in commits:
            msg = commit["message"]

            for pattern in feature_patterns:
                match = re.match(pattern, msg, re.IGNORECASE)
                if match:
                    scope = match.group(1)
                    description = match.group(2)
                    shipped.append(f"{scope}: {description}")
                    break

        # Group by project
        grouped = {}
        for item in shipped:
            parts = item.split(":", 1)
            if len(parts) == 2:
                project, desc = parts
                if project not in grouped:
                    grouped[project] = []
                grouped[project].append(desc.strip())

        # Format as bullet points
        formatted = []
        for project, items in grouped.items():
            if len(items) == 1:
                formatted.append(f"{project}: {items[0]}")
            else:
                formatted.append(f"{project}: {len(items)} changes")

        return formatted[:5]  # Top 5 items

    def _extract_blockers(
        self, batch_results: List[Dict[str, Any]], test_status: Dict[str, Any]
    ) -> List[str]:
        """Extract current blockers from failed jobs and tests."""
        blockers = []

        # Failed batch jobs
        failed_jobs = [r for r in batch_results if not r.get("success")]
        if failed_jobs:
            for job in failed_jobs[:3]:  # Top 3 failures
                error = job.get("error", "Unknown error")
                blockers.append(f"Batch job {job['job_id']}: {error}")

        # Failed tests
        failing_tests = test_status.get("failing", [])
        if failing_tests:
            if len(failing_tests) <= 3:
                for test in failing_tests:
                    blockers.append(f"Test failing: {test}")
            else:
                blockers.append(f"{len(failing_tests)} tests failing")

        return blockers

    def _suggest_focus(
        self, blockers: List[str], goals_progress: Dict[str, Any]
    ) -> str:
        """Suggest next focus based on blockers and goal progress."""
        # Priority 1: Unblock failing work
        if blockers:
            return f"Unblock: {blockers[0]}"

        # Priority 2: Advance in-progress goals
        if goals_progress.get("in_progress", 0) > 0:
            goals = goals_progress.get("goals", [])
            if goals:
                return f"Advance: {goals[0]}"

        # Priority 3: Start next goal
        if goals_progress.get("total", 0) > goals_progress.get("in_progress", 0):
            return "Start next planned goal"

        return "No clear blocker - continue current work"

    def _get_active_projects(self, commits: List[Dict[str, str]]) -> set:
        """Extract unique projects from commits."""
        projects = set()

        for commit in commits:
            # Try to extract project from commit message
            match = re.match(r'(?:feat|fix|docs)\(([^)]+)\)', commit["message"])
            if match:
                projects.add(match.group(1))

        return projects

    def format_reflection(self, reflection: Dict[str, Any]) -> str:
        """Format reflection data for terminal display."""
        lines = []

        lines.append("╔══════════════════════════════════════════════════════╗")
        lines.append("║              CORTEX - WEEKLY REFLECTION              ║")
        lines.append("╚══════════════════════════════════════════════════════╝")
        lines.append("")

        # Time period
        period = reflection["period_days"]
        lines.append(f"📅 Last {period} days")
        lines.append("")

        # What shipped
        lines.append("🚀 SHIPPED")
        lines.append("─" * 54)
        shipped = reflection["shipped"]
        if shipped:
            for item in shipped:
                lines.append(f"  • {item}")
        else:
            lines.append("  (No notable commits)")
        lines.append("")

        # Blockers
        lines.append("🚧 BLOCKED BY")
        lines.append("─" * 54)
        blockers = reflection["blocked_by"]
        if blockers:
            for blocker in blockers:
                lines.append(f"  • {blocker}")
        else:
            lines.append("  (No blockers)")
        lines.append("")

        # Suggested focus
        lines.append("🎯 SUGGESTED FOCUS")
        lines.append("─" * 54)
        lines.append(f"  {reflection['suggested_focus']}")
        lines.append("")

        # Metrics
        metrics = reflection["metrics"]
        lines.append("📊 METRICS")
        lines.append("─" * 54)
        lines.append(f"  Commits: {metrics['commits']}")
        lines.append(f"  Batch jobs: {metrics['batch_jobs_completed']} completed, {metrics['batch_jobs_failed']} failed")
        lines.append(f"  Active projects: {metrics['active_projects']}")
        lines.append("")

        # Goals progress
        goals = reflection.get("goals_progress", {})
        if goals.get("total", 0) > 0:
            lines.append("🎯 GOALS PROGRESS")
            lines.append("─" * 54)
            lines.append(f"  Total: {goals['total']}")
            lines.append(f"  In Progress: {goals['in_progress']}")
            lines.append(f"  Completed: {goals['completed']}")

            if goals.get("goals"):
                lines.append("")
                lines.append("  Active Goals:")
                for goal in goals["goals"]:
                    lines.append(f"    • {goal}")
            lines.append("")

        return "\n".join(lines)


def generate_weekly_reflection(root_dir: Optional[Path] = None, days: int = 7) -> Dict[str, Any]:
    """Generate weekly reflection summary."""
    if root_dir is None:
        root_dir = Path("/Users/jesse.kemp/Dev")

    synthesizer = ReflectionSynthesizer(root_dir)
    return synthesizer.synthesize_week(days)


def format_reflection(reflection: Dict[str, Any]) -> str:
    """Format reflection for display."""
    synthesizer = ReflectionSynthesizer(Path("/Users/jesse.kemp/Dev"))
    return synthesizer.format_reflection(reflection)
