#!/usr/bin/env python3
"""
Three-Tier Memory Architecture for Cortex.

Implements human-inspired memory tiers:
- Short-term: Current session, in-memory, limited capacity
- Working: Recent sessions (7 days), SQLite-backed, frequently accessed
- Long-term: All patterns, indexed for retrieval (existing PatternMemory)

Memory items are automatically promoted between tiers based on access patterns
and outcome quality.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from cortex.state_paths import get_cortex_dir

logger = logging.getLogger(__name__)


def _connect(db_path) -> "sqlite3.Connection":
    """Open the shared store with WAL + busy_timeout.

    Multiple processes share these databases (MCP servers per Claude session,
    the CLI, and the bridge daemon). WAL allows concurrent readers during a
    write; busy_timeout makes a second writer wait up to 5s instead of
    failing immediately with 'database is locked'.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn



@dataclass
class MemoryItem:
    """Item stored in memory."""

    id: str
    content: Dict[str, Any]
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    outcome: Optional[str] = None  # "success", "partial", "failed"
    quality_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "outcome": self.outcome,
            "quality_score": self.quality_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            outcome=data.get("outcome"),
            quality_score=data.get("quality_score"),
        )


class ShortTermMemory:
    """
    In-memory, session-scoped, limited capacity.

    Short-term memory holds items from the current session only.
    Capacity is limited (default 50 items), with LRU eviction.
    """

    def __init__(self, max_items: int = 50):
        """
        Initialize short-term memory.

        Args:
            max_items: Maximum items to store (default: 50)
        """
        self.max_items = max_items
        self.items: Dict[str, MemoryItem] = {}
        logger.debug(f"Initialized ShortTermMemory with max_items={max_items}")

    def add(self, item: MemoryItem):
        """
        Add item, evict oldest if at capacity.

        Args:
            item: Memory item to add
        """
        # If at capacity, evict least recently accessed item
        if len(self.items) >= self.max_items:
            oldest_id = min(self.items.keys(), key=lambda k: self.items[k].last_accessed)
            del self.items[oldest_id]
            logger.debug(f"Evicted item {oldest_id} from short-term memory (at capacity)")

        self.items[item.id] = item
        logger.debug(f"Added item {item.id} to short-term memory")

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """
        Get item and update access count.

        Args:
            item_id: Item ID to retrieve

        Returns:
            Memory item if found, None otherwise
        """
        item = self.items.get(item_id)
        if item:
            item.access_count += 1
            item.last_accessed = datetime.now()
            logger.debug(f"Accessed item {item_id} (count: {item.access_count})")
        return item

    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """
        Simple keyword search in short-term memory.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching memory items
        """
        query_lower = query.lower()
        results = []

        for item in self.items.values():
            # Search in content string representation
            content_str = str(item.content).lower()
            if query_lower in content_str:
                results.append(item)

        # Sort by recency (most recent first)
        results.sort(key=lambda x: x.last_accessed, reverse=True)

        return results[:limit]

    def get_frequently_accessed(self, threshold: int = 3) -> List[MemoryItem]:
        """
        Get items accessed >= threshold times.

        Args:
            threshold: Minimum access count (default: 3)

        Returns:
            List of frequently accessed items
        """
        return [item for item in self.items.values() if item.access_count >= threshold]

    def clear(self):
        """Clear all items (session end)."""
        item_count = len(self.items)
        self.items.clear()
        logger.info(f"Cleared short-term memory ({item_count} items)")

    def get_stats(self) -> Dict[str, Any]:
        """Get short-term memory statistics."""
        return {
            "item_count": len(self.items),
            "max_items": self.max_items,
            "capacity_used": len(self.items) / self.max_items if self.max_items > 0 else 0,
        }


