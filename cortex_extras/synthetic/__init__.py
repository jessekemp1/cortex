#!/usr/bin/env python3
"""
Cortex Synthetic Data Engine — Canadian FinServ synthetic dataset generation.

Generates quality-validated, outcome-calibrated synthetic data for:
- Customer profiles (demographics + financial behavior)
- Transaction data (normal + AML/KYC risk patterns)
- Market scenarios (future — competitive intelligence)

Unique approach: Cortex's outcome flywheel means synthetic data
improves from real usage feedback, not just statistical plausibility.
"""

__version__ = "0.4.0"

from .constraints import ConstraintEngine, ConstraintReport, ConstraintResult
from .discriminator import Discriminator, DiscriminatorReport, FeatureImportance
from .flywheel import Flywheel, FlywheelReport, LayerResult
from .generator import SyntheticGenerator
from .knowledge_base import CanadianFinServKB
from .privacy import PrivacyEngine, PrivacyReport, RecordPrivacy
from .quality import SyntheticQualityTracker
from .risk_validator import AdversarialResult, RiskReport, RiskValidator, RuleResult
from .schemas import (
    CustomerProfile,
    CustomerSegment,
    GenerationRequest,
    GenerationResult,
    ProductType,
    Province,
    RiskFlag,
    Transaction,
    TransactionType,
)
from .tstr import TaskResult, TSTRFramework, TSTRReport

__all__ = [
    # Core
    "SyntheticGenerator",
    "CanadianFinServKB",
    "SyntheticQualityTracker",
    # Phase 2: Flywheel
    "ConstraintEngine",
    "ConstraintReport",
    "ConstraintResult",
    "RiskValidator",
    "RiskReport",
    "RuleResult",
    "AdversarialResult",
    "Flywheel",
    "FlywheelReport",
    "LayerResult",
    # Phase 3: Discriminator + TSTR
    "Discriminator",
    "DiscriminatorReport",
    "FeatureImportance",
    "TSTRFramework",
    "TSTRReport",
    "TaskResult",
    # Phase 4: Privacy
    "PrivacyEngine",
    "PrivacyReport",
    "RecordPrivacy",
    # Schemas
    "CustomerProfile",
    "Transaction",
    "GenerationRequest",
    "GenerationResult",
    # Enums
    "Province",
    "CustomerSegment",
    "ProductType",
    "TransactionType",
    "RiskFlag",
]
