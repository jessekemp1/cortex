#!/usr/bin/env python3
"""
Segment Behavioral Models — Decision rules per customer segment.

Calibrated from public Canadian data sources:
- CBA Financial Statistics 2024 (churn, digital adoption, product penetration)
- Big 5 Annual Reports 2024 (segment distributions, cross-sell ratios)
- Statistics Canada (income, demographics)
- Equifax Canada Credit Trends 2024 (credit score dynamics)

Each segment model defines behavioral parameters that PersonaAgents use
to make decisions at each simulation step. Parameters are deliberately
conservative — better to underpredict churn than overpredict.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SegmentBehavior:
    """Behavioral parameters for a customer segment."""

    segment_name: str

    # Churn / switching
    base_annual_churn_rate: float       # Annual probability of leaving
    rate_sensitivity: float             # 0-1: how rate changes affect decisions
    fee_sensitivity: float              # 0-1: how fee changes matter
    competitor_susceptibility: float    # 0-1: response to competitor offers

    # Product behavior
    product_adoption_propensity: float  # 0-1: likelihood of adding products/year
    target_products: int                # Typical product count
    preferred_products: List[str]       # Products this segment gravitates toward

    # Financial behavior
    savings_rate_threshold: float       # Min rate to keep savings (vs switching)
    mortgage_likelihood: float          # Probability of having/getting mortgage
    investment_propensity: float        # 0-1: likelihood of investment products

    # Stress response
    unemployment_sensitivity: float     # 0-1: how unemployment affects behavior
    payment_miss_threshold: int         # Credit score below which misses start
    default_threshold: int              # Credit score below which defaults start
    credit_recovery_rate: float         # Points/month credit recovers

    # Digital behavior
    digital_preference: float           # 0-1: digital channel preference
    fintech_openness: float             # 0-1: willingness to use fintech

    # Lifecycle
    avg_tenure_years: float
    loyalty_bonus_per_year: float       # Churn reduction per year of tenure


# ============================================================================
# 8 Segment Models (CBA/StatsCan/Big 5 Annual Reports)
# ============================================================================

MASS_MARKET = SegmentBehavior(
    segment_name="mass_market",
    base_annual_churn_rate=0.18,
    rate_sensitivity=0.15,
    fee_sensitivity=0.70,
    competitor_susceptibility=0.30,
    product_adoption_propensity=0.10,
    target_products=2,
    preferred_products=["chequing", "savings", "credit_card"],
    savings_rate_threshold=2.0,
    mortgage_likelihood=0.25,
    investment_propensity=0.10,
    unemployment_sensitivity=0.80,
    payment_miss_threshold=600,
    default_threshold=500,
    credit_recovery_rate=3.0,
    digital_preference=0.55,
    fintech_openness=0.35,
    avg_tenure_years=6.0,
    loyalty_bonus_per_year=0.005,
)

MASS_AFFLUENT = SegmentBehavior(
    segment_name="mass_affluent",
    base_annual_churn_rate=0.12,
    rate_sensitivity=0.45,
    fee_sensitivity=0.50,
    competitor_susceptibility=0.50,
    product_adoption_propensity=0.25,
    target_products=4,
    preferred_products=[
        "chequing", "savings", "tfsa", "rrsp", "credit_card", "mortgage",
    ],
    savings_rate_threshold=3.5,
    mortgage_likelihood=0.55,
    investment_propensity=0.40,
    unemployment_sensitivity=0.50,
    payment_miss_threshold=620,
    default_threshold=520,
    credit_recovery_rate=4.0,
    digital_preference=0.75,
    fintech_openness=0.55,
    avg_tenure_years=9.0,
    loyalty_bonus_per_year=0.008,
)

AFFLUENT = SegmentBehavior(
    segment_name="affluent",
    base_annual_churn_rate=0.08,
    rate_sensitivity=0.65,
    fee_sensitivity=0.30,
    competitor_susceptibility=0.35,
    product_adoption_propensity=0.20,
    target_products=6,
    preferred_products=[
        "chequing", "savings", "tfsa", "rrsp", "mortgage", "heloc",
        "investment_account", "credit_card", "insurance_life",
    ],
    savings_rate_threshold=4.0,
    mortgage_likelihood=0.70,
    investment_propensity=0.70,
    unemployment_sensitivity=0.25,
    payment_miss_threshold=650,
    default_threshold=550,
    credit_recovery_rate=5.0,
    digital_preference=0.65,
    fintech_openness=0.30,
    avg_tenure_years=14.0,
    loyalty_bonus_per_year=0.010,
)

HIGH_NET_WORTH = SegmentBehavior(
    segment_name="high_net_worth",
    base_annual_churn_rate=0.05,
    rate_sensitivity=0.80,
    fee_sensitivity=0.20,
    competitor_susceptibility=0.25,
    product_adoption_propensity=0.15,
    target_products=7,
    preferred_products=[
        "chequing", "savings", "tfsa", "rrsp", "mortgage", "heloc",
        "investment_account", "gic", "insurance_life", "insurance_home",
    ],
    savings_rate_threshold=4.5,
    mortgage_likelihood=0.75,
    investment_propensity=0.90,
    unemployment_sensitivity=0.10,
    payment_miss_threshold=680,
    default_threshold=580,
    credit_recovery_rate=6.0,
    digital_preference=0.50,
    fintech_openness=0.15,
    avg_tenure_years=18.0,
    loyalty_bonus_per_year=0.012,
)

ULTRA_HNW = SegmentBehavior(
    segment_name="ultra_hnw",
    base_annual_churn_rate=0.03,
    rate_sensitivity=0.85,
    fee_sensitivity=0.10,
    competitor_susceptibility=0.15,
    product_adoption_propensity=0.10,
    target_products=8,
    preferred_products=[
        "chequing", "savings", "tfsa", "rrsp", "mortgage", "heloc",
        "investment_account", "gic", "insurance_life", "insurance_home",
        "insurance_auto",
    ],
    savings_rate_threshold=4.5,
    mortgage_likelihood=0.60,
    investment_propensity=0.95,
    unemployment_sensitivity=0.05,
    payment_miss_threshold=700,
    default_threshold=600,
    credit_recovery_rate=7.0,
    digital_preference=0.40,
    fintech_openness=0.08,
    avg_tenure_years=22.0,
    loyalty_bonus_per_year=0.015,
)

SMALL_BUSINESS = SegmentBehavior(
    segment_name="small_business",
    base_annual_churn_rate=0.15,
    rate_sensitivity=0.55,
    fee_sensitivity=0.65,
    competitor_susceptibility=0.40,
    product_adoption_propensity=0.20,
    target_products=4,
    preferred_products=[
        "chequing", "savings", "credit_card", "personal_loan", "insurance_life",
    ],
    savings_rate_threshold=3.5,
    mortgage_likelihood=0.35,
    investment_propensity=0.25,
    unemployment_sensitivity=0.70,
    payment_miss_threshold=600,
    default_threshold=500,
    credit_recovery_rate=3.5,
    digital_preference=0.70,
    fintech_openness=0.50,
    avg_tenure_years=7.0,
    loyalty_bonus_per_year=0.006,
)

COMMERCIAL = SegmentBehavior(
    segment_name="commercial",
    base_annual_churn_rate=0.06,
    rate_sensitivity=0.70,
    fee_sensitivity=0.40,
    competitor_susceptibility=0.20,
    product_adoption_propensity=0.15,
    target_products=5,
    preferred_products=[
        "chequing", "savings", "credit_card", "personal_loan",
        "investment_account", "insurance_life",
    ],
    savings_rate_threshold=4.0,
    mortgage_likelihood=0.50,
    investment_propensity=0.55,
    unemployment_sensitivity=0.40,
    payment_miss_threshold=640,
    default_threshold=540,
    credit_recovery_rate=4.5,
    digital_preference=0.55,
    fintech_openness=0.20,
    avg_tenure_years=12.0,
    loyalty_bonus_per_year=0.010,
)

NEW_TO_CANADA = SegmentBehavior(
    segment_name="new_to_canada",
    base_annual_churn_rate=0.22,
    rate_sensitivity=0.25,
    fee_sensitivity=0.80,
    competitor_susceptibility=0.60,
    product_adoption_propensity=0.40,
    target_products=3,
    preferred_products=["chequing", "savings", "credit_card", "tfsa"],
    savings_rate_threshold=2.5,
    mortgage_likelihood=0.15,
    investment_propensity=0.15,
    unemployment_sensitivity=0.75,
    payment_miss_threshold=580,
    default_threshold=480,
    credit_recovery_rate=4.0,
    digital_preference=0.85,
    fintech_openness=0.70,
    avg_tenure_years=3.0,
    loyalty_bonus_per_year=0.003,
)


SEGMENT_MODELS: Dict[str, SegmentBehavior] = {
    "mass_market": MASS_MARKET,
    "mass_affluent": MASS_AFFLUENT,
    "affluent": AFFLUENT,
    "high_net_worth": HIGH_NET_WORTH,
    "ultra_hnw": ULTRA_HNW,
    "small_business": SMALL_BUSINESS,
    "commercial": COMMERCIAL,
    "new_to_canada": NEW_TO_CANADA,
}


def get_behavior(segment: str) -> SegmentBehavior:
    """Get behavioral model for a segment. Falls back to mass_market."""
    return SEGMENT_MODELS.get(segment, MASS_MARKET)
