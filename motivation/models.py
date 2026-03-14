"""Core data models for the Kempion Wisdom Engine.

Built around the poet-warrior-monk archetype, base truth seeking,
and stoic-flavored wisdom traditions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


# --- Core Enums ---


class LifeDomain(Enum):
    """Life domains where growth happens."""

    CRAFT = "craft"  # Work, creation, building
    BODY = "body"  # Health, physical discipline
    BONDS = "bonds"  # Relationships, community
    MIND = "mind"  # Learning, understanding, clarity
    SPIRIT = "spirit"  # Meaning, purpose, transcendence
    WEALTH = "wealth"  # Financial sovereignty
    EXPRESSION = "expression"  # Art, writing, creative output


class Aspect(Enum):
    """The three aspects of the poet-warrior-monk."""

    POET = "poet"  # Sees clearly, names things, finds beauty in difficulty
    WARRIOR = "warrior"  # Acts despite uncertainty, embraces discipline
    MONK = "monk"  # Sits with discomfort, seeks understanding
    POET_WARRIOR = "poet_warrior"
    WARRIOR_MONK = "warrior_monk"
    POET_MONK = "poet_monk"
    ALL = "all"  # All three at full depth


class InnerSeason(Enum):
    """The seeker's inner season — replaces generic 'motivational state'."""

    FORGE = "forge"  # Active building, grinding, creating under pressure
    DESERT = "desert"  # Dry spell, nothing working, faith tested
    SUMMIT = "summit"  # Peak — things clicking, breakthroughs
    CONSOLIDATION = "consolidation"  # Integrating gains, building foundations
    DRIFT = "drift"  # Lost thread, disconnected from purpose
    DARK_NIGHT = "dark_night"  # Deep crisis, existential weight
    UNKNOWN = "unknown"


class TruthLayer(Enum):
    """Depth layer of a piece of wisdom."""

    SURFACE = "surface"  # Obvious, immediately actionable
    STRUCTURAL = "structural"  # About systems, habits, patterns
    ROOT = "root"  # About identity, belief, meaning
    PARADOX = "paradox"  # Truths that seem contradictory but aren't
    SILENCE = "silence"  # Beyond words — points at what can't be said


class TonePreference(Enum):
    """How the seeker prefers wisdom delivered."""

    SEVERE = "severe"  # Hard truth, no padding
    TEMPERED = "tempered"  # Firm but compassionate
    GENTLE = "gentle"  # Soft, patient, inviting


class QuestStatus(Enum):
    """Status of a quest on the path."""

    WALKING = "walking"  # Actively pursuing
    STALLED = "stalled"  # Stuck, not moving
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    QUESTIONING = "questioning"  # Unsure if this is the right quest


class DeliveryRhythm(Enum):
    """When wisdom should be delivered."""

    DAWN = "dawn"  # Morning delivery
    MIDDAY = "midday"
    DUSK = "dusk"  # Evening reflection
    ON_DEMAND = "on_demand"  # Only when asked


# --- Core Data Structures ---


@dataclass
class ToneVector:
    """Numeric representation of wisdom tone."""

    severity: float = 0.5  # 0=gentle, 1=fierce
    warmth: float = 0.5  # 0=cold/austere, 1=warm/compassionate
    directness: float = 0.5  # 0=poetic/oblique, 1=blunt/plain

    def distance_to(self, other: ToneVector) -> float:
        """Euclidean distance between two tone vectors."""
        return (
            (self.severity - other.severity) ** 2
            + (self.warmth - other.warmth) ** 2
            + (self.directness - other.directness) ** 2
        ) ** 0.5


@dataclass
class Milestone:
    """A milestone within a quest."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    target_date: Optional[date] = None
    completed: bool = False
    completed_date: Optional[date] = None


@dataclass
class Quest:
    """A goal reframed as a quest — something the seeker walks toward."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""  # "Build the product that matters"
    domain: LifeDomain = LifeDomain.CRAFT
    why: str = ""  # The deeper reason — base truth of the quest
    milestones: list[Milestone] = field(default_factory=list)
    deadline: Optional[date] = None
    status: QuestStatus = QuestStatus.WALKING
    blockers: list[str] = field(default_factory=list)
    created: date = field(default_factory=date.today)

    @property
    def progress(self) -> float:
        if not self.milestones:
            return 0.0
        return sum(1 for m in self.milestones if m.completed) / len(self.milestones)


@dataclass
class Trial:
    """A challenge reframed as a trial — something the seeker must face."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""  # "Discipline is collapsing under pressure"
    severity: float = 0.5  # 0.0-1.0
    domain: LifeDomain = LifeDomain.MIND
    truth_beneath: str = ""  # "I'm afraid it won't be good enough"
    related_quest_ids: list[str] = field(default_factory=list)
    what_ive_tried: list[str] = field(default_factory=list)
    started: date = field(default_factory=date.today)
    resolved: bool = False
    resolved_date: Optional[date] = None
    lesson_learned: Optional[str] = None  # What the trial taught


@dataclass
class WisdomEntry:
    """A piece of wisdom — quote, verse, passage — fully taxonomized."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str = ""
    author: str = "Unknown"
    source: Optional[str] = None  # Book, letter, speech, poem
    tradition: str = "stoic"  # stoic, zen, existentialist, poetic, martial, pragmatist, contemplative
    era: str = "ancient"  # ancient, medieval, modern, contemporary

    # Kempion taxonomy
    aspect: Aspect = Aspect.ALL
    truth_layer: TruthLayer = TruthLayer.STRUCTURAL
    themes: list[str] = field(default_factory=list)
    domains: list[LifeDomain] = field(default_factory=list)
    tone: ToneVector = field(default_factory=ToneVector)

    # Contextual matching
    best_for_seasons: list[InnerSeason] = field(default_factory=list)
    challenge_types: list[str] = field(default_factory=list)
    energy_match: str = "midday"  # dawn, midday, dusk, dark_night

    # Depth
    requires_context: bool = False
    companion_text: Optional[str] = None  # Framing for depth quotes
    paradox_pair_id: Optional[str] = None  # Links to opposing truth

    is_generated: bool = False  # True if LLM-generated


