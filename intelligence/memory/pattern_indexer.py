#!/usr/bin/env python3
"""
Pattern Indexer - Extract and index successful patterns from git history.

Layer 2 of Cortex Intelligence Stack: Pattern Memory.

Capabilities:
- Index commits across all projects
- Extract patterns (fixes, implementations, solutions)
- Keyword-based similarity search
- Cross-project pattern recognition
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class Pattern:
    """A successful pattern extracted from git history."""

    id: str  # Unique identifier (project:commit_hash)
    project: str
    commit_hash: str
    commit_date: datetime
    title: str
    description: str
    files_changed: List[str]
    keywords: Set[str] = field(default_factory=set)
    pattern_type: str = "unknown"  # fix, feature, refactor, test, docs

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project": self.project,
            "commit_hash": self.commit_hash,
            "commit_date": self.commit_date.isoformat(),
            "title": self.title,
            "description": self.description,
            "files_changed": self.files_changed,
            "keywords": list(self.keywords),
            "pattern_type": self.pattern_type,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Pattern":
        """Create Pattern from dictionary."""
        return cls(
            id=data["id"],
            project=data["project"],
            commit_hash=data["commit_hash"],
            commit_date=datetime.fromisoformat(data["commit_date"]),
            title=data["title"],
            description=data["description"],
            files_changed=data["files_changed"],
            keywords=set(data.get("keywords", [])),
            pattern_type=data.get("pattern_type", "unknown"),
        )


class PatternIndexer:
    """Index patterns from git history across projects."""

    def __init__(self, root_dir: Path, cache_dir: Optional[Path] = None):
        self.root_dir = Path(root_dir)
        if cache_dir is None:
            cache_dir = Path.home() / ".cortex" / "patterns"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Pattern type detection rules
        self.pattern_rules = {
            "fix": ["fix", "bug", "error", "issue", "resolve", "patch"],
            "feature": ["add", "implement", "create", "new", "feature"],
            "refactor": ["refactor", "cleanup", "simplify", "improve", "optimize"],
            "test": ["test", "testing", "coverage", "spec"],
            "docs": ["docs", "documentation", "readme", "comment"],
            "security": ["security", "auth", "vulnerability", "cve"],
            "performance": ["performance", "optimize", "speed", "cache"],
        }

        # Stop words for keyword extraction
        self.stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "up", "about", "into", "through", "during",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "should", "could", "may", "might",
            "this", "that", "these", "those", "it", "its", "as", "if", "when", "where",
        }

    def index_project(
        self, project_path: Path, since_months: int = 6, max_commits: int = 200
    ) -> List[Pattern]:
        """
        Index patterns from a project's git history.

        Args:
            project_path: Path to project directory
            since_months: Only index commits from last N months
            max_commits: Maximum commits to process

        Returns:
            List of extracted patterns
        """
        project_path = Path(project_path).resolve()
        project_name = project_path.name

        patterns = []

        try:
            # Get git log with commit details
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--since={since_months}.months",
                    f"--max-count={max_commits}",
                    "--pretty=format:%H|%ai|%s|%b",
                    "--name-only",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return patterns

            # Parse commits
            commits = self._parse_git_log(result.stdout)

            for commit in commits:
                # Skip merge commits
                if commit["title"].lower().startswith("merge"):
                    continue

                # Skip trivial commits
                if self._is_trivial_commit(commit["title"]):
                    continue

                # Extract pattern
                pattern = self._extract_pattern(project_name, commit)
                if pattern:
                    patterns.append(pattern)

        except Exception:
            pass

        return patterns

    def _parse_git_log(self, log_output: str) -> List[Dict]:
        """Parse git log output into structured commits."""
        commits = []
        current_commit = None
        files = []

        for line in log_output.split("\n"):
            line = line.strip()

            if not line:
                # Empty line separates commits
                if current_commit and current_commit.get("hash"):
                    current_commit["files"] = files
                    commits.append(current_commit)
                current_commit = None
                files = []
                continue

            if "|" in line:
                # Commit header: hash|date|title|description
                parts = line.split("|", 3)
                if len(parts) >= 3:
                    current_commit = {
                        "hash": parts[0],
                        "date": parts[1],
                        "title": parts[2],
                        "description": parts[3] if len(parts) > 3 else "",
                    }
            elif current_commit:
                # File path
                files.append(line)

        # Add last commit
        if current_commit and current_commit.get("hash"):
            current_commit["files"] = files
            commits.append(current_commit)

        return commits

    def _is_trivial_commit(self, title: str) -> bool:
        """Check if commit is trivial (formatting, typos, etc.)."""
        title_lower = title.lower()

        # Trivial patterns
        trivial_patterns = [
            "typo",
            "whitespace",
            "formatting",
            "update readme",
            "bump version",
            "wip",
            "tmp",
            "minor",
        ]

        return any(pattern in title_lower for pattern in trivial_patterns)

    def _extract_pattern(self, project_name: str, commit: Dict) -> Optional[Pattern]:
        """Extract pattern from commit."""
        # Detect pattern type
        pattern_type = self._detect_pattern_type(commit["title"], commit["description"])

        # Extract keywords
        keywords = self._extract_keywords(commit["title"], commit["description"])

        # Create pattern
        pattern_id = f"{project_name}:{commit['hash'][:8]}"

        try:
            commit_date = datetime.fromisoformat(commit["date"].replace(" ", "T").split("+")[0].split("-")[0])
        except Exception:
            commit_date = datetime.now()

        return Pattern(
            id=pattern_id,
            project=project_name,
            commit_hash=commit["hash"],
            commit_date=commit_date,
            title=commit["title"],
            description=commit["description"],
            files_changed=commit.get("files", []),
            keywords=keywords,
            pattern_type=pattern_type,
        )

    def _detect_pattern_type(self, title: str, description: str) -> str:
        """Detect pattern type from commit message."""
        combined = (title + " " + description).lower()

        # Check each pattern type
        for pattern_type, keywords in self.pattern_rules.items():
            if any(keyword in combined for keyword in keywords):
                return pattern_type

        return "unknown"

    def _extract_keywords(self, title: str, description: str) -> Set[str]:
        """Extract keywords from commit message."""
        combined = title + " " + description

        # Tokenize
        words = re.findall(r"\b[a-z_][a-z0-9_]*\b", combined.lower())

        # Filter stop words and short words
        keywords = {
            word
            for word in words
            if word not in self.stop_words and len(word) > 2
        }

        # Add tech-specific keywords
        tech_keywords = self._extract_tech_keywords(combined)
        keywords.update(tech_keywords)

        return keywords

    def _extract_tech_keywords(self, text: str) -> Set[str]:
        """Extract technology-specific keywords."""
        tech_keywords = set()

        # Common tech terms
        tech_terms = [
            "api", "rest", "graphql", "sql", "postgresql", "redis", "mongodb",
            "fastapi", "flask", "django", "react", "vue", "nextjs",
            "docker", "kubernetes", "aws", "gcp", "azure",
            "auth", "jwt", "oauth", "session",
            "cache", "queue", "pubsub",
            "test", "unittest", "pytest", "jest",
            "ci", "cd", "pipeline",
        ]

        text_lower = text.lower()
        for term in tech_terms:
            if term in text_lower:
                tech_keywords.add(term)

        return tech_keywords

    def index_all_projects(
        self, project_paths: List[Path], since_months: int = 6
    ) -> Dict[str, List[Pattern]]:
        """
        Index patterns from multiple projects.

        Args:
            project_paths: List of project directories
            since_months: Only index commits from last N months

        Returns:
            Dictionary mapping project name to patterns
        """
        all_patterns = {}

        for project_path in project_paths:
            project_name = project_path.name
            patterns = self.index_project(project_path, since_months=since_months)
            all_patterns[project_name] = patterns

        return all_patterns

    def save_patterns(self, patterns: Dict[str, List[Pattern]]):
        """Save patterns to cache."""
        # Flatten patterns
        flat_patterns = []
        for project_patterns in patterns.values():
            flat_patterns.extend([p.to_dict() for p in project_patterns])

        # Save to cache
        cache_file = self.cache_dir / "patterns.json"
        cache_file.write_text(json.dumps(flat_patterns, indent=2))

        # Save metadata
        metadata = {
            "indexed_at": datetime.now().isoformat(),
            "total_patterns": len(flat_patterns),
            "projects": list(patterns.keys()),
        }
        metadata_file = self.cache_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))

    def load_patterns(self) -> List[Pattern]:
        """Load patterns from cache."""
        cache_file = self.cache_dir / "patterns.json"
        if not cache_file.exists():
            return []

        data = json.loads(cache_file.read_text())
        return [Pattern.from_dict(p) for p in data]


class PatternSearcher:
    """Search for similar patterns using keyword matching."""

    def __init__(self, patterns: List[Pattern]):
        self.patterns = patterns

        # Build keyword index
        self.keyword_index: Dict[str, List[Pattern]] = {}
        for pattern in patterns:
            for keyword in pattern.keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                self.keyword_index[keyword].append(pattern)

    def search(
        self,
        query: str,
        pattern_type: Optional[str] = None,
        limit: int = 10,
        min_score: float = 0.1,
    ) -> List[tuple[Pattern, float]]:
        """
        Search for similar patterns.

        Args:
            query: Search query (keywords)
            pattern_type: Filter by pattern type (fix, feature, etc.)
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of (Pattern, score) tuples sorted by score
        """
        # Extract keywords from query
        query_keywords = self._extract_query_keywords(query)

        if not query_keywords:
            return []

        # Score patterns
        scores: Dict[str, float] = {}
        for keyword in query_keywords:
            if keyword in self.keyword_index:
                for pattern in self.keyword_index[keyword]:
                    if pattern.id not in scores:
                        scores[pattern.id] = 0.0
                    scores[pattern.id] += 1.0

        # Normalize scores
        max_score = max(scores.values()) if scores else 1.0
        normalized_scores = {
            pattern_id: score / max_score for pattern_id, score in scores.items()
        }

        # Filter by pattern type
        pattern_map = {p.id: p for p in self.patterns}
        results = []
        for pattern_id, score in normalized_scores.items():
            if score < min_score:
                continue

            pattern = pattern_map.get(pattern_id)
            if not pattern:
                continue

            if pattern_type and pattern.pattern_type != pattern_type:
                continue

            results.append((pattern, score))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def _extract_query_keywords(self, query: str) -> Set[str]:
        """Extract keywords from search query."""
        # Tokenize
        words = re.findall(r"\b[a-z_][a-z0-9_]*\b", query.lower())

        # Filter short words
        keywords = {word for word in words if len(word) > 2}

        return keywords

    def find_similar_work(
        self, current_project: str, task_description: str, limit: int = 5
    ) -> List[tuple[Pattern, float]]:
        """
        Find similar work from other projects.

        Args:
            current_project: Current project name (to exclude from results)
            task_description: Description of current task
            limit: Maximum results

        Returns:
            List of (Pattern, score) tuples from other projects
        """
        results = self.search(task_description, limit=limit * 2)

        # Filter out current project
        filtered = [
            (pattern, score)
            for pattern, score in results
            if pattern.project.lower() != current_project.lower()
        ]

        return filtered[:limit]


def main():
    """CLI for testing pattern indexer."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pattern_indexer.py <command> [args]")
        print("\nCommands:")
        print("  index <project_path>     - Index a single project")
        print("  index-all <root_dir>     - Index all projects in directory")
        print("  search <query>           - Search for patterns")
        return

    command = sys.argv[1]

    if command == "index":
        if len(sys.argv) < 3:
            print("Usage: python pattern_indexer.py index <project_path>")
            return

        project_path = Path(sys.argv[2])
        indexer = PatternIndexer(project_path.parent)
        patterns = indexer.index_project(project_path)

        print(f"Indexed {len(patterns)} patterns from {project_path.name}")
        for pattern in patterns[:10]:
            print(f"  [{pattern.pattern_type}] {pattern.title}")

    elif command == "index-all":
        if len(sys.argv) < 3:
            print("Usage: python pattern_indexer.py index-all <root_dir>")
            return

        root_dir = Path(sys.argv[2])

        # Find all git repos (max depth 2)
        git_repos = []

        # Check root level
        for path in root_dir.iterdir():
            if path.is_dir() and (path / ".git").exists():
                git_repos.append(path)

        # Check one level deep (for projects like Vortex/VortexV2)
        for path in root_dir.iterdir():
            if path.is_dir() and not (path / ".git").exists():
                for subpath in path.iterdir():
                    if subpath.is_dir() and (subpath / ".git").exists():
                        git_repos.append(subpath)

        print(f"Found {len(git_repos)} git repositories")

        indexer = PatternIndexer(root_dir)
        all_patterns = indexer.index_all_projects(git_repos, since_months=6)

        total = sum(len(patterns) for patterns in all_patterns.values())
        print(f"\nIndexed {total} patterns from {len(git_repos)} projects")

        # Save to cache
        indexer.save_patterns(all_patterns)
        print(f"Saved to {indexer.cache_dir / 'patterns.json'}")

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python pattern_indexer.py search <query>")
            return

        query = " ".join(sys.argv[2:])

        # Load patterns
        indexer = PatternIndexer(Path.cwd())
        patterns = indexer.load_patterns()

        if not patterns:
            print("No patterns found. Run 'index-all' first.")
            return

        print(f"Loaded {len(patterns)} patterns")

        searcher = PatternSearcher(patterns)
        results = searcher.search(query, limit=10)

        print(f"\nSearch: '{query}'")
        print(f"Found {len(results)} results\n")

        for pattern, score in results:
            print(f"[{score:.2f}] {pattern.project} - {pattern.title}")
            print(f"      Type: {pattern.pattern_type}")
            print(f"      Keywords: {', '.join(list(pattern.keywords)[:5])}")
            print()


if __name__ == "__main__":
    main()
