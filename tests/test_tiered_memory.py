#!/usr/bin/env python3
"""Tests for three-tier memory architecture."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from intelligence.memory.tiered_memory import (
    MemoryItem,
    PromotionRules,
    ShortTermMemory,
    TieredMemory,
    WorkingMemory,
)


@pytest.fixture
def memory_item():
    """Create a test memory item."""
    return MemoryItem(
        id="test_item_1",
        content={"type": "pattern", "title": "test pattern", "description": "test description"},
        created_at=datetime.now(),
        last_accessed=datetime.now(),
        access_count=0,
    )


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()


class TestMemoryItem:
    """Test MemoryItem dataclass."""

    def test_to_dict(self, memory_item):
        """Test serialization to dict."""
        data = memory_item.to_dict()

        assert data["id"] == "test_item_1"
        assert data["content"]["type"] == "pattern"
        assert "created_at" in data
        assert data["access_count"] == 0

    def test_from_dict(self, memory_item):
        """Test deserialization from dict."""
        data = memory_item.to_dict()
        restored = MemoryItem.from_dict(data)

        assert restored.id == memory_item.id
        assert restored.content == memory_item.content
        assert restored.access_count == memory_item.access_count


class TestShortTermMemory:
    """Test short-term memory tier."""

    def test_initialization(self):
        """Test short-term memory initialization."""
        stm = ShortTermMemory(max_items=10)
        assert stm.max_items == 10
        assert len(stm.items) == 0

    def test_add_item(self, memory_item):
        """Test adding items."""
        stm = ShortTermMemory(max_items=10)
        stm.add(memory_item)

        assert len(stm.items) == 1
        assert memory_item.id in stm.items

    def test_capacity_eviction(self):
        """Test LRU eviction at capacity."""
        stm = ShortTermMemory(max_items=3)

        # Add 4 items
        for i in range(4):
            item = MemoryItem(
                id=f"item_{i}",
                content={"index": i},
                created_at=datetime.now(),
                last_accessed=datetime.now() - timedelta(seconds=4 - i),
            )
            stm.add(item)

        # Should have evicted oldest (item_0)
        assert len(stm.items) == 3
        assert "item_0" not in stm.items
        assert "item_3" in stm.items

    def test_get_item(self, memory_item):
        """Test retrieving items and access count."""
        stm = ShortTermMemory()
        stm.add(memory_item)

        item = stm.get(memory_item.id)
        assert item is not None
        assert item.access_count == 1

        # Access again
        item = stm.get(memory_item.id)
        assert item.access_count == 2

    def test_search(self):
        """Test keyword search."""
        stm = ShortTermMemory()

        # Add multiple items
        for i in range(5):
            item = MemoryItem(
                id=f"item_{i}",
                content={"title": f"test pattern {i}", "type": "pattern"},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )
            stm.add(item)

        # Search for "pattern"
        results = stm.search("pattern")
        assert len(results) == 5

        # Search for specific index
        results = stm.search("pattern 3")
        assert len(results) == 1
        assert results[0].id == "item_3"

    def test_get_frequently_accessed(self):
        """Test getting frequently accessed items."""
        stm = ShortTermMemory()

        # Add items with different access counts
        for i in range(5):
            item = MemoryItem(
                id=f"item_{i}",
                content={"index": i},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=i,
            )
            stm.add(item)

        # Get items accessed 3+ times
        frequent = stm.get_frequently_accessed(threshold=3)
        assert len(frequent) == 2  # items 3 and 4
        assert all(item.access_count >= 3 for item in frequent)

    def test_clear(self):
        """Test clearing short-term memory."""
        stm = ShortTermMemory()

        # Add items
        for i in range(3):
            item = MemoryItem(
                id=f"item_{i}",
                content={},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )
            stm.add(item)

        assert len(stm.items) == 3

        # Clear
        stm.clear()
        assert len(stm.items) == 0

    def test_get_stats(self):
        """Test statistics."""
        stm = ShortTermMemory(max_items=10)

        for i in range(5):
            item = MemoryItem(
                id=f"item_{i}",
                content={},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )
            stm.add(item)

        stats = stm.get_stats()
        assert stats["item_count"] == 5
        assert stats["max_items"] == 10
        assert stats["capacity_used"] == 0.5


class TestWorkingMemory:
    """Test working memory tier."""

    def test_initialization(self, temp_db):
        """Test working memory initialization."""
        wm = WorkingMemory(retention_days=7, db_path=temp_db)
        assert wm.retention_days == 7
        assert wm.db_path == temp_db
        assert temp_db.exists()

    def test_database_schema(self, temp_db):
        """Test database schema creation."""
        WorkingMemory(db_path=temp_db)

        # Verify schema
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        assert "memory_items" in tables

    def test_add_item(self, temp_db, memory_item):
        """Test adding items to working memory."""
        wm = WorkingMemory(db_path=temp_db)
        wm.add(memory_item)

        # Verify in database
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT id FROM memory_items WHERE id = ?", (memory_item.id,))
            result = cursor.fetchone()

        assert result is not None
        assert result[0] == memory_item.id

    def test_get_item(self, temp_db, memory_item):
        """Test retrieving items from working memory."""
        wm = WorkingMemory(db_path=temp_db)
        wm.add(memory_item)

        # Retrieve
        item = wm.get(memory_item.id)
        assert item is not None
        assert item.id == memory_item.id
        assert item.access_count == 1

        # Access again
        item = wm.get(memory_item.id)
        assert item.access_count == 2

    def test_search(self, temp_db):
        """Test searching working memory."""
        wm = WorkingMemory(db_path=temp_db)

        # Add multiple items
        for i in range(5):
            item = MemoryItem(
                id=f"item_{i}",
                content={"title": f"test pattern {i}"},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )
            wm.add(item)

        # Search
        results = wm.search("pattern")
        assert len(results) == 5

        results = wm.search("pattern 3")
        assert len(results) == 1

    def test_get_successful(self, temp_db):
        """Test getting successful outcomes."""
        wm = WorkingMemory(db_path=temp_db)

        # Add items with different outcomes
        for i, outcome in enumerate(["success", "failed", "success", "partial"]):
            item = MemoryItem(
                id=f"item_{i}",
                content={},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                outcome=outcome,
            )
            wm.add(item)

        # Get successful only
        successful = wm.get_successful()
        assert len(successful) == 2
        assert all(item.outcome == "success" for item in successful)

    def test_cleanup_expired(self, temp_db):
        """Test cleanup of expired items."""
        wm = WorkingMemory(retention_days=7, db_path=temp_db)

        # Add old item (10 days ago)
        old_item = MemoryItem(
            id="old_item",
            content={},
            created_at=datetime.now() - timedelta(days=10),
            last_accessed=datetime.now() - timedelta(days=10),
        )
        wm.add(old_item)

        # Add recent item
        recent_item = MemoryItem(
            id="recent_item",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )
        wm.add(recent_item)

        # Cleanup
        deleted = wm.cleanup_expired()
        assert deleted == 1

        # Verify old item removed, recent item remains
        assert wm.get("old_item") is None
        assert wm.get("recent_item") is not None

    def test_get_stats(self, temp_db):
        """Test statistics."""
        wm = WorkingMemory(db_path=temp_db)

        # Add items with outcomes
        for i in range(5):
            item = MemoryItem(
                id=f"item_{i}",
                content={},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                outcome="success" if i % 2 == 0 else None,
            )
            wm.add(item)

        stats = wm.get_stats()
        assert stats["item_count"] == 5
        assert stats["items_with_outcomes"] == 3


class TestPromotionRules:
    """Test promotion rules."""

    def test_promote_to_working_by_access(self):
        """Test promotion to working by access count."""
        rules = PromotionRules(working_access_threshold=2)

        # Should not promote (access_count=1)
        item = MemoryItem(
            id="test",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
        )
        assert not rules.should_promote_to_working(item)

        # Should promote (access_count=2)
        item.access_count = 2
        assert rules.should_promote_to_working(item)

    def test_promote_to_working_by_outcome(self):
        """Test promotion to working by outcome."""
        rules = PromotionRules()

        # Should promote even with low access if has outcome
        item = MemoryItem(
            id="test",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            outcome="success",
        )
        assert rules.should_promote_to_working(item)

    def test_promote_to_long_term(self):
        """Test promotion to long-term."""
        rules = PromotionRules(long_term_quality_threshold=0.7)

        # Should not promote (no quality score)
        item = MemoryItem(
            id="test",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            outcome="success",
        )
        assert not rules.should_promote_to_long_term(item)

        # Should not promote (quality too low)
        item.quality_score = 0.6
        assert not rules.should_promote_to_long_term(item)

        # Should not promote (wrong outcome)
        item.quality_score = 0.8
        item.outcome = "failed"
        assert not rules.should_promote_to_long_term(item)

        # Should promote (success + high quality)
        item.outcome = "success"
        item.quality_score = 0.8
        assert rules.should_promote_to_long_term(item)


class TestTieredMemory:
    """Test full tiered memory system."""

    def test_initialization(self, temp_db):
        """Test tiered memory initialization."""
        tm = TieredMemory()
        assert tm.short_term is not None
        assert tm.working is not None
        assert tm.long_term is not None
        assert tm.promotion_rules is not None

    def test_record(self, temp_db, memory_item):
        """Test recording items."""
        tm = TieredMemory()
        tm.record(memory_item)

        # Should be in short-term
        assert memory_item.id in tm.short_term.items

    def test_record_with_promotion(self, temp_db):
        """Test automatic promotion on record."""
        tm = TieredMemory()

        # Item with high access count should promote
        item = MemoryItem(
            id="frequent",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=3,
        )
        tm.record(item)

        # Should be in both short-term and working
        assert item.id in tm.short_term.items
        assert tm.working.get(item.id) is not None

    def test_update_outcome(self, temp_db):
        """Test updating item outcome."""
        tm = TieredMemory()

        # Record item
        item = MemoryItem(
            id="test",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )
        tm.record(item)

        # Update outcome
        tm.update_outcome("test", "success", 0.8)

        # Verify updated
        updated = tm.short_term.get("test")
        assert updated.outcome == "success"
        assert updated.quality_score == 0.8

    def test_query_single_tier(self, temp_db):
        """Test querying single tier."""
        tm = TieredMemory()

        # Add item to short-term
        item = MemoryItem(
            id="st_item",
            content={"title": "short term test"},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )
        tm.short_term.add(item)

        # Query only short-term
        results = tm.query("short term", tiers=["short_term"], limit=10)
        assert len(results) > 0
        assert results[0][2] == "short_term"  # tier name

    def test_query_weighting(self, temp_db):
        """Test tier weighting in queries."""
        tm = TieredMemory()

        # Add identical items to different tiers
        st_item = MemoryItem(
            id="st_item",
            content={"title": "test pattern"},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )
        tm.short_term.add(st_item)

        wm_item = MemoryItem(
            id="wm_item",
            content={"title": "test pattern"},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )
        tm.working.add(wm_item)

        # Query across tiers
        results = tm.query("test pattern", tiers=["short_term", "working"], limit=10)

        # Short-term should have higher weight (1.5x vs 1.2x)
        if len(results) >= 2:
            short_term_result = next((r for r in results if r[2] == "short_term"), None)
            working_result = next((r for r in results if r[2] == "working"), None)

            if short_term_result and working_result:
                assert short_term_result[1] > working_result[1]  # score comparison

    def test_end_session(self, temp_db):
        """Test end-of-session processing."""
        tm = TieredMemory()

        # Add frequently accessed item
        item = MemoryItem(
            id="frequent",
            content={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=5,
        )
        tm.short_term.add(item)

        # End session
        tm.end_session()

        # Short-term should be cleared
        assert len(tm.short_term.items) == 0

        # Item should be promoted to working
        assert tm.working.get("frequent") is not None

    def test_get_stats(self, temp_db):
        """Test statistics across all tiers."""
        tm = TieredMemory()

        # Add items
        for i in range(3):
            item = MemoryItem(
                id=f"item_{i}",
                content={},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )
            tm.short_term.add(item)

        stats = tm.get_stats()

        assert "short_term" in stats
        assert "working" in stats
        assert "long_term" in stats
        assert "promotion_rules" in stats

        assert stats["short_term"]["item_count"] == 3


class TestSessionLifecycle:
    """Test full session lifecycle with memory tiers."""

    def test_full_session(self, temp_db):
        """Test complete session lifecycle."""
        tm = TieredMemory()

        # Session start: Record items
        for i in range(5):
            item = MemoryItem(
                id=f"item_{i}",
                content={"title": f"pattern {i}"},
                created_at=datetime.now(),
                last_accessed=datetime.now(),
            )
            tm.record(item)

        # During session: Access some items frequently
        for _ in range(3):
            tm.short_term.get("item_0")
            tm.short_term.get("item_1")

        # Add outcomes
        tm.update_outcome("item_0", "success", 0.85)
        tm.update_outcome("item_1", "partial", 0.60)

        # Session end
        tm.end_session()

        # Verify frequently accessed items promoted
        assert tm.working.get("item_0") is not None
        assert tm.working.get("item_1") is not None

        # Verify short-term cleared
        assert len(tm.short_term.items) == 0

    def test_cross_session_persistence(self, temp_db):
        """Test persistence across sessions."""
        # Session 1
        tm1 = TieredMemory()
        item = MemoryItem(
            id="persistent",
            content={"title": "cross-session pattern"},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=5,
        )
        tm1.working.add(item)

        # Session 2 (new instance)
        tm2 = TieredMemory()
        retrieved = tm2.working.get("persistent")

        assert retrieved is not None
        assert retrieved.content["title"] == "cross-session pattern"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
