#!/usr/bin/env python3
"""
Cortex Deep Assessment Engine — Meta-cognitive system audit.

Goes beyond self_audit.py health checks to evaluate:
1. Awareness Completeness — blind spots, orphaned state, missing context
2. Learning Optimization — is the loop compounding? Router improving?
3. Plan Accuracy — GOALS.md vs reality, deadline tracking, priority ordering
4. Recommendation Quality — hit rate, followed rate, type effectiveness
5. Predictive Planning — compounding vs stalling patterns, next moves
6. Batch Optimization — overnight utilization, deferrable work identification
7. Automation Surface — manual work that could be automated

Usage:
    python cortex/deep_assessment.py              # full assessment
    python cortex/deep_assessment.py --json        # JSON output only
    python cortex/deep_assessment.py --dimension N # single dimension (1-7)
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import os

REPO_ROOT = Path(os.environ.get("CORTEX_DEV_ROOT", str(Path.home() / "Dev")))
CORTEX_DIR = Path.home() / ".cortex"
CLAUDE_DIR = Path.home() / ".claude"
# Derive Claude's projects-dir key from REPO_ROOT (Claude encodes the path
# with slashes replaced by dashes, e.g. /Users/foo/Dev -> -Users-foo-Dev).
MEMORY_DIR = CLAUDE_DIR / "projects" / (f"-{str(REPO_ROOT).replace('/', '-').lstrip('-')}") / "memory"
GOALS_FILE = REPO_ROOT / "GOALS.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
MEMORY_MD = MEMORY_DIR / "MEMORY.md"
OUTPUT_DIR = CORTEX_DIR / "metrics"
OUTPUT_FILE = OUTPUT_DIR / "deep_assessment.json"
HISTORY_FILE = OUTPUT_DIR / "deep_assessment_history.jsonl"

# Project directories for scanning
PROJECTS = {
    "vortex": REPO_ROOT / "Vortex" / "backend",
    "vortex_frontend": REPO_ROOT / "Vortex" / "frontend",
    "cortex": REPO_ROOT / "cortex",
    "alpha_arena": REPO_ROOT / "alpha_arena",
    "pupil": REPO_ROOT / "pupil",
    "ore": REPO_ROOT / "ore",
    "from_within": REPO_ROOT / "from-within",
}

# Projects with their own git repo (submodules) — run git log with their cwd
SUBMODULE_PROJECTS = {
    "kempion_site": REPO_ROOT / "kempion-research-site",
}

# Projects that are primarily in ops/data-collection phase (low commit rate is expected)
# Key: project name, Value: GOALS.md keyword to detect ops phase
OPS_PHASE_PROJECTS = {
    "alpha_arena": "cold-start",
    "vortex": "parallel validation",
    "vortex_frontend": "parallel validation",
}


@dataclass
class Finding:
    """A single assessment finding."""

    dimension: str
    severity: str  # "info", "warning", "action", "critical"
    title: str
    detail: str
    recommendation: str
    automatable: bool = False
    batchable: bool = False


@dataclass
class DimensionScore:
    """Score for a single assessment dimension."""

    name: str
    score: float  # 0.0 - 1.0
    grade: str  # A, B, C, D, F
    findings: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


@dataclass
class AssessmentReport:
    """Complete deep assessment report."""

    timestamp: str
    overall_score: float
    overall_grade: str
    dimensions: dict = field(default_factory=dict)
    compound_trajectory: str = ""  # "accelerating", "steady", "decelerating", "stalling"
    next_actions: list = field(default_factory=list)
    batch_candidates: list = field(default_factory=list)
    automation_opportunities: list = field(default_factory=list)


def _score_to_grade(score: float) -> str:
    if score >= 0.9:
        return "A"
    elif score >= 0.75:
        return "B"
    elif score >= 0.6:
        return "C"
    elif score >= 0.4:
        return "D"
    return "F"


def _run_cmd(cmd: str, cwd: str = None) -> str:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(cwd) if cwd else str(REPO_ROOT),
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _load_jsonl(path: Path) -> list[dict]:
    entries = []
    if not path.exists():
        return entries
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return entries


# ═══════════════════════════════════════════════════════════════
# Dimension 1: Awareness Completeness
# ═══════════════════════════════════════════════════════════════


def assess_awareness() -> DimensionScore:
    """Does Cortex know about everything it should?"""
    findings = []
    metrics = {}
    score_components = []

    # 1a. State file coverage — are all projects represented in MEMORY.md?
    memory_text = MEMORY_MD.read_text() if MEMORY_MD.exists() else ""
    projects_mentioned = 0
    for proj in ["vortex", "cortex", "alpha_arena", "pupil", "dj-copilot"]:
        if (
            proj.replace("_", " ") in memory_text.lower()
            or proj.replace("_", "-") in memory_text.lower()
            or proj in memory_text.lower()
        ):
            projects_mentioned += 1
    project_coverage = projects_mentioned / 5
    metrics["project_coverage"] = f"{projects_mentioned}/5"
    score_components.append(project_coverage)

    if project_coverage < 1.0:
        missing = [
            p
            for p in ["vortex", "cortex", "alpha_arena", "pupil", "dj-copilot"]
            if p.replace("_", " ") not in memory_text.lower() and p not in memory_text.lower()
        ]
        findings.append(
            Finding(
                "awareness",
                "warning",
                "Missing project coverage in MEMORY.md",
                f"Projects not tracked: {', '.join(missing)}",
                "Add project health entries for missing projects",
            )
        )

    # 1b. Memory satellite file freshness
    satellite_count = 0
    stale_count = 0
    if MEMORY_DIR.exists():
        threshold = datetime.now(timezone.utc) - timedelta(days=14)
        for f in MEMORY_DIR.iterdir():
            if f.is_file() and f.suffix == ".md" and f.name != "MEMORY.md":
                satellite_count += 1
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    if mtime < threshold:
                        stale_count += 1
                except Exception:
                    continue

    metrics["satellite_files"] = satellite_count
    metrics["stale_satellites"] = stale_count
    stale_ratio = stale_count / max(satellite_count, 1)
    score_components.append(1.0 - stale_ratio)
    if stale_count > 3:
        findings.append(
            Finding(
                "awareness",
                "info",
                f"{stale_count} stale memory satellites (>14d)",
                "Some memory files may contain outdated information",
                "Review and update or archive stale satellites during /eod",
            )
        )

    # 1c. Cortex database coverage — are outcomes, predictions being written?
    outcomes = _load_jsonl(CORTEX_DIR / "outcomes.jsonl")
    model_outcomes = _load_jsonl(CORTEX_DIR / "model_outcomes.jsonl")
    metrics["outcome_entries"] = len(outcomes)
    metrics["model_outcome_entries"] = len(model_outcomes)

    # Check outcome freshness
    if outcomes:
        try:
            last_ts = outcomes[-1].get("timestamp", "")
            if last_ts:
                last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - last_dt).days
                metrics["outcome_freshness_days"] = days_old
                score_components.append(1.0 if days_old <= 3 else 0.7 if days_old <= 7 else 0.3)
                if days_old > 7:
                    findings.append(
                        Finding(
                            "awareness",
                            "warning",
                            f"Outcomes stale ({days_old}d)",
                            "Learning loop not receiving fresh data",
                            "Run /sync and verify outcome recording is active",
                        )
                    )
        except Exception:
            pass

    # 1d. CLAUDE.md gotcha accuracy — spot-check a few claims
    claude_text = CLAUDE_MD.read_text() if CLAUDE_MD.exists() else ""
    # Check command count claim
    cmd_match = re.search(r"~(\d+)\s+available", claude_text)
    if cmd_match:
        claimed_count = int(cmd_match.group(1))
        actual_commands = (
            len(list((REPO_ROOT / ".claude" / "commands").glob("*.md")))
            if (REPO_ROOT / ".claude" / "commands").exists()
            else 0
        )
        metrics["claimed_commands"] = claimed_count
        metrics["actual_commands"] = actual_commands
        if abs(actual_commands - claimed_count) > 5:
            findings.append(
                Finding(
                    "awareness",
                    "warning",
                    f"CLAUDE.md command count drift: claims ~{claimed_count}, actual {actual_commands}",
                    "Stale documentation leads to wrong expectations",
                    f"Update CLAUDE.md: ~{claimed_count} → ~{actual_commands}",
                )
            )
            score_components.append(0.7)
        else:
            score_components.append(1.0)

    # 1e. Agent count accuracy
    agent_match = re.search(r"(\d+)\s+agents", claude_text)
    if agent_match:
        claimed_agents = int(agent_match.group(1))
        actual_agents = (
            len(list((REPO_ROOT / ".claude" / "agents").glob("*.md")))
            if (REPO_ROOT / ".claude" / "agents").exists()
            else 0
        )
        metrics["claimed_agents"] = claimed_agents
        metrics["actual_agents"] = actual_agents
        if actual_agents != claimed_agents:
            findings.append(
                Finding(
                    "awareness",
                    "info",
                    f"Agent count: CLAUDE.md says {claimed_agents}, actual {actual_agents}",
                    "After adding new agents, update CLAUDE.md",
                    f"Update CLAUDE.md agent count to {actual_agents}",
                )
            )

    score = sum(score_components) / max(len(score_components), 1)
    return DimensionScore(
        "Awareness Completeness", score, _score_to_grade(score), findings, metrics
    )


# ═══════════════════════════════════════════════════════════════
# Dimension 2: Learning Optimization
# ═══════════════════════════════════════════════════════════════


def assess_learning() -> DimensionScore:
    """Is the learning loop producing compound returns?"""
    findings = []
    metrics = {}
    score_components = []

    # 2a. Outcome volume and growth rate
    outcomes = _load_jsonl(CORTEX_DIR / "outcomes.jsonl")
    metrics["total_outcomes"] = len(outcomes)

    if len(outcomes) >= 10:
        # Calculate growth: outcomes per week over last 4 weeks
        now = datetime.now(timezone.utc)
        weekly_counts = [0, 0, 0, 0]  # [this week, last week, 2 ago, 3 ago]
        for entry in outcomes:
            try:
                ts = entry.get("timestamp", "")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    weeks_ago = (now - dt).days // 7
                    if 0 <= weeks_ago < 4:
                        weekly_counts[weeks_ago] += 1
            except Exception:
                continue

        metrics["outcomes_weekly"] = weekly_counts
        # Growth = is this week > median of prior 3?
        # Use median (not mean) to avoid backfill spikes inflating the baseline
        prior_sorted = sorted(weekly_counts[1:])
        prior_avg = prior_sorted[1] if sum(weekly_counts[1:]) > 0 else 0
        current = weekly_counts[0]
        if prior_avg > 0:
            growth_ratio = current / prior_avg
            metrics["outcome_growth_ratio"] = round(growth_ratio, 2)
            score_components.append(min(growth_ratio, 1.0))
            if growth_ratio < 0.5:
                findings.append(
                    Finding(
                        "learning",
                        "warning",
                        f"Learning velocity declining ({current} this week vs {prior_avg:.0f} avg)",
                        "Fewer outcomes being recorded means slower improvement",
                        "Check if outcome recording hooks are active in feedback.py",
                    )
                )
        else:
            score_components.append(0.3)
    else:
        score_components.append(0.2)
        findings.append(
            Finding(
                "learning",
                "action",
                f"Low outcome volume ({len(outcomes)} total)",
                "Not enough data for the learning loop to compound",
                "Ensure all recommendations produce logged outcomes",
            )
        )

    # 2b. Success rate of followed recommendations
    # Exclude automated Arena strategy_outcome entries with empty strategies —
    # these log "partial"/"failed" even when the competition is healthy (no signal)
    followed = [
        o
        for o in outcomes
        if o.get("followed")
        and not (o.get("recommendation_type") == "strategy_outcome" and not o.get("strategies"))
    ]
    successful = [o for o in followed if o.get("outcome") == "success"]
    metrics["followed_count"] = len(followed)
    metrics["success_count"] = len(successful)

    if len(followed) >= 5:
        success_rate = len(successful) / len(followed)
        metrics["success_rate"] = round(success_rate, 3)
        score_components.append(success_rate)
        if success_rate < 0.6:
            findings.append(
                Finding(
                    "learning",
                    "action",
                    f"Low recommendation success rate ({success_rate:.0%})",
                    "Recommendations that are followed but fail waste effort",
                    "Analyze failed recommendations by type to improve targeting",
                    batchable=True,
                )
            )
    else:
        score_components.append(0.5)  # neutral — insufficient data

    # 2c. Model router improvement (are we spending less per successful task?)
    model_outcomes = _load_jsonl(CORTEX_DIR / "model_outcomes.jsonl")
    if len(model_outcomes) >= 20:
        # Compare cost efficiency: first half vs second half
        mid = len(model_outcomes) // 2
        first_half = model_outcomes[:mid]
        second_half = model_outcomes[mid:]

        def avg_cost_per_success(entries):
            successes = [e for e in entries if e.get("success")]
            if not successes:
                return 0
            total_cost = sum(e.get("cost_usd", 0) for e in successes)
            return total_cost / len(successes) if successes else 0

        cost_early = avg_cost_per_success(first_half)
        cost_recent = avg_cost_per_success(second_half)
        metrics["cost_per_success_early"] = round(cost_early, 4)
        metrics["cost_per_success_recent"] = round(cost_recent, 4)

        if cost_early > 0:
            efficiency_ratio = cost_recent / cost_early
            metrics["router_efficiency_trend"] = round(efficiency_ratio, 2)
            # Lower cost = better (ratio < 1.0 means improving)
            score_components.append(min(1.0, 1.0 / max(efficiency_ratio, 0.5)))
            if efficiency_ratio > 1.2:
                findings.append(
                    Finding(
                        "learning",
                        "warning",
                        f"Router cost efficiency degrading ({efficiency_ratio:.1f}x)",
                        "Recent tasks cost more per success than earlier ones",
                        "Review model_outcomes.jsonl — router may be over-escalating to opus",
                        batchable=True,
                    )
                )
    else:
        metrics["model_outcomes_count"] = len(model_outcomes)

    # 2d. Outcome type distribution — are we learning from diverse signals?
    type_dist = Counter(o.get("recommendation_type", "unknown") for o in outcomes)
    metrics["outcome_types"] = dict(type_dist.most_common(10))
    diversity = len(type_dist)
    score_components.append(min(diversity / 5, 1.0))  # 5+ types = full score
    if diversity <= 2:
        findings.append(
            Finding(
                "learning",
                "info",
                f"Low outcome diversity ({diversity} types)",
                "Learning concentrated in few areas limits compound learning",
                "Wire outcome recording for more recommendation types",
            )
        )

    score = sum(score_components) / max(len(score_components), 1)
    return DimensionScore("Learning Optimization", score, _score_to_grade(score), findings, metrics)


# ═══════════════════════════════════════════════════════════════
# Dimension 3: Plan Accuracy
# ═══════════════════════════════════════════════════════════════


def assess_plan_accuracy() -> DimensionScore:
    """Does GOALS.md match reality? Deadlines tracking?"""
    findings = []
    metrics = {}
    score_components = []

    goals_text = GOALS_FILE.read_text() if GOALS_FILE.exists() else ""

    # On-hold item support: - [~] marker means intentionally paused
    # Count and track separately; never surface as open work
    on_hold_items = re.findall(r"- \[~\].*", goals_text)
    metrics["on_hold_items"] = len(on_hold_items)
    if on_hold_items:
        metrics["on_hold_samples"] = [i.replace("- [~] ", "")[:60] for i in on_hold_items[:3]]

    # 3a. Deadline tracking — extract dates, check if past-due
    # Skip goals where Status line contains DONE/COMPLETE/ON HOLD
    today = datetime.now(timezone.utc).date()
    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    deadlines_found = 0
    deadlines_overdue = 0
    deadlines_at_risk = []  # approaching within 3 days

    for match in re.finditer(r"\*\*Target:\*\*\s*(.*?)(?:\||$)", goals_text):
        target_str = match.group(1).strip()
        date_match = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})", target_str
        )
        if not date_match:
            continue
        # Check if this goal's Status is already DONE/COMPLETE
        context_before = goals_text[max(0, match.start() - 300) : match.start()]
        status_match = re.search(r"\*\*Status:\*\*\s*(.*?)(?:\n|$)", context_before)
        if status_match:
            status_val = status_match.group(1).upper()
            if any(word in status_val for word in ["DONE", "COMPLETE", "ON HOLD", "ARCHIVED"]):
                continue  # skip — goal is resolved
        deadlines_found += 1
        month = month_map.get(date_match.group(1), 3)
        day = int(date_match.group(2))
        try:
            target_date = datetime(2026, month, day).date()
            days_until = (target_date - today).days
            if target_date < today:
                deadlines_overdue += 1
            elif days_until <= 3:
                goal_ctx = goals_text[max(0, match.start() - 200) : match.start()]
                goal_name_m = re.search(r"###\s+Goal\s+\d+:\s*(.+)", goal_ctx)
                deadlines_at_risk.append(
                    {
                        "name": goal_name_m.group(1).strip() if goal_name_m else "unknown",
                        "days_until": days_until,
                        "date": target_date.isoformat(),
                    }
                )
        except ValueError:
            continue

    metrics["deadlines_found"] = deadlines_found
    metrics["deadlines_overdue"] = deadlines_overdue
    metrics["deadlines_at_risk"] = deadlines_at_risk
    if deadlines_found > 0:
        on_time_ratio = 1.0 - (deadlines_overdue / deadlines_found)
        score_components.append(on_time_ratio)
        if deadlines_overdue > 0:
            findings.append(
                Finding(
                    "plan",
                    "action",
                    f"{deadlines_overdue}/{deadlines_found} deadlines overdue",
                    "Overdue targets signal scope creep or unrealistic planning",
                    "Update GOALS.md: revise dates or mark as deprioritized",
                )
            )

    # 3b. Goal staleness — goals marked IN PROGRESS but no recent commits
    in_progress_goals = re.findall(
        r"###\s+Goal\s+(\d+):.*?\n.*?Status:\*\*\s*(.*?)(?:\n|$)", goals_text
    )
    for goal_num, status in in_progress_goals:
        if "IN PROGRESS" in status.upper() or "PROGRESS" in status.upper():
            # Check for recent commits touching related files
            metrics[f"goal_{goal_num}_status"] = status.strip()

    # 3c. Current week's open items — scan "This Week" subsection + "Immediate Actions"
    # Strategy: find most recent "### This Week" or "### Mar" section with unchecked items
    this_week_pending = []

    # Scan all subsections under Immediate Actions
    imm_start = goals_text.find("## Immediate Actions")
    imm_end = goals_text.find("\n## ", imm_start + 1) if imm_start >= 0 else -1
    immediate_body = goals_text[imm_start : imm_end if imm_end > 0 else len(goals_text)]

    # Find the most recent "This Week" or "Current" subsection
    week_section_match = None
    for m in re.finditer(r"###\s+(This Week|Current Week|Mar \d+)", immediate_body):
        week_section_match = m  # keep last (most recent)

    if week_section_match:
        week_start = week_section_match.start()
        next_subsection = re.search(r"\n###", immediate_body[week_start + 1 :])
        week_end = (
            week_start + 1 + next_subsection.start() if next_subsection else len(immediate_body)
        )
        week_body = immediate_body[week_start:week_end]
        this_week_pending = re.findall(r"- \[ \] (.+)", week_body)

    # Full section counts
    checked = len(re.findall(r"- \[x\]", immediate_body))
    unchecked = len(re.findall(r"- \[ \]", immediate_body))
    on_hold_count = len(re.findall(r"- \[~\]", immediate_body))
    total = checked + unchecked + on_hold_count

    metrics["immediate_total"] = total
    metrics["immediate_complete"] = checked
    metrics["immediate_pending"] = unchecked
    metrics["immediate_on_hold"] = on_hold_count
    metrics["this_week_pending"] = len(this_week_pending)
    metrics["this_week_sample"] = [i[:70] for i in this_week_pending[:3]]

    completion_ratio = checked / max(total, 1)
    score_components.append(min(completion_ratio + 0.3, 1.0))

    if unchecked > 15:
        findings.append(
            Finding(
                "plan",
                "warning",
                f"{unchecked} open items in Immediate Actions (this week: {len(this_week_pending)})",
                "High open count suggests over-commitment or stale items",
                "Prune to 5-7 active items, move rest to on-hold [~] or backlog",
            )
        )
    elif unchecked > 0 and len(this_week_pending) > 0:
        findings.append(
            Finding(
                "plan",
                "info",
                f"This week: {len(this_week_pending)} open, {on_hold_count} on hold",
                f"Next: {this_week_pending[0][:80]}" if this_week_pending else "",
                "Work through this week's items before adding new ones",
            )
        )

    if checked > 20:
        findings.append(
            Finding(
                "plan",
                "info",
                f"{checked} completed items still in Immediate Actions",
                "Completed items add noise, making it harder to see what's pending",
                "Archive completed items to 'Completed' subsections",
                automatable=True,
            )
        )

    # 3c-2. New goal detection — goals recently added with no completed items yet
    new_goals_with_items = []
    for goal_match in re.finditer(
        r"###\s+Goal\s+(\d+):\s*(.+?)\n(.*?)(?=###\s+Goal|\Z)", goals_text, re.DOTALL
    ):
        goal_body = goal_match.group(3)
        has_done = bool(re.search(r"- \[x\]", goal_body))
        open_items = re.findall(r"- \[ \] (.+)", goal_body)
        if not has_done and open_items:
            # New goal: no done items, has open items
            new_goals_with_items.append(
                {
                    "goal": goal_match.group(2).strip()[:50],
                    "first_item": open_items[0][:70],
                    "open_count": len(open_items),
                }
            )

    metrics["new_goals_detected"] = len(new_goals_with_items)
    if new_goals_with_items:
        summary = "; ".join(
            f"Goal: {g['goal']} ({g['open_count']} items)" for g in new_goals_with_items[:3]
        )
        findings.append(
            Finding(
                "plan",
                "action",
                f"{len(new_goals_with_items)} new goal(s) with unstarted work",
                f"Not yet in weekly plan: {summary}",
                "Add first item from each new goal to 'This Week' section",
            )
        )

    # 3c-3. Dependency chain analysis — [!] blocked items
    # Format: - [!] item text (blocked by: dependency name)
    blocked_items = re.findall(r"- \[!\] (.+)", goals_text)
    metrics["blocked_items"] = len(blocked_items)

    unresolved_blockers = []
    for item in blocked_items:
        # Extract dependency: "... (blocked by: X)"
        blocker_match = re.search(r"\(blocked by:\s*(.+?)\)", item, re.IGNORECASE)
        if blocker_match:
            blocker = blocker_match.group(1).strip()
            # Check if blocker is resolved (appears as [x] item in goals)
            blocker_resolved = bool(
                re.search(rf"- \[x\].*{re.escape(blocker[:20])}", goals_text, re.IGNORECASE)
            )
            if not blocker_resolved:
                unresolved_blockers.append(
                    {
                        "item": item[:60],
                        "blocker": blocker[:50],
                        "resolved": False,
                    }
                )

    metrics["unresolved_blockers"] = len(unresolved_blockers)
    if unresolved_blockers:
        blocker_summary = "; ".join(
            f'"{b["item"][:40]}" ← {b["blocker"]}' for b in unresolved_blockers[:2]
        )
        findings.append(
            Finding(
                "plan",
                "warning",
                f"{len(unresolved_blockers)} item(s) blocked by unresolved dependencies",
                blocker_summary,
                "Resolve blockers first, or re-mark as [~] on-hold if deprioritised",
            )
        )

    # 3d. Priority ordering — are P1 items actually being worked on more than P2?
    p1_items = len(re.findall(r"\*\*Priority:\*\*\s*P1", goals_text))
    p2_items = len(re.findall(r"\*\*Priority:\*\*\s*P2", goals_text))
    metrics["p1_count"] = p1_items
    metrics["p2_count"] = p2_items

    # Check recent commits for P1 vs P2 work
    recent_commits = _run_cmd("git log --oneline -20 --format='%s'")
    if recent_commits:
        p1_keywords = ["hetzner", "cortex beta", "cortex launch", "zenodo", "migration"]
        p2_keywords = ["alpha arena", "pupil", "energy", "react"]
        p1_hits = sum(
            1
            for line in recent_commits.lower().split("\n")
            if any(kw in line for kw in p1_keywords)
        )
        p2_hits = sum(
            1
            for line in recent_commits.lower().split("\n")
            if any(kw in line for kw in p2_keywords)
        )
        metrics["recent_p1_commits"] = p1_hits
        metrics["recent_p2_commits"] = p2_hits

        if p1_items > 0 and p2_hits > p1_hits * 2:
            findings.append(
                Finding(
                    "plan",
                    "warning",
                    "P2 work outpacing P1 in recent commits",
                    f"P1 commits: {p1_hits}, P2 commits: {p2_hits} — priority inversion",
                    "Refocus on P1 items (Hetzner migration, Cortex beta launch)",
                )
            )
            score_components.append(0.5)
        else:
            score_components.append(0.9)

    # 3e. MEMORY.md session decisions freshness
    memory_text = MEMORY_MD.read_text() if MEMORY_MD.exists() else ""
    decision_dates = re.findall(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", memory_text)
    if decision_dates:
        latest_decision = max(decision_dates)
        metrics["latest_session_decision"] = latest_decision
        try:
            latest_dt = datetime.strptime(latest_decision, "%Y-%m-%d").date()
            days_since = (today - latest_dt).days
            metrics["days_since_decision"] = days_since
            score_components.append(1.0 if days_since <= 2 else 0.7 if days_since <= 5 else 0.4)
        except ValueError:
            pass

    score = sum(score_components) / max(len(score_components), 1)
    return DimensionScore("Plan Accuracy", score, _score_to_grade(score), findings, metrics)


# ═══════════════════════════════════════════════════════════════
# Dimension 4: Recommendation Quality
# ═══════════════════════════════════════════════════════════════


def assess_recommendations() -> DimensionScore:
    """Are recommendations high-quality and being followed?"""
    findings = []
    metrics = {}
    score_components = []

    outcomes = _load_jsonl(CORTEX_DIR / "outcomes.jsonl")

    if len(outcomes) < 5:
        return DimensionScore(
            "Recommendation Quality",
            0.5,
            "C",
            [
                Finding(
                    "recommendations",
                    "info",
                    "Insufficient outcome data",
                    f"Only {len(outcomes)} outcomes recorded",
                    "Need 10+ outcomes for meaningful recommendation quality analysis",
                )
            ],
            {"total_outcomes": len(outcomes)},
        )

    # 4a. Follow rate — what % of recommendations are followed?
    followed = [o for o in outcomes if o.get("followed")]
    follow_rate = len(followed) / len(outcomes) if outcomes else 0
    metrics["follow_rate"] = round(follow_rate, 3)
    score_components.append(follow_rate)

    if follow_rate < 0.4:
        findings.append(
            Finding(
                "recommendations",
                "action",
                f"Low follow rate ({follow_rate:.0%})",
                "Most recommendations are being ignored — may be low relevance",
                "Analyze unfollowed recommendations for common traits to filter",
                batchable=True,
            )
        )

    # 4b. Success rate by type
    type_outcomes = defaultdict(lambda: {"followed": 0, "success": 0, "total": 0})
    for o in outcomes:
        rtype = o.get("recommendation_type", "unknown")
        type_outcomes[rtype]["total"] += 1
        if o.get("followed"):
            type_outcomes[rtype]["followed"] += 1
        if o.get("outcome") == "success":
            type_outcomes[rtype]["success"] += 1

    metrics["type_breakdown"] = {k: dict(v) for k, v in type_outcomes.items()}

    # Identify best and worst performing types
    best_type = None
    worst_type = None
    best_rate = 0
    worst_rate = 1.0

    for rtype, stats in type_outcomes.items():
        if stats["followed"] >= 3:  # minimum sample
            rate = stats["success"] / stats["followed"]
            if rate > best_rate:
                best_rate = rate
                best_type = rtype
            if rate < worst_rate:
                worst_rate = rate
                worst_type = rtype

    if best_type:
        metrics["best_performing_type"] = f"{best_type} ({best_rate:.0%})"
    if worst_type and worst_rate < 0.5:
        findings.append(
            Finding(
                "recommendations",
                "warning",
                f"Low-performing recommendation type: {worst_type} ({worst_rate:.0%})",
                "This recommendation type fails more often than it succeeds",
                f"Improve or retire '{worst_type}' recommendations",
                batchable=True,
            )
        )

    # 4c. Confidence calibration
    high_conf = [o for o in outcomes if o.get("confidence", 0) >= 0.8 and o.get("followed")]
    if len(high_conf) >= 3:
        high_success = len([o for o in high_conf if o.get("outcome") == "success"]) / len(high_conf)
        metrics["high_confidence_success_rate"] = round(high_success, 3)
        if high_success < 0.7:
            findings.append(
                Finding(
                    "recommendations",
                    "warning",
                    f"High-confidence recommendations failing ({high_success:.0%} success)",
                    "System is overconfident — confidence scores need recalibration",
                    "Add confidence penalty for recommendation types with poor track records",
                )
            )
            score_components.append(0.5)
        else:
            score_components.append(high_success)

    # 4d. Recommendation diversity
    recent_outcomes = [o for o in outcomes[-50:]]  # last 50
    recent_types = set(o.get("recommendation_type", "unknown") for o in recent_outcomes)
    metrics["recent_type_diversity"] = len(recent_types)
    score_components.append(min(len(recent_types) / 4, 1.0))

    score = sum(score_components) / max(len(score_components), 1)
    return DimensionScore(
        "Recommendation Quality", score, _score_to_grade(score), findings, metrics
    )


# ═══════════════════════════════════════════════════════════════
# Dimension 5: Predictive Planning
# ═══════════════════════════════════════════════════════════════


def assess_predictive() -> DimensionScore:
    """Can new work be predicted from patterns? What's compounding vs stalling?"""
    findings = []
    metrics = {}
    score_components = []

    # 5a. Commit velocity by project — which are accelerating/decelerating?
    goals_text_pp = GOALS_FILE.read_text() if GOALS_FILE.exists() else ""
    project_velocity = {}

    all_proj_sources = list(PROJECTS.items()) + list(SUBMODULE_PROJECTS.items())
    for proj_name, proj_path in all_proj_sources:
        if not proj_path.exists():
            continue
        # Submodules: run git log from within their own repo
        if proj_name in SUBMODULE_PROJECTS:
            recent = _run_cmd("git log --oneline --after='7 days ago' | wc -l", cwd=str(proj_path))
            prior = _run_cmd(
                "git log --oneline --after='14 days ago' --before='7 days ago' | wc -l",
                cwd=str(proj_path),
            )
        else:
            rel = proj_path.relative_to(REPO_ROOT)
            recent = _run_cmd(f"git log --oneline --after='7 days ago' -- {rel} | wc -l")
            prior = _run_cmd(
                f"git log --oneline --after='14 days ago' --before='7 days ago' -- {rel} | wc -l"
            )
        try:
            recent_n = int(recent.strip())
            prior_n = int(prior.strip())
            if prior_n > 0:
                velocity_ratio = recent_n / prior_n
            elif recent_n > 0:
                velocity_ratio = 2.0  # new activity
            else:
                velocity_ratio = 0.0

            # Detect ops/deployment phase — low commits may be intentional
            ops_keyword = OPS_PHASE_PROJECTS.get(proj_name)
            in_ops_phase = bool(ops_keyword and ops_keyword.lower() in goals_text_pp.lower())

            project_velocity[proj_name] = {
                "recent_7d": recent_n,
                "prior_7d": prior_n,
                "velocity_ratio": round(velocity_ratio, 2),
                "ops_phase": in_ops_phase,
            }
        except ValueError:
            continue

    metrics["project_velocity"] = project_velocity

    # Identify accelerating and stalling projects
    # Exclude projects in known ops/deployment phase from stalling detection
    accelerating = [p for p, v in project_velocity.items() if v["velocity_ratio"] > 1.3]
    stalling = [
        p
        for p, v in project_velocity.items()
        if v["velocity_ratio"] < 0.5 and v["prior_7d"] > 2 and not v.get("ops_phase")
    ]
    dormant = [
        p
        for p, v in project_velocity.items()
        if v["recent_7d"] == 0 and v["prior_7d"] == 0 and not v.get("ops_phase")
    ]

    metrics["accelerating"] = accelerating
    metrics["stalling"] = stalling
    metrics["dormant"] = dormant

    if stalling:
        findings.append(
            Finding(
                "predictive",
                "warning",
                f"Stalling projects: {', '.join(stalling)}",
                "These had recent activity but velocity dropped >50% (ops-phase projects excluded)",
                "Check if blocked or intentionally deprioritized",
            )
        )

    # Score: more accelerating = better, stalling = worse
    active_count = len([v for v in project_velocity.values() if v["recent_7d"] > 0])
    if active_count > 0:
        score_components.append(min(active_count / 3, 1.0))  # 3+ active = full score

    # 5b. Compound trajectory — overall system direction
    total_recent = sum(v["recent_7d"] for v in project_velocity.values())
    total_prior = sum(v["prior_7d"] for v in project_velocity.values())
    metrics["total_commits_7d"] = total_recent
    metrics["total_commits_prior_7d"] = total_prior

    if total_prior > 0:
        overall_ratio = total_recent / total_prior
        if overall_ratio >= 1.3:
            trajectory = "accelerating"
        elif overall_ratio >= 0.8:
            trajectory = "steady"
        elif overall_ratio >= 0.4:
            trajectory = "decelerating"
        else:
            trajectory = "stalling"
    elif total_recent > 0:
        trajectory = "accelerating"
    else:
        trajectory = "stalling"

    metrics["trajectory"] = trajectory
    score_components.append(
        {"accelerating": 1.0, "steady": 0.8, "decelerating": 0.5, "stalling": 0.2}[trajectory]
    )

    # 5c. Predicted next actions based on patterns
    predicted_actions = []

    # EMOS pairs check — look for threshold in GOALS or startup data
    goals_text = GOALS_FILE.read_text() if GOALS_FILE.exists() else ""
    hrrr_match = re.search(r"HRRR\s+(\d[\d,]+)\s+READY", goals_text)
    if hrrr_match:
        pairs = int(hrrr_match.group(1).replace(",", ""))
        if pairs >= 2000:
            predicted_actions.append(
                {
                    "action": "EMOS auto-fit for HRRR",
                    "reason": f"HRRR has {pairs:,} validation pairs (>2,000 threshold)",
                    "command": "/emos-auto-fit",
                    "priority": "high",
                }
            )

    # Deadline proximity
    for match in re.finditer(r"\*\*Target:\*\*\s*(Mar|Apr|May)\s+(\d{1,2})", goals_text):
        month = {"Mar": 3, "Apr": 4, "May": 5}[match.group(1)]
        day = int(match.group(2))
        try:
            target_date = datetime(2026, month, day).date()
            days_until = (target_date - datetime.now(timezone.utc).date()).days
            if 0 < days_until <= 3:
                # Find goal name
                context = goals_text[max(0, match.start() - 200) : match.start()]
                goal_match = re.search(r"###\s+Goal\s+\d+:\s*(.+)", context)
                goal_name = goal_match.group(1) if goal_match else "Unknown goal"
                predicted_actions.append(
                    {
                        "action": f"Deadline approaching: {goal_name}",
                        "reason": f"{days_until} day(s) until target ({match.group(1)} {match.group(2)})",
                        "priority": "critical" if days_until <= 1 else "high",
                    }
                )
        except ValueError:
            continue

    metrics["predicted_actions"] = predicted_actions
    if predicted_actions:
        score_components.append(0.9)  # Prediction capability active
        for action in predicted_actions:
            findings.append(
                Finding(
                    "predictive",
                    "action" if action["priority"] != "critical" else "critical",
                    action["action"],
                    action["reason"],
                    action.get("command", "Review and take action"),
                    automatable=action.get("command") is not None,
                )
            )

    score = sum(score_components) / max(len(score_components), 1)
    return DimensionScore("Predictive Planning", score, _score_to_grade(score), findings, metrics)


