#!/usr/bin/env python3
"""Guardian measurement tool for Cortex Lean 7-day gate evaluation.

Reads V1 and Lean telemetry to evaluate Guardian #1 (Edit-without-Read).
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file into list of dicts. Returns empty list if file missing."""
    if not path.exists():
        return []

    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def analyze_lean_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze Lean guardian events and return statistics."""
    stats = {
        "total_events": len(events),
        "pass_read_verified": 0,
        "warn_blind_edit": 0,
        "warn_bash_streak": 0,
        "pass_bash_check": 0,
        "blind_edit_rate": 0.0,
        "edit_checks": 0,
    }

    for event in events:
        event_type = event.get("event", "")
        if event_type == "pass_read_verified":
            stats["pass_read_verified"] += 1
        elif event_type == "warn_blind_edit":
            stats["warn_blind_edit"] += 1
        elif event_type == "warn_bash_streak":
            stats["warn_bash_streak"] += 1
        elif event_type == "pass_bash_check":
            stats["pass_bash_check"] += 1

    # Calculate blind edit rate
    stats["edit_checks"] = stats["pass_read_verified"] + stats["warn_blind_edit"]
    if stats["edit_checks"] > 0:
        stats["blind_edit_rate"] = stats["warn_blind_edit"] / stats["edit_checks"]

    return stats


def analyze_v1_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze V1 rule events and return statistics."""
    stats = {
        "total_events": len(events),
        "violations": 0,
        "violation_rate": 0.0,
    }

    for event in events:
        event_type = event.get("event_type", "")
        if "violation" in event_type.lower():
            stats["violations"] += 1

    if stats["total_events"] > 0:
        stats["violation_rate"] = stats["violations"] / stats["total_events"]

    return stats


def load_measurement_metadata() -> Dict[str, Any]:
    """Load measurement start metadata."""
    metadata_path = Path.home() / ".cortex-lean" / "measurement_start.json"
    if not metadata_path.exists():
        return {
            "started": None,
            "baseline_blind_edit_rate": 0.13,
            "baseline_edit_failure_rate": 0.757,
        }

    with open(metadata_path) as f:
        return json.load(f)


def evaluate_gate(lean_stats: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate 7-day gate progress."""
    baseline_blind_edit = metadata["baseline_blind_edit_rate"]
    target_blind_edit = 0.05

    gate = {
        "baseline_blind_edit_rate": baseline_blind_edit,
        "target_blind_edit_rate": target_blind_edit,
        "current_blind_edit_rate": lean_stats["blind_edit_rate"],
        "meets_target": lean_stats["blind_edit_rate"] < target_blind_edit,
        "days_elapsed": 0,
        "days_required": 7,
        "status": "in_progress",
    }

    # Calculate days elapsed
    if metadata["started"]:
        start_time = datetime.fromisoformat(metadata["started"])
        # Strip timezone info to make it naive for comparison
        if start_time.tzinfo is not None:
            start_time = start_time.replace(tzinfo=None)
        days_elapsed = (datetime.now() - start_time).days
        gate["days_elapsed"] = days_elapsed

        if days_elapsed >= 7 and gate["meets_target"]:
            gate["status"] = "passed"
        elif days_elapsed >= 7:
            gate["status"] = "failed"

    return gate


def format_report(
    lean_stats: Dict[str, Any], v1_stats: Dict[str, Any], gate: Dict[str, Any]
) -> str:
    """Format full human-readable report."""
    lines = [
        "=== Cortex Lean Guardian Measurement ===",
        "",
        f"Gate Progress: Day {gate['days_elapsed']}/{gate['days_required']} | Status: {gate['status'].upper()}",
        "",
        "--- Lean Guardian (Current) ---",
        f"Total Events: {lean_stats['total_events']}",
        f"  Read Verified: {lean_stats['pass_read_verified']}",
        f"  Blind Edit Warnings: {lean_stats['warn_blind_edit']}",
        f"  Bash Streak Warnings: {lean_stats['warn_bash_streak']}",
        f"  Bash Checks Passed: {lean_stats['pass_bash_check']}",
        "",
        f"Blind Edit Rate: {lean_stats['blind_edit_rate']:.1%} (target: <{gate['target_blind_edit_rate']:.1%})",
        f"Baseline: {gate['baseline_blind_edit_rate']:.1%}",
        "",
    ]

    if gate["meets_target"]:
        lines.append("✓ Currently meeting target")
    else:
        lines.append("✗ Not meeting target")

    if v1_stats["total_events"] > 0:
        lines.extend(
            [
                "",
                "--- V1 System (Historical) ---",
                f"Total Events: {v1_stats['total_events']}",
                f"Violations: {v1_stats['violations']}",
                f"Violation Rate: {v1_stats['violation_rate']:.1%}",
            ]
        )

    return "\n".join(lines)


def format_summary(lean_stats: Dict[str, Any], gate: Dict[str, Any]) -> str:
    """Format one-line summary."""
    return (
        f"Guardian: Day {gate['days_elapsed']}/{gate['days_required']} | "
        f"{lean_stats['total_events']} events | "
        f"blind-edit {lean_stats['blind_edit_rate']:.1%} "
        f"(baseline {gate['baseline_blind_edit_rate']:.1%})"
    )


def format_json(lean_stats: Dict[str, Any], v1_stats: Dict[str, Any], gate: Dict[str, Any]) -> str:
    """Format machine-readable JSON output."""
    output = {
        "gate": gate,
        "lean": lean_stats,
        "v1": v1_stats,
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Measure Cortex Lean guardian performance")
    parser.add_argument("--summary", action="store_true", help="One-line summary output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # Load data
    lean_log_path = Path.home() / ".cortex-lean" / "guardian_log.jsonl"
    v1_log_path = Path.home() / ".cortex" / "rule_events.jsonl"

    lean_events = load_jsonl(lean_log_path)
    v1_events = load_jsonl(v1_log_path)
    metadata = load_measurement_metadata()

    # Analyze
    lean_stats = analyze_lean_events(lean_events)
    v1_stats = analyze_v1_events(v1_events)
    gate = evaluate_gate(lean_stats, metadata)

    # Output
    if args.json:
        print(format_json(lean_stats, v1_stats, gate))
    elif args.summary:
        print(format_summary(lean_stats, gate))
    else:
        print(format_report(lean_stats, v1_stats, gate))


if __name__ == "__main__":
    main()
