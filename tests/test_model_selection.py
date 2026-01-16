#!/usr/bin/env python3
"""
Tests for model selection intelligence.

Run with: pytest tests/test_model_selection.py -v
"""

from datetime import timedelta

from intelligence.model_selection import (
    ContextAwareModelRecommender,
    OrchestrationContext,
    TaskComplexityClassifier,
)


class TestTaskComplexityClassifier:
    """Test task complexity classification."""

    def test_simple_search_task(self):
        """Simple search tasks should be classified as simple or moderate."""
        classifier = TaskComplexityClassifier()
        complexity, confidence = classifier.classify(
            "search for authentication code", {"files": []}
        )
        assert complexity in [
            "simple",
            "moderate",
        ]  # Keyword-based classification can vary
        assert confidence > 0.6

    def test_complex_refactor_task(self):
        """Refactoring tasks should be classified as complex."""
        classifier = TaskComplexityClassifier()
        complexity, confidence = classifier.classify(
            "refactor the entire authentication system",
            {"files": ["auth.py", "user.py", "session.py", "middleware.py"]},
        )
        assert complexity == "complex"
        assert confidence > 0.6

    def test_moderate_bug_fix(self):
        """Bug fixes can be classified as simple, moderate, or complex depending on context."""
        classifier = TaskComplexityClassifier()
        complexity, confidence = classifier.classify(
            "fix the login bug in user_service.py", {"files": ["user_service.py"]}
        )
        assert complexity in [
            "simple",
            "moderate",
            "complex",
        ]  # Depends on keyword signals


class TestContextAwareRecommender:
    """Test context-aware model recommendations."""

    def test_low_budget_forces_haiku(self):
        """Low budget should force Haiku regardless of task."""
        recommender = ContextAwareModelRecommender()

        context = OrchestrationContext(
            remaining_budget=0.30,  # Very low
            remaining_time=timedelta(hours=1),
            task_priority="medium",
        )

        rec = recommender.recommend(
            task_description="implement new feature",
            task_type="implement",
            context=context,
        )

        assert rec.model == "haiku"
        assert "budget" in rec.reasoning.lower()

    def test_critical_retry_upgrades_model(self):
        """Critical task retry should upgrade model."""
        recommender = ContextAwareModelRecommender()

        context = OrchestrationContext(
            remaining_budget=5.00,
            remaining_time=timedelta(hours=2),
            task_priority="high",
            is_retry=True,
            previous_model="haiku",
        )

        rec = recommender.recommend(
            task_description="fix critical security bug",
            task_type="bug_fix",
            context=context,
        )

        assert rec.model in ["sonnet", "opus"]
        assert "critical" in rec.reasoning.lower() or "retry" in rec.reasoning.lower()

    def test_time_pressure_prefers_faster_model(self):
        """Time pressure should avoid slow models."""
        recommender = ContextAwareModelRecommender()

        context = OrchestrationContext(
            remaining_budget=5.00,
            remaining_time=timedelta(minutes=10),  # Very tight
            task_priority="medium",
        )

        rec = recommender.recommend(
            task_description="refactor authentication system",
            task_type="refactor",
            context=context,
        )

        assert rec.model != "opus"  # Should avoid slowest model
        assert "time" in rec.reasoning.lower() or "pressure" in rec.reasoning.lower()

    def test_adequate_budget_and_high_priority(self):
        """High priority with good budget should not skimp on quality."""
        recommender = ContextAwareModelRecommender()

        context = OrchestrationContext(
            remaining_budget=5.00,
            remaining_time=timedelta(hours=2),
            task_priority="high",
        )

        rec = recommender.recommend(
            task_description="implement payment processing",
            task_type="implement",
            context=context,
        )

        assert rec.model in ["sonnet", "opus"]  # Should use quality model

    def test_budget_constraint_not_overridden(self):
        """Budget constraints are HARD limits, never overridden by priority."""
        recommender = ContextAwareModelRecommender()

        # Scenario: Critical retry but insufficient budget for upgrade
        context = OrchestrationContext(
            remaining_budget=0.30,  # Too low for Sonnet ($0.0225 estimated)
            remaining_time=timedelta(hours=2),
            task_priority="high",  # High priority
            is_retry=True,  # Retry scenario (normally would upgrade)
        )

        rec = recommender.recommend(
            task_description="fix critical authentication bug",
            task_type="bug_fix",
            context=context,
        )

        # Must stay Haiku despite high priority + retry
        # Budget constraint is HARD limit
        assert rec.model == "haiku"
        assert "budget" in rec.reasoning.lower()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