# ═══════════════════════════════════════════════════════════════
# Dimension 6: Batch Optimization
# ═══════════════════════════════════════════════════════════════


def assess_batch() -> DimensionScore:
    """Is overnight batch capacity being optimally used?"""
    findings = []
    metrics = {}
    score_components = []

    # 6a. Recent batch submissions
    batch_dir = CORTEX_DIR / "batch"
    result_files = list(batch_dir.glob("result_*.json")) if batch_dir.exists() else []
    pending_files = list(batch_dir.glob("pending_*.json")) if batch_dir.exists() else []

    metrics["completed_batches"] = len(result_files)
    metrics["pending_batches"] = len(pending_files)

    # Check freshness of last batch result
    if result_files:
        latest_result = max(result_files, key=lambda f: f.stat().st_mtime)
        days_since = (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(latest_result.stat().st_mtime, tz=timezone.utc)
        ).days
        metrics["last_batch_result_days"] = days_since
        score_components.append(1.0 if days_since <= 2 else 0.6 if days_since <= 5 else 0.3)
        if days_since > 5:
            findings.append(
                Finding(
                    "batch",
                    "warning",
                    f"No batch results in {days_since} days",
                    "Overnight capacity going unused = missed 50% cost savings",
                    "Run /batch-auto-fill to queue overnight work",
                )
            )
    else:
        score_components.append(0.3)
        findings.append(
            Finding(
                "batch",
                "info",
                "No batch results found",
                "Batch API provides 50% cost savings for non-urgent work",
                "Use /batch-orchestrate to start filling overnight queue",
            )
        )

    # 6b. Identify batchable work from GOALS.md
    goals_text = GOALS_FILE.read_text() if GOALS_FILE.exists() else ""
    batchable_patterns = [
        (r"benchmark|benchmark", "research"),
        (r"analyze|analysis|audit", "analysis"),
        (r"documentation|docs|readme", "documentation"),
        (r"review|code review", "review"),
        (r"test gap|coverage|test plan", "test-gaps"),
    ]

    batchable_items = []
    for line in goals_text.split("\n"):
        if "- [ ]" in line:
            for pattern, batch_type in batchable_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    batchable_items.append(
                        {
                            "item": line.strip().replace("- [ ] ", ""),
                            "type": batch_type,
                        }
                    )
                    break

    metrics["batchable_goals_items"] = len(batchable_items)
    if batchable_items:
        findings.append(
            Finding(
                "batch",
                "info",
                f"{len(batchable_items)} GOALS items could run as overnight batch",
                "These items don't need interactive attention",
                "Queue via /batch-submit: " + ", ".join(set(b["type"] for b in batchable_items)),
                batchable=True,
            )
        )

    # 6c. Batch queue health
    queue_db = CORTEX_DIR / "batch_queue.db"
    if queue_db.exists():
        try:
            import sqlite3

            conn = sqlite3.connect(str(queue_db))
            cursor = conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
            queue_status = dict(cursor.fetchall())
            conn.close()
            metrics["queue_status"] = queue_status
            pending = queue_status.get("pending", 0)
            if pending > 20:
                findings.append(
                    Finding(
                        "batch",
                        "warning",
                        f"{pending} tasks stuck in pending queue",
                        "Batch tasks piling up without submission",
                        "Check batch scheduler or run /batch-submit manually",
                    )
                )
            score_components.append(1.0 if pending < 10 else 0.7 if pending < 20 else 0.4)
        except Exception:
            pass

    score = sum(score_components) / max(len(score_components), 1) if score_components else 0.5
    return DimensionScore("Batch Optimization", score, _score_to_grade(score), findings, metrics)


