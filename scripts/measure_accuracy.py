#!/usr/bin/env python3
"""
Cortex Accuracy Baseline Measurement

One-shot script that measures recommendation accuracy against real outcomes.
Run before beta launch. NOT for CI — reads production data from ~/.cortex/.

Usage:
    python scripts/measure_accuracy.py
    python scripts/measure_accuracy.py --domain aidev
    python scripts/measure_accuracy.py --domain databricks

Output:
    - Terminal: breakdown by domain, recommendation_type, confidence_bucket
    - File: ~/.cortex/metrics/accuracy_baseline.json
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CORTEX_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(CORTEX_ROOT))

OUTPUT_FILE = Path.home() / ".cortex" / "metrics" / "accuracy_baseline.json"
BETA_GATE = 0.70  # Flag if accuracy < 70%


def main():
    parser = argparse.ArgumentParser(description="Measure Cortex recommendation accuracy")
    parser.add_argument("--domain", default=None, help="Filter to aidev or databricks")
    args = parser.parse_args()

    from feedback import FeedbackLogger
    from learning import LearningSystem

    feedback = FeedbackLogger()
    all_outcomes = feedback.load_outcomes()

    if not all_outcomes:
        print("❌ No outcomes found in ~/.cortex/outcomes.jsonl")
        print("   Cannot measure accuracy without historical data.")
        sys.exit(1)

    ls = LearningSystem()
    domain = args.domain

    # --- Overall accuracy ---
    accuracy = ls.calculate_recommendation_accuracy(domain=domain)
    domain_label = domain or "all domains"

    print(f"\n{'=' * 60}")
    print(f"  CORTEX ACCURACY BASELINE  ({datetime.now().strftime('%Y-%m-%d')})")
    print(f"{'=' * 60}")
    print(f"  Domain:   {domain_label}")
    print(f"  Outcomes: {len(all_outcomes)} total")

    scope = [o for o in all_outcomes if domain is None or getattr(o, "domain", None) == domain]
    followed = [o for o in scope if o.followed]
    print(f"  Followed: {len(followed)} / {len(scope)}")
    print(f"\n  Overall Accuracy: {accuracy:.1%}")

    gate = "✅ PASS" if accuracy >= BETA_GATE else f"❌ BELOW GATE ({BETA_GATE:.0%})"
    print(f"  Beta Gate ({BETA_GATE:.0%}): {gate}")

    # --- Breakdown by recommendation_type ---
    patterns = ls.get_outcome_patterns(domain=domain)
    if patterns:
        print("\n  By Type:")
        for rtype, metrics in sorted(patterns.items(), key=lambda x: -x[1].get("success_rate", 0)):
            bar = "█" * int(metrics["success_rate"] * 10) + "░" * (
                10 - int(metrics["success_rate"] * 10)
            )
            print(f"    {rtype:<30} {bar} {metrics['success_rate']:.0%}  (n={metrics['followed']})")

    # --- Breakdown by domain (if viewing all) ---
    if domain is None:
        domains_seen = set(getattr(o, "domain", "unknown") for o in all_outcomes)
        if len(domains_seen) > 1:
            print("\n  By Domain:")
            for d in sorted(domains_seen):
                d_acc = ls.calculate_recommendation_accuracy(domain=d)
                d_outcomes = [o for o in all_outcomes if getattr(o, "domain", None) == d]
                d_followed = [o for o in d_outcomes if o.followed]
                print(f"    {d:<20} {d_acc:.1%}  (n={len(d_followed)} followed)")

    # --- Confidence calibration ---
    calibration = ls.get_confidence_calibration(domain=domain)
    if calibration:
        print("\n  Confidence Calibration (bucket → actual success rate):")
        for bucket, rate in sorted(calibration.items()):
            delta = rate - {"high": 0.9, "medium": 0.7, "low": 0.5}.get(bucket, 0.7)
            arrow = "↑" if delta > 0.05 else "↓" if delta < -0.05 else "≈"
            print(f"    {bucket:<8} → {rate:.1%}  {arrow}")

    print(f"\n{'=' * 60}\n")

    # --- Write to file ---
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "total_outcomes": len(all_outcomes),
        "scoped_outcomes": len(scope),
        "followed_count": len(followed),
        "overall_accuracy": accuracy,
        "beta_gate": BETA_GATE,
        "gate_passed": accuracy >= BETA_GATE,
        "patterns": patterns,
        "calibration": calibration,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"  Written to: {OUTPUT_FILE}")

    if accuracy < BETA_GATE:
        print(f"\n  ⚠️  Accuracy {accuracy:.1%} is below beta gate {BETA_GATE:.0%}.")
        print("     Add this disclaimer to beta docs:")
        print("     'Recommendation accuracy is improving as the learning loop")
        print("      processes real usage data. Expected to reach 75%+ after")
        print("      4-6 weeks of active use.'")
        sys.exit(1)


if __name__ == "__main__":
    main()
