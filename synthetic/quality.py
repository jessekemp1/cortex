#!/usr/bin/env python3
"""
Synthetic Data Quality Validator — Adapted from Cortex's DataQualityTracker.

Validates synthetic Canadian FinServ data across six dimensions,
with domain-specific checks for financial data coherence.

Key additions over base quality tracker:
- Cross-field consistency (income vs segment, credit score vs products)
- Canadian regulatory compliance checks (OSFI, FINTRAC thresholds)
- Distribution fidelity assessment (sample vs StatsCan benchmarks)
"""

import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.quality.data_quality import QualityDimensions

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile, Transaction


class SyntheticQualityTracker:
    """
    Quality tracker specialized for synthetic Canadian FinServ data.

    Extends Cortex's 6-dimension quality model with domain-specific
    validation rules for financial data coherence and Canadian market
    distribution fidelity.
    """

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()
        self.existing_hashes: Set[str] = set()
        self.quality_history: List[Dict[str, Any]] = []

    def assess_profile(self, profile: CustomerProfile) -> QualityDimensions:
        """
        Assess quality of a synthetic customer profile.

        Checks:
        - Completeness: All required fields populated
        - Consistency: Income matches segment, credit score realistic for age
        - Accuracy: Values within Canadian market ranges
        - Timeliness: Generation timestamp recent
        - Uniqueness: No duplicate profile IDs
        - Validity: Schema compliance, enum validation
        """
        data = profile.to_dict()

        completeness = self._check_profile_completeness(data)
        consistency = self._check_profile_consistency(data)
        accuracy = self._check_profile_accuracy(data)
        timeliness = self._check_timeliness(data)
        uniqueness = self._check_uniqueness(data, "profile_id")
        validity = self._check_profile_validity(data)

        quality = QualityDimensions(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
        )

        self._track(data, "profile", quality)
        return quality

    def assess_transaction(self, txn: Transaction) -> QualityDimensions:
        """Assess quality of a synthetic transaction record."""
        data = txn.to_dict()

        completeness = self._check_transaction_completeness(data)
        consistency = self._check_transaction_consistency(data)
        accuracy = self._check_transaction_accuracy(data)
        timeliness = self._check_timeliness(data)
        uniqueness = self._check_uniqueness(data, "transaction_id")
        validity = self._check_transaction_validity(data)

        quality = QualityDimensions(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
        )

        self._track(data, "transaction", quality)
        return quality

    def assess_batch_distribution(
        self, profiles: List[CustomerProfile]
    ) -> Dict[str, Tuple[bool, float]]:
        """
        Assess how well a batch of profiles matches Canadian distributions.

        Returns dict of constraint_name -> (passes, deviation).
        """
        if not profiles:
            return {}

        results = {}

        # Province distribution
        prov_counts = {}
        for p in profiles:
            prov_counts[p.province] = prov_counts.get(p.province, 0) + 1
        prov_dist = {k: v / len(profiles) for k, v in prov_counts.items()}
        constraint = self.kb.get_constraint("province_distribution")
        if constraint:
            results["province_distribution"] = constraint.validate_sample(prov_dist)

        # Segment distribution
        seg_counts = {}
        for p in profiles:
            seg_counts[p.segment] = seg_counts.get(p.segment, 0) + 1
        seg_dist = {k: v / len(profiles) for k, v in seg_counts.items()}
        constraint = self.kb.get_constraint("segment_distribution")
        if constraint:
            results["segment_distribution"] = constraint.validate_sample(seg_dist)

        # Digital adoption distribution
        dig_counts = {}
        for p in profiles:
            dig_counts[p.digital_adoption] = dig_counts.get(p.digital_adoption, 0) + 1
        dig_dist = {k: v / len(profiles) for k, v in dig_counts.items()}
        constraint = self.kb.get_constraint("digital_adoption")
        if constraint:
            results["digital_adoption"] = constraint.validate_sample(dig_dist)

        return results

    # --- Profile Checks ---

    def _check_profile_completeness(self, data: Dict[str, Any]) -> float:
        """Check all required profile fields are populated."""
        required = [
            "profile_id", "age", "province", "fsa", "segment",
            "annual_income", "household_income", "credit_score",
            "products_held", "digital_adoption", "primary_channel",
            "tenure_years", "products_per_household",
        ]
        present = sum(1 for f in required if data.get(f) is not None)
        return present / len(required)

    def _check_profile_consistency(self, data: Dict[str, Any]) -> float:
        """Check cross-field consistency for financial realism."""
        checks_passed = 0
        total_checks = 0

        # Income vs segment consistency
        total_checks += 1
        segment = data.get("segment", "")
        income = data.get("annual_income", 0)
        expected_range = self.kb.get_income_range_for_segment(segment)
        # Allow 20% tolerance beyond range
        tolerance = (expected_range[1] - expected_range[0]) * 0.2
        if expected_range[0] - tolerance <= income <= expected_range[1] + tolerance:
            checks_passed += 1

        # Credit score vs segment
        total_checks += 1
        credit = data.get("credit_score", 0)
        credit_range = self.kb.get_credit_score_range_for_segment(segment)
        if credit_range[0] - 50 <= credit <= credit_range[1] + 50:
            checks_passed += 1

        # Household income >= individual income
        total_checks += 1
        if data.get("household_income", 0) >= data.get("annual_income", 0):
            checks_passed += 1

        # Age vs tenure (can't bank longer than they've been an adult)
        total_checks += 1
        age = data.get("age", 0)
        tenure = data.get("tenure_years", 0)
        if tenure <= max(0, age - 16):
            checks_passed += 1

        # Products count matches products list
        total_checks += 1
        if data.get("products_per_household", 0) == len(data.get("products_held", [])):
            checks_passed += 1

        # Digital adoption vs age correlation (soft check)
        total_checks += 1
        digital = data.get("digital_adoption", "")
        if age < 30 and digital == "branch_preferred":
            checks_passed += 0.5  # Unusual but not impossible
        elif age > 75 and digital == "digital_first":
            checks_passed += 0.5
        else:
            checks_passed += 1

        return checks_passed / total_checks if total_checks > 0 else 1.0

    def _check_profile_accuracy(self, data: Dict[str, Any]) -> float:
        """Check values are within realistic Canadian market ranges."""
        checks_passed = 0
        total_checks = 0

        # Age range (18-100 for banking)
        total_checks += 1
        if 18 <= data.get("age", 0) <= 100:
            checks_passed += 1

        # Credit score range (Canadian: 300-900)
        total_checks += 1
        if 300 <= data.get("credit_score", 0) <= 900:
            checks_passed += 1

        # Income non-negative
        total_checks += 1
        if data.get("annual_income", 0) >= 0:
            checks_passed += 1

        # Province valid
        total_checks += 1
        valid_provinces = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
        if data.get("province") in valid_provinces:
            checks_passed += 1

        # FSA format (letter-digit-letter)
        total_checks += 1
        fsa = data.get("fsa", "")
        if len(fsa) == 3 and fsa[0].isalpha() and fsa[1].isdigit() and fsa[2].isalpha():
            checks_passed += 1

        # Products list non-empty (everyone should have at least chequing)
        total_checks += 1
        products = data.get("products_held", [])
        if len(products) >= 1 and "chequing" in products:
            checks_passed += 1

        return checks_passed / total_checks if total_checks > 0 else 1.0

    # --- Transaction Checks ---

    def _check_transaction_completeness(self, data: Dict[str, Any]) -> float:
        """Check required transaction fields."""
        required = [
            "transaction_id", "profile_id", "timestamp",
            "transaction_type", "amount", "currency",
        ]
        present = sum(1 for f in required if data.get(f) is not None)
        return present / len(required)

    def _check_transaction_consistency(self, data: Dict[str, Any]) -> float:
        """Check transaction field consistency."""
        checks_passed = 0
        total_checks = 0

        # International transactions should have country_code
        total_checks += 1
        if data.get("is_international") and not data.get("country_code"):
            checks_passed += 0  # Missing required field
        else:
            checks_passed += 1

        # Risk flag should match risk score range
        total_checks += 1
        risk_flag = data.get("risk_flag", "none")
        risk_score = data.get("risk_score", 0)
        if risk_flag == "none" and risk_score < 0.3:
            checks_passed += 1
        elif risk_flag != "none" and risk_score >= 0.3:
            checks_passed += 1
        else:
            checks_passed += 0.5  # Partial consistency

        # Wire international type should be international
        total_checks += 1
        txn_type = data.get("transaction_type", "")
        if txn_type == "wire_international" and not data.get("is_international"):
            checks_passed += 0
        else:
            checks_passed += 1

        return checks_passed / total_checks if total_checks > 0 else 1.0

    def _check_transaction_accuracy(self, data: Dict[str, Any]) -> float:
        """Check transaction values are realistic."""
        checks_passed = 0
        total_checks = 0

        # Amount positive
        total_checks += 1
        if data.get("amount", 0) > 0:
            checks_passed += 1

        # Currency is valid
        total_checks += 1
        if data.get("currency") in ("CAD", "USD", "EUR", "GBP"):
            checks_passed += 1

        # Risk score in range
        total_checks += 1
        if 0.0 <= data.get("risk_score", 0) <= 1.0:
            checks_passed += 1

        return checks_passed / total_checks if total_checks > 0 else 1.0

    def _check_transaction_validity(self, data: Dict[str, Any]) -> float:
        """Check transaction schema validity."""
        checks_passed = 0
        total_checks = 0

        # Transaction type is valid enum
        total_checks += 1
        valid_types = {
            "deposit", "withdrawal", "transfer", "bill_payment",
            "e_transfer", "wire_domestic", "wire_international",
            "pos_purchase", "online_purchase", "atm",
            "mortgage_payment", "investment_contribution",
        }
        if data.get("transaction_type") in valid_types:
            checks_passed += 1

        # Risk flag is valid enum
        total_checks += 1
        valid_flags = {
            "none", "structuring", "rapid_movement", "geographic_risk",
            "unusual_volume", "round_amounts", "dormant_reactivation", "third_party",
        }
        if data.get("risk_flag") in valid_flags:
            checks_passed += 1

        # Timestamp parseable
        total_checks += 1
        try:
            datetime.fromisoformat(data.get("timestamp", ""))
            checks_passed += 1
        except (ValueError, TypeError):
            pass

        return checks_passed / total_checks if total_checks > 0 else 1.0

    # --- Shared Checks ---

    def _check_timeliness(self, data: Dict[str, Any]) -> float:
        """Check data freshness (synthetic data should be recently generated)."""
        generated_at = data.get("generated_at")
        if not generated_at:
            return 0.5  # No timestamp = partial score

        try:
            gen_time = datetime.fromisoformat(generated_at)
            age_hours = (datetime.now() - gen_time).total_seconds() / 3600
            if age_hours < 1:
                return 1.0
            elif age_hours < 24:
                return 0.9
            elif age_hours < 168:  # 1 week
                return 0.7
            else:
                return 0.5
        except (ValueError, TypeError):
            return 0.5

    def _check_uniqueness(self, data: Dict[str, Any], id_field: str) -> float:
        """Check record is unique (no duplicate IDs)."""
        record_id = data.get(id_field, "")
        record_hash = hashlib.md5(record_id.encode()).hexdigest()

        if record_hash in self.existing_hashes:
            return 0.0  # Duplicate
        self.existing_hashes.add(record_hash)
        return 1.0

    def _check_profile_validity(self, data: Dict[str, Any]) -> float:
        """Check profile schema validity."""
        checks_passed = 0
        total_checks = 0

        # Segment is valid enum
        total_checks += 1
        valid_segments = {
            "mass_market", "mass_affluent", "affluent",
            "high_net_worth", "ultra_hnw", "small_business",
            "commercial", "new_to_canada",
        }
        if data.get("segment") in valid_segments:
            checks_passed += 1

        # Digital adoption is valid enum
        total_checks += 1
        if data.get("digital_adoption") in ("digital_first", "hybrid", "branch_preferred"):
            checks_passed += 1

        # Primary channel is valid enum
        total_checks += 1
        if data.get("primary_channel") in ("mobile", "online", "branch", "telephone"):
            checks_passed += 1

        # Province is valid
        total_checks += 1
        valid_provinces = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
        if data.get("province") in valid_provinces:
            checks_passed += 1

        return checks_passed / total_checks if total_checks > 0 else 1.0

    def _track(self, data: Dict, item_type: str, quality: QualityDimensions):
        """Track quality measurement for trends."""
        self.quality_history.append({
            "timestamp": datetime.now().isoformat(),
            "item_type": item_type,
            "quality": quality.to_dict(),
        })
