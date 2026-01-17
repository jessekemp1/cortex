"""
Prediction Tracker - Bayesian confidence calibration by domain.

Extends the core calibration concept from v21/learning/calibration.py
to support domain-specific trust building.

The key insight: Trust should be EARNED and SPECIFIC.
- "AI is good at code" doesn't mean "AI is good at architecture"
- Calibration curves by domain enable calibrated confidence

Uses Beta-Binomial Bayesian updating:
- Prior: Beta(α=2, β=2) = neutral 50% expectation
- Posterior: Beta(α + successes, β + failures)
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Domain categories for trust calibration
DOMAINS = [
    "code",  # Implementation, syntax, algorithms
    "architecture",  # Design decisions, patterns
    "testing",  # Test strategy, coverage
    "debugging",  # Root cause analysis
    "planning",  # Task breakdown, estimation
    "documentation",  # Docs, comments
]

# Bayesian prior parameters
PRIOR_ALPHA = 2  # Pseudo-successes
PRIOR_BETA = 2  # Pseudo-failures
MIN_OUTCOMES_FOR_CERTAINTY = 10  # Minimum data points to trust calibration


@dataclass
class Prediction:
    """A single prediction with confidence."""

    prediction_id: str
    timestamp: datetime
    domain: str
    description: str
    confidence: float  # AI's stated confidence (0-1)
    outcome: Optional[bool] = None  # True=correct, False=incorrect, None=pending
    outcome_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        if self.outcome_timestamp:
            data["outcome_timestamp"] = self.outcome_timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prediction":
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("outcome_timestamp"):
            data["outcome_timestamp"] = datetime.fromisoformat(data["outcome_timestamp"])
        return cls(**data)


@dataclass
class DomainCalibration:
    """Calibration data for a specific domain."""

    domain: str
    successes: int = 0
    failures: int = 0
    total: int = 0

    # Bayesian posterior
    @property
    def alpha(self) -> float:
        return PRIOR_ALPHA + self.successes

    @property
    def beta(self) -> float:
        return PRIOR_BETA + self.failures

    @property
    def calibrated_confidence(self) -> float:
        """
        Bayesian posterior mean, blended with prior based on data certainty.

        Low data → stays near 50% (prior)
        High data → reflects actual success rate
        """
        posterior_mean = self.alpha / (self.alpha + self.beta)
        certainty = min(1.0, self.total / MIN_OUTCOMES_FOR_CERTAINTY)
        return (posterior_mean * certainty) + (0.5 * (1 - certainty))

    @property
    def certainty(self) -> float:
        """How confident we are in the calibration (0-1)."""
        return min(1.0, self.total / MIN_OUTCOMES_FOR_CERTAINTY)

    @property
    def success_rate(self) -> float:
        """Raw success rate (before Bayesian adjustment)."""
        if self.total == 0:
            return 0.5
        return self.successes / self.total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "successes": self.successes,
            "failures": self.failures,
            "total": self.total,
            "calibrated_confidence": round(self.calibrated_confidence, 3),
            "certainty": round(self.certainty, 2),
            "success_rate": round(self.success_rate, 3),
        }


class PredictionTracker:
    """
    Tracks predictions and outcomes for calibration.

    Stores:
    - Individual predictions with outcomes
    - Aggregated calibration curves by domain
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".cortex" / "research" / "bandwidth"

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.predictions_file = self.storage_dir / "predictions.jsonl"
        self.calibration_file = self.storage_dir / "calibration_curves.json"

    def record_prediction(
        self,
        prediction_id: str,
        confidence: float,
        domain: str,
        description: str = "",
    ) -> Prediction:
        """
        Record a new prediction.

        Args:
            prediction_id: Unique identifier
            confidence: AI's stated confidence (0-1)
            domain: Domain category (code, architecture, etc.)
            description: What was predicted

        Returns:
            The recorded Prediction
        """
        if domain not in DOMAINS:
            domain = "code"  # Default to code

        prediction = Prediction(
            prediction_id=prediction_id,
            timestamp=datetime.now(),
            domain=domain,
            description=description,
            confidence=confidence,
        )

        # Append to predictions file
        with open(self.predictions_file, "a") as f:
            f.write(json.dumps(prediction.to_dict()) + "\n")

        return prediction

    def record_outcome(
        self,
        prediction_id: str,
        was_correct: bool,
    ) -> Optional[Prediction]:
        """
        Record outcome for a prediction.

        Args:
            prediction_id: ID of the prediction
            was_correct: Whether the prediction was correct

        Returns:
            Updated Prediction or None if not found
        """
        # Find and update the prediction
        predictions = self._load_all_predictions()
        updated = None

        for pred in predictions:
            if pred.prediction_id == prediction_id:
                pred.outcome = was_correct
                pred.outcome_timestamp = datetime.now()
                updated = pred
                break

        if updated:
            # Rewrite predictions file
            self._save_all_predictions(predictions)

            # Update calibration curves
            self._update_calibration(updated.domain, was_correct)

        return updated

    def get_calibration(self, domain: Optional[str] = None) -> Dict[str, DomainCalibration]:
        """
        Get calibration data for all domains or a specific domain.

        Returns:
            Dict of domain -> DomainCalibration
        """
        calibrations = self._load_calibrations()

        if domain:
            if domain in calibrations:
                return {domain: calibrations[domain]}
            return {domain: DomainCalibration(domain=domain)}

        # Return all domains with defaults for missing
        result = {}
        for d in DOMAINS:
            if d in calibrations:
                result[d] = calibrations[d]
            else:
                result[d] = DomainCalibration(domain=d)

        return result

    def get_calibrated_confidence(self, raw_confidence: float, domain: str) -> float:
        """
        Adjust raw confidence based on historical calibration.

        If AI says 80% confident in "architecture" but historical accuracy
        is 60%, this returns ~60% (weighted by data certainty).
        """
        calibrations = self._load_calibrations()

        if domain not in calibrations:
            return raw_confidence  # No calibration data, trust AI

        cal = calibrations[domain]

        if cal.certainty < 0.5:
            return raw_confidence  # Not enough data

        # Blend raw confidence with calibrated confidence
        # More data → more weight on calibration
        return (raw_confidence * (1 - cal.certainty)) + (cal.calibrated_confidence * cal.certainty)

    def get_pending_predictions(self, days: int = 7) -> List[Prediction]:
        """Get predictions awaiting outcomes."""
        cutoff = datetime.now() - timedelta(days=days)
        predictions = self._load_all_predictions()

        return [
            p
            for p in predictions
            if p.outcome is None and p.timestamp > cutoff
        ]

    def _load_all_predictions(self) -> List[Prediction]:
        """Load all predictions from file."""
        if not self.predictions_file.exists():
            return []

        predictions = []
        try:
            with open(self.predictions_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    predictions.append(Prediction.from_dict(json.loads(line)))
        except (json.JSONDecodeError, IOError):
            pass

        return predictions

    def _save_all_predictions(self, predictions: List[Prediction]) -> None:
        """Save all predictions to file."""
        with open(self.predictions_file, "w") as f:
            for pred in predictions:
                f.write(json.dumps(pred.to_dict()) + "\n")

    def _load_calibrations(self) -> Dict[str, DomainCalibration]:
        """Load calibration curves."""
        if not self.calibration_file.exists():
            return {}

        try:
            with open(self.calibration_file, "r") as f:
                data = json.load(f)

            return {
                domain: DomainCalibration(
                    domain=domain,
                    successes=cal.get("successes", 0),
                    failures=cal.get("failures", 0),
                    total=cal.get("total", 0),
                )
                for domain, cal in data.items()
            }
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_calibrations(self, calibrations: Dict[str, DomainCalibration]) -> None:
        """Save calibration curves."""
        data = {domain: cal.to_dict() for domain, cal in calibrations.items()}

        with open(self.calibration_file, "w") as f:
            json.dump(data, f, indent=2)

    def _update_calibration(self, domain: str, was_correct: bool) -> None:
        """Update calibration for a domain after an outcome."""
        calibrations = self._load_calibrations()

        if domain not in calibrations:
            calibrations[domain] = DomainCalibration(domain=domain)

        cal = calibrations[domain]
        cal.total += 1

        if was_correct:
            cal.successes += 1
        else:
            cal.failures += 1

        self._save_calibrations(calibrations)


# Convenience functions
def record_prediction(
    prediction_id: str,
    confidence: float,
    domain: str,
    description: str = "",
) -> Prediction:
    """Record a prediction (convenience function)."""
    tracker = PredictionTracker()
    return tracker.record_prediction(prediction_id, confidence, domain, description)


def record_outcome(prediction_id: str, was_correct: bool) -> Optional[Prediction]:
    """Record an outcome (convenience function)."""
    tracker = PredictionTracker()
    return tracker.record_outcome(prediction_id, was_correct)
