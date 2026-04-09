#!/usr/bin/env python3
"""
Demo: Cortex Synthetic Data Engine — Canadian FinServ

Generates synthetic customer profiles and transactions,
validates with quality framework, and shows distribution fidelity.

Usage:
    cd cortex && python -m synthetic.demo_synthetic
    OR
    python cortex/synthetic/demo_synthetic.py
"""

import json
import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.quality import SyntheticQualityTracker
from synthetic.schemas import GenerationRequest


def demo_profiles():
    """Generate and validate synthetic customer profiles."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║    CORTEX SYNTHETIC DATA ENGINE — Canadian FinServ      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    generator = SyntheticGenerator()
    kb = CanadianFinServKB()

    # --- Demo 1: Mixed-segment profile generation ---
    print("━━━ Demo 1: Generate 100 Mixed-Segment Profiles ━━━")
    request = GenerationRequest(
        data_type="profiles",
        count=100,
        min_quality_score=0.7,
        output_format="jsonl",
    )
    result = generator.generate(request)
    print(f"  {result.summary()}")
    print(f"  Output: {result.output_path}")
    print(f"  Quality distribution: {json.dumps(result.quality_distribution, indent=4)}")
    print()

    # --- Demo 2: Targeted segment generation ---
    print("━━━ Demo 2: Generate 50 Mass Affluent ON Profiles ━━━")
    request = GenerationRequest(
        data_type="profiles",
        count=50,
        segment="mass_affluent",
        province="ON",
        min_quality_score=0.8,
        output_format="jsonl",
    )
    result = generator.generate(request)
    print(f"  {result.summary()}")
    print()

    # --- Demo 3: Distribution fidelity check ---
    print("━━━ Demo 3: Distribution Fidelity vs StatsCan ━━━")
    # Generate larger batch for distribution testing
    request = GenerationRequest(data_type="profiles", count=500, min_quality_score=0.0)
    result = generator.generate(request)

    # Load generated profiles and check distributions
    if result.output_path:
        profiles = []
        from synthetic.schemas import CustomerProfile

        with open(result.output_path) as f:
            for line in f:
                data = json.loads(line)
                profiles.append(CustomerProfile(**{k: v for k, v in data.items()}))

        tracker = SyntheticQualityTracker(kb)
        dist_results = tracker.assess_batch_distribution(profiles)

        for constraint_name, (passes, deviation) in dist_results.items():
            status = "✅ PASS" if passes else "❌ FAIL"
            print(f"  {status} {constraint_name}: max deviation {deviation:.3f} (threshold: 5%)")
    print()

    # --- Demo 4: Transaction generation with AML flags ---
    print("━━━ Demo 4: Generate 200 Transactions (High Risk) ━━━")
    request = GenerationRequest(
        data_type="transactions",
        count=200,
        include_risk_flags=True,
        risk_profile="high",
        min_quality_score=0.7,
    )
    result = generator.generate(request)
    print(f"  {result.summary()}")

    # Count risk flags
    if result.output_path:
        risk_counts = {}
        with open(result.output_path) as f:
            for line in f:
                data = json.loads(line)
                flag = data.get("risk_flag", "none")
                risk_counts[flag] = risk_counts.get(flag, 0) + 1
        print(f"  Risk flag distribution: {json.dumps(risk_counts, indent=4)}")
    print()

    # --- Demo 5: Knowledge Base inspection ---
    print("━━━ Demo 5: Knowledge Base Constraints ━━━")
    constraints = kb.get_all_constraints()
    print(f"  Loaded {len(constraints)} distribution constraints:")
    for name, constraint in constraints.items():
        print(f"    • {constraint.name} ({constraint.source}, {constraint.year})")

    reg = kb.get_regulatory_params()
    print("\n  Regulatory parameters:")
    print(f"    • OSFI Stress Test Rate: {reg['stress_test_rate']}%")
    print(f"    • FINTRAC Cash Threshold: ${reg['large_cash_threshold_cad']:,}")
    print(f"    • Max GDS Ratio: {reg['max_gds_ratio'] * 100:.0f}%")
    print(f"    • Max TDS Ratio: {reg['max_tds_ratio'] * 100:.0f}%")
    print()

    # --- Demo 6: Flywheel outcome log ---
    print("━━━ Demo 6: Outcome Flywheel ━━━")
    outcome_path = Path.home() / ".cortex" / "synthetic" / "generation_outcomes.jsonl"
    if outcome_path.exists():
        with open(outcome_path) as f:
            outcomes = [json.loads(line) for line in f if line.strip()]
        print(f"  {len(outcomes)} generation runs logged for flywheel learning")
        if outcomes:
            latest = outcomes[-1]
            print(
                f"  Latest: {latest['data_type']} | {latest['count_generated']} records | "
                f"avg quality {latest['avg_quality']:.3f}"
            )
    else:
        print("  No outcomes logged yet (first run)")

    print()
    print("══════════════════════════════════════════════════════════")
    print("  Cortex SynthFinServ v0.1.0 — Minimum Evolvable Product")
    print("  Next: Wire into bridge.py + CLI for production access")
    print("══════════════════════════════════════════════════════════")


if __name__ == "__main__":
    demo_profiles()
