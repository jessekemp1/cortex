#!/usr/bin/env python3
"""
Trust Governor

Policy-driven autonomy transitions based on calibration and guardrail health.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrustThresholds:
    promote_min_accuracy: float = 0.7
    promote_max_calibration_error: float = 0.2
    promote_max_overconfidence: float = 0.15
    degrade_max_calibration_error: float = 0.3
    degrade_max_overconfidence: float = 0.25
    degrade_min_accuracy: float = 0.5


class TrustGovernor:
    """Evaluates trust signals and recommends autonomy level transitions."""

    def __init__(
        self,
        metrics_path: Path | None = None,
        thresholds: TrustThresholds | None = None,
    ):
        self.metrics_path = metrics_path
        self.thresholds = thresholds or TrustThresholds()

    def _load_calibration_stats(self) -> dict[str, Any]:
        """Load calibration stats from MetricsTracker when available."""
        try:
            from metrics_tracker import MetricsTracker

            tracker = MetricsTracker(metrics_path=self.metrics_path) if self.metrics_path else MetricsTracker()
            return tracker.get_calibration_stats()
        except Exception:
            return {
                "total_predictions": 0,
                "accuracy": 0.0,
                "calibration_error": 1.0,
                "overconfidence_index": 1.0,
            }

    def evaluate(self, current_level: int = 1) -> dict[str, Any]:
        """
        Evaluate trust state and provide recommended level transition.

        Level convention:
        0 observe-only, 1 recommend-only, 2 controlled submit, 3 policy-autonomous.
        """
        stats = self._load_calibration_stats()
        accuracy = float(stats.get("accuracy", 0.0))
        calibration_error = float(stats.get("calibration_error", 1.0))
        overconfidence = abs(float(stats.get("overconfidence_index", 1.0)))
        total_predictions = int(stats.get("total_predictions", 0))

        action = "hold"
        next_level = current_level
        rationale = []

        if total_predictions < 10:
            rationale.append("insufficient_data")
            return {
                "action": "hold",
                "current_level": current_level,
                "next_level": current_level,
                "rationale": rationale,
                "stats": stats,
            }

        if (
            accuracy < self.thresholds.degrade_min_accuracy
            or calibration_error > self.thresholds.degrade_max_calibration_error
            or overconfidence > self.thresholds.degrade_max_overconfidence
        ):
            action = "degrade"
            next_level = max(0, current_level - 1)
            rationale.append("trust_gate_breach")
        elif (
            accuracy >= self.thresholds.promote_min_accuracy
            and calibration_error <= self.thresholds.promote_max_calibration_error
            and overconfidence <= self.thresholds.promote_max_overconfidence
        ):
            action = "promote"
            next_level = min(3, current_level + 1)
            rationale.append("trust_gate_pass")
        else:
            rationale.append("mixed_signals")

        return {
            "action": action,
            "current_level": current_level,
            "next_level": next_level,
            "rationale": rationale,
            "stats": stats,
        }

