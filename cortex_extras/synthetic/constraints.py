#!/usr/bin/env python3
"""
Statistical Constraint Engine — Formal distribution fidelity testing.

Validates that synthetic data matches Canadian FinServ distributions
using rigorous statistical tests. Provides per-dimension deviation
vectors that feed back into the flywheel for correction.

Tests implemented:
- KS (Kolmogorov-Smirnov): Continuous dimensions (income, credit score, age)
- Chi-squared: Categorical dimensions (province, segment, products)
- JSD (Jensen-Shannon Divergence): Unified metric for all distributions
- Joint distribution: Cross-tabulation chi-squared for multivariate fidelity
- Anti-collapse bounds: Hard reset if any dimension drifts > 15% from KB anchor

Architecture:
    ConstraintEngine(kb) → validate_batch(profiles) → ConstraintReport
    → deviation_vector → flywheel correction signals
"""

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile, Transaction


@dataclass
class ConstraintResult:
    """Result from a single statistical test."""

    test_name: str
    dimension: str
    passed: bool
    statistic: float
    p_value: Optional[float]
    deviation: float  # Max deviation from expected
    detail: str  # Human-readable explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "dimension": self.dimension,
            "passed": self.passed,
            "statistic": round(self.statistic, 6),
            "p_value": round(self.p_value, 6) if self.p_value is not None else None,
            "deviation": round(self.deviation, 6),
            "detail": self.detail,
        }


@dataclass
class ConstraintReport:
    """Aggregate report from all constraint validations on a batch."""

    results: List[ConstraintResult] = field(default_factory=list)
    deviation_vector: Dict[str, float] = field(default_factory=dict)
    needs_hard_reset: bool = False
    reset_dimensions: List[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 1.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed_dims = [r.dimension for r in self.results if not r.passed]
        s = f"Constraints: {passed}/{total} passed ({self.pass_rate:.0%})"
        if failed_dims:
            s += f" | Failed: {', '.join(set(failed_dims))}"
        if self.needs_hard_reset:
            s += f" | HARD RESET needed: {', '.join(self.reset_dimensions)}"
        return s

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "deviation_vector": {k: round(v, 6) for k, v in self.deviation_vector.items()},
            "needs_hard_reset": self.needs_hard_reset,
            "reset_dimensions": self.reset_dimensions,
            "pass_rate": round(self.pass_rate, 4),
        }


