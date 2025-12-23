"""
Git Analyzer - Extract project health metrics from git repositories

Provides:
- Commit activity analysis
- Contributor patterns
- File change tracking
- Health score calculation
- Trend detection
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess
import json
from collections import defaultdict


class GitAnalyzer:
    """Analyze git repositories for project health metrics"""

    def __init__(self, repo_path: Path):
        """
        Initialize analyzer for a git repository

        Args:
            repo_path: Path to git repository root
        """
        self.repo_path = Path(repo_path)
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

    def get_recent_commits(self, days: int = 30) -> Dict[str, Any]:
        """
        Get commits from last N days with analysis

        Args:
            days: Number of days to look back

        Returns:
            Dict with commit count, authors, files changed, trend
        """
        since_date = datetime.now() - timedelta(days=days)
        since_str = since_date.strftime("%Y-%m-%d")

        # Get commits with stats
        cmd = [
            "git", "log",
            f"--since={since_str}",
            "--pretty=format:%H|%an|%ae|%at|%s",
            "--numstat"
        ]

        result = subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return {
                "count": 0,
                "authors": {},
                "files_changed": {},
                "trend": "unknown",
                "error": result.stderr
            }

        commits = self._parse_commit_log(result.stdout)

        return {
            "count": len(commits),
            "authors": self._get_author_stats(commits),
            "files_changed": self._get_file_stats(commits),
            "trend": self._calculate_trend(commits, days),
            "commits": commits[:10]  # Last 10 for reference
        }

    def _parse_commit_log(self, log_output: str) -> List[Dict[str, Any]]:
        """Parse git log output into structured commit data"""
        commits = []
        current_commit = None

        for line in log_output.split('\n'):
            if '|' in line and len(line.split('|')) == 5:
                # New commit header
                if current_commit:
                    commits.append(current_commit)

                hash_val, author, email, timestamp, message = line.split('|')
                current_commit = {
                    "hash": hash_val[:7],
                    "author": author,
                    "email": email,
                    "timestamp": int(timestamp),
                    "message": message,
                    "files": []
                }
            elif current_commit and '\t' in line:
                # File stat line (additions, deletions, filename)
                parts = line.split('\t')
                if len(parts) == 3:
                    additions, deletions, filename = parts
                    try:
                        current_commit["files"].append({
                            "filename": filename,
                            "additions": int(additions) if additions != '-' else 0,
                            "deletions": int(deletions) if deletions != '-' else 0
                        })
                    except ValueError:
                        # Binary file or special case
                        current_commit["files"].append({
                            "filename": filename,
                            "additions": 0,
                            "deletions": 0
                        })

        if current_commit:
            commits.append(current_commit)

        return commits

    def _get_author_stats(self, commits: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get commit count per author"""
        author_counts = defaultdict(int)
        for commit in commits:
            author_counts[commit["author"]] += 1
        return dict(author_counts)

    def _get_file_stats(self, commits: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get change count per file"""
        file_counts = defaultdict(int)
        for commit in commits:
            for file_info in commit.get("files", []):
                file_counts[file_info["filename"]] += 1
        # Return top 20 most changed files
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_files[:20])

    def _calculate_trend(self, commits: List[Dict[str, Any]], total_days: int) -> str:
        """
        Calculate commit trend (increasing/decreasing/stable)

        Compares first half vs second half of the period
        """
        if len(commits) < 2:
            return "insufficient_data"

        # Sort commits by timestamp
        sorted_commits = sorted(commits, key=lambda x: x["timestamp"])

        # Split into two halves
        mid_point = len(sorted_commits) // 2
        first_half = sorted_commits[:mid_point]
        second_half = sorted_commits[mid_point:]

        first_count = len(first_half)
        second_count = len(second_half)

        # Calculate rate (commits per day)
        first_rate = first_count / (total_days / 2)
        second_rate = second_count / (total_days / 2)

        # Determine trend
        if second_rate > first_rate * 1.2:
            return "increasing"
        elif second_rate < first_rate * 0.8:
            return "decreasing"
        else:
            return "stable"

    def get_branch_info(self) -> Dict[str, Any]:
        """Get information about branches"""
        # Get current branch
        current_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )

        # Get all branches
        branches_result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )

        branches = [
            b.strip().replace("* ", "")
            for b in branches_result.stdout.split('\n')
            if b.strip() and not b.strip().startswith("remotes/")
        ]

        return {
            "current": current_result.stdout.strip(),
            "total_local": len(branches),
            "branches": branches
        }

    def get_uncommitted_changes(self) -> Dict[str, Any]:
        """Get information about uncommitted changes"""
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )

        if status_result.returncode != 0:
            return {"error": status_result.stderr}

        lines = [line for line in status_result.stdout.split('\n') if line.strip()]

        modified = [line[3:] for line in lines if line.startswith(" M")]
        added = [line[3:] for line in lines if line.startswith("A ")]
        deleted = [line[3:] for line in lines if line.startswith(" D")]
        untracked = [line[3:] for line in lines if line.startswith("??")]

        return {
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "untracked": untracked,
            "total": len(lines),
            "has_changes": len(lines) > 0
        }

    def calculate_health_score(
        self,
        commit_data: Dict[str, Any],
        uncommitted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate project health score (0-100)

        Scoring:
        - Commit activity (0-40 points): Recent commits indicate active project
        - Trend (0-25 points): Increasing/stable is good, decreasing is concerning
        - Uncommitted work (0-25 points): Clean repo is good
        - Contributor diversity (0-10 points): Multiple contributors is healthy

        Args:
            commit_data: From get_recent_commits()
            uncommitted_data: From get_uncommitted_changes()

        Returns:
            Dict with score, breakdown, and assessment
        """
        scores = {}

        # 1. Commit Activity Score (0-40 points)
        commit_count = commit_data.get("count", 0)
        if commit_count >= 30:
            scores["activity"] = 40
        elif commit_count >= 20:
            scores["activity"] = 35
        elif commit_count >= 10:
            scores["activity"] = 25
        elif commit_count >= 5:
            scores["activity"] = 15
        else:
            scores["activity"] = max(0, commit_count * 2)

        # 2. Trend Score (0-25 points)
        trend = commit_data.get("trend", "unknown")
        if trend == "increasing":
            scores["trend"] = 25
        elif trend == "stable":
            scores["trend"] = 20
        elif trend == "decreasing":
            scores["trend"] = 10
        else:
            scores["trend"] = 15

        # 3. Clean Repository Score (0-25 points)
        uncommitted_count = uncommitted_data.get("total", 0)
        if uncommitted_count == 0:
            scores["cleanliness"] = 25
        elif uncommitted_count <= 3:
            scores["cleanliness"] = 20
        elif uncommitted_count <= 10:
            scores["cleanliness"] = 12
        else:
            scores["cleanliness"] = max(0, 25 - uncommitted_count)

        # 4. Contributor Diversity Score (0-10 points)
        authors = commit_data.get("authors", {})
        author_count = len(authors)
        if author_count >= 3:
            scores["diversity"] = 10
        elif author_count == 2:
            scores["diversity"] = 7
        elif author_count == 1:
            scores["diversity"] = 5
        else:
            scores["diversity"] = 0

        total_score = sum(scores.values())

        # Determine assessment
        if total_score >= 80:
            assessment = "excellent"
        elif total_score >= 60:
            assessment = "good"
        elif total_score >= 40:
            assessment = "fair"
        else:
            assessment = "needs_attention"

        return {
            "total_score": total_score,
            "breakdown": scores,
            "assessment": assessment,
            "max_score": 100
        }

    def get_project_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive project summary

        Args:
            days: Days to analyze

        Returns:
            Complete project health summary
        """
        commits = self.get_recent_commits(days)
        branches = self.get_branch_info()
        uncommitted = self.get_uncommitted_changes()
        health = self.calculate_health_score(commits, uncommitted)

        return {
            "project": self.repo_path.name,
            "path": str(self.repo_path),
            "analysis_period_days": days,
            "commits": commits,
            "branches": branches,
            "uncommitted": uncommitted,
            "health": health,
            "timestamp": datetime.now().isoformat()
        }


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python git_analyzer.py <repo_path> [days]")
        print("Example: python git_analyzer.py /Users/jesse.kemp/Dev/Vortex/VortexV2 30")
        sys.exit(1)

    repo_path = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    analyzer = GitAnalyzer(repo_path)
    summary = analyzer.get_project_summary(days)

    print(json.dumps(summary, indent=2, default=str))
