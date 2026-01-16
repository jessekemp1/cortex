"""
Layer 2: Pattern Memory

Pattern recognition and historical learning from past work.
"""

from intelligence.memory.pattern_indexer import Pattern, PatternIndexer, PatternSearcher
from intelligence.memory.pattern_memory import PatternMemory, SimilarWork

__all__ = [
    "PatternMemory",
    "SimilarWork",
    "Pattern",
    "PatternIndexer",
    "PatternSearcher",
]
