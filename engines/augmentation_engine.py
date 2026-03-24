"""
Augmentation Engine

Takes a raw idea and enriches it via three passes:
1. Graph query — related patterns from SynthesisCore
2. Prior outcomes — similar past ideas from WorkstreamOrchestrator history
3. Bridge query — Cortex intelligence at :8765 (fails gracefully if offline)

Returns AugmentedIdea with confidence score for quality-gating.

Usage:
    engine = AugmentationEngine()
    result = engine.augment("add caching to forecast API", "vortex", "build")
    print(result.refined)
    print(result.related_patterns)
"""

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("CORTEX_BRIDGE_URL", "http://localhost:8765")
AUGMENTATIONS_PATH = Path.home() / ".cortex" / "augmentations.jsonl"


@dataclass
class AugmentedIdea:
    """Result of an augmentation cycle."""

    original: str
    project: str
    refined: str  # Sharpened restatement of the idea
    related_patterns: List[str]  # Graph-matched patterns
    prior_outcomes: List[str]  # Similar past ideas + what happened
    counter_arguments: List[str]  # Adversarial pass
    confidence: float  # 0–1, based on pattern match quality
    augmentation_id: str  # For tracking
    phase: str = "build"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class AugmentationEngine:
    """
    Enriches raw ideas using Cortex memory.

    Three-pass augmentation:
    - Pass 1: SynthesisCore graph — pattern/lesson nodes
    - Pass 2: WorkstreamOrchestrator — prior signal outcomes
    - Pass 3: Bridge intelligence — deep Cortex query (optional)
    """

    def __init__(self, bridge_url: str = BRIDGE_URL):
        self.bridge_url = bridge_url
        AUGMENTATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Lazy-initialized engine references
        self._orchestrator = None
        self._synthesis = None

    # ─── Public Interface ────────────────────────────────────

    def augment(self, idea: str, project: str, phase: str = "build") -> AugmentedIdea:
        """
        Enrich an idea via three augmentation passes.

        Args:
            idea:    Raw idea text
            project: Project context (e.g., "vortex", "cortex")
            phase:   Work phase (e.g., "build", "design")

        Returns:
            AugmentedIdea with enriched context and confidence score
        """
        aug_id = f"aug_{uuid.uuid4().hex[:8]}"

        # Pass 1: SynthesisCore graph
        related_patterns = self._query_graph(idea)

        # Pass 2: Prior outcomes from orchestrator
        prior_outcomes = self._query_prior_outcomes(idea)

        # Pass 3: Bridge intelligence (optional, fails gracefully)
        bridge_data = self._query_bridge(idea)
        bridge_patterns = bridge_data.get("patterns", [])
        all_patterns = list(dict.fromkeys(related_patterns + bridge_patterns))  # dedupe

        # Compose refined statement
        refined = self._refine_idea(idea, all_patterns, prior_outcomes)

        # Adversarial pass — generate counter-arguments
        counter_args = self._generate_counter_arguments(idea, all_patterns)

        # Confidence: based on pattern match count + bridge availability
        confidence = self._calculate_confidence(related_patterns, prior_outcomes, bridge_data)

        result = AugmentedIdea(
            original=idea,
            project=project,
            refined=refined,
            related_patterns=all_patterns[:6],
            prior_outcomes=prior_outcomes[:4],
            counter_arguments=counter_args[:3],
            confidence=confidence,
            augmentation_id=aug_id,
            phase=phase,
        )

        self._record_augmentation(result)
        return result

    # ─── Private Passes ──────────────────────────────────────

    def _query_graph(self, idea: str) -> List[str]:
        """Pass 1: Search SynthesisCore for related pattern/lesson nodes."""
        try:
            synthesis = self._get_synthesis()
            result = synthesis.query(idea, limit=8)

            patterns = []
            for node in result.get("nodes", []):
                name = node.get("name", "")
                node_type = node.get("type", "")
                if node_type in ("pattern", "lesson") and name:
                    patterns.append(name)
                elif name:
                    patterns.append(f"{node_type}: {name}")

            return patterns
        except Exception as e:
            logger.debug("graph query failed: %s", e)
            return []

    def _query_prior_outcomes(self, idea: str) -> List[str]:
        """Pass 2: Find similar signals from WorkstreamOrchestrator history."""
        try:
            orchestrator = self._get_orchestrator()
            recent = orchestrator.get_recent_signals(limit=100)

            idea_lower = idea.lower()
            keywords = set(idea_lower.split())
            # Remove common stop words
            stop_words = {"the", "a", "an", "to", "for", "in", "of", "and", "or", "is"}
            keywords -= stop_words

            matches = []
            for signal in recent:
                if signal.content_type not in ("idea", "decision", "insight"):
                    continue
                content_lower = signal.content.lower()
                overlap = sum(1 for kw in keywords if kw in content_lower)
                if overlap >= 2:
                    matches.append((overlap, signal))

            matches.sort(key=lambda x: -x[0])
            return [f"[{s.project}] {s.content[:120]}" for _, s in matches[:4]]
        except Exception as e:
            logger.debug("prior outcomes query failed: %s", e)
            return []

    def _query_bridge(self, idea: str) -> Dict[str, Any]:
        """Pass 3: Query Cortex bridge at :8765 for intelligence enrichment.

        Fails gracefully — returns empty dict if bridge is offline.
        """
        try:
            payload = json.dumps(
                {
                    "request": f"Patterns and insights related to: {idea}",
                    "project": "cross-project",
                    "query_type": "research",
                }
            ).encode()

            req = urllib.request.Request(
                f"{self.bridge_url}/intelligence",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                # Extract pattern hints from bridge response
                response_text = str(data.get("response", ""))
                # Heuristic: lines starting with "-" or "•" are patterns
                patterns = [
                    line.lstrip("-•* ").strip()
                    for line in response_text.splitlines()
                    if line.strip().startswith(("-", "•", "*")) and len(line.strip()) > 10
                ]
                return {"patterns": patterns[:4], "raw": response_text[:400]}
        except (urllib.error.URLError, OSError):
            # Bridge offline — expected in tests and offline usage
            return {}
        except Exception as e:
            logger.debug("bridge query failed: %s", e)
            return {}

    def _refine_idea(
        self,
        idea: str,
        patterns: List[str],
        prior_outcomes: List[str],
    ) -> str:
        """Compose a refined restatement of the idea.

        Incorporates the most relevant matched patterns. When no patterns
        are found the idea is returned with light capitalisation fix.
        """
        refined = idea.strip()
        if not refined.endswith("."):
            refined += "."

        if patterns:
            top = patterns[0]
            refined = f"{refined} (Relates to pattern: {top})"

        if prior_outcomes:
            refined += f" Previously seen in: {prior_outcomes[0][:80]}"

        return refined

    def _generate_counter_arguments(self, idea: str, patterns: List[str]) -> List[str]:
        """Generate adversarial counter-arguments.

        Uses rule-based heuristics since bridge may be offline.
        """
        counters = []

        if "cach" in idea.lower():
            counters.append("Cache invalidation adds complexity — verify stale-data risk first.")
        if "refactor" in idea.lower():
            counters.append("Refactoring without tests is risky — ensure coverage before changing.")
        if "new" in idea.lower() or "add" in idea.lower():
            counters.append(
                "New surface area = new failure modes — start with the minimum viable implementation."
            )
        if not counters:
            counters.append("Validate against existing tests before expanding scope.")

        if patterns:
            counters.append(f"Consider: does this conflict with '{patterns[0]}'?")

        return counters

    def _calculate_confidence(
        self,
        patterns: List[str],
        prior_outcomes: List[str],
        bridge_data: Dict,
    ) -> float:
        """Calculate 0–1 confidence from match quality."""
        score = 0.0

        # Pattern matches: up to 0.4
        score += min(len(patterns) * 0.1, 0.4)

        # Prior outcomes: up to 0.3
        score += min(len(prior_outcomes) * 0.1, 0.3)

        # Bridge available: +0.2
        if bridge_data and bridge_data.get("patterns"):
            score += 0.2

        # Baseline: 0.1 (we always have at least a structured output)
        score += 0.1

        return round(min(score, 1.0), 3)

    def _record_augmentation(self, result: AugmentedIdea) -> None:
        """Append augmentation event to JSONL log."""
        try:
            with open(AUGMENTATIONS_PATH, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except Exception as e:
            logger.warning("augmentation record failed: %s", e)

    # ─── Engine Access (lazy) ────────────────────────────────

    def _get_orchestrator(self):
        if self._orchestrator is None:
            try:
                from cortex.engines.workstream_orchestrator import WorkstreamOrchestrator
            except ImportError:
                from .workstream_orchestrator import WorkstreamOrchestrator
            self._orchestrator = WorkstreamOrchestrator()
        return self._orchestrator

    def _get_synthesis(self):
        if self._synthesis is None:
            try:
                from cortex.engines.synthesis import SynthesisCore
            except ImportError:
                from .synthesis import SynthesisCore
            self._synthesis = SynthesisCore()
        return self._synthesis
