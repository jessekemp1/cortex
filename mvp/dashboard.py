#!/usr/bin/env python3
"""
Cortex Intelligence Platform - Dashboard

Interactive Streamlit dashboard for:
- Signal exploration
- Contract generation and viewing
- Health monitoring
- Queue visualization
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.signals import SignalDetector, Signal, SignalType
from intelligence.contracts import ContractGenerator
from intelligence.risk import RiskClassifier
from health.monitor import HealthMonitor


# Page config
st.set_page_config(
    page_title="Cortex Intelligence Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components
@st.cache_resource
def get_components():
    """Initialize all components (cached)."""
    return {
        'detector': SignalDetector(),
        'generator': ContractGenerator(),
        'classifier': RiskClassifier(),
        'monitor': HealthMonitor(),
    }

components = get_components()
cache_dir = Path.home() / ".cortex"


def main():
    """Main dashboard entry point."""

    # Sidebar navigation
    st.sidebar.title("🧠 Cortex Intelligence")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigate",
        ["🏥 Health", "🔍 Signals", "📋 Contracts", "📊 Queue"],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Actions")

    if st.sidebar.button("🔄 Scan for Signals", use_container_width=True):
        scan_signals()

    if st.sidebar.button("💾 Refresh Data", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    # Route to page
    if page == "🏥 Health":
        show_health_page()
    elif page == "🔍 Signals":
        show_signals_page()
    elif page == "📋 Contracts":
        show_contracts_page()
    elif page == "📊 Queue":
        show_queue_page()


def show_health_page():
    """Health monitoring page."""
    st.title("🏥 System Health")

    # Get health status
    monitor = components['monitor']
    metrics, alerts = monitor.health_status()

    # Metrics cards
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        queue_status = "🟢" if 3 <= metrics.queue_depth <= 8 else "🟡"
        st.metric(
            "Queue Depth",
            metrics.queue_depth,
            help="Optimal: 3-8 tasks"
        )
        st.caption(f"{queue_status} Optimal: 3-8")

    with col2:
        success_status = "🟢" if metrics.success_rate >= 0.85 else "🔴"
        st.metric(
            "Success Rate",
            f"{metrics.success_rate:.1%}",
            help="Optimal: >85%"
        )
        st.caption(f"{success_status} Optimal: >85%")

    with col3:
        cycle_status = "🟢" if metrics.avg_cycle_time_hours <= 4.0 else "🟡"
        st.metric(
            "Cycle Time",
            f"{metrics.avg_cycle_time_hours:.1f}h",
            help="Optimal: <4h"
        )
        st.caption(f"{cycle_status} Optimal: <4h")

    with col4:
        blocked_status = "🟢" if metrics.blocked_tasks == 0 else "🔴"
        st.metric(
            "Blocked Tasks",
            metrics.blocked_tasks,
            help="Optimal: 0"
        )
        st.caption(f"{blocked_status} Optimal: 0")

    with col5:
        cost_status = "🟢" if metrics.cost_per_day_usd <= 50 else "🟡"
        st.metric(
            "Cost/Day",
            f"${metrics.cost_per_day_usd:.2f}",
            help="Optimal: <$50"
        )
        st.caption(f"{cost_status} Optimal: <$50")

    st.markdown("---")

    # Activity metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Active Executors", metrics.active_executors)

    with col2:
        st.metric("Completed (24h)", metrics.tasks_completed_24h)

    with col3:
        st.metric("Failed (24h)", metrics.tasks_failed_24h)

    st.markdown("---")

    # Alerts
    st.subheader("🚨 Alerts")

    if not alerts:
        st.success("✅ No alerts - system healthy")
    else:
        for alert in alerts:
            if alert.severity == "critical":
                st.error(f"**{alert.message}**\n\n→ {alert.action}")
            elif alert.severity == "warning":
                st.warning(f"**{alert.message}**\n\n→ {alert.action}")
            else:
                st.info(f"**{alert.message}**\n\n→ {alert.action}")

    # Orchestration Intelligence
    st.markdown("---")
    st.subheader("⚙️ Orchestration Intelligence")

    try:
        from orchestration.anomaly_detector import OrchestrationAnomalyManager
        from orchestration.anti_pattern_detector import AntiPatternDetector
        from orchestration.database import OrchestrationDatabase

        db = OrchestrationDatabase()
        anomaly_manager = OrchestrationAnomalyManager(db)
        anti_pattern_detector = AntiPatternDetector(db=None, root_dir=Path.cwd())

        # Detect anomalies
        orchestration_anomalies = anomaly_manager.detect_all(context={
            "active_projects": 26,  # TODO: Get from actual state
            "total_projects": 30,
            "goals_in_progress": 0,
            "goals_pending": 9
        })

        # Detect anti-patterns
        anti_patterns = anti_pattern_detector.detect_all()

        # Combine and display
        all_issues = []

        for anomaly in orchestration_anomalies:
            if anomaly.severity.value.lower() in ["critical", "warning"]:
                all_issues.append({
                    "severity": anomaly.severity.value.lower(),
                    "title": anomaly.title,
                    "action": anomaly.remediation
                })

        for pattern in anti_patterns:
            if pattern.severity.value.lower() in ["critical", "high"]:
                all_issues.append({
                    "severity": pattern.severity.value.lower(),
                    "title": f"{pattern.pattern_type.value}: {pattern.validated_item}",
                    "action": pattern.suggested_action
                })

        if not all_issues:
            st.success("✅ No orchestration issues detected")
        else:
            for issue in all_issues:
                if issue["severity"] in ["critical", "high"]:
                    st.error(f"**{issue['title']}**\n\n→ {issue['action']}")
                elif issue["severity"] == "warning":
                    st.warning(f"**{issue['title']}**\n\n→ {issue['action']}")
                else:
                    st.info(f"**{issue['title']}**\n\n→ {issue['action']}")

    except Exception as e:
        st.warning(f"Orchestration intelligence unavailable: {e}")

    # Health history (if available)
    st.markdown("---")
    st.subheader("📈 Health History (24h)")

    history = monitor.get_history(hours=24)
    if history:
        # Simple line chart of success rate over time
        timestamps = [h['timestamp'] for h in reversed(history)]
        success_rates = [h['metrics']['success_rate'] for h in reversed(history)]

        import pandas as pd
        df = pd.DataFrame({
            'Time': timestamps,
            'Success Rate': success_rates
        })

        st.line_chart(df.set_index('Time'))
    else:
        st.info("No historical data available yet")


def show_signals_page():
    """Signal exploration page."""
    st.title("🔍 Signal Detection")

    # Load latest signals
    summary_file = cache_dir / "latest_scan.json"

    if not summary_file.exists():
        st.warning("No signals found. Click 'Scan for Signals' in the sidebar.")
        return

    data = json.loads(summary_file.read_text())
    signals_data = data.get("signals", [])

    if not signals_data:
        st.info("No signals detected in last scan.")
        return

    # Summary stats
    st.markdown(f"**Last Scan**: {data.get('scanned_at', 'Unknown')}")
    st.markdown(f"**Total Signals**: {data.get('count', 0)}")

    col1, col2, col3, col4 = st.columns(4)
    by_severity = data.get('by_severity', {})

    with col1:
        st.metric("🚨 Critical", by_severity.get('critical', 0))
    with col2:
        st.metric("⚠️ High", by_severity.get('high', 0))
    with col3:
        st.metric("💡 Medium", by_severity.get('medium', 0))
    with col4:
        st.metric("ℹ️ Low", by_severity.get('low', 0))

    st.markdown("---")

    # Filter controls
    col1, col2 = st.columns(2)

    with col1:
        severity_filter = st.multiselect(
            "Filter by Severity",
            ["critical", "high", "medium", "low"],
            default=["critical", "high", "medium", "low"]
        )

    with col2:
        type_filter = st.multiselect(
            "Filter by Type",
            ["validation_gap", "test_failure", "strategic_gap", "tech_debt", "security", "performance", "documentation"],
            default=["validation_gap", "test_failure", "strategic_gap", "tech_debt", "security", "performance", "documentation"]
        )

    # Filter signals
    filtered_signals = [
        s for s in signals_data
        if s['severity'] in severity_filter and s['type'] in type_filter
    ]

    st.markdown(f"**Showing {len(filtered_signals)} of {len(signals_data)} signals**")

    # Display signals
    for signal in filtered_signals:
        severity_icon = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "💡",
            "low": "ℹ️"
        }[signal['severity']]

        with st.expander(f"{severity_icon} [{signal['type']}] {signal['title']}"):
            st.markdown(f"**Description**: {signal['description']}")
            st.markdown(f"**Impact**: {signal['estimated_impact']}")

            st.markdown("**Evidence**:")
            for evidence in signal['evidence']:
                st.markdown(f"- {evidence}")

            st.markdown("**Context**:")
            st.json(signal['context'])

            # Generate contract button
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("Generate Contract", key=f"gen_{signal['id']}"):
                    st.session_state['generate_contract_for'] = signal['id']
                    st.rerun()

            with col2:
                st.caption(f"Signal ID: `{signal['id']}`")

    # Handle contract generation
    if 'generate_contract_for' in st.session_state:
        signal_id = st.session_state['generate_contract_for']
        generate_contract_for_signal(signal_id, signals_data)
        del st.session_state['generate_contract_for']


def show_contracts_page():
    """Contract viewing page."""
    st.title("📋 Contracts")

    contracts_dir = cache_dir / "contracts"

    if not contracts_dir.exists():
        st.info("No contracts generated yet.")
        return

    contract_files = sorted(contracts_dir.glob("*.json"), reverse=True)

    if not contract_files:
        st.info("No contracts found.")
        return

    st.markdown(f"**Total Contracts**: {len(contract_files)}")

    # Display contracts
    for contract_file in contract_files:
        try:
            contract_data = json.loads(contract_file.read_text())

            risk_color = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴"
            }[contract_data['risk_level']]

            auto_exec_badge = "✅ Auto-executable" if contract_data['auto_executable'] else "⚠️ Requires approval"

            with st.expander(f"{risk_color} {contract_data['title']} ({auto_exec_badge})"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Risk Level", contract_data['risk_level'].upper())

                with col2:
                    st.metric("Max Cost", f"${contract_data['max_cost_usd']:.2f}")

                with col3:
                    st.metric("Max Attempts", contract_data['max_attempts'])

                st.markdown("---")

                # Requirements
                st.markdown("**Requirements**:")
                for i, req in enumerate(contract_data['requirements'], 1):
                    st.markdown(f"{i}. {req}")

                # Constraints
                if contract_data['constraints']:
                    st.markdown("**Constraints**:")
                    for constraint in contract_data['constraints']:
                        st.markdown(f"- {constraint}")

                # Success criteria
                st.markdown("**Success Criteria**:")

                success = contract_data['success_criteria']

                if success.get('tests'):
                    st.markdown("*Tests:*")
                    for test in success['tests']:
                        st.markdown(f"- {test}")

                if success.get('metrics'):
                    st.markdown("*Metrics:*")
                    for metric, threshold in success['metrics'].items():
                        st.markdown(f"- {metric}: {threshold}")

                # Human gates
                if contract_data['human_gates']:
                    st.markdown("**Human Gates**:")
                    st.markdown(", ".join(contract_data['human_gates']))

                # Metadata
                st.caption(f"Contract ID: `{contract_data['contract_id']}`")
                st.caption(f"Created: {contract_data['created_at']}")

        except (json.JSONDecodeError, KeyError):
            st.error(f"Error loading contract: {contract_file.name}")


def show_queue_page():
    """Queue visualization page."""
    st.title("📊 Task Queue")

    # This is a placeholder - in full implementation, would show:
    # - Pending tasks
    # - Executing tasks
    # - Completed tasks
    # in a Kanban-style layout

    st.info("Queue visualization coming soon. Use CLI: `python cortex/batch/orchestrator.py list`")

    # Show recent batch jobs
    try:
        from batch.orchestrator import BatchOrchestrator

        orchestrator = BatchOrchestrator()
        jobs = orchestrator.list_jobs(backend="both", limit=20)

        if jobs:
            # Group by status
            pending = [j for j in jobs if j.state.value in ["pending", "queued"]]
            executing = [j for j in jobs if j.state.value in ["running", "scheduled"]]
            completed = [j for j in jobs if j.state.value == "completed"]
            failed = [j for j in jobs if j.state.value == "failed"]

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("⏸️ Pending", len(pending))
            with col2:
                st.metric("⚙️ Executing", len(executing))
            with col3:
                st.metric("✅ Completed", len(completed))
            with col4:
                st.metric("❌ Failed", len(failed))

            st.markdown("---")

            # Show jobs by category
            tab1, tab2, tab3, tab4 = st.tabs(["Pending", "Executing", "Completed", "Failed"])

            with tab1:
                show_jobs(pending)

            with tab2:
                show_jobs(executing)

            with tab3:
                show_jobs(completed)

            with tab4:
                show_jobs(failed)
        else:
            st.info("No jobs in queue")

    except Exception as e:
        st.error(f"Error loading queue: {e}")


def show_jobs(jobs):
    """Display list of jobs."""
    if not jobs:
        st.info("No jobs in this category")
        return

    for job in jobs:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{job.description}**")

            with col2:
                st.caption(f"Priority: {job.priority.upper()}")

            with col3:
                st.caption(f"Backend: {job.backend.value}")

            st.caption(f"Job ID: `{job.id}`")

            if job.error_message:
                st.error(f"Error: {job.error_message}")

            st.markdown("---")


def scan_signals():
    """Run signal detection and show results."""
    with st.spinner("Scanning for signals..."):
        detector = components['detector']
        signals = detector.detect_all()

        if signals:
            st.success(f"✅ Found {len(signals)} signals!")
            st.rerun()
        else:
            st.info("No signals detected")


def generate_contract_for_signal(signal_id, signals_data):
    """Generate contract for a signal."""
    # Find signal
    signal_dict = None
    for s in signals_data:
        if s['id'] == signal_id:
            signal_dict = s
            break

    if not signal_dict:
        st.error(f"Signal not found: {signal_id}")
        return

    # Show progress
    with st.spinner("Generating contract with Opus 4.5... (30-60 seconds)"):
        try:
            # Reconstruct Signal object
            signal = Signal(
                id=signal_dict["id"],
                type=SignalType(signal_dict["type"]),
                severity=signal_dict["severity"],
                title=signal_dict["title"],
                description=signal_dict["description"],
                context=signal_dict["context"],
                evidence=signal_dict["evidence"],
                estimated_impact=signal_dict["estimated_impact"],
                detected_at=datetime.fromisoformat(signal_dict["detected_at"]),
            )

            # Generate contract (async)
            import asyncio
            generator = components['generator']
            contract = asyncio.run(generator.generate_contract(signal))

            st.success("✅ Contract generated!")
            st.balloons()

            # Show contract details
            st.markdown(f"### Contract: {contract.title}")
            st.markdown(f"**Risk**: {contract.risk_level} | **Auto-executable**: {contract.auto_executable}")

            # Switch to contracts page
            st.info("Contract saved! Switch to 'Contracts' page to view details.")

        except Exception as e:
            st.error(f"Error generating contract: {e}")


if __name__ == "__main__":
    main()