# ═══════════════════════════════════════════════════════════════
# Dimension 7: Automation Surface
# ═══════════════════════════════════════════════════════════════


def assess_automation() -> DimensionScore:
    """What manual work could be automated?"""
    findings = []
    metrics = {}
    score_components = []

    # 7a. Agent utilization — which agents exist but are underused?
    agents_dir = REPO_ROOT / ".claude" / "agents"
    agent_count = len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0
    metrics["total_agents"] = agent_count

    # Check which agents have been invoked recently (via outcomes/logs)
    outcomes = _load_jsonl(CORTEX_DIR / "outcomes.jsonl")
    agent_mentions = Counter()
    for o in outcomes[-100:]:
        context = o.get("context", {})
        agent = context.get("agent") or o.get("recommendation_type", "")
        if agent:
            agent_mentions[agent] += 1

    metrics["agent_usage_recent"] = dict(agent_mentions.most_common(10))
    agents_used = len(agent_mentions)
    utilization = agents_used / max(agent_count, 1)
    metrics["agent_utilization"] = round(utilization, 2)
    score_components.append(min(utilization + 0.3, 1.0))  # Bonus — not all agents need constant use

    # 7b. LaunchAgent coverage — what's automated vs manual?
    la_dir = Path.home() / "Library" / "LaunchAgents"
    la_count = 0
    la_running = 0
    if la_dir.exists():
        la_plists = (
            list(la_dir.glob("com.cortex*.plist"))
            + list(la_dir.glob("com.vortex*.plist"))
            + list(la_dir.glob("com.alphaarena*.plist"))
        )
        la_count = len(la_plists)
        # Check how many are actually loaded
        launchctl_output = _run_cmd("launchctl list 2>/dev/null")
        for plist in la_plists:
            label = plist.stem
            if label in launchctl_output:
                la_running += 1
    metrics["launchagent_count"] = la_count
    metrics["launchagent_running"] = la_running
    score_components.append(min(la_count / 10, 1.0))  # 10+ automated services = full score
    if la_count > 5 and la_running < la_count * 0.5:
        findings.append(
            Finding(
                "automation",
                "warning",
                f"{la_count - la_running}/{la_count} LaunchAgents not running",
                "Configured automation not executing — services may have crashed",
                "Run: launchctl list | grep -E 'cortex|vortex|arena' to check status",
                automatable=True,
            )
        )

    # 7c. Identify automation opportunities from patterns
    automation_opportunities = []

    # Check if daily_scan runs
    daily_log = CORTEX_DIR / "logs" / "daily_scan.log"
    if daily_log.exists():
        try:
            mtime = datetime.fromtimestamp(daily_log.stat().st_mtime, tz=timezone.utc)
            days_since = (datetime.now(timezone.utc) - mtime).days
            if days_since > 2:
                automation_opportunities.append(
                    {
                        "task": "Daily scan not running",
                        "reason": f"Last run {days_since} days ago",
                        "fix": "Check com.cortex.daily LaunchAgent: launchctl list | grep cortex",
                    }
                )
        except Exception:
            pass
    else:
        automation_opportunities.append(
            {
                "task": "No daily scan log found",
                "reason": "Daily assessment not running automatically",
                "fix": "Install LaunchAgent for cortex daily scan",
            }
        )

    # Check for repeated manual patterns in git history
    recent_msgs = _run_cmd("git log --oneline -50 --format='%s'")
    manual_patterns = Counter()
    for msg in recent_msgs.split("\n"):
        msg_lower = msg.lower()
        if "fix" in msg_lower and "test" in msg_lower:
            manual_patterns["test-fixing"] += 1
        if "deploy" in msg_lower or "production" in msg_lower:
            manual_patterns["manual-deploy"] += 1
        if "update goals" in msg_lower or "update memory" in msg_lower:
            manual_patterns["state-update"] += 1

    for pattern, count in manual_patterns.items():
        if count >= 3:
            automation_opportunities.append(
                {
                    "task": f"Repeated manual pattern: {pattern} ({count}x in last 50 commits)",
                    "reason": "Repeated manual work = automation candidate",
                    "fix": f"Create hook or agent for '{pattern}' pattern",
                }
            )

    metrics["automation_opportunities"] = len(automation_opportunities)
    for opp in automation_opportunities:
        findings.append(
            Finding(
                "automation",
                "info",
                opp["task"],
                opp["reason"],
                opp["fix"],
                automatable=True,
            )
        )

    # 7d. Hook coverage — which events trigger automated responses?
    settings_file = CLAUDE_DIR / "settings.json"
    hook_count = 0
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
            hooks = settings.get("hooks", {})
            hook_count = sum(len(v) if isinstance(v, list) else 1 for v in hooks.values())
        except Exception:
            pass
    metrics["hook_count"] = hook_count
    score_components.append(min(hook_count / 3, 1.0))  # 3+ hooks = full score

    score = sum(score_components) / max(len(score_components), 1)
    return DimensionScore("Automation Surface", score, _score_to_grade(score), findings, metrics)


