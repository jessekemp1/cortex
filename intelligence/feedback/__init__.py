"""
Cortex Feedback System - Implicit and explicit feedback collection

Implements automated tracking of user interactions with recommendations
to enable learning from implicit signals (follows, ignores, overrides).
Part of AI Engineering Improvements Phase 2.
"""

from cortex.intelligence.feedback.implicit_collector import (
    ImplicitFeedbackCollector,
    ImplicitSignal,
)

__all__ = [
    "ImplicitFeedbackCollector",
    "ImplicitSignal",
]
