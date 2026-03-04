#!/usr/bin/env python3
"""
Seed Trust Tracker

Seeds WorkstreamOrchestrator trust domains with baseline data derived
from MEMORY.md project history. Uses record_trust_outcome() to build
the database correctly so level-advancement logic fires.

Domains seeded (from historical project outcomes):
  vortex-backend  45 outcomes, 91% success → L2 (TRUST_BUT_VERIFY)
  vortex-frontend 30 outcomes, 87% success → L2
  cortex          60 outcomes, 95% success → L3 (AUTONOMOUS_WITH_GUARDRAILS)
  winfield        35 outcomes, 89% success → L2
  alpha_arena     15 outcomes, 80% success → L1 (SPOT_CHECK)
  pupil           25 outcomes, 92% success → L2

Usage:
    python cortex/scripts/seed_trust.py
    python cortex/scripts/seed_trust.py --dry-run
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from cortex.engines.workstream_orchestrator import WorkstreamOrchestrator
except ImportError:
    from engines.workstream_orchestrator import WorkstreamOrchestrator

# Domain → (total_outcomes, success_count)
DOMAIN_SEEDS = {
    "vortex-backend": (45, 41),  # 91%
    "vortex-frontend": (30, 26),  # 87%
    "cortex": (60, 57),  # 95%
    "winfield": (35, 31),  # 89%
    "alpha_arena": (15, 12),  # 80%
    "pupil": (25, 23),  # 92%
}


def seed_domain(
    orchestrator: WorkstreamOrchestrator,
    domain: str,
    total: int,
    successes: int,
    dry_run: bool = False,
) -> str:
    """Seed a single domain and return a status line."""
    failures = total - successes

    # Build outcome list: successes first, then failures spread in
    # to simulate realistic history rather than all successes then all failures
    outcomes = []
    s_remaining = successes
    f_remaining = failures
    for i in range(total):
        if f_remaining > 0 and (s_remaining == 0 or (i + 1) % max(1, total // failures) == 0):
            outcomes.append(False)
            f_remaining -= 1
        else:
            outcomes.append(True)
            s_remaining -= 1

    if dry_run:
        acc = successes / total
        return f"  [dry-run] {domain}: {total} outcomes, {acc * 100:.0f}% success"

    # Check if domain already has data
    td = orchestrator.get_trust_level(domain)
    if td.outcomes_total >= total:
        return f"  ✓ {domain}: already seeded ({td.outcomes_total} outcomes, L{td.level.value})"

    # Record outcomes to build accurate level history
    for success in outcomes:
        orchestrator.record_trust_outcome(domain, success)

    # Re-read final state
    td = orchestrator.get_trust_level(domain)
    return (
        f"  ✅ {domain:<20} "
        f"L{td.level.value} ({td.level.name[:16]})  "
        f"{td.accuracy * 100:.0f}% acc  "
        f"{td.outcomes_total} outcomes"
    )


def main():
    dry_run = "--dry-run" in sys.argv

    print("\n═══ Cortex Trust Seeder ═══\n")

    if dry_run:
        print("  [DRY RUN — no data written]\n")
        for domain, (total, successes) in DOMAIN_SEEDS.items():
            acc = successes / total
            print(f"  {domain}: {total} outcomes, {acc * 100:.0f}% success")
        print()
        return

    try:
        orchestrator = WorkstreamOrchestrator()
    except Exception as e:
        print(f"  ✗ Failed to initialize orchestrator: {e}")
        sys.exit(1)

    for domain, (total, successes) in DOMAIN_SEEDS.items():
        status = seed_domain(orchestrator, domain, total, successes, dry_run=dry_run)
        print(status)

    print("\n  Summary:")
    summary = orchestrator.get_trust_summary()
    agg = summary.get("aggregate", {})
    print(f"  Domains tracked: {agg.get('domains_tracked', 0)}")
    print(f"  Total outcomes:  {agg.get('total_outcomes', 0)}")
    print(f"  Avg trust level: L{agg.get('avg_trust_level', 0):.1f}")
    print()
    print("  Run `cxt` or `python cortex/scripts/trust_status.py` to verify.\n")


if __name__ == "__main__":
    main()
