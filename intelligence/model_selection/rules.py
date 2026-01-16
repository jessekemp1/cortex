#!/usr/bin/env python3
"""
Rule-Based Model Recommender.

Provides fallback recommendations when no historical data available.
Uses hardcoded heuristics based on task type and complexity.
"""

from typing import Any, Dict

from intelligence.model_selection.models import ModelRecommendation


class RuleBasedRecommender:
    """
    Rule-based model recommendations.

    Fallback system used when ModelPerformanceLearner has insufficient data.
    Provides immediate value with reasonable defaults.
    """

    # Task type → model mapping
    RULES = {
        # Simple operations (Haiku)
        "explore": "haiku",
        "search": "haiku",
        "read": "haiku",
        "list": "haiku",
        "find": "haiku",
        # Moderate operations (Sonnet)
        "bug_fix": "sonnet",
        "implement": "sonnet",
        "debug": "sonnet",
        "test": "sonnet",
        "update": "sonnet",
        # Complex operations (Opus)
        "refactor": "opus",
        "design": "opus",
        "architect": "opus",
        "optimize": "opus",
        "migrate": "opus",
    }

    # Complexity fallback
    COMPLEXITY_MAP = {
        "simple": "haiku",
        "moderate": "sonnet",
        "complex": "opus",
    }

    # Model cost estimates (per 1K tokens, approximate)
    MODEL_COSTS = {
        "haiku": 0.0025,
        "sonnet": 0.0075,
        "opus": 0.045,
    }

    # Token estimates by complexity
    TOKEN_ESTIMATES = {
        "simple": 1500,
        "moderate": 3000,
        "complex": 5000,
    }

    def recommend(
        self, task_type: str, complexity: str, context: Dict[str, Any]
    ) -> ModelRecommendation:
        """
        Generate rule-based model recommendation.

        Args:
            task_type: Type of task (e.g., "bug_fix", "explore")
            complexity: Classified complexity ("simple", "moderate", "complex")
            context: Additional context (unused in rules, but kept for interface consistency)

        Returns:
            ModelRecommendation with rule-based reasoning
        """
        # Try task type match first
        if task_type in self.RULES:
            model = self.RULES[task_type]
            reason = f"Task type '{task_type}' typically uses {model}"
        else:
            # Fall back to complexity
            model = self.COMPLEXITY_MAP.get(complexity, "sonnet")
            reason = f"Complexity '{complexity}' suggests {model}"

        # Estimate tokens and cost
        estimated_tokens = self.TOKEN_ESTIMATES.get(complexity, 3000)
        estimated_cost = (estimated_tokens / 1000) * self.MODEL_COSTS[model]

        # Get alternatives
        alternatives = self._get_alternatives(model, complexity)

        return ModelRecommendation(
            model=model,
            confidence=0.6,  # Rules have moderate confidence
            reasoning=f"[RULES] {reason}",
            estimated_success_rate=0.75,  # Conservative estimate
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost,
            similar_tasks_count=0,  # No historical data
            historical_success_rate=0.0,
            alternatives=alternatives,
        )

    def _get_alternatives(self, selected_model: str, complexity: str) -> list:
        """
        Generate alternative model options.

        Args:
            selected_model: The selected model
            complexity: Task complexity

        Returns:
            List of alternative models with rationale
        """
        alternatives = []
        models = ["haiku", "sonnet", "opus"]

        for model in models:
            if model == selected_model:
                continue

            estimated_tokens = self.TOKEN_ESTIMATES.get(complexity, 3000)
            estimated_cost = (estimated_tokens / 1000) * self.MODEL_COSTS[model]

            # Determine suitability
            model_complexity_map = {
                "haiku": "simple",
                "sonnet": "moderate",
                "opus": "complex",
            }
            model_complexity = model_complexity_map[model]

            if model_complexity < complexity:
                suitability = "may_struggle"
                note = "Might not handle full complexity"
            elif model_complexity > complexity:
                suitability = "overkill"
                note = "More capable than needed (higher cost)"
            else:
                suitability = "suitable"
                note = "Appropriate for this complexity"

            alternatives.append(
                {
                    "model": model,
                    "estimated_cost": estimated_cost,
                    "estimated_tokens": estimated_tokens,
                    "suitability": suitability,
                    "note": note,
                }
            )

        return alternatives

    def explain_rules(self) -> str:
        """
        Explain the rule-based system (for documentation/debugging).

        Returns:
            Human-readable explanation of rules
        """
        explanation = "Rule-Based Model Selection\n"
        explanation += "=" * 50 + "\n\n"

        explanation += "Task Type Rules:\n"
        for task_type, model in sorted(self.RULES.items()):
            explanation += f"  {task_type:15} → {model}\n"

        explanation += "\nComplexity Fallback:\n"
        for complexity, model in self.COMPLEXITY_MAP.items():
            explanation += f"  {complexity:15} → {model}\n"

        explanation += "\nConfidence: 0.6 (moderate - rules are heuristics)\n"
        explanation += "Success Rate: ~75% (conservative estimate)\n"

        return explanation
