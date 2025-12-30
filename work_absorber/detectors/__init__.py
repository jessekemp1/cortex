"""
Signal detectors for the Work Absorber system.

Each detector extracts work signals from a specific source:
- GitDetector: Git commits
- DocDetector: Completion documents (*_COMPLETE.md)
- BatchDetector: Batch API results
"""

from .base import SignalDetector
from .git_detector import GitSignalDetector
from .doc_detector import CompletionDocDetector
from .batch_detector import BatchResultDetector

__all__ = [
    "SignalDetector",
    "GitSignalDetector",
    "CompletionDocDetector",
    "BatchResultDetector",
]
