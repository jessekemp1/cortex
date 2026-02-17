"""
Cortex Evaluation System - AI-as-a-Judge for quality assessment

Implements automated quality evaluation using Claude as a judge.
Part of AI Engineering Improvements Phase 2.
"""

try:
    from cortex.intelligence.evaluation.quality_judge import (
        PatternScore,
        QualityJudge,
        RecommendationScore,
    )
except ImportError:
    from intelligence.evaluation.quality_judge import (  # type: ignore[no-redef]
        PatternScore,
        QualityJudge,
        RecommendationScore,
    )

__all__ = [
    "QualityJudge",
    "PatternScore",
    "RecommendationScore",
]
