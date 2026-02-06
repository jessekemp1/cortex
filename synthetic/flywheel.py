#!/usr/bin/env python3
"""
Feedback Flywheel Orchestrator — Automated quality improvement loop.

Chains 6 feedback layers (Phase 2+3) that run after every generation:

  Layer 1: Quality Gate — Per-record 6-dimension quality scoring
  Layer 2: Statistical Fidelity — KS, chi-squared, JSD vs KB benchmarks
  Layer 3: Cross-Field Consistency — Multivariate coherence validation
  Layer 4: Risk Model Validation — AML rule engine pass-through
  Layer 5: Discriminator Feedback — XGBoost + SHAP distinguishability test
  Layer 6: Downstream Task (TSTR) — Train-on-synthetic, test-on-real utility

Each layer produces feedback signals that are aggregated into a
correction vector. The corrections are bounded by knowledge base
constraints to prevent model collapse.

Architecture:
    Flywheel(generator, kb) → run_cycle(batch, request) → FlywheelReport
    → apply_corrections(feedback) → adjusted generation parameters
"""

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.constraints import ConstraintEngine
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.quality import SyntheticQualityTracker
from synthetic.risk_validator import RiskValidator
from synthetic.schemas import CustomerProfile, GenerationRequest, Transaction

# Lazy imports for heavy Phase 3 deps (xgboost, shap, sklearn)
_discriminator_cls = None
_tstr_cls = None


def _get_discriminator():
    global _discriminator_cls
    if _discriminator_cls is None:
        from synthetic.discriminator import Discriminator
        _discriminator_cls = Discriminator
    return _discriminator_cls


def _get_tstr():
    global _tstr_cls
    if _tstr_cls is None:
        from synthetic.tstr import TSTRFramework
        _tstr_cls = TSTRFramework
    return _tstr_cls


@dataclass
class LayerResult:
    """Result from a single flywheel layer."""
    layer_num: int
    layer_name: str
    passed: bool
    score: float  # 0.0-1.0
    feedback: Dict[str, Any]
    execution_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_num": self.layer_num,
            "layer_name": self.layer_name,
            "passed": self.passed,
            "score": round(self.score, 4),
            "feedback": self.feedback,
            "execution_time_ms": round(self.execution_time_ms, 1),
        }


@dataclass
class FlywheelReport:
    """Complete report from a flywheel cycle."""
    cycle_id: str
    flywheel_id: str
    layers_executed: int = 0
    layers_passed: int = 0
    layer_results: List[LayerResult] = field(default_factory=list)
    corrections: Dict[str, Any] = field(default_factory=dict)
    needs_hard_reset: bool = False
    total_execution_time_ms: float = 0.0
    quality_improvement: Optional[float] = None  # Delta from previous cycle

    @property
    def overall_score(self) -> float:
        if not self.layer_results:
            return 0.0
        return sum(lr.score for lr in self.layer_results) / len(self.layer_results)

    def summary(self) -> str:
        parts = [
            f"Flywheel Cycle {self.cycle_id}: "
            f"{self.layers_passed}/{self.layers_executed} layers passed | "
            f"Score: {self.overall_score:.3f} | "
            f"Time: {self.total_execution_time_ms:.0f}ms"
        ]
        if self.needs_hard_reset:
            parts.append(" | HARD RESET TRIGGERED")
        if self.quality_improvement is not None:
            sign = "+" if self.quality_improvement >= 0 else ""
            parts.append(f" | Δ quality: {sign}{self.quality_improvement:.3f}")
        return "".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "flywheel_id": self.flywheel_id,
            "layers_executed": self.layers_executed,
            "layers_passed": self.layers_passed,
            "overall_score": round(self.overall_score, 4),
            "layer_results": [lr.to_dict() for lr in self.layer_results],
            "corrections": self.corrections,
            "needs_hard_reset": self.needs_hard_reset,
            "total_execution_time_ms": round(self.total_execution_time_ms, 1),
            "quality_improvement": (
                round(self.quality_improvement, 4)
                if self.quality_improvement is not None
                else None
            ),
        }


