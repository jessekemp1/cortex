#!/usr/bin/env python3
"""Tests for compact briefing formatter and stale item detection."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add cortex to path
cortex_dir = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_dir))
sys.path.insert(0, str(cortex_dir.parent / "scripts"))

from briefing import (
    BriefingData,
    detect_resume_context,
    detect_stale_items,
    format_compact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_briefing(**kwargs) -> BriefingData:
    defaults = dict(
        active_projects=["vortex", "cortex"],
        recent_commits_24h=3,
        total_commits_7d=12,
        blockers=[],
        priority_actions=[{"title": "Fix embeddings client", "action": "fix"}],
        patterns=[],
        waiting_on=[],
        generated_at=datetime(2026, 4, 9, 8, 0, 0),
        resource_status=None,
    )
    defaults.update(kwargs)
    return BriefingData(**defaults)


@pytest.fixture(autouse=True)
def _patch_slow_ops():
    """Patch slow briefing operations that require live git/disk access."""
    from unittest.mock import MagicMock

    mock_pm = MagicMock()
    mock_pm.alert_generator.generate_alerts.return_value = []

    with (
        patch("briefing.GitTracker", None),
        patch("briefing.ProcessMonitor", None),
    ):
        yield


# ---------------------------------------------------------------------------
# 1. format_compact produces a bordered box
# ---------------------------------------------------------------------------


def test_format_compact_produces_bordered_box():
    briefing = _make_briefing()
    with (
        patch("briefing.detect_resume_context", return_value=None),
        patch("briefing.detect_stale_items", return_value=[]),
    ):
        output = format_compact(briefing, use_color=False)

    lines = output.splitlines()
    assert lines[0].startswith("┌"), f"Expected top border starting with ┌, got: {lines[0]!r}"
    assert lines[-1].startswith("└"), f"Expected bottom border starting with └, got: {lines[-1]!r}"
    assert lines[-1].endswith("┘"), f"Expected bottom border ending with ┘, got: {lines[-1]!r}"
    # Inner lines should have │ borders
    inner = lines[1:-1]
    for line in inner:
        assert line.startswith("│"), f"Expected inner line starting with │, got: {line!r}"
        assert line.endswith("│"), f"Expected inner line ending with │, got: {line!r}"


# ---------------------------------------------------------------------------
# 2. format_compact is action-first (▸ on first content line)
# ---------------------------------------------------------------------------


def test_format_compact_action_first():
    briefing = _make_briefing()
    resume_ctx = {
        "summary": "supervisor (4 files)",
        "files": [
            {"name": "dispatch.py", "insertions": 43},
            {"name": "router.py", "insertions": 33},
        ],
        "directory": "cortex/supervisor",
    }
    with (
        patch("briefing.detect_resume_context", return_value=resume_ctx),
        patch("briefing.detect_stale_items", return_value=[]),
    ):
        output = format_compact(briefing, use_color=False)

    lines = output.splitlines()
    # First content line (index 1) should contain the ▸ action indicator
    first_content = lines[1]
    assert "▸" in first_content, f"Expected ▸ on first content line, got: {first_content!r}"
    assert "RESUME" in first_content or "supervisor" in first_content


# ---------------------------------------------------------------------------
# 3. detect_resume_context with changes
# ---------------------------------------------------------------------------


def test_detect_resume_context_with_changes():
    diff_stat_output = (
        " cortex/supervisor/dispatch.py | 43 ++++++++++---\n"
        " cortex/supervisor/router.py   | 33 ++++++------\n"
        " 2 files changed, 43 insertions(+), 33 deletions(-)\n"
    )
    status_output = "M  cortex/supervisor/dispatch.py\nM  cortex/supervisor/router.py\n"

    mock_diff = MagicMock()
    mock_diff.stdout = diff_stat_output
    mock_diff.returncode = 0

    mock_status = MagicMock()
    mock_status.stdout = status_output
    mock_status.returncode = 0

    with patch("subprocess.run", side_effect=[mock_diff, mock_status]):
        result = detect_resume_context()

    assert result is not None
    assert "supervisor" in result["summary"]
    assert "2 files" in result["summary"] or "file" in result["summary"]
    assert len(result["files"]) >= 1
    # Should detect insertions for dispatch.py
    dispatch = next((f for f in result["files"] if "dispatch" in f["name"]), None)
    assert dispatch is not None
    assert dispatch["insertions"] == 43


# ---------------------------------------------------------------------------
# 4. detect_resume_context with clean workspace
# ---------------------------------------------------------------------------


def test_detect_resume_context_clean_workspace():
    mock_diff = MagicMock()
    mock_diff.stdout = ""
    mock_diff.returncode = 0

    mock_status = MagicMock()
    mock_status.stdout = ""
    mock_status.returncode = 0

    with patch("subprocess.run", side_effect=[mock_diff, mock_status]):
        result = detect_resume_context()

    assert result is None


# ---------------------------------------------------------------------------
# 5. detect_stale_items finds old items
# ---------------------------------------------------------------------------


def test_detect_stale_items_finds_old_items(tmp_path):
    # Create a fake GOALS.md
    goals = tmp_path / "GOALS.md"
    goals.write_text(
        "# Goals\n## Immediate Actions\n- [ ] batch queue fix\n- [ ] wire RTOFS direct\n"
    )

    # Build fake git blame --line-porcelain output
    # timestamp: 10 days ago
    import time

    old_ts = int(time.time()) - (10 * 86400)
    recent_ts = int(time.time()) - (2 * 86400)

    blame_output = (
        f"aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111 1 1 1\n"
        f"author Jesse\n"
        f"author-time {old_ts}\n"
        f"summary Initial\n"
        f"\t# Goals\n"
        f"bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222 2 2 1\n"
        f"author Jesse\n"
        f"author-time {old_ts}\n"
        f"summary Initial\n"
        f"\t## Immediate Actions\n"
        f"cccc3333cccc3333cccc3333cccc3333cccc3333 3 3 1\n"
        f"author Jesse\n"
        f"author-time {old_ts}\n"
        f"summary Initial\n"
        f"\t- [ ] batch queue fix\n"
        f"dddd4444dddd4444dddd4444dddd4444dddd4444 4 4 1\n"
        f"author Jesse\n"
        f"author-time {recent_ts}\n"
        f"summary Recent\n"
        f"\t- [ ] wire RTOFS direct\n"
    )

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = blame_output

    with patch("subprocess.run", return_value=mock_result):
        stale = detect_stale_items(goals_path=goals, threshold_days=7)

    assert len(stale) == 1
    assert "batch queue fix" in stale[0]["text"]
    assert stale[0]["age_days"] >= 10


# ---------------------------------------------------------------------------
# 6. detect_stale_items returns empty for recent items
# ---------------------------------------------------------------------------


def test_detect_stale_items_no_stale(tmp_path):
    import time

    goals = tmp_path / "GOALS.md"
    goals.write_text("## Actions\n- [ ] fresh task\n")

    recent_ts = int(time.time()) - (2 * 86400)  # 2 days ago

    blame_output = (
        f"aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111 1 1 1\n"
        f"author Jesse\n"
        f"author-time {recent_ts}\n"
        f"summary Recent\n"
        f"\t## Actions\n"
        f"bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222 2 2 1\n"
        f"author Jesse\n"
        f"author-time {recent_ts}\n"
        f"summary Recent\n"
        f"\t- [ ] fresh task\n"
    )

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = blame_output

    with patch("subprocess.run", return_value=mock_result):
        stale = detect_stale_items(goals_path=goals, threshold_days=7)

    assert stale == []


# ---------------------------------------------------------------------------
# 7. format_compact includes STALE line when stale items exist
# ---------------------------------------------------------------------------


def test_format_compact_includes_stale_warning():
    briefing = _make_briefing()
    stale_items = [{"text": "batch queue fix", "age_days": 3}]

    with (
        patch("briefing.detect_resume_context", return_value=None),
        patch("briefing.detect_stale_items", return_value=stale_items),
    ):
        output = format_compact(briefing, use_color=False)

    assert "STALE" in output
    assert "batch queue fix" in output
    assert "3d" in output


# ---------------------------------------------------------------------------
# 8. format_compact works without colorama (no-color mode)
# ---------------------------------------------------------------------------


def test_format_compact_no_color_mode():
    briefing = _make_briefing()
    with (
        patch("briefing.detect_resume_context", return_value=None),
        patch("briefing.detect_stale_items", return_value=[]),
    ):
        output = format_compact(briefing, use_color=False)

    assert isinstance(output, str)
    assert len(output) > 0
    # No ANSI escape codes should be present
    assert "\x1b[" not in output

    # Box structure intact
    lines = output.splitlines()
    assert lines[0].startswith("┌")
    assert lines[-1].endswith("┘")


# ---------------------------------------------------------------------------
# 9. --compact flag exists in CLI and routes to format_compact
# ---------------------------------------------------------------------------


def test_compact_flag_in_cli():
    """Verify --compact is a recognized argument and calls format_compact."""
    import argparse

    # Import the CLI main to get the parser structure
    # We test by patching format_compact and verifying it gets called
    from cli.commands.briefing import cmd_briefing

    mock_briefing = _make_briefing()

    args = argparse.Namespace(
        compact=True,
        root=str(cortex_dir.parent),
        no_color=True,
        portfolio=False,
        format="text",
        strict_signal=False,
    )

    compact_output = "┌─ CORTEX ─┐\n│ ▸ test   │\n└──────────┘"

    with (
        patch("cli.commands.briefing.generate_daily_briefing", return_value=mock_briefing),
        patch("cli.commands.briefing.format_compact", return_value=compact_output) as mock_fc,
        patch("builtins.print") as mock_print,
    ):
        cmd_briefing(args)

    mock_fc.assert_called_once_with(mock_briefing, use_color=False)
    mock_print.assert_called_once_with(compact_output)
