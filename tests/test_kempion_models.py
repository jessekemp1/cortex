"""Tests for Kempion data models."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motivation.models import (
    Aspect,
    DomainPotential,
    GrowthTrajectory,
    InnerSeason,
    LifeDomain,
    Milestone,
    PotentialMap,
    Quest,
    QuestStatus,
    SeekerProfile,
    TonePreference,
    ToneVector,
    Trial,
    TruthLayer,
    WisdomEntry,
    WisdomInteraction,
)


class TestToneVector:
    def test_distance_to_same(self):
        a = ToneVector(0.5, 0.5, 0.5)
        assert a.distance_to(a) == 0.0

    def test_distance_to_different(self):
        a = ToneVector(0.0, 0.0, 0.0)
        b = ToneVector(1.0, 1.0, 1.0)
        dist = a.distance_to(b)
        assert 1.7 < dist < 1.8  # sqrt(3) ≈ 1.732

    def test_distance_symmetry(self):
        a = ToneVector(0.2, 0.8, 0.5)
        b = ToneVector(0.7, 0.3, 0.9)
        assert abs(a.distance_to(b) - b.distance_to(a)) < 1e-10


class TestQuest:
    def test_progress_no_milestones(self):
        quest = Quest(description="Test")
        assert quest.progress == 0.0

    def test_progress_partial(self):
        quest = Quest(
            description="Test",
            milestones=[
                Milestone(description="A", completed=True),
                Milestone(description="B", completed=False),
            ],
        )
        assert quest.progress == 0.5

    def test_progress_complete(self):
        quest = Quest(
            description="Test",
            milestones=[
                Milestone(description="A", completed=True),
                Milestone(description="B", completed=True),
            ],
        )
        assert quest.progress == 1.0


class TestSeekerProfile:
    def test_active_trials(self):
        profile = SeekerProfile(
            current_trials=[
                Trial(description="A", resolved=False),
                Trial(description="B", resolved=True),
                Trial(description="C", resolved=False),
            ]
        )
        assert len(profile.active_trials) == 2

    def test_active_quests(self):
        profile = SeekerProfile(
            quests=[
                Quest(description="Walking", status=QuestStatus.WALKING),
                Quest(description="Done", status=QuestStatus.COMPLETED),
                Quest(description="Stalled", status=QuestStatus.STALLED),
            ]
        )
        assert len(profile.active_quests) == 2

    def test_dominant_aspect(self):
        profile = SeekerProfile(
            aspect_balance={"poet": 0.5, "warrior": 0.3, "monk": 0.2}
        )
        assert profile.dominant_aspect == "poet"

    def test_top_domains(self):
        profile = SeekerProfile(
            quests=[
                Quest(description="A", domain=LifeDomain.CRAFT, status=QuestStatus.WALKING),
                Quest(description="B", domain=LifeDomain.CRAFT, status=QuestStatus.WALKING),
                Quest(description="C", domain=LifeDomain.MIND, status=QuestStatus.WALKING),
            ]
        )
        domains = profile.top_domains
        assert domains[0] == LifeDomain.CRAFT

    def test_default_anti_patterns(self):
        profile = SeekerProfile()
        assert "toxic_positivity" in profile.anti_patterns
        assert "hustle_porn" in profile.anti_patterns
        assert "spiritual_bypassing" in profile.anti_patterns


class TestDomainPotential:
    def test_gap(self):
        dp = DomainPotential(current_level=0.3, target_level=0.8)
        assert abs(dp.gap - 0.5) < 1e-10

    def test_gap_exceeded(self):
        dp = DomainPotential(current_level=0.9, target_level=0.8)
        assert dp.gap == 0.0


class TestPotentialMap:
    def test_overall_score(self):
        pm = PotentialMap(
            domains={
                "craft": DomainPotential(current_level=0.6),
                "mind": DomainPotential(current_level=0.8),
            }
        )
        assert abs(pm.overall_score() - 0.7) < 1e-10

    def test_overall_score_empty(self):
        pm = PotentialMap()
        assert pm.overall_score() == 0.0


class TestWisdomEntry:
    def test_default_values(self):
        entry = WisdomEntry(text="Test", author="Author")
        assert entry.aspect == Aspect.ALL
        assert entry.truth_layer == TruthLayer.STRUCTURAL
        assert entry.is_generated is False

    def test_paradox_pair(self):
        entry = WisdomEntry(text="A", paradox_pair_id="xyz")
        assert entry.paradox_pair_id == "xyz"
