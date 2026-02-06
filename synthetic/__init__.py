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

__version__ = "0.2.0"

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
from .knowledge_base import CanadianFinServKB
from .generator import SyntheticGenerator
from .quality import SyntheticQualityTracker
from .constraints import ConstraintEngine, ConstraintReport, ConstraintResult
from .risk_validator import RiskValidator, RiskReport, RuleResult, AdversarialResult
from .flywheel import Flywheel, FlywheelReport, LayerResult

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
