"""
Deep Analysis Mode - Comprehensive portfolio intelligence

Implements depth-first analysis without speed optimizations.
Prioritizes quality over latency.

Design: Simple, synchronous, comprehensive
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GitAnalysis:
    """Comprehensive git analysis"""

    commits: List[Dict]
    commit_count: int
    authors: List[str]
    branches: List[str]
    current_branch: str
    uncommitted_files: int
    stale_branches: List[str]
    days_analyzed: int
    churn_stats: Optional[Dict] = None


@dataclass
class HealthAnalysis:
    """Fresh health analysis (no caching)"""

    score: int
    assessment: str
    trend: str
    commits_7d: int
    commits_30d: int
    uncommitted_files: int
    last_commit_days: int
    contributors_active: int
    warnings: List[str]


@dataclass
class SpecMatch:
    """Relevant specification match"""

    title: str
    path: str
    similarity: float
    summary: str


@dataclass
class PatternMatch:
    """Cross-project pattern match"""

    name: str
    description: str
    projects: List[str]
    confidence: float
    relevance: float


@dataclass
class CodeQuality:
    """Code quality metrics"""

    linting_issues: int
    complexity_score: float
    test_coverage: Optional[float]
    todos: int
    fixmes: int
    tech_debt_markers: int


@dataclass
class DependencyGraph:
    """Project dependency analysis"""

    dependencies: Dict[str, List[str]]
    circular_deps: List[List[str]]
    depth: int
    complexity_score: float


@dataclass
class DeepIntelligence:
    """Comprehensive deep intelligence result"""

    timestamp: datetime
    project: str
    mode: str
    latency_ms: float

    # Core analyses
    git: GitAnalysis
    health: HealthAnalysis
    specs: List[SpecMatch]
    patterns: List[PatternMatch]
    quality: CodeQuality
    dependencies: Optional[DependencyGraph]

    # Insights
    warnings: List[str]
    recommendations: List[Dict]
    next_actions: List[str]

    # Metadata
    analysis_config: Dict


class DeepAnalyzer:
    """
    Deep portfolio intelligence analyzer

    No caching, no lazy loading, no async - just comprehensive analysis
    """

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)

    def analyze(self, project: str, config: Dict) -> DeepIntelligence:
        """
        Run comprehensive deep analysis

        Args:
            project: Project name
            config: Analysis configuration from adaptive_latency

        Returns:
            DeepIntelligence with all analysis results
        """
        start_time = datetime.now()
        project_path = self.root_dir / project

        # Run all analyses (no optimization, just correctness)
        git_analysis = self._analyze_git(project_path, config)
        health_analysis = self._analyze_health(git_analysis, config)
        spec_matches = self._search_specs(project, config)
        pattern_matches = self._match_patterns(project, config)
        quality_analysis = self._analyze_quality(project_path, config)
        dependency_graph = self._analyze_dependencies(project_path, config)

        # Generate insights
        warnings = self._generate_warnings(git_analysis, health_analysis, quality_analysis)
        recommendations = self._generate_recommendations(
            git_analysis, health_analysis, spec_matches, pattern_matches
        )
        next_actions = self._identify_next_actions(recommendations)

        end_time = datetime.now()
        latency_ms = (end_time - start_time).total_seconds() * 1000

        return DeepIntelligence(
            timestamp=end_time,
            project=project,
            mode="deep",
            latency_ms=latency_ms,
            git=git_analysis,
            health=health_analysis,
            specs=spec_matches,
            patterns=pattern_matches,
            quality=quality_analysis,
            dependencies=dependency_graph,
            warnings=warnings,
            recommendations=recommendations,
            next_actions=next_actions,
            analysis_config=config,
        )

    def _analyze_git(self, project_path: Path, config: Dict) -> GitAnalysis:
        """
        Deep git analysis - no caching, fresh data

        Args:
            project_path: Path to project
            config: Analysis config with git_days

        Returns:
            GitAnalysis with comprehensive git data
        """
        days = config.get("git_days", 90)

        try:
            # Get commit history
            log_result = subprocess.run(
                ["git", "log", f"--since={days} days ago", "--pretty=format:%H|%an|%ae|%ad|%s"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            commits = []
            if log_result.returncode == 0:
                for line in log_result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 5:
                        commits.append(
                            {
                                "hash": parts[0],
                                "author": parts[1],
                                "email": parts[2],
                                "date": parts[3],
                                "message": parts[4],
                            }
                        )

            # Get authors
            authors = list(set(c["author"] for c in commits))

            # Get branches
            branches_result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            branches = []
            current_branch = ""
            if branches_result.returncode == 0:
                for line in branches_result.stdout.split("\n"):
                    line = line.strip()
                    if line.startswith("* "):
                        current_branch = line[2:]
                        branches.append(current_branch)
                    elif line:
                        branches.append(line)

            # Get uncommitted files
            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            uncommitted_files = len([l for l in status_result.stdout.split("\n") if l.strip()])

            # Detect stale branches (branches with no commits in last 60 days)
            stale_branches = []
            if config.get("git_include_stats", True):
                for branch in branches:
                    if branch == current_branch or not branch:
                        continue
                    last_commit = subprocess.run(
                        ["git", "log", "-1", "--since=60 days ago", branch],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if last_commit.returncode == 0 and not last_commit.stdout.strip():
                        stale_branches.append(branch)

            churn_stats = None
            if config.get("git_include_stats", True):
                # Calculate code churn (files changed most frequently)
                churn_result = subprocess.run(
                    ["git", "log", f"--since={days} days ago", "--name-only", "--pretty=format:"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if churn_result.returncode == 0:
                    files = [f for f in churn_result.stdout.split("\n") if f.strip()]
                    file_counts = {}
                    for f in files:
                        file_counts[f] = file_counts.get(f, 0) + 1
                    top_churn = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    churn_stats = {
                        "total_files_changed": len(file_counts),
                        "top_churn_files": [{"file": f, "changes": c} for f, c in top_churn],
                    }

            return GitAnalysis(
                commits=commits,
                commit_count=len(commits),
                authors=authors,
                branches=branches,
                current_branch=current_branch,
                uncommitted_files=uncommitted_files,
                stale_branches=stale_branches,
                days_analyzed=days,
                churn_stats=churn_stats,
            )

        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            # Return minimal data on error
            return GitAnalysis(
                commits=[],
                commit_count=0,
                authors=[],
                branches=[],
                current_branch="",
                uncommitted_files=0,
                stale_branches=[],
                days_analyzed=days,
            )

    def _analyze_health(self, git: GitAnalysis, config: Dict) -> HealthAnalysis:
        """
        Calculate fresh health score (no caching)

        Args:
            git: Git analysis results
            config: Analysis config

        Returns:
            HealthAnalysis with fresh health data
        """
        # Simple scoring algorithm
        score = 100

        # Deduct for lack of recent activity
        commits_7d = len([c for c in git.commits if self._is_recent(c["date"], 7)])
        commits_30d = len([c for c in git.commits if self._is_recent(c["date"], 30)])

        if commits_7d == 0:
            score -= 20
        elif commits_7d < 3:
            score -= 10

        # Deduct for uncommitted work
        if git.uncommitted_files > 50:
            score -= 20
        elif git.uncommitted_files > 20:
            score -= 10

        # Deduct for stale branches
        if len(git.stale_branches) > 5:
            score -= 15
        elif len(git.stale_branches) > 2:
            score -= 5

        # Calculate trend
        trend = "stable"
        if commits_7d > commits_30d / 2:
            trend = "improving"
        elif commits_7d < commits_30d / 6:
            trend = "declining"

        # Assessment
        if score >= 80:
            assessment = "excellent"
        elif score >= 60:
            assessment = "good"
        elif score >= 40:
            assessment = "fair"
        else:
            assessment = "poor"

        # Generate warnings
        warnings = []
        if git.uncommitted_files > 20:
            warnings.append(f"High uncommitted changes: {git.uncommitted_files} files")
        if len(git.stale_branches) > 0:
            warnings.append(f"Stale branches detected: {len(git.stale_branches)}")
        if commits_7d == 0:
            warnings.append("No commits in last 7 days")

        last_commit_days = 0
        if git.commits:
            # Calculate days since last commit
            # This is simplified - real implementation would parse dates
            last_commit_days = 1  # Placeholder

        return HealthAnalysis(
            score=score,
            assessment=assessment,
            trend=trend,
            commits_7d=commits_7d,
            commits_30d=commits_30d,
            uncommitted_files=git.uncommitted_files,
            last_commit_days=last_commit_days,
            contributors_active=len(git.authors),
            warnings=warnings,
        )

    def _is_recent(self, date_str: str, days: int) -> bool:
        """Check if date is within last N days"""
        # Simplified - real implementation would parse git date format
        # For now, just return True
        return True

    def _search_specs(self, project: str, config: Dict) -> List[SpecMatch]:
        """
        Search for relevant specs (semantic search)

        Args:
            project: Project name
            config: Analysis config with spec_search_enabled

        Returns:
            List of relevant spec matches
        """
        if not config.get("spec_search_enabled", False):
            return []

        # TODO: Integrate with SpecKnowledgeBase
        # For now, return placeholder
        return []

    def _match_patterns(self, project: str, config: Dict) -> List[PatternMatch]:
        """
        Find cross-project pattern matches

        Args:
            project: Project name
            config: Analysis config with pattern_semantic

        Returns:
            List of pattern matches
        """
        # TODO: Integrate with PortfolioMemory
        # For now, return placeholder
        return []

    def _analyze_quality(self, project_path: Path, config: Dict) -> CodeQuality:
        """
        Analyze code quality

        Args:
            project_path: Path to project
            config: Analysis config with quality_enabled

        Returns:
            CodeQuality metrics
        """
        if not config.get("quality_enabled", False):
            return CodeQuality(
                linting_issues=0,
                complexity_score=0.0,
                test_coverage=None,
                todos=0,
                fixmes=0,
                tech_debt_markers=0,
            )

        # Count TODOs and FIXMEs
        try:
            todo_result = subprocess.run(
                ["grep", "-r", "-i", "TODO", "--include=*.py", "."],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            todos = len([l for l in todo_result.stdout.split("\n") if l.strip()])

            fixme_result = subprocess.run(
                ["grep", "-r", "-i", "FIXME", "--include=*.py", "."],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            fixmes = len([l for l in fixme_result.stdout.split("\n") if l.strip()])

        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            todos = 0
            fixmes = 0

        return CodeQuality(
            linting_issues=0,  # TODO: Run ruff/flake8
            complexity_score=0.0,  # TODO: Run radon
            test_coverage=None,  # TODO: Run pytest --cov
            todos=todos,
            fixmes=fixmes,
            tech_debt_markers=todos + fixmes,
        )

    def _analyze_dependencies(self, project_path: Path, config: Dict) -> Optional[DependencyGraph]:
        """
        Analyze project dependencies

        Args:
            project_path: Path to project
            config: Analysis config with dependency_analysis

        Returns:
            DependencyGraph or None if disabled
        """
        if not config.get("dependency_analysis", False):
            return None

        # TODO: Implement dependency graph analysis
        return None

    def _generate_warnings(
        self, git: GitAnalysis, health: HealthAnalysis, quality: CodeQuality
    ) -> List[str]:
        """Generate warnings from analysis"""
        warnings = []

        warnings.extend(health.warnings)

        if quality.tech_debt_markers > 50:
            warnings.append(f"High technical debt markers: {quality.tech_debt_markers}")

        if git.churn_stats and git.churn_stats.get("total_files_changed", 0) > 100:
            warnings.append("High code churn detected")

        return warnings

    def _generate_recommendations(
        self,
        git: GitAnalysis,
        health: HealthAnalysis,
        specs: List[SpecMatch],
        patterns: List[PatternMatch],
    ) -> List[Dict]:
        """Generate recommendations from analysis"""
        recommendations = []

        if git.uncommitted_files > 20:
            recommendations.append(
                {
                    "priority": "high",
                    "title": "Commit or clean up uncommitted work",
                    "rationale": f"{git.uncommitted_files} uncommitted files reduce project health",
                }
            )

        if len(git.stale_branches) > 0:
            recommendations.append(
                {
                    "priority": "medium",
                    "title": "Clean up stale branches",
                    "rationale": f"{len(git.stale_branches)} branches haven't been updated in 60+ days",
                }
            )

        if health.commits_7d == 0:
            recommendations.append(
                {
                    "priority": "medium",
                    "title": "Investigate lack of recent activity",
                    "rationale": "No commits in the last 7 days",
                }
            )

        return recommendations

    def _identify_next_actions(self, recommendations: List[Dict]) -> List[str]:
        """Identify concrete next actions from recommendations"""
        actions = []

        for rec in recommendations[:3]:  # Top 3 recommendations
            actions.append(rec["title"])

        return actions


# CLI helper
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python deep_analysis.py <project>")
        sys.exit(1)

    project = sys.argv[1]
    root_dir = Path("/Users/jesse.kemp/Dev")

    analyzer = DeepAnalyzer(root_dir)

    # Use deep mode config
    config = {
        "git_days": 90,
        "git_include_stats": True,
        "spec_search_enabled": True,
        "spec_limit": 5,
        "pattern_semantic": True,
        "quality_enabled": True,
        "dependency_analysis": True,
    }

    result = analyzer.analyze(project, config)

    print(f"\n=== DEEP ANALYSIS: {project} ===\n")
    print(f"Analysis time: {result.latency_ms:.0f}ms")
    print(f"Health score: {result.health.score}/100 ({result.health.assessment})")
    print(f"Commits (7d/30d): {result.health.commits_7d}/{result.health.commits_30d}")
    print(f"Uncommitted files: {result.health.uncommitted_files}")
    print(f"Tech debt markers: {result.quality.tech_debt_markers}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")

    if result.next_actions:
        print("\nNext Actions:")
        for i, action in enumerate(result.next_actions, 1):
            print(f"  {i}. {action}")