# ═══════════════════════════════════════════════════════════════
# Assessment Orchestrator
# ═══════════════════════════════════════════════════════════════


def run_assessment(dimension: int = 0) -> AssessmentReport:
    """Run full deep assessment (or single dimension if specified)."""

    assessors = [
        (1, assess_awareness),
        (2, assess_learning),
        (3, assess_plan_accuracy),
        (4, assess_recommendations),
        (5, assess_predictive),
        (6, assess_batch),
        (7, assess_automation),
    ]

    dimensions = {}
    for num, assessor in assessors:
        if dimension > 0 and num != dimension:
            continue
        try:
            result = assessor()
            dimensions[result.name] = result
        except Exception as e:
            dimensions[f"Dimension {num}"] = DimensionScore(
                f"Dimension {num} (ERROR)",
                0.0,
                "F",
                [
                    Finding(
                        f"dim{num}", "critical", "Assessment failed", str(e), "Fix assessment code"
                    )
                ],
                {"error": str(e)},
            )

    # Calculate overall
    scores = [d.score for d in dimensions.values()]
    overall_score = sum(scores) / max(len(scores), 1)
    overall_grade = _score_to_grade(overall_score)

    # Determine compound trajectory from predictive dimension
    predictive = dimensions.get("Predictive Planning")
    trajectory = predictive.metrics.get("trajectory", "unknown") if predictive else "unknown"

    # Collect all findings sorted by severity
    all_findings = []
    for dim in dimensions.values():
        all_findings.extend(dim.findings)

    severity_order = {"critical": 0, "action": 1, "warning": 2, "info": 3}
    all_findings.sort(key=lambda f: severity_order.get(f.severity, 4))

    # Top next actions
    next_actions = [
        {"action": f.recommendation, "severity": f.severity, "dimension": f.dimension}
        for f in all_findings
        if f.severity in ("critical", "action")
    ][:5]

    # Batch candidates
    batch_candidates = [
        {"action": f.recommendation, "title": f.title} for f in all_findings if f.batchable
    ]

    # Automation opportunities
    automation_opps = [
        {"action": f.recommendation, "title": f.title} for f in all_findings if f.automatable
    ]

    # Analyze trend from history
    trend_insights = _analyze_trend()

    report = AssessmentReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        overall_score=round(overall_score, 3),
        overall_grade=overall_grade,
        dimensions={
            k: {
                "score": round(v.score, 3),
                "grade": v.grade,
                "finding_count": len(v.findings),
                "metrics": v.metrics,
                "findings": [asdict(f) for f in v.findings],
            }
            for k, v in dimensions.items()
        },
        compound_trajectory=trajectory,
        next_actions=next_actions,
        batch_candidates=batch_candidates,
        automation_opportunities=automation_opps,
    )

    # Inject trend insights into next_actions if significant
    for insight in trend_insights:
        report.next_actions.insert(
            0,
            {
                "action": insight,
                "severity": "info",
                "dimension": "trend",
            },
        )

    return report


