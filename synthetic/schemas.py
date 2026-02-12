#!/usr/bin/env python3
"""
Synthetic Data Schemas — Dataclasses for Canadian FinServ synthetic data.

Defines the core data models for:
- CustomerProfile: Demographics + financial behavior
- Transaction: Individual transaction records
- GenerationRequest: Configuration for generation runs
- GenerationResult: Output from generation with quality metadata
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Province(str, Enum):
    """Canadian provinces and territories."""

    AB = "AB"
    BC = "BC"
    MB = "MB"
    NB = "NB"
    NL = "NL"
    NS = "NS"
    NT = "NT"
    NU = "NU"
    ON = "ON"
    PE = "PE"
    QC = "QC"
    SK = "SK"
    YT = "YT"


class CustomerSegment(str, Enum):
    """Bank customer segments aligned with Big 5 segmentation."""

    MASS_MARKET = "mass_market"  # <$75K income
    MASS_AFFLUENT = "mass_affluent"  # $75K-$150K
    AFFLUENT = "affluent"  # $150K-$500K
    HIGH_NET_WORTH = "high_net_worth"  # $500K-$1M
    ULTRA_HNW = "ultra_hnw"  # >$1M
    SMALL_BUSINESS = "small_business"
    COMMERCIAL = "commercial"
    NEW_TO_CANADA = "new_to_canada"


class ProductType(str, Enum):
    """Canadian financial products."""

    CHEQUING = "chequing"
    SAVINGS = "savings"
    TFSA = "tfsa"
    RRSP = "rrsp"
    FHSA = "fhsa"
    RESP = "resp"
    GIC = "gic"
    MORTGAGE = "mortgage"
    HELOC = "heloc"
    CREDIT_CARD = "credit_card"
    PERSONAL_LOAN = "personal_loan"
    AUTO_LOAN = "auto_loan"
    INVESTMENT_ACCOUNT = "investment_account"
    INSURANCE_LIFE = "insurance_life"
    INSURANCE_HOME = "insurance_home"
    INSURANCE_AUTO = "insurance_auto"


class TransactionType(str, Enum):
    """Transaction categories."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    BILL_PAYMENT = "bill_payment"
    E_TRANSFER = "e_transfer"
    WIRE_DOMESTIC = "wire_domestic"
    WIRE_INTERNATIONAL = "wire_international"
    POS_PURCHASE = "pos_purchase"
    ONLINE_PURCHASE = "online_purchase"
    ATM = "atm"
    MORTGAGE_PAYMENT = "mortgage_payment"
    INVESTMENT_CONTRIBUTION = "investment_contribution"


class RiskFlag(str, Enum):
    """AML/KYC risk indicators for transaction data."""

    NONE = "none"
    STRUCTURING = "structuring"  # Just under $10K threshold
    RAPID_MOVEMENT = "rapid_movement"  # In-and-out pattern
    GEOGRAPHIC_RISK = "geographic_risk"  # High-risk jurisdiction
    UNUSUAL_VOLUME = "unusual_volume"  # Spike vs baseline
    ROUND_AMOUNTS = "round_amounts"  # Suspicious round numbers
    DORMANT_REACTIVATION = "dormant_reactivation"  # Dormant account suddenly active
    THIRD_PARTY = "third_party"  # Third-party deposits


@dataclass
class CustomerProfile:
    """Synthetic Canadian financial services customer profile."""

    # Identity (synthetic — no real PII)
    profile_id: str
    age: int
    province: str  # Province enum value
    fsa: str  # Forward Sortation Area (first 3 chars of postal code)
    segment: str  # CustomerSegment enum value

    # Financial
    annual_income: float
    household_income: float
    credit_score: int  # Equifax/TransUnion range (300-900 in Canada)
    products_held: List[str]  # ProductType enum values
    total_deposits: float
    total_credit_outstanding: float

    # Behavioral
    digital_adoption: str  # "digital_first", "hybrid", "branch_preferred"
    primary_channel: str  # "mobile", "online", "branch", "telephone"
    tenure_years: float  # Years as customer
    products_per_household: int

    # Metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_version: str = "1.0"
    quality_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "profile_id": self.profile_id,
            "age": self.age,
            "province": self.province,
            "fsa": self.fsa,
            "segment": self.segment,
            "annual_income": self.annual_income,
            "household_income": self.household_income,
            "credit_score": self.credit_score,
            "products_held": self.products_held,
            "total_deposits": self.total_deposits,
            "total_credit_outstanding": self.total_credit_outstanding,
            "digital_adoption": self.digital_adoption,
            "primary_channel": self.primary_channel,
            "tenure_years": self.tenure_years,
            "products_per_household": self.products_per_household,
            "generated_at": self.generated_at,
            "generation_version": self.generation_version,
            "quality_score": self.quality_score,
        }


