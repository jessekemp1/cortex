"""
Learning System Configuration

Calibrates recommendation weights based on historical success rates.
Weights are multipliers applied to recommendation confidence scores.

Last calibrated: 2026-01-15
Source: 30-day analysis of outcomes.jsonl
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

# Recommendation type weights based on historical success rates
# Weight > 1.0 boosts recommendations, < 1.0 penalizes them
# These are derived from actual outcome data
RECOMMENDATION_TYPE_WEIGHTS = {
    # High performers (100% success rate in 30-day analysis)
    "next_action": 1.2,  # Boost - historically very accurate
    "goal_progress": 1.1,  # Slight boost - good track record
    # Medium performers
    "alert": 1.0,  # Neutral - alerts are important regardless
    "health": 1.0,  # Neutral
    # Low performers — split from legacy "optimization" (25% success rate)
    "performance": 0.7,  # Penalize - premature perf opts rarely survive review
    "refactor": 0.9,  # Near-neutral - refactors succeed when scoped well
    # Default for unknown types
    "default": 1.0,
}

# Confidence thresholds
MIN_CONFIDENCE = 0.3  # Below this, don't recommend
HIGH_CONFIDENCE = 0.8  # Above this, prioritize

# Learning rate - how quickly to adjust based on new outcomes
LEARNING_RATE = 0.1  # 10% adjustment per outcome


@dataclass
class LearningConfig:
    """Runtime learning configuration with persistence."""

    weights: Dict[str, float] = field(default_factory=lambda: RECOMMENDATION_TYPE_WEIGHTS.copy())
    min_outcomes_for_calibration: int = 5

    _config_path: Path = field(
        default_factory=lambda: Path.home() / ".cortex" / "learning_config.json"
    )

    def load(self):
        """Load weights from disk if available."""
        if self._config_path.exists():
            try:
                data = json.loads(self._config_path.read_text())
                self.weights = {
                    **RECOMMENDATION_TYPE_WEIGHTS,
                    **data.get("weights", {}),
                }
            except (json.JSONDecodeError, KeyError):
                pass
        return self

    def save(self):
        """Save current weights to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "weights": self.weights,
            "last_updated": __import__("datetime").datetime.now().isoformat(),
        }
        self._config_path.write_text(json.dumps(data, indent=2))

    def get_weight(self, recommendation_type: str) -> float:
        """Get weight for a recommendation type."""
        return self.weights.get(recommendation_type, self.weights.get("default", 1.0))

    def apply_weight(self, recommendation_type: str, base_confidence: float) -> float:
        """Apply weight to a confidence score."""
        weight = self.get_weight(recommendation_type)
        weighted = base_confidence * weight
        # Clamp to valid range
        return max(MIN_CONFIDENCE, min(1.0, weighted))

    def update_weight(self, recommendation_type: str, outcome: str):
        """
        Update weight based on outcome.

        Args:
            recommendation_type: Type of recommendation
            outcome: "success", "partial", or "failed"
        """
        current = self.weights.get(recommendation_type, 1.0)

        # Outcome adjustments
        if outcome == "success":
            adjustment = LEARNING_RATE * 0.1  # Boost slightly
        elif outcome == "partial":
            adjustment = 0  # No change
        else:  # failed
            adjustment = -LEARNING_RATE * 0.1  # Penalize

        new_weight = current + adjustment
        # Clamp between 0.5 and 1.5
        self.weights[recommendation_type] = max(0.5, min(1.5, new_weight))


# Global instance
_config = None


def get_learning_config() -> LearningConfig:
    """Get or create the global learning config."""
    global _config
    if _config is None:
        _config = LearningConfig().load()
    return _config
