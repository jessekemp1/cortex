"""
Pupil Behavioral Schemas — Dataclasses for agent-based behavioral data.

This module extends the core SynthFinServ schemas with behavioral and temporal
models for agent-based simulation and prediction.
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

    MASS_MARKET = "mass_market"
    MASS_AFFLUENT = "mass_affluent"
    AFFLUENT = "affluent"
    HIGH_NET_WORTH = "high_net_worth"
    ULTRA_HNW = "ultra_hnw"
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


class AgentState(str, Enum):
    """Behavioral lifecycle states for financial customers."""

    ONBOARDING = "onboarding"  # < 6 months with institution
    ACTIVE = "active"  # Primary banking customer
    TRANSITIONING = "transitioning"  # Considering changes
    AT_RISK = "at_risk"  # Showing churn signals
    CHURNED = "churned"  # Left primary institution
    REACTIVATED = "reactivated"  # Returned after churn


class BehavioralActionType(str, Enum):
    """Types of customer actions in behavioral sequences."""

    PRODUCT_ADOPTION = "product_adoption"  # New product
    PRODUCT_SWITCH = "product_switch"  # Switch provider
    PRODUCT_CANCELLATION = "product_cancellation"  # Drop product
    CHANNEL_USAGE = "channel_usage"  # Banking channel
    TRANSACTION = "transaction"  # Financial activity
    GOAL_UPDATE = "goal_update"  # Change priorities
    REVIEW_COMPLETED = "review_completed"  # Service interaction
    COMPLAINT = "complaint"  # Negative feedback
    REFERRAL = "referral"  # Word of mouth


class GoalType(str, Enum):
    """Financial goals that drive customer behavior."""

    SAVE_DOWN_PAYMENT = "save_down_payment"
    PAY_OFF_DEBT = "pay_off_debt"
    BUILD_EMERGENCY_FUND = "build_emergency_fund"
    RETIREMENT_SAVINGS = "retirement_savings"
    CHILD_EDUCATION = "child_education"
    START_BUSINESS = "start_business"
    TRAVEL = "travel"
    HOME_RENOVATION = "home_renovation"
    MAXIMIZE_RETURNS = "maximize_returns"
    MINIMIZE_FEES = "minimize_fees"


@dataclass
class BehavioralAction:
    """Single action in a customer's behavioral sequence."""

    action_type: str  # BehavioralActionType enum value
    timestamp: str
    amount: Optional[float] = None  # Monetary value if applicable
    product_involved: Optional[str] = None  # ProductType if applicable
    institution_involved: Optional[str] = None  # Institution name
    reasoning: Optional[str] = None  # LLM reasoning trail (optional)
    confidence: float = 1.0  # Model confidence in action (0.0-1.0)

    # Impact metrics
    satisfaction_impact: float = 0.0  # -1.0 to +1.0
    financial_impact: float = 0.0  # Monthly $ impact
    risk_impact: float = 0.0  # AML risk score change

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type,
            "timestamp": self.timestamp,
            "amount": self.amount,
            "product_involved": self.product_involved,
            "institution_involved": self.institution_involved,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "satisfaction_impact": self.satisfaction_impact,
            "financial_impact": self.financial_impact,
            "risk_impact": self.risk_impact,
        }


@dataclass
class Goal:
    type: str  # GoalType enum value
    priority: float  # 0.0-1.0, higher = more important
    progress: float  # 0.0-1.0, current completion
    monthly_target: float  # $ target per month
    deadline: Optional[str]  # ISO date or None
    satisfaction: float  # 0.0-1.0, satisfaction with progress

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "priority": self.priority,
            "progress": self.progress,
            "monthly_target": self.monthly_target,
            "deadline": self.deadline,
            "satisfaction": self.satisfaction,
        }

    @property
    def is_achieved(self) -> bool:
        """Check if goal is achieved."""
        return self.progress >= 1.0

    def update_progress(self, amount: float, month: str):
        """Update progress based on savings contribution."""
        self.progress = min(1.0, self.progress + amount / self.monthly_target)
        # Update satisfaction based on monthly performance
        monthly_actual = amount
        if monthly_actual >= self.monthly_target * 0.9:
            self.satisfaction = min(1.0, self.satisfaction + 0.1)
        elif monthly_actual < self.monthly_target * 0.5:
            self.satisfaction = max(0.0, self.satisfaction - 0.2)


@dataclass
class BehavioralProfile:
    """Behavioral profile combining customer data with simulated actions."""

    profile: CustomerProfile
    behavioral_actions: List[BehavioralAction] = field(default_factory=list)
    goals: List[Goal] = field(default_factory=list)


@dataclass
class BehavioralSequence:
    """Time-ordered sequence of behavioral actions for one customer."""

    profile_id: str
    actions: List[BehavioralAction] = field(default_factory=list)


@dataclass
class PupilRequest:
    """Request for Pupil behavioral generation/simulation."""

    # Agent creation
    agent_count: int = 100
    data_sources: List[str] = field(default_factory=lambda: ["census", "cba"])
    include_reasoning: bool = False  # LLM enrichment

    # Behavioral parameters
    simulation_months: int = 12
    scenario_events: List[Dict[str, Any]] = field(default_factory=list)
    seed: Optional[int] = None

    # Market events
    rate_scenarios: List[float] = field(default_factory=list)  # BoC rate changes
    competitive_events: List[Dict[str, Any]] = field(default_factory=list)
    macro_events: List[Dict[str, Any]] = field(default_factory=list)

    # Quality validation
    validate_statistics: bool = True
    validate_behavior: bool = True
    validate_privacy: bool = True

    # Output
    include_reasoning_trails: bool = False  # LLM reasoning logs
    temporal_granularity: str = "monthly"  # monthly, quarterly

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_count": self.agent_count,
            "data_sources": self.data_sources,
            "include_reasoning": self.include_reasoning,
            "simulation_months": self.simulation_months,
            "scenario_events": self.scenario_events,
            "seed": self.seed,
            "rate_scenarios": self.rate_scenarios,
            "competitive_events": self.competitive_events,
            "macro_events": self.macro_events,
            "validate_statistics": self.validate_statistics,
            "validate_behavior": self.validate_behavior,
            "validate_privacy": self.validate_privacy,
            "include_reasoning_trails": self.include_reasoning_trails,
            "temporal_granularity": self.temporal_granularity,
        }


@dataclass
class PupilResult:
    """Result from Pupil behavioral generation/simulation."""

    request: PupilRequest
    behavioral_profiles: List[BehavioralProfile]
    behavioral_sequences: List[BehavioralSequence]
    simulation_metadata: Dict[str, Any]

    # Quality scores
    generation_time_seconds: float
    behavioral_fidelity_score: float  # L8 score
    temporal_coherence_score: float  # L9 score
    statistical_fidelity_score: float  # L2 score
    privacy_score: float  # L7 score

    # Validation results
    flywheel_id: str
    validation_passed: bool
    validation_reports: Dict[str, Any]  # L8-L9 reports

    def summary(self) -> str:
        """Human-readable summary."""
        profile_count = len(self.behavioral_profiles)
        sequence_count = len(self.behavioral_sequences)
        avg_quality = (
            self.behavioral_fidelity_score
            + self.temporal_coherence_score
            + self.statistical_fidelity_score
            + self.privacy_score
        ) / 4

        return (
            f"Generated {profile_count} behavioral profiles "
            f"| {sequence_count} behavioral sequences "
            f"| Avg quality: {avg_quality:.3f} "
            f"| Validation: {'PASS' if self.validation_passed else 'FAIL'} "
            f"| Time: {self.generation_time_seconds:.1f}s"
        )
