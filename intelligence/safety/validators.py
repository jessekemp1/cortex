"""
Input and Output Validators for Cortex

Validates user inputs and AI outputs to ensure safety and quality.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .injection_detector import InjectionDetector


@dataclass
class ValidationCheck:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, error

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ValidationResult:
    """Result of validation with multiple checks."""

    passed: bool
    checks: List[ValidationCheck]
    validated_value: Optional[Any] = None

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "has_warnings": any(c.severity == "warning" for c in self.checks),
            "has_errors": any(c.severity == "error" for c in self.checks),
        }

    def get_errors(self) -> List[ValidationCheck]:
        """Get all error-level checks."""
        return [c for c in self.checks if c.severity == "error"]

    def get_warnings(self) -> List[ValidationCheck]:
        """Get all warning-level checks."""
        return [c for c in self.checks if c.severity == "warning"]


class InputValidator:
    """Validates user inputs before processing."""

    def __init__(
        self,
        max_length: int = 10000,
        min_length: int = 1,
        allowed_domains: Optional[List[str]] = None,
    ):
        """
        Initialize input validator.

        Args:
            max_length: Maximum query length in characters
            min_length: Minimum query length in characters
            allowed_domains: Allowed query domains (e.g., ["development", "project_mgmt"])
        """
        self.max_length = max_length
        self.min_length = min_length
        self.allowed_domains = allowed_domains or [
            "development",
            "project_management",
            "testing",
            "deployment",
            "architecture",
            "debugging",
        ]
        self.injection_detector = InjectionDetector()
        self.logger = logging.getLogger(__name__)

    def validate(self, query: str) -> ValidationResult:
        """
        Validate a user query.

        Args:
            query: User query to validate

        Returns:
            ValidationResult with all checks
        """
        checks = []

        # Length check
        checks.append(self._check_length(query))

        # Injection check
        checks.append(self._check_injection(query))

        # Scope check (optional, more heuristic)
        checks.append(self._check_scope(query))

        # Character check (detect suspicious encodings)
        checks.append(self._check_characters(query))

        # All checks must pass for overall pass
        passed = all(c.passed for c in checks)

        return ValidationResult(
            passed=passed,
            checks=checks,
            validated_value=query if passed else None,
        )

    def _check_length(self, query: str) -> ValidationCheck:
        """Check query length."""
        length = len(query)

        if length < self.min_length:
            return ValidationCheck(
                name="length_check",
                passed=False,
                message=f"Query too short: {length} chars (min: {self.min_length})",
                severity="error",
            )

        if length > self.max_length:
            return ValidationCheck(
                name="length_check",
                passed=False,
                message=f"Query too long: {length} chars (max: {self.max_length})",
                severity="error",
            )

        return ValidationCheck(
            name="length_check",
            passed=True,
            message=f"Query length OK: {length} chars",
        )

    def _check_injection(self, query: str) -> ValidationCheck:
        """Check for injection attempts."""
        attempt = self.injection_detector.detect(query)

        if attempt:
            return ValidationCheck(
                name="injection_check",
                passed=False,
                message=f"Injection detected: {attempt.severity.value} - {attempt.matched_text}",
                severity="error" if attempt.severity.value in ["high", "critical"] else "warning",
            )

        return ValidationCheck(
            name="injection_check",
            passed=True,
            message="No injection patterns detected",
        )

    def _check_scope(self, query: str) -> ValidationCheck:
        """Check if query is within allowed scope (heuristic)."""
        # This is a soft check - just warn if it looks out of scope
        query_lower = query.lower()

        # Look for domain keywords
        [domain for domain in self.allowed_domains if domain.lower() in query_lower]

        # Suspicious out-of-scope keywords
        out_of_scope_keywords = [
            "write me a story",
            "creative writing",
            "poem",
            "joke",
            "song lyrics",
            "personal advice",
            "medical advice",
            "legal advice",
            "financial investment",
        ]

        out_of_scope_matches = [
            keyword for keyword in out_of_scope_keywords if keyword.lower() in query_lower
        ]

        if out_of_scope_matches:
            return ValidationCheck(
                name="scope_check",
                passed=True,  # Don't fail, just warn
                message=f"Query may be out of scope: {out_of_scope_matches[0]}",
                severity="warning",
            )

        return ValidationCheck(
            name="scope_check",
            passed=True,
            message="Query appears in-scope",
        )

    def _check_characters(self, query: str) -> ValidationCheck:
        """Check for suspicious character patterns."""
        # Check for excessive special characters (possible encoding attack)
        special_char_ratio = sum(1 for c in query if not c.isalnum() and not c.isspace()) / max(
            len(query), 1
        )

        if special_char_ratio > 0.3:
            return ValidationCheck(
                name="character_check",
                passed=True,  # Don't fail, just warn
                message=f"High special character ratio: {special_char_ratio:.1%}",
                severity="warning",
            )

        return ValidationCheck(
            name="character_check",
            passed=True,
            message="Character distribution OK",
        )


class OutputValidator:
    """Validates AI outputs before returning."""

    def __init__(self, min_confidence: float = 0.0):
        """
        Initialize output validator.

        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
        """
        self.min_confidence = min_confidence
        self.logger = logging.getLogger(__name__)

    def validate(self, response: Dict[str, Any]) -> ValidationResult:
        """
        Validate an AI response.

        Args:
            response: AI response dictionary

        Returns:
            ValidationResult with all checks
        """
        checks = []

        # Format check
        checks.append(self._check_format(response))

        # Confidence check (if present)
        if "confidence" in response:
            checks.append(self._check_confidence(response))

        # Hallucination markers check
        checks.append(self._check_hallucination_markers(response))

        # Completeness check
        checks.append(self._check_completeness(response))

        # All checks must pass for overall pass
        passed = all(c.passed for c in checks)

        return ValidationResult(
            passed=passed,
            checks=checks,
            validated_value=response if passed else None,
        )

    def _check_format(self, response: Dict[str, Any]) -> ValidationCheck:
        """Check response format."""
        # Basic structure check
        if not isinstance(response, dict):
            return ValidationCheck(
                name="format_check",
                passed=False,
                message=f"Response must be dict, got {type(response)}",
                severity="error",
            )

        return ValidationCheck(
            name="format_check",
            passed=True,
            message="Response format OK",
        )

    def _check_confidence(self, response: Dict[str, Any]) -> ValidationCheck:
        """Check confidence level."""
        confidence = response.get("confidence")

        if confidence is None:
            return ValidationCheck(
                name="confidence_check",
                passed=True,
                message="No confidence score provided",
            )

        if not isinstance(confidence, (int, float)):
            return ValidationCheck(
                name="confidence_check",
                passed=False,
                message=f"Invalid confidence type: {type(confidence)}",
                severity="error",
            )

        if confidence < self.min_confidence:
            return ValidationCheck(
                name="confidence_check",
                passed=False,
                message=f"Confidence too low: {confidence:.2f} (min: {self.min_confidence:.2f})",
                severity="warning",
            )

        return ValidationCheck(
            name="confidence_check",
            passed=True,
            message=f"Confidence OK: {confidence:.2f}",
        )

    def _check_hallucination_markers(self, response: Dict[str, Any]) -> ValidationCheck:
        """Check for common hallucination markers."""
        # Extract text from response
        text = ""
        if "content" in response:
            text = str(response["content"])
        elif "recommendation" in response:
            text = str(response["recommendation"])
        elif "analysis" in response:
            text = str(response["analysis"])
        else:
            # No text to check
            return ValidationCheck(
                name="hallucination_check",
                passed=True,
                message="No text content to check",
            )

        # Check for hallucination markers
        hallucination_markers = [
            "I apologize, but I don't actually have",
            "I made that up",
            "I'm not certain",
            "this is speculation",
            "I may be hallucinating",
            "I don't have access to",
            "I cannot verify",
        ]

        text_lower = text.lower()
        found_markers = [marker for marker in hallucination_markers if marker.lower() in text_lower]

        if found_markers:
            return ValidationCheck(
                name="hallucination_check",
                passed=True,  # Don't fail, AI is being honest
                message=f"Uncertainty markers found: {found_markers[0]}",
                severity="warning",
            )

        return ValidationCheck(
            name="hallucination_check",
            passed=True,
            message="No hallucination markers detected",
        )

    def _check_completeness(self, response: Dict[str, Any]) -> ValidationCheck:
        """Check if response has key expected fields."""
        # This is specific to Cortex responses
        # We expect at least one of: content, recommendation, analysis, patterns

        expected_fields = ["content", "recommendation", "analysis", "patterns", "context"]

        has_content = any(field in response for field in expected_fields)

        if not has_content:
            return ValidationCheck(
                name="completeness_check",
                passed=False,
                message=f"Response missing expected fields: {expected_fields}",
                severity="warning",
            )

        return ValidationCheck(
            name="completeness_check",
            passed=True,
            message="Response has expected content",
        )
