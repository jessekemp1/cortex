"""Tests for the Kempion wisdom engine, database, and delivery system."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motivation.models import (
    Aspect,
    InnerSeason,
    LifeDomain,
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
from motivation.quote_database import WisdomDatabase
from motivation.quote_engine import WisdomEngine, ScoredWisdom
from motivation.delivery import DeliveryManager, format_wisdom
from motivation.profile_manager import ProfileManager
from motivation.learning import LearningManager
from motivation.potential import PotentialTracker


def _make_wisdom(**kwargs) -> WisdomEntry:
    defaults = {
        "text": "Test wisdom",
        "author": "Test Author",
        "tradition": "stoic",
        "aspect": Aspect.WARRIOR,
        "truth_layer": TruthLayer.STRUCTURAL,
        "themes": ["discipline"],
        "domains": [LifeDomain.CRAFT],
        "best_for_seasons": [InnerSeason.FORGE],
        "challenge_types": ["stagnation"],
        "energy_match": "dawn",
    }
    defaults.update(kwargs)
    return WisdomEntry(**defaults)


def _make_profile(**kwargs) -> SeekerProfile:
    defaults = {
        "core_values": ["truth", "discipline"],
        "tradition_affinity": {"stoic": 0.8, "zen": 0.5},
        "tone_preference": TonePreference.TEMPERED,
        "depth_preference": TruthLayer.STRUCTURAL,
        "inner_season": InnerSeason.FORGE,
        "aspect_balance": {"poet": 0.3, "warrior": 0.4, "monk": 0.3},
    }
    defaults.update(kwargs)
    return SeekerProfile(**defaults)


class TestWisdomDatabase:
    def test_add_and_get(self):
        db = WisdomDatabase()
        entry = _make_wisdom(text="Test")
        db.add(entry)
        assert db.get(entry.id) is entry
        assert len(db) == 1

    def test_remove(self):
        db = WisdomDatabase()
        entry = _make_wisdom()
        db.add(entry)
        assert db.remove(entry.id) is True
        assert db.get(entry.id) is None
        assert len(db) == 0

    def test_by_aspect(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(aspect=Aspect.WARRIOR))
        db.add(_make_wisdom(aspect=Aspect.MONK))
        db.add(_make_wisdom(aspect=Aspect.ALL))
        results = db.by_aspect(Aspect.WARRIOR)
        # Should include WARRIOR + ALL
        assert len(results) == 2

    def test_by_tradition(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(tradition="stoic"))
        db.add(_make_wisdom(tradition="zen"))
        assert len(db.by_tradition("stoic")) == 1
        assert len(db.by_tradition("Stoic")) == 1  # case insensitive

    def test_by_season(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(best_for_seasons=[InnerSeason.FORGE]))
        db.add(_make_wisdom(best_for_seasons=[InnerSeason.DESERT]))
        assert len(db.by_season(InnerSeason.FORGE)) == 1

    def test_by_theme(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(themes=["discipline", "courage"]))
        db.add(_make_wisdom(themes=["patience"]))
        assert len(db.by_theme("discipline")) == 1

    def test_search_multi_filter(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(
            tradition="stoic",
            themes=["discipline"],
            best_for_seasons=[InnerSeason.FORGE],
        ))
        db.add(_make_wisdom(
            tradition="zen",
            themes=["discipline"],
            best_for_seasons=[InnerSeason.FORGE],
        ))
        results = db.search(themes=["discipline"], tradition="stoic")
        assert len(results) == 1

    def test_search_exclude_ids(self):
        db = WisdomDatabase()
        w1 = _make_wisdom()
        w2 = _make_wisdom()
        db.add(w1)
        db.add(w2)
        results = db.search(exclude_ids={w1.id})
        assert len(results) == 1
        assert results[0].id == w2.id

    def test_paradox_pair(self):
        db = WisdomDatabase()
        w1 = _make_wisdom(paradox_pair_id="pair-2")
        w2 = WisdomEntry(id="pair-2", text="Opposite", paradox_pair_id=w1.id)
        db.add(w1)
        db.add(w2)
        partner = db.get_paradox_pair(w1.id)
        assert partner is w2
        pairs = db.all_paradox_pairs()
        assert len(pairs) == 1

    def test_load_seed_data(self):
        db = WisdomDatabase()
        seed_path = Path(__file__).parent.parent / "motivation" / "data" / "quotes.json"
        if seed_path.exists():
            count = db.load_from_seed_data(seed_path)
            assert count > 0
            assert len(db) == count

    def test_by_tone_proximity(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(tone=ToneVector(0.5, 0.5, 0.5)))
        db.add(_make_wisdom(tone=ToneVector(0.9, 0.1, 0.9)))
        target = ToneVector(0.5, 0.5, 0.5)
        results = db.by_tone_proximity(target, max_distance=0.2)
        assert len(results) == 1


class TestWisdomEngine:
    def _setup_engine(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(
            text="Forge wisdom",
            tradition="stoic",
            aspect=Aspect.WARRIOR,
            themes=["discipline"],
            best_for_seasons=[InnerSeason.FORGE],
            tone=ToneVector(0.5, 0.5, 0.6),
        ))
        db.add(_make_wisdom(
            text="Desert wisdom",
            tradition="zen",
            aspect=Aspect.MONK,
            themes=["patience"],
            best_for_seasons=[InnerSeason.DESERT],
            tone=ToneVector(0.2, 0.8, 0.3),
        ))
        return WisdomEngine(db)

    def test_select_wisdom_returns_result(self):
        engine = self._setup_engine()
        profile = _make_profile(inner_season=InnerSeason.FORGE)
        result = engine.select_wisdom(profile)
        assert result is not None
        assert isinstance(result, ScoredWisdom)
        assert result.total_score > 0

    def test_season_affects_selection(self):
        engine = self._setup_engine()

        forge_profile = _make_profile(inner_season=InnerSeason.FORGE)
        desert_profile = _make_profile(inner_season=InnerSeason.DESERT)

        forge_scores = engine.score_all(forge_profile)
        desert_scores = engine.score_all(desert_profile)

        # The forge wisdom should score higher for forge profile
        forge_wisdom_in_forge = next(
            s for s in forge_scores if s.wisdom.text == "Forge wisdom"
        )
        forge_wisdom_in_desert = next(
            s for s in desert_scores if s.wisdom.text == "Forge wisdom"
        )
        assert forge_wisdom_in_forge.total_score > forge_wisdom_in_desert.total_score

    def test_seen_ids_penalized(self):
        engine = self._setup_engine()
        profile = _make_profile()
        all_scores = engine.score_all(profile)
        first_id = all_scores[0].wisdom.id
        seen_scores = engine.score_all(profile, seen_ids={first_id})
        first_rescore = next(s for s in seen_scores if s.wisdom.id == first_id)
        assert first_rescore.total_score < all_scores[0].total_score

    def test_resonance_update(self):
        engine = self._setup_engine()
        profile = _make_profile()
        wisdom = engine.database.all_entries()[0]
        engine.update_resonance(profile.id, wisdom.id, 0.95)
        score = engine._resonance_score(profile.id, wisdom.id)
        assert score == 0.95

    def test_score_breakdown_has_all_components(self):
        engine = self._setup_engine()
        profile = _make_profile()
        scored = engine.score_all(profile)
        breakdown = scored[0].score_breakdown
        expected_keys = {
            "truth_depth", "aspect_alignment", "season_fit",
            "tradition_affinity", "trial_relevance", "quest_alignment",
            "temporal_resonance", "novelty", "learned_resonance",
            "repetition_penalty", "anti_pattern_penalty",
        }
        assert set(breakdown.keys()) == expected_keys

    def test_anti_pattern_penalizes(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(themes=["toxic_positivity"]))
        db.add(_make_wisdom(themes=["discipline"]))
        engine = WisdomEngine(db)
        profile = _make_profile(anti_patterns=["toxic_positivity"])
        scored = engine.score_all(profile)
        toxic = next(s for s in scored if "toxic_positivity" in s.wisdom.themes)
        clean = next(s for s in scored if "discipline" in s.wisdom.themes)
        assert clean.total_score > toxic.total_score

    def test_paradox_pair_selection(self):
        db = WisdomDatabase()
        w1 = _make_wisdom(paradox_pair_id="pair-w2")
        w2 = WisdomEntry(
            id="pair-w2", text="Opposite", author="Test",
            paradox_pair_id=w1.id,
            best_for_seasons=[InnerSeason.FORGE],
        )
        db.add(w1)
        db.add(w2)
        engine = WisdomEngine(db)
        profile = _make_profile()
        result = engine.select_paradox_pair(profile)
        assert result is not None
        scored, partner = result
        assert partner.id in (w1.id, w2.id)


class TestDeliveryManager:
    def test_deliver_wisdom(self):
        db = WisdomDatabase()
        db.add(_make_wisdom(text="Test delivery"))
        engine = WisdomEngine(db)
        delivery = DeliveryManager(engine)
        profile = _make_profile()
        result = delivery.deliver_wisdom(profile)
        assert result is not None
        assert "Test delivery" in result.formatted_text
        assert result.reflection_prompt is not None

    def test_dawn_briefing(self):
        db = WisdomDatabase()
        db.add(_make_wisdom())
        engine = WisdomEngine(db)
        delivery = DeliveryManager(engine)
        profile = _make_profile(inner_season=InnerSeason.FORGE)
        briefing = delivery.generate_dawn_briefing(profile)
        assert briefing is not None
        assert "fire" in briefing.greeting.lower() or "shape" in briefing.greeting.lower()
        assert briefing.inner_season == InnerSeason.FORGE

    def test_trial_sequence(self):
        db = WisdomDatabase()
        for i in range(5):
            db.add(_make_wisdom(text=f"Wisdom {i}"))
        engine = WisdomEngine(db)
        delivery = DeliveryManager(engine)
        profile = _make_profile()
        seq = delivery.generate_trial_sequence(
            profile, "Discipline is breaking down", num_entries=3
        )
        assert seq is not None
        assert len(seq.wisdom_entries) == 3
        assert len(seq.micro_challenges) == 3
        assert "teach" in seq.closing_reflection.lower()

    def test_format_wisdom(self):
        entry = WisdomEntry(text="Test text", author="Author", source="Source Book")
        formatted = format_wisdom(entry)
        assert '"Test text"' in formatted
        assert "Author" in formatted
        assert "Source Book" in formatted

    def test_paradox_delivery(self):
        db = WisdomDatabase()
        w1 = _make_wisdom(text="Act decisively", paradox_pair_id="pair-p")
        w2 = WisdomEntry(
            id="pair-p", text="Be patient", author="Test",
            paradox_pair_id=w1.id,
            best_for_seasons=[InnerSeason.FORGE],
        )
        db.add(w1)
        db.add(w2)
        engine = WisdomEngine(db)
        delivery = DeliveryManager(engine)
        profile = _make_profile()
        result = delivery.deliver_paradox_pair(profile)
        assert result is not None
        assert "Hold both" in result.framing


class TestProfileManager:
    def test_create_and_get(self):
        pm = ProfileManager()
        profile = pm.create_profile(name="Seeker")
        assert pm.get_profile(profile.id) is profile
        assert profile.name == "Seeker"

    def test_add_quest(self):
        pm = ProfileManager()
        profile = pm.create_profile()
        quest = Quest(description="Build the thing", domain=LifeDomain.CRAFT, why="It matters")
        assert pm.add_quest(profile.id, quest) is True
        assert len(profile.quests) == 1

    def test_declare_and_resolve_trial(self):
        pm = ProfileManager()
        profile = pm.create_profile()
        trial = Trial(description="Fear of failure", severity=0.7, truth_beneath="Not good enough")
        pm.declare_trial(profile.id, trial)
        assert len(profile.active_trials) == 1

        pm.resolve_trial(profile.id, trial.id, lesson_learned="Fear was the teacher")
        assert len(profile.active_trials) == 0
        assert trial.lesson_learned == "Fear was the teacher"

    def test_detect_season_desert_no_data(self):
        """A fresh profile with no interactions or quests lands in DESERT."""
        pm = ProfileManager()
        profile = pm.create_profile()
        season = pm.detect_season(profile.id)
        assert season == InnerSeason.DESERT

    def test_hit_different_tracked(self):
        pm = ProfileManager()
        profile = pm.create_profile()
        interaction = WisdomInteraction(
            wisdom_id="w1", seeker_id=profile.id, hit_different=True
        )
        pm.record_interaction(interaction)
        assert "w1" in profile.resonance_history

    def test_seen_wisdom_ids(self):
        pm = ProfileManager()
        profile = pm.create_profile()
        pm.record_interaction(
            WisdomInteraction(wisdom_id="w1", seeker_id=profile.id)
        )
        pm.record_interaction(
            WisdomInteraction(wisdom_id="w2", seeker_id=profile.id)
        )
        seen = pm.get_seen_wisdom_ids(profile.id)
        assert seen == {"w1", "w2"}

    def test_delete_profile(self):
        pm = ProfileManager()
        profile = pm.create_profile()
        assert pm.delete_profile(profile.id) is True
        assert pm.get_profile(profile.id) is None


class TestLearningManager:
    def test_process_interaction(self):
        db = WisdomDatabase()
        engine = WisdomEngine(db)
        lm = LearningManager(engine)

        interaction = WisdomInteraction(
            wisdom_id="w1", seeker_id="s1", rating=5, hit_different=True
        )
        lm.process_interaction(interaction, ["discipline", "courage"], "stoic")

        # Resonance should be updated in engine
        score = engine._resonance_score("s1", "w1")
        assert score > 0.9

    def test_resonance_stats(self):
        db = WisdomDatabase()
        engine = WisdomEngine(db)
        lm = LearningManager(engine)

        interactions = [
            WisdomInteraction(wisdom_id="w1", seeker_id="s1", rating=5, hit_different=True),
            WisdomInteraction(wisdom_id="w2", seeker_id="s1", rating=3),
            WisdomInteraction(wisdom_id="w3", seeker_id="s1", skipped=True),
        ]
        for i in interactions:
            lm.process_interaction(i, ["discipline"], "stoic")

        stats = lm.get_resonance_stats("s1", interactions)
        assert stats.total_interactions == 3
        assert stats.total_rated == 2
        assert stats.average_rating == 4.0
        assert stats.hit_different_count == 1
        assert stats.skip_count == 1


class TestPotentialTracker:
    def test_initialize_map(self):
        pt = PotentialTracker()
        profile = _make_profile()
        profile.quests = [
            Quest(description="Build", domain=LifeDomain.CRAFT, status=QuestStatus.WALKING)
        ]
        pmap = pt.initialize_map(profile)
        assert "craft" in pmap.domains
        assert pmap.overall_score() > 0

    def test_update_domain_level(self):
        pt = PotentialTracker()
        profile = _make_profile()
        profile.quests = [
            Quest(description="Build", domain=LifeDomain.CRAFT, status=QuestStatus.WALKING)
        ]
        pt.initialize_map(profile)
        assert pt.update_domain_level(profile.id, LifeDomain.CRAFT, 0.7) is True
        pmap = pt.get_map(profile.id)
        assert pmap.domains["craft"].current_level == 0.7

    def test_take_snapshot(self):
        pt = PotentialTracker()
        profile = _make_profile()
        profile.quests = [
            Quest(description="Build", domain=LifeDomain.CRAFT, status=QuestStatus.WALKING)
        ]
        pt.initialize_map(profile)
        snapshot = pt.take_snapshot(profile.id, InnerSeason.FORGE)
        assert snapshot is not None
        trajectory = pt.get_trajectory(profile.id)
        assert len(trajectory.snapshots) == 1

    def test_wisdom_gaps(self):
        pt = PotentialTracker()
        profile = _make_profile()
        profile.quests = [
            Quest(description="Build", domain=LifeDomain.CRAFT, status=QuestStatus.WALKING)
        ]
        pt.initialize_map(profile)
        # Default level is 0.3, target is 1.0, gap is 0.7 > 0.3 threshold
        gaps = pt.identify_wisdom_gaps(profile.id)
        assert "craft" in gaps
        assert "discipline" in gaps["craft"]
