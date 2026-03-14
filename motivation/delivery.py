"""Kempion delivery system — dawn briefings, trial mode, and wisdom formatting.

Delivers wisdom in the voice of the poet-warrior-monk. No hype.
No sugar. Just the truth that serves this moment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from motivation.models import (
    InnerSeason,
    SeekerProfile,
    WisdomEntry,
)
from motivation.quote_engine import ScoredWisdom, WisdomEngine


@dataclass
class DeliveredWisdom:
    """A piece of wisdom packaged for delivery."""

    wisdom: WisdomEntry
    formatted_text: str
    context_note: Optional[str] = None
    reflection_prompt: Optional[str] = None
    companion_text: Optional[str] = None
    score: float = 0.0
    delivered_at: datetime = field(default_factory=datetime.now)


@dataclass
class DawnBriefing:
    """The seeker's daily wisdom briefing."""

    greeting: str
    primary_wisdom: DeliveredWisdom
    focus_prompt: str
    active_quests_summary: list[str]
    active_trials_summary: list[str]
    inner_season: InnerSeason
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TrialSequence:
    """A curated sequence of wisdom for trial mode."""

    trial_description: str
    truth_beneath: str
    wisdom_entries: list[DeliveredWisdom]  # Poet → Warrior → Monk escalation
    micro_challenges: list[str]
    closing_reflection: str


@dataclass
class ParadoxDelivery:
    """Two opposing truths delivered together."""

    first: DeliveredWisdom
    second: DeliveredWisdom
    framing: str  # "Hold both of these..."


class DeliveryManager:
    """Manages wisdom delivery in the Kempion voice."""

    def __init__(self, engine: WisdomEngine) -> None:
        self.engine = engine

    def deliver_wisdom(
        self,
        profile: SeekerProfile,
        seen_ids: Optional[set[str]] = None,
    ) -> Optional[DeliveredWisdom]:
        """Select and format wisdom for the seeker."""
        scored = self.engine.select_wisdom(profile, seen_ids=seen_ids)
        if not scored:
            return None

        return _package_wisdom(scored, profile)

    def generate_dawn_briefing(
        self,
        profile: SeekerProfile,
        seen_ids: Optional[set[str]] = None,
    ) -> Optional[DawnBriefing]:
        """Generate the seeker's dawn briefing."""
        delivered = self.deliver_wisdom(profile, seen_ids=seen_ids)
        if not delivered:
            return None

        greeting = _season_greeting(profile.inner_season)
        quests = [
            f"{q.description} [{q.status.value}]" for q in profile.active_quests[:5]
        ]
        trials = [
            f"{t.description} (severity: {t.severity:.1f})"
            for t in profile.active_trials[:3]
        ]

        return DawnBriefing(
            greeting=greeting,
            primary_wisdom=delivered,
            focus_prompt=_focus_prompt(profile),
            active_quests_summary=quests,
            active_trials_summary=trials,
            inner_season=profile.inner_season,
        )

    def generate_trial_sequence(
        self,
        profile: SeekerProfile,
        trial_description: str,
        truth_beneath: str = "",
        num_entries: int = 3,
        seen_ids: Optional[set[str]] = None,
    ) -> Optional[TrialSequence]:
        """Generate a poet → warrior → monk wisdom sequence for a trial."""
        seen = set(seen_ids or set())
        entries: list[DeliveredWisdom] = []

        for _ in range(num_entries):
            delivered = self.deliver_wisdom(profile, seen_ids=seen)
            if delivered:
                entries.append(delivered)
                seen.add(delivered.wisdom.id)

        if not entries:
            return None

        return TrialSequence(
            trial_description=trial_description,
            truth_beneath=truth_beneath,
            wisdom_entries=entries,
            micro_challenges=_trial_micro_challenges(trial_description, num_entries),
            closing_reflection=f"You faced '{trial_description}' today. What did the trial teach you?",
        )

    def deliver_paradox_pair(
        self,
        profile: SeekerProfile,
        seen_ids: Optional[set[str]] = None,
    ) -> Optional[ParadoxDelivery]:
        """Deliver two opposing truths together."""
        result = self.engine.select_paradox_pair(profile, seen_ids=seen_ids)
        if not result:
            return None

        scored_first, partner = result
        first = _package_wisdom(scored_first, profile)
        second = DeliveredWisdom(
            wisdom=partner,
            formatted_text=format_wisdom(partner),
            score=0.0,
        )

        return ParadoxDelivery(
            first=first,
            second=second,
            framing="Hold both of these. The truth is in the space between.",
        )


