#!/usr/bin/env python3
"""
Context Intelligence - Predicts relevant context for Cortex

Integrates with personal-ai-dataset to provide relevant context predictions.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ContextPrediction:
    """A predicted context item that may be relevant."""

    title: str
    context_type: str  # "knowledge_base", "project_docs", "recent_activity"
    confidence: float  # 0.0 - 1.0
    description: str = ""
    rationale: str = ""
    command: str = ""  # Command to access this context
    file_path: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


class ContextIntelligence:
    """Predicts relevant context based on current activity."""

    # Path to personal-ai-dataset
    KNOWLEDGE_BASE_PATH = Path("/Users/jesse.kemp/Dev/personal-ai-dataset")

    # Project documentation patterns
    DOC_PATTERNS = [
        "README.md",
        "CLAUDE.md",
        "ACTION_PLAN.md",
        "docs/",
        "documentation/",
    ]

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir
        self.kb_available = self._check_knowledge_base()

    def _check_knowledge_base(self) -> bool:
        """Check if personal-ai-dataset is available."""
        kb_cli = self.KNOWLEDGE_BASE_PATH / "kb_cli.py"
        return kb_cli.exists()

    def predict_context(
        self,
        current_project: Optional[str] = None,
        current_task: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 5,
        include_cross_project: bool = True,
    ) -> List[ContextPrediction]:
        """
        Predict relevant context for current work with enhanced accuracy.

        Args:
            current_project: Current project name
            current_task: Current task description
            keywords: Additional keywords to search
            limit: Maximum predictions to return
            include_cross_project: Whether to include cross-project context discovery

        Returns:
            List of ContextPrediction objects with improved relevance scoring
        """
        predictions = []

        # Extract keywords from task if not provided
        if current_task and not keywords:
            keywords = self._extract_keywords(current_task, max_keywords=10)

        # 1. Search knowledge base if available
        if self.kb_available:
            kb_results = self._search_knowledge_base(
                project=current_project,
                task=current_task,
                keywords=keywords,
                limit=limit,
            )
            predictions.extend(kb_results)

        # 2. Find relevant project documentation
        if current_project:
            doc_results = self._find_project_docs(current_project)
            predictions.extend(doc_results)

        # 3. Find recent activity context
        recent_results = self._find_recent_context(current_project)
        predictions.extend(recent_results)

        # 4. Cross-project context discovery
        if include_cross_project and keywords:
            cross_project_results = self._find_cross_project_context(
                current_project, keywords
            )
            predictions.extend(cross_project_results)

        # 5. Find CursorRules Context (Explicit or Implicit)
        if (keywords and "cursorrules" in [k.lower() for k in keywords]) or (
            current_task and "rules" in current_task.lower()
        ):
            predictions.extend(self._find_cursorrules_context(current_project))

        # Sort by relevance and deduplicate
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        predictions = self._deduplicate(predictions)

        # Enhance predictions with keyword matching (improved algorithm)
        predictions = self._enhance_predictions_with_keywords(
            predictions, current_task, keywords
        )

        # Fuse context from multiple sources (enhanced deduplication)
        predictions = self._fuse_context(predictions)

        # Re-sort after enhancement
        predictions.sort(key=lambda p: p.confidence, reverse=True)

        return predictions[:limit]

    def _search_knowledge_base(
        self,
        project: Optional[str] = None,
        task: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[ContextPrediction]:
        """Search personal-ai-dataset for relevant context."""
        predictions = []

        if not self.kb_available:
            return predictions

        # Build search query
        search_terms = []
        if project:
            search_terms.append(project)
        if task:
            # Extract key terms from task
            search_terms.extend(self._extract_keywords(task))
        if keywords:
            search_terms.extend(keywords)

        if not search_terms:
            return predictions

        query = " ".join(search_terms[:5])  # Limit query length

        try:
            # Run kb_cli.py search
            result = subprocess.run(
                ["python3", "kb_cli.py", "search", query, "--limit", str(limit)],
                cwd=self.KNOWLEDGE_BASE_PATH,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout:
                # Parse output (assumes JSON or structured output)
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue

                    # Try to parse as JSON first
                    try:
                        item = json.loads(line)
                        predictions.append(
                            ContextPrediction(
                                title=item.get("title", "Knowledge Base Result"),
                                context_type="knowledge_base",
                                confidence=float(item.get("score", 0.7)),
                                description=item.get("snippet", "")[:200],
                                rationale="From personal knowledge base search",
                                command=f"kb search '{query}'",
                                file_path=item.get("path"),
                                keywords=search_terms,
                            )
                        )
                    except json.JSONDecodeError:
                        # Plain text result
                        if len(line) > 10:
                            predictions.append(
                                ContextPrediction(
                                    title=line[:100],
                                    context_type="knowledge_base",
                                    confidence=0.6,
                                    description=line[:200],
                                    rationale="From personal knowledge base",
                                    command=f"kb search '{query}'",
                                    keywords=search_terms,
                                )
                            )

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # Silently fail - context is optional
            pass

        return predictions

    def _find_project_docs(self, project: str) -> List[ContextPrediction]:
        """Find relevant documentation for a project."""
        predictions = []

        # Find project directory
        project_path = self._find_project_path(project)
        if not project_path:
            return predictions

        # Look for documentation files
        for pattern in self.DOC_PATTERNS:
            if pattern.endswith("/"):
                # Directory pattern
                doc_dir = project_path / pattern.rstrip("/")
                if doc_dir.exists() and doc_dir.is_dir():
                    for doc_file in doc_dir.glob("*.md"):
                        predictions.append(
                            self._create_doc_prediction(doc_file, project)
                        )
            else:
                # File pattern
                doc_file = project_path / pattern
                if doc_file.exists():
                    predictions.append(self._create_doc_prediction(doc_file, project))

        return predictions[:3]  # Limit to 3 docs per project

    def _create_doc_prediction(self, doc_path: Path, project: str) -> ContextPrediction:
        """Create a context prediction from a documentation file."""
        try:
            content = doc_path.read_text()[:500]
            # Extract first meaningful line as snippet
            lines = [
                l.strip()
                for l in content.split("\n")
                if l.strip() and not l.startswith("#")
            ]
            snippet = lines[0] if lines else ""
        except Exception:
            snippet = ""

        return ContextPrediction(
            title=f"{project}/{doc_path.name}",
            context_type="project_docs",
            confidence=0.8 if doc_path.name in ["README.md", "CLAUDE.md"] else 0.6,
            description=snippet[:200],
            rationale=f"Project documentation for {project}",
            command=f"cat {doc_path}",
            file_path=str(doc_path),
            keywords=[project, doc_path.stem],
        )

    def _find_recent_context(
        self, project: Optional[str] = None
    ) -> List[ContextPrediction]:
        """Find context from recent git activity."""
        predictions = []

        if project:
            project_path = self._find_project_path(project)
            if project_path:
                predictions.extend(
                    self._get_recent_commits_context(project_path, project)
                )

        # Also check ACTION_PLAN.md for recent context
        action_plan = self.root_dir / "ACTION_PLAN.md"
        if action_plan.exists():
            predictions.append(
                ContextPrediction(
                    title="ACTION_PLAN.md - Current priorities",
                    context_type="recent_activity",
                    confidence=0.9,
                    description="Repository action plan with current goals and priorities",
                    rationale="Contains your current strategic goals and priorities",
                    command=f"cat {action_plan}",
                    file_path=str(action_plan),
                    keywords=["goals", "priorities", "action plan"],
                )
            )

        return predictions

    def _get_recent_commits_context(
        self, project_path: Path, project: str
    ) -> List[ContextPrediction]:
        """Get context from recent commits."""
        predictions = []

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-5", "--format=%s"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout:
                commits = result.stdout.strip().split("\n")
                if commits and commits[0]:
                    predictions.append(
                        ContextPrediction(
                            title=f"Recent {project} commits",
                            context_type="recent_activity",
                            confidence=0.7,
                            description="; ".join(commits[:3]),
                            rationale=f"Recent development activity in {project}",
                            command=f"git -C {project_path} log --oneline -5",
                            file_path=str(project_path),
                            keywords=[project, "commits", "recent"],
                        )
                    )

        except Exception:
            pass

        return predictions

    def _find_cursorrules_context(
        self, project_name: Optional[str]
    ) -> List[ContextPrediction]:
        """Find CursorRules specific context."""
        predictions = []
        if not project_name:
            return predictions

        project_path = self._find_project_path(project_name)
        if not project_path:
            return predictions

        try:
            # Lazy import to avoid circular dependencies
            from cortex.ai_intelligence import ProjectScanner

            scanner = ProjectScanner(self.root_dir)

            # Use the new scoring method
            score, missing = scanner._score_cursorrules(project_path)

            predictions.append(
                ContextPrediction(
                    title=f"CursorRules Status: {project_name} (Score: {score:.0f})",
                    context_type="cursorrules",
                    confidence=1.0,
                    description=f"Score: {score}/100. Missing patterns: {', '.join(missing) if missing else 'None'}.",
                    rationale="Current CursorRules configuration state",
                    command="cortex scan (internal)",
                    file_path=str(project_path / ".cursorrules"),
                    keywords=["cursorrules", "rules", "ai context"],
                )
            )

            # If missing patterns, suggest them
            if missing:
                for pattern in missing:
                    predictions.append(
                        ContextPrediction(
                            title=f"Missing Rule: {pattern}",
                            context_type="cursorrules_gap",
                            confidence=0.9,
                            description=f"Project needs {pattern} rules but they are missing.",
                            rationale=f"Detected {pattern} usage but no corresponding .mdc rule found.",
                            command="trigger cursorrules_enhancer",
                            keywords=["missing", pattern],
                        )
                    )

        except ImportError:
            pass
        except Exception:
            pass

        return predictions

    def _find_cross_project_context(
        self,
        current_project: Optional[str],
        keywords: List[str]
    ) -> List[ContextPrediction]:
        """
        Find relevant context from other projects based on keywords.
        
        Args:
            current_project: Current project name (to exclude)
            keywords: Keywords to search for
            
        Returns:
            List of context predictions from other projects
        """
        predictions = []
        
        if not keywords:
            return predictions
        
        # Search other projects for relevant documentation
        for item in self.root_dir.iterdir():
            if not item.is_dir() or item.name == current_project:
                continue
            
            # Check if project has relevant documentation
            for doc_pattern in self.DOC_PATTERNS:
                if doc_pattern.endswith("/"):
                    doc_dir = item / doc_pattern.rstrip("/")
                    if doc_dir.exists():
                        # Search doc files for keywords
                        for doc_file in doc_dir.glob("*.md"):
                            try:
                                content = doc_file.read_text().lower()
                                # Check if any keywords appear in content
                                keyword_matches = sum(
                                    1 for kw in keywords if kw.lower() in content
                                )
                                if keyword_matches > 0:
                                    # Calculate relevance based on keyword matches
                                    relevance = min(keyword_matches / len(keywords), 1.0)
                                    predictions.append(
                                        ContextPrediction(
                                            title=f"{item.name}/{doc_file.name}",
                                            context_type="cross_project_docs",
                                            confidence=0.5 + (relevance * 0.3),  # 0.5-0.8 range
                                            description=f"Documentation from {item.name} project",
                                            rationale=f"Contains {keyword_matches} matching keywords",
                                            command=f"cat {doc_file}",
                                            file_path=str(doc_file),
                                            keywords=keywords[:5],
                                        )
                                    )
                            except Exception:
                                pass
                else:
                    doc_file = item / doc_pattern
                    if doc_file.exists():
                        try:
                            content = doc_file.read_text().lower()
                            keyword_matches = sum(
                                1 for kw in keywords if kw.lower() in content
                            )
                            if keyword_matches > 0:
                                relevance = min(keyword_matches / len(keywords), 1.0)
                                predictions.append(
                                    ContextPrediction(
                                        title=f"{item.name}/{doc_file.name}",
                                        context_type="cross_project_docs",
                                        confidence=0.5 + (relevance * 0.3),
                                        description=f"Documentation from {item.name} project",
                                        rationale=f"Contains {keyword_matches} matching keywords",
                                        command=f"cat {doc_file}",
                                        file_path=str(doc_file),
                                        keywords=keywords[:5],
                                    )
                                )
                        except Exception:
                            pass
        
        return predictions[:5]  # Limit cross-project results

    def _find_project_path(self, project: str) -> Optional[Path]:
        """Find project directory path."""
        # Direct match
        direct = self.root_dir / project
        if direct.exists():
            return direct

        # Case-insensitive search
        for item in self.root_dir.iterdir():
            if item.is_dir() and item.name.lower() == project.lower():
                return item

        # Check nested paths (e.g., Vortex/VortexV2)
        for parent in self.root_dir.iterdir():
            if parent.is_dir():
                nested = parent / project
                if nested.exists():
                    return nested

        return None

    def extract_keywords_from_commits(
        self, project_path: Path, limit: int = 10
    ) -> List[str]:
        """
        Extract keywords from recent commit messages.

        Args:
            project_path: Path to project directory
            limit: Number of recent commits to analyze

        Returns:
            List of extracted keywords
        """
        keywords = []
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--format=%s %b"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout:
                commit_messages = result.stdout.strip()
                keywords = self._extract_keywords(commit_messages)
        except Exception:
            pass

        return keywords[:limit]

    def extract_keywords_from_task(self, task_description: str) -> List[str]:
        """
        Extract keywords from a task description.

        Args:
            task_description: Task description text

        Returns:
            List of extracted keywords
        """
        return self._extract_keywords(task_description)

    def _extract_keywords(self, text: str, min_length: int = 3, max_keywords: int = 20) -> List[str]:
        """
        Extract keywords from text with enhanced filtering and scoring.
        
        Args:
            text: Text to extract keywords from
            min_length: Minimum keyword length
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List of extracted keywords, sorted by relevance
        """
        # Simple keyword extraction with enhanced filtering
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "and",
            "but",
            "or",
            "nor",
            "so",
            "yet",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "not",
            "only",
            "own",
            "same",
            "than",
            "too",
            "very",
            "just",
            "also",
            "now",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "any",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "this",
            "that",
            "these",
            "those",
        }

        # Tokenize and filter with frequency scoring
        words = text.lower().split()
        keyword_counts = {}
        
        for word in words:
            # Clean word
            clean = "".join(c for c in word if c.isalnum() or c == "-")
            if clean and len(clean) >= min_length and clean not in stop_words:
                keyword_counts[clean] = keyword_counts.get(clean, 0) + 1
        
        # Sort by frequency (more frequent = more relevant)
        sorted_keywords = sorted(
            keyword_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return top keywords
        return [kw for kw, _ in sorted_keywords[:max_keywords]]

    def _deduplicate(
        self, predictions: List[ContextPrediction]
    ) -> List[ContextPrediction]:
        """Remove duplicate predictions."""
        seen = set()
        unique = []

        for pred in predictions:
            key = (pred.title.lower(), pred.context_type)
            if key not in seen:
                seen.add(key)
                unique.append(pred)

        return unique

    def _enhance_predictions_with_keywords(
        self,
        predictions: List[ContextPrediction],
        current_task: Optional[str],
        keywords: Optional[List[str]]
    ) -> List[ContextPrediction]:
        """
        Enhance predictions with keyword-based relevance scoring and cross-project matching.
        
        Args:
            predictions: List of context predictions
            current_task: Current task description
            keywords: Additional keywords
            
        Returns:
            Enhanced predictions with improved confidence scores
        """
        if not current_task and not keywords:
            return predictions

        # Extract keywords from task with enhanced extraction
        task_keywords = set()
        if current_task:
            task_keywords.update(self._extract_keywords(current_task, max_keywords=15))
        if keywords:
            task_keywords.update(keywords)

        # Boost confidence for predictions matching keywords
        for pred in predictions:
            pred_keywords = set(kw.lower() for kw in pred.keywords)
            task_keywords_lower = set(kw.lower() for kw in task_keywords)
            
            # Calculate overlap
            overlap = len(task_keywords_lower & pred_keywords)
            
            if overlap > 0:
                # Enhanced boost calculation based on overlap ratio
                overlap_ratio = overlap / max(len(task_keywords_lower), 1)
                
                # Stronger boost for higher overlap
                if overlap_ratio >= 0.5:
                    boost = 0.25  # High overlap
                elif overlap_ratio >= 0.3:
                    boost = 0.15  # Medium overlap
                else:
                    boost = 0.1   # Low overlap
                
                # Additional boost if keywords appear in title or description
                title_lower = pred.title.lower()
                desc_lower = pred.description.lower()
                title_matches = sum(1 for kw in task_keywords_lower if kw in title_lower)
                desc_matches = sum(1 for kw in task_keywords_lower if kw in desc_lower)
                
                if title_matches > 0:
                    boost += 0.1  # Keywords in title are very relevant
                if desc_matches > 0:
                    boost += 0.05  # Keywords in description add relevance
                
                pred.confidence = max(0.0, min(pred.confidence + boost, 1.0))

        return predictions

    def _fuse_context(
        self, predictions: List[ContextPrediction]
    ) -> List[ContextPrediction]:
        """
        Fuse context from multiple sources with enhanced deduplication and prioritization.

        Args:
            predictions: List of context predictions

        Returns:
            Fused and prioritized list of predictions with duplicates removed
        """
        if not predictions:
            return []

        # Group by context type
        by_type: Dict[str, List[ContextPrediction]] = {}
        for pred in predictions:
            if pred.context_type not in by_type:
                by_type[pred.context_type] = []
            by_type[pred.context_type].append(pred)

        # Prioritize: knowledge_base > project_docs > recent_activity > cursorrules
        priority_order = [
            "knowledge_base",
            "project_docs",
            "recent_activity",
            "cursorrules",
            "cursorrules_gap"
        ]

        fused = []
        seen_titles = set()
        seen_file_paths = set()

        # Add predictions in priority order with enhanced deduplication
        for ctx_type in priority_order:
            if ctx_type in by_type:
                # Sort by confidence within each type
                type_predictions = sorted(
                    by_type[ctx_type],
                    key=lambda p: p.confidence,
                    reverse=True
                )
                
                for pred in type_predictions:
                    # Deduplicate by title
                    title_key = pred.title.lower()
                    if title_key in seen_titles:
                        continue
                    
                    # Also deduplicate by file path if available
                    if pred.file_path:
                        file_key = str(pred.file_path).lower()
                        if file_key in seen_file_paths:
                            continue
                        seen_file_paths.add(file_key)
                    
                    seen_titles.add(title_key)
                    fused.append(pred)

        # Final sort by confidence (highest first)
        fused.sort(key=lambda p: p.confidence, reverse=True)

        return fused

    def get_context_for_recommendation(
        self, recommendation: Any
    ) -> List[ContextPrediction]:
        """Get context specifically for a recommendation."""
        keywords = []

        # Extract keywords from recommendation
        if hasattr(recommendation, "title"):
            keywords.extend(self._extract_keywords(recommendation.title))
        if hasattr(recommendation, "related_projects"):
            keywords.extend(recommendation.related_projects)

        return self.predict_context(
            current_project=(
                recommendation.related_projects[0]
                if hasattr(recommendation, "related_projects")
                and recommendation.related_projects
                else None
            ),
            keywords=keywords,
            limit=3,
        )


def main():
    """CLI for testing context intelligence."""
    import argparse

    parser = argparse.ArgumentParser(description="Predict relevant context")
    parser.add_argument("--project", help="Current project")
    parser.add_argument("--task", help="Current task description")
    parser.add_argument("--keywords", nargs="+", help="Search keywords")
    parser.add_argument("--limit", type=int, default=5, help="Max predictions")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    intel = ContextIntelligence()

    print(f"Knowledge base available: {intel.kb_available}\n")

    predictions = intel.predict_context(
        current_project=args.project,
        current_task=args.task,
        keywords=args.keywords,
        limit=args.limit,
    )

    if args.json:
        output = []
        for p in predictions:
            output.append(
                {
                    "title": p.title,
                    "context_type": p.context_type,
                    "confidence": p.confidence,
                    "description": p.description,
                    "rationale": p.rationale,
                    "command": p.command,
                    "file_path": p.file_path,
                    "keywords": p.keywords,
                }
            )
        print(json.dumps(output, indent=2))
    else:
        print(f"Found {len(predictions)} context predictions\n")

        for i, pred in enumerate(predictions, 1):
            confidence_bar = "█" * int(pred.confidence * 10) + "░" * (
                10 - int(pred.confidence * 10)
            )
            print(f"{i}. [{confidence_bar}] {pred.title}")
            print(f"   Type: {pred.context_type} | Confidence: {pred.confidence:.0%}")
            if pred.description:
                print(f"   Description: {pred.description[:100]}...")
            if pred.command:
                print(f"   Command: {pred.command}")
            print()


if __name__ == "__main__":
    main()
