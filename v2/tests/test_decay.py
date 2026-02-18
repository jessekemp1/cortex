"""Tests for temporal decay."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from cortex.v2.memory.decay import DecayResult, TemporalDecay
from cortex.v2.memory.types import Pattern


@pytest.fixture
def decay():
    """Create a TemporalDecay instance."""
    return TemporalDecay()


@pytest.fixture
def old_pattern():
    """Create a pattern from 180 days ago (half-life for patterns)."""
    created = datetime.utcnow() - timedelta(days=180)
    return Pattern(
        id="pattern_old",
        title="Old Pattern",
        content="Old content",
        problem="Old problem",
        solution="Old solution",
        projects=["Test"],
        confidence=0.8,
        created_at=created,
        last_used=created,
        use_count=0,
    )


@pytest.fixture
def new_pattern():
    """Create a fresh pattern."""
    now = datetime.utcnow()
    return Pattern(
        id="pattern_new",
        title="New Pattern",
        content="New content",
        problem="New problem",
        solution="New solution",
        projects=["Test"],
        confidence=0.8,
        created_at=now,
        last_used=now,
        use_count=0,
    )


@pytest.fixture
def used_pattern():
    """Create an old but frequently used pattern."""
    created = datetime.utcnow() - timedelta(days=180)
    return Pattern(
        id="pattern_used",
        title="Used Pattern",
        content="Used content",
        problem="Used problem",
        solution="Used solution",
        projects=["Test"],
        confidence=0.8,
        created_at=created,
        last_used=created,
        use_count=10,  # Used 10 times
    )


class TestTemporalDecay:
    """Test TemporalDecay class."""

    def test_new_memory_no_decay(self, decay, new_pattern):
        """New memories should have no decay (factor ~1.0)."""
        factor = decay.calculate_decay(
            memory_type="pattern",
            created_at=new_pattern.created_at,
            last_used=new_pattern.last_used,
            use_count=new_pattern.use_count,
        )
        assert factor >= 0.99  # Should be essentially 1.0

    def test_half_life_decay(self, decay, old_pattern):
        """Memory at half-life should have ~50% relevance."""
        factor = decay.calculate_decay(
            memory_type="pattern",
            created_at=old_pattern.created_at,
            last_used=old_pattern.last_used,
            use_count=old_pattern.use_count,
        )
        # At exactly half-life (180 days), should be ~0.5
        assert 0.45 <= factor <= 0.55

    def test_usage_boost(self, decay, used_pattern):
        """Frequently used memories should decay slower."""
        # Used pattern (10 uses) should have higher relevance than unused
        used_factor = decay.calculate_decay(
            memory_type="pattern",
            created_at=used_pattern.created_at,
            last_used=used_pattern.last_used,
            use_count=used_pattern.use_count,
        )

        # Same age, no uses
        unused_factor = decay.calculate_decay(
            memory_type="pattern",
            created_at=used_pattern.created_at,
            last_used=used_pattern.last_used,
            use_count=0,
        )

        assert used_factor > unused_factor
        # 10 uses = 30% boost (max)
        assert used_factor - unused_factor >= 0.25

    def test_type_specific_half_lives(self, decay):
        """Different memory types should have different half-lives."""
        created = datetime.utcnow() - timedelta(days=180)

        # Pattern: 180 days half-life -> ~50%
        pattern_decay = decay.calculate_decay(
            memory_type="pattern", created_at=created, last_used=created
        )

        # Incident: 90 days half-life -> ~25% at 180 days
        incident_decay = decay.calculate_decay(
            memory_type="incident", created_at=created, last_used=created
        )

        # Decision: 730 days half-life -> ~83% at 180 days
        decision_decay = decay.calculate_decay(
            memory_type="decision", created_at=created, last_used=created
        )

        # Incident should decay faster than pattern
        assert incident_decay < pattern_decay
        # Decision should decay slower than pattern
        assert decision_decay > pattern_decay

    def test_apply_decay(self, decay, new_pattern, old_pattern, used_pattern):
        """apply_decay should set effective_confidence on memories."""
        memories = [new_pattern, old_pattern, used_pattern]

        result = decay.apply_decay(memories, sort_by_relevance=True)

        # All should have effective_confidence set
        for m in result:
            assert hasattr(m, "effective_confidence")
            assert 0 <= m.effective_confidence <= 1

        # New pattern should be first (highest effective_confidence)
        assert result[0].id == "pattern_new"

    def test_get_stale_memories(self, decay):
        """get_stale_memories should find old, unused memories."""
        very_old = datetime.utcnow() - timedelta(days=1000)  # Very old

        stale_pattern = Pattern(
            id="pattern_stale",
            title="Stale",
            content="Stale",
            problem="Stale",
            solution="Stale",
            projects=["Test"],
            confidence=0.8,
            created_at=very_old,
            last_used=very_old,
            use_count=0,
        )

        fresh_pattern = Pattern(
            id="pattern_fresh",
            title="Fresh",
            content="Fresh",
            problem="Fresh",
            solution="Fresh",
            projects=["Test"],
            confidence=0.8,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=0,
        )

        stale = decay.get_stale_memories([stale_pattern, fresh_pattern])

        assert len(stale) == 1
        assert stale[0].id == "pattern_stale"

    def test_refresh_memory(self, decay, old_pattern):
        """refresh_memory should update last_used and use_count."""
        old_last_used = old_pattern.last_used
        old_use_count = old_pattern.use_count

        decay.refresh_memory(old_pattern)

        assert old_pattern.last_used > old_last_used
        assert old_pattern.use_count == old_use_count + 1

    def test_calculate_decay_result(self, decay, old_pattern):
        """calculate_decay_result should return detailed metrics."""
        result = decay.calculate_decay_result(old_pattern)

        assert isinstance(result, DecayResult)
        assert result.memory_id == old_pattern.id
        assert result.memory_type == "pattern"
        assert 0 <= result.decay_factor <= 1
        assert result.effective_confidence == old_pattern.confidence * result.decay_factor
        assert result.days_since_use >= 180

    def test_decay_stats(self, decay, new_pattern, old_pattern):
        """get_decay_stats should return statistics."""
        stats = decay.get_decay_stats([new_pattern, old_pattern])

        assert stats["total"] == 2
        assert "pattern" in stats["by_type"]
        assert stats["by_type"]["pattern"]["count"] == 2
        assert 0 <= stats["avg_decay"] <= 1

    def test_estimate_days_until_stale(self, decay):
        """estimate_days_until_stale should return reasonable values."""
        # New pattern with no uses
        days = decay.estimate_days_until_stale("pattern", current_decay=1.0, use_count=0)

        # Should be around when decay < 0.1 threshold
        # For pattern (180 day half-life), this should be around 600 days
        assert days > 500

        # High use count should extend time
        days_with_uses = decay.estimate_days_until_stale("pattern", current_decay=1.0, use_count=10)
        assert days_with_uses > days

    def test_custom_half_lives(self):
        """Custom half-lives should be respected."""
        custom_decay = TemporalDecay(half_lives={"pattern": 30})  # 30 days

        created = datetime.utcnow() - timedelta(days=30)
        factor = custom_decay.calculate_decay(
            memory_type="pattern", created_at=created, last_used=created
        )

        # At 30 days with 30-day half-life, should be ~50%
        assert 0.45 <= factor <= 0.55


class TestDecayIntegration:
    """Test decay integration with memory store."""

    def test_store_query_applies_decay(self):
        """TypedMemoryStore.query should apply decay when enabled."""
        from cortex.v2.memory.store import TypedMemoryStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = TypedMemoryStore(data_dir=Path(tmpdir))

            # Add a fresh pattern
            fresh = Pattern.create(
                title="Fresh Caching Pattern",
                problem="Slow API",
                solution="Use cache",
                projects=["Test"],
            )

            # Add an old pattern (manually set dates)
            old = Pattern.create(
                title="Old Caching Pattern",
                problem="Slow API",
                solution="Use cache",
                projects=["Test"],
            )
            old.created_at = datetime.utcnow() - timedelta(days=365)
            old.last_used = datetime.utcnow() - timedelta(days=365)

            store.add(fresh)
            store.add(old)

            # Query with decay
            results = store.query("caching", apply_decay=True)

            # Both should be returned (term match)
            assert len(results) >= 2

            # Fresh should come first due to higher effective_confidence
            fresh_result = next(r for r in results if "Fresh" in r.title)
            old_result = next(r for r in results if "Old" in r.title)

            assert fresh_result.effective_confidence > old_result.effective_confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