@dataclass
class Transaction:
    """Synthetic transaction record."""

    transaction_id: str
    profile_id: str  # Links to CustomerProfile
    timestamp: str
    transaction_type: str  # TransactionType enum value
    amount: float
    currency: str  # "CAD", "USD", etc.
    merchant_category: Optional[str] = None
    counterparty_institution: Optional[str] = None
    is_international: bool = False
    country_code: Optional[str] = None  # ISO 3166-1 alpha-2
    risk_flag: str = "none"  # RiskFlag enum value
    risk_score: float = 0.0  # 0.0-1.0

    # Metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    quality_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "transaction_id": self.transaction_id,
            "profile_id": self.profile_id,
            "timestamp": self.timestamp,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "currency": self.currency,
            "merchant_category": self.merchant_category,
            "counterparty_institution": self.counterparty_institution,
            "is_international": self.is_international,
            "country_code": self.country_code,
            "risk_flag": self.risk_flag,
            "risk_score": self.risk_score,
            "generated_at": self.generated_at,
            "quality_score": self.quality_score,
        }


@dataclass
class GenerationRequest:
    """Request parameters for synthetic data generation."""

    # What to generate
    data_type: str  # "profiles", "transactions", "scenarios"
    count: int = 100
    segment: Optional[str] = None  # Target customer segment
    province: Optional[str] = None  # Target province
    scenario: Optional[str] = None  # For scenario generation

    # Constraints
    income_range: Optional[tuple] = None  # (min, max)
    age_range: Optional[tuple] = None  # (min, max)
    risk_profile: Optional[str] = None  # "low", "medium", "high" for AML scenarios
    include_risk_flags: bool = False  # Generate AML risk indicators

    # Quality
    min_quality_score: float = 0.7  # Minimum quality threshold
    use_knowledge_base: bool = True  # Apply Canadian distribution constraints

    # Output
    output_format: str = "jsonl"  # "jsonl", "csv", "json"
    output_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data_type": self.data_type,
            "count": self.count,
            "segment": self.segment,
            "province": self.province,
            "scenario": self.scenario,
            "income_range": self.income_range,
            "age_range": self.age_range,
            "risk_profile": self.risk_profile,
            "include_risk_flags": self.include_risk_flags,
            "min_quality_score": self.min_quality_score,
            "use_knowledge_base": self.use_knowledge_base,
            "output_format": self.output_format,
            "output_path": self.output_path,
        }


@dataclass
class GenerationResult:
    """Result from a synthetic data generation run."""

    request: GenerationRequest
    records_generated: int
    records_passed_quality: int
    records_rejected: int
    average_quality_score: float
    quality_distribution: Dict[str, int]  # quality bucket -> count
    generation_time_seconds: float
    output_path: Optional[str] = None
    flywheel_id: Optional[str] = None  # For outcome tracking

    def summary(self) -> str:
        """Human-readable summary."""
        pass_rate = (
            self.records_passed_quality / self.records_generated * 100
            if self.records_generated > 0
            else 0
        )
        return (
            f"Generated {self.records_generated} {self.request.data_type} "
            f"| {self.records_passed_quality} passed quality ({pass_rate:.1f}%) "
            f"| Avg quality: {self.average_quality_score:.3f} "
            f"| Time: {self.generation_time_seconds:.1f}s"
        )
