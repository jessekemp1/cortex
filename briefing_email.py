"""Kempion-infused Cortex morning briefing email generator.

Generates a full HTML briefing combining:
- Kempion dawn wisdom (poet-warrior-monk)
- What Cortex is learning (intelligence metrics + patterns)
- Portfolio insights (cross-project intelligence)
- 5 next tasks per active project
- Full Cortex briefing data
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

try:
    from briefing import BriefingData, BriefingGenerator
except ImportError:
    BriefingData = None
    BriefingGenerator = None

try:
    from motivation.api import KempionApp
except ImportError:
    KempionApp = None

try:
    from task_discovery import get_all_tasks
except ImportError:
    get_all_tasks = None

try:
    from recommendation_engine import RecommendationEngine
except ImportError:
    RecommendationEngine = None


# Default seeker profile for Jesse's Kempion configuration
DEFAULT_SEEKER_CONFIG = {
    "name": "Jesse",
    "core_values": ["truth", "discipline", "craft", "sovereignty", "silence"],
    "tone_preference": "tempered",
    "depth_preference": "root",
    "tradition_affinity": {
        "stoic": 0.85,
        "zen": 0.6,
        "existentialist": 0.55,
        "martial": 0.5,
        "poetic": 0.65,
        "pragmatist": 0.5,
        "contemplative": 0.45,
    },
}


def generate_morning_briefing_html(
    root_dir: Optional[Path] = None,
    seeker_config: Optional[dict] = None,
) -> dict[str, str]:
    """Generate a full Kempion-infused morning briefing.

    Returns:
        dict with keys: 'html', 'text', 'subject'
    """
    now = datetime.now()
    config = seeker_config or DEFAULT_SEEKER_CONFIG

    # --- 1. Generate Kempion wisdom ---
    kempion_section = _generate_kempion_section(config)

    # --- 2. Generate Cortex briefing ---
    briefing = None
    if BriefingGenerator:
        try:
            generator = BriefingGenerator(root_dir)
            briefing = generator.generate_daily_briefing()
        except Exception:
            pass

    # --- 3. Build all sections ---
    learning_section = _build_learning_section(briefing)
    insights_section = _build_insights_section(briefing)
    project_tasks_section = _build_project_tasks_section(briefing, root_dir)
    portfolio_section = _build_portfolio_section(briefing)
    blockers_section = _build_blockers_section(briefing)

    # --- 4. Compose HTML ---
    date_str = now.strftime("%A, %B %d, %Y")
    subject = f"Kempion Dawn Briefing — {now.strftime('%b %d')}"

    html = _compose_html(
        date_str=date_str,
        kempion=kempion_section,
        learning=learning_section,
        insights=insights_section,
        project_tasks=project_tasks_section,
        portfolio=portfolio_section,
        blockers=blockers_section,
    )

    text = _compose_text(
        date_str=date_str,
        kempion=kempion_section,
        learning=learning_section,
        insights=insights_section,
        project_tasks=project_tasks_section,
        portfolio=portfolio_section,
        blockers=blockers_section,
    )

    return {"html": html, "text": text, "subject": subject}


def _generate_kempion_section(config: dict) -> dict:
    """Generate the Kempion dawn wisdom section."""
    section: dict[str, Any] = {
        "greeting": "Another day on the path. Let's walk.",
        "wisdom_text": "",
        "wisdom_author": "",
        "wisdom_source": "",
        "reflection_prompt": "What is the base truth of this moment?",
        "focus_prompt": "What is the one thing that matters most today?",
    }

    if not KempionApp:
        return section

    try:
        app = KempionApp()
        app.initialize()

        profile = app.create_seeker(**config)
        briefing = app.get_dawn_briefing(profile.id)

        if briefing:
            section["greeting"] = briefing.get("greeting", section["greeting"])
            wisdom = briefing.get("wisdom", {})
            section["wisdom_text"] = wisdom.get("text", "")
            section["wisdom_author"] = wisdom.get("author", "")
            section["reflection_prompt"] = wisdom.get(
                "reflection_prompt", section["reflection_prompt"]
            )
            section["focus_prompt"] = briefing.get(
                "focus_prompt", section["focus_prompt"]
            )
    except Exception:
        pass

    return section


def _build_learning_section(briefing: Optional[Any]) -> dict:
    """Build the 'What Cortex is Learning' section."""
    section: dict[str, Any] = {"metrics": {}, "patterns": [], "available": False}

    if not briefing:
        return section

    # Intelligence metrics
    metrics = getattr(briefing, "intelligence_metrics", None) or {}
    if metrics:
        section["available"] = True
        section["metrics"] = {
            "recommendation_accuracy": metrics.get("recommendation_accuracy"),
            "confidence_calibration": metrics.get("confidence_calibration"),
            "success_rate": metrics.get("success_rate"),
            "total_outcomes": metrics.get("total_outcomes"),
        }

    # Patterns from briefing
    patterns = getattr(briefing, "patterns", []) or []
    if patterns:
        section["available"] = True
        section["patterns"] = patterns[:5]

    # Predictive insights
    predictive = getattr(briefing, "predictive_insights", None) or {}
    if predictive:
        section["available"] = True
        section["likely_focus"] = predictive.get("likely_focus")
        section["optimal_sequence"] = predictive.get("optimal_sequence", [])[:3]

    return section


def _build_insights_section(briefing: Optional[Any]) -> dict:
    """Build the cross-project insights section."""
    section: dict[str, Any] = {
        "health": {},
        "shared_patterns": [],
        "lessons": [],
        "strategic": {},
        "available": False,
    }

    if not briefing:
        return section

    cross = getattr(briefing, "cross_project_insights", None) or {}
    if cross:
        section["available"] = True
        section["health"] = cross.get("portfolio_health", {})
        section["shared_patterns"] = cross.get("shared_patterns", [])[:3]
        section["lessons"] = cross.get("relevant_lessons", [])[:3]

    strategic = getattr(briefing, "strategic_alignment", None) or {}
    if strategic:
        section["available"] = True
        section["strategic"] = {
            "goal_velocity": strategic.get("goal_velocity"),
            "drift_detected": strategic.get("drift_detected", False),
            "alignment_score": strategic.get("alignment_score"),
        }

    return section


def _build_project_tasks_section(
    briefing: Optional[Any], root_dir: Optional[Path] = None
) -> list[dict]:
    """Build 5 next tasks per active project."""
    projects: list[dict] = []

    if not briefing:
        return projects

    active_projects = getattr(briefing, "active_projects", []) or []
    snapshot = getattr(briefing, "project_snapshot", []) or []
    priority_actions = getattr(briefing, "priority_actions", []) or []

    # Build task list per project
    for project_name in active_projects[:8]:
        project_data: dict[str, Any] = {
            "name": project_name,
            "tasks": [],
            "commits_7d": 0,
            "status": "active",
        }

        # Get snapshot data
        for snap in snapshot:
            if snap.get("project") == project_name:
                project_data["commits_7d"] = snap.get("commits_7d", 0)
                project_data["status"] = snap.get("status", "active")
                project_data["trend"] = snap.get("trend", "")
                break

        # Get priority actions for this project
        for action in priority_actions:
            if action.get("project") == project_name and len(project_data["tasks"]) < 5:
                project_data["tasks"].append({
                    "title": action.get("title", ""),
                    "priority": action.get("priority", "MEDIUM"),
                    "source": action.get("source", ""),
                    "rationale": action.get("rationale", "")[:100],
                })

        # Try task_discovery for remaining slots
        if get_all_tasks and len(project_data["tasks"]) < 5:
            try:
                all_tasks = get_all_tasks()
                project_tasks = [
                    t for t in all_tasks
                    if t.get("project", "").lower() == project_name.lower()
                ]
                for task in project_tasks:
                    if len(project_data["tasks"]) >= 5:
                        break
                    title = task.get("name", task.get("title", ""))
                    if title and not any(
                        t["title"].lower() == title.lower() for t in project_data["tasks"]
                    ):
                        project_data["tasks"].append({
                            "title": title,
                            "priority": "MEDIUM",
                            "source": "task_discovery",
                            "rationale": "",
                        })
            except Exception:
                pass

        # Fill remaining with generic next actions from goals/blockers
        blockers = getattr(briefing, "blockers", []) or []
        for blocker in blockers:
            if len(project_data["tasks"]) >= 5:
                break
            if blocker.get("project") == project_name:
                project_data["tasks"].append({
                    "title": f"Resolve: {blocker.get('blocker', 'Unknown blocker')}",
                    "priority": "HIGH",
                    "source": "blocker",
                    "rationale": "",
                })

        projects.append(project_data)

    return projects


def _build_portfolio_section(briefing: Optional[Any]) -> dict:
    """Build the portfolio pulse section."""
    section: dict[str, Any] = {
        "active_count": 0,
        "commits_24h": 0,
        "commits_7d": 0,
        "available": False,
    }

    if not briefing:
        return section

    section["active_count"] = len(getattr(briefing, "active_projects", []) or [])
    section["commits_24h"] = getattr(briefing, "recent_commits_24h", 0)
    section["commits_7d"] = getattr(briefing, "total_commits_7d", 0)
    section["available"] = section["active_count"] > 0

    # Resource intelligence
    resource = getattr(briefing, "resource_intelligence", None) or {}
    if resource:
        section["burn_rate"] = resource.get("burn_rate")
        section["weekly_projection"] = resource.get("weekly_projection")

    # Velocity
    velocity = getattr(briefing, "velocity_metrics", None) or {}
    if velocity:
        section["velocity"] = velocity

    return section


def _build_blockers_section(briefing: Optional[Any]) -> list[dict]:
    """Build the blockers section."""
    if not briefing:
        return []
    return (getattr(briefing, "blockers", []) or [])[:10]


# --- HTML Composition ---

def _compose_html(
    date_str: str,
    kempion: dict,
    learning: dict,
    insights: dict,
    project_tasks: list[dict],
    portfolio: dict,
    blockers: list[dict],
) -> str:
    """Compose the full HTML email."""

    # Kempion wisdom section
    wisdom_html = ""
    if kempion.get("wisdom_text"):
        wisdom_html = f"""
        <div style="background:#1a1a2e; color:#e0e0e0; padding:24px 28px; border-radius:8px; margin:20px 0; border-left:4px solid #c4a35a;">
            <p style="font-size:20px; font-style:italic; line-height:1.6; margin:0 0 12px 0; color:#f0e6d3;">
                &ldquo;{_esc(kempion['wisdom_text'])}&rdquo;
            </p>
            <p style="text-align:right; color:#c4a35a; margin:0; font-size:14px;">
                &mdash; {_esc(kempion.get('wisdom_author', ''))}
            </p>
        </div>
        <p style="color:#888; font-style:italic; font-size:14px; margin:8px 0 0 0;">
            {_esc(kempion.get('reflection_prompt', ''))}
        </p>
        """

    # Learning section
    learning_html = ""
    if learning.get("available"):
        metrics = learning.get("metrics", {})
        patterns = learning.get("patterns", [])
        items = []
        if metrics.get("recommendation_accuracy") is not None:
            acc = metrics["recommendation_accuracy"]
            items.append(f"<li>Recommendation accuracy: <strong>{acc:.0%}</strong></li>")
        if metrics.get("success_rate") is not None:
            sr = metrics["success_rate"]
            items.append(f"<li>Success rate: <strong>{sr:.0%}</strong></li>")
        if metrics.get("total_outcomes") is not None:
            items.append(f"<li>Total outcomes tracked: <strong>{metrics['total_outcomes']}</strong></li>")
        for p in patterns[:3]:
            items.append(f"<li>{_esc(str(p))}</li>")

        likely = learning.get("likely_focus")
        if likely:
            items.append(f"<li>Predicted focus today: <strong>{_esc(str(likely))}</strong></li>")

        if items:
            learning_html = f"""
            <h2 style="color:#c4a35a; font-size:18px; border-bottom:1px solid #333; padding-bottom:8px;">
                What Cortex Is Learning
            </h2>
            <ul style="color:#ccc; line-height:1.8;">{''.join(items)}</ul>
            """

    # Cross-project insights
    insights_html = ""
    if insights.get("available"):
        items = []
        health = insights.get("health", {})
        if health:
            healthy = health.get("healthy_count", 0)
            at_risk = health.get("at_risk_count", 0)
            items.append(f"<li>Portfolio: <strong>{healthy} healthy</strong>, {at_risk} at risk</li>")

        strategic = insights.get("strategic", {})
        if strategic.get("drift_detected"):
            items.append('<li style="color:#e74c3c;">Strategic drift detected — review goal alignment</li>')
        if strategic.get("alignment_score") is not None:
            items.append(f"<li>Strategic alignment: <strong>{strategic['alignment_score']:.0%}</strong></li>")

        for pattern in insights.get("shared_patterns", []):
            p_text = pattern.get("pattern", str(pattern)) if isinstance(pattern, dict) else str(pattern)
            items.append(f"<li>{_esc(p_text[:100])}</li>")

        for lesson in insights.get("lessons", []):
            l_text = lesson.get("lesson", str(lesson)) if isinstance(lesson, dict) else str(lesson)
            l_proj = lesson.get("project", "") if isinstance(lesson, dict) else ""
            prefix = f"[{_esc(l_proj)}] " if l_proj else ""
            items.append(f"<li>{prefix}{_esc(l_text[:100])}</li>")

        if items:
            insights_html = f"""
            <h2 style="color:#c4a35a; font-size:18px; border-bottom:1px solid #333; padding-bottom:8px;">
                Portfolio Insights
            </h2>
            <ul style="color:#ccc; line-height:1.8;">{''.join(items)}</ul>
            """

    # Project tasks (5 per project)
    projects_html = ""
    if project_tasks:
        project_blocks = []
        for proj in project_tasks:
            name = _esc(proj["name"])
            commits = proj.get("commits_7d", 0)
            trend = proj.get("trend", "")
            trend_icon = {"hot": "🔥", "active": "⚡", "steady": "→", "idle": "·"}.get(trend, "")

            tasks_rows = ""
            for i, task in enumerate(proj.get("tasks", []), 1):
                priority = task.get("priority", "MEDIUM")
                p_color = {"HIGH": "#e74c3c", "MEDIUM": "#f39c12", "LOW": "#27ae60"}.get(priority, "#888")
                tasks_rows += f"""
                <tr>
                    <td style="padding:4px 8px; color:#888; font-size:13px;">{i}.</td>
                    <td style="padding:4px 8px; color:#e0e0e0; font-size:13px;">{_esc(task.get('title', ''))}</td>
                    <td style="padding:4px 8px; font-size:12px;"><span style="color:{p_color};">{priority}</span></td>
                </tr>"""

            if not tasks_rows:
                tasks_rows = '<tr><td colspan="3" style="padding:4px 8px; color:#666; font-style:italic;">No tasks discovered</td></tr>'

            project_blocks.append(f"""
            <div style="margin-bottom:20px;">
                <h3 style="color:#e0e0e0; font-size:15px; margin:0 0 8px 0;">
                    {trend_icon} {name}
                    <span style="color:#666; font-weight:normal; font-size:12px; margin-left:8px;">{commits} commits (7d)</span>
                </h3>
                <table style="width:100%; border-collapse:collapse;">{tasks_rows}</table>
            </div>""")

        projects_html = f"""
        <h2 style="color:#c4a35a; font-size:18px; border-bottom:1px solid #333; padding-bottom:8px;">
            Next 5 Tasks Per Project
        </h2>
        {''.join(project_blocks)}
        """

    # Portfolio pulse
    portfolio_html = ""
    if portfolio.get("available"):
        portfolio_html = f"""
        <h2 style="color:#c4a35a; font-size:18px; border-bottom:1px solid #333; padding-bottom:8px;">
            Portfolio Pulse
        </h2>
        <table style="color:#ccc; font-size:14px; line-height:2;">
            <tr><td style="padding-right:16px;">Active projects:</td><td><strong>{portfolio['active_count']}</strong></td></tr>
            <tr><td style="padding-right:16px;">Commits (24h):</td><td><strong>{portfolio['commits_24h']}</strong></td></tr>
            <tr><td style="padding-right:16px;">Commits (7d):</td><td><strong>{portfolio['commits_7d']}</strong></td></tr>
        </table>
        """

    # Blockers
    blockers_html = ""
    if blockers:
        blocker_items = ""
        for b in blockers:
            blocker_items += f'<li><strong>{_esc(b.get("project", ""))}</strong>: {_esc(b.get("blocker", ""))}</li>'
        blockers_html = f"""
        <h2 style="color:#e74c3c; font-size:18px; border-bottom:1px solid #333; padding-bottom:8px;">
            Blockers
        </h2>
        <ul style="color:#ccc; line-height:1.8;">{blocker_items}</ul>
        """

    # Focus prompt
    focus_html = ""
    if kempion.get("focus_prompt"):
        focus_html = f"""
        <div style="background:#1a1a2e; padding:16px 20px; border-radius:8px; margin:20px 0; text-align:center;">
            <p style="color:#c4a35a; font-size:16px; font-style:italic; margin:0;">
                {_esc(kempion['focus_prompt'])}
            </p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="background:#0d0d1a; color:#e0e0e0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace; margin:0; padding:0;">