def _analyze_trend() -> list[str]:
    """Analyze assessment history for compound patterns."""
    history = _load_jsonl(HISTORY_FILE)
    if len(history) < 2:
        return []

    insights = []
    recent = history[-5:]  # last 5 assessments

    # Overall score trend
    scores = [h["overall_score"] for h in recent]
    if len(scores) >= 3:
        if all(scores[i] >= scores[i - 1] for i in range(1, len(scores))):
            insights.append(f"TREND: Score improving steadily ({scores[0]:.0%} → {scores[-1]:.0%})")
        elif all(scores[i] <= scores[i - 1] for i in range(1, len(scores))):
            insights.append(
                f"TREND: Score declining ({scores[0]:.0%} → {scores[-1]:.0%}) — investigate root cause"
            )
        elif len(set(h["overall_grade"] for h in recent)) == 1 and len(recent) >= 3:
            insights.append(
                f"PLATEAU: Grade stuck at {recent[-1]['overall_grade']} for {len(recent)} assessments — structural change needed"
            )

    # Dimension-level trends — find consistently low dimensions
    if len(recent) >= 3 and "dimension_scores" in recent[-1]:
        for dim_name in recent[-1].get("dimension_scores", {}):
            dim_scores = [h.get("dimension_scores", {}).get(dim_name, 0) for h in recent]
            dim_scores = [s for s in dim_scores if s > 0]
            if dim_scores and all(s < 0.5 for s in dim_scores[-3:]):
                insights.append(
                    f"CHRONIC: {dim_name} scored below 50% for {len(dim_scores)} consecutive assessments"
                )

    # Finding count trend — are we creating more problems or solving them?
    finding_counts = [h.get("finding_count", 0) for h in recent]
    if len(finding_counts) >= 3:
        if finding_counts[-1] > finding_counts[0] * 1.5:
            insights.append(
                f"DRIFT: Finding count growing ({finding_counts[0]} → {finding_counts[-1]}) — system complexity outpacing maintenance"
            )
        elif finding_counts[-1] < finding_counts[0] * 0.7:
            insights.append(
                f"IMPROVING: Finding count shrinking ({finding_counts[0]} → {finding_counts[-1]}) — issues being resolved"
            )

    return insights


