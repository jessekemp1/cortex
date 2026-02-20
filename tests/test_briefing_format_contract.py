#!/usr/bin/env python3
"""Regression tests for briefing format/style contract."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from briefing import (
    BriefingData,
    format_briefing,
    format_statusline,
    validate_briefing_style,
)


def _sample_briefing() -> BriefingData:
    return BriefingData(
        active_projects=["vortex-backend", "cortex", "alpha_arena"],
        recent_commits_24h=21,
        total_commits_7d=133,
        blockers=[{"project": "Winfield", "blocker": "Missing .env file"}],
        priority_actions=[
            {
                "priority": "HIGH",
                "title": "Fix forecast endpoint reliability",
                "project": "vortex-backend",
                "steps": ["Add guard for model lookup", "Run e2e API tests"],
                "estimated_impact": "high",
            }
        ],
        patterns=["Vortex backend momentum: 30 commits this week"],
        waiting_on=[],
        project_snapshot=[
            {
                "project": "vortex-backend",
                "commits_7d": 30,
                "uncommitted": 2,
                "status": "active",
                "trend": "hot",
            },
            {
                "project": "cortex",
                "commits_7d": 18,
                "uncommitted": 1,
                "status": "active",
                "trend": "active",
            },
            {
                "project": "alpha_arena",
                "commits_7d": 7,
                "uncommitted": 0,
                "status": "active",
                "trend": "active",
            },
        ],
        git_status={
            "summary": {"current_branch": "main", "uncommitted_changes": 3, "untracked_files": 1}
        },
        work_progress={"items_24h": 4, "orphaned_24h": 1, "drifts_total": 2},
        batch_insights={"total_completed_24h": 6},
        temporal_context={"day_of_week": "Friday", "time_of_day": "Morning"},
        predictive_insights={
            "predictions": [
                {
                    "confidence": "high",
                    "prediction": "Continue work on Vortex backend",
                    "reason": "Momentum and open action items",
                }
            ],
            "optimal_sequence": [{"task": "Review and commit pending changes"}],
        },
        generated_at=datetime(2026, 2, 13, 8, 0, 0),
    )


def test_briefing_format_contains_required_sections():
    briefing = _sample_briefing()
    output = format_briefing(briefing, use_color=False)

    required_headers = [
        "DAILY BRIEFING - February 13, 2026",
        "TL;DR",
        "EXECUTIVE SUMMARY",
        "PROJECT SNAPSHOT",
        "PORTFOLIO PULSE",
        "PRIORITY ACTIONS",
        "TODAY'S CONTEXT",
        "PREDICTIVE INSIGHTS",
    ]
    for header in required_headers:
        assert header in output

    assert "Health ratio:" in output
    assert "Commit trend (24h→7d):" in output


def test_project_snapshot_has_tabular_row():
    briefing = _sample_briefing()
    output = format_briefing(briefing, use_color=False)
    assert "Project                     C7d  WIP  Trend" in output
    assert "vortex-backend" in output


def test_briefing_style_validation_rejects_invalid_config():
    invalid = {
        "separator_width": 10,  # too narrow
        "show_ascii_graphics": "yes",  # must be bool
        "progress_bar": {"width": 0, "filled_char": "##"},  # invalid width/char
        "sparkline_chars": "_",  # too short
    }
    errors = validate_briefing_style(invalid)
    assert errors
    assert any("separator_width" in err for err in errors)
    assert any("show_ascii_graphics" in err for err in errors)


def test_statusline_contains_core_metrics_single_line():
    briefing = _sample_briefing()
    output = format_statusline(briefing, use_color=False, max_width=200)

    assert "\n" not in output
    assert "[CORTEX]" in output
    assert "P:3" in output
    assert "C7:133" in output
    assert "B:1" in output
    assert "SIG:" in output
    assert "TOP[HIGH]:" in output


def test_briefing_shows_signal_warning_when_dirty_tree_is_high():
    briefing = _sample_briefing()
    briefing.git_status = {
        "summary": {
            "current_branch": "main",
            "uncommitted_changes": 57,
            "untracked_files": 33,
        }
    }
    output = format_briefing(briefing, use_color=False)
    assert "[SIGNAL QUALITY: LOW]" in output
