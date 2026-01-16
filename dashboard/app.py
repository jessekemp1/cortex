#!/usr/bin/env python3
"""
Cortex Intelligence Dashboard v2

Decision-focused dashboard that answers:
- What should I work on now?
- How effective am I being?
- What has Cortex learned?
- Where are the problems?
"""

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# === Configuration ===
CORTEX_DATA = Path.home() / ".cortex"
DEV_DIR = Path.home() / "Dev"
CLAUDE_DATA = Path.home() / ".claude"

# Database paths
CORTEX_DB = CORTEX_DATA / "cortex.db"
COMMAND_DB = CORTEX_DATA / "command_tracking.db"

# Files
OUTCOMES_FILE = CORTEX_DATA / "outcomes.jsonl"
INTERACTION_QUEUE = CORTEX_DATA / "interaction_queue.jsonl"
ACTION_PLAN = DEV_DIR / "ACTION_PLAN.md"


# === Data Loading ===
def load_jsonl(path: Path, limit: int = 500) -> List[Dict[str, Any]]:
    """Load entries from JSONL file."""
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]


def query_db(db_path: Path, query: str, params: tuple = ()) -> pd.DataFrame:
    """Query SQLite database safely."""
    if not db_path.exists():
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def parse_action_plan() -> Dict[str, Any]:
    """Parse ACTION_PLAN.md into structured data."""
    if not ACTION_PLAN.exists():
        return {"items": [], "priorities": {}}

    content = ACTION_PLAN.read_text()
    items = []
    current_item = None
    current_priority = "C"

    for line in content.split("\n"):
        line = line.strip()

        # Detect priority headers
        if "Priority A" in line:
            current_priority = "A"
        elif "Priority B" in line:
            current_priority = "B"
        elif "Priority C" in line:
            current_priority = "C"

        # Detect item headers (#### N. **Name**)
        if line.startswith("####") and "**" in line:
            if current_item:
                items.append(current_item)

            # Extract name
            name = line.split("**")[1] if "**" in line else line[4:].strip()
            current_item = {
                "name": name,
                "priority": current_priority,
                "status": "pending",
                "project": "",
                "progress": 0,
            }

        # Detect status
        if current_item and line.startswith("**Status:**"):
            status = line.replace("**Status:**", "").strip().lower()
            current_item["status"] = status

        # Detect project
        if current_item and line.startswith("**Project:**"):
            current_item["project"] = line.replace("**Project:**", "").strip()

        # Detect progress
        if current_item and line.startswith("**Progress:**"):
            try:
                progress = int(line.replace("**Progress:**", "").replace("%", "").strip())
                current_item["progress"] = progress
            except ValueError:
                pass

    if current_item:
        items.append(current_item)

    # Group by priority
    priorities = {"A": [], "B": [], "C": []}
    for item in items:
        p = item.get("priority", "C")
        if p in priorities:
            priorities[p].append(item)

    return {"items": items, "priorities": priorities}


def analyze_productivity(interactions: List[Dict]) -> Dict[str, Any]:
    """Analyze productivity patterns from interactions."""
    if not interactions:
        return {}

    # Parse timestamps
    hourly = defaultdict(int)
    daily = defaultdict(int)
    projects = defaultdict(int)

    for i in interactions:
        ts_str = i.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            hourly[ts.hour] += 1
            daily[ts.strftime("%A")] += 1
        except (ValueError, TypeError):
            pass

        project = i.get("project", "unknown")
        if project:
            projects[project] += 1

    # Find peak hours
    peak_hour = max(hourly.items(), key=lambda x: x[1])[0] if hourly else 12
    peak_day = max(daily.items(), key=lambda x: x[1])[0] if daily else "Monday"

    return {
        "hourly": dict(hourly),
        "daily": dict(daily),
        "projects": dict(projects),
        "peak_hour": peak_hour,
        "peak_day": peak_day,
        "total_interactions": len(interactions),
    }


def calculate_success_trends(outcomes: List[Dict], window_days: int = 7) -> Dict[str, Any]:
    """Calculate success rate trends."""
    if not outcomes:
        return {"current_rate": 0, "trend": 0, "by_type": {}}

    now = datetime.now()
    recent = []
    older = []

    for o in outcomes:
        ts_str = o.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            age = (now - ts).days
            if age <= window_days:
                recent.append(o)
            elif age <= window_days * 2:
                older.append(o)
        except (ValueError, TypeError):
            pass

    def success_rate(items):
        if not items:
            return 0
        successes = sum(1 for i in items if i.get("outcome") == "success")
        return successes / len(items) * 100

    current_rate = success_rate(recent)
    previous_rate = success_rate(older)
    trend = current_rate - previous_rate

    # By type
    by_type = defaultdict(lambda: {"success": 0, "total": 0})
    for o in outcomes:
        t = o.get("recommendation_type", "unknown")
        by_type[t]["total"] += 1
        if o.get("outcome") == "success":
            by_type[t]["success"] += 1

    type_rates = {
        k: round(v["success"] / v["total"] * 100, 1) if v["total"] > 0 else 0
        for k, v in by_type.items()
    }

    return {
        "current_rate": round(current_rate, 1),
        "previous_rate": round(previous_rate, 1),
        "trend": round(trend, 1),
        "by_type": type_rates,
        "recent_count": len(recent),
    }


