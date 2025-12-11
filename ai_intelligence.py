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
import os


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
    """Scans git repositories for activity analysis."""

    # Directories to skip when scanning
    SKIP_DIRS = {
        'node_modules', 'venv', 'env', '.venv', '__pycache__',
        '.git', '.idea', '.vscode', 'build', 'dist', '.next',
        'target', 'vendor', '.cache', '.pytest_cache'
    }

    # Known project directories (whitelist for faster scanning)
    KNOWN_PROJECTS = {
        'VortexV2', 'alpha_arena', 'personal-ai-dataset', 'keto-tracker',
        'financial-aggregator', 'ai-project-curator', 'Windfield', 'Vortex',
        'cortex', 'local-orchestrator', 'youtube-summarizer', 'DJ-CoPilot',
        'cursor-usage-optimizer', 'Databricks'
    }

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def find_git_repos(self, max_depth: int = 2) -> List[Path]:
        """Find git repositories under root directory."""
        repos = []

        # First check known projects for faster scanning
        for project_name in self.KNOWN_PROJECTS:
            project_path = self.root_dir / project_name
            git_path = project_path / '.git'
            if git_path.exists():
                repos.append(project_path)

        # Also check subdirectories (e.g., Vortex/VortexV2)
        for item in self.root_dir.iterdir():
            if not item.is_dir() or item.name in self.SKIP_DIRS:
                continue
            if item.name.startswith('.'):
                continue

            # Check if it's a git repo
            if (item / '.git').exists() and item not in repos:
                repos.append(item)

            # Check one level deeper for nested projects
            if max_depth > 1:
                for subitem in item.iterdir():
                    if not subitem.is_dir() or subitem.name in self.SKIP_DIRS:
                        continue
                    if (subitem / '.git').exists() and subitem not in repos:
                        repos.append(subitem)

        return repos

    def analyze_project(self, repo_path: Path) -> ProjectActivity:
        """Analyze a git repository for activity metrics."""
        name = repo_path.name

        # Get commit counts
        commits_7d = self._count_commits(repo_path, days=7)
        commits_30d = self._count_commits(repo_path, days=30)

        # Determine status
        if commits_7d >= 3:
            status = "active"
        elif commits_7d > 0 or commits_30d > 0:
            status = "recent"
        else:
            status = "dormant"

        # Get other metrics
        files_changed_7d = self._count_files_changed(repo_path, days=7)
        uncommitted_changes = self._count_uncommitted_changes(repo_path)
        current_branch = self._get_current_branch(repo_path)
        last_commit_date, last_commit_msg = self._get_last_commit_info(repo_path)

        # Detect blockers
        blockers = self._detect_blockers(repo_path, uncommitted_changes)

        return ProjectActivity(
            name=name,
            path=repo_path,
            status=status,
            commits_7d=commits_7d,
            commits_30d=commits_30d,
            files_changed_7d=files_changed_7d,
            uncommitted_changes=uncommitted_changes,
            blockers=blockers,
            current_branch=current_branch,
            last_commit_date=last_commit_date,
            last_commit_msg=last_commit_msg
        )

    def _run_git_command(self, repo_path: Path, args: List[str]) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _count_commits(self, repo_path: Path, days: int) -> int:
        """Count commits in the last N days."""
        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        output = self._run_git_command(
            repo_path,
            ['log', '--oneline', f'--since={since_date}']
        )
        if not output:
            return 0
        return len(output.split('\n'))

    def _count_files_changed(self, repo_path: Path, days: int) -> int:
        """Count unique files changed in the last N days."""
        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        output = self._run_git_command(
            repo_path,
            ['log', '--name-only', '--pretty=format:', f'--since={since_date}']
        )
        if not output:
            return 0
        files = set(f for f in output.split('\n') if f.strip())
        return len(files)

    def _count_uncommitted_changes(self, repo_path: Path) -> int:
        """Count uncommitted changes (staged + unstaged)."""
        output = self._run_git_command(repo_path, ['status', '--porcelain'])
        if not output:
            return 0
        return len([l for l in output.split('\n') if l.strip()])

    def _get_current_branch(self, repo_path: Path) -> str:
        """Get current git branch."""
        return self._run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])

    def _get_last_commit_info(self, repo_path: Path) -> tuple:
        """Get last commit date and message."""
        date_str = self._run_git_command(
            repo_path,
            ['log', '-1', '--format=%ci']
        )
        msg = self._run_git_command(
            repo_path,
            ['log', '-1', '--format=%s']
        )

        last_date = None
        if date_str:
            try:
                # Parse git date format: 2024-01-15 10:30:00 -0500
                last_date = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

        return last_date, msg

    def _detect_blockers(self, repo_path: Path, uncommitted_changes: int) -> List[str]:
        """Detect potential blockers for a project."""
        blockers = []

        # Large uncommitted changes
        if uncommitted_changes > 20:
            blockers.append(f"Large uncommitted changes ({uncommitted_changes} files)")

        # Missing .env file
        if (repo_path / '.env.example').exists() and not (repo_path / '.env').exists():
            blockers.append("Missing .env file (copy from .env.example)")

        # Missing dependencies
        if (repo_path / 'requirements.txt').exists():
            if not (repo_path / 'venv').exists() and not (repo_path / '.venv').exists():
                blockers.append("No virtualenv detected")

        if (repo_path / 'package.json').exists():
            if not (repo_path / 'node_modules').exists():
                blockers.append("Missing node_modules (run npm install)")

        # Merge conflicts
        output = self._run_git_command(repo_path, ['diff', '--name-only', '--diff-filter=U'])
        if output:
            blockers.append("Unresolved merge conflicts")

        # Detached HEAD
        branch = self._get_current_branch(repo_path)
        if branch == 'HEAD':
            blockers.append("Detached HEAD state")

        return blockers