def format_report(report: AssessmentReport) -> str:
    """Format as ASCII terminal display."""
    lines = []

    # Header
    lines.append("")
    lines.append("╔══════════════════════════════════════════════════════════╗")
    lines.append("║           CORTEX DEEP ASSESSMENT                       ║")
    lines.append("║           Meta-Cognitive System Audit                   ║")
    lines.append("╚══════════════════════════════════════════════════════════╝")
    lines.append(f"  {report.timestamp[:19]}  |  Trajectory: {report.compound_trajectory.upper()}")
    lines.append("")

    # Overall score bar
    bar_width = 40
    filled = int(report.overall_score * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    lines.append(f"  Overall: [{bar}] {report.overall_score:.0%} ({report.overall_grade})")
    lines.append("")

    # Dimension scores
    lines.append("  ┌─────────────────────────────┬───────┬───────┬──────────┐")
    lines.append("  │ Dimension                   │ Score │ Grade │ Findings │")
    lines.append("  ├─────────────────────────────┼───────┼───────┼──────────┤")

    for name, dim in report.dimensions.items():
        name_short = name[:27].ljust(27)
        score_str = f"{dim['score']:.0%}".rjust(5)
        grade_str = dim["grade"].center(5)
        finding_count = str(dim["finding_count"]).center(8)
        lines.append(f"  │ {name_short} │ {score_str} │ {grade_str} │ {finding_count} │")

    lines.append("  └─────────────────────────────┴───────┴───────┴──────────┘")
    lines.append("")

    # Critical/Action findings
    all_findings = []
    for dim in report.dimensions.values():
        for f in dim.get("findings", []):
            all_findings.append(f)

    severity_icons = {"critical": "🔴", "action": "🟡", "warning": "🟠", "info": "🔵"}
    actionable = [f for f in all_findings if f["severity"] in ("critical", "action", "warning")]

    if actionable:
        lines.append("  ── Findings ──────────────────────────────────────────")
        for f in actionable[:8]:
            icon = severity_icons.get(f["severity"], "·")
            lines.append(f"  {icon} [{f['severity'].upper():8s}] {f['title']}")
            lines.append(f"     → {f['recommendation']}")
        lines.append("")

    # Next actions
    if report.next_actions:
        lines.append("  ── Next Actions ──────────────────────────────────────")
        for i, action in enumerate(report.next_actions[:5], 1):
            lines.append(f"  {i}. {action['action']}")
        lines.append("")

    # Batch candidates
    if report.batch_candidates:
        lines.append("  ── Batch Candidates (50% cost savings) ───────────────")
        for b in report.batch_candidates[:3]:
            lines.append(f"  · {b['title']}")
        lines.append("")

    # Automation opportunities
    if report.automation_opportunities:
        lines.append("  ── Automation Opportunities ──────────────────────────")
        for a in report.automation_opportunities[:3]:
            lines.append(f"  · {a['title']}")
        lines.append("")

    # Trend analysis from history
    history = _load_jsonl(HISTORY_FILE)
    if len(history) >= 2:
        lines.append("  ── Trend (last assessments) ──────────────────────────")
        recent_history = history[-5:]
        score_line = "  Score: " + " → ".join(f"{h['overall_score']:.0%}" for h in recent_history)
        # Determine trend direction
        if len(recent_history) >= 3:
            scores = [h["overall_score"] for h in recent_history]
            if scores[-1] > scores[0] + 0.05:
                score_line += "  [IMPROVING]"
            elif scores[-1] < scores[0] - 0.05:
                score_line += "  [DECLINING]"
            elif len(set(h["overall_grade"] for h in recent_history)) == 1:
                score_line += "  [PLATEAU]"
            else:
                score_line += "  [STABLE]"
        lines.append(score_line)

        # Show dimension with biggest change
        if "dimension_scores" in history[-1] and len(history) >= 2:
            prev_dims = history[-2].get("dimension_scores", {})
            curr_dims = history[-1].get("dimension_scores", {})
            changes = {}
            for dim_name in curr_dims:
                if dim_name in prev_dims:
                    delta = curr_dims[dim_name] - prev_dims[dim_name]
                    if abs(delta) > 0.05:
                        changes[dim_name] = delta
            if changes:
                biggest = max(changes, key=lambda k: abs(changes[k]))
                direction = "+" if changes[biggest] > 0 else ""
                lines.append(f"  Biggest move: {biggest} ({direction}{changes[biggest]:.0%})")
        lines.append("")

    lines.append("  ════════════════════════════════════════════════════════")
    return "\n".join(lines)


def save_report(report: AssessmentReport):
    """Save report to JSON + append to history."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(asdict(report), indent=2))

    # Append summary to history for trend analysis
    summary = {
        "timestamp": report.timestamp,
        "overall_score": report.overall_score,
        "overall_grade": report.overall_grade,
        "trajectory": report.compound_trajectory,
        "dimension_scores": {k: v["score"] for k, v in report.dimensions.items()},
        "finding_count": sum(v["finding_count"] for v in report.dimensions.values()),
        "action_count": len(report.next_actions),
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(summary) + "\n")


def main():
    json_only = "--json" in sys.argv
    show_plan = "--plan" in sys.argv
    dimension = 0

    for arg in sys.argv[1:]:
        if arg.startswith("--dimension"):
            try:
                dimension = int(sys.argv[sys.argv.index(arg) + 1])
            except (ValueError, IndexError):
                pass

    report = run_assessment(dimension)
    save_report(report)

    if json_only:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report(report))
        print(f"\n  Report saved: {OUTPUT_FILE}")
        print(f"  History:      {HISTORY_FILE}")

        # Inline weekly plan proposal when run without dimension filter
        if dimension == 0 and show_plan:
            try:
                from cortex.weekly_planner import propose_week, format_proposal

                goals_text = GOALS_FILE.read_text()
                plan_result = propose_week(goals_text)
                print("\n")
                print(format_proposal(plan_result))
            except Exception as e:
                print(f"\n  [weekly planner error: {e}]")


if __name__ == "__main__":
    main()
