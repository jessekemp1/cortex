#!/usr/bin/env python3
"""
Briefing Generator - Daily briefing system for cross-project status

Synthesizes:
- Portfolio pulse (active projects, commits, blockers)
- Priority actions (top recommendations)
- Patterns noticed (activity trends)
- Waiting on (decisions needed)
"""

import inspect
import json
import os
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

try:
    from learning import LearningSystem
except ImportError:
    LearningSystem = None

try:
    from portfolio_memory import PortfolioMemory
except ImportError:
    PortfolioMemory = None

try:
    from intelligence.session_manager import SessionManager
except ImportError:
    SessionManager = None

try:
    from batch.usage_optimizer import UsageOptimizer
except ImportError:
    UsageOptimizer = None

try:
    from metrics_tracker import MetricsTracker
except ImportError:
    MetricsTracker = None

try:
    from intelligence.bandwidth.contracts import ContractMetricsStore
except ImportError:
    ContractMetricsStore = None

try:
    from intelligence.bandwidth.queue_slo import check_queue_slo
except ImportError:
    check_queue_slo = None


DEFAULT_BRIEFING_STYLE = {
    "separator_width": 64,
    "show_ascii_graphics": True,
    "show_infographics": True,
    "show_sparklines": True,
    "progress_bar": {
        "width": 10,
        "filled_char": "#",
        "empty_char": ".",
        "left_bracket": "[",
        "right_bracket": "]",
    },
    "sparkline_chars": "▁▂▃▄▅▆▇█",
}


# _load_briefing_style + _build_progress_bar + format_statusline migrated to
# briefing/formatters.py. Re-exported at the bottom of this file for
# import-site compatibility with existing callers.


# _sparkline + _compute_signal_quality + get_briefing_signal_quality
# migrated to briefing/signal_quality.py — re-exported at the bottom of
# this file for import-site compatibility with existing callers.


def get_briefing_style_path() -> Path:
    """Get path to persistent briefing style config."""
    return Path(__file__).parent / "config" / "briefing_style.json"


def get_briefing_style() -> Dict[str, Any]:
    """Get effective briefing style (defaults merged with file)."""
    return _load_briefing_style()


def validate_briefing_style(style: Optional[Dict[str, Any]] = None) -> List[str]:
    """Validate briefing style and return list of errors (empty if valid)."""
    data = style or _load_briefing_style()
    errors: List[str] = []

    if not isinstance(data.get("separator_width"), int) or data.get("separator_width", 0) < 20:
        errors.append("separator_width must be an integer >= 20")

    for key in ["show_ascii_graphics", "show_infographics", "show_sparklines"]:
        if not isinstance(data.get(key), bool):
            errors.append(f"{key} must be true/false")

    pb = data.get("progress_bar")
    if not isinstance(pb, dict):
        errors.append("progress_bar must be an object")
    else:
        if not isinstance(pb.get("width"), int) or pb.get("width", 0) < 1:
            errors.append("progress_bar.width must be an integer >= 1")
        for char_key in ["filled_char", "empty_char", "left_bracket", "right_bracket"]:
            val = pb.get(char_key)
            if not isinstance(val, str) or len(val) != 1:
                errors.append(f"progress_bar.{char_key} must be a single character")

    sparkline_chars = data.get("sparkline_chars")
    if not isinstance(sparkline_chars, str) or len(sparkline_chars) < 2:
        errors.append("sparkline_chars must be a string with at least 2 characters")

    return errors


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
    project_snapshot: Optional[List[Dict[str, Any]]] = None  # Top active projects with metrics
    period: str = "24h"

    # Enhanced intelligence fields
    intelligence_metrics: Optional[Dict[str, Any]] = None  # Learning system metrics
    strategic_alignment: Optional[Dict[str, Any]] = None  # Goal velocity, drift
    temporal_context: Optional[Dict[str, Any]] = None  # Day patterns, session continuity
    cross_project_insights: Optional[Dict[str, Any]] = None  # Related work, patterns
    predictive_insights: Optional[Dict[str, Any]] = None  # Predicted focus, optimal sequence

    # Resource & Orchestration Intelligence (High-Value)
    resource_intelligence: Optional[Dict[str, Any]] = None  # AIO consumption, pacing
    orchestration_advisory: Optional[Dict[str, Any]] = (
        None  # Agent recommendations, batch vs interactive
    )
    velocity_metrics: Optional[Dict[str, Any]] = None  # ROI, time savings

    # Overnight batch insights (surfaced from completed AI analysis tasks)
    batch_insights: Optional[Dict[str, Any]] = None
    bandwidth_contract_metrics: Optional[Dict[str, Any]] = None
    queue_slo: Optional[Dict[str, Any]] = None


# BriefingGenerator + generate_daily_briefing migrated to briefing/generator.py
# — re-exported at the bottom of this file for import-site compatibility.


# format_briefing migrated to briefing/formatters.py — see re-export below.


# format_briefing_json migrated to briefing/formatters.py — see re-export below.


# format_statusline migrated to briefing/formatters.py — see re-export below.


# format_statusline_json + get_executive_summary migrated to
# briefing/formatters.py. Re-exported at the bottom of this file.




# ============================================================================
# Re-exports for the briefing/formatters.py split (Phase 3b)
# ============================================================================
# Functions migrated to briefing.formatters are re-exported here so existing
# `from briefing import X` import sites continue to work unchanged. New
# callers should import directly from briefing.formatters.
from briefing.formatters import (  # noqa: E402
    _load_briefing_style,
    _build_progress_bar,
    detect_resume_context,
    detect_stale_items,
    format_briefing,
    format_briefing_json,
    format_compact,
    format_statusline,
    format_statusline_json,
    get_executive_summary,
)
from briefing.signal_quality import (  # noqa: E402
    _compute_signal_quality,
    _sparkline,
    get_briefing_signal_quality,
)
from briefing.generator import (  # noqa: E402
    BriefingGenerator,
    generate_daily_briefing,
)


if __name__ == "__main__":
    # Test the briefing generator
    briefing = generate_daily_briefing()
    print(format_briefing(briefing))
    print("\n--- EXECUTIVE SUMMARY ---\n")
    print(get_executive_summary(briefing))