def format_wisdom(entry: WisdomEntry) -> str:
    """Format a wisdom entry for display."""
    text = f'"{entry.text}"'
    attribution = f"-- {entry.author}"
    if entry.source:
        attribution += f", {entry.source}"
    return f"{text}\n\n{attribution}"


def _package_wisdom(scored: ScoredWisdom, profile: SeekerProfile) -> DeliveredWisdom:
    """Package a scored wisdom entry for delivery."""
    wisdom = scored.wisdom
    return DeliveredWisdom(
        wisdom=wisdom,
        formatted_text=format_wisdom(wisdom),
        context_note=_context_note(wisdom, profile),
        reflection_prompt=_reflection_prompt(profile),
        companion_text=wisdom.companion_text,
        score=scored.total_score,
    )


def _context_note(wisdom: WisdomEntry, profile: SeekerProfile) -> Optional[str]:
    """Generate a brief note connecting the wisdom to the seeker's path."""
    matching_quests = [
        q for q in profile.active_quests if q.domain in wisdom.domains
    ]
    if matching_quests:
        return f"For your quest: {matching_quests[0].description}"

    matching_trials = [
        t for t in profile.active_trials
        if any(ct.lower() in t.description.lower() for ct in wisdom.challenge_types)
    ]
    if matching_trials:
        return f"For what you're facing: {matching_trials[0].description}"

    return None


def _reflection_prompt(profile: SeekerProfile) -> str:
    """Generate a reflection prompt based on the seeker's inner season."""
    prompts = {
        InnerSeason.FORGE: "What will you forge today with this fire?",
        InnerSeason.DESERT: "What is the desert trying to teach you?",
        InnerSeason.SUMMIT: "What can you see from up here that you couldn't before?",
        InnerSeason.CONSOLIDATION: "What foundation are you building right now?",
        InnerSeason.DRIFT: "What originally called you to the path?",
        InnerSeason.DARK_NIGHT: "What is one thing within your power right now?",
    }
    return prompts.get(profile.inner_season, "What is the base truth of this moment?")


def _season_greeting(season: InnerSeason) -> str:
    greetings = {
        InnerSeason.FORGE: "The fire is hot. Good. Let's shape something.",
        InnerSeason.DESERT: "The desert strips away everything that isn't essential. Trust the process.",
        InnerSeason.SUMMIT: "You've earned this view. Take it in, then look for the next peak.",
        InnerSeason.CONSOLIDATION: "Roots before branches. You're building something that lasts.",
        InnerSeason.DRIFT: "You're here. That's the first step back. Welcome.",
        InnerSeason.DARK_NIGHT: "This is the hardest ground. But you're still standing.",
        InnerSeason.UNKNOWN: "Another day on the path. Let's walk.",
    }
    return greetings.get(season, "Another day on the path. Let's walk.")


def _focus_prompt(profile: SeekerProfile) -> str:
    if profile.active_trials:
        top_trial = max(profile.active_trials, key=lambda t: t.severity)
        return f"What is one true thing you can do today about '{top_trial.description}'?"
    if profile.active_quests:
        return f"What is one step toward '{profile.active_quests[0].description}' today?"
    return "What is the one thing that matters most today?"


def _trial_micro_challenges(description: str, count: int) -> list[str]:
    templates = [
        f"The Poet's task: Write one honest sentence about '{description}'.",
        f"The Warrior's task: Take one concrete action toward '{description}', however small.",
        f"The Monk's task: Sit with '{description}' for 5 minutes without trying to fix it.",
        f"Name the fear beneath '{description}'. Say it out loud.",
        f"Find one person who has walked through something like '{description}'. Learn from them.",
    ]
    return templates[:count]
