#!/usr/bin/env python3
"""Tests for briefing_resilient.py — tiered fallback briefing."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add cortex to path
cortex_dir = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_dir))

from briefing_resilient import (
    format_resilient_briefing,
    generate_resilient_briefing,
    _extract_immediate_actions,
    _extract_active_goals,
    _extract_high_priority,
    _get_cortex_state,
    _parse_goals_md,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_GOALS_MD = """\
# Strategic Goals

## Active Goals

### Goal 3: Alpha Arena Strategy Ensemble Engine v3
**Priority:** P2 | **Status:** IN PROGRESS (live data)
- [x] Phase 1-3 done
- [ ] Gather live data

### Goal 5: Cortex Private Beta
**Priority:** P2 | **Status:** ON HOLD

---

## Immediate Actions (Week: Apr 7 - Apr 11)

### This Week (Apr 7 - Apr 11)

- [x] **Remove Winfield from Cortex monitoring** — done
- [ ] **Alpha Arena adaptive ensemble staleness** — open-loop
- [ ] Pupil Phase 3: first live unemployment nowcast
- [~] Goal 9: Install shell hooks (on hold)
- [!] **Blocked item** — waiting on credentials

### High Priority

1. **Cortex batch queue fix** — 19k failed jobs
2. **EMOS production analysis** — data accumulating

### Medium Priority

