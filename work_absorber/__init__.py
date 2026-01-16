"""
Work Absorber - Automatically track and consolidate work progress across all projects.

Usage:
    from cortex.work_absorber import WorkAbsorber

    absorber = WorkAbsorber()
    report = absorber.absorb()
    print(f"Detected {report.signals_detected} work signals")
"""

from .absorber import WorkAbsorber
from .correlator import DriftAnalyzer, PlanCorrelator
from .models import (
    AbsorptionReport,
    DriftType,
    PlanDrift,
    ProgressEntry,
    WorkItem,
    WorkSignal,
    WorkSignalType,
    WorkStatus,
)
from .storage import WorkAbsorberStorage

__all__ = [
    # Core
    "WorkAbsorber",
    "WorkAbsorberStorage",
    "PlanCorrelator",
    "DriftAnalyzer",
    # Models
    "WorkSignal",
    "WorkItem",
    "ProgressEntry",
    "PlanDrift",
    "AbsorptionReport",
    # Enums
    "WorkSignalType",
    "WorkStatus",
    "DriftType",
]
