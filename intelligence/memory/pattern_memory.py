#!/usr/bin/env python3
"""
Pattern Memory API - High-level interface for pattern recognition.

Layer 2 of Cortex Intelligence Stack: Pattern Memory.

Provides:
- find_similar_solutions() - Find similar work from other projects
- get_relevant_patterns() - Get patterns for current context
- suggest_from_history() - Suggest next steps based on past patterns
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Add cortex to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from intelligence.memory.pattern_indexer import (
    Pattern,
    PatternIndexer,
    PatternSearcher,
)


@dataclass
class SimilarWork:
    """Similar work found in other projects."""

    project: str
    title: str
    description: str
    pattern_type: str
    files_changed: List[str]
    relevance_score: float
    commit_hash: str

    def to_compact_str(self, max_length: int = 100) -> str:
        """Convert to compact string for display."""
        text = f"[{self.project}] {self.title}"
        if len(text) > max_length:
            text = text[: max_length - 3] + "..."
        return text

    def to_suggestion(self) -> str:
        """Convert to actionable suggestion."""
        files_summary = ", ".join(self.files_changed[:3])
        if len(self.files_changed) > 3:
            files_summary += f" (+ {len(self.files_changed) - 3} more)"

        return f"Similar work in {self.project}: {self.title}\n  Modified: {files_summary}\n  Commit: {self.commit_hash[:8]}"


class PatternMemory:
    """High-level API for pattern recognition and memory."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")

        self.root_dir = root_dir
        self.indexer = PatternIndexer(root_dir)

        # Load cached patterns
        self.patterns = self.indexer.load_patterns()
        self.searcher = PatternSearcher(self.patterns) if self.patterns else None

    def find_similar_solutions(
        self,
        task: str,
        current_project: str,
        pattern_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[SimilarWork]:
        """
        Find similar solutions from other projects.

        Args:
            task: Description of current task
            current_project: Current project name (to exclude from results)
            pattern_type: Filter by pattern type (fix, feature, etc.)
            limit: Maximum results

        Returns:
            List of similar work from other projects
        """
        if not self.searcher:
            return []

        results = self.searcher.find_similar_work(
            current_project=current_project, task_description=task, limit=limit
        )

        similar_work = []
        for pattern, score in results:
            # Filter by pattern type if specified
            if pattern_type and pattern.pattern_type != pattern_type:
                continue

            similar_work.append(
                SimilarWork(
                    project=pattern.project,
                    title=pattern.title,
                    description=pattern.description,
                    pattern_type=pattern.pattern_type,
                    files_changed=pattern.files_changed,
                    relevance_score=score,
                    commit_hash=pattern.commit_hash,
                )
            )

        return similar_work

    def get_relevant_patterns(self, context: str, limit: int = 10) -> List[SimilarWork]:
        """
        Get relevant patterns for current context.

        Args:
            context: Current context (e.g., file being edited, error message)
            limit: Maximum results

        Returns:
            List of relevant patterns
        """
        if not self.searcher:
            return []

        results = self.searcher.search(context, limit=limit)

        patterns = []
        for pattern, score in results:
            patterns.append(
                SimilarWork(
                    project=pattern.project,
                    title=pattern.title,
                    description=pattern.description,
                    pattern_type=pattern.pattern_type,
                    files_changed=pattern.files_changed,
                    relevance_score=score,
                    commit_hash=pattern.commit_hash,
                )
            )

        return patterns

    def suggest_from_history(self, task: str, current_project: str, limit: int = 3) -> List[str]:
        """
        Suggest next steps based on past patterns.

        Args:
            task: Description of current task
            current_project: Current project name
            limit: Maximum suggestions

        Returns:
            List of actionable suggestions
        """
        similar_work = self.find_similar_solutions(
            task=task, current_project=current_project, limit=limit
        )

        suggestions = []
        for work in similar_work:
            suggestion = f"We solved this before in {work.project}:\n"
            suggestion += f"  {work.title}\n"

            if work.files_changed:
                files = ", ".join(work.files_changed[:3])
                if len(work.files_changed) > 3:
                    files += f" (+ {len(work.files_changed) - 3} more)"
                suggestion += f"  Modified: {files}\n"

            suggestion += f"  Pattern: {work.pattern_type}\n"
            suggestion += f"  Relevance: {int(work.relevance_score * 100)}%"

            suggestions.append(suggestion)

        return suggestions

    def reindex(self, since_months: int = 6):
        """
        Reindex all projects.

        Args:
            since_months: Only index commits from last N months
        """
        # Find all git repos
        git_repos = self._find_git_repos()

        print(f"Reindexing {len(git_repos)} projects...")

        # Index all projects
        all_patterns = self.indexer.index_all_projects(git_repos, since_months=since_months)

        # Save to cache
        self.indexer.save_patterns(all_patterns)

        # Reload patterns
        self.patterns = self.indexer.load_patterns()
        self.searcher = PatternSearcher(self.patterns)

        total = sum(len(patterns) for patterns in all_patterns.values())
        print(f"Indexed {total} patterns from {len(git_repos)} projects")

    def _find_git_repos(self) -> List[Path]:
        """Find all git repositories in root directory."""
        git_repos = []

        # Check root level
        for path in self.root_dir.iterdir():
            if path.is_dir() and (path / ".git").exists():
                git_repos.append(path)

        # Check one level deep
        for path in self.root_dir.iterdir():
            if path.is_dir() and not (path / ".git").exists():
                try:
                    for subpath in path.iterdir():
                        if subpath.is_dir() and (subpath / ".git").exists():
                            git_repos.append(subpath)
                except PermissionError:
                    pass

        return git_repos

    def get_stats(self) -> dict:
        """Get pattern memory statistics."""
        if not self.patterns:
            return {
                "total_patterns": 0,
                "projects": 0,
                "pattern_types": {},
                "cache_exists": False,
            }

        # Count by project
        projects = set(p.project for p in self.patterns)

        # Count by pattern type
        pattern_types = {}
        for p in self.patterns:
            pattern_types[p.pattern_type] = pattern_types.get(p.pattern_type, 0) + 1

        return {
            "total_patterns": len(self.patterns),
            "projects": len(projects),
            "pattern_types": pattern_types,
            "cache_exists": True,
            "cache_path": str(self.indexer.cache_dir / "patterns.json"),
        }


def main():
    """CLI for testing pattern memory."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pattern_memory.py <command> [args]")
        print("\nCommands:")
        print("  reindex              - Reindex all projects")
        print("  search <query>       - Search for patterns")
        print("  suggest <task>       - Get suggestions from history")
        print("  stats                - Show pattern memory statistics")
        return

    command = sys.argv[1]
    memory = PatternMemory()

    if command == "reindex":
        memory.reindex()

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python pattern_memory.py search <query>")
            return

        query = " ".join(sys.argv[2:])
        patterns = memory.get_relevant_patterns(query, limit=10)

        print(f"Search: '{query}'")
        print(f"Found {len(patterns)} relevant patterns\n")

        for pattern in patterns:
            print(f"[{pattern.relevance_score:.2f}] {pattern.project} - {pattern.title}")
            print(f"      Type: {pattern.pattern_type}")
            if pattern.files_changed:
                files = ", ".join(pattern.files_changed[:3])
                if len(pattern.files_changed) > 3:
                    files += "..."
                print(f"      Files: {files}")
            print()

    elif command == "suggest":
        if len(sys.argv) < 3:
            print("Usage: python pattern_memory.py suggest <task>")
            return

        task = " ".join(sys.argv[2:])
        current_project = Path.cwd().name

        suggestions = memory.suggest_from_history(task, current_project, limit=5)

        print(f"Task: '{task}'")
        print(f"Current project: {current_project}")
        print(f"\nSuggestions from pattern history:\n")

        if not suggestions:
            print("No similar patterns found. Try reindexing first.")
        else:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}\n")

    elif command == "stats":
        stats = memory.get_stats()

        print("Pattern Memory Statistics")
        print("=" * 40)
        print(f"Total patterns: {stats['total_patterns']}")
        print(f"Projects indexed: {stats['projects']}")
        print(f"Cache exists: {stats['cache_exists']}")

        if stats["cache_exists"]:
            print(f"Cache path: {stats['cache_path']}")

        if stats["pattern_types"]:
            print("\nPattern types:")
            for ptype, count in sorted(
                stats["pattern_types"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {ptype}: {count}")


if __name__ == "__main__":
    main()