3. **Pupil Phase 3** — leading indicators validated
"""


@pytest.fixture()
def tmp_goals(tmp_path: Path) -> Path:
    """Create a temp GOALS.md and return the root dir."""
    (tmp_path / "GOALS.md").write_text(SAMPLE_GOALS_MD, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Tier 1 tests
# ---------------------------------------------------------------------------


class TestTier1:
    def test_tier1_succeeds_when_modules_available(self, tmp_path):
        """When BriefingGenerator works, result should be tier=1."""
        mock_briefing = MagicMock()

        with patch(
            "briefing_resilient._tier1_full_briefing",
            return_value={"briefing_object": mock_briefing},
        ):
            result = generate_resilient_briefing(root_dir=tmp_path)

        assert result["tier"] == 1
        assert result["data"]["briefing_object"] is mock_briefing
        assert result["warnings"] == []

    def test_tier1_warning_captured_on_failure(self, tmp_path):
        """If Tier 1 raises, a warning should be added and fallback happens."""

        def raise_import(root_dir):
            raise ImportError("briefing module broken")

        # Tier 2 also needs to not crash — patch it to succeed
        fake_tier2 = {
            "immediate_actions": [],
            "active_goals": [],
            "high_priority": [],
            "git": {},
            "cortex_state": {},
        }

        with patch("briefing_resilient._tier1_full_briefing", side_effect=raise_import):
            with patch("briefing_resilient._tier2_file_based", return_value=fake_tier2):
                result = generate_resilient_briefing(root_dir=tmp_path)

        assert result["tier"] == 2
        assert any("Tier 1" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Tier 2 tests
# ---------------------------------------------------------------------------


class TestTier2:
    def test_tier2_fallback_on_import_error(self, tmp_goals):
        """If Tier 1 fails with ImportError, Tier 2 should parse GOALS.md."""

        def raise_import(root_dir):
            raise ImportError("no module named briefing")

        with patch("briefing_resilient._tier1_full_briefing", side_effect=raise_import):
            result = generate_resilient_briefing(root_dir=tmp_goals)

        assert result["tier"] == 2
        assert any("Tier 1" in w for w in result["warnings"])
        data = result["data"]
        assert "immediate_actions" in data
        assert "git" in data

    def test_tier2_parses_goals_md_correctly(self, tmp_goals):
        """Tier 2 should correctly parse all item types from GOALS.md."""
        parsed = _parse_goals_md(tmp_goals / "GOALS.md")

        actions = parsed["immediate_actions"]

        # Done item
        done_item = next((a for a in actions if "Remove Winfield" in a["text"]), None)
        assert done_item is not None
        assert done_item["status"] == "done"

        # Pending items
        pending = [a for a in actions if a["status"] == "pending"]
        assert len(pending) >= 2

        # On-hold
        onhold = next((a for a in actions if a["status"] == "on-hold"), None)
        assert onhold is not None
        assert "shell hooks" in onhold["text"]

        # Blocked
        blocked = next((a for a in actions if a["status"] == "blocked"), None)
        assert blocked is not None
        assert "Blocked item" in blocked["text"]

    def test_tier2_parses_active_goals(self, tmp_goals):
        """Active goals should include title, priority, and status."""
        parsed = _parse_goals_md(tmp_goals / "GOALS.md")
        goals = parsed["active_goals"]

        assert len(goals) >= 1
        arena = next((g for g in goals if "Alpha Arena" in g["title"]), None)
        assert arena is not None
        assert arena["priority"] == "P2"
        assert "IN PROGRESS" in arena["status"]

    def test_tier2_parses_high_priority(self, tmp_goals):
        """High priority items should be extracted as plain strings."""
        parsed = _parse_goals_md(tmp_goals / "GOALS.md")
        high = parsed["high_priority"]
        assert len(high) >= 1
        assert any("Cortex batch queue fix" in item for item in high)

    def test_tier2_reads_cortex_state_files(self, tmp_path, monkeypatch):
        """Tier 2 should read outcomes.jsonl and count lines."""
        cortex_home = tmp_path / ".cortex"
        learning_dir = cortex_home / "learning"
        learning_dir.mkdir(parents=True)

        outcomes = learning_dir / "outcomes.jsonl"
        outcomes.write_text('{"id": 1}\n{"id": 2}\n{"id": 3}\n', encoding="utf-8")

        alerts_path = cortex_home / "alerts.jsonl"
        alerts_path.write_text(
            '{"message": "test alert 1"}\n{"message": "test alert 2"}\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        state = _get_cortex_state()
        assert state["outcomes_count"] == 3
        assert len(state["recent_alerts"]) == 2
        assert "test alert" in state["recent_alerts"][0]

    def test_tier2_missing_cortex_state_returns_defaults(self, tmp_path, monkeypatch):
        """If ~/.cortex/ doesn't exist, cortex_state should still return a dict."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
        state = _get_cortex_state()
        assert isinstance(state, dict)
        assert state.get("outcomes_count", 0) == 0
        assert state.get("recent_alerts") == []

    def test_tier2_missing_goals_md_raises(self, tmp_path):
        """_parse_goals_md should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            _parse_goals_md(tmp_path / "GOALS.md")


# ---------------------------------------------------------------------------
# Tier 3 tests
# ---------------------------------------------------------------------------


class TestTier3:
    def _fail_everything_except_git(self, root_dir):
        raise RuntimeError("tier 2 forced fail")

    def test_tier3_fallback_on_everything_failing(self, tmp_path):
        """When both Tier 1 and Tier 2 fail, Tier 3 should succeed with git data."""

        def raise_t1(root_dir):
            raise ImportError("no briefing module")

        def raise_t2(root_dir, warnings):
            raise RuntimeError("file-based failed")

        with (
            patch("briefing_resilient._tier1_full_briefing", side_effect=raise_t1),
            patch("briefing_resilient._tier2_file_based", side_effect=raise_t2),
        ):
            result = generate_resilient_briefing(root_dir=tmp_path)

        assert result["tier"] == 3
        assert "git" in result["data"]
        assert any("Tier 1" in w for w in result["warnings"])
        assert any("Tier 2" in w for w in result["warnings"])

    def test_tier3_always_returns_git_status(self, tmp_path):
        """Tier 3 should always return git dict even when in a real repo."""

        def raise_t1(root_dir):
            raise ImportError("no briefing")

        def raise_t2(root_dir, warnings):
            raise RuntimeError("file fail")

        with (
            patch("briefing_resilient._tier1_full_briefing", side_effect=raise_t1),
            patch("briefing_resilient._tier2_file_based", side_effect=raise_t2),
        ):
            result = generate_resilient_briefing(root_dir=tmp_path)

        git = result["data"]["git"]
        assert "branch" in git
        assert "status_lines" in git
        assert "recent_commits" in git
        # branch should be a non-empty string
        assert isinstance(git["branch"], str)
        assert len(git["branch"]) > 0


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_tier2_includes_immediate_actions(self, tmp_goals):
        """Tier 2 formatted output should list immediate action items."""

        def raise_t1(root_dir):
            raise ImportError("no briefing")

        with patch("briefing_resilient._tier1_full_briefing", side_effect=raise_t1):
            result = generate_resilient_briefing(root_dir=tmp_goals)

        assert result["tier"] == 2
        output = format_resilient_briefing(result, use_color=False)
        assert "Immediate Actions" in output
        # Pending items should appear
        assert "Alpha Arena adaptive ensemble staleness" in output
        # Status markers should be present
        assert "[ ]" in output or "[x]" in output

    def test_format_tier2_shows_bridge_warning(self, tmp_goals):
        """Tier 2 output should include the 'local mode' warning."""

        def raise_t1(root_dir):
            raise ImportError("no briefing")

        with patch("briefing_resilient._tier1_full_briefing", side_effect=raise_t1):
            result = generate_resilient_briefing(root_dir=tmp_goals)

        output = format_resilient_briefing(result, use_color=False)
        assert "local mode" in output.lower() or "bridge" in output.lower()

    def test_format_tier3_shows_warning(self, tmp_path):
        """Tier 3 formatted output should have a prominent minimal-mode warning."""

        def raise_t1(root_dir):
            raise ImportError("no briefing")

        def raise_t2(root_dir, warnings):
            raise RuntimeError("file fail")

        with (
            patch("briefing_resilient._tier1_full_briefing", side_effect=raise_t1),
            patch("briefing_resilient._tier2_file_based", side_effect=raise_t2),
        ):
            result = generate_resilient_briefing(root_dir=tmp_path)

        output = format_resilient_briefing(result, use_color=False)
        assert "MINIMAL MODE" in output or "minimal mode" in output.lower()

    def test_format_tier1_delegates_to_format_briefing(self):
        """Tier 1 format should call briefing.format_briefing."""
        mock_briefing = MagicMock()
        mock_formatted = "FULL BRIEFING OUTPUT"

        with patch(
            "briefing_resilient._tier1_full_briefing",
            return_value={"briefing_object": mock_briefing},
        ):
            result = generate_resilient_briefing(root_dir=Path("/tmp"))

        with patch("briefing.format_briefing", return_value=mock_formatted) as mock_fb:
            output = format_resilient_briefing(result, use_color=False)

        mock_fb.assert_called_once_with(mock_briefing, use_color=False)
        assert output == mock_formatted


# ---------------------------------------------------------------------------
# Warnings tests
# ---------------------------------------------------------------------------


class TestWarnings:
    def test_resilient_reports_warnings_about_failures(self, tmp_path):
        """Warnings list should describe what failed and why."""

        def raise_t1(root_dir):
            raise ImportError("cannot import briefing: module not found")

        fake_t2 = {
            "immediate_actions": [],
            "active_goals": [],
            "high_priority": [],
            "git": {},
            "cortex_state": {},
        }

        with patch("briefing_resilient._tier1_full_briefing", side_effect=raise_t1):
            with patch("briefing_resilient._tier2_file_based", return_value=fake_t2):
                result = generate_resilient_briefing(root_dir=tmp_path)

        assert len(result["warnings"]) >= 1
        combined = " ".join(result["warnings"])
        assert "Tier 1" in combined
        # Error message should be included
        assert "briefing" in combined.lower() or "import" in combined.lower()

    def test_resilient_empty_warnings_on_tier1_success(self, tmp_path):
        """When Tier 1 succeeds, warnings should be empty."""
        mock_briefing = MagicMock()

        with patch(
            "briefing_resilient._tier1_full_briefing",
            return_value={"briefing_object": mock_briefing},
        ):
            result = generate_resilient_briefing(root_dir=tmp_path)

        assert result["tier"] == 1
        assert result["warnings"] == []
