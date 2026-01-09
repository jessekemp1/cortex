#!/usr/bin/env python3
"""
Briefing Generator - Daily briefing system for cross-project status

Synthesizes:
- Portfolio pulse (active projects, commits, blockers)
- Priority actions (top recommendations)
- Patterns noticed (activity trends)
- Waiting on (decisions needed)
"""

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import existing tools
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

try:
    from ai_intelligence import ProjectActivity, ProjectScanner
except ImportError:
    ProjectScanner = None
    ProjectActivity = None

try:
    from goal_parser import Goal, GoalParser
except ImportError:
    GoalParser = None
    Goal = None

try:
    from recommendation_engine import Recommendation, RecommendationEngine
except ImportError:
    RecommendationEngine = None
    Recommendation = None

try:
    from intelligence.process_monitor import ProcessMonitor
except ImportError:
    ProcessMonitor = None

try:
    from integration.git_tracker import GitTracker, get_git_briefing
except ImportError:
    GitTracker = None
    get_git_briefing = None


@dataclass
class BriefingData:
    """Structured briefing data."""

    # Portfolio pulse
    active_projects: List[str]
    recent_commits_24h: int
    total_commits_7d: int
    blockers: List[Dict[str, str]]

    # Priority actions
    priority_actions: List[Dict[str, Any]]

    # Patterns noticed
    patterns: List[str]

    # Waiting on
    waiting_on: List[str]

    # Metadata
    generated_at: datetime

    # Optional fields
    resource_status: Optional[Dict[str, Any]] = None
    batch_queue_status: Optional[Dict[str, Any]] = None
    git_status: Optional[Dict[str, Any]] = None
    work_progress: Optional[Dict[str, Any]] = None  # Work absorber status
    period: str = "24h"


