#!/usr/bin/env python3
"""
Test Evidence Generator

Interactive tool to collect and validate test evidence.
Generates evidence file required by TestingEnforcer.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List


def generate_evidence(feature_name: str) -> dict:
    """Interactively generate test evidence.

    This FORCES you to actually test before claiming ready.
    """
    print("\n" + "=" * 70)
    print(f"TEST EVIDENCE GENERATOR: {feature_name}")
    print("=" * 70)
    print("\n This tool collects PROOF that you tested the feature.")
    print(" You cannot proceed without completing ALL tests.\n")

    evidence = {
        "feature_name": feature_name,
        "timestamp": datetime.now().isoformat(),
    }

    # 1. User Command Test
    print("=" * 70)
    print("1. USER COMMAND TEST")
    print("=" * 70)
    print("\nYou must test the ACTUAL command/interface the user will use.")
    print("NOT just 'python script.py', but the real /command or UI.\n")

    response = input("Did you test the user-facing command? (yes/no): ").strip().lower()

    if response != "yes":
        print("\n❌ BLOCKED: You must test the user command before claiming ready.")
        print("   Go test it now, then run this again.\n")
        return None

    evidence["user_command_tested"] = True

    print("\nPaste the command you ran (e.g., '/command-name arg'):")
    command = input("> ").strip()

    print("\nPaste the output (first 5 lines or summary):")
    output_lines = []
    print("(Press Enter twice when done)")

    while True:
        line = input()
        if not line:
            break
        output_lines.append(line)

    if not output_lines:
        print("\n❌ BLOCKED: You must provide command output as proof.")
        return None

    evidence["user_command_output"] = f"Command: {command}\n" + "\n".join(output_lines)

    # 2. Edge Cases
    print("\n" + "=" * 70)
    print("2. EDGE CASE TESTING")
    print("=" * 70)
    print("\nYou must test what happens when things go wrong:")
    print("  • No data / empty input")
    print("  • Invalid data / bad input")
    print("  • Large data")
    print("\n")

    response = input("Did you test edge cases? (yes/no): ").strip().lower()

    if response != "yes":
        print("\n❌ BLOCKED: Edge cases must be tested.")
        print("   Test at least 2 edge cases, then run this again.\n")
        return None

    evidence["edge_cases_tested"] = True

    print("\nDescribe each edge case and result:")
    print("(Format: 'Scenario: Result')")
    print("(Press Enter twice when done)")

    edge_cases = []
    while True:
        case = input("> ").strip()
        if not case:
            break
        edge_cases.append(case)

    if len(edge_cases) < 2:
        print("\n❌ BLOCKED: Must test at least 2 edge cases.")
        return None

    evidence["edge_case_results"] = edge_cases

    # 3. Regression Tests
    print("\n" + "=" * 70)
    print("3. REGRESSION TESTING")
    print("=" * 70)
    print("\nYou must verify existing features still work:")
    print("  • Test at least 2 existing commands/features")
    print("  • Confirm nothing broke")
    print("\n")

    response = input("Did you test existing features? (yes/no): ").strip().lower()

    if response != "yes":
        print("\n❌ BLOCKED: Regression tests required.")
        print("   Test existing features, then run this again.\n")
        return None

    evidence["regression_passed"] = True

    print("\nList features tested (one per line):")
    print("(Press Enter twice when done)")

    tested_features = []
    while True:
        feature = input("> ").strip()
        if not feature:
            break
        tested_features.append(feature)

    if len(tested_features) < 2:
        print("\n❌ BLOCKED: Must test at least 2 existing features.")
        return None

    evidence["regression_results"] = (
        f"Tested {len(tested_features)} existing features:\n" + "\n".join(f"  • {f}" for f in tested_features)
    )

    # All evidence collected
    print("\n" + "=" * 70)
    print("✅ TEST EVIDENCE COMPLETE")
    print("=" * 70)
    print("\nSummary:")
    print(f"  • User command tested: ✅")
    print(f"  • Edge cases tested: ✅ ({len(edge_cases)} cases)")
    print(f"  • Regression passed: ✅ ({len(tested_features)} features)")
    print("\nThis evidence will be saved and verified by the enforcer.")
    print("=" * 70 + "\n")

    return evidence


def save_evidence(evidence: dict) -> Path:
    """Save evidence to file."""
    evidence_dir = Path.home() / ".cortex" / "test_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    feature_name = evidence["feature_name"]
    evidence_file = evidence_dir / f"{feature_name}.json"

    with open(evidence_file, "w") as f:
        json.dump(evidence, f, indent=2)

    return evidence_file


def main():
    """Interactive evidence generation."""
    import sys

    if len(sys.argv) < 2:
        print("\nUsage: python evidence_generator.py <feature-name>")
        print("\nExample:")
        print("  python evidence_generator.py prompt-learn")
        print("\nThis tool collects test evidence required by the enforcer.")
        print("You cannot claim a feature is 'ready' without this evidence.\n")
        return

    feature_name = sys.argv[1]

    # Generate evidence
    evidence = generate_evidence(feature_name)

    if evidence is None:
        print("\n❌ Evidence generation failed.")
        print("   Complete all required tests before trying again.\n")
        sys.exit(1)

    # Save evidence
    evidence_file = save_evidence(evidence)

    print(f"\n✅ Evidence saved to: {evidence_file}")
    print("\nYou can now claim this feature is ready.")
    print("The enforcer will verify this evidence before allowing commits.\n")


if __name__ == "__main__":
    main()
