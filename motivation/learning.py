"""Kempion learning loop — resonance tracking and anti-pattern refinement.

Learns what wisdom lands for this seeker and what misses. Adjusts
the engine's scoring weights based on accumulated feedback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from motivation.models import SeekerProfile, WisdomInteraction
from motivation.quote_engine import WisdomEngine


@dataclass
class ResonanceStats:
    """Aggregated resonance statistics for a seeker."""

    total_interactions: int = 0
    total_rated: int = 0
    average_rating: float = 0.0
    hit_different_count: int = 0
    hit_different_rate: float = 0.0
    skip_count: int = 0
    skip_rate: float = 0.0
    saved_count: int = 0
    reflection_count: int = 0
    top_resonating_themes: list[str] = field(default_factory=list)
    top_resonating_traditions: list[str] = field(default_factory=list)
    anti_pattern_misses: list[str] = field(default_factory=list)


class LearningManager:
    """Processes feedback to improve wisdom selection over time."""

    def __init__(self, engine: WisdomEngine) -> None:
        self.engine = engine
        self._theme_scores: dict[str, dict[str, list[float]]] = {}  # seeker -> theme -> ratings
        self._tradition_scores: dict[str, dict[str, list[float]]] = {}  # seeker -> tradition -> ratings
        self._miss_tracker: dict[str, list[str]] = {}  # seeker -> [wisdom_ids that missed]

    def process_interaction(
        self,
        interaction: WisdomInteraction,
        wisdom_themes: list[str],
        wisdom_tradition: str,
    ) -> None:
        """Process a wisdom interaction and update learned resonance."""
        seeker_id = interaction.seeker_id
        wisdom_id = interaction.wisdom_id

        # Compute resonance score from interaction signals
        resonance = self._compute_resonance(interaction)

        # Update engine's resonance cache
        self.engine.update_resonance(seeker_id, wisdom_id, resonance)

        # Track theme-level resonance
        if seeker_id not in self._theme_scores:
            self._theme_scores[seeker_id] = {}
        for theme in wisdom_themes:
            theme_lower = theme.lower()
            if theme_lower not in self._theme_scores[seeker_id]:
                self._theme_scores[seeker_id][theme_lower] = []
            self._theme_scores[seeker_id][theme_lower].append(resonance)

        # Track tradition-level resonance
        if seeker_id not in self._tradition_scores:
            self._tradition_scores[seeker_id] = {}
        trad_lower = wisdom_tradition.lower()
        if trad_lower not in self._tradition_scores[seeker_id]:
            self._tradition_scores[seeker_id][trad_lower] = []
        self._tradition_scores[seeker_id][trad_lower].append(resonance)

        # Track misses
        if resonance < 0.3:
            if seeker_id not in self._miss_tracker:
                self._miss_tracker[seeker_id] = []
            self._miss_tracker[seeker_id].append(wisdom_id)

    def get_resonance_stats(
        self,
        seeker_id: str,
        interactions: list[WisdomInteraction],
    ) -> ResonanceStats:
        """Compute aggregated resonance statistics."""
        if not interactions:
            return ResonanceStats()

        rated = [i for i in interactions if i.rating is not None]
        avg_rating = sum(i.rating for i in rated) / len(rated) if rated else 0.0
        hit_diff = [i for i in interactions if i.hit_different]
        skipped = [i for i in interactions if i.skipped]
        saved = [i for i in interactions if i.saved_to_commonplace]
        reflected = [i for i in interactions if i.reflection]

        # Top themes
        theme_avgs = {}
        for theme, scores in self._theme_scores.get(seeker_id, {}).items():
            if scores:
                theme_avgs[theme] = sum(scores) / len(scores)
        top_themes = sorted(theme_avgs, key=theme_avgs.get, reverse=True)[:5]

        # Top traditions
        trad_avgs = {}
        for trad, scores in self._tradition_scores.get(seeker_id, {}).items():
            if scores:
                trad_avgs[trad] = sum(scores) / len(scores)
        top_trads = sorted(trad_avgs, key=trad_avgs.get, reverse=True)[:3]

        return ResonanceStats(
            total_interactions=len(interactions),
            total_rated=len(rated),
            average_rating=avg_rating,
            hit_different_count=len(hit_diff),
            hit_different_rate=len(hit_diff) / len(interactions) if interactions else 0.0,
            skip_count=len(skipped),
            skip_rate=len(skipped) / len(interactions) if interactions else 0.0,
            saved_count=len(saved),
            reflection_count=len(reflected),
            top_resonating_themes=top_themes,
            top_resonating_traditions=top_trads,
            anti_pattern_misses=self._miss_tracker.get(seeker_id, [])[-10:],
        )

    def suggest_tradition_affinity_update(
        self, seeker_id: str
    ) -> Optional[dict[str, float]]:
        """Suggest updated tradition affinity based on learned resonance."""
        trad_scores = self._tradition_scores.get(seeker_id, {})
        if not trad_scores:
            return None

        updated = {}
        for tradition, scores in trad_scores.items():
            if len(scores) >= 3:  # Need enough data
                updated[tradition] = min(1.0, max(0.0, sum(scores) / len(scores)))

        return updated if updated else None

    def _compute_resonance(self, interaction: WisdomInteraction) -> float:
        """Compute a 0-1 resonance score from interaction signals."""
        if interaction.skipped:
            return 0.0

        score = 0.5  # Baseline: they saw it

        # Rating is the strongest explicit signal
        if interaction.rating is not None:
            score = interaction.rating / 5.0

        # "Hit different" is the highest signal
        if interaction.hit_different:
            score = max(score, 0.95)

        # Saving to commonplace book is a strong signal
        if interaction.saved_to_commonplace:
            score = min(1.0, score + 0.15)

        # Writing a reflection is a depth signal
        if interaction.reflection:
            score = min(1.0, score + 0.1)

        return score