class BriefingGenerator:
    """Generate daily briefings from cross-project data."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir

        # Initialize tools
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        self.recommendation_engine = (
            RecommendationEngine() if RecommendationEngine else None
        )

    def generate_daily_briefing(self) -> BriefingData:
        """
        Generate daily briefing with portfolio status and recommendations.

        Returns:
            BriefingData with all briefing sections
        """
        # 1. Get project activity
        project_activity = []
        if self.project_scanner:
            try:
                repos = self.project_scanner.find_git_repos()
                project_activity = [
                    self.project_scanner.analyze_project(repo) for repo in repos
                ]
            except Exception as e:
                print(f"Warning: Could not scan projects: {e}", file=sys.stderr)

        # 2. Get goals
        goals = []
        if self.goal_parser:
            try:
                goals = self.goal_parser.parse()
            except Exception as e:
                print(f"Warning: Could not parse goals: {e}", file=sys.stderr)

        # 3. Get recommendations
        recommendations = []
        if self.recommendation_engine:
            try:
                recommendations = self.recommendation_engine.generate_recommendations(
                    project_activity=project_activity if project_activity else None,
                    limit=5,
                )
            except Exception as e:
                print(
                    f"Warning: Could not generate recommendations: {e}", file=sys.stderr
                )

        # 4. Get Git/GitHub status
        git_status = None
        if GitTracker:
            try:
                tracker = GitTracker(str(self.root_dir))
                git_status = {
                    "summary": tracker.get_summary(),
                    "recommendations": tracker.get_recommendations(),
                    "formatted": tracker.format_for_briefing()
                }
            except Exception as e:
                print(f"Warning: Could not get Git status: {e}", file=sys.stderr)

        # 5. Get resource status
        resource_status = None
        batch_queue_status = None
        if ProcessMonitor:
            try:
                monitor = ProcessMonitor()
                resource_status = monitor.get_status()

                # Get batch queue statistics and task details
                from intelligence.process_monitor import TaskState
                batch_queue_status = monitor.batch_queue.get_queue_stats()

                # Add detailed task lists
                batch_queue_status['running_tasks'] = monitor.batch_queue.get_running_tasks()
                batch_queue_status['scheduled_tasks'] = monitor.batch_queue.get_scheduled_tasks()[:5]  # Next 5
                batch_queue_status['pending_tasks'] = monitor.batch_queue.get_pending_tasks()[:5]  # First 5
                batch_queue_status['recent_completed'] = monitor.batch_queue.get_task_history(limit=3, state=TaskState.COMPLETED)
                batch_queue_status['recent_failed'] = monitor.batch_queue.get_task_history(limit=3, state=TaskState.FAILED)
            except Exception as e:
                print(f"Warning: Could not get resource status: {e}", file=sys.stderr)

        # 6. Get work absorber status
        work_progress = None
        try:
            from work_absorber import WorkAbsorber
            absorber = WorkAbsorber()

            # Get recent work summary
            recent_items = absorber.get_recent_work(days=1)
            all_items = absorber.get_recent_work(days=7)
            drift_summary = absorber.get_drift_summary()

            # Build work progress summary
            work_progress = {
                "items_24h": len(recent_items),
                "items_7d": len(all_items),
                "correlated_24h": sum(1 for i in recent_items if i.plan_step_id),
                "orphaned_24h": sum(1 for i in recent_items if not i.plan_step_id),
                "drifts_total": drift_summary.get("total", 0),
                "drifts_by_type": dict(drift_summary.get("by_type", {})),
                "recent_work": [
                    {"title": i.title, "project": i.project, "scope": i.scope}
                    for i in recent_items[:5]
                ],
            }
        except ImportError:
            pass  # Work absorber not available
        except Exception as e:
            print(f"Warning: Could not get work progress: {e}", file=sys.stderr)

        # 7. Build briefing sections
        briefing = BriefingData(
            active_projects=self._get_active_projects(project_activity),
            recent_commits_24h=self._count_recent_commits(project_activity, hours=24),
            total_commits_7d=self._count_recent_commits(project_activity, days=7),
            blockers=self._get_blockers(project_activity, goals),
            priority_actions=self._get_priority_actions(recommendations, goals),
            patterns=self._detect_patterns(project_activity),
            waiting_on=self._get_waiting_on(goals, project_activity),
            resource_status=resource_status,
            batch_queue_status=batch_queue_status,
            git_status=git_status,
            work_progress=work_progress,
            generated_at=datetime.now(),
        )

        return briefing

    def _get_active_projects(self, projects: List[ProjectActivity]) -> List[str]:
        """Get list of active project names."""
        if not projects:
            return []

        # Active = has commits in last 7 days
        active = [p.name for p in projects if p.commits_7d > 0]

        # Sort by activity (most commits first)
        active.sort(
            key=lambda name: next(
                (p.commits_7d for p in projects if p.name == name), 0
            ),
            reverse=True,
        )

        return active

    def _count_recent_commits(
        self,
        projects: List[ProjectActivity],
        hours: Optional[int] = None,
        days: Optional[int] = None,
    ) -> int:
        """Count commits in recent time period."""
        if not projects:
            return 0

        total = 0
        now = datetime.now()

        for project in projects:
            if not project.last_commit_date:
                continue

            # Check if commit is within time window
            if hours:
                cutoff = now - timedelta(hours=hours)
                if project.last_commit_date >= cutoff:
                    # Count all commits in 7d as proxy for 24h
                    # (we don't have 24h granularity in ProjectActivity)
                    total += max(1, project.commits_7d // 7)
            elif days:
                total += project.commits_7d if days <= 7 else project.commits_30d

        return total

    def _get_blockers(
        self, projects: List[ProjectActivity], goals: List[Goal]
    ) -> List[Dict[str, str]]:
        """Get all current blockers from projects and goals."""
        blockers = []

        # Project blockers
        if projects:
            for project in projects:
                if project.blockers and project.status in ["active", "recent"]:
                    for blocker in project.blockers:
                        blockers.append(
                            {
                                "project": project.name,
                                "blocker": blocker,
                                "source": "project",
                            }
                        )

        # Goal blockers
        if goals:
            for goal in goals:
                if goal.status == "blocked" and goal.project:
                    blocker_text = f"{goal.title}"
                    if goal.blockers:
                        blocker_text = goal.blockers[0]
                    blockers.append(
                        {
                            "project": goal.project,
                            "blocker": blocker_text,
                            "source": "goal",
                        }
                    )

        return blockers

    def _get_priority_actions(
        self, recommendations: List[Recommendation], goals: List[Goal]
    ) -> List[Dict[str, Any]]:
        """Get top 5 priority actions from recommendations and goals with detailed info."""
        actions = []
        seen_titles = set()  # Track titles to avoid duplicates

        def normalize_title(title: str) -> str:
            """Normalize title for deduplication."""
            import re
            # Remove project prefix (e.g., "cortex: " or "VortexV2: ")
            normalized = re.sub(r'^[^:]+:\s*', '', title.lower())
            # Remove parenthetical content (e.g., "(feat/branch-name)")
            normalized = re.sub(r'\([^)]*\)', '', normalized)
            # Remove punctuation
            normalized = re.sub(r'[^\w\s]', '', normalized)
            # Normalize common variations
            normalized = normalized.replace('complete', 'finish')
            normalized = normalized.replace('pr 2', 'pr2')
            # Remove extra whitespace
            normalized = ' '.join(normalized.split())
            return normalized.strip()

        # Add recommendations first
        if recommendations:
            for rec in recommendations[:3]:
                title = rec.action_title if hasattr(rec, "action_title") else rec.title
                norm_title = normalize_title(title)

                if norm_title in seen_titles:
                    continue
                seen_titles.add(norm_title)

                action = {
                    "title": title,
                    "priority": rec.priority.upper(),
                    "project": (
                        rec.related_projects[0]
                        if rec.related_projects
                        else "General"
                    ),
                    "rationale": rec.rationale,
                    "source": "recommendation",
                    "steps": getattr(rec, 'steps', []) or [],
                    "estimated_effort": getattr(rec, 'estimated_effort', None),
                    "estimated_impact": getattr(rec, 'estimated_impact', None),
                    "confidence": getattr(rec, 'confidence', None),
                }
                actions.append(action)

        # Fill remaining with high-priority goals (avoiding duplicates)
        if goals:
            priority_goals = [
                g
                for g in goals
                if g.priority == "A" and g.status in ["pending", "in_progress"]
            ]

            for goal in priority_goals:
                if len(actions) >= 5:
                    break

                norm_title = normalize_title(goal.title)
                if norm_title in seen_titles:
                    continue
                seen_titles.add(norm_title)

                action = {
                    "title": goal.title,
                    "priority": "HIGH",
                    "project": goal.project or "General",
                    "rationale": goal.description[:150] if goal.description else "",
                    "source": "goal",
                    "steps": goal.actions[:3] if goal.actions else [],
                    "success_criteria": goal.success_criteria,
                    "estimated_effort": getattr(goal, 'estimated_effort', None),
                    "completion_percentage": getattr(goal, 'completion_percentage', 0),
                }
                actions.append(action)

        return actions[:5]

    def _detect_patterns(self, projects: List[ProjectActivity]) -> List[str]:
        """Detect activity patterns and trends."""
        patterns = []

        if not projects:
            return patterns

        # 1. Most productive project
        active_projects = [p for p in projects if p.commits_7d > 0]
        if active_projects:
            most_active = max(active_projects, key=lambda p: p.commits_7d)
            patterns.append(
                f"{most_active.name} momentum: {most_active.commits_7d} commits this week"
            )

        # 2. Multi-project activity
        if len(active_projects) >= 3:
            patterns.append(
                f"Multi-project sprint: {len(active_projects)} projects active this week"
            )

        # 3. Dormant projects awakening
        recently_awakened = [
            p
            for p in projects
            if p.commits_7d > 0 and p.commits_30d <= p.commits_7d + 1
        ]
        if recently_awakened:
            patterns.append(f"Renewed focus on {recently_awakened[0].name}")

        # 4. Consistency patterns (commits every day vs burst)
        steady_projects = [
            p for p in active_projects if p.commits_7d >= 5 and p.commits_7d <= 10
        ]
        if steady_projects:
            patterns.append(
                f"Steady progress on {steady_projects[0].name} (daily commits)"
            )

        # 5. Burst activity
        burst_projects = [p for p in active_projects if p.commits_7d >= 15]
        if burst_projects:
            patterns.append(
                f"Sprint on {burst_projects[0].name} ({burst_projects[0].commits_7d} commits)"
            )

        return patterns[:3]  # Top 3 patterns

    def _get_waiting_on(
        self, goals: List[Goal], projects: List[ProjectActivity]
    ) -> List[str]:
        """Get list of things waiting on user decisions."""
        waiting = []

        # 1. Blocked goals
        if goals:
            blocked_goals = [g for g in goals if g.status == "blocked"]
            for goal in blocked_goals:
                if goal.blockers:
                    waiting.append(f"{goal.project or 'Project'}: {goal.blockers[0]}")
                else:
                    waiting.append(f"{goal.project or 'Project'}: {goal.title}")

        # 2. Missing .env files (API keys needed)
        if projects:
            for project in projects:
                if "Missing .env file" in project.blockers:
                    waiting.append(f"{project.name}: Environment configuration needed")

        # 3. Uncommitted changes (decisions to commit or not)
        if projects:
            uncommitted = [p for p in projects if p.uncommitted_changes > 5]
            for project in uncommitted[:2]:  # Top 2
                waiting.append(
                    f"{project.name}: {project.uncommitted_changes} uncommitted changes to review"
                )

        return waiting[:4]  # Top 4 items


def generate_daily_briefing(root_dir: Optional[Path] = None) -> BriefingData:
    """
    Convenience function to generate daily briefing.

    Args:
        root_dir: Root directory to scan (default: /Users/jesse.kemp/Dev)

    Returns:
        BriefingData with briefing information
    """
    generator = BriefingGenerator(root_dir)
    return generator.generate_daily_briefing()


def format_briefing(briefing: BriefingData, use_color: bool = True) -> str:
    """
    Format briefing data into readable text output.

    Args:
        briefing: BriefingData to format
        use_color: Use terminal colors (if available)

    Returns:
        Formatted briefing string
    """
    lines = []

    # Try to use rich/colorama for colors, fallback to plain text
    try:
        if use_color:
            from colorama import Fore, Style, init

            init(autoreset=True)
            BOLD = Style.BRIGHT
            RESET = Style.RESET_ALL
            BLUE = Fore.BLUE
            GREEN = Fore.GREEN
            YELLOW = Fore.YELLOW
            RED = Fore.RED
        else:
            raise ImportError
    except ImportError:
        BOLD = RESET = BLUE = GREEN = YELLOW = RED = ""

    # Header
    lines.append("=" * 64)
    lines.append(
        f"{BOLD}DAILY BRIEFING - {briefing.generated_at.strftime('%B %d, %Y')}{RESET}"
    )
    lines.append("=" * 64)
    lines.append("")

    # ==================== TL;DR SECTION ====================
    lines.append(f"{BOLD}TL;DR{RESET}")
    lines.append("")

    # Portfolio status bullet
    active_count = len(briefing.active_projects)
    blocker_count = len(briefing.blockers)
    blocker_status = f"{RED}{blocker_count} blockers{RESET}" if blocker_count > 0 else f"{GREEN}no blockers{RESET}"
    lines.append(f"  • {BOLD}Portfolio:{RESET} {active_count} active projects, {briefing.total_commits_7d} commits this week, {blocker_status}")

    # Top priority bullet
    if briefing.priority_actions:
        top = briefing.priority_actions[0]
        priority_color = RED if top["priority"] == "HIGH" else YELLOW if top["priority"] == "MEDIUM" else GREEN
        lines.append(f"  • {BOLD}Top Priority:{RESET} [{priority_color}{top['priority']}{RESET}] {top['title']}")

    # Git status bullet
    if briefing.git_status and briefing.git_status.get("summary"):
        gs = briefing.git_status["summary"]
        branch = gs.get("current_branch", "unknown")
        modified = gs.get("working_tree", {}).get("modified", 0)
        untracked = gs.get("working_tree", {}).get("untracked", 0)
        pr_count = len(gs.get("pull_requests", []))
        pr_text = f", {pr_count} open PR{'s' if pr_count != 1 else ''}" if pr_count > 0 else ""
        lines.append(f"  • {BOLD}Git:{RESET} on `{branch}`, {modified} modified, {untracked} untracked{pr_text}")

    # Work progress bullet
    if briefing.work_progress:
        wp = briefing.work_progress
        items_24h = wp.get("items_24h", 0)
        orphaned = wp.get("orphaned_24h", 0)
        drifts = wp.get("drifts_total", 0)
        orphan_text = f", {YELLOW}{orphaned} unplanned{RESET}" if orphaned > 0 else ""
        drift_text = f", {YELLOW}{drifts} drift items{RESET}" if drifts > 0 else ""
        lines.append(f"  • {BOLD}Work:{RESET} {items_24h} items today{orphan_text}{drift_text}")

    # Resource status bullet
    if briefing.resource_status:
        rs = briefing.resource_status
        cpu_avail = rs.get('cpu_available', 0)
        mem_used = rs.get('memory_usage_percent', 0)
        cpu_color = RED if cpu_avail < 30 else YELLOW if cpu_avail < 60 else GREEN
        mem_color = RED if mem_used > 80 else YELLOW if mem_used > 60 else GREEN
        waste = rs.get('waste_items', 0)
        waste_text = f", {YELLOW}{waste} waste items{RESET}" if waste > 10 else ""
        lines.append(f"  • {BOLD}System:{RESET} {cpu_color}{cpu_avail:.0f}% CPU free{RESET}, {mem_color}{mem_used:.0f}% mem used{RESET}{waste_text}")

    # Batch queue bullet
    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status
        running = bq.get('running_count', 0)
        pending = bq.get('pending_count', 0) + bq.get('scheduled_count', 0)
        failed = bq.get('failed_count', 0)
        if running > 0 or pending > 0 or failed > 0:
            parts = []
            if running > 0:
                parts.append(f"{running} running")
            if pending > 0:
                parts.append(f"{pending} queued")
            if failed > 0:
                parts.append(f"{RED}{failed} failed{RESET}")
            lines.append(f"  • {BOLD}Batch:{RESET} {', '.join(parts)}")

    lines.append("")
    lines.append("-" * 64)
    lines.append("")

    # ==================== EXPANDED DETAILS ====================

    # Portfolio Pulse
    lines.append(f"{BOLD}PORTFOLIO PULSE{RESET}")
    lines.append(
        f"  Active projects: {len(briefing.active_projects)} ({', '.join(briefing.active_projects[:5])}{'...' if len(briefing.active_projects) > 5 else ''})"
    )
    lines.append(
        f"  Recent commits: {briefing.recent_commits_24h} in last 24h, {briefing.total_commits_7d} in last 7d"
    )

    if briefing.blockers:
        lines.append(f"  {RED}Blockers: {len(briefing.blockers)}{RESET}")
        for blocker in briefing.blockers[:3]:
            lines.append(f"    - {blocker['project']}: {blocker['blocker']}")
    else:
        lines.append(f"  {GREEN}Blockers: None{RESET}")

    lines.append("")

    # Git & GitHub Status
    if briefing.git_status and briefing.git_status.get("formatted"):
        lines.append(briefing.git_status["formatted"])
        lines.append("")

    # Work Progress (from Work Absorber)
    if briefing.work_progress:
        wp = briefing.work_progress
        lines.append(f"{BOLD}WORK PROGRESS{RESET}")

        items_24h = wp.get("items_24h", 0)
        items_7d = wp.get("items_7d", 0)
        correlated = wp.get("correlated_24h", 0)
        orphaned = wp.get("orphaned_24h", 0)

        lines.append(f"  Work items: {items_24h} in 24h, {items_7d} in 7d")

        if items_24h > 0:
            if correlated > 0:
                lines.append(f"  {GREEN}Planned work: {correlated} items{RESET}")
            if orphaned > 0:
                lines.append(f"  {YELLOW}Unplanned work: {orphaned} items{RESET}")

        # Show drifts
        drifts = wp.get("drifts_total", 0)
        if drifts > 0:
            drift_types = wp.get("drifts_by_type", {})
            drift_summary = ", ".join(f"{k}: {v}" for k, v in list(drift_types.items())[:3])
            lines.append(f"  {YELLOW}Plan drift: {drifts} ({drift_summary}){RESET}")

        # Recent work
        recent = wp.get("recent_work", [])
        if recent:
            lines.append("  Recent:")
            for item in recent[:3]:
                scope_badge = f"[{item.get('scope', 'misc')}]" if item.get('scope') else ""
                lines.append(f"    - {item['title'][:45]} {scope_badge}")

        lines.append("")

    # Resource Pulse
    if briefing.resource_status:
        lines.append(f"{BOLD}⚡ RESOURCE PULSE{RESET}")
        rs = briefing.resource_status

        # CPU and Memory
        cpu_color = RED if rs['cpu_available'] < 30 else YELLOW if rs['cpu_available'] < 60 else GREEN
        mem_color = RED if rs['memory_usage_percent'] > 80 else YELLOW if rs['memory_usage_percent'] > 60 else GREEN

        lines.append(f"  CPU: {cpu_color}{rs['cpu_available']:.0f}% available{RESET} | Memory: {mem_color}{rs['memory_usage_percent']:.0f}% used{RESET}")
        lines.append(f"  Processes: {rs['process_count']}")

        # AI Tools & Services
        if rs.get('ai_tool_cpu', 0) > 0 or rs.get('dev_service_cpu', 0) > 0:
            lines.append(f"  AI Tools: {rs.get('ai_tool_cpu', 0):.1f}% CPU | Dev Services: {rs.get('dev_service_cpu', 0):.1f}% CPU")

        # Alerts and Waste
        alerts_color = RED if rs.get('critical_alerts', 0) > 0 else YELLOW if rs.get('alerts_count', 0) > 5 else ""
        waste_color = YELLOW if rs.get('waste_items', 0) > 10 else ""

        if rs.get('alerts_count', 0) > 0:
            lines.append(f"  Alerts: {alerts_color}{rs.get('alerts_count', 0)} ({rs.get('critical_alerts', 0)} critical){RESET}")

        if rs.get('waste_items', 0) > 0:
            lines.append(f"  Resource Waste: {waste_color}{rs.get('waste_items', 0)} items detected{RESET}")

        # Optimization opportunities
        if rs.get('optimization_opportunities', 0) > 0:
            lines.append(f"  💡 {rs.get('optimization_opportunities', 0)} optimization opportunities")

        lines.append("")

    # Batch Queue Status
    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status

        # Only show if there are tasks in the queue
        total_tasks = (
            bq.get('pending_count', 0) +
            bq.get('scheduled_count', 0) +
            bq.get('running_count', 0)
        )

        if total_tasks > 0 or bq.get('completed_count', 0) > 0 or bq.get('failed_count', 0) > 0:
            lines.append(f"{BOLD}📋 BATCH QUEUE{RESET}")

            # Show running tasks with details
            running_tasks = bq.get('running_tasks', [])
            if running_tasks:
                lines.append(f"  {YELLOW}▶️  Running Now:{RESET}")
                for task in running_tasks[:3]:  # Show up to 3
                    desc = task.description[:50] + "..." if len(task.description) > 50 else task.description
                    elapsed = ""
                    if task.started_at:
                        from datetime import datetime
                        elapsed_sec = (datetime.now() - task.started_at).total_seconds()
                        if elapsed_sec < 60:
                            elapsed = f" ({elapsed_sec:.0f}s elapsed)"
                        else:
                            elapsed = f" ({elapsed_sec/60:.1f}m elapsed)"
                    lines.append(f"     • {desc}{elapsed}")
                if len(running_tasks) > 3:
                    lines.append(f"     ... and {len(running_tasks) - 3} more")
                lines.append("")

            # Show scheduled tasks with times
            scheduled_tasks = bq.get('scheduled_tasks', [])
            if scheduled_tasks:
                lines.append(f"  📅 Scheduled:")
                for task in scheduled_tasks[:3]:  # Show up to 3
                    desc = task.description[:45] + "..." if len(task.description) > 45 else task.description
                    when = ""
                    if task.scheduled_time:
                        from datetime import datetime
                        now = datetime.now()
                        time_until = (task.scheduled_time - now).total_seconds()

                        if time_until < 0:
                            when = " (ready now)"
                        elif time_until < 60:
                            when = f" (in {time_until:.0f}s)"
                        elif time_until < 3600:
                            when = f" (in {time_until/60:.0f}m)"
                        elif time_until < 86400:
                            when = f" (at {task.scheduled_time.strftime('%H:%M')})"
                        else:
                            when = f" ({task.scheduled_time.strftime('%b %d %H:%M')})"

                    priority_marker = ""
                    if task.priority == "immediate":
                        priority_marker = f" {RED}[!]{RESET}"
                    elif task.priority == "high":
                        priority_marker = f" {YELLOW}[H]{RESET}"

                    lines.append(f"     • {desc}{when}{priority_marker}")

                if len(scheduled_tasks) > 3:
                    lines.append(f"     ... and {len(scheduled_tasks) - 3} more")
                lines.append("")

            # Show pending tasks
            pending_tasks = bq.get('pending_tasks', [])
            if pending_tasks:
                lines.append(f"  ⏳ Pending (not yet scheduled):")
                for task in pending_tasks[:3]:  # Show up to 3
                    desc = task.description[:50] + "..." if len(task.description) > 50 else task.description
                    lines.append(f"     • {desc}")
                if len(pending_tasks) > 3:
                    lines.append(f"     ... and {len(pending_tasks) - 3} more")
                lines.append("")

            # Show recent completions with details
            recent_completed = bq.get('recent_completed', [])
            if recent_completed:
                lines.append(f"  {GREEN}✅ Recently Completed:{RESET}")
                for task in recent_completed:
                    desc = task.description[:45] + "..." if len(task.description) > 45 else task.description
                    duration = ""
                    if task.actual_duration_seconds is not None:
                        if task.actual_duration_seconds < 1:
                            duration = f" ({task.actual_duration_seconds*1000:.0f}ms)"
                        elif task.actual_duration_seconds < 60:
                            duration = f" ({task.actual_duration_seconds:.1f}s)"
                        else:
                            duration = f" ({task.actual_duration_seconds/60:.1f}m)"
                    lines.append(f"     • {desc}{duration}")
                lines.append("")

            # Show recent failures with error details
            recent_failed = bq.get('recent_failed', [])
            if recent_failed:
                lines.append(f"  {RED}❌ Recently Failed:{RESET}")
                for task in recent_failed:
                    desc = task.description[:45] + "..." if len(task.description) > 45 else task.description
                    lines.append(f"     • {desc}")
                    if task.error_message:
                        error = task.error_message[:60] + "..." if len(task.error_message) > 60 else task.error_message
                        lines.append(f"       Error: {error}")
                lines.append(f"  💡 View details: {BLUE}cortex batch list --state failed{RESET}")
                lines.append("")

            # Show overall stats summary
            if bq.get('completed_count', 0) > 0 or bq.get('failed_count', 0) > 0:
                completed = bq.get('completed_count', 0)
                failed = bq.get('failed_count', 0)
                total = completed + failed

                if total > 0:
                    success_rate = bq.get('success_rate', 0)
                    success_color = GREEN if success_rate >= 0.9 else YELLOW if success_rate >= 0.7 else RED
                    lines.append(f"  Overall: {completed} completed, {failed} failed ({success_color}{success_rate:.0%} success{RESET})")
                    lines.append("")

            lines.append("")

    # Priority Actions
    lines.append(f"{BOLD}PRIORITY ACTIONS{RESET}")
    if briefing.priority_actions:
        for i, action in enumerate(briefing.priority_actions, 1):
            priority_color = (
                RED
                if action["priority"] == "HIGH"
                else YELLOW if action["priority"] == "MEDIUM" else GREEN
            )

            # Title with project inline
            project_suffix = f" ({action['project']})" if action.get("project") and action["project"] != "General" else ""
            lines.append(
                f"  {i}. [{priority_color}{action['priority']}{RESET}] {action['title']}{project_suffix}"
            )

            # Show progress if available
            if action.get("completion_percentage", 0) > 0:
                pct = action["completion_percentage"]
                progress_bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"     Progress: [{progress_bar}] {pct}%")

            # Show steps/actions if available
            steps = action.get("steps", [])
            if steps:
                lines.append(f"     {YELLOW}Next steps:{RESET}")
                for step in steps[:3]:
                    step_text = step[:70] + "..." if len(step) > 70 else step
                    lines.append(f"       → {step_text}")

            # Show success criteria if available
            if action.get("success_criteria"):
                criteria = action["success_criteria"]
                criteria_text = criteria[:80] + "..." if len(criteria) > 80 else criteria
                lines.append(f"     {GREEN}Done when:{RESET} {criteria_text}")

            # Show effort/impact for recommendations
            if action.get("estimated_effort") or action.get("estimated_impact"):
                meta_parts = []
                if action.get("estimated_effort"):
                    meta_parts.append(f"Effort: {action['estimated_effort']}")
                if action.get("estimated_impact"):
                    meta_parts.append(f"Impact: {action['estimated_impact']}")
                if meta_parts:
                    lines.append(f"     {BLUE}{' | '.join(meta_parts)}{RESET}")

            lines.append("")  # Spacing between actions

    else:
        lines.append("  No priority actions at this time")

    lines.append("")

    # Patterns Noticed
    lines.append(f"{BOLD}PATTERNS NOTICED{RESET}")
    if briefing.patterns:
        for pattern in briefing.patterns:
            lines.append(f"  {pattern}")
    else:
        lines.append("  No significant patterns detected")

    lines.append("=" * 64)

    return "\n".join(lines)


def format_briefing_json(briefing: BriefingData) -> str:
    """
    Format briefing as JSON.

    Args:
        briefing: BriefingData to format

    Returns:
        JSON string
    """
    import json

    data = {
        "generated_at": briefing.generated_at.isoformat(),
        "period": briefing.period,
        "portfolio_pulse": {
            "active_projects": briefing.active_projects,
            "recent_commits_24h": briefing.recent_commits_24h,
            "total_commits_7d": briefing.total_commits_7d,
            "blockers": briefing.blockers,
        },
        "priority_actions": briefing.priority_actions,
        "patterns_noticed": briefing.patterns,
        "waiting_on": briefing.waiting_on,
    }

    return json.dumps(data, indent=2)



def get_executive_summary(briefing: BriefingData) -> str:
    """
    Generate a concise, high-impact executive summary (Operator Persona).
    
    Format: "Morning, Jesse. [Active] Active Projects. [Blockers] Blockers. Top Priority: [Action]. [Pattern]."
    """
    parts = []
    
    # Greeting based on time
    hour = datetime.now().hour
    greeting = "Morning" if 5 <= hour < 12 else "Afternoon" if 12 <= hour < 17 else "Evening"
    parts.append(f"{greeting}, Jesse.")
    
    # Pulse
    active_count = len(briefing.active_projects)
    parts.append(f"{active_count} Active Projects.")
    
    # Blockers
    blocker_count = len(briefing.blockers)
    if blocker_count > 0:
        parts.append(f"{blocker_count} Blockers.")
    else:
        parts.append("Systems Nominal.")
        
    # Top Priority
    if briefing.priority_actions:
        top_action = briefing.priority_actions[0]
        parts.append(f"Top Priority: {top_action['title']}.")
    else:
        parts.append("No immediate actions.")
        
    # Pattern
    if briefing.patterns:
        # Pick the most interesting pattern (usually the first one)
        parts.append(f"Insight: {briefing.patterns[0]}.")
        
    return " ".join(parts)


if __name__ == "__main__":
    # Test the briefing generator
    briefing = generate_daily_briefing()
    print(format_briefing(briefing))
    print("\n--- EXECUTIVE SUMMARY ---\n")
    print(get_executive_summary(briefing))
