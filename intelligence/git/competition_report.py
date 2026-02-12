#!/usr/bin/env python3
"""
Git Automation Competition Report

After 7 days, generates comparison: acceptance rate, modification rate,
latency, false positive rate, winner declaration per metric.

Run: python cortex/intelligence/git/competition_report.py --days 7
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cortex.intelligence.git.automation_metrics import get_events_with_responses


def generate_report(days: int = 7) -> dict:
    events = get_events_with_responses(days)
    lean = [e for e in events if e.get("source") == "lean"]
    v1 = [e for e in events if e.get("source") == "v1"]
    report = {
        "period_days": days, "total_events": len(events),
        "lean": _analyze_source(lean), "v1": _analyze_source(v1),
        "winners": {}, "recommendation": "",
    }
    report["winners"] = _determine_winners(report["lean"], report["v1"])
    report["recommendation"] = _make_recommendation(report)
    return report


def _analyze_source(events: list[dict]) -> dict:
    if not events:
        return {"count": 0, "acceptance_rate": 0, "modification_rate": 0,
                "false_positive_rate": 0, "avg_latency_ms": 0, "p95_latency_ms": 0, "by_type": {}}
    responded = [e for e in events if e.get("user_response")]
    accepted = sum(1 for e in responded if e["user_response"] == "accepted")
    modified = sum(1 for e in responded if e["user_response"] == "modified")
    ignored = len(events) - len(responded)
    by_type = {}
    for e in events:
        et = e.get("event_type", "unknown")
        if et not in by_type:
            by_type[et] = {"count": 0, "accepted": 0, "rejected": 0}
        by_type[et]["count"] += 1
        if e.get("user_response") == "accepted":
            by_type[et]["accepted"] += 1
        elif e.get("user_response") == "rejected":
            by_type[et]["rejected"] += 1
    latencies = [e["latency_ms"] for e in events if "latency_ms" in e]
    return {
        "count": len(events),
        "acceptance_rate": round(accepted / len(responded), 3) if responded else 0,
        "modification_rate": round(modified / len(responded), 3) if responded else 0,
        "false_positive_rate": round(ignored / len(events), 3) if events else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 1),
        "by_type": by_type,
    }


def _determine_winners(lean: dict, v1: dict) -> dict:
    winners = {}
    metrics = [
        ("acceptance_rate", "higher"), ("modification_rate", "lower"),
        ("false_positive_rate", "lower"), ("avg_latency_ms", "lower"),
    ]
    for metric, better in metrics:
        lv, vv = lean.get(metric, 0), v1.get(metric, 0)
        if lv == vv:
            winners[metric] = "tie"
        elif better == "higher":
            winners[metric] = "lean" if lv > vv else "v1"
        else:
            winners[metric] = "lean" if lv < vv else "v1"
    return winners


def _make_recommendation(report: dict) -> str:
    lean, v1 = report["lean"], report["v1"]
    if lean["count"] < 5 or v1["count"] < 5:
        return "INSUFFICIENT_DATA: Need at least 5 events per source"
    lean_wins = sum(1 for w in report["winners"].values() if w == "lean")
    v1_wins = sum(1 for w in report["winners"].values() if w == "v1")
    if lean_wins > v1_wins:
        return f"LEAN_PREFERRED: Lean wins {lean_wins}/{len(report['winners'])} metrics."
    elif v1_wins > lean_wins:
        return f"V1_PREFERRED: V1 wins {v1_wins}/{len(report['winners'])} metrics."
    else:
        if lean["acceptance_rate"] >= v1["acceptance_rate"]:
            return "LEAN_SLIGHT_EDGE: Tied but Lean has equal/better acceptance + lower latency."
        return "V1_SLIGHT_EDGE: Tied but V1 has better acceptance rate."


def format_report(report: dict) -> str:
    lines = [f"=== Git Automation Competition Report ({report['period_days']} days) ===",
             f"Total events: {report['total_events']}", ""]
    for source in ("lean", "v1"):
        s = report[source]
        lines.extend([
            f"[{source.upper()}]",
            f"  Suggestions:        {s['count']}",
            f"  Acceptance rate:     {s['acceptance_rate']:.1%}",
            f"  Modification rate:   {s['modification_rate']:.1%}",
            f"  False positive rate: {s['false_positive_rate']:.1%}",
            f"  Avg latency:         {s['avg_latency_ms']:.0f}ms",
            f"  P95 latency:         {s['p95_latency_ms']:.0f}ms", "",
        ])
    lines.append("Winners per metric:")
    for metric, winner in report["winners"].items():
        icon = {"lean": "L", "v1": "V", "tie": "="}[winner]
        lines.append(f"  [{icon}] {metric}")
    lines.append(f"\nRecommendation: {report['recommendation']}")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Git Automation Competition Report")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = generate_report(args.days)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()
