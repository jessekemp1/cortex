#!/usr/bin/env python3
"""
Synthetic Data Generator — Core engine for generating Canadian FinServ data.

Uses LLM-based generation with statistical constraints from the knowledge base.
Integrates with Cortex's quality framework for validation and the outcome
flywheel for continuous improvement.

Architecture:
    GenerationRequest → KnowledgeBase constraints → LLM generation
    → Quality validation → Filter low-quality → GenerationResult
    → Outcome flywheel (learn from usage)
"""

import json
import random
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import (
    CustomerProfile,
    GenerationRequest,
    GenerationResult,
    Transaction,
)


class SyntheticGenerator:
    """
    Core synthetic data generation engine.

    Generates Canadian FinServ data using a hybrid approach:
    1. Statistical sampling from knowledge base distributions
    2. LLM-based enrichment for realistic detail (optional, for complex fields)
    3. Quality validation using Cortex's 6-dimension framework
    4. Outcome tracking for flywheel improvement

    The statistical approach is primary — LLM is used for coherence and
    enrichment, not raw generation. This keeps costs low and quality high.
    """

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()
        self._quality_tracker = None
        self._output_dir = Path.home() / ".cortex" / "synthetic"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def quality_tracker(self):
        """Lazy-load quality tracker to avoid circular imports."""
        if self._quality_tracker is None:
            try:
                from synthetic.quality import SyntheticQualityTracker
                self._quality_tracker = SyntheticQualityTracker(self.kb)
            except ImportError:
                self._quality_tracker = None
        return self._quality_tracker

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate synthetic data based on request parameters.

        Args:
            request: GenerationRequest with type, count, constraints

        Returns:
            GenerationResult with generated records and quality metadata
        """
        start_time = time.time()

        if request.data_type == "profiles":
            records, quality_scores = self._generate_profiles(request)
        elif request.data_type == "transactions":
            records, quality_scores = self._generate_transactions(request)
        else:
            raise ValueError(f"Unsupported data_type: {request.data_type}")

        # Filter by quality threshold
        passed = []
        rejected = 0
        for record, score in zip(records, quality_scores):
            if score >= request.min_quality_score:
                record.quality_score = score
                passed.append(record)
            else:
                rejected += 1

        # Calculate quality distribution
        quality_dist = {"excellent_0.9+": 0, "good_0.8-0.9": 0, "fair_0.7-0.8": 0, "low_<0.7": 0}
        for score in quality_scores:
            if score >= 0.9:
                quality_dist["excellent_0.9+"] += 1
            elif score >= 0.8:
                quality_dist["good_0.8-0.9"] += 1
            elif score >= 0.7:
                quality_dist["fair_0.7-0.8"] += 1
            else:
                quality_dist["low_<0.7"] += 1

        # Write output
        output_path = self._write_output(passed, request)

        elapsed = time.time() - start_time

        result = GenerationResult(
            request=request,
            records_generated=len(records),
            records_passed_quality=len(passed),
            records_rejected=rejected,
            average_quality_score=(
                sum(quality_scores) / len(quality_scores)
                if quality_scores
                else 0.0
            ),
            quality_distribution=quality_dist,
            generation_time_seconds=elapsed,
            output_path=str(output_path) if output_path else None,
            flywheel_id=str(uuid.uuid4()),
        )

        # Log for outcome flywheel
        self._log_generation_outcome(result)

        return result

    def _generate_profiles(
        self, request: GenerationRequest
    ) -> Tuple[List[CustomerProfile], List[float]]:
        """Generate customer profiles using statistical sampling + constraints."""
        profiles = []
        quality_scores = []

        # Get distributions from knowledge base
        province_dist = self.kb.get_constraint("province_distribution")
        age_dist = self.kb.get_constraint("age_distribution")
        segment_dist = self.kb.get_constraint("segment_distribution")
        digital_dist = self.kb.get_constraint("digital_adoption")
        channel_dist = self.kb.get_constraint("primary_channel")

        for i in range(request.count):
            # Determine segment
            if request.segment:
                segment = request.segment
            else:
                segment = self._weighted_choice(segment_dist.distribution)

            # Determine province
            if request.province:
                province = request.province
            else:
                province = self._weighted_choice(province_dist.distribution)

            # Get segment-specific ranges
            income_range = request.income_range or self.kb.get_income_range_for_segment(segment)
            credit_range = self.kb.get_credit_score_range_for_segment(segment)
            age_range = request.age_range or self._age_range_from_distribution(age_dist)

            # Generate correlated fields
            age = random.randint(age_range[0], age_range[1])
            annual_income = self._generate_income(income_range, age)
            household_income = annual_income * random.uniform(1.0, 1.8)
            credit_score = self._generate_credit_score(credit_range, age, annual_income)

            # Generate products (correlated with segment)
            product_likelihoods = self.kb.get_product_likelihood(segment)
            products = self._sample_products(product_likelihoods)

            # FSA
            fsas = self.kb.get_fsa_for_province(province)
            fsa = random.choice(fsas) if fsas else "M5V"

            # Digital adoption (correlated with age)
            digital = self._digital_adoption_for_age(age, digital_dist)
            channel = self._channel_for_digital(digital, channel_dist)

            # Tenure (correlated with age)
            max_tenure = max(1, age - 18)
            tenure = round(random.uniform(0.5, min(max_tenure, 30)), 1)

            profile = CustomerProfile(
                profile_id=f"SYN-{uuid.uuid4().hex[:12].upper()}",
                age=age,
                province=province,
                fsa=fsa,
                segment=segment,
                annual_income=round(annual_income, 2),
                household_income=round(household_income, 2),
                credit_score=credit_score,
                products_held=products,
                total_deposits=self._estimate_deposits(annual_income, age, segment),
                total_credit_outstanding=self._estimate_credit(annual_income, products),
                digital_adoption=digital,
                primary_channel=channel,
                tenure_years=tenure,
                products_per_household=len(products),
            )

            profiles.append(profile)

            # Quality assessment
            if self.quality_tracker:
                quality = self.quality_tracker.assess_profile(profile)
                quality_scores.append(quality.overall_score())
            else:
                quality_scores.append(0.85)  # Default when tracker unavailable

        return profiles, quality_scores

    def _generate_transactions(
        self, request: GenerationRequest
    ) -> Tuple[List[Transaction], List[float]]:
        """Generate transaction records with optional AML risk flags."""
        transactions = []
        quality_scores = []

        for i in range(request.count):
            is_suspicious = (
                request.include_risk_flags
                and request.risk_profile in ("medium", "high")
                and random.random() < (0.15 if request.risk_profile == "high" else 0.05)
            )

            if is_suspicious:
                txn = self._generate_suspicious_transaction(request)
            else:
                txn = self._generate_normal_transaction(request)

            transactions.append(txn)

            if self.quality_tracker:
                quality = self.quality_tracker.assess_transaction(txn)
                quality_scores.append(quality.overall_score())
            else:
                quality_scores.append(0.85)

        return transactions, quality_scores

    def _generate_normal_transaction(self, request: GenerationRequest) -> Transaction:
        """Generate a normal (non-suspicious) transaction."""
        txn_types = {
            "pos_purchase": 0.35,
            "e_transfer": 0.20,
            "bill_payment": 0.15,
            "online_purchase": 0.12,
            "transfer": 0.08,
            "atm": 0.05,
            "deposit": 0.03,
            "withdrawal": 0.02,
        }
        txn_type = self._weighted_choice(txn_types)

        amount_ranges = {
            "pos_purchase": (5, 500),
            "e_transfer": (20, 3000),
            "bill_payment": (30, 2000),
            "online_purchase": (10, 1000),
            "transfer": (100, 10000),
            "atm": (20, 500),
            "deposit": (500, 5000),
            "withdrawal": (50, 2000),
        }
        lo, hi = amount_ranges.get(txn_type, (10, 1000))
        amount = round(random.uniform(lo, hi), 2)

        return Transaction(
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            profile_id=request.segment or "UNLINKED",
            timestamp=datetime.now().isoformat(),
            transaction_type=txn_type,
            amount=amount,
            currency="CAD",
            is_international=False,
            risk_flag="none",
            risk_score=random.uniform(0.0, 0.15),
        )

    def _generate_suspicious_transaction(self, request: GenerationRequest) -> Transaction:
        """Generate a transaction with AML risk indicators."""
        risk_patterns = {
            "structuring": self._pattern_structuring,
            "rapid_movement": self._pattern_rapid_movement,
            "round_amounts": self._pattern_round_amounts,
            "geographic_risk": self._pattern_geographic_risk,
        }
        pattern_name = random.choice(list(risk_patterns.keys()))
        return risk_patterns[pattern_name](request)

    def _pattern_structuring(self, request: GenerationRequest) -> Transaction:
        """Generate structuring pattern: just under $10K reporting threshold."""
        amount = round(random.uniform(9000, 9999), 2)
        return Transaction(
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            profile_id=request.segment or "UNLINKED",
            timestamp=datetime.now().isoformat(),
            transaction_type="deposit",
            amount=amount,
            currency="CAD",
            risk_flag="structuring",
            risk_score=random.uniform(0.6, 0.9),
        )

    def _pattern_rapid_movement(self, request: GenerationRequest) -> Transaction:
        """Generate rapid movement pattern: large deposit followed by withdrawal."""
        amount = round(random.uniform(15000, 50000), 2)
        return Transaction(
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            profile_id=request.segment or "UNLINKED",
            timestamp=datetime.now().isoformat(),
            transaction_type=random.choice(["wire_domestic", "transfer"]),
            amount=amount,
            currency="CAD",
            risk_flag="rapid_movement",
            risk_score=random.uniform(0.5, 0.85),
        )

    def _pattern_round_amounts(self, request: GenerationRequest) -> Transaction:
        """Generate suspicious round-amount transfers."""
        amount = random.choice([5000, 10000, 15000, 20000, 25000, 50000])
        return Transaction(
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            profile_id=request.segment or "UNLINKED",
            timestamp=datetime.now().isoformat(),
            transaction_type="wire_domestic",
            amount=float(amount),
            currency="CAD",
            risk_flag="round_amounts",
            risk_score=random.uniform(0.4, 0.7),
        )

    def _pattern_geographic_risk(self, request: GenerationRequest) -> Transaction:
        """Generate transaction with high-risk jurisdiction."""
        amount = round(random.uniform(5000, 100000), 2)
        return Transaction(
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            profile_id=request.segment or "UNLINKED",
            timestamp=datetime.now().isoformat(),
            transaction_type="wire_international",
            amount=amount,
            currency="CAD",
            is_international=True,
            country_code=random.choice(["IR", "KP", "SY", "MM", "AF"]),
            risk_flag="geographic_risk",
            risk_score=random.uniform(0.7, 0.95),
        )

    # --- Statistical Sampling Helpers ---

    def _weighted_choice(self, distribution: Dict[str, float]) -> str:
        """Sample from a weighted distribution."""
        items = list(distribution.keys())
        weights = list(distribution.values())
        return random.choices(items, weights=weights, k=1)[0]

    def _age_range_from_distribution(self, age_dist) -> Tuple[int, int]:
        """Sample an age range from the age distribution."""
        band = self._weighted_choice(age_dist.distribution)
        ranges = {
            "18-24": (18, 24), "25-34": (25, 34), "35-44": (35, 44),
            "45-54": (45, 54), "55-64": (55, 64), "65-74": (65, 74),
            "75+": (75, 95),
        }
        return ranges.get(band, (25, 65))

    def _generate_income(self, income_range: Tuple[float, float], age: int) -> float:
        """Generate income correlated with age (peaks 45-55)."""
        base = random.uniform(income_range[0], income_range[1])
        # Age-income correlation: peaks around 50
        age_factor = 1.0 - abs(age - 50) * 0.005
        age_factor = max(0.6, min(1.2, age_factor))
        return base * age_factor

    def _generate_credit_score(
        self, credit_range: Tuple[int, int], age: int, income: float
    ) -> int:
        """Generate credit score correlated with age and income."""
        base = random.randint(credit_range[0], credit_range[1])
        # Older = slightly higher credit (longer history)
        age_bonus = min(30, max(0, (age - 25) * 0.5))
        # Higher income = slightly higher credit
        income_bonus = min(20, income / 50000 * 5)
        score = int(base + age_bonus + income_bonus)
        return max(300, min(900, score))

    def _sample_products(self, likelihoods: Dict[str, float]) -> List[str]:
        """Sample products based on segment-adjusted likelihoods."""
        products = []
        for product, probability in likelihoods.items():
            if random.random() < probability:
                products.append(product)
        # Everyone has at least chequing
        if "chequing" not in products:
            products.insert(0, "chequing")
        return products

    def _digital_adoption_for_age(self, age: int, dist) -> str:
        """Adjust digital adoption based on age."""
        adjusted = dict(dist.distribution)
        if age < 35:
            adjusted["digital_first"] = adjusted.get("digital_first", 0.5) * 1.4
            adjusted["branch_preferred"] = adjusted.get("branch_preferred", 0.1) * 0.3
        elif age > 65:
            adjusted["digital_first"] = adjusted.get("digital_first", 0.5) * 0.5
            adjusted["branch_preferred"] = adjusted.get("branch_preferred", 0.1) * 2.5
        # Normalize
        total = sum(adjusted.values())
        adjusted = {k: v / total for k, v in adjusted.items()}
        return self._weighted_choice(adjusted)

    def _channel_for_digital(self, digital: str, dist) -> str:
        """Adjust channel based on digital adoption."""
        adjusted = dict(dist.distribution)
        if digital == "digital_first":
            adjusted["mobile"] = adjusted.get("mobile", 0.45) * 1.5
            adjusted["branch"] = adjusted.get("branch", 0.18) * 0.2
        elif digital == "branch_preferred":
            adjusted["branch"] = adjusted.get("branch", 0.18) * 3.0
            adjusted["mobile"] = adjusted.get("mobile", 0.45) * 0.3
        total = sum(adjusted.values())
        adjusted = {k: v / total for k, v in adjusted.items()}
        return self._weighted_choice(adjusted)

    def _estimate_deposits(self, income: float, age: int, segment: str) -> float:
        """Estimate total deposits based on income, age, segment."""
        # Savings rate increases with income and age
        savings_rate = min(0.35, 0.05 + (income / 1_000_000) + (age / 500))
        years_saving = max(1, age - 22)
        base = income * savings_rate * years_saving * random.uniform(0.3, 0.7)
        return round(max(0, base), 2)

    def _estimate_credit(self, income: float, products: List[str]) -> float:
        """Estimate total credit outstanding based on income and products."""
        credit = 0.0
        if "mortgage" in products:
            credit += income * random.uniform(3, 6)  # 3-6x income
        if "heloc" in products:
            credit += income * random.uniform(0.5, 2)
        if "credit_card" in products:
            credit += random.uniform(1000, 15000)
        if "personal_loan" in products:
            credit += random.uniform(5000, 30000)
        if "auto_loan" in products:
            credit += random.uniform(10000, 50000)
        return round(credit, 2)

    # --- Output ---

    def _write_output(
        self, records: list, request: GenerationRequest
    ) -> Optional[Path]:
        """Write generated records to output file."""
        if not records:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.data_type}_{timestamp}"

        if request.output_path:
            output_path = Path(request.output_path)
        else:
            output_path = self._output_dir / f"{filename}.jsonl"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if request.output_format == "jsonl":
            with open(output_path, "w") as f:
                for record in records:
                    f.write(json.dumps(record.to_dict()) + "\n")
        elif request.output_format == "json":
            output_path = output_path.with_suffix(".json")
            with open(output_path, "w") as f:
                json.dump([r.to_dict() for r in records], f, indent=2)
        elif request.output_format == "csv":
            output_path = output_path.with_suffix(".csv")
            import csv
            if records:
                fieldnames = list(records[0].to_dict().keys())
                with open(output_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for record in records:
                        writer.writerow(record.to_dict())

        return output_path

    def _log_generation_outcome(self, result: GenerationResult):
        """Log generation run for the Cortex outcome flywheel."""
        outcome_path = self._output_dir / "generation_outcomes.jsonl"
        outcome = {
            "flywheel_id": result.flywheel_id,
            "timestamp": datetime.now().isoformat(),
            "data_type": result.request.data_type,
            "count_requested": result.request.count,
            "count_generated": result.records_generated,
            "count_passed": result.records_passed_quality,
            "count_rejected": result.records_rejected,
            "avg_quality": result.average_quality_score,
            "quality_distribution": result.quality_distribution,
            "generation_time_s": result.generation_time_seconds,
            "segment": result.request.segment,
            "province": result.request.province,
            "min_quality_threshold": result.request.min_quality_score,
            # Outcome fields — filled later by flywheel
            "usage_outcome": None,
            "client_feedback": None,
        }
        with open(outcome_path, "a") as f:
            f.write(json.dumps(outcome) + "\n")