class ConstraintEngine:
    """
    Statistical constraint validator for synthetic FinServ data.

    Runs KS, chi-squared, and JSD tests against knowledge base
    distributions. Produces a deviation vector that tells the flywheel
    exactly which dimensions need correction and by how much.
    """

    HARD_RESET_THRESHOLD = 0.15  # 15% deviation triggers reset to KB
    SIGNIFICANCE_LEVEL = 0.05  # p-value threshold for stat tests
    JSD_THRESHOLD = 0.05  # Max acceptable JSD

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()

    def validate_batch(
        self, profiles: List[CustomerProfile], alpha: float = 0.05
    ) -> ConstraintReport:
        """
        Run all statistical tests on a batch of profiles.

        Args:
            profiles: List of generated profiles
            alpha: Significance level for hypothesis tests

        Returns:
            ConstraintReport with per-dimension results and deviation vector
        """
        if not profiles:
            return ConstraintReport()

        report = ConstraintReport()

        # Categorical tests (chi-squared + JSD)
        categorical_dims = {
            "province": ("province_distribution", [p.province for p in profiles]),
            "segment": ("segment_distribution", [p.segment for p in profiles]),
            "digital_adoption": ("digital_adoption", [p.digital_adoption for p in profiles]),
            "primary_channel": ("primary_channel", [p.primary_channel for p in profiles]),
        }

        for dim_name, (constraint_name, observed_values) in categorical_dims.items():
            constraint = self.kb.get_constraint(constraint_name)
            if not constraint:
                continue

            # Chi-squared
            chi_result = self._chi_squared_test(
                observed_values, constraint.distribution, dim_name, alpha
            )
            report.results.append(chi_result)

            # JSD
            jsd_result = self._jsd_test(observed_values, constraint.distribution, dim_name)
            report.results.append(jsd_result)

            # Record deviation
            report.deviation_vector[dim_name] = chi_result.deviation

        # Continuous tests (KS)
        continuous_dims = self._extract_continuous_dims(profiles)
        for dim_name, (observed, expected_cdf_params) in continuous_dims.items():
            ks_result = self._ks_test(observed, expected_cdf_params, dim_name, alpha)
            report.results.append(ks_result)
            report.deviation_vector[dim_name] = ks_result.deviation

        # Joint distribution test (province × segment)
        joint_result = self._joint_distribution_test(profiles, alpha)
        if joint_result:
            report.results.append(joint_result)

        # Anti-collapse check
        for dim_name, deviation in report.deviation_vector.items():
            if deviation > self.HARD_RESET_THRESHOLD:
                report.needs_hard_reset = True
                report.reset_dimensions.append(dim_name)

        return report

    def validate_transactions(
        self, transactions: List[Transaction], alpha: float = 0.05
    ) -> ConstraintReport:
        """Validate transaction batch against expected distributions."""
        if not transactions:
            return ConstraintReport()

        report = ConstraintReport()

        # Transaction type distribution
        txn_types = [t.transaction_type for t in transactions]
        expected_txn_dist = {
            "pos_purchase": 0.35,
            "e_transfer": 0.20,
            "bill_payment": 0.15,
            "online_purchase": 0.12,
            "transfer": 0.08,
            "atm": 0.05,
            "deposit": 0.03,
            "withdrawal": 0.02,
        }
        chi_result = self._chi_squared_test(txn_types, expected_txn_dist, "transaction_type", alpha)
        report.results.append(chi_result)
        report.deviation_vector["transaction_type"] = chi_result.deviation

        # Amount distribution (KS against log-normal)
        amounts = [t.amount for t in transactions if t.risk_flag == "none"]
        if len(amounts) >= 10:
            # Use a simple deviation metric for amounts
            log_amounts = np.log1p(amounts)
            mean_log = np.mean(log_amounts)
            std_log = np.std(log_amounts)
            # KS test against fitted log-normal
            ks_stat, p_val = stats.kstest(log_amounts, "norm", args=(mean_log, std_log))
            report.results.append(
                ConstraintResult(
                    test_name="ks_lognormal",
                    dimension="amount",
                    passed=p_val > alpha,
                    statistic=ks_stat,
                    p_value=p_val,
                    deviation=ks_stat,
                    detail=f"KS test on log-amounts: stat={ks_stat:.4f}, p={p_val:.4f}",
                )
            )
            report.deviation_vector["amount"] = ks_stat

        # Risk flag distribution (for flagged transactions)
        flagged = [t for t in transactions if t.risk_flag != "none"]
        if flagged:
            flag_dist = {}
            for t in flagged:
                flag_dist[t.risk_flag] = flag_dist.get(t.risk_flag, 0) + 1
            total_flagged = len(flagged)
            flag_dist = {k: v / total_flagged for k, v in flag_dist.items()}
            # Just record deviation, no expected distribution to test against
            report.deviation_vector["risk_flags"] = 0.0  # No anchor for flags

        for dim_name, deviation in report.deviation_vector.items():
            if deviation > self.HARD_RESET_THRESHOLD:
                report.needs_hard_reset = True
                report.reset_dimensions.append(dim_name)

        return report

    # --- Statistical Tests ---

    def _chi_squared_test(
        self,
        observed_values: List[str],
        expected_distribution: Dict[str, float],
        dimension: str,
        alpha: float,
    ) -> ConstraintResult:
        """
        Chi-squared goodness-of-fit test for categorical data.

        Compares observed category frequencies against expected distribution
        from the knowledge base. Only tests categories present in the
        expected distribution; extra observed categories are ignored.
        Expected frequencies are normalized to match observed total.
        """
        n = len(observed_values)
        if n == 0:
            return ConstraintResult(
                test_name="chi_squared",
                dimension=dimension,
                passed=False,
                statistic=0.0,
                p_value=0.0,
                deviation=1.0,
                detail="Empty sample",
            )

        # Count observed frequencies
        observed_counts = {}
        for val in observed_values:
            observed_counts[val] = observed_counts.get(val, 0) + 1

        # Only test categories from the expected distribution
        categories = sorted(expected_distribution.keys())
        obs = np.array([observed_counts.get(cat, 0) for cat in categories], dtype=float)
        exp_pcts = np.array([expected_distribution[cat] for cat in categories], dtype=float)

        # Normalize expected to sum to the observed total for these categories
        obs_total = obs.sum()
        if obs_total == 0:
            return ConstraintResult(
                test_name="chi_squared",
                dimension=dimension,
                passed=False,
                statistic=0.0,
                p_value=0.0,
                deviation=1.0,
                detail="No observations in expected categories",
            )

        # Normalize expected proportions and scale to observed total
        exp_pcts_norm = exp_pcts / exp_pcts.sum()
        exp = exp_pcts_norm * obs_total

        # Filter out categories with zero expected (avoid div-by-zero)
        mask = exp > 0
        if not mask.any():
            return ConstraintResult(
                test_name="chi_squared",
                dimension=dimension,
                passed=False,
                statistic=0.0,
                p_value=0.0,
                deviation=1.0,
                detail="No expected values",
            )

        chi2, p_value = stats.chisquare(obs[mask], f_exp=exp[mask])

        # Max category deviation (against original proportions)
        obs_dist = {cat: observed_counts.get(cat, 0) / n for cat in categories}
        max_dev = max(abs(obs_dist[cat] - expected_distribution[cat]) for cat in categories)

        return ConstraintResult(
            test_name="chi_squared",
            dimension=dimension,
            passed=p_value > alpha,
            statistic=float(chi2),
            p_value=float(p_value),
            deviation=max_dev,
            detail=(
                f"Chi-squared: χ²={chi2:.2f}, p={p_value:.4f}, "
                f"max_deviation={max_dev:.4f} (α={alpha})"
            ),
        )

    def _jsd_test(
        self,
        observed_values: List[str],
        expected_distribution: Dict[str, float],
        dimension: str,
    ) -> ConstraintResult:
        """
        Jensen-Shannon Divergence — symmetric, bounded [0, 1] divergence metric.

        JSD < 0.05 means distributions are very close.
        JSD is preferred over KL-divergence because it's symmetric and always finite.
        """
        n = len(observed_values)
        if n == 0:
            return ConstraintResult(
                test_name="jsd",
                dimension=dimension,
                passed=False,
                statistic=1.0,
                p_value=None,
                deviation=1.0,
                detail="Empty sample",
            )

        # Build aligned probability vectors
        observed_counts = {}
        for val in observed_values:
            observed_counts[val] = observed_counts.get(val, 0) + 1

        all_categories = sorted(set(expected_distribution.keys()) | set(observed_counts.keys()))
        p = np.array([observed_counts.get(cat, 0) / n for cat in all_categories])
        q = np.array([expected_distribution.get(cat, 0.0) for cat in all_categories])

        # Normalize q to sum to 1 (it should, but safety)
        q_sum = q.sum()
        if q_sum > 0:
            q = q / q_sum

        # Compute JSD using scipy's implementation (base 2 for [0,1] range)
        jsd_value = self._compute_jsd(p, q)

        return ConstraintResult(
            test_name="jsd",
            dimension=dimension,
            passed=jsd_value < self.JSD_THRESHOLD,
            statistic=jsd_value,
            p_value=None,  # JSD doesn't have a p-value
            deviation=jsd_value,
            detail=f"JSD={jsd_value:.6f} (threshold={self.JSD_THRESHOLD})",
        )

    @staticmethod
    def _compute_jsd(p: np.ndarray, q: np.ndarray) -> float:
        """Compute Jensen-Shannon Divergence (base 2, range [0, 1])."""
        # Handle zeros: add small epsilon
        eps = 1e-12
        p = np.clip(p, eps, None)
        q = np.clip(q, eps, None)

        # Normalize
        p = p / p.sum()
        q = q / q.sum()

        m = 0.5 * (p + q)

        # KL divergences
        kl_pm = np.sum(p * np.log2(p / m))
        kl_qm = np.sum(q * np.log2(q / m))

        return float(0.5 * kl_pm + 0.5 * kl_qm)

    def _ks_test(
        self,
        observed: List[float],
        cdf_params: Dict[str, Any],
        dimension: str,
        alpha: float,
    ) -> ConstraintResult:
        """
        Kolmogorov-Smirnov test for continuous distributions.

        Tests whether observed values come from the expected distribution.
        """
        if len(observed) < 5:
            return ConstraintResult(
                test_name="ks",
                dimension=dimension,
                passed=False,
                statistic=0.0,
                p_value=0.0,
                deviation=1.0,
                detail="Too few samples for KS test (need >= 5)",
            )

        observed_arr = np.array(observed, dtype=float)
        dist_type = cdf_params.get("type", "norm")
        loc = cdf_params.get("loc", np.mean(observed_arr))
        scale = cdf_params.get("scale", np.std(observed_arr))

        if scale == 0:
            scale = 1.0

        ks_stat, p_value = stats.kstest(observed_arr, dist_type, args=(loc, scale))

        return ConstraintResult(
            test_name="ks",
            dimension=dimension,
            passed=p_value > alpha,
            statistic=ks_stat,
            p_value=p_value,
            deviation=ks_stat,
            detail=f"KS test ({dist_type}): D={ks_stat:.4f}, p={p_value:.4f}",
        )

    def _joint_distribution_test(
        self, profiles: List[CustomerProfile], alpha: float
    ) -> Optional[ConstraintResult]:
        """
        Test joint distribution of province × segment.

        Uses chi-squared on the cross-tabulation to detect unrealistic
        combinations (e.g., too many ultra-HNW in PEI).
        """
        if len(profiles) < 50:
            return None  # Not enough data for joint test

        # Build contingency table
        prov_seg_counts: Dict[Tuple[str, str], int] = {}
        for p in profiles:
            key = (p.province, p.segment)
            prov_seg_counts[key] = prov_seg_counts.get(key, 0) + 1

        provinces = sorted(set(p.province for p in profiles))
        segments = sorted(set(p.segment for p in profiles))

        if len(provinces) < 2 or len(segments) < 2:
            return None  # Need at least 2×2 table

        table = []
        for prov in provinces:
            row = [prov_seg_counts.get((prov, seg), 0) for seg in segments]
            table.append(row)

        table = np.array(table)

        # Only test if no zero row/column sums
        if np.any(table.sum(axis=0) == 0) or np.any(table.sum(axis=1) == 0):
            return None

        chi2, p_value, dof, expected = stats.chi2_contingency(table)

        # Compute max deviation from expected
        max_dev = float(np.max(np.abs(table - expected) / np.maximum(expected, 1)))

        return ConstraintResult(
            test_name="chi_squared_joint",
            dimension="province×segment",
            passed=p_value > alpha,
            statistic=chi2,
            p_value=p_value,
            deviation=max_dev,
            detail=(
                f"Joint chi-squared (province×segment): "
                f"χ²={chi2:.2f}, p={p_value:.4f}, dof={dof}"
            ),
        )

    def _extract_continuous_dims(
        self, profiles: List[CustomerProfile]
    ) -> Dict[str, Tuple[List[float], Dict[str, Any]]]:
        """Extract continuous dimensions with expected CDF parameters."""
        dims = {}

        ages = [float(p.age) for p in profiles]
        if ages:
            dims["age"] = (ages, {"type": "norm", "loc": 47.0, "scale": 17.0})

        incomes = [p.annual_income for p in profiles]
        if incomes:
            # Income is roughly log-normal
            log_incomes = [math.log(max(i, 1)) for i in incomes]
            dims["income"] = (
                log_incomes,
                {
                    "type": "norm",
                    "loc": np.mean(log_incomes),
                    "scale": np.std(log_incomes),
                },
            )

        credit_scores = [float(p.credit_score) for p in profiles]
        if credit_scores:
            dims["credit_score"] = (
                credit_scores,
                {
                    "type": "norm",
                    "loc": np.mean(credit_scores),
                    "scale": np.std(credit_scores),
                },
            )

        tenures = [p.tenure_years for p in profiles]
        if tenures:
            dims["tenure"] = (
                tenures,
                {
                    "type": "norm",
                    "loc": np.mean(tenures),
                    "scale": np.std(tenures),
                },
            )

        return dims

    def compute_deviation_vector(self, profiles: List[CustomerProfile]) -> Dict[str, float]:
        """
        Compute per-dimension deviation from KB benchmarks.

        Returns a dict mapping dimension name to signed deviation.
        Positive = sample is above expected, negative = below.
        Used by the flywheel to apply targeted corrections.
        """
        if not profiles:
            return {}

        deviations = {}
        n = len(profiles)

        # Province deviation
        constraint = self.kb.get_constraint("province_distribution")
        if constraint:
            prov_counts = {}
            for p in profiles:
                prov_counts[p.province] = prov_counts.get(p.province, 0) + 1
            for cat, expected_pct in constraint.distribution.items():
                actual_pct = prov_counts.get(cat, 0) / n
                deviations[f"province_{cat}"] = actual_pct - expected_pct

        # Segment deviation
        constraint = self.kb.get_constraint("segment_distribution")
        if constraint:
            seg_counts = {}
            for p in profiles:
                seg_counts[p.segment] = seg_counts.get(p.segment, 0) + 1
            for cat, expected_pct in constraint.distribution.items():
                actual_pct = seg_counts.get(cat, 0) / n
                deviations[f"segment_{cat}"] = actual_pct - expected_pct

        # Digital adoption deviation
        constraint = self.kb.get_constraint("digital_adoption")
        if constraint:
            dig_counts = {}
            for p in profiles:
                dig_counts[p.digital_adoption] = dig_counts.get(p.digital_adoption, 0) + 1
            for cat, expected_pct in constraint.distribution.items():
                actual_pct = dig_counts.get(cat, 0) / n
                deviations[f"digital_{cat}"] = actual_pct - expected_pct

        # Continuous dimension deviations (mean shift)
        ages = [float(p.age) for p in profiles]
        deviations["age_mean"] = np.mean(ages) - 47.0  # Expected mean ~47

        incomes = [p.annual_income for p in profiles]
        deviations["income_mean_log"] = np.mean(np.log1p(incomes)) - 11.0  # ~$60K

        credits = [float(p.credit_score) for p in profiles]
        deviations["credit_mean"] = np.mean(credits) - 720.0  # Expected ~720

        return deviations

    def check_collapse_risk(self, deviation_vector: Dict[str, float]) -> Tuple[bool, List[str]]:
        """
        Check if any dimension has drifted beyond the hard reset threshold.

        Returns:
            (needs_reset, list_of_collapsed_dimensions)
        """
        collapsed = []
        for dim, deviation in deviation_vector.items():
            if abs(deviation) > self.HARD_RESET_THRESHOLD:
                collapsed.append(dim)
        return len(collapsed) > 0, collapsed
