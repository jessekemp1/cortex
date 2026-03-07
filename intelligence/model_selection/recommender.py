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
    not just task characteristics. When historical outcome data is available,
    learned performance overrides rule-based defaults.
    """

    def __init__(self):
        self.classifier = TaskComplexityClassifier()
        self.rule_recommender = RuleBasedRecommender()
        self._perf_cache: dict | None = None
        self._perf_cache_age: float = 0

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

        # 2. Get base recommendation from rules
        base_rec = self.rule_recommender.recommend(task_type, complexity, {})

        # 3. Override with learned performance data if available
        learned_rec = self._apply_learned_override(base_rec, task_type, context.project)

        # 4. Apply context adjustments (budget/time/priority)
        adjusted_rec = self._apply_context_adjustments(learned_rec, context, complexity)

        return adjusted_rec

    def _apply_learned_override(
        self,
        rec: ModelRecommendation,
        task_type: str,
        project: str,
    ) -> ModelRecommendation:
        """
        Override rule-based recommendation with learned performance data.

        Only overrides when historical data shows a statistically meaningful
        difference (min 3 samples, >10% success rate improvement).
        """
        try:
            from intelligence.outcome_logger import compare_model_performance
        except ImportError:
            return rec

        perf = self._get_perf_data(task_type, project)
        if not perf or "error" in perf or not perf.get("by_task_type"):
            return rec

        task_data = perf["by_task_type"].get(task_type)
        if not task_data or not task_data.get("best_model"):
            return rec

        best_model = task_data["best_model"]
        best_rate = task_data["success_rate"]
        samples = task_data["samples"]

        # Only override if learned model differs and has meaningfully better data
        if best_model == rec.model:
            # Same model — just enrich with historical data
            return ModelRecommendation(
                model=rec.model,
                confidence=min(0.95, rec.confidence + 0.15),
                reasoning=rec.reasoning
                + f"\n[LEARNED] Confirmed by {samples} outcomes ({best_rate:.0%} success)",
                estimated_success_rate=best_rate,
                estimated_tokens=rec.estimated_tokens,
                estimated_cost_usd=rec.estimated_cost_usd,
                similar_tasks_count=samples,
                historical_success_rate=best_rate,
                alternatives=rec.alternatives,
            )

        # Different model — override if improvement is significant
        all_models = task_data.get("all_models", {})
        current_rate = all_models.get(rec.model, 0.0)

        if best_rate - current_rate < 0.10:
            # Less than 10% improvement — not worth overriding
            return rec

        return ModelRecommendation(
            model=best_model,
            confidence=min(0.90, 0.7 + (samples / 50)),  # Confidence grows with data
            reasoning=(
                f"[LEARNED] Overriding {rec.model}→{best_model} for {task_type}: "
                f"{best_rate:.0%} success (n={samples}) vs {current_rate:.0%} for {rec.model}"
            ),
            estimated_success_rate=best_rate,
            estimated_tokens=rec.estimated_tokens,
            estimated_cost_usd=rec.estimated_cost_usd
            * self._cost_multiplier(rec.model, best_model),
            similar_tasks_count=samples,
            historical_success_rate=best_rate,
            alternatives=rec.alternatives,
        )

    def _get_perf_data(self, task_type: str, project: str) -> dict | None:
        """Get performance data with simple time-based caching (60s TTL)."""
        import time

        now = time.time()
        if self._perf_cache is not None and (now - self._perf_cache_age) < 60:
            return self._perf_cache

        try:
            from intelligence.outcome_logger import compare_model_performance

            self._perf_cache = compare_model_performance(
                task_type=task_type,
                project=project if project else None,
                min_samples=3,
            )
            self._perf_cache_age = now
            return self._perf_cache
        except Exception:
            return None

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
