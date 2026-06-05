#!/usr/bin/env python3
"""
Seed Cortex intelligence from existing data sources.

Populates:
  1. SpecKnowledgeBase (ChromaDB) — from outcomes.jsonl + recent git commits + GOALS.md
  2. PortfolioMemory (project_index.json) — from git log per project

Run manually or from morning_processor after a successful overnight batch.

Usage:
    python3 cortex/scripts/seed_intelligence.py
    python3 cortex/scripts/seed_intelligence.py --projects vortex cortex
"""

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import os as _os

REPO_ROOT = Path(_os.environ.get("CORTEX_DEV_ROOT", str(Path.home() / "Dev")))
CORTEX_DIR = Path.home() / ".cortex"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cortex"))


def seed_from_outcomes(kb, limit: int = 200):
    """Index outcomes.jsonl into SpecKnowledgeBase."""
    outcomes_file = CORTEX_DIR / "outcomes.jsonl"
    if not outcomes_file.exists():
        print("  No outcomes.jsonl found, skipping")
        return 0

    outcomes = [json.loads(l) for l in outcomes_file.read_text().splitlines() if l.strip()]
    # Only successful/followed outcomes are worth indexing
    signal = [o for o in outcomes if o.get("followed") or o.get("outcome") == "success"]
    signal = signal[-limit:]  # most recent

    indexed = 0
    for o in signal:
        title = o.get("recommendation_title", "outcome")
        project = o.get("domain") or "general"
        rec_type = o.get("recommendation_type", "general")
        outcome = o.get("outcome", "unknown")
        ts = o.get("timestamp", "")[:10]
        text = f"{title}\nType: {rec_type}\nOutcome: {outcome}\nDate: {ts}"
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
        doc_id = f"outcome_{content_hash}"
        try:
            kb.index_text(text, title=title, project=project, domain=rec_type, doc_id=doc_id)
            indexed += 1
        except Exception as e:
            print(f"  Warning: failed to index outcome '{title}': {e}")

    return indexed


def seed_from_git(kb, projects: list):
    """Index recent git commits per project into SpecKnowledgeBase."""
    indexed = 0
    for project in projects:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--since=60 days ago", "--", f"{project}/"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            if not lines:
                continue
            text = f"Recent work in {project} (last 60 days):\n" + "\n".join(lines[:30])
            kb.index_text(
                text,
                title=f"{project} recent commits",
                project=project,
                domain="git_history",
                doc_id=f"git_{project}_recent",
            )
            indexed += 1
        except Exception as e:
            print(f"  Warning: git index failed for {project}: {e}")
    return indexed


def seed_from_goals(kb):
    """Index pending GOALS.md items into SpecKnowledgeBase."""
    goals_file = REPO_ROOT / "GOALS.md"
    if not goals_file.exists():
        return 0

    text = goals_file.read_text()
    pending = [l.strip() for l in text.splitlines() if l.strip().startswith("- [ ]")]
    if not pending:
        return 0

    content = "Pending work items from GOALS.md:\n" + "\n".join(pending[:40])
    try:
        kb.index_text(
            content,
            title="Active GOALS.md work items",
            project="root",
            domain="goals",
            doc_id="goals_pending_current",
        )
        return 1
    except Exception as e:
        print(f"  Warning: goals index failed: {e}")
        return 0


def seed_portfolio_memory(portfolio, projects: list):
    """Populate portfolio_memory from git history per project."""
    seeded = 0
    for project in projects:
        project_dir = REPO_ROOT / project
        if not project_dir.exists():
            continue
        try:
            # Get recent commits
            result = subprocess.run(
                ["git", "log", "--oneline", "-20", "--", f"{project}/"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            commits = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]

            # Get language composition
            py_count = len(list(project_dir.rglob("*.py")))
            ts_count = len(list(project_dir.rglob("*.ts"))) + len(list(project_dir.rglob("*.tsx")))
            languages = []
            if py_count > 0:
                languages.append("Python")
            if ts_count > 0:
                languages.append("TypeScript")

            portfolio.store_deep_analysis(
                project=project,
                tech_stack={"languages": languages, "py_files": py_count, "ts_files": ts_count},
                architecture={"recent_commits": commits[:10]},
                code_quality={"seeded_at": datetime.now(timezone.utc).isoformat()},
            )
            seeded += 1
        except Exception as e:
            print(f"  Warning: portfolio seed failed for {project}: {e}")
    return seeded


def main():
    parser = argparse.ArgumentParser(description="Seed Cortex intelligence from existing data")
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["cortex", "Vortex/backend", "Vortex/frontend", "alpha_arena", "pupil"],
        help="Projects to include in git/portfolio seeding",
    )
    parser.add_argument(
        "--outcomes-limit", type=int, default=200, help="Max outcomes to index (most recent)"
    )
    args = parser.parse_args()

    from cortex.intelligence.spec_knowledge_base import SpecKnowledgeBase
    from cortex.portfolio_memory import PortfolioMemory

    print("=== Cortex Intelligence Seeder ===")

    print("\n[1/3] Seeding SpecKnowledgeBase (ChromaDB)...")
    kb = SpecKnowledgeBase()
    before = kb.collection.count()
    print(f"  Collection before: {before} docs")

    n1 = seed_from_outcomes(kb, limit=args.outcomes_limit)
    print(f"  Indexed {n1} outcomes")

    n2 = seed_from_git(kb, args.projects)
    print(f"  Indexed {n2} project git histories")

    n3 = seed_from_goals(kb)
    print(f"  Indexed {n3} goals document")

    after = kb.collection.count()
    print(f"  Collection after: {after} docs (+{after - before})")

    print("\n[2/3] Seeding PortfolioMemory (project_index.json)...")
    portfolio = PortfolioMemory()
    n4 = seed_portfolio_memory(portfolio, args.projects)
    print(f"  Seeded {n4} projects")

    print("\n[3/3] Verification — bridge query test...")
    try:
        from cortex.intelligence.unified_intelligence import UnifiedIntelligence
        from cortex.intelligence.models import IntelligenceQueryType

        ui = UnifiedIntelligence(root_dir=REPO_ROOT)
        result = ui.query(
            "recent wins and blockers", project="cortex", query_type=IntelligenceQueryType.research
        )
        print(f"  similar_work: {len(result.similar_work)} results")
        print(f"  lessons: {len(result.lessons)}")
        print(f"  patterns: {len(result.applicable_patterns)}")
        print(f"  confidence: {result.overall_confidence:.0%}")
        if result.similar_work:
            print(f"  Top result: {result.similar_work[0].title[:60]}")
    except Exception as e:
        print(f"  Bridge query failed: {e}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
