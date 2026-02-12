"""
Retry logic and failure escalation system for Cortex orchestration.

Provides:
- Automatic failure classification
- Intelligent retry strategies
- Exponential backoff with jitter
- Human escalation for permanent failures
- Database persistence of retry state

Example usage in verifier.py:

    from .retry_handler import RetryHandler

    try:
        run_tests()
    except ValidationFailure as e:
        retry = RetryHandler(self.db, self)
        decision = retry.handle_failure(task, str(e), task.phase)

        if decision.should_retry:
            # Schedule retry
            return VerificationResult(
                passed=False,
                evidence={
                    "retry_scheduled": True,
                    "delay_seconds": decision.delay_seconds,
                    "retry_count": decision.retry_count,
                    "strategy": decision.strategy.value
                }
            )
        elif decision.escalate:
            # Human intervention required
            logger.error(f"Task {task.id} escalated: {decision.reason}")
            raise
        else:
            # Permanent failure, no retry
            raise
"""

import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from .models import Task, TaskPhase, TraceEvent, TraceEventType, create_task_event

if TYPE_CHECKING:
    from .database import OrchestrationDatabase
    from .verifier import PhaseVerifier

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Strategy for retrying failed tasks."""

    IMMEDIATE = "immediate"  # Retry immediately (for transient errors)
    EXPONENTIAL = "exponential"  # Exponential backoff (for resource issues)
    DEPENDENCY_WAIT = "dependency_wait"  # Wait for dependencies (long delay)
    NO_RETRY = "no_retry"  # Don't retry (permanent failures)


class FailureType(str, Enum):
    """Classification of failure types for intelligent retry decisions."""

    TRANSIENT = "transient"  # Temporary network/service issues
    RESOURCE = "resource"  # Resource exhaustion (memory, disk, quota)
    VALIDATION = "validation"  # Test/lint failures (requires code fix)
    DEPENDENCY = "dependency"  # Blocked by other tasks
    PERMANENT = "permanent"  # Unrecoverable errors (auth, invalid input)
    UNKNOWN = "unknown"  # Cannot classify


@dataclass
class RetryConfig:
    """
    Configuration for task retry behavior.

    Persisted in database to track retry state across executions.
    """

    # Retry limits
    max_retries: int = 3
    current_retry_count: int = 0

    # Strategy
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL

    # Timing (seconds)
    base_delay_seconds: int = 60
    backoff_multiplier: float = 2.0
    max_delay_seconds: int = 3600  # 1 hour max

    # Failure tracking
    last_retry_at: Optional[datetime] = None
    failure_type: Optional[FailureType] = None

    # Escalation
    escalated: bool = False
    escalation_reason: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for database storage."""
        return {
            "max_retries": self.max_retries,
            "current_retry_count": self.current_retry_count,
            "strategy": self.strategy.value,
            "base_delay_seconds": self.base_delay_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "max_delay_seconds": self.max_delay_seconds,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryConfig":
        """Deserialize from database."""
        # Remove task_id (not part of dataclass)
        data = dict(data)  # Make a copy
        data.pop("task_id", None)

        # Convert enums
        if data.get("strategy"):
            data["strategy"] = RetryStrategy(data["strategy"])
        if data.get("failure_type"):
            data["failure_type"] = FailureType(data["failure_type"])

        # Convert datetimes
        for field_name in ["last_retry_at", "created_at", "updated_at"]:
            if data.get(field_name):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**data)


@dataclass
class RetryDecision:
    """
    Decision on whether and how to retry a failed task.

    Returned by RetryHandler.handle_failure() to guide orchestration logic.
    """

    should_retry: bool
    delay_seconds: int
    failure_type: FailureType
    strategy: RetryStrategy
    retry_count: int
    reason: str
    escalate: bool = False
    escalation_reason: Optional[str] = None


