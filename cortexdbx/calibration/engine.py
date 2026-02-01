"""
Beta-Binomial calibration engine for CortexDBx.

Updates confidence per (context, strategy) based on outcomes.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List, Any
import math


@dataclass
class CalibrationState:
    """State for a single (context, strategy) edge."""

    alpha: float
    beta: float
    success_count: int
    failure_count: int
    partial_count: int

    @property
    def confidence(self) -> float:
        """Current P(success) estimate."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def evidence_count(self) -> int:
        return self.success_count + self.failure_count + self.partial_count

    @property
    def uncertainty(self) -> float:
        """Variance of Beta distribution - higher = more uncertain."""
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))


class CalibrationEngine:
    """
    Bayesian calibration using Beta-Binomial model.

    Updates confidence per (context, strategy) pair based on outcomes.
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.states: Dict[Tuple[str, str], CalibrationState] = {}

    def get_state(self, context_id: str, strategy_id: str) -> CalibrationState:
        """Get or create calibration state for (context, strategy)."""
        key = (context_id, strategy_id)
        if key not in self.states:
            self.states[key] = CalibrationState(
                alpha=self.prior_alpha,
                beta=self.prior_beta,
                success_count=0,
                failure_count=0,
                partial_count=0,
            )
        return self.states[key]

    def update(
        self, context_id: str, strategy_id: str, result: str
    ) -> CalibrationState:
        """
        Update calibration based on new outcome.

        result: 'SUCCESS' (counts as 1), 'PARTIAL' (counts as 0.5), 'FAILURE' (counts as 0)
        """
        state = self.get_state(context_id, strategy_id)
        result_upper = result.upper()

        if result_upper == "SUCCESS":
            state.alpha += 1.0
            state.success_count += 1
        elif result_upper == "PARTIAL":
            state.alpha += 0.5
            state.beta += 0.5
            state.partial_count += 1
        else:
            state.beta += 1.0
            state.failure_count += 1

        return state

    def get_confidence(
        self, context_id: str, strategy_id: str
    ) -> Tuple[float, str]:
        """
        Get current confidence with explanation.

        Returns: (confidence, explanation)
        """
        state = self.get_state(context_id, strategy_id)

        if state.evidence_count == 0:
            return 0.5, "No historical data"

        confidence = state.confidence
        explanation = (
            f"{confidence:.0%} confidence based on {state.evidence_count} outcomes "
            f"({state.success_count} success, {state.failure_count} failure, "
            f"{state.partial_count} partial)"
        )
        return confidence, explanation

    def ingest_outcomes(
        self, outcomes: List[Dict[str, Any]]
    ) -> int:
        """
        Ingest a list of outcome records and update calibration.

        Each outcome must have context_id, strategy_id, result.
        Returns count of outcomes ingested.
        """
        count = 0
        for o in outcomes:
            ctx = o.get("context_id")
            strat = o.get("strategy_id")
            result = o.get("result")
            if ctx and strat and result:
                self.update(ctx, strat, result)
                count += 1
        return count

    def evaluate_calibration(
        self, ground_truth: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Evaluate calibration quality against ground truth.

        ground_truth: strategy_id -> actual success rate
        Returns metrics including Brier score and MAE.
        """
        predictions: List[float] = []
        actuals: List[float] = []

        for (ctx, strat), state in self.states.items():
            if strat in ground_truth and state.evidence_count >= 5:
                predictions.append(state.confidence)
                actuals.append(ground_truth[strat])

        if not predictions:
            return {"error": "Insufficient data for evaluation", "n": 0}

        brier = sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / len(
            predictions
        )
        mae = sum(abs(p - a) for p, a in zip(predictions, actuals)) / len(
            predictions
        )

        high_conf = [(p, a) for p, a in zip(predictions, actuals) if p > 0.8]
        precision_high = (
            sum(1 for p, a in high_conf if a > 0.6) / len(high_conf)
            if high_conf
            else None
        )

        return {
            "brier_score": brier,
            "mean_absolute_error": mae,
            "precision_at_high_confidence": precision_high,
            "num_evaluated": len(predictions),
        }

    def get_top_strategies(
        self, context_id: str, min_confidence: float = 0.0, limit: int = 10
    ) -> List[Tuple[str, float]]:
        """Return (strategy_id, confidence) for a context, sorted by confidence."""
        candidates = [
            (strat_id, state.confidence)
            for (ctx_id, strat_id), state in self.states.items()
            if ctx_id == context_id and state.confidence >= min_confidence
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]
