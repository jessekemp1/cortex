#!/usr/bin/env python3
"""
Baseline Capture for Experiments 5–8

Captures Day 0 measurements before Sprint 2 changes take effect.
Writes to ~/.cortex/metrics/experiment_baselines.json.

Experiments:
  Exp 5: Context switch time + flow duration
  Exp 6: Insight hit rate (cross-project patterns surfaced)
  Exp 7: Delegation rate by trust level
  Exp 8: Ideas implemented (count from 2-week commit history)

Usage:
    python cortex/scripts/baseline_capture.py
    python cortex/scripts/baseline_capture.py --show
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BASELINES_PATH = Path.home() / ".cortex" / "metrics" / "experiment_baselines.json"


def capture_exp5_context_switch() -> dict:
    """Exp 5: Context switch time + flow duration baselines.

    Before Sprint 2, context switching is fully manual.
    Manual estimate from observation: ~2 minutes (120s) per switch.
    Flow duration baseline: no measurement yet (0).
    """
    return {
        "experiment": 5,
        "name": "Context Switch Reduction",
        "metric": "context_switch_time_seconds",
        "baseline_value": 120,  # Manual estimate: 2 min per switch
        "unit": "seconds",
        "measurement_method": "manual_estimate",
        "flow_duration_baseline_minutes": 0,  # No measurement yet
        "notes": "Pre-automation baseline. Sprint 2 target: <30s via cxw alias.",
    }


def capture_exp6_insight_hit_rate() -> dict:
    """Exp 6: Cross-project insight surfacing rate.

    Before PatternSurfacer: 0 insights surfaced per session.
    Target after Sprint 2: >0.3 (30% of sessions surface ≥1 relevant pattern).
    """
    return {
        "experiment": 6,
        "name": "Insight Hit Rate",
        "metric": "insight_hit_rate",
        "baseline_value": 0.0,  # No surfacing before Sprint 2
        "unit": "fraction_of_sessions",
        "measurement_method": "zero_baseline",
        "threshold": 0.4,  # PatternSurfacer confidence threshold
        "notes": "PatternSurfacer not yet active. Baseline is 0.",
    }


def capture_exp7_delegation_rate() -> dict:
    """Exp 7: Delegation rate by trust level before seeding.

    Before seed_trust.py: all domains at L0 (VERIFY_EVERYTHING).
    After seeding: mix of L1–L3.
    """
    try:
        from cortex.engines.workstream_orchestrator import WorkstreamOrchestrator
    except ImportError:
        from engines.workstream_orchestrator import WorkstreamOrchestrator

    try:
        orchestrator = WorkstreamOrchestrator()
        summary = orchestrator.get_trust_summary()
        domains = summary.get("domains", {})
        avg_level = summary.get("aggregate", {}).get("avg_trust_level", 0)
        domains_tracked = len(domains)
    except Exception:
        domains = {}
        avg_level = 0
        domains_tracked = 0

    return {
        "experiment": 7,
        "name": "Delegation Rate by Trust Level",
        "metric": "avg_trust_level",
        "baseline_value": avg_level,
        "unit": "trust_level_0_to_4",
        "domains_tracked": domains_tracked,
        "domain_breakdown": {domain: info.get("level", 0) for domain, info in domains.items()},
        "measurement_method": "orchestrator_db",
        "notes": "Baseline captured before seed_trust.py. Run seed after.",
    }


def capture_exp8_ideas_implemented() -> dict:
    """Exp 8: Ideas implemented — count from last 2-week commit history.

    Counts commits with keywords: feat, add, implement, ship, deploy.
    """
    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    commit_count = 0
    feature_keywords = ["feat", "add", "implement", "ship", "deploy", "new"]

    try:
        result = subprocess.run(
            ["git", "log", f"--since={cutoff}", "--oneline", "--no-merges"],
            capture_output=True,
            text=True,
            cwd=Path.home() / "Dev",
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line_lower = line.lower()
                if any(kw in line_lower for kw in feature_keywords):
                    commit_count += 1
    except Exception:
        pass  # git not available or no repo

    return {
        "experiment": 8,
        "name": "Ideas Implemented Rate",
        "metric": "feature_commits_per_2weeks",
        "baseline_value": commit_count,
        "unit": "commits",
        "lookback_days": 14,
        "measurement_method": "git_log_keyword_count",
        "keywords": feature_keywords,
        "notes": "Count of feature/impl commits in last 2 weeks.",
    }


def main():
    show_only = "--show" in sys.argv

    if show_only and BASELINES_PATH.exists():
        with open(BASELINES_PATH) as f:
            data = json.load(f)
        print(json.dumps(data, indent=2))
        return

    print("\n═══ Cortex Experiment Baselines — Day 0 ═══\n")

    baselines = {
        "captured_at": datetime.now().isoformat(),
        "sprint": "sprint_2",
        "experiments": [
            capture_exp5_context_switch(),
            capture_exp6_insight_hit_rate(),
            capture_exp7_delegation_rate(),
            capture_exp8_ideas_implemented(),
        ],
    }

    BASELINES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINES_PATH, "w") as f:
        json.dump(baselines, f, indent=2)

    print(f"  Written to: {BASELINES_PATH}\n")

    for exp in baselines["experiments"]:
        print(
            f"  Exp {exp['experiment']}: {exp['name']}\n"
            f"    Baseline: {exp['baseline_value']} {exp['unit']}\n"
        )

    print("  Run with --show to view again.\n")


if __name__ == "__main__":
    main()
