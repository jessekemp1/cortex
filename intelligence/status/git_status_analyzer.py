#!/usr/bin/env python3
"""
GitStatusAnalyzer - Intelligent git status analysis using Cortex intelligence.

Provides semantic grouping of uncommitted changes based on:
- File patterns and project structure
- Historical commit patterns
- Dependency relationships
- Best practices (tests with code, docs with features)
"""

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class ChangeGroup:
    """A semantically related group of file changes."""

    name: str
    files: List[str]
    change_type: str  # bug_fix, feature, refactor, chore, data_update
    project: str  # alpha_arena, cortex, vortex, etc.
    confidence: float  # 0.0 to 1.0
    should_commit: str  # "now", "after_tests", "bulk", "maybe"
    suggested_message: str
    related_files: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high


@dataclass
class CommitSuggestion:
    """A suggested commit with full context."""

    priority: int  # 1 = highest
    group: ChangeGroup
    reasoning: str
    blockers: List[str] = field(default_factory=list)


class GitStatusAnalyzer:
    """Intelligent git status analysis using Cortex intelligence."""

    # Project detection patterns
    PROJECT_PATTERNS = {
        "alpha_arena": r"^alpha_arena/",
        "cortex": r"^cortex/",
        "vortex": r"^Vortex/VortexV2/",
        "dj_copilot": r"^DJ-CoPilot/",
        "kempion_site": r"^kempion-research-site",
    }

    # File type categorization
    FILE_CATEGORIES = {
        "source_code": [".py", ".js", ".ts", ".tsx", ".jsx"],
        "tests": ["/test_", "/tests/", "_test.py"],
        "docs": [".md", "/docs/"],
        "config": [".json", ".yaml", ".yml", ".toml", ".ini"],
        "data": [".parquet", ".csv", ".jsonl"],
    }

    # Conventional commit types
    COMMIT_TYPES = {
        "feat": ["add", "implement", "create", "new"],
        "fix": ["fix", "resolve", "correct", "patch"],
        "refactor": ["refactor", "restructure", "reorganize"],
        "chore": ["update", "cleanup", "remove", "delete"],
        "docs": ["document", "readme", "guide"],
        "test": ["test", "spec", "coverage"],
    }

    def __init__(self, repo_path: Path):
        """
        Initialize analyzer for a git repository.

        Args:
            repo_path: Path to git repository root
        """
        self.repo_path = Path(repo_path)
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

    def analyze_uncommitted_changes(self) -> Dict[str, ChangeGroup]:
        """
        Group uncommitted changes intelligently.

        Returns:
            Dict of group_id -> ChangeGroup
        """
        # Get all uncommitted changes
        modified, deleted, untracked = self._get_git_status()

        # Group files by project and semantic meaning
        groups = self._group_files_semantically(modified, deleted, untracked)

        # Enhance groups with intelligence
        for group_id, group in groups.items():
            self._enhance_group_with_patterns(group, modified, deleted, untracked)

        return groups

    def suggest_commit_sequence(
        self, change_groups: Dict[str, ChangeGroup]
    ) -> List[CommitSuggestion]:
        """
        Generate ordered list of suggested commits.

        Args:
            change_groups: Dict of group_id -> ChangeGroup

        Returns:
            Ordered list of CommitSuggestion (highest priority first)
        """
        suggestions = []

        for group_id, group in change_groups.items():
            # Calculate priority based on confidence, risk, and readiness
            priority = self._calculate_priority(group)

            # Generate reasoning
            reasoning = self._generate_reasoning(group)

            # Check for blockers
            blockers = self._check_blockers(group)

            suggestions.append(
                CommitSuggestion(
                    priority=priority, group=group, reasoning=reasoning, blockers=blockers
                )
            )

        # Sort by priority (lowest number = highest priority)
        suggestions.sort(key=lambda s: s.priority)

        return suggestions

    def _get_git_status(self) -> Tuple[List[str], List[str], List[str]]:
        """Get modified, deleted, and untracked files."""
        # Get modified and deleted files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        modified = [f for f in result.stdout.strip().split("\n") if f]

        # Get deleted files
        result = subprocess.run(
            ["git", "ls-files", "--deleted"], cwd=self.repo_path, capture_output=True, text=True
        )
        deleted = [f for f in result.stdout.strip().split("\n") if f]

        # Get untracked files
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        untracked = [f for f in result.stdout.strip().split("\n") if f]

        return modified, deleted, untracked

    def _group_files_semantically(
        self, modified: List[str], deleted: List[str], untracked: List[str]
    ) -> Dict[str, ChangeGroup]:
        """Group files by semantic meaning."""
        groups = {}

        all_files = modified + deleted + untracked

        # Group by project
        by_project = defaultdict(list)
        for f in all_files:
            project = self._detect_project(f)
            by_project[project].append(f)

        # Within each project, group by change type
        for project, files in by_project.items():
            project_groups = self._group_project_files(project, files, deleted, untracked)
            groups.update(project_groups)

        return groups

    def _detect_project(self, filepath: str) -> str:
        """Detect which project a file belongs to."""
        for project, pattern in self.PROJECT_PATTERNS.items():
            if re.match(pattern, filepath):
                return project
        return "root"

    def _group_project_files(
        self, project: str, files: List[str], deleted: List[str], untracked: List[str]
    ) -> Dict[str, ChangeGroup]:
        """Group files within a project."""
        groups = {}

        # Special handling for specific patterns

        # 1. Bulk metadata files (DJ-CoPilot loops)
        if project == "dj_copilot":
            loop_files = [f for f in files if "loops/loops/" in f and f.endswith("_metadata.json")]
            if len(loop_files) > 50:  # Bulk import
                group_id = f"{project}_bulk_metadata"
                groups[group_id] = ChangeGroup(
                    name=f"DJ-CoPilot Bulk Metadata Import ({len(loop_files)} files)",
                    files=loop_files,
                    change_type="feat",
                    project=project,
                    confidence=0.99,
                    should_commit="bulk",
                    suggested_message=f"feat(DJ-CoPilot): Add {len(loop_files)} new loop metadata files",
                    risk_level="low",
                )
                # Remove from files list
                files = [f for f in files if f not in loop_files]

        # 2. Documentation cleanup (deleted .md files)
        deleted_docs = [f for f in deleted if f.endswith(".md") and f in files]
        if len(deleted_docs) > 3:
            group_id = f"{project}_doc_cleanup"
            groups[group_id] = ChangeGroup(
                name=f"{project.title()} Documentation Cleanup",
                files=deleted_docs,
                change_type="chore",
                project=project,
                confidence=0.95,
                should_commit="now",
                suggested_message=f"chore({project}): Archive outdated documentation",
                risk_level="low",
            )
            files = [f for f in files if f not in deleted_docs]

        # 3. UI changes (single file, no deps)
        ui_files = [f for f in files if "/ui/" in f and f.endswith(".py")]
        if ui_files and project == "alpha_arena":
            for ui_file in ui_files:
                group_id = f"{project}_ui_fix"
                # Check if this is the only file
                if len([f for f in files if f.startswith(str(Path(ui_file).parent))]) == 1:
                    groups[group_id] = ChangeGroup(
                        name=f"Alpha Arena UI Fix ({Path(ui_file).name})",
                        files=[ui_file],
                        change_type="fix",
                        project=project,
                        confidence=0.95,
                        should_commit="now",
                        suggested_message=f"fix(ui): Update {Path(ui_file).stem}",
                        risk_level="low",
                    )
                    files = [f for f in files if f != ui_file]

        # 4. API changes with tests
        api_files = [f for f in files if "/api/" in f and f.endswith(".py")]
        if api_files and project == "vortex":
            test_files = [f for f in files if "/test" in f and any(api in f for api in api_files)]
            group_id = f"{project}_api_changes"
            groups[group_id] = ChangeGroup(
                name=f"VortexV2 API Changes ({len(api_files)} files)",
                files=api_files + test_files,
                change_type="feat",
                project=project,
                confidence=0.87,
                should_commit="after_tests",
                suggested_message="feat(vortex): Add V2a validation API endpoints",
                related_files=test_files,
                missing_files=[] if test_files else ["tests/unit/test_validation_v2a.py"],
                warnings=[] if test_files else ["API changes typically include test files"],
                risk_level="medium" if not test_files else "low",
            )
            files = [f for f in files if f not in api_files and f not in test_files]

        # 5. Runtime data (portfolio files, logs)
        data_files = [
            f for f in files if any(p in f for p in ["data/", "portfolio", "competition_log"])
        ]
        if data_files and project == "alpha_arena":
            group_id = f"{project}_runtime_data"
            groups[group_id] = ChangeGroup(
                name="Alpha Arena Runtime Data",
                files=data_files,
                change_type="data_update",
                project=project,
                confidence=0.92,
                should_commit="maybe",
                suggested_message="data(alpha_arena): Update portfolio positions",
                warnings=["Runtime data typically not committed"],
                risk_level="low",
            )
            files = [f for f in files if f not in data_files]

        # 6. Config/Claude files (.claude commands, memories, CLAUDE.md)
        config_files = [f for f in files if ".claude/" in f or f.endswith("CLAUDE.md")]
        if config_files:
            group_id = f"{project}_config_updates"
            groups[group_id] = ChangeGroup(
                name="Configuration Updates",
                files=config_files,
                change_type="chore",
                project=project,
                confidence=0.88,
                should_commit="now",
                suggested_message=f"chore({project}): Update configuration and memories",
                risk_level="low",
            )
            files = [f for f in files if f not in config_files]

        # 7. Remaining files (catch-all)
        if files:
            group_id = f"{project}_misc_changes"
            groups[group_id] = ChangeGroup(
                name=f"{project.title()} Miscellaneous Changes",
                files=files,
                change_type="refactor",
                project=project,
                confidence=0.60,
                should_commit="review",
                suggested_message=f"refactor({project}): Update project files",
                warnings=["Please review these changes manually"],
                risk_level="medium",
            )

        return groups

    def _enhance_group_with_patterns(
        self, group: ChangeGroup, modified: List[str], deleted: List[str], untracked: List[str]
    ):
        """Enhance group with pattern-based intelligence."""
        # Check for missing test files if source code changed
        if group.change_type in ["feat", "fix", "refactor"]:
            source_files = [
                f
                for f in group.files
                if any(f.endswith(ext) for ext in self.FILE_CATEGORIES["source_code"])
            ]
            if source_files:
                test_files = [
                    f
                    for f in group.files
                    if any(pattern in f for pattern in self.FILE_CATEGORIES["tests"])
                ]
                if not test_files and "/test" not in str(group.files):
                    group.warnings.append("Source code changes without test file updates")
                    group.risk_level = "medium"

    def _calculate_priority(self, group: ChangeGroup) -> int:
        """Calculate priority (1=highest, 10=lowest)."""
        # High priority: High confidence + "now" + low risk
        if group.should_commit == "now" and group.confidence > 0.9 and group.risk_level == "low":
            return 1

        # Medium priority: Bulk commits, chores
        if group.should_commit == "bulk" or group.change_type == "chore":
            return 2

        # Lower priority: Needs tests or review
        if group.should_commit in ["after_tests", "review"]:
            return 5

        # Lowest priority: Maybe/uncertain
        if group.should_commit == "maybe":
            return 8

        return 5  # Default medium priority

    def _generate_reasoning(self, group: ChangeGroup) -> str:
        """Generate human-readable reasoning for suggestion."""
        reasons = []

        # Confidence reasoning
        if group.confidence > 0.9:
            reasons.append("High confidence grouping")
        elif group.confidence < 0.7:
            reasons.append("Manual review recommended")

        # Risk reasoning
        if group.risk_level == "low" and not group.warnings:
            reasons.append("Safe to commit")
        elif group.warnings:
            reasons.append(f"⚠️ {len(group.warnings)} warning(s)")

        # Pattern reasoning
        if group.change_type == "feat" and group.related_files:
            reasons.append(f"Includes {len(group.related_files)} related test files")

        if not reasons:
            reasons.append("Standard change group")

        return " • ".join(reasons)

    def _check_blockers(self, group: ChangeGroup) -> List[str]:
        """Check for blockers preventing commit."""
        blockers = []

        if group.missing_files:
            blockers.append(f"Missing expected files: {', '.join(group.missing_files)}")

        if group.risk_level == "high":
            blockers.append("High risk - manual review required")

        if group.should_commit == "after_tests":
            blockers.append("Run tests before committing")

        return blockers


def main():
    """CLI entry point for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: git_status_analyzer.py <repo_path>")
        sys.exit(1)

    repo_path = Path(sys.argv[1])
    analyzer = GitStatusAnalyzer(repo_path)

    print(f"🔍 Analyzing: {repo_path}\n")

    groups = analyzer.analyze_uncommitted_changes()
    suggestions = analyzer.suggest_commit_sequence(groups)

    print(f"📊 Found {len(groups)} change groups:\n")

    for i, suggestion in enumerate(suggestions, 1):
        group = suggestion.group
        print(f"{i}. [{group.project}] {group.name}")
        print(
            f"   Type: {group.change_type} | Confidence: {group.confidence:.0%} | Risk: {group.risk_level}"
        )
        print(f"   Files: {len(group.files)}")
        print(f"   Suggested: {group.suggested_message}")
        print(f"   Reasoning: {suggestion.reasoning}")
        if suggestion.blockers:
            print(f"   ⚠️ Blockers: {'; '.join(suggestion.blockers)}")
        print()


if __name__ == "__main__":
    main()
