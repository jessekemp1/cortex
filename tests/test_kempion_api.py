"""Tests for the Kempion API layer (KempionApp)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motivation.api import KempionApp


class TestKempionApp:
    def _setup_app(self) -> KempionApp:
        app = KempionApp()
        app.initialize()  # Load seed data
        return app

    def test_create_seeker(self):
        app = self._setup_app()
        profile = app.create_seeker(
            name="Jesse",
            core_values=["truth", "discipline", "craft"],
            tone_preference="tempered",
            tradition_affinity={"stoic": 0.8, "zen": 0.6},
        )
        assert profile.name == "Jesse"
        assert "truth" in profile.core_values
        assert app.get_seeker(profile.id) is profile

    def test_add_quest(self):
        app = self._setup_app()
        profile = app.create_seeker(name="Seeker")
        quest = app.add_quest(
            profile.id,
            description="Build Kempion",
            domain="craft",
            why="Wisdom should be personal",
        )
        assert quest is not None
        assert quest.description == "Build Kempion"

    def test_declare_trial(self):
        app = self._setup_app()
        profile = app.create_seeker()
        trial = app.declare_trial(
            profile.id,
            description="Losing discipline",
            severity=0.6,
            domain="mind",
            truth_beneath="Afraid of failure",
        )
        assert trial is not None
        assert trial.severity == 0.6

    def test_resolve_trial(self):
        app = self._setup_app()
        profile = app.create_seeker()
        trial = app.declare_trial(profile.id, "Test trial")
        assert app.resolve_trial(profile.id, trial.id, "Learned something") is True

    def test_get_wisdom(self):
        app = self._setup_app()
        profile = app.create_seeker(
            tradition_affinity={"stoic": 0.9},
        )
        result = app.get_wisdom(profile.id)
        assert result is not None
        assert "text" in result
        assert "author" in result
        assert "formatted" in result
        assert "reflection_prompt" in result
        assert len(result["text"]) > 0

    def test_get_wisdom_nonexistent_seeker(self):
        app = self._setup_app()
        assert app.get_wisdom("nonexistent") is None

    def test_rate_wisdom(self):
        app = self._setup_app()
        profile = app.create_seeker()
        wisdom = app.get_wisdom(profile.id)
        assert wisdom is not None
        success = app.rate_wisdom(
            profile.id,
            wisdom["wisdom_id"],
            rating=5,
            hit_different=True,
            reflection="This is exactly what I needed.",
        )
        assert success is True

    def test_dawn_briefing(self):
        app = self._setup_app()
        profile = app.create_seeker(name="Dawn Seeker")
        app.add_quest(profile.id, "Build the thing", domain="craft", why="It matters")
        briefing = app.get_dawn_briefing(profile.id)
        assert briefing is not None
        assert "greeting" in briefing
        assert "wisdom" in briefing
        assert "focus_prompt" in briefing
        assert "inner_season" in briefing

    def test_detect_season(self):
        app = self._setup_app()
        profile = app.create_seeker()
        season = app.detect_season(profile.id)
        assert season is not None

    def test_resonance_stats(self):
        app = self._setup_app()
        profile = app.create_seeker()
        # Get and rate some wisdom
        for _ in range(3):
            w = app.get_wisdom(profile.id)
            if w:
                app.rate_wisdom(profile.id, w["wisdom_id"], rating=4)

        stats = app.get_resonance_stats(profile.id)
        assert stats is not None
        assert stats["total_interactions"] == 3

    def test_initialize_potential(self):
        app = self._setup_app()
        profile = app.create_seeker()
        app.add_quest(profile.id, "Build", domain="craft")
        potential = app.initialize_potential(profile.id)
        assert potential is not None
        assert "craft" in potential["domains"]
        assert "overall_score" in potential

    def test_full_flow(self):
        """End-to-end: create seeker, add quest, declare trial, get wisdom, rate it."""
        app = self._setup_app()

        # Create seeker with Kempion-aligned values
        profile = app.create_seeker(
            name="Poet-Warrior",
            core_values=["truth", "discipline", "craft", "silence"],
            tone_preference="tempered",
            depth_preference="root",
            tradition_affinity={"stoic": 0.8, "zen": 0.6, "existentialist": 0.5},
        )

        # Add a quest
        quest = app.add_quest(
            profile.id,
            description="Build Kempion into a real product",
            domain="craft",
            why="Wisdom should be earned, not consumed",
        )

        # Declare a trial
        trial = app.declare_trial(
            profile.id,
            description="Perfectionism blocking shipping",
            severity=0.6,
            domain="mind",
            truth_beneath="Fear that it's not good enough",
        )

        # Get wisdom
        wisdom = app.get_wisdom(profile.id)
        assert wisdom is not None
        assert len(wisdom["text"]) > 0

        # Rate it
        app.rate_wisdom(
            profile.id,
            wisdom["wisdom_id"],
            rating=5,
            hit_different=True,
            saved=True,
            reflection="The obstacle is the way. Ship it.",
        )

        # Get dawn briefing
        briefing = app.get_dawn_briefing(profile.id)
        assert briefing is not None

        # Check stats
        stats = app.get_resonance_stats(profile.id)
        assert stats["hit_different_count"] == 1

        # Resolve the trial
        app.resolve_trial(profile.id, trial.id, "Shipped imperfectly. That was the lesson.")

        # Init potential
        potential = app.initialize_potential(profile.id)
        assert "craft" in potential["domains"]
