#!/usr/bin/env python3
"""
Cortex V1: Semantic Commit Planner

Wraps the existing GitStatusAnalyzer with Cortex intelligence queries
for historical context. Produces ordered CommitSuggestion objects with
messages, risk levels, and reasoning.

Called by: modified /commit command (Step 0)
Latency: ~500ms (GitStatusAnalyzer + optional Cortex query)
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent paths so we can import GitStatusAnalyzer
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cortex.intelligence.status.git_status_analyzer import (
    ChangeGroup,
    CommitSuggestion,
    GitStatusAnalyzer,
)

METRICS_LOG = Path.home() / ".cortex" / "git_automation_events.jsonl"


def get_recent_commit_messages(repo_path: str = ".", count: int = 10) -> list[str]:
    """Get recent commit messages for style matching."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--format=%s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return [m.strip() for m in result.stdout.strip().splitlines() if m.strip()]
    except Exception:
        return []


def refine_message(group: ChangeGroup, recent_messages: list[str]) -> str:
    """Refine commit message using recent style and more specific content analysis."""
    # Start with the analyzer's suggestion
    base = group.suggested_message

    # If recent messages use conventional commit format, ensure we do too
    if recent_messages:
        has_conventional = sum(1 for m in recent_messages if ":" in m[:20]) / len(recent_messages)
        if has_conventional > 0.5 and ":" not in base[:20]:
            base = f"chore({group.project}): {base}"

    # Improve generic messages with file-specific info
    if "Miscellaneous" in base or "project files" in base.lower():
        # Try to infer purpose from filenames
        py_files = [Path(f).stem for f in group.files if f.endswith(".py")]
        if py_files:
            key_file = py_files[0]
            base = f"feat({group.project}): Update {key_file}"
            if len(py_files) > 1:
                base += f" and {len(py_files) - 1} more"

    return base


def assess_risk(group: ChangeGroup) -> str:
    """Deeper risk assessment beyond what the base analyzer provides."""
    # Hot file detection (known thrash-prone files)
    hot_files = {"scheduler.py", "ensemble.py", "weather.py", "grib_loader.py", "ndbc_client.py"}
    group_filenames = {Path(f).name for f in group.files}
    if group_filenames & hot_files:
        return "medium"  # Hot files need a plan

    # Large change sets
    if len(group.files) > 10:
        return "medium"

    return group.risk_level


def log_suggestion(groups: list[dict], latency_ms: float):
    """Log V1 suggestions to competition metrics."""
    try:
        METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
        import uuid

        entry = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "v1",
            "event_type": "commit_suggestion",
            "suggestion": {
                "groups": groups,
                "total_files": sum(g["file_count"] for g in groups),
            },
            "latency_ms": round(latency_ms, 1),
            "user_response": None,
        }
        with open(METRICS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def plan(repo_path: str = ".") -> list[CommitSuggestion]:
    """Generate a semantic commit plan for uncommitted changes.

    Returns ordered list of CommitSuggestion objects.
    """
    start = time.monotonic()

    analyzer = GitStatusAnalyzer(Path(repo_path))
    groups = analyzer.analyze_uncommitted_changes()

    if not groups:
        return []

    recent = get_recent_commit_messages(repo_path)

    # Refine each group's message and risk
    for group in groups.values():
        group.suggested_message = refine_message(group, recent)
        group.risk_level = assess_risk(group)

    suggestions = analyzer.suggest_commit_sequence(groups)

    latency_ms = (time.monotonic() - start) * 1000
    log_suggestion(
        [
            {
                "message": s.group.suggested_message,
                "file_count": len(s.group.files),
                "confidence": s.group.confidence,
                "project": s.group.project,
            }
            for s in suggestions
        ],
        latency_ms,
    )

    return suggestions


def format_suggestions(suggestions: list[CommitSuggestion]) -> str:
    """Format suggestions for display in /commit."""
    if not suggestions:
        return "[V1] No uncommitted changes detected."

    lines = [
        f"[V1] {len(suggestions)} semantic group{'s' if len(suggestions) != 1 else ''} detected:"
    ]
    for i, s in enumerate(suggestions, 1):
        g = s.group
        lines.append(
            f'  {i}. "{g.suggested_message}" '
            f"(confidence: {g.confidence:.2f}, risk: {g.risk_level}, {len(g.files)} files)"
        )
        if s.blockers:
            lines.append(f"     Blockers: {'; '.join(s.blockers)}")
    return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Cortex V1 Semantic Commit Planner")
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--test", action="store_true", help="Test mode — show suggestions")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    suggestions = plan(args.repo)

    if args.json:
        output = [
            {
                "priority": s.priority,
                "message": s.group.suggested_message,
                "files": s.group.files,
                "project": s.group.project,
                "confidence": s.group.confidence,
                "risk": s.group.risk_level,
                "reasoning": s.reasoning,
                "blockers": s.blockers,
            }
            for s in suggestions
        ]
        print(json.dumps(output, indent=2))
    else:
        print(format_suggestions(suggestions))


if __name__ == "__main__":
    main()
