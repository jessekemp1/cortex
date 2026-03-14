"""Kempion API — FastAPI endpoints for the wisdom engine.

All endpoints are prefixed with /api/kempion.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from motivation.delivery import DeliveryManager
from motivation.learning import LearningManager
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
from motivation.potential import PotentialTracker
from motivation.profile_manager import ProfileManager
from motivation.quote_database import WisdomDatabase
from motivation.quote_engine import WisdomEngine


class KempionApp:
    """Main application container wiring all Kempion components together.

    This can be mounted into a FastAPI app or used standalone.
    """

    def __init__(self) -> None:
        self.database = WisdomDatabase()
        self.engine = WisdomEngine(self.database)
        self.profiles = ProfileManager()
        self.delivery = DeliveryManager(self.engine)
        self.learning = LearningManager(self.engine)
        self.potential = PotentialTracker()

    def initialize(self) -> int:
        """Load seed data and return count of wisdom entries loaded."""
        return self.database.load_from_seed_data()

    # --- Profile operations ---

    def create_seeker(
        self,
        name: str = "",
        core_values: Optional[list[str]] = None,
        tone_preference: str = "tempered",
        depth_preference: str = "structural",
        tradition_affinity: Optional[dict[str, float]] = None,
    ) -> SeekerProfile:
        return self.profiles.create_profile(
            name=name,
            core_values=core_values,
            tone_preference=TonePreference(tone_preference),
            depth_preference=TruthLayer(depth_preference),
            tradition_affinity=tradition_affinity,
        )

    def get_seeker(self, seeker_id: str) -> Optional[SeekerProfile]:
        return self.profiles.get_profile(seeker_id)

    # --- Quest operations ---

    def add_quest(
        self,
        seeker_id: str,
        description: str,
        domain: str = "craft",
        why: str = "",
    ) -> Optional[Quest]:
        quest = Quest(description=description, domain=LifeDomain(domain), why=why)
        if self.profiles.add_quest(seeker_id, quest):
            return quest
        return None

    def update_quest_status(self, seeker_id: str, quest_id: str, status: str) -> bool:
        return self.profiles.update_quest_status(seeker_id, quest_id, QuestStatus(status))

    # --- Trial operations ---

    def declare_trial(
        self,
        seeker_id: str,
        description: str,
        severity: float = 0.5,
        domain: str = "mind",
        truth_beneath: str = "",
    ) -> Optional[Trial]:
        trial = Trial(
            description=description,
            severity=severity,
            domain=LifeDomain(domain),
            truth_beneath=truth_beneath,
        )
        if self.profiles.declare_trial(seeker_id, trial):
            return trial
        return None

    def resolve_trial(self, seeker_id: str, trial_id: str, lesson: str = "") -> bool:
        return self.profiles.resolve_trial(seeker_id, trial_id, lesson or None)

    # --- Wisdom delivery ---

    def get_wisdom(self, seeker_id: str) -> Optional[dict]:
        profile = self.profiles.get_profile(seeker_id)
        if not profile:
            return None

        seen = self.profiles.get_seen_wisdom_ids(seeker_id)
        delivered = self.delivery.deliver_wisdom(profile, seen_ids=seen)
        if not delivered:
            return None

        return {
            "wisdom_id": delivered.wisdom.id,
            "text": delivered.wisdom.text,
            "author": delivered.wisdom.author,
            "source": delivered.wisdom.source,
            "tradition": delivered.wisdom.tradition,
            "aspect": delivered.wisdom.aspect.value,
            "formatted": delivered.formatted_text,
            "context_note": delivered.context_note,
            "reflection_prompt": delivered.reflection_prompt,
            "companion_text": delivered.companion_text,
            "score": delivered.score,
        }

    def rate_wisdom(
        self,
        seeker_id: str,
        wisdom_id: str,
        rating: Optional[int] = None,
        hit_different: bool = False,
        saved: bool = False,
        reflection: Optional[str] = None,
    ) -> bool:
        wisdom = self.database.get(wisdom_id)
        if not wisdom:
            return False

        profile = self.profiles.get_profile(seeker_id)
        if not profile:
            return False

        interaction = WisdomInteraction(
            wisdom_id=wisdom_id,
            seeker_id=seeker_id,
            rating=rating,
            hit_different=hit_different,
            saved_to_commonplace=saved,
            reflection=reflection,
            inner_season_at_time=profile.inner_season,
        )

        self.profiles.record_interaction(interaction)
        self.learning.process_interaction(
            interaction,
            wisdom_themes=wisdom.themes,
            wisdom_tradition=wisdom.tradition,
        )
        return True

    # --- Briefings ---

    def get_dawn_briefing(self, seeker_id: str) -> Optional[dict]:
        profile = self.profiles.get_profile(seeker_id)
        if not profile:
            return None

        # Detect current season
        self.profiles.detect_season(seeker_id)

        seen = self.profiles.get_seen_wisdom_ids(seeker_id)
        briefing = self.delivery.generate_dawn_briefing(profile, seen_ids=seen)
        if not briefing:
            return None

        return {
            "greeting": briefing.greeting,
            "wisdom": {
                "text": briefing.primary_wisdom.wisdom.text,
                "author": briefing.primary_wisdom.wisdom.author,
                "formatted": briefing.primary_wisdom.formatted_text,
                "reflection_prompt": briefing.primary_wisdom.reflection_prompt,
            },
            "focus_prompt": briefing.focus_prompt,
            "active_quests": briefing.active_quests_summary,
            "active_trials": briefing.active_trials_summary,
            "inner_season": briefing.inner_season.value,
        }

    # --- Season detection ---

    def detect_season(self, seeker_id: str) -> Optional[str]:
        season = self.profiles.detect_season(seeker_id)
        return season.value

    # --- Resonance stats ---

    def get_resonance_stats(self, seeker_id: str) -> Optional[dict]:
        interactions = self.profiles.get_interactions(seeker_id, limit=200)
        stats = self.learning.get_resonance_stats(seeker_id, interactions)
        return asdict(stats)

    # --- Potential ---

    def initialize_potential(self, seeker_id: str) -> Optional[dict]:
        profile = self.profiles.get_profile(seeker_id)
        if not profile:
            return None
        potential_map = self.potential.initialize_map(profile)
        return {
            "overall_score": potential_map.overall_score(),
            "domains": {
                k: {"current": d.current_level, "target": d.target_level, "gap": d.gap}
                for k, d in potential_map.domains.items()
            },
        }