@dataclass
class WisdomInteraction:
    """Record of a seeker's encounter with a piece of wisdom."""

    wisdom_id: str = ""
    seeker_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    rating: Optional[int] = None  # 1-5
    hit_different: bool = False  # The highest signal
    skipped: bool = False
    saved_to_commonplace: bool = False
    reflection: Optional[str] = None  # Personal annotation
    inner_season_at_time: InnerSeason = InnerSeason.UNKNOWN


@dataclass
class EnergyPattern:
    """Time-of-day energy/receptivity mapping."""

    dawn: float = 0.7  # 5am-9am — fresh, receptive
    morning: float = 0.6  # 9am-12pm — active, building
    afternoon: float = 0.4  # 12pm-5pm — grinding, fatigued
    dusk: float = 0.6  # 5pm-8pm — reflective
    night: float = 0.3  # 8pm-5am — deep, quiet


@dataclass
class SeekerProfile:
    """The seeker's complete profile — who they are, where they walk."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    created: datetime = field(default_factory=datetime.now)

    # The Three Aspects — personal balance
    aspect_balance: dict[str, float] = field(
        default_factory=lambda: {"poet": 0.33, "warrior": 0.34, "monk": 0.33}
    )

    # Values & Affinities
    core_values: list[str] = field(default_factory=list)  # truth, craft, endurance...
    tradition_affinity: dict[str, float] = field(
        default_factory=lambda: {"stoic": 0.7, "zen": 0.5, "existentialist": 0.4}
    )

    # The Path
    quests: list[Quest] = field(default_factory=list)
    current_trials: list[Trial] = field(default_factory=list)
    inner_season: InnerSeason = InnerSeason.UNKNOWN

    # Preferences
    tone_preference: TonePreference = TonePreference.TEMPERED
    depth_preference: TruthLayer = TruthLayer.STRUCTURAL
    delivery_rhythm: DeliveryRhythm = DeliveryRhythm.DAWN
    energy_patterns: EnergyPattern = field(default_factory=EnergyPattern)

    # Learned over time
    trigger_words: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(
        default_factory=lambda: ["toxic_positivity", "hustle_porn", "spiritual_bypassing"]
    )
    resonance_history: list[str] = field(default_factory=list)  # Wisdom IDs that hit different

    @property
    def active_trials(self) -> list[Trial]:
        return [t for t in self.current_trials if not t.resolved]

    @property
    def active_quests(self) -> list[Quest]:
        return [
            q for q in self.quests
            if q.status not in (QuestStatus.COMPLETED, QuestStatus.ABANDONED)
        ]

    @property
    def dominant_aspect(self) -> str:
        """Which aspect currently leads."""
        if not self.aspect_balance:
            return "warrior"
        return max(self.aspect_balance, key=self.aspect_balance.get)

    @property
    def top_domains(self) -> list[LifeDomain]:
        """Domains with active quests, ordered by quest count."""
        domain_counts: dict[LifeDomain, int] = {}
        for q in self.active_quests:
            domain_counts[q.domain] = domain_counts.get(q.domain, 0) + 1
        return sorted(domain_counts, key=domain_counts.get, reverse=True)


# --- Potential & Growth ---


@dataclass
class DomainPotential:
    """Potential assessment for a single life domain."""

    domain: LifeDomain = LifeDomain.MIND
    current_level: float = 0.0
    target_level: float = 1.0
    growth_velocity: float = 0.0
    limiting_beliefs: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    wisdom_themes_needed: list[str] = field(default_factory=list)

    @property
    def gap(self) -> float:
        return max(0.0, self.target_level - self.current_level)


@dataclass
class PotentialSnapshot:
    """Point-in-time snapshot of potential levels."""

    timestamp: datetime = field(default_factory=datetime.now)
    domain_levels: dict[str, float] = field(default_factory=dict)
    inner_season: InnerSeason = InnerSeason.UNKNOWN


@dataclass
class GrowthPattern:
    """A detected pattern in the seeker's growth trajectory."""

    description: str = ""
    domain: LifeDomain = LifeDomain.MIND
    trend: str = "stable"  # improving | stable | declining
    confidence: float = 0.5


@dataclass
class PotentialMap:
    """Full potential map across all domains."""

    seeker_id: str = ""
    domains: dict[str, DomainPotential] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

    def overall_score(self) -> float:
        if not self.domains:
            return 0.0
        return sum(d.current_level for d in self.domains.values()) / len(self.domains)


@dataclass
class GrowthTrajectory:
    """Tracks growth over time with pattern detection."""

    seeker_id: str = ""
    snapshots: list[PotentialSnapshot] = field(default_factory=list)
    patterns: list[GrowthPattern] = field(default_factory=list)
    inflection_points: list[dict] = field(default_factory=list)
    wisdom_correlations: dict[str, float] = field(default_factory=dict)