def get_stale_items(action_plan: Dict, days_threshold: int = 14) -> List[Dict]:
    """Find items that might be stuck or forgotten."""
    stale = []
    for item in action_plan.get("items", []):
        status = item.get("status", "").lower()
        if status == "in_progress" and item.get("progress", 0) < 50:
            stale.append({**item, "reason": "Low progress while in_progress"})
        elif status == "pending" and item.get("priority") == "A":
            stale.append({**item, "reason": "Priority A still pending"})
    return stale


def generate_recommendations(
    action_plan: Dict, outcomes: List[Dict], productivity: Dict
) -> List[Dict[str, str]]:
    """Generate smart recommendations based on data."""
    recommendations = []

    # Check ACTION_PLAN
    priority_a = action_plan.get("priorities", {}).get("A", [])
    in_progress_a = [i for i in priority_a if i.get("status") == "in_progress"]
    pending_a = [i for i in priority_a if i.get("status") == "pending"]

    if pending_a:
        recommendations.append(
            {
                "priority": "HIGH",
                "action": f"Start Priority A item: {pending_a[0].get('name', 'Unknown')}",
                "reason": f"{len(pending_a)} Priority A items still pending",
            }
        )

    if len(in_progress_a) > 2:
        recommendations.append(
            {
                "priority": "MEDIUM",
                "action": "Focus - too many items in progress",
                "reason": f"{len(in_progress_a)} Priority A items in progress simultaneously",
            }
        )

    # Check success trends
    trends = calculate_success_trends(outcomes)
    if trends.get("trend", 0) < -10:
        recommendations.append(
            {
                "priority": "HIGH",
                "action": "Review recent failures",
                "reason": f"Success rate dropped {abs(trends['trend']):.0f}% this week",
            }
        )

    # Check productivity
    if productivity:
        peak = productivity.get("peak_hour", 12)
        current_hour = datetime.now().hour
        if abs(current_hour - peak) <= 2:
            recommendations.append(
                {
                    "priority": "LOW",
                    "action": "Peak productivity time - tackle hard problems now",
                    "reason": f"Your most productive hour is around {peak}:00",
                }
            )

    # Check stale items
    stale = get_stale_items(action_plan)
    if stale:
        recommendations.append(
            {
                "priority": "MEDIUM",
                "action": f"Review stale item: {stale[0].get('name', 'Unknown')}",
                "reason": stale[0].get("reason", "Item may be stuck"),
            }
        )

    return recommendations


# === Page Config ===
st.set_page_config(
    page_title="Cortex Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for cleaner look
st.markdown(
    """
<style>
    .stMetric { background: #1a1a2e; padding: 15px; border-radius: 10px; }
    .recommendation-high { border-left: 4px solid #ff4444; padding-left: 10px; }
    .recommendation-medium { border-left: 4px solid #ffaa00; padding-left: 10px; }
    .recommendation-low { border-left: 4px solid #44aa44; padding-left: 10px; }
</style>
""",
    unsafe_allow_html=True,
)

# === Load All Data ===
action_plan = parse_action_plan()
outcomes = load_jsonl(OUTCOMES_FILE)
interactions = load_jsonl(INTERACTION_QUEUE)
productivity = analyze_productivity(interactions)
trends = calculate_success_trends(outcomes)
recommendations = generate_recommendations(action_plan, outcomes, productivity)

# === Header ===
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.title("🧠 Cortex Intelligence")
with col2:
    st.metric(
        "Success Rate",
        f"{trends.get('current_rate', 0):.0f}%",
        f"{trends.get('trend', 0):+.0f}%",
    )
with col3:
    if st.button("🔄 Refresh"):
        st.rerun()

st.markdown("---")

# === Main Layout: 3 Columns ===
left, middle, right = st.columns([1, 1, 1])

# === LEFT: What to Do Now ===
with left:
    st.subheader("🎯 What to Do Now")

    if recommendations:
        for rec in recommendations[:4]:
            priority = rec.get("priority", "LOW")
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
            st.markdown(
                f"""
            {icon} **{rec.get('action', '')}**
            <small style='color: gray;'>{rec.get('reason', '')}</small>
            """,
                unsafe_allow_html=True,
            )
            st.markdown("")
    else:
        st.success("No urgent recommendations. You're on track!")

    st.markdown("---")

    # Priority A Status
    st.markdown("**Priority A Items**")
    priority_a = action_plan.get("priorities", {}).get("A", [])
    if priority_a:
        for item in priority_a[:5]:
            status = item.get("status", "pending")
            icon = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}.get(status, "⬜")
            progress = item.get("progress", 0)
            name = item.get("name", "Unknown")[:40]
            st.markdown(f"{icon} {name} ({progress}%)")
    else:
        st.info("No Priority A items found")

