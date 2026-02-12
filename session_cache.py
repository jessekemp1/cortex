#!/usr/bin/env python3
"""
Session Cache - Fast session context for startup hooks.

Writes session context to cache file for instant retrieval at startup.
Updates periodically via daemon or on-demand via commands.

Cache file: ~/.cortex/session_cache.json
TTL: 5 minutes (cache is "fresh enough" for startup)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

CACHE_FILE = Path.home() / ".cortex" / "session_cache.json"
CACHE_TTL = timedelta(minutes=5)


def get_session_cache() -> Optional[Dict]:
    """
    Read session cache if it exists and is fresh.

    Returns:
        Session context dict or None if cache is stale/missing
    """
    if not CACHE_FILE.exists():
        return None

    try:
        data = json.loads(CACHE_FILE.read_text())

        # Check freshness
        cached_at = datetime.fromisoformat(data.get("cached_at", ""))
        age = datetime.now() - cached_at

        if age > CACHE_TTL:
            return None  # Stale

        return data.get("context")
    except Exception:
        return None


def write_session_cache(context: Dict) -> bool:
    """
    Write session context to cache.

    Args:
        context: Session context dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {"cached_at": datetime.now().isoformat(), "context": context}

        CACHE_FILE.write_text(json.dumps(cache_data, indent=2))
        return True
    except Exception:
        return False


def get_pr_status() -> Dict:
    """
    Get GitHub PR status (fast - single gh command).

    Returns:
        Dict with open_prs count and details
    """
    import subprocess

    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--limit", "5", "--json", "number,title,isDraft,reviewDecision"],
            cwd=Path.home() / "Dev",
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            import json

            prs = json.loads(result.stdout)
            return {
                "open_prs": len(prs),
                "details": [
                    {
                        "number": pr["number"],
                        "title": pr["title"][:60],  # Truncate long titles
                        "status": pr.get("reviewDecision", "pending").lower(),
                    }
                    for pr in prs[:3]  # Top 3 PRs
                ],
            }
    except Exception:
        pass

    return {"open_prs": 0, "details": []}


def get_project_insights(project_name: str) -> Dict:
    """
    Get project-specific insights and context.

    Args:
        project_name: Name of the project

    Returns:
        Dict with project-specific insights
    """
    workspace = Path.home() / "Dev"
    insights = {"validation_alerts": [], "test_status": None, "deployment_needed": False}

    # VortexV2 specific insights
    if project_name == "VortexV2":
        try:
            # Check for validation reports indicating improvements
            validation_dir = workspace / "Vortex" / "VortexV2" / "data" / "validation"
            if validation_dir.exists():
                reports = list(validation_dir.glob("*REPORT*.md"))
                for report in reports[:3]:
                    content = report.read_text()
                    if any(
                        word in content.lower() for word in ["improvement", "better", "outperform"]
                    ):
                        insights["validation_alerts"].append(
                            f"Validated improvement in {report.stem.replace('_', ' ')}"
                        )
        except Exception:
            pass

    # Alpha Arena specific insights
    elif project_name == "Alpha Arena":
        try:
            # Check for recent competition logs
            comp_log = workspace / "alpha_arena" / "data" / "competition_log.jsonl"
            if comp_log.exists():
                insights["test_status"] = "Competition logs active"
        except Exception:
            pass

    # Cortex specific insights
    elif project_name == "Cortex":
        try:
            # Check for pending batch jobs
            batch_dir = Path.home() / ".cortex" / "batch"
            if batch_dir.exists():
                pending = list(batch_dir.glob("*.pending"))
                if pending:
                    insights["test_status"] = f"{len(pending)} batch jobs pending"
        except Exception:
            pass

    return insights


