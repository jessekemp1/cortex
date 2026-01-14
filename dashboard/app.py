#!/usr/bin/env python3
"""
Cortex Intelligence Dashboard

Unified view of Claude Code + Cortex learning system.
Shows plugin insights, patterns, sessions, and recommendations.
"""

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# Data paths
CORTEX_DATA = Path.home() / ".cortex"
CLAUDE_DATA = Path.home() / ".claude"

# Database paths
CORTEX_DB = CORTEX_DATA / "cortex.db"
COMMAND_DB = CORTEX_DATA / "command_tracking.db"
SESSION_DB = CORTEX_DATA / "claude_sessions.db"

# JSONL files
OUTCOMES_FILE = CORTEX_DATA / "outcomes.jsonl"
PLUGIN_INSIGHTS_FILE = CORTEX_DATA / "plugin_insights.jsonl"
SESSION_SUMMARIES_FILE = CORTEX_DATA / "session_summaries.jsonl"
INTERACTION_QUEUE_FILE = CORTEX_DATA / "interaction_queue.jsonl"

# Pattern files
PATTERNS_DIR = CORTEX_DATA / "patterns"


def load_jsonl(path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    """Load recent entries from JSONL file."""
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


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def query_db(db_path: Path, query: str) -> pd.DataFrame:
    """Query SQLite database."""
    if not db_path.exists():
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"DB error: {e}")
        return pd.DataFrame()


# === Page Config ===
st.set_page_config(
    page_title="Cortex Intelligence Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# === Sidebar Navigation ===
st.sidebar.title("🧠 Cortex")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Plugin Insights", "Patterns", "Sessions", "Commands", "Outcomes"],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Data Dir:** `~/.cortex`")
st.sidebar.markdown(f"**Updated:** {datetime.now().strftime('%H:%M:%S')}")

if st.sidebar.button("🔄 Refresh"):
    st.rerun()


# === Overview Page ===
if page == "Overview":
    st.title("Cortex Intelligence Overview")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    # Count insights
    insights = load_jsonl(PLUGIN_INSIGHTS_FILE)
    with col1:
        st.metric("Plugin Insights", len(insights))

    # Count outcomes
    outcomes = load_jsonl(OUTCOMES_FILE)
    with col2:
        success_count = sum(1 for o in outcomes if o.get("outcome") == "success")
        st.metric("Outcomes Logged", len(outcomes), f"{success_count} success")

    # Count patterns
    patterns_file = PATTERNS_DIR / "plugin_extracted.json"
    patterns_data = load_json(patterns_file)
    patterns = patterns_data.get("patterns", [])
    with col3:
        st.metric("Patterns Extracted", len(patterns))

    # Session count
    sessions = load_jsonl(SESSION_SUMMARIES_FILE)
    with col4:
        st.metric("Sessions Tracked", len(sessions))

    st.markdown("---")

    # Recent Activity
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Recent Plugin Activity")
        if insights:
            recent = insights[-10:]
            for i in reversed(recent):
                ts = i.get("timestamp", "")[:16]
                source = i.get("source", "unknown")
                has_issues = "⚠️" if i.get("findings", {}).get("has_issues") else "✓"
                st.markdown(f"- `{ts}` {has_issues} **{source}**")
        else:
            st.info("No plugin insights yet. Use review agents to generate data.")

    with col2:
        st.subheader("📈 Recent Outcomes")
        if outcomes:
            recent = outcomes[-10:]
            for o in reversed(recent):
                ts = o.get("timestamp", "")[:10]
                title = o.get("recommendation_title", "")[:50]
                outcome = o.get("outcome", "unknown")
                icon = {"success": "✅", "partial": "🔶", "failed": "❌"}.get(outcome, "❓")
                st.markdown(f"- `{ts}` {icon} {title}")
        else:
            st.info("No outcomes logged yet.")

    st.markdown("---")

    # System Health
    st.subheader("🔧 System Health")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Data Files**")
        files = [
            ("outcomes.jsonl", OUTCOMES_FILE),
            ("plugin_insights.jsonl", PLUGIN_INSIGHTS_FILE),
            ("cortex.db", CORTEX_DB),
        ]
        for name, path in files:
            exists = "✅" if path.exists() else "❌"
            size = f"{path.stat().st_size / 1024:.1f}KB" if path.exists() else "N/A"
            st.markdown(f"- {exists} `{name}` ({size})")

    with col2:
        st.markdown("**Hooks Active**")
        settings = load_json(Path.home() / "Dev" / ".claude" / "settings.json")
        hooks = settings.get("hooks", {})
        for hook_type in ["SessionStart", "PostToolUse", "Stop"]:
            active = "✅" if hook_type in hooks else "❌"
            st.markdown(f"- {active} {hook_type}")

    with col3:
        st.markdown("**Plugins Installed**")
        plugins_file = CLAUDE_DATA / "plugins" / "installed_plugins.json"
        plugins_data = load_json(plugins_file)
        plugins = list(plugins_data.get("plugins", {}).keys())[:5]
        for p in plugins:
            st.markdown(f"- `{p.split('@')[0]}`")