# === MIDDLE: Productivity Insights ===
with middle:
    st.subheader("📊 Productivity Insights")

    if productivity:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Peak Hour", f"{productivity.get('peak_hour', 12)}:00")
        with col2:
            st.metric("Peak Day", productivity.get("peak_day", "N/A"))

        st.markdown("---")

        # Hourly distribution
        st.markdown("**Activity by Hour**")
        hourly = productivity.get("hourly", {})
        if hourly:
            # Create 24-hour chart
            hours = list(range(24))
            counts = [hourly.get(h, 0) for h in hours]
            chart_df = pd.DataFrame({"Hour": hours, "Activity": counts})
            st.bar_chart(chart_df.set_index("Hour"), height=150)

        # Project focus
        st.markdown("**Project Focus (Last 500 interactions)**")
        projects = productivity.get("projects", {})
        if projects:
            sorted_projects = sorted(projects.items(), key=lambda x: -x[1])[:5]
            for proj, count in sorted_projects:
                pct = count / productivity.get("total_interactions", 1) * 100
                st.markdown(f"- **{proj}**: {pct:.0f}%")
    else:
        st.info("Not enough data for productivity insights yet")

# === RIGHT: Learning & Trends ===
with right:
    st.subheader("📈 Learning & Trends")

    # Success by type
    st.markdown("**Success Rate by Type**")
    by_type = trends.get("by_type", {})
    if by_type:
        sorted_types = sorted(by_type.items(), key=lambda x: -x[1])
        for t, rate in sorted_types[:5]:
            color = "🟢" if rate >= 70 else "🟡" if rate >= 50 else "🔴"
            st.markdown(f"{color} **{t[:25]}**: {rate:.0f}%")
    else:
        st.info("No outcome data yet")

    st.markdown("---")

    # Recent outcomes
    st.markdown("**Recent Outcomes**")
    if outcomes:
        for o in reversed(outcomes[-5:]):
            outcome = o.get("outcome", "unknown")
            icon = {"success": "✅", "partial": "🔶", "failed": "❌"}.get(outcome, "❓")
            title = o.get("recommendation_title", "")[:35]
            st.markdown(f"{icon} {title}")
    else:
        st.info("No outcomes logged yet")

st.markdown("---")

# === Bottom Section: Detailed Views ===
tab1, tab2, tab3 = st.tabs(["📋 Full ACTION_PLAN", "🕐 Session History", "⚙️ System"])

with tab1:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Priority A")
        for item in action_plan.get("priorities", {}).get("A", []):
            status_icon = {"completed": "✅", "in_progress": "🔄"}.get(item.get("status", ""), "⬜")
            st.markdown(f"{status_icon} **{item.get('name', '')}**")
            st.markdown(f"   {item.get('project', '')} | {item.get('progress', 0)}%")

    with col2:
        st.markdown("### Priority B")
        for item in action_plan.get("priorities", {}).get("B", [])[:6]:
            status_icon = {"completed": "✅", "in_progress": "🔄"}.get(item.get("status", ""), "⬜")
            st.markdown(f"{status_icon} **{item.get('name', '')}**")

    with col3:
        st.markdown("### Priority C (Evaluate/Archive)")
        for item in action_plan.get("priorities", {}).get("C", [])[:6]:
            st.markdown(f"⬜ {item.get('name', '')[:30]}")

with tab2:
    st.markdown("### Interaction Patterns")
    if interactions:
        # Daily activity
        daily_counts = defaultdict(int)
        for i in interactions[-200:]:
            ts_str = i.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                daily_counts[ts.strftime("%Y-%m-%d")] += 1
            except (ValueError, TypeError):
                pass

        if daily_counts:
            df = pd.DataFrame(list(daily_counts.items()), columns=["Date", "Interactions"])
            df = df.sort_values("Date")
            st.line_chart(df.set_index("Date"))
    else:
        st.info("No interaction data available")

with tab3:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Data Files")
        files = [
            ("ACTION_PLAN.md", ACTION_PLAN),
            ("outcomes.jsonl", OUTCOMES_FILE),
            ("interaction_queue.jsonl", INTERACTION_QUEUE),
            ("cortex.db", CORTEX_DB),
        ]
        for name, path in files:
            exists = "✅" if path.exists() else "❌"
            if path.exists():
                size = path.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / 1024 / 1024:.1f}MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size}B"
            else:
                size_str = "N/A"
            st.markdown(f"{exists} `{name}` ({size_str})")

    with col2:
        st.markdown("### Quick Stats")
        st.markdown(f"- **Outcomes logged:** {len(outcomes)}")
        st.markdown(f"- **Interactions tracked:** {len(interactions)}")
        st.markdown(f"- **ACTION_PLAN items:** {len(action_plan.get('items', []))}")

        # Cortex learning
        completed_a = sum(
            1
            for i in action_plan.get("priorities", {}).get("A", [])
            if i.get("status") == "completed"
        )
        total_a = len(action_plan.get("priorities", {}).get("A", []))
        if total_a > 0:
            st.markdown(f"- **Priority A completion:** {completed_a}/{total_a}")
