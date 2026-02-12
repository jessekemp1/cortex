#!/usr/bin/env python3
"""
Testing Enforcement Gate

Blocks delivery claims without test evidence.
Cannot be bypassed. Cannot be disabled.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TestEvidence:
    """Required evidence for marking feature ready."""

    feature_name: str
    user_command_tested: bool
    user_command_output: str
    edge_cases_tested: bool
    edge_case_results: List[str]
    regression_passed: bool
    regression_results: str
    timestamp: str

    def is_complete(self) -> bool:
        """Check if all evidence is present."""
        return (
            self.user_command_tested
            and self.edge_cases_tested
            and self.regression_passed
            and bool(self.user_command_output)
            and bool(self.edge_case_results)
            and bool(self.regression_results)
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "feature_name": self.feature_name,
            "user_command_tested": self.user_command_tested,
            "user_command_output": self.user_command_output,
            "edge_cases_tested": self.edge_cases_tested,
            "edge_case_results": self.edge_case_results,
            "regression_passed": self.regression_passed,
            "regression_results": self.regression_results,
            "timestamp": self.timestamp,
            "complete": self.is_complete(),
        }


class MissingTestEvidence(Exception):
    """Raised when delivery claim lacks required test evidence."""

    pass


class InsufficientEvidence(Exception):
    """Raised when test evidence is incomplete."""

    pass


class TestingEnforcer:
    """Enforces testing requirements for delivery claims.

    This is ACTIVE enforcement - blocks actions, not just logs them.
    """

    def __init__(self, evidence_dir: Optional[Path] = None):
        if evidence_dir is None:
            evidence_dir = Path.home() / ".cortex" / "test_evidence"

        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        self.violations_file = evidence_dir / "violations.jsonl"
        self.enforcement_active = True

    def require_evidence(self, feature_name: str) -> TestEvidence:
        """Require test evidence for a feature.

        Raises:
            MissingTestEvidence: If no evidence file found
            InsufficientEvidence: If evidence incomplete

        Returns:
            TestEvidence object if complete
        """
        evidence_file = self.evidence_dir / f"{feature_name}.json"

        if not evidence_file.exists():
            self._log_violation(feature_name=feature_name, reason="No test evidence file found")

            raise MissingTestEvidence(
                f"\n❌ CANNOT PROCEED WITHOUT TEST EVIDENCE\n"
                f"\n"
                f"Feature: {feature_name}\n"
                f"Required evidence file: {evidence_file}\n"
                f"\n"
                f"You must provide:\n"
                f"  1. User command test results\n"
                f"  2. Edge case handling proof\n"
                f"  3. Regression test pass\n"
                f"\n"
                f"Generate evidence:\n"
                f"  python cortex/enforcement/evidence_generator.py {feature_name}\n"
                f"\n"
                f"This is ENFORCED. Cannot bypass.\n"
            )

        # Load evidence
        with open(evidence_file, "r") as f:
            data = json.load(f)

        evidence = TestEvidence(
            feature_name=data["feature_name"],
            user_command_tested=data.get("user_command_tested", False),
            user_command_output=data.get("user_command_output", ""),
            edge_cases_tested=data.get("edge_cases_tested", False),
            edge_case_results=data.get("edge_case_results", []),
            regression_passed=data.get("regression_passed", False),
            regression_results=data.get("regression_results", ""),
            timestamp=data.get("timestamp", ""),
        )

        # Verify completeness
        if not evidence.is_complete():
            self._log_violation(feature_name=feature_name, reason="Incomplete test evidence")

            missing = []
            if not evidence.user_command_tested or not evidence.user_command_output:
                missing.append("User command test")
            if not evidence.edge_cases_tested or not evidence.edge_case_results:
                missing.append("Edge case tests")
            if not evidence.regression_passed or not evidence.regression_results:
                missing.append("Regression tests")

            raise InsufficientEvidence(
                f"\n❌ INCOMPLETE TEST EVIDENCE\n"
                f"\n"
                f"Feature: {feature_name}\n"
                f"Missing: {', '.join(missing)}\n"
                f"\n"
                f"Evidence file exists but is incomplete.\n"
                f"Complete all required tests before claiming ready.\n"
                f"\n"
                f"This is ENFORCED. Cannot bypass.\n"
            )

        # Evidence is complete
        print(f"\n✅ Test evidence verified for: {feature_name}")
        print("   User command: TESTED")
        print("   Edge cases: TESTED")
        print("   Regression: PASSED")
        print(f"   Timestamp: {evidence.timestamp}\n")

        return evidence

    def check_delivery_claim(self, claim: str, context: Dict) -> bool:
        """Check if a delivery claim has required evidence.

        Args:
            claim: The claim being made (e.g., "feature is ready")
            context: Context including feature name, test evidence, etc.

        Returns:
            True if claim is allowed, False if blocked

        This runs BEFORE allowing any "ready" claim.
        """
        # Detect delivery claims
        delivery_keywords = [
            "ready",
            "complete",
            "done",
            "working",
            "tested",
            "finished",
            "delivered",
            "built",
            "implemented",
        ]

        if not any(kw in claim.lower() for kw in delivery_keywords):
            return True  # Not a delivery claim

        # This is a delivery claim - ENFORCE
        print("\n⚠️  DELIVERY CLAIM DETECTED")
        print(f"   Claim: '{claim}'")
        print("\n   Testing enforcement ACTIVE\n")

        feature_name = context.get("feature_name")
        if not feature_name:
            print("   ❌ No feature name provided")
            print("   Cannot verify without feature name\n")
            return False

        # Check for test evidence
        try:
            self.require_evidence(feature_name)
            print("   ✅ Delivery claim approved\n")
            return True

        except (MissingTestEvidence, InsufficientEvidence) as e:
            print(str(e))
            return False

    def _log_violation(self, feature_name: str, reason: str) -> None:
        """Log a testing violation."""
        violation = {
            "feature_name": feature_name,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.violations_file, "a") as f:
            f.write(json.dumps(violation) + "\n")

    def get_violations(self, days: int = 7) -> List[Dict]:
        """Get recent violations."""
        if not self.violations_file.exists():
            return []

        violations = []
        cutoff = datetime.now().timestamp() - (days * 86400)

        with open(self.violations_file, "r") as f:
            for line in f:
                try:
                    v = json.loads(line.strip())
                    v_time = datetime.fromisoformat(v["timestamp"]).timestamp()
                    if v_time >= cutoff:
                        violations.append(v)
                except (json.JSONDecodeError, KeyError):
                    continue

        return violations

    def session_startup_check(self) -> None:
        """Show violations from recent sessions.

        Call this at session startup to remind about untested claims.
        """
        violations = self.get_violations(days=7)

        if violations:
            print("\n" + "=" * 70)
            print("⚠️  TESTING VIOLATIONS FROM LAST 7 DAYS")
            print("=" * 70)

            for v in violations:
                print(f"\n   Feature: {v['feature_name']}")
                print(f"   Reason: {v['reason']}")
                print(f"   Time: {v['timestamp']}")

            print("\n   These delivery claims were BLOCKED due to missing test evidence.")
            print("   Complete testing before making new claims.")
            print("\n" + "=" * 70 + "\n")


class DeliveryGate:
    """Gate that blocks delivery without evidence.

    Use this in commit hooks, CI/CD, and workflows.
    """

    def __init__(self):
        self.enforcer = TestingEnforcer()

    def allow_commit(self, commit_message: str) -> bool:
        """Check if commit can proceed.

        Returns:
            True if commit allowed, False if blocked
        """
        # Parse feature name from commit message
        # Format: "feat: description" or "fix: description"
        feature_name = self._extract_feature_from_commit(commit_message)

        if not feature_name:
            return True  # Not a feature commit

        # Check for delivery claims
        context = {"feature_name": feature_name}

        try:
            return self.enforcer.check_delivery_claim(commit_message, context)
        except (MissingTestEvidence, InsufficientEvidence):
            return False

    def _extract_feature_from_commit(self, message: str) -> Optional[str]:
        """Extract feature name from commit message."""
        # Look for conventional commit format
        import re

        pattern = r"^(feat|feature|add|implement|build)[\(\:]\s*(.+)$"
        match = re.match(pattern, message.lower())

        if match:
            feature_desc = match.group(2).strip()
            # Convert to snake_case filename
            feature_name = re.sub(r"[^a-z0-9]+", "_", feature_desc.lower())
            return feature_name

        return None


def main():
    """CLI for testing the enforcer."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python testing_gate.py <command> [args]")
        print("\nCommands:")
        print("  check <feature-name>  - Check if feature has test evidence")
        print("  violations            - Show recent violations")
        print("  startup               - Run session startup check")
        return

    command = sys.argv[1]
    enforcer = TestingEnforcer()

    if command == "check":
        if len(sys.argv) < 3:
            print("Usage: python testing_gate.py check <feature-name>")
            return

        feature_name = sys.argv[2]

        try:
            evidence = enforcer.require_evidence(feature_name)
            print(f"\n✅ Feature '{feature_name}' has complete test evidence")
            print(json.dumps(evidence.to_dict(), indent=2))

        except (MissingTestEvidence, InsufficientEvidence) as e:
            print(str(e))
            sys.exit(1)

    elif command == "violations":
        violations = enforcer.get_violations(days=7)

        if not violations:
            print("\n✅ No violations in last 7 days")
        else:
            print(f"\n⚠️  {len(violations)} violations in last 7 days:\n")
            for v in violations:
                print(f"  • {v['feature_name']}: {v['reason']}")
                print(f"    {v['timestamp']}")

    elif command == "startup":
        enforcer.session_startup_check()


if __name__ == "__main__":
    main()
