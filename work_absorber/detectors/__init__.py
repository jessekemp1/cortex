"""
Signal detectors for the Work Absorber system.

Each detector extracts work signals from a specific source:
- GitDetector: Git commits
- DocDetector: Completion documents (*_COMPLETE.md)
- BatchDetector: Batch API results
"""

from .base import SignalDetector
from .batch_detector import BatchResultDetector
from .doc_detector import CompletionDocDetector
from .git_detector import GitSignalDetector

__all__ = [
    "SignalDetector",
    "GitSignalDetector",
    "CompletionDocDetector",
    "BatchResultDetector",
]