<div style="max-width:640px; margin:0 auto; padding:32px 24px;">

    <!-- Header -->
    <div style="text-align:center; margin-bottom:24px;">
        <h1 style="color:#c4a35a; font-size:24px; letter-spacing:2px; margin:0;">KEMPION</h1>
        <p style="color:#666; font-size:13px; margin:4px 0 0 0;">Dawn Briefing &mdash; {_esc(date_str)}</p>
    </div>

    <!-- Greeting -->
    <p style="color:#999; font-size:15px; font-style:italic; margin:0 0 8px 0;">
        {_esc(kempion.get('greeting', ''))}
    </p>

    <!-- Wisdom -->
    {wisdom_html}

    <!-- Learning -->
    {learning_html}

    <!-- Insights -->
    {insights_html}

    <!-- Project Tasks -->
    {projects_html}

    <!-- Portfolio -->
    {portfolio_html}

    <!-- Blockers -->
    {blockers_html}

    <!-- Focus -->
    {focus_html}

    <!-- Footer -->
    <div style="text-align:center; margin-top:32px; padding-top:16px; border-top:1px solid #222;">
        <p style="color:#444; font-size:12px; margin:0;">
            Cortex &middot; Kempion Wisdom Engine &middot; Poet-Warrior-Monk
        </p>
    </div>