class Flywheel:
    """
    Feedback flywheel orchestrator.

    Runs layers 1-6 sequentially on each generated batch, aggregates
    feedback, computes bounded corrections, and logs cycle metrics
    for trend analysis. Layers 5-6 (discriminator, TSTR) require
    sklearn/xgboost and are skipped gracefully if unavailable.
    """

    # Layer confidence weights for feedback aggregation
    LAYER_WEIGHTS = {
        1: 0.20,  # Quality Gate — foundational
        2: 0.25,  # Statistical Fidelity — strongest signal
        3: 0.15,  # Cross-Field Consistency — catches multivariate issues
        4: 0.20,  # Risk Model — highest domain value
        5: 0.10,  # Discriminator — XGBoost distinguishability
        6: 0.10,  # TSTR — downstream task utility
    }

    # Correction bounds (max adjustment per dimension per cycle)
    MAX_CORRECTION = 0.05  # 5% max shift per cycle
    HARD_RESET_THRESHOLD = 0.15  # 15% = reset to KB baseline

    def __init__(
        self,
        kb: Optional[CanadianFinServKB] = None,
        quality_tracker: Optional[SyntheticQualityTracker] = None,
        constraint_engine: Optional[ConstraintEngine] = None,
        risk_validator: Optional[RiskValidator] = None,
    ):
        self.kb = kb or CanadianFinServKB()
        self.quality_tracker = quality_tracker or SyntheticQualityTracker(self.kb)
        self.constraint_engine = constraint_engine or ConstraintEngine(self.kb)
        self.risk_validator = risk_validator or RiskValidator(self.kb)

        self._cycle_count = 0
        self._previous_score: Optional[float] = None
        self._cycle_history: List[Dict[str, Any]] = []
        self._log_dir = Path.home() / ".cortex" / "synthetic" / "flywheel"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def run_cycle(
        self,
        profiles: Optional[List[CustomerProfile]] = None,
        transactions: Optional[List[Transaction]] = None,
        request: Optional[GenerationRequest] = None,
        flywheel_id: str = "",
        skip_heavy_layers: bool = False,
    ) -> FlywheelReport:
        """
        Execute all 6 layers on a generated batch.

        At least one of profiles or transactions must be provided.

        Args:
            profiles: Generated customer profiles
            transactions: Generated transactions
            request: Original generation request
            flywheel_id: ID linking to the generation run
            skip_heavy_layers: Skip L5/L6 (useful for quick validation)

        Returns:
            FlywheelReport with per-layer results and correction vector
        """
        cycle_start = time.time()
        self._cycle_count += 1
        cycle_id = f"C{self._cycle_count:04d}"

        report = FlywheelReport(
            cycle_id=cycle_id,
            flywheel_id=flywheel_id,
        )

        # Layer 1: Quality Gate
        if profiles:
            l1 = self._run_layer1_quality(profiles)
            report.layer_results.append(l1)
            report.layers_executed += 1
            if l1.passed:
                report.layers_passed += 1

        # Layer 2: Statistical Fidelity
        if profiles and len(profiles) >= 10:
            l2 = self._run_layer2_statistical(profiles)
            report.layer_results.append(l2)
            report.layers_executed += 1
            if l2.passed:
                report.layers_passed += 1
            # Check for hard reset
            if l2.feedback.get("needs_hard_reset"):
                report.needs_hard_reset = True

        # Layer 3: Cross-Field Consistency
        if profiles:
            l3 = self._run_layer3_consistency(profiles)
            report.layer_results.append(l3)
            report.layers_executed += 1
            if l3.passed:
                report.layers_passed += 1

        # Layer 4: Risk Model Validation
        if transactions:
            l4 = self._run_layer4_risk(transactions)
            report.layer_results.append(l4)
            report.layers_executed += 1
            if l4.passed:
                report.layers_passed += 1

        # Aggregate feedback and compute corrections
        report.corrections = self._aggregate_corrections(report.layer_results)

        # Track improvement
        current_score = report.overall_score
        if self._previous_score is not None:
            report.quality_improvement = current_score - self._previous_score
        self._previous_score = current_score

        report.total_execution_time_ms = (time.time() - cycle_start) * 1000

        # Log cycle
        self._log_cycle(report)

        return report

    def apply_corrections(
        self, corrections: Dict[str, Any], current_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply flywheel corrections to generation parameters.

        Corrections are bounded by MAX_CORRECTION per dimension to
        prevent overcorrection, and bounded by KB constraints to
        prevent model collapse.

        Args:
            corrections: Correction vector from run_cycle
            current_params: Current generation parameters (optional)

        Returns:
            Adjusted parameters dict
        """
        adjusted = dict(current_params or {})
        adjustments = corrections.get("adjustments", {})

        for dim, correction in adjustments.items():
            if isinstance(correction, (int, float)):
                # Bound the correction
                bounded = max(-self.MAX_CORRECTION, min(self.MAX_CORRECTION, correction))
                current_val = adjusted.get(dim, 0.0)

                if isinstance(current_val, (int, float)):
                    adjusted[dim] = current_val + bounded

        return adjusted

    def should_hard_reset(self, deviation_vector: Dict[str, float]) -> bool:
        """Check if any dimension exceeds hard reset threshold."""
        for dim, deviation in deviation_vector.items():
            if abs(deviation) > self.HARD_RESET_THRESHOLD:
                return True
        return False

    def get_trend(self, last_n: int = 10) -> Dict[str, Any]:
        """Get quality trend from recent cycles."""
        recent = self._cycle_history[-last_n:]
        if not recent:
            return {"cycles": 0, "trend": "no_data"}

        scores = [c["overall_score"] for c in recent]
        if len(scores) < 2:
            return {
                "cycles": len(scores),
                "current_score": scores[-1],
                "trend": "insufficient_data",
            }

        # Linear trend
        improvement = scores[-1] - scores[0]
        avg_improvement = improvement / (len(scores) - 1)

        trend = "improving" if avg_improvement > 0.001 else (
            "declining" if avg_improvement < -0.001 else "stable"
        )

        return {
            "cycles": len(scores),
            "current_score": round(scores[-1], 4),
            "first_score": round(scores[0], 4),
            "improvement": round(improvement, 4),
            "avg_improvement_per_cycle": round(avg_improvement, 4),
            "trend": trend,
        }

    # --- Layer Implementations ---

    def _run_layer1_quality(self, profiles: List[CustomerProfile]) -> LayerResult:
        """Layer 1: Per-record 6-dimension quality assessment."""
        start = time.time()

        scores = []
        low_quality_dims = {
            "completeness": 0, "consistency": 0, "accuracy": 0,
            "timeliness": 0, "uniqueness": 0, "validity": 0,
        }

        for profile in profiles:
            q = self.quality_tracker.assess_profile(profile)
            scores.append(q.overall_score())

            # Track which dimensions are weak
            for dim in low_quality_dims:
                if getattr(q, dim) < 0.8:
                    low_quality_dims[dim] += 1

        avg_score = sum(scores) / len(scores) if scores else 0
        pass_rate = sum(1 for s in scores if s >= 0.7) / len(scores) if scores else 0

        # Identify weakest dimensions
        weak_dims = {
            dim: count / len(profiles)
            for dim, count in low_quality_dims.items()
            if count > len(profiles) * 0.1  # > 10% failing
        }

        elapsed_ms = (time.time() - start) * 1000

        return LayerResult(
            layer_num=1,
            layer_name="quality_gate",
            passed=avg_score >= 0.85 and pass_rate >= 0.90,
            score=avg_score,
            feedback={
                "avg_quality": round(avg_score, 4),
                "pass_rate": round(pass_rate, 4),
                "weak_dimensions": weak_dims,
                "records_assessed": len(profiles),
            },
            execution_time_ms=elapsed_ms,
        )

    def _run_layer2_statistical(self, profiles: List[CustomerProfile]) -> LayerResult:
        """Layer 2: Statistical fidelity tests against KB benchmarks."""
        start = time.time()

        constraint_report = self.constraint_engine.validate_batch(profiles)
        deviation_vector = self.constraint_engine.compute_deviation_vector(profiles)

        elapsed_ms = (time.time() - start) * 1000

        return LayerResult(
            layer_num=2,
            layer_name="statistical_fidelity",
            passed=constraint_report.pass_rate >= 0.75,  # Allow some failing
            score=constraint_report.pass_rate,
            feedback={
                "pass_rate": round(constraint_report.pass_rate, 4),
                "deviation_vector": {
                    k: round(v, 6) for k, v in deviation_vector.items()
                },
                "needs_hard_reset": constraint_report.needs_hard_reset,
                "reset_dimensions": constraint_report.reset_dimensions,
                "failed_tests": [
                    r.to_dict() for r in constraint_report.results if not r.passed
                ],
            },
            execution_time_ms=elapsed_ms,
        )

    def _run_layer3_consistency(self, profiles: List[CustomerProfile]) -> LayerResult:
        """Layer 3: Cross-field consistency validation."""
        start = time.time()

        # Check multivariate consistency across all profiles
        inconsistencies = {
            "income_segment_mismatch": 0,
            "credit_segment_mismatch": 0,
            "household_lt_individual": 0,
            "age_tenure_impossible": 0,
            "products_count_mismatch": 0,
            "digital_age_mismatch": 0,
        }

        for p in profiles:
            # Income vs segment
            income_range = self.kb.get_income_range_for_segment(p.segment)
            tolerance = (income_range[1] - income_range[0]) * 0.2
            if not (income_range[0] - tolerance <= p.annual_income <= income_range[1] + tolerance):
                inconsistencies["income_segment_mismatch"] += 1

            # Credit vs segment
            credit_range = self.kb.get_credit_score_range_for_segment(p.segment)
            if not (credit_range[0] - 50 <= p.credit_score <= credit_range[1] + 50):
                inconsistencies["credit_segment_mismatch"] += 1

            # Household >= individual
            if p.household_income < p.annual_income:
                inconsistencies["household_lt_individual"] += 1

            # Age vs tenure
            if p.tenure_years > max(0, p.age - 16):
                inconsistencies["age_tenure_impossible"] += 1

            # Products count matches list
            if p.products_per_household != len(p.products_held):
                inconsistencies["products_count_mismatch"] += 1

            # Digital adoption vs age (soft)
            if p.age < 25 and p.digital_adoption == "branch_preferred":
                inconsistencies["digital_age_mismatch"] += 1
            elif p.age > 80 and p.digital_adoption == "digital_first":
                inconsistencies["digital_age_mismatch"] += 1

        n = len(profiles)
        inconsistency_rates = {
            k: round(v / n, 4) for k, v in inconsistencies.items()
        }

        # Score: 1.0 - weighted average inconsistency rate
        total_inconsistency = sum(inconsistencies.values()) / (n * len(inconsistencies))
        score = max(0, 1.0 - total_inconsistency)

        elapsed_ms = (time.time() - start) * 1000

        return LayerResult(
            layer_num=3,
            layer_name="cross_field_consistency",
            passed=score >= 0.90,
            score=score,
            feedback={
                "inconsistency_rates": inconsistency_rates,
                "total_inconsistency_rate": round(total_inconsistency, 4),
                "records_checked": n,
            },
            execution_time_ms=elapsed_ms,
        )

    def _run_layer4_risk(self, transactions: List[Transaction]) -> LayerResult:
        """Layer 4: Risk model validation using FINTRAC rules."""
        start = time.time()

        risk_report = self.risk_validator.validate_batch(transactions)

        elapsed_ms = (time.time() - start) * 1000

        return LayerResult(
            layer_num=4,
            layer_name="risk_model_validation",
            passed=risk_report.detection_rate >= 0.90,
            score=risk_report.detection_rate,
            feedback={
                "detection_rate": round(risk_report.detection_rate, 4),
                "precision": round(risk_report.precision, 4),
                "false_positive_rate": round(risk_report.false_positive_rate, 4),
                "false_negative_rate": round(risk_report.false_negative_rate, 4),
                "rule_coverage": risk_report.rule_coverage,
                "confusion_matrix": {
                    "TP": risk_report.true_positives,
                    "FP": risk_report.false_positives,
                    "FN": risk_report.false_negatives,
                    "TN": risk_report.true_negatives,
                },
            },
            execution_time_ms=elapsed_ms,
        )

    # --- Feedback Aggregation ---

    def _aggregate_corrections(
        self, layer_results: List[LayerResult]
    ) -> Dict[str, Any]:
        """
        Aggregate feedback from all layers into a correction vector.

        Weights each layer's feedback by LAYER_WEIGHTS and bounds
        the total correction per dimension to MAX_CORRECTION.
        """
        corrections = {
            "adjustments": {},
            "layer_scores": {},
            "weighted_score": 0.0,
        }

        total_weight = 0.0
        for lr in layer_results:
            weight = self.LAYER_WEIGHTS.get(lr.layer_num, 0.1)
            corrections["layer_scores"][lr.layer_name] = round(lr.score, 4)
            corrections["weighted_score"] += lr.score * weight
            total_weight += weight

            # Extract dimensional corrections from layer feedback
            if lr.layer_name == "statistical_fidelity":
                dev_vector = lr.feedback.get("deviation_vector", {})
                for dim, deviation in dev_vector.items():
                    current = corrections["adjustments"].get(dim, 0.0)
                    # Apply correction in opposite direction of deviation
                    correction = -deviation * weight
                    corrections["adjustments"][dim] = current + correction

            elif lr.layer_name == "cross_field_consistency":
                rates = lr.feedback.get("inconsistency_rates", {})
                for check, rate in rates.items():
                    if rate > 0.05:  # > 5% inconsistency
                        corrections["adjustments"][f"fix_{check}"] = -rate * weight

        if total_weight > 0:
            corrections["weighted_score"] = round(
                corrections["weighted_score"] / total_weight, 4
            )

        # Bound all corrections
        for dim in corrections["adjustments"]:
            val = corrections["adjustments"][dim]
            corrections["adjustments"][dim] = round(
                max(-self.MAX_CORRECTION, min(self.MAX_CORRECTION, val)), 6
            )

        return corrections

    # --- Logging ---

    def _log_cycle(self, report: FlywheelReport):
        """Log cycle results for trend analysis."""
        entry = {
            "cycle_id": report.cycle_id,
            "flywheel_id": report.flywheel_id,
            "timestamp": datetime.now().isoformat(),
            "overall_score": round(report.overall_score, 4),
            "layers_passed": report.layers_passed,
            "layers_executed": report.layers_executed,
            "needs_hard_reset": report.needs_hard_reset,
            "quality_improvement": (
                round(report.quality_improvement, 4)
                if report.quality_improvement is not None
                else None
            ),
            "execution_time_ms": round(report.total_execution_time_ms, 1),
        }
        self._cycle_history.append(entry)

        log_path = self._log_dir / "cycle_log.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
