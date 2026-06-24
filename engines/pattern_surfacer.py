"""
Pattern Surfacer

Surfaces cross-project insights when activating a workstream.
Queries the synthesis graph for pattern/lesson nodes from other projects,
ranks by keyword overlap, and emits results to stdout for shell hook capture.

Only surfaces patterns with confidence > 0.4 to avoid noise (Experiment 6).

Usage:
    surfacer = PatternSurfacer()
    patterns = surfacer.surface("cortex", recent_signals)
    for p in patterns:
        print(p.pattern, p.project_source, p.relevance)
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.4  # Experiment 6: only surface if above this


@dataclass
class SurfacedPattern:
    """A cross-project pattern surfaced for the active workstream."""

    pattern: str
    project_source: str
    relevance: float  # 0–1
    node_type: str
    summary: str
    node_id: str = ""
    surfaced_at: datetime = field(default_factory=datetime.now)

    def display(self) -> str:
        """One-line display for shell output."""
        icon = "💡" if self.node_type == "pattern" else "📖"
        bar = "█" * int(self.relevance * 5) + "░" * (5 - int(self.relevance * 5))
        return (
            f"  {icon} [{self.project_source}] {self.pattern[:60]}\n"
            f"     {bar} {self.relevance:.2f}  {self.summary[:80]}"
        )


class PatternSurfacer:
    """
    Cross-project pattern detection for workstream activation.

    Connects to the synthesis graph and ranks pattern/lesson nodes
    from other projects by keyword overlap with recent signals.
    """

    def __init__(self):
        self._synthesis = None
        self._bus = None

    def surface(
        self,
        active_project: str,
        recent_signals: Optional[List[Any]] = None,
    ) -> List[SurfacedPattern]:
        """
        Surface cross-project patterns relevant to the active workstream.

        Args:
            active_project:  The currently active project (excluded from results)
            recent_signals:  Recent WorkspaceSignal objects for keyword extraction

        Returns:
            List of SurfacedPattern objects with relevance > CONFIDENCE_THRESHOLD,
            sorted by relevance descending.
        """
        keywords = self._extract_keywords(recent_signals or [])
        matches = self._find_graph_matches(keywords, exclude_project=active_project)
        ranked = self._rank_by_relevance(matches, keywords)

        # Filter and emit
        results = [p for p in ranked if p.relevance > CONFIDENCE_THRESHOLD]

        if results:
            self._emit(active_project, results)
            self._record_to_bus(active_project, results)

        return results

    def surface_for_keywords(
        self,
        keywords: List[str],
        exclude_project: str,
        limit: int = 5,
    ) -> List[SurfacedPattern]:
        """Surface patterns for explicit keyword list.

        Useful for augmentation engine integration.
        """
        matches = self._find_graph_matches(keywords, exclude_project)
        ranked = self._rank_by_relevance(matches, keywords)
        return [p for p in ranked if p.relevance > CONFIDENCE_THRESHOLD][:limit]

    # ─── Private ─────────────────────────────────────────────

    def _find_graph_matches(self, keywords: List[str], exclude_project: str) -> List[Any]:
        """Find graph nodes from other projects matching keywords."""
        nodes = []
        try:
            synthesis = self._get_synthesis()
            graph = synthesis.graph

            try:
                from cortex.engines.synthesis import NodeType
            except ImportError:
                from .synthesis import NodeType

            for node in graph.nodes.values():
                if node.type not in (NodeType.PATTERN, NodeType.LESSON):
                    continue

                node_project = node.data.get("project", "")
                if node_project == exclude_project:
                    continue

                # Include if any keyword matches name or data
                node_text = (node.name + " " + str(node.data)).lower()
                if any(kw in node_text for kw in keywords if len(kw) > 3):
                    nodes.append(node)

        except Exception as e:
            logger.debug("graph match failed: %s", e)

        return nodes

    def _rank_by_relevance(self, matches: List[Any], keywords: List[str]) -> List[SurfacedPattern]:
        """Score and rank matched nodes by keyword overlap."""
        scored: List[tuple] = []

        for node in matches:
            node_text = (node.name + " " + str(node.data)).lower()
            hits = sum(1 for kw in keywords if len(kw) > 3 and kw in node_text)
            if not keywords:
                score = 0.1
            else:
                score = round(min(hits / max(len(keywords), 1), 1.0), 3)

            try:
                from cortex.engines.synthesis import NodeType
            except ImportError:
                pass

            pattern = SurfacedPattern(
                pattern=node.name,
                project_source=node.data.get("project", "unknown"),
                relevance=score,
                node_type=node.type.value,
                summary=str(node.data.get("description", node.name))[:200],
                node_id=node.id,
            )
            scored.append((score, pattern))

        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored]

    def _extract_keywords(self, signals: List[Any]) -> List[str]:
        """Extract meaningful keywords from recent signals."""
        stop_words = {
            "the",
            "a",
            "an",
            "to",
            "for",
            "in",
            "of",
            "and",
            "or",
            "is",
            "be",
            "was",
            "are",
            "with",
            "from",
            "at",
            "by",
            "this",
            "that",
        }
        words: Dict[str, int] = {}

        for signal in signals[-20:]:
            text = getattr(signal, "content", "")
            for word in text.lower().split():
                word = word.strip(".,;:!?()[]")
                if len(word) > 3 and word not in stop_words:
                    words[word] = words.get(word, 0) + 1

        # Return most frequent keywords
        sorted_words = sorted(words.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:15]]

    def _emit(self, active_project: str, patterns: List[SurfacedPattern]) -> None:
        """Print surfaced patterns to stdout for shell hook capture."""
        print(f"\n🔀 Cross-project patterns for {active_project}:")
        for p in patterns[:5]:
            print(p.display())
        print()
        sys.stdout.flush()

    def _record_to_bus(self, active_project: str, patterns: List[SurfacedPattern]) -> None:
        """Record surfaced patterns to UniversalSignalBus."""
        try:
            from cortex.engines.universal_signal_bus import UniversalSignalBus
            from cortex.engines.workstream_orchestrator import (
                WorkspaceSignal,
                SignalSource,
                WorkstreamPhase,
            )
        except ImportError:
            try:
                from .universal_signal_bus import UniversalSignalBus
                from .workstream_orchestrator import WorkspaceSignal, SignalSource, WorkstreamPhase
            except ImportError:
                return

        try:
            bus = UniversalSignalBus()
            for p in patterns:
                signal = WorkspaceSignal(
                    source=SignalSource.MANUAL,
                    timestamp=datetime.now(),
                    project=active_project,
                    workstream=WorkstreamPhase.RESEARCH,
                    content_type="insight",
                    content=f"Cross-project pattern from {p.project_source}: {p.pattern}",
                    confidence=p.relevance,
                )
                bus.absorb(signal)
        except Exception as e:
            logger.debug("bus record failed: %s", e)

    def _get_synthesis(self):
        if self._synthesis is None:
            try:
                from cortex.engines.synthesis import SynthesisCore
            except ImportError:
                from .synthesis import SynthesisCore
            self._synthesis = SynthesisCore()
        return self._synthesis


# ─── CLI Entry Point ──────────────────────────────────────────


def main():
    """Surface cross-project patterns for the active workstream."""
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "cortex"
    surfacer = PatternSurfacer()
    patterns = surfacer.surface(project)

    if not patterns:
        print(f"No cross-project patterns found for {project}")
    sys.exit(0)


if __name__ == "__main__":
    main()