class WorkingMemory:
    """
    7-day retention, SQLite-backed, frequently accessed items.

    Working memory persists across sessions, storing items that are
    accessed frequently or have outcomes. Items older than retention_days
    are automatically cleaned up.
    """

    def __init__(self, retention_days: int = 7, db_path: Optional[Path] = None):
        """
        Initialize working memory.

        Args:
            retention_days: Days to retain items (default: 7)
            db_path: Path to SQLite database (default: ~/.cortex/working_memory.db)
        """
        self.retention_days = retention_days

        if db_path is None:
            db_path = get_cortex_dir() / "working_memory.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        logger.debug(f"Initialized WorkingMemory with retention={retention_days}d, db={db_path}")

    def _init_db(self):
        """Initialize SQLite database schema."""
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    outcome TEXT,
                    quality_score REAL
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_last_accessed
                ON memory_items(last_accessed)
            """
            )
            conn.commit()
        logger.debug("Initialized working memory database schema")

    def add(self, item: MemoryItem):
        """
        Add item to working memory.

        Args:
            item: Memory item to add
        """
        import json

        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_items
                (id, content_json, created_at, last_accessed, access_count, outcome, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item.id,
                    json.dumps(item.content),
                    item.created_at.isoformat(),
                    item.last_accessed.isoformat(),
                    item.access_count,
                    item.outcome,
                    item.quality_score,
                ),
            )
            conn.commit()
        logger.debug(f"Added item {item.id} to working memory")

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """
        Get item from working memory.

        Args:
            item_id: Item ID to retrieve

        Returns:
            Memory item if found, None otherwise
        """
        import json

        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()

        if not row:
            return None

        # Update access count
        item = MemoryItem(
            id=row["id"],
            content=json.loads(row["content_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed=datetime.now(),
            access_count=row["access_count"] + 1,
            outcome=row["outcome"],
            quality_score=row["quality_score"],
        )

        # Save updated access info
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE memory_items
                SET last_accessed = ?, access_count = ?
                WHERE id = ?
            """,
                (item.last_accessed.isoformat(), item.access_count, item.id),
            )
            conn.commit()

        logger.debug(f"Retrieved item {item_id} from working memory (count: {item.access_count})")
        return item

    def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """
        Search working memory.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching memory items
        """
        import json

        query_lower = query.lower()
        results = []

        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM memory_items")

            for row in cursor:
                content = json.loads(row["content_json"])
                content_str = str(content).lower()

                if query_lower in content_str:
                    item = MemoryItem(
                        id=row["id"],
                        content=content,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_accessed=datetime.fromisoformat(row["last_accessed"]),
                        access_count=row["access_count"],
                        outcome=row["outcome"],
                        quality_score=row["quality_score"],
                    )
                    results.append(item)

        # Sort by recency
        results.sort(key=lambda x: x.last_accessed, reverse=True)

        return results[:limit]

    def get_successful(self) -> List[MemoryItem]:
        """
        Get items with successful outcomes for promotion.

        Returns:
            List of successful memory items
        """
        import json

        results = []

        with _connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM memory_items WHERE outcome = 'success'")

            for row in cursor:
                item = MemoryItem(
                    id=row["id"],
                    content=json.loads(row["content_json"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_accessed=datetime.fromisoformat(row["last_accessed"]),
                    access_count=row["access_count"],
                    outcome=row["outcome"],
                    quality_score=row["quality_score"],
                )
                results.append(item)

        return results

    def cleanup_expired(self):
        """Remove items older than retention_days."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        with _connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM memory_items WHERE last_accessed < ?",
                (cutoff.isoformat(),),
            )
            deleted_count = cursor.rowcount
            conn.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired items from working memory")

        return deleted_count

    def get_stats(self) -> Dict[str, Any]:
        """Get working memory statistics."""
        with _connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM memory_items")
            total_count = cursor.fetchone()[0]

            # Count items with outcomes
            cursor = conn.execute("SELECT COUNT(*) FROM memory_items WHERE outcome IS NOT NULL")
            outcome_count = cursor.fetchone()[0]

        return {
            "item_count": total_count,
            "items_with_outcomes": outcome_count,
            "retention_days": self.retention_days,
            "db_path": str(self.db_path),
        }


class LongTermMemory:
    """Wrapper around existing PatternMemory for long-term storage."""

    def __init__(self, pattern_memory=None):
        """
        Initialize long-term memory.

        Args:
            pattern_memory: Existing PatternMemory instance (optional)
        """
        # Import here to avoid circular dependency
        from intelligence.memory.pattern_memory import PatternMemory

        if pattern_memory is None:
            pattern_memory = PatternMemory()

        self.pattern_memory = pattern_memory
        logger.debug("Initialized LongTermMemory with PatternMemory")

    def search(self, query: str, limit: int = 10) -> List[Any]:
        """
        Search long-term memory using PatternMemory.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of relevant patterns
        """
        return self.pattern_memory.get_relevant_patterns(query, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """Get long-term memory statistics."""
        return self.pattern_memory.get_stats()


class PromotionRules:
    """Rules for promoting items between tiers."""

    def __init__(
        self,
        working_access_threshold: int = 2,
        long_term_quality_threshold: float = 0.7,
    ):
        """
        Initialize promotion rules.

        Args:
            working_access_threshold: Min accesses to promote to working (default: 2)
            long_term_quality_threshold: Min quality to promote to long-term (default: 0.7)
        """
        self.working_access_threshold = working_access_threshold
        self.long_term_quality_threshold = long_term_quality_threshold

    def should_promote_to_working(self, item: MemoryItem) -> bool:
        """
        Promote if accessed 2+ times or has outcome.

        Args:
            item: Memory item to check

        Returns:
            True if should promote to working memory
        """
        return item.access_count >= self.working_access_threshold or item.outcome is not None

    def should_promote_to_long_term(self, item: MemoryItem) -> bool:
        """
        Promote if successful outcome and quality > 0.7.

        Args:
            item: Memory item to check

        Returns:
            True if should promote to long-term memory
        """
        return (
            item.outcome == "success"
            and item.quality_score is not None
            and item.quality_score > self.long_term_quality_threshold
        )


class TieredMemory:
    """Three-tier memory: short-term, working, long-term."""

    def __init__(
        self,
        short_term_max: int = 50,
        working_retention_days: int = 7,
        pattern_memory=None,
    ):
        """
        Initialize tiered memory system.

        Args:
            short_term_max: Max items in short-term memory (default: 50)
            working_retention_days: Days to retain in working memory (default: 7)
            pattern_memory: Existing PatternMemory instance (optional)
        """
        self.short_term = ShortTermMemory(max_items=short_term_max)
        self.working = WorkingMemory(retention_days=working_retention_days)
        self.long_term = LongTermMemory(pattern_memory=pattern_memory)
        self.promotion_rules = PromotionRules()

        logger.info("Initialized TieredMemory system")

    def query(self, query: str, tiers: Optional[List[str]] = None, limit: int = 10) -> List[tuple]:
        """
        Query across memory tiers with priority weighting.

        Short-term: weight 1.5x (most relevant to current session)
        Working: weight 1.2x (recent, frequently accessed)
        Long-term: weight 1.0x (historical patterns)

        Args:
            query: Search query
            tiers: List of tiers to search (default: all)
            limit: Maximum results to return

        Returns:
            List of (item, weighted_score, tier) tuples sorted by score
        """
        if tiers is None:
            tiers = ["short_term", "working", "long_term"]

        all_results = []

        # Search short-term memory
        if "short_term" in tiers:
            short_term_items = self.short_term.search(query, limit=limit)
            for item in short_term_items:
                # Weight by recency and access count
                base_score = 1.0
                recency_boost = 1.0 / (
                    (datetime.now() - item.last_accessed).total_seconds() / 3600 + 1
                )
                access_boost = min(item.access_count / 10.0, 1.0)
                score = base_score + recency_boost + access_boost

                # Apply tier weight
                weighted_score = score * 1.5
                all_results.append((item, weighted_score, "short_term"))

        # Search working memory
        if "working" in tiers:
            working_items = self.working.search(query, limit=limit)
            for item in working_items:
                # Weight by access count and quality
                base_score = 1.0
                access_boost = min(item.access_count / 10.0, 1.0)
                quality_boost = item.quality_score or 0.0
                score = base_score + access_boost + quality_boost

                # Apply tier weight
                weighted_score = score * 1.2
                all_results.append((item, weighted_score, "working"))

        # Search long-term memory
        if "long_term" in tiers:
            long_term_patterns = self.long_term.search(query, limit=limit)
            for pattern in long_term_patterns:
                # Pattern comes with relevance score
                score = pattern.relevance_score if hasattr(pattern, "relevance_score") else 1.0

                # Apply tier weight (1.0x)
                weighted_score = score * 1.0
                all_results.append((pattern, weighted_score, "long_term"))

        # Sort by weighted score
        all_results.sort(key=lambda x: x[1], reverse=True)

        return all_results[:limit]

    def record(self, item: MemoryItem):
        """
        Record to short-term, auto-promote based on rules.

        Args:
            item: Memory item to record
        """
        # Add to short-term
        self.short_term.add(item)

        # Check if should promote to working
        if self.promotion_rules.should_promote_to_working(item):
            self.working.add(item)
            logger.debug(f"Promoted item {item.id} to working memory")

    def update_outcome(self, item_id: str, outcome: str, quality_score: float):
        """
        Update item outcome and trigger promotion check.

        Args:
            item_id: Item ID to update
            outcome: Outcome value ("success", "partial", "failed")
            quality_score: Quality score (0.0-1.0)
        """
        # Try to find item in short-term first
        item = self.short_term.get(item_id)

        if not item:
            # Try working memory
            item = self.working.get(item_id)

        if item:
            item.outcome = outcome
            item.quality_score = quality_score

            # Update in both tiers
            self.short_term.add(item)
            self.working.add(item)

            # Check promotion to long-term
            # Note: Long-term memory uses PatternMemory which is populated via git indexing
            # We log this for future integration with pattern generation
            if self.promotion_rules.should_promote_to_long_term(item):
                logger.info(
                    f"Item {item_id} qualifies for long-term promotion (outcome={outcome}, quality={quality_score})"
                )

    def end_session(self):
        """End-of-session processing: promote/consolidate."""
        # Promote frequently accessed short-term items to working
        frequently_accessed = self.short_term.get_frequently_accessed(threshold=3)
        for item in frequently_accessed:
            self.working.add(item)
            logger.debug(f"Promoted frequently accessed item {item.id} to working memory")

        # Cleanup expired working memory items
        self.working.cleanup_expired()

        # Clear short-term memory
        self.short_term.clear()

        logger.info("Session ended, memory consolidated")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics across all tiers."""
        return {
            "short_term": self.short_term.get_stats(),
            "working": self.working.get_stats(),
            "long_term": self.long_term.get_stats(),
            "promotion_rules": {
                "working_access_threshold": self.promotion_rules.working_access_threshold,
                "long_term_quality_threshold": self.promotion_rules.long_term_quality_threshold,
            },
        }