</div>
</body>
</html>"""


def _compose_text(
    date_str: str,
    kempion: dict,
    learning: dict,
    insights: dict,
    project_tasks: list[dict],
    portfolio: dict,
    blockers: list[dict],
) -> str:
    """Compose plain-text fallback."""
    lines = [
        f"KEMPION — Dawn Briefing — {date_str}",
        "=" * 50,
        "",
        kempion.get("greeting", ""),
        "",
    ]

    if kempion.get("wisdom_text"):
        lines.extend([
            f'  "{kempion["wisdom_text"]}"',
            f'  — {kempion.get("wisdom_author", "")}',
            "",
            f'  {kempion.get("reflection_prompt", "")}',
            "",
        ])

    if learning.get("available"):
        lines.append("WHAT CORTEX IS LEARNING")
        lines.append("-" * 30)
        metrics = learning.get("metrics", {})
        if metrics.get("recommendation_accuracy") is not None:
            lines.append(f"  Recommendation accuracy: {metrics['recommendation_accuracy']:.0%}")
        for p in learning.get("patterns", []):
            lines.append(f"  - {p}")
        lines.append("")

    if insights.get("available"):
        lines.append("PORTFOLIO INSIGHTS")
        lines.append("-" * 30)
        for pattern in insights.get("shared_patterns", []):
            p_text = pattern.get("pattern", str(pattern)) if isinstance(pattern, dict) else str(pattern)
            lines.append(f"  - {p_text[:100]}")
        for lesson in insights.get("lessons", []):
            l_text = lesson.get("lesson", str(lesson)) if isinstance(lesson, dict) else str(lesson)
            lines.append(f"  - {l_text[:100]}")
        lines.append("")

    if project_tasks:
        lines.append("NEXT 5 TASKS PER PROJECT")
        lines.append("-" * 30)
        for proj in project_tasks:
            lines.append(f"\n  {proj['name']} ({proj.get('commits_7d', 0)} commits 7d)")
            for i, task in enumerate(proj.get("tasks", []), 1):
                lines.append(f"    {i}. [{task.get('priority', 'MED')}] {task.get('title', '')}")
        lines.append("")

    if portfolio.get("available"):
        lines.append("PORTFOLIO PULSE")
        lines.append("-" * 30)
        lines.append(f"  Active: {portfolio['active_count']} | 24h: {portfolio['commits_24h']} commits | 7d: {portfolio['commits_7d']} commits")
        lines.append("")

    if blockers:
        lines.append("BLOCKERS")
        lines.append("-" * 30)
        for b in blockers:
            lines.append(f"  [{b.get('project', '')}] {b.get('blocker', '')}")
        lines.append("")

    if kempion.get("focus_prompt"):
        lines.extend(["", kempion["focus_prompt"], ""])

    lines.append("—")
    lines.append("Cortex · Kempion · Poet-Warrior-Monk")

    return "\n".join(lines)


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
