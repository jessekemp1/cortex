#!/usr/bin/env python3
"""
Git Hygiene Analyzer - Proactive checks to prevent mega-PRs.

Monitors:
- Uncommitted line count (warn at 500, alert at 1000)
- Branch age (warn at 3 days, alert at 7 days)
- Commits ahead of main (warn at 10, alert at 25)
- File count changes (warn at 50, alert at 100)

Anti-pattern prevented: Mega-PR Accumulation (65+ commits, 135K+ lines)
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class HygieneAlert:
    """A single hygiene alert."""
    level: str  # "ok", "warning", "alert", "critical"
    category: str  # "lines", "age", "commits", "files"
    message: str
    value: int
    threshold: int
    recommendation: str


@dataclass
class HygieneReport:
    """Complete git hygiene report."""
    timestamp: datetime
    branch: str
    alerts: List[HygieneAlert]
    uncommitted_lines: int
    uncommitted_files: int
    branch_age_days: float
    commits_ahead: int

    @property
    def overall_status(self) -> str:
        """Get worst alert level."""
        levels = ["ok", "warning", "alert", "critical"]
        max_level = 0
        for alert in self.alerts:
            level_idx = levels.index(alert.level)
            max_level = max(max_level, level_idx)
        return levels[max_level]

    @property
    def needs_action(self) -> bool:
        """Check if any alert requires action."""
        return self.overall_status in ("alert", "critical")

    def summary(self) -> str:
        """Generate human-readable summary."""
        status_icons = {
            "ok": "✅",
            "warning": "⚠️",
            "alert": "🔴",
            "critical": "🚨"
        }

        lines = [
            f"\n{'='*60}",
            f"🧹 GIT HYGIENE CHECK - {self.branch}",
            f"{'='*60}",
            f"",
            f"📊 Status: {status_icons[self.overall_status]} {self.overall_status.upper()}",
            f"",
            f"Metrics:",
            f"  • Uncommitted lines: {self.uncommitted_lines:,}",
            f"  • Uncommitted files: {self.uncommitted_files}",
            f"  • Branch age: {self.branch_age_days:.1f} days",
            f"  • Commits ahead of main: {self.commits_ahead}",
        ]

        if self.alerts:
            lines.append(f"\nAlerts:")
            for alert in self.alerts:
                icon = status_icons[alert.level]
                lines.append(f"  {icon} [{alert.category}] {alert.message}")
                lines.append(f"     → {alert.recommendation}")

        lines.append(f"\n{'='*60}")
        return "\n".join(lines)


class GitHygieneAnalyzer:
    """Analyzes git repository for hygiene issues."""

    # Thresholds
    THRESHOLDS = {
        "lines": {
            "warning": 500,
            "alert": 1000,
            "critical": 2000
        },
        "files": {
            "warning": 30,
            "alert": 50,
            "critical": 100
        },
        "branch_age_days": {
            "warning": 3,
            "alert": 5,
            "critical": 7
        },
        "commits_ahead": {
            "warning": 10,
            "alert": 25,
            "critical": 50
        }
    }

    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize with repository path."""
        self.repo_path = Path(repo_path) if repo_path else self._find_git_root()

    def _find_git_root(self) -> Path:
        """Find the git repository root."""
        path = Path.cwd()
        while path != path.parent:
            if (path / ".git").exists():
                return path
            path = path.parent
        raise ValueError("Not in a git repository")

    def _run_git(self, *args) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_path)] + list(args),
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return ""

    def get_current_branch(self) -> str:
        """Get current branch name."""
        return self._run_git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"

    def get_uncommitted_stats(self) -> Tuple[int, int]:
        """Get uncommitted line count and file count."""
        # Get diff stats for staged + unstaged
        diff_output = self._run_git("diff", "--stat", "HEAD")

        # Also count untracked files
        untracked = self._run_git("ls-files", "--others", "--exclude-standard")
        untracked_files = [f for f in untracked.split("\n") if f.strip()]

        # Parse diff output for line counts
        total_lines = 0
        total_files = 0

        if diff_output:
            lines = diff_output.strip().split("\n")
            for line in lines:
                # Match patterns like "3 insertions(+), 1 deletion(-)"
                if "changed" in line:
                    # Summary line
                    import re
                    nums = re.findall(r'(\d+)', line)
                    if len(nums) >= 2:
                        total_files = int(nums[0])
                        total_lines = sum(int(n) for n in nums[1:])

        # Add untracked files (estimate 50 lines each if we can't read them)
        total_files += len(untracked_files)
        for f in untracked_files:
            try:
                file_path = self.repo_path / f
                if file_path.exists() and file_path.is_file():
                    with open(file_path, 'r', errors='ignore') as fp:
                        total_lines += sum(1 for _ in fp)
            except:
                total_lines += 50  # Estimate

        return total_lines, total_files

    def get_branch_age_days(self) -> float:
        """Get age of current branch in days."""
        branch = self.get_current_branch()
        if branch in ("main", "master"):
            return 0.0

        # Get the commit where branch diverged from main
        merge_base = self._run_git("merge-base", "main", "HEAD")
        if not merge_base:
            merge_base = self._run_git("merge-base", "master", "HEAD")

        if not merge_base:
            return 0.0

        # Get timestamp of that commit
        timestamp = self._run_git("show", "-s", "--format=%ct", merge_base)
        if not timestamp:
            return 0.0

        try:
            branch_start = datetime.fromtimestamp(int(timestamp))
            age = datetime.now() - branch_start
            return age.total_seconds() / 86400  # Convert to days
        except:
            return 0.0

    def get_commits_ahead(self) -> int:
        """Get number of commits ahead of main."""
        branch = self.get_current_branch()
        if branch in ("main", "master"):
            return 0

        # Try main first, then master
        count = self._run_git("rev-list", "--count", "main..HEAD")
        if not count:
            count = self._run_git("rev-list", "--count", "master..HEAD")

        try:
            return int(count) if count else 0
        except:
            return 0

    def _check_threshold(
        self,
        category: str,
        value: float,
        unit: str = ""
    ) -> Optional[HygieneAlert]:
        """Check a value against thresholds."""
        thresholds = self.THRESHOLDS.get(category, {})

        recommendations = {
            "lines": {
                "warning": "Consider committing current work with `/commit`",
                "alert": "Split changes into logical commits NOW",
                "critical": "STOP! Commit immediately before adding more changes"
            },
            "files": {
                "warning": "Group related files and commit separately",
                "alert": "Too many files - split into multiple commits",
                "critical": "STOP! This will be unreviewable. Commit in parts."
            },
            "branch_age_days": {
                "warning": "Consider merging to main soon",
                "alert": "Branch is getting stale - merge or rebase",
                "critical": "STOP! Merge to main immediately to avoid conflicts"
            },
            "commits_ahead": {
                "warning": "Consider creating a PR",
                "alert": "Too many commits - create PR and merge",
                "critical": "STOP! This PR will be impossible to review"
            }
        }

        level = "ok"
        for lvl in ["critical", "alert", "warning"]:
            if lvl in thresholds and value >= thresholds[lvl]:
                level = lvl
                break

        if level == "ok":
            return None

        return HygieneAlert(
            level=level,
            category=category,
            message=f"{value:,.0f}{unit} (threshold: {thresholds[level]}{unit})",
            value=int(value),
            threshold=thresholds[level],
            recommendation=recommendations.get(category, {}).get(level, "Take action")
        )

    def analyze(self) -> HygieneReport:
        """Run full hygiene analysis."""
        branch = self.get_current_branch()
        lines, files = self.get_uncommitted_stats()
        age = self.get_branch_age_days()
        commits = self.get_commits_ahead()

        alerts = []

        # Check each metric
        if alert := self._check_threshold("lines", lines):
            alerts.append(alert)

        if alert := self._check_threshold("files", files):
            alerts.append(alert)

        if alert := self._check_threshold("branch_age_days", age, " days"):
            alerts.append(alert)

        if alert := self._check_threshold("commits_ahead", commits):
            alerts.append(alert)

        return HygieneReport(
            timestamp=datetime.now(),
            branch=branch,
            alerts=alerts,
            uncommitted_lines=lines,
            uncommitted_files=files,
            branch_age_days=age,
            commits_ahead=commits
        )

    def quick_check(self) -> str:
        """Quick one-line status for embedding in other commands."""
        report = self.analyze()

        if report.overall_status == "ok":
            return "✅ Git hygiene: OK"
        elif report.overall_status == "warning":
            return f"⚠️ Git hygiene: {len(report.alerts)} warning(s) - run `/git-hygiene` for details"
        elif report.overall_status == "alert":
            return f"🔴 Git hygiene: ACTION NEEDED - {report.uncommitted_lines:,} uncommitted lines"
        else:
            return f"🚨 Git hygiene: CRITICAL - commit immediately!"


def main():
    """CLI entry point."""
    import sys

    repo_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    try:
        analyzer = GitHygieneAnalyzer(repo_path)
        report = analyzer.analyze()
        print(report.summary())

        # Exit with code based on status
        exit_codes = {"ok": 0, "warning": 0, "alert": 1, "critical": 2}
        sys.exit(exit_codes.get(report.overall_status, 0))

    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
