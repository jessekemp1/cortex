"""Profile manager — seeker lifecycle, season detection, quest/trial management.

Detects inner seasons from behavioral signals. Manages the seeker's path
through quests and trials with the poet-warrior-monk framework.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from motivation.models import (
    DeliveryRhythm,
    InnerSeason,
    LifeDomain,
    Quest,
    QuestStatus,
    SeekerProfile,
    TonePreference,
    Trial,
    TruthLayer,
    WisdomInteraction,
)


class ProfileManager:
    """Manages seeker profiles and detects inner seasons."""

    def __init__(self) -> None:
        self._profiles: dict[str, SeekerProfile] = {}
        self._interactions: dict[str, list[WisdomInteraction]] = {}

    def create_profile(
        self,
        name: str = "",
        core_values: Optional[list[str]] = None,
        aspect_balance: Optional[dict[str, float]] = None,
        tradition_affinity: Optional[dict[str, float]] = None,
        tone_preference: TonePreference = TonePreference.TEMPERED,
        depth_preference: TruthLayer = TruthLayer.STRUCTURAL,
        delivery_rhythm: DeliveryRhythm = DeliveryRhythm.DAWN,
        anti_patterns: Optional[list[str]] = None,
    ) -> SeekerProfile:
        """Create a new seeker profile."""
        profile = SeekerProfile(
            name=name,
            core_values=core_values or ["truth", "discipline", "craft"],
            aspect_balance=aspect_balance or {"poet": 0.33, "warrior": 0.34, "monk": 0.33},
            tradition_affinity=tradition_affinity or {"stoic": 0.7, "zen": 0.5, "existentialist": 0.4},
            tone_preference=tone_preference,
            depth_preference=depth_preference,
            delivery_rhythm=delivery_rhythm,
            anti_patterns=anti_patterns or ["toxic_positivity", "hustle_porn", "spiritual_bypassing"],
        )
        self._profiles[profile.id] = profile
        self._interactions[profile.id] = []
        return profile

    def get_profile(self, seeker_id: str) -> Optional[SeekerProfile]:
        return self._profiles.get(seeker_id)

    def list_profiles(self) -> list[SeekerProfile]:
        return list(self._profiles.values())

    def delete_profile(self, seeker_id: str) -> bool:
        removed = self._profiles.pop(seeker_id, None)
        self._interactions.pop(seeker_id, None)
        return removed is not None

    # --- Quest management ---

    def add_quest(self, seeker_id: str, quest: Quest) -> bool:
        profile = self._profiles.get(seeker_id)
        if not profile:
            return False
        profile.quests.append(quest)
        return True

    def update_quest_status(self, seeker_id: str, quest_id: str, status: QuestStatus) -> bool:
        profile = self._profiles.get(seeker_id)
        if not profile:
            return False
        for quest in profile.quests:
            if quest.id == quest_id:
                quest.status = status
                return True
        return False

    def complete_milestone(self, seeker_id: str, quest_id: str, milestone_id: str) -> bool:
        profile = self._profiles.get(seeker_id)
        if not profile:
            return False
        for quest in profile.quests:
            if quest.id == quest_id:
                for ms in quest.milestones:
                    if ms.id == milestone_id:
                        ms.completed = True
                        ms.completed_date = date.today()
                        return True
        return False

    # --- Trial management ---

    def declare_trial(self, seeker_id: str, trial: Trial) -> bool:
        """Declare a new trial the seeker is facing."""
        profile = self._profiles.get(seeker_id)
        if not profile:
            return False
        profile.current_trials.append(trial)
        return True

    def resolve_trial(
        self, seeker_id: str, trial_id: str, lesson_learned: Optional[str] = None
    ) -> bool:
        """Resolve a trial, optionally recording the lesson."""
        profile = self._profiles.get(seeker_id)
        if not profile:
            return False
        for trial in profile.current_trials:
            if trial.id == trial_id:
                trial.resolved = True
                trial.resolved_date = date.today()
                trial.lesson_learned = lesson_learned
                return True
        return False

    # --- Interaction tracking ---

    def record_interaction(self, interaction: WisdomInteraction) -> None:
        if interaction.seeker_id not in self._interactions:
            self._interactions[interaction.seeker_id] = []
        self._interactions[interaction.seeker_id].append(interaction)

        # Track "hit different" in resonance history
        if interaction.hit_different:
            profile = self._profiles.get(interaction.seeker_id)
            if profile and interaction.wisdom_id not in profile.resonance_history:
                profile.resonance_history.append(interaction.wisdom_id)

    def get_interactions(self, seeker_id: str, limit: int = 50) -> list[WisdomInteraction]:
        interactions = self._interactions.get(seeker_id, [])
        return sorted(interactions, key=lambda i: i.timestamp, reverse=True)[:limit]

    def get_seen_wisdom_ids(self, seeker_id: str) -> set[str]:
        return {i.wisdom_id for i in self._interactions.get(seeker_id, [])}

    # --- Inner Season Detection ---

    def detect_season(self, seeker_id: str) -> InnerSeason:
        """Detect the seeker's inner season from behavioral signals.

        The detection hierarchy:
        1. Dark Night — severe trials + disengagement (most urgent)
        2. Desert — extended low engagement, stalled quests
        3. Summit — breakthroughs, high resonance, milestone completions
        4. Forge — active engagement, steady progress, warrior energy
        5. Consolidation — moderate engagement, reflection-heavy
        6. Drift — sporadic engagement, no active direction
        """
        profile = self._profiles.get(seeker_id)
        if not profile:
            return InnerSeason.UNKNOWN

        interactions = self._interactions.get(seeker_id, [])
        recent = _recent_interactions(interactions, days=7)
        recent_14 = _recent_interactions(interactions, days=14)

        # --- Dark Night: severe trials + dropping engagement ---
        severe_trials = [t for t in profile.active_trials if t.severity >= 0.8]
        if severe_trials and len(recent) <= 2:
            profile.inner_season = InnerSeason.DARK_NIGHT
            return InnerSeason.DARK_NIGHT

        # --- Desert: extended low engagement, stalled quests ---
        stalled_quests = [q for q in profile.active_quests if q.status == QuestStatus.STALLED]
        if len(recent_14) <= 3 and (stalled_quests or not profile.active_quests):
            profile.inner_season = InnerSeason.DESERT
            return InnerSeason.DESERT

        # --- Summit: breakthroughs, high resonance ---
        recent_completions = _recent_milestone_completions(profile, days=7)
        hit_different_count = sum(1 for i in recent if i.hit_different)
        high_ratings = [i for i in recent if i.rating and i.rating >= 4]
        if (recent_completions >= 2 or hit_different_count >= 2) and len(high_ratings) >= 2:
            profile.inner_season = InnerSeason.SUMMIT
            return InnerSeason.SUMMIT

        # --- Forge: consistent engagement, progress ---
        if len(recent) >= 5 and _avg_rating(recent) >= 3.5:
            walking_quests = [q for q in profile.active_quests if q.status == QuestStatus.WALKING]
            if walking_quests:
                profile.inner_season = InnerSeason.FORGE
                return InnerSeason.FORGE

        # --- Drift: sporadic, no direction ---
        if len(recent) <= 1 and len(interactions) > 5:
            questioning = [q for q in profile.active_quests if q.status == QuestStatus.QUESTIONING]
            if not profile.active_quests or questioning:
                profile.inner_season = InnerSeason.DRIFT
                return InnerSeason.DRIFT

        # --- Consolidation: moderate engagement, reflective ---
        saved_count = sum(1 for i in recent if i.saved_to_commonplace)
        reflection_count = sum(1 for i in recent if i.reflection)
        if saved_count >= 2 or reflection_count >= 2:
            profile.inner_season = InnerSeason.CONSOLIDATION
            return InnerSeason.CONSOLIDATION

        # Default to forge if there's any engagement
        if recent:
            profile.inner_season = InnerSeason.FORGE
            return InnerSeason.FORGE

        profile.inner_season = InnerSeason.UNKNOWN
        return InnerSeason.UNKNOWN


def _recent_interactions(
    interactions: list[WisdomInteraction], days: int = 7
) -> list[WisdomInteraction]:
    cutoff = datetime.now() - timedelta(days=days)
    return [i for i in interactions if i.timestamp >= cutoff]


def _avg_rating(interactions: list[WisdomInteraction]) -> float:
    rated = [i for i in interactions if i.rating is not None]
    if not rated:
        return 0.0
    return sum(i.rating for i in rated) / len(rated)


def _recent_milestone_completions(profile: SeekerProfile, days: int = 7) -> int:
    cutoff = date.today() - timedelta(days=days)
    count = 0
    for quest in profile.quests:
        for ms in quest.milestones:
            if ms.completed and ms.completed_date and ms.completed_date >= cutoff:
                count += 1
    return count
