#!/usr/bin/env python3
"""
Context-Aware Model Recommender.

Recommends optimal model (Haiku/Sonnet/Opus) based on:
- Task type and complexity
- Orchestration context (budget, time, priority)
- Historical performance data
- Rule-based fallbacks
"""

from datetime import timedelta

from intelligence.model_selection.classifier import TaskComplexityClassifier
from intelligence.model_selection.models import (
    ModelRecommendation,
    OrchestrationContext,
)
from intelligence.model_selection.rules import RuleBasedRecommender


class ContextAwareModelRecommender:
    """
    Intelligent model recommender with context awareness.

    Key innovation: Considers orchestration context (budget, time, priority)
    not just task characteristics.
    """

    def __init__(self):
        self.classifier = TaskComplexityClassifier()
        self.rule_recommender = RuleBasedRecommender()
        # Note: ModelPerformanceLearner will be added in Week 2

    def recommend(
        self,
        task_description: str,
        task_type: str,
        context: OrchestrationContext,
    ) -> ModelRecommendation:
        """
        Get context-aware model recommendation.

        Args:
            task_description: Description of the task
            task_type: Type of task (explore, implement, etc.)
            context: Orchestration context with budget/time/priority

        Returns:
            ModelRecommendation with reasoning
        """
        # 1. Classify complexity
        complexity, complexity_conf = self.classifier.classify(
            task_description, {"files": context.files, "project": context.project}
        )

        # 2. Get base recommendation (from rules for now, learner in Week 2)
        base_rec = self.rule_recommender.recommend(task_type, complexity, {})

        # 3. Apply context adjustments (KEY DIFFERENTIATION)
        adjusted_rec = self._apply_context_adjustments(base_rec, context, complexity)

        return adjusted_rec

    def _apply_context_adjustments(
        self,
        rec: ModelRecommendation,
        context: OrchestrationContext,
        complexity: str,
    ) -> ModelRecommendation:
        """
        Adjust recommendation based on orchestration context.

        This is where context-awareness happens.
        """
        adjustments = []
        model = rec.model
        confidence = rec.confidence

        # BUDGET CONSTRAINT
        if context.remaining_budget < 0.50:
            # Very low budget - force Haiku
            if model != "haiku":
                model = "haiku"
                confidence *= 0.7  # Lower confidence (forced)
                adjustments.append(
                    "Downgraded to Haiku due to low budget ($%.2f)" % context.remaining_budget
                )

        elif context.remaining_budget < 1.00:
            # Low budget - prefer cheaper models
            if model == "opus":
                model = "sonnet"
                adjustments.append("Downgraded Opus→Sonnet due to budget constraint")

        # TIME PRESSURE
        if context.remaining_time < timedelta(minutes=15):
            # Very little time - prefer speed
            if model == "opus":
                model = "sonnet"
                adjustments.append("Downgraded Opus→Sonnet: time pressure (faster)")
            # Don't downgrade sonnet→haiku in time pressure (may cause failures)

        # CRITICAL TASK + RETRY
        if context.task_priority == "high" and context.is_retry:
            # Critical task failed once - upgrade for reliability
            # BUT respect budget constraints (budget is HARD limit)
            if model == "haiku" and context.remaining_budget > 1.00:
                model = "sonnet"
                adjustments.append("Upgraded Haiku→Sonnet: critical task retry")
            elif model == "sonnet" and context.remaining_budget > 2.00:
                # Only upgrade to Opus if we can afford it
                model = "opus"
                adjustments.append("Upgraded Sonnet→Opus: critical task retry")

        # HIGH PRIORITY + ADEQUATE BUDGET
        if context.task_priority == "high" and context.remaining_budget > 3.00:
            # High priority with budget - ensure quality
            if model == "haiku" and complexity != "simple":
                model = "sonnet"
                adjustments.append("Upgraded Haiku→Sonnet: high priority + budget available")

        # PARALLEL LOAD (future enhancement placeholder)
        # if context.parallel_tasks > 3:
        #     # Many parallel tasks - prefer faster models to reduce queue time
        #     pass

        # Update recommendation
        if adjustments:
            new_reasoning = (
                rec.reasoning
                + "\n\nContext adjustments:\n"
                + "\n".join(f"  • {adj}" for adj in adjustments)
            )
            return ModelRecommendation(
                model=model,
                confidence=confidence,
                reasoning=new_reasoning,
                estimated_success_rate=rec.estimated_success_rate,
                estimated_tokens=rec.estimated_tokens,
                estimated_cost_usd=rec.estimated_cost_usd * self._cost_multiplier(rec.model, model),
                similar_tasks_count=rec.similar_tasks_count,
                historical_success_rate=rec.historical_success_rate,
                alternatives=rec.alternatives,
            )
        else:
            return rec

    def _cost_multiplier(self, original_model: str, new_model: str) -> float:
        """Calculate cost multiplier when changing models."""
        costs = {"haiku": 1.0, "sonnet": 3.0, "opus": 18.0}
        return costs.get(new_model, 3.0) / costs.get(original_model, 3.0)