class FailureClassifier:
    """
    Classifies failures based on error messages and context.

    Uses pattern matching to determine failure type and appropriate retry strategy.
    Similar to pattern matching in verifier.py:452.
    """

    # Error patterns for each failure type
    TRANSIENT_PATTERNS = [
        r"timeout",
        r"timed out",
        r"connection.*reset",
        r"connection.*refused",
        r"connection.*closed",
        r"network.*unreachable",
        r"temporary failure",
        r"rate limit",
        r"too many requests",
        r"502 bad gateway",
        r"503 service unavailable",
        r"504 gateway timeout",
        r"retry",
        r"transient",
    ]

    RESOURCE_PATTERNS = [
        r"out of memory",
        r"memory.*exhausted",
        r"disk.*full",
        r"no space left",
        r"quota exceeded",
        r"resource.*exhausted",
        r"capacity.*exceeded",
        r"too many.*open files",
        r"cannot allocate memory",
    ]

    VALIDATION_PATTERNS = [
        r"test.*failed",
        r"tests? failed",
        r"assertion.*error",
        r"assertion.*failed",
        r"lint.*error",
        r"syntax.*error",
        r"type.*error",
        r"import.*error",
        r"module.*not found",
        r"failed.*validation",
        r"validation.*failed",
        r"check.*failed",
    ]

    DEPENDENCY_PATTERNS = [
        r"blocked by",
        r"dependency.*not.*met",
        r"waiting.*for",
        r"prerequisite.*failed",
        r"depends on",
        r"missing.*dependency",
    ]

    PERMANENT_PATTERNS = [
        r"unauthorized",
        r"forbidden",
        r"access denied",
        r"permission denied",
        r"authentication.*failed",
        r"404.*not found",
        r"file.*not found",
        r"cannot be.*null",
        r"required.*missing",
        r"malformed.*request",
        r"invalid.*credentials",
        r"invalid.*api.*key",
    ]

    def classify(self, task: Task, error: str) -> FailureType:
        """
        Classify failure type based on error message.

        Args:
            task: The failed task
            error: Error message or exception text

        Returns:
            FailureType indicating the nature of the failure
        """
        error_lower = error.lower()

        # Check each pattern type (order matters - most specific first)
        if self._matches_any(error_lower, self.PERMANENT_PATTERNS):
            return FailureType.PERMANENT

        if self._matches_any(error_lower, self.VALIDATION_PATTERNS):
            return FailureType.VALIDATION

        if self._matches_any(error_lower, self.DEPENDENCY_PATTERNS):
            return FailureType.DEPENDENCY

        if self._matches_any(error_lower, self.RESOURCE_PATTERNS):
            return FailureType.RESOURCE

        if self._matches_any(error_lower, self.TRANSIENT_PATTERNS):
            return FailureType.TRANSIENT

        # Default to unknown
        return FailureType.UNKNOWN

    def get_strategy(self, failure_type: FailureType) -> RetryStrategy:
        """
        Determine retry strategy based on failure type.

        Args:
            failure_type: Classification of the failure

        Returns:
            Appropriate RetryStrategy for this failure type
        """
        strategy_map = {
            FailureType.TRANSIENT: RetryStrategy.IMMEDIATE,
            FailureType.RESOURCE: RetryStrategy.EXPONENTIAL,
            FailureType.VALIDATION: RetryStrategy.NO_RETRY,
            FailureType.DEPENDENCY: RetryStrategy.DEPENDENCY_WAIT,
            FailureType.PERMANENT: RetryStrategy.NO_RETRY,
            FailureType.UNKNOWN: RetryStrategy.EXPONENTIAL,  # Conservative default
        }
        return strategy_map[failure_type]

    def _matches_any(self, text: str, patterns: list) -> bool:
        """Check if text matches any pattern in the list."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


# Default retry configurations for each failure type
DEFAULT_RETRY_CONFIGS = {
    FailureType.TRANSIENT: RetryConfig(
        max_retries=3,
        strategy=RetryStrategy.IMMEDIATE,
        base_delay_seconds=10,
        backoff_multiplier=1.5,
    ),
    FailureType.RESOURCE: RetryConfig(
        max_retries=3,
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=60,
        backoff_multiplier=2.0,
    ),
    FailureType.DEPENDENCY: RetryConfig(
        max_retries=24,  # Check every 5 minutes for 2 hours
        strategy=RetryStrategy.DEPENDENCY_WAIT,
        base_delay_seconds=300,  # 5 minutes
        backoff_multiplier=1.0,  # No backoff for dependency waits
    ),
    FailureType.VALIDATION: RetryConfig(
        max_retries=0,
        strategy=RetryStrategy.NO_RETRY,
    ),
    FailureType.PERMANENT: RetryConfig(
        max_retries=0,
        strategy=RetryStrategy.NO_RETRY,
    ),
    FailureType.UNKNOWN: RetryConfig(
        max_retries=2,
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=120,
        backoff_multiplier=2.0,
    ),
}


class RetryHandler:
    """
    Handles retry logic and failure escalation for tasks.

    Integrates with PhaseVerifier to provide intelligent retry decisions
    based on failure classification and retry history.
    """

    def __init__(self, db: "OrchestrationDatabase", verifier: Optional["PhaseVerifier"] = None):
        """
        Initialize retry handler.

        Args:
            db: Database for persisting retry state
            verifier: Optional PhaseVerifier for validation context
        """
        self.db = db
        self.verifier = verifier
        self.classifier = FailureClassifier()

    def handle_failure(
        self,
        task: Task,
        error: str,
        phase: TaskPhase,
    ) -> RetryDecision:
        """
        Handle a task failure and determine retry strategy.

        Main entry point for retry logic. Classifies failure, checks retry
        limits, calculates backoff delay, and decides whether to retry or escalate.

        Args:
            task: The failed task
            error: Error message or exception text
            phase: Task phase where failure occurred

        Returns:
            RetryDecision with should_retry, delay, and escalation info
        """
        # Classify the failure
        failure_type = self.classifier.classify(task, error)
        strategy = self.classifier.get_strategy(failure_type)

        # Get or create retry config
        config = self.get_retry_config(task.id)
        if config is None:
            # First failure - create config based on failure type
            config = DEFAULT_RETRY_CONFIGS[failure_type]
            config.failure_type = failure_type
        else:
            # Update config with latest failure info
            config.failure_type = failure_type
            config.strategy = strategy
            config.current_retry_count += 1
            config.updated_at = datetime.now()

        # Check if we should retry
        should_retry = self.should_retry(task, config)

        # Calculate delay if retrying
        delay_seconds = 0
        if should_retry:
            delay_seconds = self.calculate_retry_delay(config)
            config.last_retry_at = datetime.now()

        # Check if escalation needed
        escalate = False
        escalation_reason = None

        if not should_retry and config.current_retry_count >= config.max_retries:
            escalate = True
            escalation_reason = (
                f"Max retries ({config.max_retries}) exceeded for {failure_type.value} failure"
            )
            config.escalated = True
            config.escalation_reason = escalation_reason
        elif failure_type in [FailureType.VALIDATION, FailureType.PERMANENT]:
            escalate = True
            escalation_reason = f"{failure_type.value} failure requires human intervention"
            config.escalated = True
            config.escalation_reason = escalation_reason

        # Save config to database
        self._save_retry_config(task.id, config)

        # Log trace event
        self._log_retry_event(task, config, should_retry, delay_seconds, failure_type, error)

        # Escalate to human if needed
        if escalate:
            self.escalate_to_human(
                task,
                escalation_reason or "Unknown reason",
                {
                    "error": error,
                    "failure_type": failure_type.value,
                    "retry_count": config.current_retry_count,
                    "phase": phase.value,
                },
            )

        return RetryDecision(
            should_retry=should_retry,
            delay_seconds=delay_seconds,
            failure_type=failure_type,
            strategy=strategy,
            retry_count=config.current_retry_count,
            reason=error,
            escalate=escalate,
            escalation_reason=escalation_reason,
        )

    def should_retry(self, task: Task, config: RetryConfig) -> bool:
        """
        Determine if a task should be retried.

        Args:
            task: The failed task
            config: Current retry configuration

        Returns:
            True if task should be retried, False otherwise
        """
        # Check strategy
        if config.strategy == RetryStrategy.NO_RETRY:
            return False

        # Check retry limit
        if config.current_retry_count >= config.max_retries:
            return False

        # Check if already escalated
        if config.escalated:
            return False

        return True

    def calculate_retry_delay(self, config: RetryConfig) -> int:
        """
        Calculate retry delay using exponential backoff with jitter.

        Formula (similar to batch/batch_api_client.py:265-272):
            delay = base_delay * (multiplier ** retry_count)
            jitter = delay * random.uniform(0, 0.2)  # 0-20% jitter
            final_delay = min(delay + jitter, max_delay)

        Args:
            config: Retry configuration with backoff parameters

        Returns:
            Delay in seconds before next retry
        """
        if config.strategy == RetryStrategy.IMMEDIATE:
            # Immediate retry with minimal jitter
            return random.randint(1, 5)

        # Calculate exponential backoff
        delay = config.base_delay_seconds * (config.backoff_multiplier**config.current_retry_count)

        # Add jitter (0-20% of delay)
        jitter = delay * random.uniform(0, 0.2)
        final_delay = delay + jitter

        # Cap at max delay
        final_delay = min(final_delay, config.max_delay_seconds)

        return int(final_delay)

    def escalate_to_human(
        self,
        task: Task,
        reason: str,
        context: Dict[str, Any],
    ) -> None:
        """
        Escalate a task to human for intervention.

        Logs escalation event and marks task for manual review.

        Args:
            task: The task requiring escalation
            reason: Why escalation is needed
            context: Additional context (error, retry count, etc.)
        """
        logger.warning(
            f"Task {task.id} escalated to human: {reason}\n"
            f"Context: {json.dumps(context, indent=2)}"
        )

        # Log trace event
        event = create_task_event(
            event_type=TraceEventType.ERROR_OCCURRED,
            task=task,
            message=f"Task escalated: {reason}",
            details={
                "escalation_reason": reason,
                **context,
            },
        )
        self.db.add_trace_event(event)

    def get_retry_config(self, task_id: str) -> Optional[RetryConfig]:
        """
        Get retry configuration for a task.

        Args:
            task_id: Task identifier

        Returns:
            RetryConfig if exists, None otherwise
        """
        return self.db.get_retry_config(task_id)

    def _save_retry_config(self, task_id: str, config: RetryConfig) -> None:
        """
        Save retry configuration to database.

        Args:
            task_id: Task identifier
            config: Retry configuration to save
        """
        # Check if config exists
        existing = self.db.get_retry_config(task_id)

        if existing is None:
            self.db.create_retry_config(task_id, config)
        else:
            self.db.update_retry_config(task_id, config)

    def _log_retry_event(
        self,
        task: Task,
        config: RetryConfig,
        should_retry: bool,
        delay_seconds: int,
        failure_type: FailureType,
        error: str,
    ) -> None:
        """Log retry decision as trace event."""
        import uuid

        if should_retry:
            message = (
                f"Retry scheduled (attempt {config.current_retry_count + 1}/"
                f"{config.max_retries}) after {delay_seconds}s"
            )
            event_type = TraceEventType.TASK_RETRIED
        else:
            message = f"No retry - {failure_type.value} failure"
            event_type = TraceEventType.ERROR_OCCURRED

        event = TraceEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            task_id=task.id,
            message=message,
            details={
                "failure_type": failure_type.value,
                "strategy": config.strategy.value,
                "retry_count": config.current_retry_count,
                "should_retry": should_retry,
                "delay_seconds": delay_seconds,
                "error_preview": error[:200] if error else "",
            },
            phase=task.phase.value,
        )

        self.db.add_trace_event(event)