# === Plugin Insights Page ===
elif page == "Plugin Insights":
    st.title("Plugin Insights")

    insights = load_jsonl(PLUGIN_INSIGHTS_FILE, limit=200)

    if not insights:
        st.info("No plugin insights captured yet. Use pr-review-toolkit or feature-dev agents.")
    else:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            sources = list(set(i.get("source", "unknown") for i in insights))
            selected_source = st.selectbox("Filter by Source", ["All"] + sources)
        with col2:
            projects = list(set(i.get("project", "unknown") for i in insights))
            selected_project = st.selectbox("Filter by Project", ["All"] + projects)

        # Apply filters
        filtered = insights
        if selected_source != "All":
            filtered = [i for i in filtered if i.get("source") == selected_source]
        if selected_project != "All":
            filtered = [i for i in filtered if i.get("project") == selected_project]

        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Insights", len(filtered))
        with col2:
            issues = sum(1 for i in filtered if i.get("findings", {}).get("has_issues"))
            st.metric("With Issues", issues)
        with col3:
            types = Counter(i.get("insight_type") for i in filtered)
            top_type = types.most_common(1)[0][0] if types else "N/A"
            st.metric("Top Type", top_type)

        st.markdown("---")

        # Insights Table
        st.subheader("Insights Detail")
        df_data = []
        for i in filtered:
            df_data.append({
                "Timestamp": i.get("timestamp", "")[:19],
                "Source": i.get("source", ""),
                "Type": i.get("insight_type", ""),
                "Project": i.get("project", ""),
                "Has Issues": "⚠️" if i.get("findings", {}).get("has_issues") else "✓",
                "Confidence": f"{i.get('confidence', 0):.2f}",
            })

        if df_data:
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)

        # Chart
        st.subheader("Insights by Type")
        type_counts = Counter(i.get("insight_type", "unknown") for i in filtered)
        if type_counts:
            chart_df = pd.DataFrame(list(type_counts.items()), columns=["Type", "Count"])
            st.bar_chart(chart_df.set_index("Type"))


# === Patterns Page ===
elif page == "Patterns":
    st.title("Extracted Patterns")

    patterns_file = PATTERNS_DIR / "plugin_extracted.json"
    patterns_data = load_json(patterns_file)
    patterns = patterns_data.get("patterns", [])

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**Last Updated:** {patterns_data.get('last_updated', 'Never')[:19]}")
    with col2:
        if st.button("Run Extraction"):
            import subprocess
            result = subprocess.run(
                ["python3", str(Path.home() / "Dev" / ".claude" / "scripts" / "extract_plugin_patterns.py")],
                capture_output=True,
                text=True,
            )
            st.code(result.stdout)
            st.rerun()

    if not patterns:
        st.info("No patterns extracted yet. Use review agents to accumulate insights, then run extraction.")
    else:
        # Pattern type breakdown
        col1, col2, col3 = st.columns(3)
        type_counts = Counter(p.get("type") for p in patterns)
        with col1:
            st.metric("Anti-Patterns", type_counts.get("anti_pattern", 0))
        with col2:
            st.metric("Observations", type_counts.get("observation", 0))
        with col3:
            st.metric("Lessons", type_counts.get("lesson", 0))

        st.markdown("---")

        # Patterns list
        for p in patterns:
            with st.expander(f"**{p.get('category', 'unknown')}** - {p.get('description', '')[:80]}"):
                st.markdown(f"**Type:** {p.get('type')}")
                st.markdown(f"**Confidence:** {p.get('confidence', 0):.2f}")
                st.markdown(f"**Recommendation:** {p.get('recommendation', 'N/A')}")
                st.markdown(f"**Extracted:** {p.get('extracted_at', '')[:19]}")


