#!/usr/bin/env python3
"""
Git Automation Competition Metrics

Shared event store for Lean and V1 git automation systems.
Storage: ~/.cortex/git_automation_events.jsonl
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

METRICS_FILE = Path.home() / ".cortex" / "git_automation_events.jsonl"


def ensure_metrics_dir():
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)


def log_event(source: str, event_type: str, suggestion: dict, latency_ms: float,
              user_response: str | None = None) -> str:
    ensure_metrics_dir()
    event_id = str(uuid.uuid4())
    entry = {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "event_type": event_type,
        "suggestion": suggestion,
        "latency_ms": round(latency_ms, 1),
        "user_response": user_response,
    }
    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return event_id


def update_response(event_id: str, user_response: str, modified_message: str | None = None):
    ensure_metrics_dir()
    entry = {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "response_update",
        "user_response": user_response,
        "modified_message": modified_message,
    }
    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_events(days: int = 7) -> list[dict]:
    if not METRICS_FILE.exists():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    events = []
    for line in METRICS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
            if ts >= cutoff:
                events.append(entry)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return events


def get_events_with_responses(days: int = 7) -> list[dict]:
    raw = load_events(days)
    originals = {}
    updates = {}
    for entry in raw:
        if entry.get("type") == "response_update":
            updates[entry["event_id"]] = entry
        elif "source" in entry:
            originals[entry["event_id"]] = entry
    for eid, update in updates.items():
        if eid in originals:
            originals[eid]["user_response"] = update["user_response"]
            if update.get("modified_message"):
                originals[eid]["modified_message"] = update["modified_message"]
    return list(originals.values())


def summary_stats(days: int = 7) -> dict:
    events = get_events_with_responses(days)
    stats = {"lean": _source_stats(events, "lean"), "v1": _source_stats(events, "v1")}
    stats["total_events"] = len(events)
    stats["days"] = days
    return stats


def _source_stats(events: list[dict], source: str) -> dict:
    source_events = [e for e in events if e.get("source") == source]
    if not source_events:
        return {"count": 0, "accepted": 0, "rejected": 0, "ignored": 0, "modified": 0,
                "acceptance_rate": 0.0, "avg_latency_ms": 0.0}
    responded = [e for e in source_events if e.get("user_response")]
    accepted = sum(1 for e in responded if e["user_response"] == "accepted")
    rejected = sum(1 for e in responded if e["user_response"] == "rejected")
    modified = sum(1 for e in responded if e["user_response"] == "modified")
    ignored = len(source_events) - len(responded)
    latencies = [e["latency_ms"] for e in source_events if "latency_ms" in e]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    acceptance_rate = accepted / len(responded) if responded else 0.0
    return {
        "count": len(source_events), "accepted": accepted, "rejected": rejected,
        "modified": modified, "ignored": ignored,
        "acceptance_rate": round(acceptance_rate, 3),
        "avg_latency_ms": round(avg_latency, 1),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Git Automation Metrics")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    stats = summary_stats(args.days)
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"Git Automation Metrics ({args.days} days)")
        print(f"Total events: {stats['total_events']}")
        for source in ("lean", "v1"):
            s = stats[source]
            print(f"\n  [{source.upper()}]")
            print(f"    Suggestions: {s['count']}")
            print(f"    Accepted: {s['accepted']} | Rejected: {s['rejected']} | Modified: {s['modified']} | Ignored: {s['ignored']}")
            print(f"    Acceptance rate: {s['acceptance_rate']:.1%}")
            print(f"    Avg latency: {s['avg_latency_ms']:.0f}ms")


if __name__ == "__main__":
    main()
