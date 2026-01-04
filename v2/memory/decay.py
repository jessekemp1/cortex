"""Temporal decay for memory relevance.

Older memories decay in relevance over time, with type-specific half-lives.
Frequently used memories decay slower.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .types import TypedMemory


@dataclass
class DecayResult:
    """Result of decay calculation for a memory."""
    memory_id: str
    memory_type: str
    decay_factor: float
    effective_confidence: float
    days_since_use: int
    use_count: int
    is_stale: bool


class TemporalDecay:
    """Time-based relevance decay for memories.

    Uses exponential decay with configurable half-lives per memory type.
    Frequently used memories get a boost that slows decay.

    Formula:
        base_decay = 0.5 ^ (days_since_use / half_life)
        use_boost = min(0.3, use_count * 0.03)
        effective_relevance = min(1.0, base_decay + use_boost)
    """

    # Half-life in days (relevance drops to 50% after this time)
    DEFAULT_HALF_LIVES: Dict[str, int] = {
        "pattern": 180,    # 6 months - patterns stay relevant
        "incident": 90,    # 3 months - incidents fade faster
        "skill": 365,      # 1 year - skills are durable
        "decision": 730,   # 2 years - decisions are semi-permanent
        "fact": 365,       # 1 year - facts may become outdated
    }

    # Stale threshold - memories below this are candidates for cleanup
    DEFAULT_STALE_THRESHOLD = 0.1

    def __init__(
        self,
        half_lives: Optional[Dict[str, int]] = None,
        stale_threshold: float = DEFAULT_STALE_THRESHOLD
    ):
        """Initialize temporal decay.

        Args:
            half_lives: Custom half-lives per memory type (in days)
            stale_threshold: Decay factor below which memory is stale
        """
        self.half_lives = half_lives or self.DEFAULT_HALF_LIVES.copy()
        self.stale_threshold = stale_threshold

    def calculate_decay(
        self,
        memory_type: str,
        created_at: datetime,
        last_used: Optional[datetime] = None,
        use_count: int = 0
    ) -> float:
        """Calculate decay factor for a memory.

        Args:
            memory_type: Type of memory (pattern, incident, skill, decision)
            created_at: When the memory was created
            last_used: When the memory was last used (defaults to created_at)
            use_count: Number of times memory has been used

        Returns:
            Decay factor between 0.0 (fully decayed) and 1.0 (fully relevant)
        """
        now = datetime.utcnow()
        half_life = self.half_lives.get(memory_type.lower(), 180)

        # Use last_used if available, otherwise created_at
        reference_time = last_used or created_at
        days_old = max(0, (now - reference_time).days)

        # Exponential decay: relevance = 0.5 ^ (days / half_life)
        if half_life <= 0:
            base_decay = 1.0
        else:
            base_decay = math.pow(0.5, days_old / half_life)

        # Usage boost: each use adds ~3% relevance (diminishing, capped at 30%)
        use_boost = min(0.3, use_count * 0.03)

        # Final relevance (capped at 1.0)
        return min(1.0, base_decay + use_boost)

    def calculate_decay_result(
        self,
        memory: "TypedMemory"
    ) -> DecayResult:
        """Calculate detailed decay result for a memory.

        Args:
            memory: The memory to analyze

        Returns:
            DecayResult with all decay metrics
        """
        memory_type = memory.__class__.__name__.lower()
        decay_factor = self.calculate_decay(
            memory_type=memory_type,
            created_at=memory.created_at,
            last_used=memory.last_used,
            use_count=memory.use_count
        )

        days_since_use = max(0, (datetime.utcnow() - memory.last_used).days)

        return DecayResult(
            memory_id=memory.id,
            memory_type=memory_type,
            decay_factor=decay_factor,
            effective_confidence=memory.confidence * decay_factor,
            days_since_use=days_since_use,
            use_count=memory.use_count,
            is_stale=decay_factor < self.stale_threshold
        )

    def apply_decay(
        self,
        memories: List["TypedMemory"],
        sort_by_relevance: bool = True
    ) -> List["TypedMemory"]:
        """Apply decay to a list of memories.

        Sets `effective_confidence` on each memory based on decay.

        Args:
            memories: List of memories to process
            sort_by_relevance: If True, sort by effective_confidence descending

        Returns:
            Same memories with effective_confidence set
        """
        for memory in memories:
            memory_type = memory.__class__.__name__.lower()
            decay_factor = self.calculate_decay(
                memory_type=memory_type,
                created_at=memory.created_at,
                last_used=memory.last_used,
                use_count=memory.use_count
            )
            # Set effective confidence (original * decay)
            memory.effective_confidence = memory.confidence * decay_factor

        if sort_by_relevance:
            memories.sort(key=lambda m: m.effective_confidence, reverse=True)

        return memories

    def get_stale_memories(
        self,
        memories: List["TypedMemory"],
        threshold: Optional[float] = None
    ) -> List["TypedMemory"]:
        """Find memories that have decayed below threshold.

        Args:
            memories: List of memories to check
            threshold: Custom threshold (defaults to self.stale_threshold)

        Returns:
            List of stale memories
        """
        threshold = threshold if threshold is not None else self.stale_threshold
        stale = []

        for memory in memories:
            memory_type = memory.__class__.__name__.lower()
            decay = self.calculate_decay(
                memory_type=memory_type,
                created_at=memory.created_at,
                last_used=memory.last_used,
                use_count=memory.use_count
            )
            if decay < threshold:
                stale.append(memory)

        return stale

    def refresh_memory(self, memory: "TypedMemory") -> None:
        """Mark a memory as recently used (refreshes decay).

        Args:
            memory: Memory to refresh
        """
        memory.last_used = datetime.utcnow()
        memory.use_count += 1

    def get_decay_stats(
        self,
        memories: List["TypedMemory"]
    ) -> Dict:
        """Get statistics about decay across memories.

        Args:
            memories: List of memories to analyze

        Returns:
            Dict with decay statistics
        """
        if not memories:
            return {
                "total": 0,
                "stale_count": 0,
                "stale_percentage": 0.0,
                "avg_decay": 0.0,
                "by_type": {}
            }

        by_type: Dict[str, List[float]] = {}
        stale_count = 0

        for memory in memories:
            memory_type = memory.__class__.__name__.lower()
            decay = self.calculate_decay(
                memory_type=memory_type,
                created_at=memory.created_at,
                last_used=memory.last_used,
                use_count=memory.use_count
            )

            if memory_type not in by_type:
                by_type[memory_type] = []
            by_type[memory_type].append(decay)

            if decay < self.stale_threshold:
                stale_count += 1

        all_decays = [d for decays in by_type.values() for d in decays]

        return {
            "total": len(memories),
            "stale_count": stale_count,
            "stale_percentage": stale_count / len(memories) if memories else 0,
            "avg_decay": sum(all_decays) / len(all_decays) if all_decays else 0,
            "by_type": {
                t: {
                    "count": len(decays),
                    "avg_decay": sum(decays) / len(decays),
                    "min_decay": min(decays),
                    "max_decay": max(decays),
                }
                for t, decays in by_type.items()
            }
        }

    def estimate_days_until_stale(
        self,
        memory_type: str,
        current_decay: float = 1.0,
        use_count: int = 0
    ) -> int:
        """Estimate days until a memory becomes stale.

        Args:
            memory_type: Type of memory
            current_decay: Current decay factor (default 1.0 = new)
            use_count: Current use count

        Returns:
            Estimated days until stale
        """
        half_life = self.half_lives.get(memory_type.lower(), 180)
        use_boost = min(0.3, use_count * 0.03)

        # We need: base_decay + use_boost < stale_threshold
        # base_decay < stale_threshold - use_boost
        # 0.5^(days/half_life) < stale_threshold - use_boost
        # days/half_life > log_0.5(stale_threshold - use_boost)
        # days > half_life * log_0.5(stale_threshold - use_boost)

        target = self.stale_threshold - use_boost
        if target <= 0:
            return 999999  # Never stale with this use count

        # log_0.5(x) = log(x) / log(0.5)
        days = half_life * (math.log(target) / math.log(0.5))
        return max(0, int(days))
