"""
Cortex Enforcement System

ACTIVE prevention of known anti-patterns.
Does not rely on memory or promises.
Cannot be bypassed.
"""

from .testing_gate import DeliveryGate, TestingEnforcer

__all__ = [
    "TestingEnforcer",
    "DeliveryGate",
]

# Future: pattern_detector, evidence_validator will be added
