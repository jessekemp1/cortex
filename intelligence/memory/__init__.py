"""
Layer 2: Pattern Memory

Pattern recognition and historical learning from past work.
"""

from intelligence.memory.pattern_memory import (
    PatternMemory,
    SimilarWork
)
from intelligence.memory.pattern_indexer import (
    Pattern,
    PatternIndexer,
    PatternSearcher
)

__all__ = [
    'PatternMemory',
    'SimilarWork',
    'Pattern',
    'PatternIndexer',
    'PatternSearcher',
]