def main():
    """CLI for testing project scanner."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Scan projects for activity')
    parser.add_argument('--root', default='/Users/jesse.kemp/Dev', help='Root directory')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--recommend', action='store_true', help='Show recommendations')
    args = parser.parse_args()

    scanner = ProjectScanner(args.root)
    repos = scanner.find_git_repos()

    projects = []
    for repo in repos:
        activity = scanner.analyze_project(repo)
        projects.append(activity)

    # Sort by activity (active first, then by commits)
    projects.sort(key=lambda p: (
        0 if p.status == 'active' else 1 if p.status == 'recent' else 2,
        -p.commits_7d
    ))

    if args.json:
        output = []
        for p in projects:
            output.append({
                'name': p.name,
                'path': str(p.path),
                'status': p.status,
                'commits_7d': p.commits_7d,
                'commits_30d': p.commits_30d,
                'files_changed_7d': p.files_changed_7d,
                'uncommitted_changes': p.uncommitted_changes,
                'blockers': p.blockers,
                'current_branch': p.current_branch,
                'last_commit_date': p.last_commit_date.isoformat() if p.last_commit_date else None,
                'last_commit_msg': p.last_commit_msg
            })
        print(json.dumps(output, indent=2))
    else:
        print(f"Found {len(projects)} projects\n")

        active = [p for p in projects if p.status == 'active']
        recent = [p for p in projects if p.status == 'recent']
        dormant = [p for p in projects if p.status == 'dormant']

        if active:
            print("ACTIVE (3+ commits in 7d):")
            for p in active:
                print(f"  {p.name}: {p.commits_7d} commits, {p.files_changed_7d} files changed")

        if recent:
            print("\nRECENT (activity in 30d):")
            for p in recent:
                print(f"  {p.name}: {p.commits_7d}/{p.commits_30d} commits (7d/30d)")

        if dormant:
            print("\nDORMANT (no recent activity):")
            for p in dormant[:5]:  # Limit dormant to 5
                print(f"  {p.name}")
            if len(dormant) > 5:
                print(f"  ... and {len(dormant) - 5} more")

        # Show blockers
        all_blockers = [(p.name, b) for p in projects for b in p.blockers]
        if all_blockers:
            print("\nBLOCKERS:")
            for name, blocker in all_blockers[:10]:
                print(f"  {name}: {blocker}")


if __name__ == '__main__':
    main()
