#!/usr/bin/env python3
"""
Cortex Orchestration Dashboard

Real-time view of batch task execution and orchestration.
Shows:
- Queue health metrics
- Active task execution
- Worker pool status
- Task dependencies and flow
- Needs attention alerts
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# === Configuration ===
CORTEX_DATA = Path.home() / ".cortex"

# Database paths
BATCH_QUEUE_DB = CORTEX_DATA / "batch_queue.db"
ORCHESTRATION_DB = CORTEX_DATA / "orchestration.db"  # Future: Worker 1's database

# Batch API tracking
BATCHES_DIR = CORTEX_DATA / "batches"

# Cost tracking (approximation for now)
INTERACTION_QUEUE = CORTEX_DATA / "interaction_queue.jsonl"


# === Data Loading Helpers ===
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


def load_batch_queue_tasks() -> List[Dict[str, Any]]:
    """Load tasks from batch_queue.db."""
    if not BATCH_QUEUE_DB.exists():
        return []

    try:
        conn = sqlite3.connect(BATCH_QUEUE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM batch_tasks ORDER BY created_at DESC LIMIT 500")
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks
    except Exception:
        return []


def load_batch_api_jobs() -> List[Dict[str, Any]]:
    """Load batch API jobs from batches/*.json files."""
    if not BATCHES_DIR.exists():
        return []

    jobs = []
    for metadata_file in BATCHES_DIR.glob("msgbatch_*_metadata.json"):
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
                metadata["batch_id"] = metadata_file.stem.replace("_metadata", "")
                jobs.append(metadata)
        except Exception:
            continue

    # Sort by created_at if available
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jobs[:100]


def estimate_daily_cost(tasks: List[Dict]) -> Dict[str, float]:
    """Estimate cost metrics from task data."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    today_tasks = []
    for task in tasks:
        created_at = task.get("created_at", "")
        try:
            task_date = datetime.fromisoformat(created_at)
            if task_date >= today:
                today_tasks.append(task)
        except (ValueError, TypeError):
            pass

    # Rough estimates: $3 per 1M input tokens, $15 per 1M output tokens
    total_input_tokens = sum(t.get("estimated_input_tokens", 0) for t in today_tasks)
    total_output_tokens = sum(t.get("estimated_output_tokens", 0) for t in today_tasks)

    input_cost = (total_input_tokens / 1_000_000) * 3.0
    output_cost = (total_output_tokens / 1_000_000) * 15.0
    total_cost = input_cost + output_cost

    # Estimated savings: Compare to interactive usage at $15/hour
    estimated_hours_saved = len(today_tasks) * 0.5  # Assume 30min per task
    interactive_cost = estimated_hours_saved * 15.0
    savings = max(0, interactive_cost - total_cost)

    # Daily budget (rough estimate: $50/day for batch work)
    daily_budget = 50.0
    budget_pct = (total_cost / daily_budget * 100) if daily_budget > 0 else 0

    return {
        "spend": total_cost,
        "savings": savings,
        "budget_pct": budget_pct,
        "daily_budget": daily_budget,
    }


def analyze_task_states(tasks: List[Dict]) -> Dict[str, Any]:
    """Analyze task states for metrics."""
    states = defaultdict(int)
    for task in tasks:
        state = task.get("state", "unknown")
        states[state] += 1

    # Get today's completed tasks
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = 0
    for task in tasks:
        if task.get("state") == "completed":
            completed_at = task.get("completed_at", "")
            try:
                task_date = datetime.fromisoformat(completed_at)
                if task_date >= today:
                    completed_today += 1
            except (ValueError, TypeError):
                pass

    return {
        "queued": states.get("pending", 0) + states.get("scheduled", 0),
        "active": states.get("running", 0),
        "completed_today": completed_today,
        "failed": states.get("failed", 0),
        "cancelled": states.get("cancelled", 0),
        "total": len(tasks),
    }


def detect_needs_attention(tasks: List[Dict]) -> List[Dict[str, Any]]:
    """Detect tasks that need attention."""
    alerts = []

    # Parse dependencies
    for task in tasks:
        task_id = task.get("task_id", "")
        state = task.get("state", "")

        # Blocked tasks (pending with unmet dependencies)
        if state in ["pending", "scheduled"]:
            deps_json = task.get("dependencies", "[]")
            try:
                dependencies = json.loads(deps_json) if isinstance(deps_json, str) else deps_json
                if dependencies:
                    # Check if dependencies are completed
                    dep_states = []
                    for dep_id in dependencies:
                        dep_task = next((t for t in tasks if t.get("task_id") == dep_id), None)
                        if dep_task:
                            dep_states.append(dep_task.get("state"))

                    if dep_states and not all(s == "completed" for s in dep_states):
                        alerts.append(
                            {
                                "type": "blocked",
                                "severity": "warning",
                                "task_id": task_id,
                                "description": task.get("description", "Unknown task"),
                                "reason": f"Waiting on {len(dependencies)} dependencies",
                            }
                        )
            except (json.JSONDecodeError, TypeError):
                pass

        # Slow tasks (running > 2x estimated duration)
        if state == "running":
            started_at = task.get("started_at", "")
            estimated_duration_min = task.get("estimated_duration_minutes", 10.0)
            try:
                start_time = datetime.fromisoformat(started_at)
                elapsed_min = (datetime.now() - start_time).total_seconds() / 60
                if elapsed_min > estimated_duration_min * 2:
                    alerts.append(
                        {
                            "type": "slow",
                            "severity": "warning",
                            "task_id": task_id,
                            "description": task.get("description", "Unknown task"),
                            "reason": f"Running {elapsed_min:.0f}m (expected {estimated_duration_min:.0f}m)",
                        }
                    )
            except (ValueError, TypeError):
                pass

        # Failed tasks
        if state == "failed":
            error_msg = task.get("error_message", "Unknown error")
            alerts.append(
                {
                    "type": "failed",
                    "severity": "error",
                    "task_id": task_id,
                    "description": task.get("description", "Unknown task"),
                    "reason": error_msg[:100],
                }
            )

    # Sort by severity
    severity_order = {"error": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda x: (severity_order.get(x["severity"], 9), x["type"]))

    return alerts


def get_running_tasks_with_progress(tasks: List[Dict]) -> List[Dict[str, Any]]:
    """Get running tasks with progress calculation."""
    running = []

    for task in tasks:
        if task.get("state") != "running":
            continue

        started_at = task.get("started_at", "")
        estimated_duration_min = task.get("estimated_duration_minutes", 10.0)

        try:
            start_time = datetime.fromisoformat(started_at)
            elapsed_min = (datetime.now() - start_time).total_seconds() / 60
            progress_pct = min(95, int((elapsed_min / estimated_duration_min) * 100))

            # Determine phase based on progress
            if progress_pct < 20:
                phase = "Initializing"
            elif progress_pct < 50:
                phase = "Processing"
            elif progress_pct < 80:
                phase = "Finalizing"
            else:
                phase = "Completing"

            running.append(
                {
                    "task_id": task.get("task_id", "")[:8],
                    "description": task.get("description", "Unknown task"),
                    "task_type": task.get("task_type", "general"),
                    "progress_pct": progress_pct,
                    "phase": phase,
                    "elapsed_min": int(elapsed_min),
                    "estimated_min": int(estimated_duration_min),
                }
            )
        except (ValueError, TypeError):
            pass

    return running


def build_dependency_tree(tasks: List[Dict]) -> Dict[str, List[str]]:
    """Build dependency tree for visualization."""
    tree = defaultdict(list)

    for task in tasks:
        task_id = task.get("task_id", "")[:8]
        deps_json = task.get("dependencies", "[]")
        try:
            dependencies = json.loads(deps_json) if isinstance(deps_json, str) else deps_json
            for dep_id in dependencies:
                dep_short = dep_id[:8] if dep_id else ""
                tree[dep_short].append(task_id)
        except (json.JSONDecodeError, TypeError):
            pass

    return dict(tree)


# === Streamlit App ===
st.set_page_config(
    page_title="Cortex Orchestration",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS
st.markdown(
    """
<style>
    .stMetric { background: #1a1a2e; padding: 15px; border-radius: 10px; }
    .alert-error { border-left: 4px solid #ff4444; padding: 10px; background: #2a1a1a; margin: 5px 0; }
    .alert-warning { border-left: 4px solid #ffaa00; padding: 10px; background: #2a2a1a; margin: 5px 0; }
    .alert-info { border-left: 4px solid #4444ff; padding: 10px; background: #1a1a2a; margin: 5px 0; }
    .task-running { background: #1a2a1a; padding: 10px; margin: 5px 0; border-radius: 5px; }
</style>
""",
    unsafe_allow_html=True,
)

# === Load Data ===
tasks = load_batch_queue_tasks()
batch_jobs = load_batch_api_jobs()
task_states = analyze_task_states(tasks)
cost_metrics = estimate_daily_cost(tasks)
alerts = detect_needs_attention(tasks)
running_tasks = get_running_tasks_with_progress(tasks)

# === Header ===
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🎯 Cortex Orchestration Dashboard")
with col2:
    if st.button("🔄 Refresh"):
        st.rerun()

st.markdown("---")

# === Header Row: Metrics ===
metric_col1, metric_col2, metric_col3 = st.columns(3)

with metric_col1:
    st.markdown("### 📊 Queue Health")
    sub1, sub2, sub3 = st.columns(3)
    with sub1:
        st.metric("Queued", task_states["queued"])
    with sub2:
        st.metric("Active", task_states["active"])
    with sub3:
        st.metric("Done Today", task_states["completed_today"])

with metric_col2:
    st.markdown("### ⚡ Active Now")
    if running_tasks:
        task = running_tasks[0]
        st.metric("Running", task_states["active"])
        st.caption(f"Current: {task['phase']} ({task['task_type']})")
    else:
        st.metric("Running", 0)
        st.caption("No active tasks")

with metric_col3:
    st.markdown("### 💰 Cost Today")
    st.metric(
        "Spend",
        f"${cost_metrics['spend']:.2f}",
        f"{cost_metrics['budget_pct']:.0f}% of ${cost_metrics['daily_budget']:.0f}",
    )
    st.caption(f"Saved: ${cost_metrics['savings']:.2f} vs interactive")

st.markdown("---")

# === Needs Attention Panel ===
if alerts:
    st.markdown("### 🚨 Needs Attention")

    with st.expander(f"⚠️ {len(alerts)} items need attention", expanded=True):
        for alert in alerts[:10]:
            severity_class = f"alert-{alert['severity']}"
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(alert["severity"], "•")

            st.markdown(
                f"""
<div class="{severity_class}">
    {icon} <strong>{alert['description'][:50]}</strong><br>
    <small>{alert['reason']}</small><br>
    <small style='color: gray;'>Task: {alert['task_id'][:8]}</small>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("---")

# === Three Column Layout ===
col_left, col_middle, col_right = st.columns([1, 1, 1])

# === LEFT: Active Execution ===
with col_left:
    st.markdown("### 🔄 Active Execution")

    if running_tasks:
        for task in running_tasks[:10]:
            st.markdown(
                f"""
<div class="task-running">
    <strong>{task['description'][:40]}</strong><br>
    <small>{task['phase']} • {task['elapsed_min']}/{task['estimated_min']}m</small>
</div>
""",
                unsafe_allow_html=True,
            )
            st.progress(task["progress_pct"] / 100)
            st.markdown("")
    else:
        st.info("No tasks currently running")

    # Recent completions
    st.markdown("**Recent Completions**")
    completed = [t for t in tasks if t.get("state") == "completed"][:5]
    if completed:
        for task in completed:
            desc = task.get("description", "Unknown")[:35]
            completed_at = task.get("completed_at", "")
            try:
                dt = datetime.fromisoformat(completed_at)
                time_str = dt.strftime("%H:%M")
                st.markdown(f"✅ {desc} ({time_str})")
            except (ValueError, TypeError):
                st.markdown(f"✅ {desc}")
    else:
        st.caption("No recent completions")

# === MIDDLE: Agent Pool Status ===
with col_middle:
    st.markdown("### 🤖 Agent Pool Status")

    # For now, show capacity visualization based on running vs queued
    total_capacity = 5  # Assume 5 worker capacity
    used_capacity = min(task_states["active"], total_capacity)

    st.markdown(f"**Capacity: {used_capacity}/{total_capacity} workers**")
    st.progress(used_capacity / total_capacity if total_capacity > 0 else 0)

    st.markdown("")
    st.markdown("**Worker Status**")

    # Show workers
    for i in range(total_capacity):
        if i < used_capacity:
            st.markdown(f"🟢 Worker {i+1}: ACTIVE")
        else:
            st.markdown(f"⚪ Worker {i+1}: IDLE")

    st.markdown("---")

    # Queue depth
    st.markdown("**Queue Depth**")
    st.metric("Pending Tasks", task_states["queued"])

    if task_states["queued"] > 0:
        # Show queue by priority
        priority_counts = defaultdict(int)
        for task in tasks:
            if task.get("state") in ["pending", "scheduled"]:
                priority = task.get("priority", "normal")
                priority_counts[priority] += 1

        if priority_counts:
            st.markdown("**By Priority:**")
            for priority in ["immediate", "high", "normal", "low"]:
                count = priority_counts.get(priority, 0)
                if count > 0:
                    st.markdown(f"- {priority.title()}: {count}")

# === RIGHT: Task Flow ===
with col_right:
    st.markdown("### 🔀 Task Flow")

    # Show sprints/waves if available
    sprints = set()
    waves = set()
    for task in tasks:
        sprint_id = task.get("sprint_id", "")
        wave_id = task.get("wave_id", "")
        if sprint_id:
            sprints.add(sprint_id)
        if wave_id:
            waves.add(wave_id)

    if sprints:
        st.markdown("**Sprints**")
        for sprint_id in sorted(sprints):
            sprint_tasks = [t for t in tasks if t.get("sprint_id") == sprint_id]
            completed = sum(1 for t in sprint_tasks if t.get("state") == "completed")
            total = len(sprint_tasks)
            pct = (completed / total * 100) if total > 0 else 0

            st.markdown(f"**{sprint_id}**: {completed}/{total} ({pct:.0f}%)")
            st.progress(pct / 100)

    if waves:
        st.markdown("**Waves**")
        for wave_id in sorted(waves):
            wave_tasks = [t for t in tasks if t.get("wave_id") == wave_id]
            completed = sum(1 for t in wave_tasks if t.get("state") == "completed")
            total = len(wave_tasks)
            pct = (completed / total * 100) if total > 0 else 0

            st.markdown(f"**{wave_id}**: {completed}/{total} ({pct:.0f}%)")
            st.progress(pct / 100)

    if not sprints and not waves:
        st.info("No sprint/wave organization detected")

    st.markdown("---")

    # Dependency visualization (simple text version)
    st.markdown("**Dependencies**")

    blocked_count = sum(1 for a in alerts if a["type"] == "blocked")
    if blocked_count > 0:
        st.warning(f"{blocked_count} tasks blocked")
    else:
        st.success("No blocked tasks")

    # Show dependency tree sample
    dep_tree = build_dependency_tree(tasks)
    if dep_tree:
        st.caption("Dependency chains detected:")
        shown = 0
        for parent, children in list(dep_tree.items())[:3]:
            st.markdown(f"- `{parent}` → {len(children)} tasks")
            shown += 1

st.markdown("---")

# === Bottom Section: Detailed Views ===
tab1, tab2, tab3 = st.tabs(["📋 All Tasks", "🔄 Batch API Jobs", "📊 Statistics"])

with tab1:
    st.markdown("### All Tasks")

    if tasks:
        # Convert to DataFrame for easy filtering
        df_tasks = pd.DataFrame(tasks)

        # Add filters
        col1, col2, col3 = st.columns(3)
        with col1:
            state_filter = st.selectbox(
                "Filter by State",
                ["all"] + list(df_tasks["state"].unique()),
                index=0,
            )
        with col2:
            task_type_filter = st.selectbox(
                "Filter by Type",
                ["all"] + list(df_tasks["task_type"].unique()),
                index=0,
            )
        with col3:
            limit = st.number_input("Limit", min_value=10, max_value=500, value=50)

        # Apply filters
        filtered_df = df_tasks
        if state_filter != "all":
            filtered_df = filtered_df[filtered_df["state"] == state_filter]
        if task_type_filter != "all":
            filtered_df = filtered_df[filtered_df["task_type"] == task_type_filter]

        # Display table
        display_cols = ["task_id", "description", "state", "task_type", "priority", "created_at"]
        display_cols = [c for c in display_cols if c in filtered_df.columns]

        st.dataframe(
            filtered_df[display_cols].head(limit),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tasks found in batch_queue.db")

with tab2:
    st.markdown("### Batch API Jobs")

    if batch_jobs:
        for job in batch_jobs[:20]:
            batch_id = job.get("batch_id", "unknown")
            status = job.get("processing_status", "unknown")
            created_at = job.get("created_at", "")

            status_icon = {
                "in_progress": "🔄",
                "ended": "✅",
                "validating": "⏳",
                "failed": "❌",
            }.get(status, "❓")

            with st.expander(f"{status_icon} {batch_id} - {status}"):
                st.json(job)
    else:
        st.info("No batch API jobs found in ~/.cortex/batches/")

with tab3:
    st.markdown("### Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Task States**")
        state_counts = defaultdict(int)
        for task in tasks:
            state = task.get("state", "unknown")
            state_counts[state] += 1

        for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
            pct = (count / len(tasks) * 100) if tasks else 0
            st.markdown(f"- **{state}**: {count} ({pct:.1f}%)")

    with col2:
        st.markdown("**Task Types**")
        type_counts = defaultdict(int)
        for task in tasks:
            task_type = task.get("task_type", "unknown")
            type_counts[task_type] += 1

        for task_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
            pct = (count / len(tasks) * 100) if tasks else 0
            st.markdown(f"- **{task_type}**: {count} ({pct:.1f}%)")

    st.markdown("---")

    st.markdown("**Performance**")

    # Calculate average duration by task type
    durations = defaultdict(list)
    for task in tasks:
        if task.get("actual_duration_seconds"):
            task_type = task.get("task_type", "unknown")
            durations[task_type].append(task["actual_duration_seconds"] / 60)

    if durations:
        st.markdown("Average duration by type:")
        for task_type, times in sorted(durations.items(), key=lambda x: -sum(x[1]) / len(x[1]))[:5]:
            avg_min = sum(times) / len(times)
            st.markdown(f"- **{task_type}**: {avg_min:.1f}m (n={len(times)})")

    # Success rate
    completed = sum(1 for t in tasks if t.get("state") == "completed")
    failed = sum(1 for t in tasks if t.get("state") == "failed")
    if completed + failed > 0:
        success_rate = completed / (completed + failed) * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")

st.markdown("---")
st.caption(
    f"Data sources: {BATCH_QUEUE_DB} ({len(tasks)} tasks), {BATCHES_DIR} ({len(batch_jobs)} API jobs)"
)