def build_fast_session_context() -> Dict:
    """
    Build session context using fast operations only.

    Avoids heavy imports - uses only:
    - Git commands (fast)
    - File system checks (fast)
    - GOALS.md parsing (fast)
    - GitHub CLI (fast, 2s timeout)
    - Project-specific file checks (fast)

    Returns:
        Session context dict
    """
    import subprocess

    context = {
        "project": "Unknown",
        "focus": "Unknown",
        "goals": [],
        "recent_work": [],
        "pr_status": {"open_prs": 0, "details": []},
        "insights": {},
    }

    # Detect project from current directory
    try:
        cwd = Path.cwd()
        if "VortexV2" in str(cwd) or (cwd / "Vortex" / "VortexV2").exists():
            context["project"] = "VortexV2"
        elif "alpha_arena" in str(cwd) or (cwd / "alpha_arena").exists():
            context["project"] = "Alpha Arena"
        elif "cortex" in str(cwd) or (cwd / "cortex").exists():
            context["project"] = "Cortex"
        elif "kempion-research-site" in str(cwd):
            context["project"] = "Kempion Research"
        elif "DJ-CoPilot" in str(cwd):
            context["project"] = "DJ-CoPilot"
        else:
            # Fallback - check workspace root
            workspace = Path.home() / "Dev"
            if workspace.exists():
                context["project"] = "Dev Workspace"
    except Exception:
        pass

    # Infer focus from recent commits
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%s"],
            cwd=Path.home() / "Dev",
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            msg = result.stdout.lower()
            if "test" in msg:
                context["focus"] = "Testing"
            elif "fix" in msg or "bug" in msg:
                context["focus"] = "Bug fixing"
            elif "feat" in msg or "add" in msg:
                context["focus"] = "Feature development"
            elif "perf" in msg or "optim" in msg:
                context["focus"] = "Performance optimization"
            elif "refactor" in msg:
                context["focus"] = "Refactoring"
            elif "doc" in msg:
                context["focus"] = "Documentation"
            else:
                context["focus"] = "Development"
    except Exception:
        pass

    # Get recent commits for context
    try:
        result = subprocess.run(
            ["git", "log", "-3", "--pretty=format:%s"],
            cwd=Path.home() / "Dev",
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            commits = result.stdout.strip().split("\n")
            context["recent_work"] = [{"summary": c} for c in commits if c]
    except Exception:
        pass

    # Parse goals from GOALS.md
    try:
        goals_file = Path.home() / "Dev" / "GOALS.md"
        if goals_file.exists():
            content = goals_file.read_text()
            goals = []
            for line in content.split("\n"):
                # Look for bullet points or numbered lists
                line = line.strip()
                if line.startswith("- [ ]") or line.startswith("*"):
                    goal = line.lstrip("- [ ]").lstrip("*").strip()
                    if goal and len(goal) > 10:  # Meaningful goals only
                        goals.append(goal)
                elif line.startswith(("1.", "2.", "3.")):
                    goal = line.split(".", 1)[1].strip()
                    if goal and len(goal) > 10:
                        goals.append(goal)

            context["goals"] = goals[:3]  # Top 3
    except Exception:
        pass

    # Get GitHub PR status (fast - 2s timeout)
    context["pr_status"] = get_pr_status()

    # Get project-specific insights
    context["insights"] = get_project_insights(context["project"])

    return context


def update_session_cache() -> bool:
    """
    Update session cache with current context.

    Returns:
        True if successful, False otherwise
    """
    context = build_fast_session_context()
    return write_session_cache(context)


def main():
    """CLI entry point for manual cache updates."""
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        print("Updating session cache...")
        if update_session_cache():
            print(f"✓ Session cache updated: {CACHE_FILE}")
        else:
            print("✗ Failed to update session cache")
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == "read":
        cache = get_session_cache()
        if cache:
            print(json.dumps(cache, indent=2))
        else:
            print("✗ No valid cache found")
            sys.exit(1)
    else:
        print("Usage: session_cache.py {update|read}")
        sys.exit(1)


if __name__ == "__main__":
    main()
