"""
Synthetic data generator for CortexDBx MVP.

Generates realistic outcomes across 6 domains for dev and testing.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Generator, Optional
import random
import hashlib
import json
from datetime import datetime, timedelta
import uuid


@dataclass
class DomainConfig:
    """Domain-specific configuration for realistic data generation."""

    context_factors: List[str]
    strategy_types: List[str]
    outcome_weights: Dict[str, float]


DOMAIN_CONFIGS: Dict[str, DomainConfig] = {
    "fraud_investigation": DomainConfig(
        context_factors=[
            "alert_type",
            "transaction_amount_bucket",
            "account_age_bucket",
            "swift_code_region",
            "time_of_day",
            "device_fingerprint_match",
            "historical_fraud_rate",
            "velocity_score",
        ],
        strategy_types=[
            "auto_close_low_risk",
            "escalate_to_analyst",
            "freeze_account",
            "request_verification",
            "manual_review_queue",
            "ml_rescore",
        ],
        outcome_weights={"SUCCESS": 0.70, "FAILURE": 0.20, "PARTIAL": 0.10},
    ),
    "clinical_trial": DomainConfig(
        context_factors=[
            "trial_phase",
            "therapeutic_area",
            "inclusion_criteria_count",
            "site_location",
            "patient_demographics",
            "prior_trial_history",
            "enrollment_velocity",
            "dropout_rate",
        ],
        strategy_types=[
            "relax_bmi_criteria",
            "add_recruitment_site",
            "extend_age_range",
            "modify_exclusion_criteria",
            "increase_compensation",
            "digital_outreach",
        ],
        outcome_weights={"SUCCESS": 0.55, "FAILURE": 0.30, "PARTIAL": 0.15},
    ),
    "maintenance": DomainConfig(
        context_factors=[
            "equipment_type",
            "sensor_reading_pattern",
            "operating_hours",
            "last_maintenance_days",
            "failure_history",
            "manufacturer",
            "environmental_conditions",
            "criticality_level",
        ],
        strategy_types=[
            "replace_bearing",
            "check_alignment",
            "lubrication_cycle",
            "full_inspection",
            "sensor_recalibration",
            "schedule_shutdown",
        ],
        outcome_weights={"SUCCESS": 0.65, "FAILURE": 0.25, "PARTIAL": 0.10},
    ),
    "marketing_campaign": DomainConfig(
        context_factors=[
            "audience_segment",
            "channel",
            "creative_type",
            "offer_type",
            "time_of_year",
            "competitor_activity",
            "budget_tier",
            "campaign_duration",
        ],
        strategy_types=[
            "urgency_messaging",
            "value_messaging",
            "social_proof",
            "personalization",
            "retargeting",
            "influencer_partnership",
        ],
        outcome_weights={"SUCCESS": 0.45, "FAILURE": 0.35, "PARTIAL": 0.20},
    ),
    "security_incident": DomainConfig(
        context_factors=[
            "alert_severity",
            "attack_vector",
            "affected_systems",
            "time_to_detection",
            "attacker_sophistication",
            "data_sensitivity",
            "business_hours",
            "prior_incident_similarity",
        ],
        strategy_types=[
            "block_ip",
            "geo_block_rate_limit",
            "isolate_system",
            "credential_rotation",
            "forensic_capture",
            "executive_notification",
        ],
        outcome_weights={"SUCCESS": 0.60, "FAILURE": 0.25, "PARTIAL": 0.15},
    ),
    "supply_chain": DomainConfig(
        context_factors=[
            "product_category",
            "origin_region",
            "destination_region",
            "shipping_mode",
            "weather_conditions",
            "supplier_tier",
            "demand_urgency",
            "customs_complexity",
        ],
        strategy_types=[
            "primary_supplier",
            "backup_supplier",
            "air_freight_upgrade",
            "split_shipment",
            "local_warehouse",
            "expedited_customs",
        ],
        outcome_weights={"SUCCESS": 0.55, "FAILURE": 0.30, "PARTIAL": 0.15},
    ),
}


class SyntheticDataGenerator:
    """Generate realistic synthetic data for CortexDBx MVP."""

    def __init__(self, domain: str, seed: Optional[int] = 42):
        if domain not in DOMAIN_CONFIGS:
            raise ValueError(
                f"Unknown domain: {domain}. Valid: {list(DOMAIN_CONFIGS.keys())}"
            )
        self.domain = domain
        self.config = DOMAIN_CONFIGS[domain]
        random.seed(seed)
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._generate_strategies()

    def _generate_strategies(self) -> None:
        """Pre-generate strategies with inherent success rates."""
        for i, name in enumerate(self.config.strategy_types):
            base_success_rate = random.uniform(0.3, 0.9)
            sid = f"strategy_{self.domain}_{i}"
            self._strategies[sid] = {
                "strategy_id": sid,
                "name": name,
                "domain": self.domain,
                "inherent_success_rate": base_success_rate,
                "category": random.choice(
                    ["primary", "fallback", "experimental"]
                ),
            }

    def _generate_context(self) -> Dict[str, Any]:
        """Generate a random context."""
        factors = []
        for factor_name in self.config.context_factors:
            if "bucket" in factor_name or "tier" in factor_name:
                value = random.choice(["low", "medium", "high"])
            elif "rate" in factor_name or "score" in factor_name:
                value = str(round(random.uniform(0, 1), 2))
            elif "count" in factor_name:
                value = str(random.randint(1, 20))
            elif "days" in factor_name or "hours" in factor_name:
                value = str(random.randint(1, 365))
            else:
                value = f"value_{random.randint(1, 10)}"
            factors.append({"key": factor_name, "value": value})

        factors_str = json.dumps(sorted(factors, key=lambda x: x["key"]))
        context_hash = hashlib.sha256(factors_str.encode()).hexdigest()[:16]
        return {
            "context_id": f"ctx_{context_hash}",
            "context_hash": context_hash,
            "domain": self.domain,
            "factors": factors,
        }

    def _generate_outcome(
        self, context: Dict[str, Any], strategy: Dict[str, Any], timestamp: datetime
    ) -> Dict[str, Any]:
        """Generate an outcome based on strategy inherent success rate."""
        inherent_rate = strategy["inherent_success_rate"]
        effective_rate = inherent_rate + random.gauss(0, 0.1)
        effective_rate = max(0.05, min(0.95, effective_rate))

        roll = random.random()
        if roll < effective_rate:
            result = "SUCCESS"
        elif roll < effective_rate + 0.15:
            result = "PARTIAL"
        else:
            result = "FAILURE"

        return {
            "outcome_id": str(uuid.uuid4()),
            "context_id": context["context_id"],
            "strategy_id": strategy["strategy_id"],
            "result": result,
            "evidence": json.dumps(
                {
                    "source": "synthetic_generator",
                    "context_factors": context["factors"][:3],
                    "strategy_name": strategy["name"],
                }
            ),
            "actor": f"synthetic_user_{random.randint(1, 10)}",
            "created_at": timestamp.isoformat(),
        }

    def generate_dataset(
        self, num_outcomes: int, days_span: int = 90
    ) -> Generator[Dict[str, Any], None, None]:
        """Generate a complete synthetic dataset."""
        num_contexts = max(1, min(num_outcomes // 10, 500))
        contexts = [self._generate_context() for _ in range(num_contexts)]
        start_date = datetime.now() - timedelta(days=days_span)
        strategies_list = list(self._strategies.values())

        for _ in range(num_outcomes):
            random_days = random.uniform(0, days_span)
            timestamp = start_date + timedelta(days=random_days)
            context = random.choice(contexts)
            strategy = random.choice(strategies_list)
            outcome = self._generate_outcome(context, strategy, timestamp)
            yield {
                "context": context,
                "strategy": strategy,
                "outcome": outcome,
            }

    def get_ground_truth(self) -> Dict[str, float]:
        """Return ground truth success rates for validation."""
        return {
            s["strategy_id"]: s["inherent_success_rate"]
            for s in self._strategies.values()
        }

    @property
    def strategies(self) -> Dict[str, Dict[str, Any]]:
        """Return strategy definitions."""
        return dict(self._strategies)


def generate_all_domains(
    outcomes_per_domain: int = 1000,
) -> Dict[str, Dict[str, Any]]:
    """Generate synthetic data for all 6 use cases."""
    all_data: Dict[str, Dict[str, Any]] = {}
    for domain in DOMAIN_CONFIGS:
        generator = SyntheticDataGenerator(domain)
        data = list(generator.generate_dataset(outcomes_per_domain))
        all_data[domain] = {
            "outcomes": data,
            "ground_truth": generator.get_ground_truth(),
            "strategies": generator.strategies,
        }
    return all_data
