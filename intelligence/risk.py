#!/usr/bin/env python3
"""
Risk Classification System

Determines whether a task can auto-execute or needs human approval.
Uses pattern matching and risk heuristics to classify tasks into:
- Auto-execute: Safe, reversible, low-impact
- Queue for approval: Production impact, breaking changes, security

This enables the hybrid approach: auto-execute low-risk, queue high-risk.
"""

from dataclasses import dataclass
from typing import List, Tuple

from intelligence.contracts import TaskContract


@dataclass
class RiskAssessment:
    """Result of risk classification."""

    risk_level: str  # "low", "medium", "high", "critical"
    auto_executable: bool
    rationale: str
    concerns: List[str]


class RiskClassifier:
    """Determines if task can auto-execute or needs human approval."""

    # Patterns for auto-executable tasks
    AUTO_EXECUTE_PATTERNS = {
        "test": ["test", "pytest", "unittest", "integration test"],
        "documentation": ["docs", "readme", "documentation", "docstring", "comment"],
        "analysis": ["analyze", "analysis", "audit", "scan", "check"],
        "refactor_safe": ["rename", "extract function", "inline", "simplify"],
        "bug_fix_minor": ["typo", "formatting", "lint", "style"],
        "dependency_patch": ["patch version", "security patch", "dependency update"],
    }

    # Patterns that require approval
    QUEUE_FOR_APPROVAL_PATTERNS = {
        "deployment": ["deploy", "deployment", "release", "production", "prod"],
        "breaking_change": ["breaking", "backwards incompatible", "API change"],
        "security_fix": ["security", "vulnerability", "CVE", "exposed secret"],
        "refactor_major": ["architecture", "restructure", "major refactor"],
        "new_feature": ["new feature", "add feature", "implement"],
        "dependency_major": ["major version", "upgrade major"],
        "data_migration": ["migrate", "migration", "schema change"],
    }

    def classify(self, contract: TaskContract) -> RiskAssessment:
        """
        Classify contract risk and determine if auto-executable.

        Returns:
            RiskAssessment with risk level and auto-executable flag
        """

        # Collect concerns
        concerns = []

        # Check title and description for patterns
        text = f"{contract.title} {contract.description}".lower()

        # Critical risk indicators (never auto-execute)
        if any(pattern in text for pattern in self.QUEUE_FOR_APPROVAL_PATTERNS["deployment"]):
            concerns.append("Production deployment detected")

        if any(pattern in text for pattern in self.QUEUE_FOR_APPROVAL_PATTERNS["breaking_change"]):
            concerns.append("Potential breaking change detected")

        if any(pattern in text for pattern in self.QUEUE_FOR_APPROVAL_PATTERNS["data_migration"]):
            concerns.append("Data migration detected")

        # High risk indicators
        if "production" in text or "prod" in text:
            concerns.append("Production environment mentioned")

        if "API" in contract.title and "change" in text:
            concerns.append("API change detected")

        # Check human gates
        if "PRODUCTION" in contract.human_gates or "DEPLOY" in contract.human_gates:
            concerns.append("Requires production deployment approval")

        # Check constraints for backwards compatibility
        for constraint in contract.constraints:
            if "backwards" in constraint.lower() or "compatibility" in constraint.lower():
                concerns.append("Backwards compatibility required")

        # Determine risk level and auto-executable status
        if concerns:
            # Has concerns - requires approval
            if len(concerns) >= 3 or any("production" in c.lower() or "breaking" in c.lower() for c in concerns):
                risk_level = "critical"
                auto_executable = False
                rationale = "Critical risk: Multiple concerns or production/breaking change detected"
            elif len(concerns) >= 2:
                risk_level = "high"
                auto_executable = False
                rationale = "High risk: Multiple concerns require human review"
            else:
                risk_level = "medium"
                # Medium risk can be auto-executed if dependencies satisfied and no critical patterns
                auto_executable = self._can_auto_execute_medium_risk(contract)
                rationale = "Medium risk: Can auto-execute if dependencies satisfied" if auto_executable else "Medium risk: Requires approval"
        else:
            # No concerns - check for safe patterns
            is_safe = self._matches_safe_patterns(text)

            if is_safe:
                risk_level = "low"
                auto_executable = True
                rationale = "Low risk: Matches safe patterns (tests, docs, analysis)"
            else:
                risk_level = "medium"
                auto_executable = False
                rationale = "Medium risk: No explicit concerns but no safe pattern match"

        return RiskAssessment(
            risk_level=risk_level,
            auto_executable=auto_executable,
            rationale=rationale,
            concerns=concerns,
        )

    def _matches_safe_patterns(self, text: str) -> bool:
        """Check if text matches safe auto-executable patterns."""
        for category, patterns in self.AUTO_EXECUTE_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                return True
        return False

    def _can_auto_execute_medium_risk(self, contract: TaskContract) -> bool:
        """
        Determine if medium-risk task can auto-execute.

        Criteria:
        - All dependencies satisfied
        - No production human gates
        - Has verification criteria (tests/metrics)
        """

        # Check dependencies
        if contract.dependencies:
            # In real implementation, verify dependencies exist
            # For now, assume they need checking
            return False

        # Check human gates
        if "PRODUCTION" in contract.human_gates:
            return False

        # Check if has strong verification
        has_tests = bool(contract.success_criteria.get("tests"))
        has_metrics = bool(contract.success_criteria.get("metrics"))

        if has_tests or has_metrics:
            return True

        return False

    def should_notify_user(self, contract: TaskContract, assessment: RiskAssessment) -> Tuple[bool, str]:
        """
        Determine if user should be notified about this task.

        Returns:
            (should_notify, notification_message)
        """

        if assessment.auto_executable:
            # Auto-executing - only notify if low risk
            if assessment.risk_level == "low":
                return (False, "")  # Silent execution
            else:
                return (True, f"Auto-executing {assessment.risk_level} risk task: {contract.title}")
        else:
            # Requires approval - always notify
            return (True, f"Task requires approval ({assessment.risk_level} risk): {contract.title}")


