#!/usr/bin/env python3
"""Analyze Claude Code interaction patterns from interaction_queue.jsonl.

This script surfaces actionable insights from the captured tool usage data.
"""

import json
from collections import defaultdict
from pathlib import Path


def load_interactions(path: Path) -> list[dict]:
    """Load interactions from JSONL file."""
    interactions = []
    with open(path) as f:
        for line in f:
            try:
                interactions.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return interactions


def analyze_tool_success(interactions: list[dict]) -> dict:
    """Analyze success rates by tool."""
    stats = defaultdict(lambda: {"success": 0, "fail": 0})
    for i in interactions:
        tool = i.get("tool_name", "unknown")
        if i.get("success"):
            stats[tool]["success"] += 1
        else:
            stats[tool]["fail"] += 1

    # Calculate rates
    results = {}
    for tool, data in stats.items():
        total = data["success"] + data["fail"]
        if total > 0:
            results[tool] = {
                "success": data["success"],
                "fail": data["fail"],
                "total": total,
                "rate": round(data["success"] / total * 100, 1),
            }
    return dict(sorted(results.items(), key=lambda x: x[1]["total"], reverse=True))


def analyze_projects(interactions: list[dict]) -> dict:
    """Analyze work distribution by project."""
    projects = defaultdict(int)
    for i in interactions:
        cwd = i.get("cwd", "")
        parts = cwd.split("/")
        if "Dev" in parts:
            idx = parts.index("Dev")
            if idx + 1 < len(parts):
                projects[parts[idx + 1]] += 1
            else:
                projects["Dev (root)"] += 1
    return dict(sorted(projects.items(), key=lambda x: x[1], reverse=True))


def analyze_sessions(interactions: list[dict]) -> dict:
    """Analyze session patterns."""
    sessions = defaultdict(list)
    for i in interactions:
        sid = i.get("session_id", "unknown")
        sessions[sid].append(i)

    session_stats = []
    for sid, items in sessions.items():
        if items:
            session_stats.append(
                {
                    "id": sid[:8],
                    "interactions": len(items),
                    "tools_used": len(set(i.get("tool_name") for i in items)),
                    "success_rate": round(
                        sum(1 for i in items if i.get("success")) / len(items) * 100, 1
                    ),
                }
            )

    return {
        "total_sessions": len(sessions),
        "avg_interactions": (
            round(sum(s["interactions"] for s in session_stats) / len(session_stats), 1)
            if session_stats
            else 0
        ),
        "top_sessions": sorted(session_stats, key=lambda x: x["interactions"], reverse=True)[:5],
    }


def get_problem_patterns(tool_stats: dict) -> list[str]:
    """Identify tools with low success rates."""
    problems = []
    for tool, data in tool_stats.items():
        if data["total"] >= 10 and data["rate"] < 50:
            problems.append(f"• {tool}: {data['rate']}% success ({data['fail']} failures)")
    return problems


def main():
    queue_path = Path.home() / ".cortex" / "interaction_queue.jsonl"
    if not queue_path.exists():
        print("No interaction_queue.jsonl found")
        return

    interactions = load_interactions(queue_path)
    if not interactions:
        print("No interactions found")
        return

    # Get date range
    dates = [i.get("queued_at", "")[:10] for i in interactions if i.get("queued_at")]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "unknown"

    print("=" * 60)
    print("INTERACTION ANALYSIS")
    print("=" * 60)
    print(f"\nData range: {date_range}")
    print(f"Total interactions: {len(interactions)}")

    # Tool success rates
    print("\n--- Tool Success Rates ---")
    tool_stats = analyze_tool_success(interactions)
    print(f"{'Tool':<20} {'Success':>8} {'Fail':>8} {'Rate':>8}")
    print("-" * 46)
    for tool, data in list(tool_stats.items())[:12]:
        print(f"{tool:<20} {data['success']:>8} {data['fail']:>8} {data['rate']:>7}%")

    # Problem patterns
    problems = get_problem_patterns(tool_stats)
    if problems:
        print("\n--- Action Required: Low Success Tools ---")
        for p in problems:
            print(p)

    # Project distribution
    print("\n--- Work Distribution ---")
    projects = analyze_projects(interactions)
    total = sum(projects.values())
    for proj, count in list(projects.items())[:8]:
        pct = round(count / total * 100, 1)
        print(f"{proj:<25} {count:>6} ({pct}%)")

    # Meta-work ratio
    meta_work = projects.get("cortex", 0)
    if meta_work > 0:
        meta_pct = round(meta_work / total * 100, 1)
        if meta_pct > 10:
            print(f"\n⚠ Meta-work overhead: {meta_pct}% on Cortex itself")

    # Session stats
    print("\n--- Session Patterns ---")
    sessions = analyze_sessions(interactions)
    print(f"Total sessions: {sessions['total_sessions']}")
    print(f"Avg interactions/session: {sessions['avg_interactions']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
