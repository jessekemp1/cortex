#!/usr/bin/env python3
"""
Canadian FinServ Knowledge Base — Distribution constraints and domain knowledge.

Sources (all public):
- Statistics Canada (Census 2021): Demographics, income, geography
- CMHC: Housing/mortgage market data
- Bank of Canada: Interest rates, economic indicators
- OSFI: Regulatory parameters, stress test rates
- Big 5 Annual Reports: Product mix, segment distribution

This module provides the statistical constraints that make synthetic data
realistic. The generator uses these distributions to calibrate output.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DistributionConstraint:
    """A statistical constraint for synthetic data generation."""

    name: str
    dimension: str  # Which field this constrains
    distribution: Dict[str, float]  # value -> probability
    source: str  # Data source citation
    year: int  # Source data year
    tolerance: float = 0.05  # Acceptable deviation from target (5%)

    def validate_sample(self, sample_distribution: Dict[str, float]) -> Tuple[bool, float]:
        """Check if a sample distribution matches within tolerance."""
        max_deviation = 0.0
        for key, target_pct in self.distribution.items():
            actual_pct = sample_distribution.get(key, 0.0)
            deviation = abs(actual_pct - target_pct)
            max_deviation = max(max_deviation, deviation)
        return max_deviation <= self.tolerance, max_deviation


class CanadianFinServKB:
    """
    Canadian Financial Services Knowledge Base.

    Provides distribution constraints and domain knowledge for generating
    realistic synthetic data calibrated to the Canadian market.
    """

    def __init__(self):
        self._constraints: Dict[str, DistributionConstraint] = {}
        self._load_demographics()
        self._load_income_distributions()
        self._load_credit_distributions()
        self._load_product_distributions()
        self._load_digital_adoption()
        self._load_regulatory_parameters()

    def _load_demographics(self):
        """Population distribution by province (StatsCan Census 2021)."""
        self._constraints["province_distribution"] = DistributionConstraint(
            name="Provincial Population Distribution",
            dimension="province",
            distribution={
                "ON": 0.385,  # 38.5% — Ontario
                "QC": 0.228,  # 22.8% — Quebec
                "BC": 0.134,  # 13.4% — British Columbia
                "AB": 0.116,  # 11.6% — Alberta
                "MB": 0.037,  # 3.7% — Manitoba
                "SK": 0.031,  # 3.1% — Saskatchewan
                "NS": 0.027,  # 2.7% — Nova Scotia
                "NB": 0.022,  # 2.2% — New Brunswick
                "NL": 0.014,  # 1.4% — Newfoundland & Labrador
                "PE": 0.005,  # 0.5% — PEI
                "NT": 0.001,  # Northern territories combined
                "NU": 0.001,
                "YT": 0.001,
            },
            source="Statistics Canada, Census 2021, Table 98-10-0001-01",
            year=2021,
        )

        self._constraints["age_distribution"] = DistributionConstraint(
            name="Adult Age Distribution (Banking Population 18+)",
            dimension="age",
            distribution={
                "18-24": 0.10,
                "25-34": 0.17,
                "35-44": 0.16,
                "45-54": 0.16,
                "55-64": 0.17,
                "65-74": 0.14,
                "75+": 0.10,
            },
            source="Statistics Canada, Census 2021, Age and Sex",
            year=2021,
        )

    def _load_income_distributions(self):
        """Income distributions by segment (StatsCan + bank reports)."""
        self._constraints["income_distribution"] = DistributionConstraint(
            name="Individual Income Distribution",
            dimension="annual_income",
            distribution={
                "under_25k": 0.28,
                "25k_50k": 0.24,
                "50k_75k": 0.17,
                "75k_100k": 0.12,
                "100k_150k": 0.10,
                "150k_250k": 0.06,
                "250k_plus": 0.03,
            },
            source="Statistics Canada, Income Statistics 2022, Table 11-10-0239-01",
            year=2022,
        )

        self._constraints["segment_distribution"] = DistributionConstraint(
            name="Customer Segment Distribution (Big 5 Average)",
            dimension="segment",
            distribution={
                "mass_market": 0.55,
                "mass_affluent": 0.25,
                "affluent": 0.12,
                "high_net_worth": 0.05,
                "ultra_hnw": 0.01,
                "small_business": 0.015,
                "commercial": 0.005,
            },
            source="Big 5 Bank Annual Reports Aggregate, 2024",
            year=2024,
        )

    def _load_credit_distributions(self):
        """Credit score distributions (Equifax Canada)."""
        self._constraints["credit_score_distribution"] = DistributionConstraint(
            name="Credit Score Distribution (Canadian Adults)",
            dimension="credit_score",
            distribution={
                "300-579": 0.08,  # Poor
                "580-659": 0.12,  # Fair
                "660-724": 0.20,  # Good
                "725-759": 0.22,  # Very Good
                "760-900": 0.38,  # Excellent
            },
            source="Equifax Canada Consumer Credit Trends, 2024",
            year=2024,
        )

    def _load_product_distributions(self):
        """Product penetration rates (CBA/Big 5 reports)."""
        self._constraints["product_penetration"] = DistributionConstraint(
            name="Product Penetration (% of banking customers)",
            dimension="products_held",
            distribution={
                "chequing": 0.95,
                "savings": 0.72,
                "credit_card": 0.83,
                "tfsa": 0.57,
                "rrsp": 0.46,
                "mortgage": 0.28,
                "heloc": 0.12,
                "gic": 0.15,
                "investment_account": 0.22,
                "fhsa": 0.04,
                "resp": 0.14,
                "insurance_life": 0.31,
                "insurance_home": 0.42,
                "insurance_auto": 0.55,
            },
            source="Canadian Bankers Association Financial Statistics 2024",
            year=2024,
        )

        self._constraints["products_per_customer"] = DistributionConstraint(
            name="Products Per Customer Distribution",
            dimension="products_per_household",
            distribution={
                "1-2": 0.25,
                "3-4": 0.35,
                "5-6": 0.25,
                "7+": 0.15,
            },
            source="Big 5 Bank Average Cross-Sell Metrics, 2024",
            year=2024,
        )

    def _load_digital_adoption(self):
        """Digital banking adoption (CBA Digital Banking Survey)."""
        self._constraints["digital_adoption"] = DistributionConstraint(
            name="Digital Banking Adoption",
            dimension="digital_adoption",
            distribution={
                "digital_first": 0.52,  # Mobile/online primary
                "hybrid": 0.35,  # Mix of digital and branch
                "branch_preferred": 0.13,  # Branch primary
            },
            source="CBA Digital Banking Survey, 2024",
            year=2024,
        )

        self._constraints["primary_channel"] = DistributionConstraint(
            name="Primary Banking Channel",
            dimension="primary_channel",
            distribution={
                "mobile": 0.45,
                "online": 0.28,
                "branch": 0.18,
                "telephone": 0.09,
            },
            source="CBA Digital Banking Survey, 2024",
            year=2024,
        )

    def _load_regulatory_parameters(self):
        """OSFI and regulatory constraints."""
        self._regulatory = {
            # OSFI B-20 Stress Test (qualifying rate)
            "stress_test_rate": 5.25,  # Current qualifying rate floor
            "stress_test_buffer": 2.0,  # Contract rate + 2%
            # AML thresholds (FINTRAC)
            "large_cash_threshold_cad": 10_000,
            "eft_threshold_cad": 10_000,
            "casino_threshold_cad": 10_000,
            # CMHC insurance thresholds
            "insured_mortgage_max": 1_000_000,
            "min_down_payment_pct_under_500k": 0.05,
            "min_down_payment_pct_500k_1m": 0.10,
            # GDS/TDS ratios
            "max_gds_ratio": 0.39,
            "max_tds_ratio": 0.44,
            # Credit score minimums for products
            "min_credit_score_prime_mortgage": 680,
            "min_credit_score_credit_card": 600,
            "min_credit_score_heloc": 650,
        }

    # --- Public API ---

    def get_constraint(self, name: str) -> Optional[DistributionConstraint]:
        """Get a specific distribution constraint by name."""
        return self._constraints.get(name)

    def get_all_constraints(self) -> Dict[str, DistributionConstraint]:
        """Get all distribution constraints."""
        return dict(self._constraints)

    def get_regulatory_params(self) -> Dict[str, Any]:
        """Get regulatory parameters."""
        return dict(self._regulatory)

    def get_income_range_for_segment(self, segment: str) -> Tuple[float, float]:
        """Get realistic income range for a customer segment."""
        ranges = {
            "mass_market": (20_000, 74_999),
            "mass_affluent": (75_000, 149_999),
            "affluent": (150_000, 499_999),
            "high_net_worth": (500_000, 999_999),
            "ultra_hnw": (1_000_000, 10_000_000),
            "small_business": (50_000, 500_000),
            "commercial": (100_000, 5_000_000),
            "new_to_canada": (25_000, 100_000),
        }
        return ranges.get(segment, (20_000, 150_000))

    def get_credit_score_range_for_segment(self, segment: str) -> Tuple[int, int]:
        """Get realistic credit score range for a customer segment."""
        ranges = {
            "mass_market": (580, 760),
            "mass_affluent": (680, 830),
            "affluent": (720, 870),
            "high_net_worth": (750, 900),
            "ultra_hnw": (780, 900),
            "small_business": (650, 820),
            "commercial": (680, 850),
            "new_to_canada": (300, 700),  # Often no/thin file
        }
        return ranges.get(segment, (580, 800))

    def get_product_likelihood(self, segment: str) -> Dict[str, float]:
        """Get product holding likelihood by segment."""
        base = dict(self._constraints["product_penetration"].distribution)

        # Adjust by segment
        modifiers = {
            "mass_market": {"mortgage": 0.7, "investment_account": 0.5, "heloc": 0.3},
            "mass_affluent": {"mortgage": 1.2, "investment_account": 1.5, "tfsa": 1.2},
            "affluent": {"mortgage": 1.1, "investment_account": 2.5, "heloc": 2.0, "gic": 1.5},
            "high_net_worth": {"investment_account": 3.0, "heloc": 2.5, "insurance_life": 1.8},
            "ultra_hnw": {"investment_account": 3.5, "heloc": 2.0, "insurance_life": 2.5},
            "new_to_canada": {"mortgage": 0.3, "credit_card": 0.6, "tfsa": 0.3, "rrsp": 0.2},
        }

        segment_mods = modifiers.get(segment, {})
        adjusted = {}
        for product, base_rate in base.items():
            modifier = segment_mods.get(product, 1.0)
            adjusted[product] = min(base_rate * modifier, 0.99)  # Cap at 99%

        return adjusted

    def get_fsa_for_province(self, province: str) -> List[str]:
        """Get common Forward Sortation Areas for a province."""
        # First letter of FSA indicates province/region
        fsa_prefixes = {
            "NL": ["A"],
            "NS": ["B"],
            "PE": ["C"],
            "NB": ["E"],
            "QC": ["G", "H", "J"],
            "ON": ["K", "L", "M", "N", "P"],
            "MB": ["R"],
            "SK": ["S"],
            "AB": ["T"],
            "BC": ["V"],
            "NT": ["X"],
            "NU": ["X"],
            "YT": ["Y"],
        }
        prefixes = fsa_prefixes.get(province, ["M"])
        # Generate common FSAs (digit + letter pattern)
        fsas = []
        for prefix in prefixes:
            for digit in range(10):
                for letter in "ABCEGHJKLMNPRSTVWXYZ":  # Valid FSA letters
                    fsas.append(f"{prefix}{digit}{letter}")
                    if len(fsas) >= 50:
                        return fsas
        return fsas

    def build_generation_prompt(
        self,
        data_type: str,
        segment: Optional[str] = None,
        province: Optional[str] = None,
        count: int = 10,
    ) -> str:
        """
        Build a constrained generation prompt for the LLM.

        Returns a prompt that includes Canadian distribution constraints
        so the LLM generates realistic, calibrated data.
        """
        constraints = []

        if data_type == "profiles":
            constraints.append(self._format_profile_constraints(segment, province))
        elif data_type == "transactions":
            constraints.append(self._format_transaction_constraints(segment))

        return "\n\n".join(constraints)

    def _format_profile_constraints(self, segment: Optional[str], province: Optional[str]) -> str:
        """Format profile generation constraints."""
        parts = ["## Canadian FinServ Profile Constraints\n"]

        if segment:
            income_range = self.get_income_range_for_segment(segment)
            credit_range = self.get_credit_score_range_for_segment(segment)
            products = self.get_product_likelihood(segment)
            top_products = sorted(products.items(), key=lambda x: x[1], reverse=True)[:8]

            parts.append(f"**Segment**: {segment}")
            parts.append(f"**Income Range**: ${income_range[0]:,.0f} - ${income_range[1]:,.0f}")
            parts.append(f"**Credit Score Range**: {credit_range[0]} - {credit_range[1]}")
            parts.append(f"**Common Products**: {', '.join(p[0] for p in top_products)}")
        else:
            seg_dist = self._constraints["segment_distribution"]
            parts.append("**Segment Distribution**:")
            for seg, pct in seg_dist.distribution.items():
                parts.append(f"  - {seg}: {pct*100:.1f}%")

        if province:
            parts.append(f"\n**Province**: {province}")
            fsas = self.get_fsa_for_province(province)[:10]
            parts.append(f"**Sample FSAs**: {', '.join(fsas)}")
        else:
            prov_dist = self._constraints["province_distribution"]
            parts.append("\n**Province Distribution**:")
            for prov, pct in sorted(prov_dist.distribution.items(), key=lambda x: -x[1])[:5]:
                parts.append(f"  - {prov}: {pct*100:.1f}%")

        age_dist = self._constraints["age_distribution"]
        parts.append("\n**Age Distribution (18+)**:")
        for age_band, pct in age_dist.distribution.items():
            parts.append(f"  - {age_band}: {pct*100:.0f}%")

        digital = self._constraints["digital_adoption"]
        parts.append("\n**Digital Adoption**:")
        for channel, pct in digital.distribution.items():
            parts.append(f"  - {channel}: {pct*100:.0f}%")

        return "\n".join(parts)

    def _format_transaction_constraints(self, segment: Optional[str]) -> str:
        """Format transaction generation constraints."""
        reg = self._regulatory
        parts = ["## Canadian Transaction Constraints\n"]

        parts.append("**FINTRAC Reporting Thresholds**:")
        parts.append(f"  - Large cash transaction: ${reg['large_cash_threshold_cad']:,}")
        parts.append(f"  - EFT reporting: ${reg['eft_threshold_cad']:,}")

        parts.append("\n**AML Red Flag Patterns**:")
        parts.append("  - Structuring: Multiple transactions just under $10,000")
        parts.append("  - Rapid movement: Funds in and out within 24-48 hours")
        parts.append("  - Geographic risk: Transactions to/from high-risk jurisdictions")
        parts.append("  - Unusual volume: 3x+ baseline transaction volume")
        parts.append("  - Round amounts: Repeated exact round-number transfers")
        parts.append("  - Dormant reactivation: Inactive >6 months then sudden activity")

        return "\n".join(parts)
