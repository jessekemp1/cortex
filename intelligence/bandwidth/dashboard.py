"""
Bandwidth Dashboard - CLI visualization of human-AI bandwidth metrics.

Provides:
- Session statistics summary
- Trust calibration by domain
- Context efficiency metrics
- Trend comparison to baseline
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from intelligence.bandwidth.handoff_capture import HandoffStorage
from intelligence.bandwidth.meter import BandwidthMeter
from intelligence.bandwidth.predictions import PredictionTracker


def render_dashboard(
    project: Optional[str] = None,
    days: int = 7,
    show_calibration: bool = True,
    show_handoffs: bool = True,
) -> str:
    """
    Render the bandwidth dashboard as a formatted string.

    Args:
        project: Filter by project (None = all)
        days: Number of days to show stats for
        show_calibration: Include trust calibration section
        show_handoffs: Include recent handoffs section

    Returns:
        Formatted dashboard string
    """
    lines = []

    # Header
    lines.append("╔════════════════════════════════════════════════════════╗")
    lines.append("║            HUMAN-AI BANDWIDTH METRICS                  ║")
    lines.append("╠════════════════════════════════════════════════════════╣")
    lines.append("")

    # Session Stats Section
    lines.extend(_render_session_stats(project, days))

    # Trust Calibration Section
    if show_calibration:
        lines.append("")
        lines.extend(_render_calibration())

    # Context Efficiency Section
    lines.append("")
    lines.extend(_render_context_efficiency(project, days))

    # Recent Handoffs Section
    if show_handoffs:
        lines.append("")
        lines.extend(_render_recent_handoffs(project))

    # Trend Comparison Section
    lines.append("")
    lines.extend(_render_trends(project, days))

    lines.append("")
    lines.append("╚════════════════════════════════════════════════════════╝")

    return "\n".join(lines)


def _render_session_stats(project: Optional[str], days: int) -> list:
    """Render session statistics section."""
    lines = []
    meter = BandwidthMeter()

    stats = meter.get_aggregate_stats(days=days, project=project)

    lines.append("│  📊 SESSION STATS (Last {} days)                        │".format(days))
    lines.append("│  ────────────────────────────────────────              │")

    if stats["sessions"] == 0:
        lines.append("│  No session data yet. Start capturing!                │")
        lines.append("│                                                        │")
        lines.append("│  Usage: from cortex.intelligence.bandwidth import \\   │")
        lines.append("│         get_session_metrics                            │")
    else:
        lines.append(f"│  Sessions: {stats['sessions']:<45}│")
        lines.append(
            f"│  Avg Signal Ratio: {stats['avg_signal_ratio']:.2f}                               │"
        )
        lines.append(
            f"│  Corrections/Session: {stats['avg_correction_rate']:.1f}                           │"
        )
        lines.append(f"│  Files Modified: {stats['total_files_modified']:<39}│")

    return lines


def _render_calibration() -> list:
    """Render trust calibration section."""
    lines = []
    tracker = PredictionTracker()

    lines.append("│  🎯 TRUST CALIBRATION                                  │")
    lines.append("│  ────────────────────────────────────────              │")

    calibrations = tracker.get_calibration()

    has_data = any(cal.total > 0 for cal in calibrations.values())

    if not has_data:
        lines.append("│  No calibration data yet. Record predictions!         │")
        lines.append("│                                                        │")
        lines.append("│  Usage: cortex bandwidth record-prediction \\          │")
        lines.append("│         --domain code --confidence 0.8                 │")
    else:
        # Sort by confidence (highest first)
        sorted_cals = sorted(
            calibrations.items(),
            key=lambda x: x[1].calibrated_confidence,
            reverse=True,
        )

        for domain, cal in sorted_cals:
            if cal.total == 0:
                bar = "░" * 10
                pct = "N/A"
            else:
                filled = int(cal.calibrated_confidence * 10)
                bar = "█" * filled + "░" * (10 - filled)
                pct = f"{cal.calibrated_confidence * 100:.0f}%"

            lines.append(f"│  {domain.capitalize():14s} {bar} {pct:>5s}               │")

    return lines


def _render_context_efficiency(project: Optional[str], days: int) -> list:
    """Render context efficiency section."""
    lines = []
    meter = BandwidthMeter()

    comparison = meter.compare_to_baseline(baseline_days=30, recent_days=days, project=project)

    lines.append("│  📈 CONTEXT EFFICIENCY                                 │")
    lines.append("│  ────────────────────────────────────────              │")

    if not comparison.get("has_baseline") and not comparison.get("has_recent"):
        lines.append("│  Insufficient data for efficiency metrics             │")
    else:
        signal_delta = comparison.get("signal_ratio_delta", 0)
        correction_delta = comparison.get("correction_rate_delta", 0)
        time_delta = comparison.get("time_to_productive_delta", 0)

        signal_indicator = "▲" if signal_delta > 0 else "▼" if signal_delta < 0 else "─"
        correction_indicator = "▲" if correction_delta > 0 else "▼" if correction_delta < 0 else "─"
        time_indicator = "▲" if time_delta > 0 else "▼" if time_delta < 0 else "─"

        lines.append(
            f"│  Signal Ratio: {signal_indicator} {abs(signal_delta)*100:+.0f}% vs baseline               │"
        )
        lines.append(
            f"│  Corrections:  {correction_indicator} {abs(correction_delta)*100:+.0f}% vs baseline               │"
        )
        lines.append(
            f"│  Time to Prod: {time_indicator} {abs(time_delta):+.0f}s vs baseline                │"
        )

    return lines


def _render_recent_handoffs(project: Optional[str], limit: int = 3) -> list:
    """Render recent session handoffs section."""
    lines = []
    storage = HandoffStorage()

    handoffs = storage.load_recent(limit=limit, project=project)

    lines.append("│  🔄 RECENT HANDOFFS                                    │")
    lines.append("│  ────────────────────────────────────────              │")

    if not handoffs:
        lines.append("│  No handoffs captured yet.                            │")
        lines.append("│                                                        │")
        lines.append("│  Usage: from cortex.intelligence.bandwidth import \\   │")
        lines.append("│         capture_handoff                                │")
    else:
        for handoff in handoffs[:limit]:
            time_str = handoff.timestamp.strftime("%m/%d %H:%M")
            task_short = (
                handoff.active_task[:30] + "..."
                if len(handoff.active_task) > 30
                else handoff.active_task
            )
            lines.append(f"│  [{time_str}] {task_short:<34}│")

    return lines


def _render_trends(project: Optional[str], days: int) -> list:
    """Render trend comparison section."""
    lines = []

    lines.append("│  📉 TRENDS                                             │")
    lines.append("│  ────────────────────────────────────────              │")

    # Check for experiment results
    experiments_dir = Path.home() / ".cortex" / "research" / "bandwidth" / "experiments"
    synthesis_report = experiments_dir / "synthesis_report.json"

    if synthesis_report.exists():
        import json

        with open(synthesis_report) as f:
            report = json.load(f)

        findings = report.get("key_findings", [])[:2]
        for finding in findings:
            finding_short = finding[:50] + "..." if len(finding) > 50 else finding
            lines.append(f"│  • {finding_short:<51}│")
    else:
        lines.append("│  Run bandwidth experiments for trend analysis         │")
        lines.append("│                                                        │")
        lines.append("│  Usage: cortex bandwidth experiment --all              │")

    return lines


def get_dashboard_data(
    project: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Get dashboard data as a dictionary (for JSON output).

    Args:
        project: Filter by project
        days: Number of days

    Returns:
        Dict with all dashboard data
    """
    meter = BandwidthMeter()
    tracker = PredictionTracker()
    storage = HandoffStorage()

    return {
        "generated_at": datetime.now().isoformat(),
        "period_days": days,
        "project_filter": project,
        "session_stats": meter.get_aggregate_stats(days=days, project=project),
        "calibration": {domain: cal.to_dict() for domain, cal in tracker.get_calibration().items()},
        "trends": meter.compare_to_baseline(baseline_days=30, recent_days=days, project=project),
        "recent_handoffs": [h.to_dict() for h in storage.load_recent(limit=5, project=project)],
    }
