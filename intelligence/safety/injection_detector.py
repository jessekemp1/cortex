"""
Prompt Injection Detection

Detects common prompt injection patterns and attempts to manipulate system behavior.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class InjectionSeverity(Enum):
    """Severity levels for injection attempts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class InjectionAttempt:
    """Details of a detected injection attempt."""

    pattern: str
    matched_text: str
    severity: InjectionSeverity
    timestamp: datetime
    query: str

    def to_dict(self):
        """Convert to dictionary for logging."""
        return {
            "pattern": self.pattern,
            "matched_text": self.matched_text,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query[:100] + "..." if len(self.query) > 100 else self.query,
        }


class InjectionDetector:
    """Detects prompt injection attempts in user queries."""

    # Common injection patterns with severity levels
    INJECTION_PATTERNS = [
        # Critical: Direct instruction override
        (
            r"\bignore\s+(all\s+)?(previous\s+|prior\s+|above\s+)?(instructions?|prompts?|rules?)",
            InjectionSeverity.CRITICAL,
        ),
        (
            r"\bdisregard\s+(your\s+|the\s+|all\s+)?(rules?|guidelines?|instructions?)",
            InjectionSeverity.CRITICAL,
        ),
        (r"\bforget\s+(everything|all|previous|your)\b", InjectionSeverity.CRITICAL),
        (r"\bnew\s+instructions?:\s", InjectionSeverity.CRITICAL),
        (r"\bsystem\s+prompt\b", InjectionSeverity.HIGH),
        # High: Role manipulation
        (r"\byou are now (a |an )?(?!cortex)", InjectionSeverity.HIGH),
        (r"\bpretend (you are|to be|you're)", InjectionSeverity.HIGH),
        (r"\bact as (if|though|a |an )", InjectionSeverity.HIGH),
        (r"\broleplay as\b", InjectionSeverity.HIGH),
        (r"\bsimulate (being|a |an )", InjectionSeverity.HIGH),
        # High: Information extraction
        (r"\breveal (your|the) (prompt|instructions?|system message)", InjectionSeverity.HIGH),
        (r"\bshow me (your|the) (prompt|instructions?|rules?)", InjectionSeverity.HIGH),
        (r"\bwhat are your (instructions?|rules?|prompts?)", InjectionSeverity.HIGH),
        (r"\brepeat (your|the) (instructions?|prompt|rules?)", InjectionSeverity.HIGH),
        # Medium: Constraint bypass attempts
        (r"\bwithout (any )?restrictions?\b", InjectionSeverity.MEDIUM),
        (r"\bbypass (the |your )?safety\b", InjectionSeverity.MEDIUM),
        (r"\bignore (the |your )?limitations?\b", InjectionSeverity.MEDIUM),
        (r"\bunrestricted mode\b", InjectionSeverity.MEDIUM),
        (r"\bdeveloper mode\b", InjectionSeverity.MEDIUM),
        (r"\bjailbreak\b", InjectionSeverity.MEDIUM),
        # Medium: End-of-instruction markers
        (r"\[/?INST\]", InjectionSeverity.MEDIUM),
        (r"<\|im_start\|>", InjectionSeverity.MEDIUM),
        (r"<\|im_end\|>", InjectionSeverity.MEDIUM),
        (r"###\s*(System|User|Assistant)", InjectionSeverity.MEDIUM),
        # Low: Suspicious patterns
        (r"\boverride (mode|settings?|defaults?)", InjectionSeverity.LOW),
        (r"\bchange your (behavior|personality|role)", InjectionSeverity.LOW),
        (r"\bstop being\b", InjectionSeverity.LOW),
    ]

    def __init__(self, log_path: Optional[Path] = None):
        """
        Initialize injection detector.

        Args:
            log_path: Path to log injection attempts. Defaults to ~/.cortex/security.log
        """
        self.logger = logging.getLogger(__name__)
        self.log_path = log_path or Path.home() / ".cortex" / "security.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Compile patterns for efficiency
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), severity)
            for pattern, severity in self.INJECTION_PATTERNS
        ]

    def detect(self, query: str) -> Optional[InjectionAttempt]:
        """
        Detect injection attempts in a query.

        Args:
            query: User query to check

        Returns:
            InjectionAttempt if detected, None otherwise
        """
        for pattern_re, severity in self.compiled_patterns:
            match = pattern_re.search(query)
            if match:
                attempt = InjectionAttempt(
                    pattern=pattern_re.pattern,
                    matched_text=match.group(0),
                    severity=severity,
                    timestamp=datetime.now(),
                    query=query,
                )
                self._log_attempt(attempt)
                return attempt

        return None

    def _log_attempt(self, attempt: InjectionAttempt):
        """Log injection attempt to file and logger."""
        # Log to Python logger
        self.logger.warning(
            f"Injection attempt detected: {attempt.severity.value} - "
            f"Pattern: {attempt.pattern} - Matched: {attempt.matched_text}"
        )

        # Log to security file
        try:
            with open(self.log_path, "a") as f:
                import json

                f.write(json.dumps(attempt.to_dict()) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to log injection attempt: {e}")

    def is_safe(self, query: str) -> bool:
        """
        Check if query is safe (no injection detected).

        Args:
            query: User query to check

        Returns:
            True if safe, False if injection detected
        """
        return self.detect(query) is None

    def get_severity_score(self, query: str) -> float:
        """
        Get severity score for a query.

        Args:
            query: User query to check

        Returns:
            Score from 0.0 (safe) to 1.0 (critical injection)
        """
        attempt = self.detect(query)
        if not attempt:
            return 0.0

        severity_scores = {
            InjectionSeverity.LOW: 0.25,
            InjectionSeverity.MEDIUM: 0.5,
            InjectionSeverity.HIGH: 0.75,
            InjectionSeverity.CRITICAL: 1.0,
        }

        return severity_scores.get(attempt.severity, 0.0)
