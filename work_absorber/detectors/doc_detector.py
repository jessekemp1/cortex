"""
Completion document detector - Extract work signals from markdown docs.

Parses *_COMPLETE.md, *_SUMMARY.md, and similar completion documentation
to extract structured work achievements.
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import SignalDetector
from ..models import WorkSignal, WorkSignalType

logger = logging.getLogger(__name__)


class CompletionDocDetector(SignalDetector):
    """
    Detect work signals from completion documents.

    Looks for files matching patterns like:
    - *_COMPLETE.md
    - *_SUMMARY.md
    - *_DONE.md
    - CHANGELOG.md

    Parses markdown to extract:
    - Title from filename or first heading
    - Date from frontmatter or file modification time
    - Achievements from bullet lists
    - Scope from content analysis
    """

    # File patterns to search
    PATTERNS = [
        "*_COMPLETE.md",
        "*_SUMMARY.md",
        "*_DONE.md",
        "*_IMPLEMENTATION*.md",
        "CHANGELOG.md",
    ]

    @property
    def name(self) -> str:
        return "doc"

    def supports_incremental(self) -> bool:
        return True  # Can use file modification time

    def detect(
        self,
        project: str,
        project_path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[WorkSignal]:
        """
        Detect work signals from completion documents.

        Args:
            project: Project name
            project_path: Path to project directory
            since: Only docs modified after this time
            until: Only docs modified before this time

        Returns:
            List of WorkSignal objects
        """
        signals = []
        docs = self._find_completion_docs(project_path)

        for doc_path in docs:
            # Check modification time filter
            mtime = datetime.fromtimestamp(doc_path.stat().st_mtime)

            if since and mtime < since:
                continue
            if until and mtime > until:
                continue

            signal = self._parse_doc(project, doc_path, mtime)
            if signal:
                signals.append(signal)

        logger.info(f"Detected {len(signals)} doc signals for {project}")
        return signals

    def _find_completion_docs(self, project_path: Path) -> List[Path]:
        """Find all completion documents in the project."""
        docs = []

        for pattern in self.PATTERNS:
            # Search in project root
            docs.extend(project_path.glob(pattern))

            # Search one level deep (e.g., docs/, .claude/)
            docs.extend(project_path.glob(f"*/{pattern}"))

        # Deduplicate and sort by modification time (newest first)
        docs = list(set(docs))
        docs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        return docs

    def _parse_doc(
        self,
        project: str,
        doc_path: Path,
        mtime: datetime,
    ) -> Optional[WorkSignal]:
        """Parse a completion document into a WorkSignal."""
        try:
            content = doc_path.read_text(encoding="utf-8", errors="ignore")

            # Extract metadata
            title = self._extract_title(doc_path, content)
            date = self._extract_date(content, mtime)
            achievements = self._extract_achievements(content)
            scope = self._extract_scope(doc_path, content)
            description = self._extract_description(content)

            # Generate deterministic ID
            signal_id = WorkSignal.generate_id(
                WorkSignalType.COMPLETION_DOC,
                str(doc_path),
                date,
            )

            return WorkSignal(
                id=signal_id,
                signal_type=WorkSignalType.COMPLETION_DOC,
                source_path=str(doc_path),
                project=project,
                timestamp=date,
                title=title,
                description=description,
                achievements=achievements,
                scope=scope,
                metadata={
                    "file_name": doc_path.name,
                    "file_size": doc_path.stat().st_size,
                    "word_count": len(content.split()),
                },
            )

        except Exception as e:
            logger.warning(f"Failed to parse doc {doc_path}: {e}")
            return None

    def _extract_title(self, doc_path: Path, content: str) -> str:
        """Extract title from doc filename or first heading."""
        # Try first H1 heading
        h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        # Fall back to filename
        name = doc_path.stem
        # Convert BATCH_SCHEDULER_COMPLETE to "Batch Scheduler Complete"
        name = name.replace("_", " ").title()
        return name

    def _extract_date(self, content: str, fallback: datetime) -> datetime:
        """Extract date from frontmatter or content."""
        # Try YAML frontmatter
        frontmatter_match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
        if frontmatter_match:
            fm = frontmatter_match.group(1)
            date_match = re.search(r"date:\s*(\d{4}-\d{2}-\d{2})", fm)
            if date_match:
                try:
                    return datetime.fromisoformat(date_match.group(1))
                except ValueError:
                    pass

        # Try common date patterns in content
        patterns = [
            r"\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})",
            r"\*\*Created\*\*:\s*(\d{4}-\d{2}-\d{2})",
            r"\*\*Completed?\*\*:\s*(\d{4}-\d{2}-\d{2})",
            r"Date:\s*(\d{4}-\d{2}-\d{2})",
            r"Completed?:\s*(\d{4}-\d{2}-\d{2})",
            # Also try "December 27, 2025" format
            r"(\w+\s+\d{1,2},?\s+\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try ISO format first
                    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                        return datetime.fromisoformat(date_str)
                    # Try natural format
                    from dateutil import parser
                    return parser.parse(date_str)
                except (ValueError, ImportError):
                    continue

        return fallback

    def _extract_achievements(self, content: str) -> List[str]:
        """Extract achievements from bullet lists."""
        achievements = []

        # Find sections with achievement indicators
        achievement_sections = [
            r"##?\s*(?:Achievements?|What Was Built|Completed?|Summary|Key (?:Features?|Achievements?))\s*\n([\s\S]*?)(?=\n##|\Z)",
            r"##?\s*\S+\s+COMPLETE\s*\n([\s\S]*?)(?=\n##|\Z)",
        ]

        for pattern in achievement_sections:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                section = match.group(1)
                # Extract bullet points
                bullets = re.findall(r"^\s*[-*]\s+(.+)$", section, re.MULTILINE)
                for bullet in bullets:
                    # Clean up the bullet
                    cleaned = bullet.strip()
                    if cleaned and len(cleaned) > 5:
                        achievements.append(cleaned[:200])  # Limit length

        # Also look for checkmarks
        checkmarks = re.findall(r"^\s*[-*]\s+\[x\]\s+(.+)$", content, re.MULTILINE | re.IGNORECASE)
        for item in checkmarks:
            cleaned = item.strip()
            if cleaned and cleaned not in achievements:
                achievements.append(cleaned[:200])

        return achievements[:20]  # Limit to 20 achievements

    def _extract_scope(self, doc_path: Path, content: str) -> Optional[str]:
        """Determine the scope/type of work from the document."""
        name_lower = doc_path.stem.lower()
        content_lower = content.lower()

        # Check filename first
        scope_indicators = {
            "feature": ["feature", "feat", "implementation", "add"],
            "bugfix": ["fix", "bug", "patch", "resolve"],
            "refactor": ["refactor", "clean", "reorganize"],
            "docs": ["docs", "documentation", "readme"],
            "test": ["test", "testing", "coverage"],
            "performance": ["perf", "performance", "optimization"],
            "deploy": ["deploy", "deployment", "release"],
        }

        for scope, keywords in scope_indicators.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return scope

        # Check content
        for scope, keywords in scope_indicators.items():
            for keyword in keywords:
                if keyword in content_lower[:500]:  # First 500 chars
                    return scope

        return "feature"  # Default

    def _extract_description(self, content: str) -> str:
        """Extract a brief description from the document."""
        # Try to get executive summary or first paragraph
        summary_match = re.search(
            r"##?\s*(?:Executive\s+)?Summary\s*\n([\s\S]*?)(?=\n##|\Z)",
            content,
            re.IGNORECASE,
        )
        if summary_match:
            summary = summary_match.group(1).strip()
            # Get first paragraph
            paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]
            if paragraphs:
                return paragraphs[0][:500]

        # Fall back to first non-heading paragraph
        paragraphs = re.findall(r"^(?!#|\*|-|\|)(.{50,})$", content, re.MULTILINE)
        if paragraphs:
            return paragraphs[0].strip()[:500]

        return ""

    def get_latest_doc_mtime(self, project_path: Path) -> Optional[datetime]:
        """Get the latest modification time for checkpointing."""
        docs = self._find_completion_docs(project_path)
        if not docs:
            return None

        latest = max(docs, key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest.stat().st_mtime)