# === Sessions Page ===
elif page == "Sessions":
    st.title("Session History")

    sessions = load_jsonl(SESSION_SUMMARIES_FILE, limit=50)

    if not sessions:
        st.info("No session summaries yet. Sessions are logged when Claude Code exits.")
    else:
        # Session stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Sessions", len(sessions))
        with col2:
            total_insights = sum(s.get("insights_captured", 0) for s in sessions)
            st.metric("Total Insights Captured", total_insights)
        with col3:
            total_patterns = sum(s.get("patterns_extracted", 0) for s in sessions)
            st.metric("Total Patterns", total_patterns)

        st.markdown("---")

        # Sessions table
        df_data = []
        for s in reversed(sessions):
            df_data.append({
                "Timestamp": s.get("timestamp", "")[:19],
                "Directory": s.get("cwd", "")[-30:],
                "Insights": s.get("insights_captured", 0),
                "Issues": s.get("issues_found", 0),
                "Patterns": s.get("patterns_extracted", 0),
            })

        if df_data:
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)

        # Chart
        st.subheader("Insights Over Time")
        if len(sessions) > 1:
            chart_data = [
                {"date": s.get("timestamp", "")[:10], "insights": s.get("insights_captured", 0)}
                for s in sessions
            ]
            chart_df = pd.DataFrame(chart_data)
            chart_df = chart_df.groupby("date").sum().reset_index()
            st.line_chart(chart_df.set_index("date"))


# === Commands Page ===
elif page == "Commands":
    st.title("Command Usage")

    # Query command tracking database
    if COMMAND_DB.exists():
        df = query_db(COMMAND_DB, """
            SELECT command, project, COUNT(*) as count,
                   MAX(timestamp) as last_used
            FROM command_executions
            GROUP BY command, project
            ORDER BY count DESC
            LIMIT 50
        """)

        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Unique Commands", df["command"].nunique())
            with col2:
                st.metric("Total Executions", df["count"].sum())

            st.markdown("---")
            st.subheader("Command Usage by Project")
            st.dataframe(df, use_container_width=True)

            # Chart
            st.subheader("Top Commands")
            top_commands = df.groupby("command")["count"].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_commands)
        else:
            st.info("No command usage data yet.")
    else:
        st.info("Command tracking database not found.")


# === Outcomes Page ===
elif page == "Outcomes":
    st.title("Recommendation Outcomes")

    outcomes = load_jsonl(OUTCOMES_FILE, limit=200)

    if not outcomes:
        st.info("No outcomes logged yet.")
    else:
        # Outcome stats
        outcome_counts = Counter(o.get("outcome") for o in outcomes)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total", len(outcomes))
        with col2:
            st.metric("✅ Success", outcome_counts.get("success", 0))
        with col3:
            st.metric("🔶 Partial", outcome_counts.get("partial", 0))
        with col4:
            st.metric("❌ Failed", outcome_counts.get("failed", 0))

        # Success rate
        total_definitive = outcome_counts.get("success", 0) + outcome_counts.get("failed", 0)
        if total_definitive > 0:
            success_rate = outcome_counts.get("success", 0) / total_definitive
            st.progress(success_rate, f"Success Rate: {success_rate:.1%}")

        st.markdown("---")

        # Filter by type
        types = list(set(o.get("recommendation_type", "unknown") for o in outcomes))
        selected_type = st.selectbox("Filter by Type", ["All"] + types)

        filtered = outcomes
        if selected_type != "All":
            filtered = [o for o in outcomes if o.get("recommendation_type") == selected_type]

        # Outcomes table
        df_data = []
        for o in reversed(filtered[-50:]):
            df_data.append({
                "Date": o.get("timestamp", "")[:10],
                "Title": o.get("recommendation_title", "")[:50],
                "Type": o.get("recommendation_type", ""),
                "Outcome": o.get("outcome", ""),
                "Confidence": f"{o.get('confidence', 0):.2f}",
            })

        if df_data:
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)

        # Outcomes by type chart
        st.subheader("Outcomes by Type")
        type_outcomes = {}
        for o in outcomes:
            t = o.get("recommendation_type", "unknown")
            if t not in type_outcomes:
                type_outcomes[t] = {"success": 0, "partial": 0, "failed": 0}
            outcome = o.get("outcome", "unknown")
            if outcome in type_outcomes[t]:
                type_outcomes[t][outcome] += 1

        if type_outcomes:
            chart_df = pd.DataFrame(type_outcomes).T
            st.bar_chart(chart_df)
