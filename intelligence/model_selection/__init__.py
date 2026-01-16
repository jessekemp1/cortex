#!/usr/bin/env python3
"""
Model Selection Intelligence.

Provides intelligent model recommendations (Haiku/Sonnet/Opus)
based on task characteristics and orchestration context.
"""

from intelligence.model_selection.classifier import TaskComplexityClassifier
from intelligence.model_selection.models import (
    ModelOutcomeEntry,
    ModelRecommendation,
    OrchestrationContext,
    RecoveryAction,
    SessionOutcomeEntry,
    WorkflowOutcomeEntry,
)
from intelligence.model_selection.recommender import ContextAwareModelRecommender
from intelligence.model_selection.rules import RuleBasedRecommender

__all__ = [
    "TaskComplexityClassifier",
    "RuleBasedRecommender",
    "ContextAwareModelRecommender",
    "ModelRecommendation",
    "ModelOutcomeEntry",
    "WorkflowOutcomeEntry",
    "SessionOutcomeEntry",
    "OrchestrationContext",
    "RecoveryAction",
]