if __name__ == "__main__":
    from intelligence.contracts import TaskContract

    # Test risk classification
    classifier = RiskClassifier()

    # Test case 1: Low risk (tests)
    test_contract = TaskContract(
        contract_id="test_1",
        signal_id="signal_1",
        title="Fix failing unit tests in test_ensemble.py",
        description="Fix 3 failing unit tests in the ensemble module",
        requirements=["Fix test failures"],
        constraints=[],
        success_criteria={"tests": ["Unit tests pass"]},
        dependencies=[],
        human_gates=[],
        risk_level="low",
        auto_executable=True,
    )

    assessment = classifier.classify(test_contract)
    print(f"Test Contract: {test_contract.title}")
    print(f"  Risk Level: {assessment.risk_level}")
    print(f"  Auto-executable: {assessment.auto_executable}")
    print(f"  Rationale: {assessment.rationale}")
    print()

    # Test case 2: High risk (deployment)
    deploy_contract = TaskContract(
        contract_id="deploy_1",
        signal_id="signal_2",
        title="Deploy FieldSelectiveEnsemble to production",
        description="Deploy the validated FieldSelectiveEnsemble model to production environment",
        requirements=["Deploy to production"],
        constraints=["Zero downtime"],
        success_criteria={"tests": ["Integration tests pass"], "metrics": {"accuracy": ">= 0.87"}},
        dependencies=[],
        human_gates=["PRODUCTION"],
        risk_level="high",
        auto_executable=False,
    )

    assessment = classifier.classify(deploy_contract)
    print(f"Deploy Contract: {deploy_contract.title}")
    print(f"  Risk Level: {assessment.risk_level}")
    print(f"  Auto-executable: {assessment.auto_executable}")
    print(f"  Rationale: {assessment.rationale}")
    print(f"  Concerns: {', '.join(assessment.concerns)}")
