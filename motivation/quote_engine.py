"""Kempion Wisdom Engine — base-truth scoring for the poet-warrior-monk.

Multi-signal ranking that optimizes for truth that serves growth,
not dopamine hits disguised as wisdom. Includes anti-pattern guard
and paradox pair awareness.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from motivation.models import (
    Aspect,
    InnerSeason,
    SeekerProfile,
    TonePreference,
    ToneVector,
    TruthLayer,
    WisdomEntry,
)
from motivation.quote_database import WisdomDatabase


# Tone preference → target tone vector mapping
_TONE_TARGETS: dict[TonePreference, ToneVector] = {
    TonePreference.SEVERE: ToneVector(severity=0.9, warmth=0.2, directness=0.9),
    TonePreference.TEMPERED: ToneVector(severity=0.5, warmth=0.5, directness=0.6),
    TonePreference.GENTLE: ToneVector(severity=0.2, warmth=0.8, directness=0.3),
}

# Season → dominant aspect mapping (what aspect leads in each season)
_SEASON_ASPECT_WEIGHTS: dict[InnerSeason, dict[str, float]] = {
    InnerSeason.FORGE: {"warrior": 0.5, "poet": 0.2, "monk": 0.3},
    InnerSeason.DESERT: {"monk": 0.5, "poet": 0.3, "warrior": 0.2},
    InnerSeason.SUMMIT: {"poet": 0.5, "warrior": 0.2, "monk": 0.3},
    InnerSeason.CONSOLIDATION: {"monk": 0.4, "warrior": 0.4, "poet": 0.2},
    InnerSeason.DRIFT: {"poet": 0.4, "warrior": 0.4, "monk": 0.2},
    InnerSeason.DARK_NIGHT: {"monk": 0.34, "poet": 0.33, "warrior": 0.33},
    InnerSeason.UNKNOWN: {"warrior": 0.34, "poet": 0.33, "monk": 0.33},
}

# Anti-pattern keywords that Kempion filters against
_BUILTIN_ANTI_PATTERNS = {
    "toxic_positivity", "hustle_porn", "spiritual_bypassing",
    "manifest", "grindset", "boss_babe", "rise_and_grind",
}


@dataclass
class ScoringWeights:
    """Configurable weights for the base-truth scoring formula."""

    truth_depth: float = 0.12
    aspect_alignment: float = 0.15
    season_fit: float = 0.15
    tradition_affinity: float = 0.12
    trial_relevance: float = 0.15
    quest_alignment: float = 0.10
    temporal_resonance: float = 0.05
    novelty: float = 0.08
    learned_resonance: float = 0.08
    repetition_penalty: float = 0.25
    anti_pattern_penalty: float = 0.50


@dataclass
class ScoredWisdom:
    """A wisdom entry with its computed relevance score."""

    wisdom: WisdomEntry
    total_score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)


class WisdomEngine:
    """Base-truth scoring engine for the poet-warrior-monk path."""

    def __init__(
        self,
        database: WisdomDatabase,
        weights: Optional[ScoringWeights] = None,
    ) -> None:
        self.database = database
        self.weights = weights or ScoringWeights()
        self._resonance_cache: dict[str, dict[str, float]] = {}

    def select_wisdom(
        self,
        profile: SeekerProfile,
        seen_ids: Optional[set[str]] = None,
        current_hour: Optional[int] = None,
        candidate_limit: int = 10,
    ) -> Optional[ScoredWisdom]:
        """Select the best wisdom for the seeker's current moment."""
        scored = self.score_all(profile, seen_ids=seen_ids, current_hour=current_hour)
        if not scored:
            return None

        top = scored[:candidate_limit]
        if len(top) > 3:
            weights = [max(0.01, sw.total_score) for sw in top]
            total = sum(weights)
            weights = [w / total for w in weights]
            return random.choices(top, weights=weights, k=1)[0]
        return top[0]

    def select_paradox_pair(
        self,
        profile: SeekerProfile,
        seen_ids: Optional[set[str]] = None,
    ) -> Optional[tuple[ScoredWisdom, WisdomEntry]]:
        """Select a wisdom entry that has a paradox pair, return both."""
        scored = self.score_all(profile, seen_ids=seen_ids)
        for sw in scored:
            if sw.wisdom.paradox_pair_id:
                partner = self.database.get(sw.wisdom.paradox_pair_id)
                if partner:
                    return sw, partner
        return None

    def score_all(
        self,
        profile: SeekerProfile,
        seen_ids: Optional[set[str]] = None,
        current_hour: Optional[int] = None,
    ) -> list[ScoredWisdom]:
        """Score all wisdom entries for the seeker. Returns sorted desc."""
        seen = seen_ids or set()
        if current_hour is None:
            current_hour = datetime.now().hour

        all_entries = self.database.all_entries()
        scored: list[ScoredWisdom] = []

        for entry in all_entries:
            score, breakdown = self._compute_score(entry, profile, seen, current_hour)
            scored.append(ScoredWisdom(wisdom=entry, total_score=score, score_breakdown=breakdown))

        scored.sort(key=lambda s: s.total_score, reverse=True)
        return scored

    def update_resonance(self, seeker_id: str, wisdom_id: str, score: float) -> None:
        if seeker_id not in self._resonance_cache:
            self._resonance_cache[seeker_id] = {}
        self._resonance_cache[seeker_id][wisdom_id] = score

    def _compute_score(
        self,
        entry: WisdomEntry,
        profile: SeekerProfile,
        seen_ids: set[str],
        current_hour: int,
    ) -> tuple[float, dict[str, float]]:
        w = self.weights
        breakdown: dict[str, float] = {}

        breakdown["truth_depth"] = w.truth_depth * _truth_depth_match(entry, profile)
        breakdown["aspect_alignment"] = w.aspect_alignment * _aspect_alignment(entry, profile)
        breakdown["season_fit"] = w.season_fit * _season_fit(entry, profile)
        breakdown["tradition_affinity"] = w.tradition_affinity * _tradition_affinity(entry, profile)
        breakdown["trial_relevance"] = w.trial_relevance * _trial_relevance(entry, profile)
        breakdown["quest_alignment"] = w.quest_alignment * _quest_alignment(entry, profile)
        breakdown["temporal_resonance"] = w.temporal_resonance * _temporal_resonance(entry, current_hour, profile)
        breakdown["novelty"] = w.novelty * _novelty(entry, seen_ids)
        breakdown["learned_resonance"] = w.learned_resonance * self._resonance_score(profile.id, entry.id)

        # Penalties
        breakdown["repetition_penalty"] = -w.repetition_penalty * _repetition_penalty(entry, seen_ids)
        breakdown["anti_pattern_penalty"] = -w.anti_pattern_penalty * _anti_pattern_match(entry, profile)

        total = sum(breakdown.values())
        return total, breakdown

    def _resonance_score(self, seeker_id: str, wisdom_id: str) -> float:
        user_cache = self._resonance_cache.get(seeker_id, {})
        return user_cache.get(wisdom_id, 0.5)


