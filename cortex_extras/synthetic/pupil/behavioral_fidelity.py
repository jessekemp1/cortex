#!/usr/bin/env python3
"""
Layer 8: Behavioral Fidelity Validator — Validates simulated agent behavior
against CBA-calibrated segment benchmarks.

Checks that Pupil simulation outputs produce behaviorally plausible results:
- Per-segment churn rates within tolerance of CBA calibration
- Product adoption rates proportional to segment propensity
- Deposit sensitivity direction correct (rates up -> deposits up)
- Credit score distributions stay within valid ranges (300-900)
- Lifecycle state transitions are valid (no impossible churned->active)

Architecture:
    SimulationResult -> BehavioralFidelityValidator.validate() -> FidelityReport
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .segment_models import SEGMENT_MODELS, get_behavior
from .simulation import SimulationResult

# ============================================================================
# Report Dataclasses
# ============================================================================


@dataclass
class FidelityCheck:
    """Result of a single behavioral fidelity check."""

    check_name: str
    passed: bool
    score: float  # 0.0-1.0
    detail: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "score": round(self.score, 4),
            "detail": self.detail,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class FidelityReport:
    """Complete behavioral fidelity validation report."""

    overall_score: float
    passed: bool
    checks: List[FidelityCheck] = field(default_factory=list)
    segment_scores: Dict[str, float] = field(default_factory=dict)
    n_agents: int = 0
    n_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 4),
            "passed": self.passed,
            "n_agents": self.n_agents,
            "n_steps": self.n_steps,
            "checks": [c.to_dict() for c in self.checks],
            "segment_scores": {k: round(v, 4) for k, v in self.segment_scores.items()},
        }


# ============================================================================
# Check Weights
# ============================================================================

CHECK_WEIGHTS = {
    "churn_rate_fidelity": 0.30,
    "product_adoption_fidelity": 0.20,
    "deposit_sensitivity": 0.15,
    "credit_score_range": 0.15,
    "lifecycle_transitions": 0.20,
}


# ============================================================================
# Validator
# ============================================================================


class BehavioralFidelityValidator:
    """
    Validates that simulation outputs match CBA-calibrated behavioral
    benchmarks within acceptable tolerances.

    Runs 5 checks weighted by importance. Produces a 0.0-1.0 composite
    score where >= 0.6 is considered passing.
    """

    PASS_THRESHOLD = 0.6

    # Churn tolerance: +/- 50% of calibrated annual rate (converted to
    # simulation-period rate). E.g., mass_market 18% annual -> 9-27%.
    CHURN_TOLERANCE_FACTOR = 0.50

    # Valid lifecycle transitions — only these (from, to) pairs are allowed
    VALID_TRANSITIONS = {
        ("onboarding", "active"),
        ("onboarding", "at_risk"),
        ("onboarding", "churned"),
        ("active", "at_risk"),
        ("active", "churned"),
        ("at_risk", "active"),
        ("at_risk", "churned"),
        ("at_risk", "dormant"),
        ("dormant", "active"),
        ("dormant", "churned"),
    }

    def validate(self, result: SimulationResult) -> FidelityReport:
        """
        Validate simulation result against behavioral benchmarks.

        Args:
            result: SimulationResult from SimulationEngine.run()

        Returns:
            FidelityReport with per-check scores and overall assessment
        """
        if not result.steps or not result.final_snapshots:
            return FidelityReport(
                overall_score=0.0,
                passed=False,
                n_agents=result.n_agents,
                n_steps=result.n_steps,
                checks=[
                    FidelityCheck(
                        check_name="empty_result",
                        passed=False,
                        score=0.0,
                        detail="Simulation result is empty (no steps or snapshots)",
                    )
                ],
            )

        checks = []

        # Check 1: Per-segment churn rate fidelity
        checks.append(self._check_churn_rate_fidelity(result))

        # Check 2: Product adoption proportional to segment propensity
        checks.append(self._check_product_adoption_fidelity(result))

        # Check 3: Deposit sensitivity direction
        checks.append(self._check_deposit_sensitivity(result))

        # Check 4: Credit score range validity
        checks.append(self._check_credit_score_range(result))

        # Check 5: Lifecycle state transitions validity
        checks.append(self._check_lifecycle_transitions(result))

        # Compute weighted overall score
        weighted_sum = 0.0
        total_weight = 0.0
        segment_scores: Dict[str, float] = {}

        for check in checks:
            weight = CHECK_WEIGHTS.get(check.check_name, 0.1)
            weighted_sum += check.score * weight
            total_weight += weight

        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Per-segment scoring (from churn check)
        segment_scores = self._compute_segment_scores(result)

        return FidelityReport(
            overall_score=overall_score,
            passed=overall_score >= self.PASS_THRESHOLD,
            checks=checks,
            segment_scores=segment_scores,
            n_agents=result.n_agents,
            n_steps=result.n_steps,
        )

    # ------------------------------------------------------------------
    # Individual Checks
    # ------------------------------------------------------------------

    def _check_churn_rate_fidelity(self, result: SimulationResult) -> FidelityCheck:
        """
        Check 1: Per-segment churn rates within +/- 50% of CBA calibration.

        Converts annual calibrated rate to the simulation period rate,
        then checks if observed churn falls within tolerance.
        """
        by_segment = self._group_by_segment(result)
        n_months = result.n_steps

        segment_results = {}
        passes = 0
        total = 0

        for segment, snapshots in by_segment.items():
            behavior = get_behavior(segment)
            n = len(snapshots)
            if n == 0:
                continue

            # Convert annual rate to simulation-period rate
            # P(churn in n months) = 1 - (1 - annual_rate)^(n/12)
            expected_rate = 1.0 - (1.0 - behavior.base_annual_churn_rate) ** (n_months / 12.0)
            tolerance = expected_rate * self.CHURN_TOLERANCE_FACTOR

            # Observed churn rate for this segment
            churned = sum(1 for s in snapshots if s["state"] == "churned")
            observed_rate = churned / n

            lower = max(0.0, expected_rate - tolerance)
            upper = min(1.0, expected_rate + tolerance)
            in_range = lower <= observed_rate <= upper

            segment_results[segment] = {
                "expected": round(expected_rate, 4),
                "observed": round(observed_rate, 4),
                "tolerance": round(tolerance, 4),
                "in_range": in_range,
                "n_agents": n,
            }

            if in_range:
                passes += 1
            total += 1

        score = passes / total if total > 0 else 0.0

        return FidelityCheck(
            check_name="churn_rate_fidelity",
            passed=score >= 0.5,
            score=score,
            detail=f"{passes}/{total} segments have churn within CBA tolerance",
            expected="Per-segment churn within +/-50% of calibration",
            actual=segment_results,
        )

    def _check_product_adoption_fidelity(self, result: SimulationResult) -> FidelityCheck:
        """
        Check 2: Product adoption rates proportional to segment propensity.

        Segments with higher product_adoption_propensity should have more
        adoption actions per agent.
        """
        by_segment = self._group_by_segment(result)

        # Count adoption actions per segment
        agent_segments: Dict[str, str] = {}
        for snap in result.final_snapshots:
            agent_segments[snap["agent_id"]] = snap["segment"]

        segment_adoptions: Dict[str, int] = defaultdict(int)
        for action in result.all_actions:
            if action.action_type.value == "adopt_product":
                seg = agent_segments.get(action.agent_id, "unknown")
                segment_adoptions[seg] += 1

        # Compute per-agent adoption rate
        segment_adoption_rates: Dict[str, float] = {}
        for segment, snapshots in by_segment.items():
            n = len(snapshots)
            if n == 0:
                continue
            segment_adoption_rates[segment] = segment_adoptions.get(segment, 0) / n

        # Check rank ordering: higher propensity segments should have higher
        # adoption rates. We check pairwise consistency.
        segments_with_data = [
            (seg, segment_adoption_rates[seg])
            for seg in segment_adoption_rates
            if seg in SEGMENT_MODELS and len(by_segment.get(seg, [])) >= 5
        ]

        if len(segments_with_data) < 2:
            return FidelityCheck(
                check_name="product_adoption_fidelity",
                passed=True,
                score=1.0,
                detail="Insufficient segment diversity for adoption comparison",
                expected="Higher-propensity segments adopt more",
                actual=segment_adoption_rates,
            )

        # Sort by propensity
        segments_with_data.sort(
            key=lambda x: get_behavior(x[0]).product_adoption_propensity,
            reverse=True,
        )

        # Count how many high-propensity segments have >= adoption rate
        # compared to low-propensity segments
        consistent_pairs = 0
        total_pairs = 0
        for i in range(len(segments_with_data)):
            for j in range(i + 1, len(segments_with_data)):
                higher_propensity_seg = segments_with_data[i]
                lower_propensity_seg = segments_with_data[j]
                # Higher propensity should have >= adoption rate
                if higher_propensity_seg[1] >= lower_propensity_seg[1]:
                    consistent_pairs += 1
                total_pairs += 1

        score = consistent_pairs / total_pairs if total_pairs > 0 else 1.0

        return FidelityCheck(
            check_name="product_adoption_fidelity",
            passed=score >= 0.4,
            score=score,
            detail=(
                f"{consistent_pairs}/{total_pairs} segment pairs have "
                f"adoption consistent with propensity"
            ),
            expected="Higher-propensity segments adopt more products",
            actual={seg: round(rate, 4) for seg, rate in segment_adoption_rates.items()},
        )

    def _check_deposit_sensitivity(self, result: SimulationResult) -> FidelityCheck:
        """
        Check 3: Deposit sensitivity direction — rates up should lead to
        deposits up (or stable), not a dramatic drop.

        Compares first-half average deposits to second-half.
        """
        if len(result.steps) < 4:
            return FidelityCheck(
                check_name="deposit_sensitivity",
                passed=True,
                score=1.0,
                detail="Too few steps for deposit sensitivity analysis",
            )

        # Get average deposits per active agent in first and second halves
        mid = len(result.steps) // 2
        first_half_deposits = []
        second_half_deposits = []

        for step in result.steps[:mid]:
            active_deps = [s["deposits"] for s in step.snapshots if s["state"] != "churned"]
            if active_deps:
                first_half_deposits.append(sum(active_deps) / len(active_deps))

        for step in result.steps[mid:]:
            active_deps = [s["deposits"] for s in step.snapshots if s["state"] != "churned"]
            if active_deps:
                second_half_deposits.append(sum(active_deps) / len(active_deps))

        if not first_half_deposits or not second_half_deposits:
            return FidelityCheck(
                check_name="deposit_sensitivity",
                passed=True,
                score=1.0,
                detail="No active agents in one half — cannot assess deposits",
            )

        avg_first = sum(first_half_deposits) / len(first_half_deposits)
        avg_second = sum(second_half_deposits) / len(second_half_deposits)

        # In a baseline scenario (stable rates), deposits should not crash.
        # Allow up to 30% decline (stress scenarios may cause more).
        if avg_first > 0:
            change_pct = (avg_second - avg_first) / avg_first
        else:
            change_pct = 0.0

        # Score: 1.0 if deposits grew, scaling down to 0.0 if >30% decline
        if change_pct >= 0:
            score = 1.0
        elif change_pct >= -0.30:
            score = 1.0 + (change_pct / 0.30)  # Linear from 1.0 to 0.0
        else:
            score = 0.0

        return FidelityCheck(
            check_name="deposit_sensitivity",
            passed=score >= 0.5,
            score=score,
            detail=(
                f"Deposit change first-to-second half: {change_pct:+.1%} "
                f"(avg {avg_first:.0f} -> {avg_second:.0f})"
            ),
            expected="Deposits should not crash (>-30% decline)",
            actual={"first_half_avg": round(avg_first, 2), "second_half_avg": round(avg_second, 2)},
        )

    def _check_credit_score_range(self, result: SimulationResult) -> FidelityCheck:
        """
        Check 4: Credit scores stay within valid 300-900 range at all steps.
        """
        violations = 0
        total_observations = 0

        for step in result.steps:
            for snap in step.snapshots:
                if snap["state"] == "churned":
                    continue
                total_observations += 1
                if snap["credit_score"] < 300 or snap["credit_score"] > 900:
                    violations += 1

        if total_observations == 0:
            return FidelityCheck(
                check_name="credit_score_range",
                passed=True,
                score=1.0,
                detail="No active observations to check",
            )

        violation_rate = violations / total_observations
        score = max(0.0, 1.0 - violation_rate * 10)  # Each 10% violations = -1.0

        return FidelityCheck(
            check_name="credit_score_range",
            passed=violations == 0,
            score=score,
            detail=(f"{violations}/{total_observations} observations outside 300-900 range"),
            expected="All credit scores within 300-900",
            actual={"violations": violations, "total_observations": total_observations},
        )

    def _check_lifecycle_transitions(self, result: SimulationResult) -> FidelityCheck:
        """
        Check 5: Lifecycle state transitions are valid.

        Specifically forbids impossible transitions like churned->active.
        """
        if len(result.steps) < 2:
            return FidelityCheck(
                check_name="lifecycle_transitions",
                passed=True,
                score=1.0,
                detail="Only 1 step — no transitions to validate",
            )

        invalid_transitions = []
        total_transitions = 0

        for i in range(1, len(result.steps)):
            prev_states = {s["agent_id"]: s["state"] for s in result.steps[i - 1].snapshots}
            curr_states = {s["agent_id"]: s["state"] for s in result.steps[i].snapshots}

            for agent_id, curr_state in curr_states.items():
                prev_state = prev_states.get(agent_id)
                if prev_state is None:
                    continue
                if prev_state == curr_state:
                    continue

                total_transitions += 1
                transition = (prev_state, curr_state)

                if transition not in self.VALID_TRANSITIONS:
                    invalid_transitions.append(
                        {
                            "agent_id": agent_id,
                            "step": i,
                            "from": prev_state,
                            "to": curr_state,
                        }
                    )

        if total_transitions == 0:
            return FidelityCheck(
                check_name="lifecycle_transitions",
                passed=True,
                score=1.0,
                detail="No state transitions observed",
            )

        invalid_rate = len(invalid_transitions) / total_transitions
        score = max(0.0, 1.0 - invalid_rate * 5)  # Harsh penalty for invalid

        return FidelityCheck(
            check_name="lifecycle_transitions",
            passed=len(invalid_transitions) == 0,
            score=score,
            detail=(
                f"{len(invalid_transitions)}/{total_transitions} " f"invalid transitions detected"
            ),
            expected="Only valid lifecycle transitions",
            actual=(invalid_transitions[:10] if invalid_transitions else "All transitions valid"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _group_by_segment(self, result: SimulationResult) -> Dict[str, List[Dict]]:
        """Group final snapshots by segment."""
        by_segment: Dict[str, List[Dict]] = defaultdict(list)
        for snap in result.final_snapshots:
            by_segment[snap["segment"]].append(snap)
        return dict(by_segment)

    def _compute_segment_scores(self, result: SimulationResult) -> Dict[str, float]:
        """Compute a fidelity score per segment based on churn accuracy."""
        by_segment = self._group_by_segment(result)
        n_months = result.n_steps
        scores: Dict[str, float] = {}

        for segment, snapshots in by_segment.items():
            behavior = get_behavior(segment)
            n = len(snapshots)
            if n == 0:
                continue

            expected_rate = 1.0 - (1.0 - behavior.base_annual_churn_rate) ** (n_months / 12.0)
            churned = sum(1 for s in snapshots if s["state"] == "churned")
            observed_rate = churned / n

            # Score based on distance from expected (normalized by expected)
            if expected_rate > 0:
                error = abs(observed_rate - expected_rate) / expected_rate
                scores[segment] = max(0.0, 1.0 - error)
            else:
                scores[segment] = 1.0 if churned == 0 else 0.0

        return scores