# --- Scoring components ---


def _truth_depth_match(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """How well the wisdom's depth matches what the seeker needs right now."""
    if entry.truth_layer == profile.depth_preference:
        return 1.0

    # Adjacent depth layers score well
    depth_order = [TruthLayer.SURFACE, TruthLayer.STRUCTURAL, TruthLayer.ROOT, TruthLayer.PARADOX, TruthLayer.SILENCE]
    try:
        entry_idx = depth_order.index(entry.truth_layer)
        pref_idx = depth_order.index(profile.depth_preference)
        distance = abs(entry_idx - pref_idx)
        return max(0.2, 1.0 - distance * 0.25)
    except ValueError:
        return 0.5


def _aspect_alignment(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """How well the wisdom's aspect matches the seeker's aspect balance + current season."""
    if entry.aspect == Aspect.ALL:
        return 0.7  # Universal wisdom is good but not perfectly targeted

    # Blend seeker's personal aspect balance with season-driven aspect weighting
    season_weights = _SEASON_ASPECT_WEIGHTS.get(profile.inner_season, {})
    personal = profile.aspect_balance

    # Effective weights: 60% season-driven, 40% personal preference
    effective: dict[str, float] = {}
    for aspect_name in ["poet", "warrior", "monk"]:
        season_w = season_weights.get(aspect_name, 0.33)
        personal_w = personal.get(aspect_name, 0.33)
        effective[aspect_name] = 0.6 * season_w + 0.4 * personal_w

    # Map entry aspect to aspect names
    aspect_map: dict[Aspect, list[str]] = {
        Aspect.POET: ["poet"],
        Aspect.WARRIOR: ["warrior"],
        Aspect.MONK: ["monk"],
        Aspect.POET_WARRIOR: ["poet", "warrior"],
        Aspect.WARRIOR_MONK: ["warrior", "monk"],
        Aspect.POET_MONK: ["poet", "monk"],
    }

    entry_aspects = aspect_map.get(entry.aspect, [])
    if not entry_aspects:
        return 0.5

    return sum(effective.get(a, 0.33) for a in entry_aspects) / len(entry_aspects)


def _season_fit(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """How well the wisdom fits the seeker's current inner season."""
    if profile.inner_season == InnerSeason.UNKNOWN:
        return 0.5
    if profile.inner_season in entry.best_for_seasons:
        return 1.0
    if not entry.best_for_seasons:
        return 0.4  # Untagged wisdom gets a mild score
    return 0.2


def _tradition_affinity(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """Score based on how much the seeker resonates with this tradition."""
    if not profile.tradition_affinity:
        return 0.5
    return profile.tradition_affinity.get(entry.tradition.lower(), 0.3)


def _trial_relevance(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """How well the wisdom addresses the seeker's active trials."""
    trials = profile.active_trials
    if not trials:
        return 0.5

    trial_words = set()
    for trial in trials:
        trial_words.update(trial.description.lower().split())
        trial_words.update(trial.truth_beneath.lower().split())

    quote_types = {ct.lower() for ct in entry.challenge_types}
    type_match = len(quote_types & trial_words)

    severity_boost = max((t.severity for t in trials), default=0.5)

    if type_match > 0:
        return min(1.0, 0.5 + 0.2 * type_match + 0.2 * severity_boost)

    # Theme overlap with trial descriptions
    theme_match = sum(1 for t in entry.themes if t.lower() in trial_words)
    if theme_match > 0:
        return min(1.0, 0.4 + 0.15 * theme_match)

    return 0.3


def _quest_alignment(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """How well the wisdom aligns with the seeker's active quests."""
    if not profile.active_quests:
        return 0.5

    quest_domains = {q.domain for q in profile.active_quests}
    quote_domains = set(entry.domains)
    domain_overlap = len(quest_domains & quote_domains)

    if domain_overlap > 0:
        return min(1.0, 0.6 + 0.2 * domain_overlap)

    # Check theme relevance to quest descriptions/why
    quest_words = set()
    for q in profile.active_quests:
        quest_words.update(q.description.lower().split())
        quest_words.update(q.why.lower().split())

    theme_match = sum(1 for t in entry.themes if t.lower() in quest_words)
    if theme_match > 0:
        return min(1.0, 0.4 + 0.15 * theme_match)

    return 0.3


def _temporal_resonance(entry: WisdomEntry, current_hour: int, profile: SeekerProfile) -> float:
    """Match wisdom energy to seeker's time-of-day energy."""
    energy = profile.energy_patterns
    if 5 <= current_hour < 9:
        time_label = "dawn"
        user_energy = energy.dawn
    elif 9 <= current_hour < 12:
        time_label = "midday"
        user_energy = energy.morning
    elif 12 <= current_hour < 17:
        time_label = "midday"
        user_energy = energy.afternoon
    elif 17 <= current_hour < 20:
        time_label = "dusk"
        user_energy = energy.dusk
    else:
        time_label = "dark_night"
        user_energy = energy.night

    # Direct time label match
    if entry.energy_match == time_label:
        return 1.0

    # Low energy → dawn/dusk wisdom preferred
    if user_energy < 0.4 and entry.energy_match in ("dawn", "dusk"):
        return 0.7

    return 0.4


def _novelty(entry: WisdomEntry, seen_ids: set[str]) -> float:
    return 1.0 if entry.id not in seen_ids else 0.0


def _repetition_penalty(entry: WisdomEntry, seen_ids: set[str]) -> float:
    return 1.0 if entry.id in seen_ids else 0.0


def _anti_pattern_match(entry: WisdomEntry, profile: SeekerProfile) -> float:
    """Check if the wisdom matches any anti-patterns the seeker has flagged."""
    user_anti = {ap.lower() for ap in profile.anti_patterns}
    all_anti = user_anti | _BUILTIN_ANTI_PATTERNS

    # Check themes against anti-patterns
    entry_themes = {t.lower() for t in entry.themes}
    if entry_themes & all_anti:
        return 1.0

    # Check challenge types against anti-patterns
    entry_challenges = {ct.lower() for ct in entry.challenge_types}
    if entry_challenges & all_anti:
        return 1.0

    return 0.0
