"""
Tests for cortex/session_delta.py

Covers:
  - Snapshot capture and persistence
  - Loading latest / history
  - Delta computation (increases, no change, new commits)
  - Projection logic (on_track, stalled, ready, insufficient_data)
  - Formatting helpers
  - get_session_delta_report() first-session graceful handling
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure cortex root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from session_delta import (
    SessionDelta,
    SessionSnapshot,
    Projection,
    capture_snapshot,
    compute_delta,
    format_delta,
    format_projections,
    get_session_delta_report,
    load_latest_snapshot,
    load_snapshot_history,
    project_emos,
    project_metric,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    hours_ago: float = 0.0,
    emos: dict = None,
    batch: dict = None,
    goals_checksum: str = "abc123",
    uncommitted_files: list = None,
    last_commit: str = "deadbeef",
    test_counts: dict = None,
    bridge_status: str = "healthy",
    session_id: str = "testid01",
) -> SessionSnapshot:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return SessionSnapshot(
        timestamp=ts,
        session_id=session_id,
        emos=emos or {"ecmwf": 473, "gfs": 416, "hrrr": 2100, "ensemble": 44},
        batch=batch or {"failed": 100, "completed": 200},
        goals_checksum=goals_checksum,
        uncommitted_files=uncommitted_files or [],
        last_commit=last_commit,
        test_counts=test_counts or {"cortex": 1341},
        bridge_status=bridge_status,
    )


def _write_snapshot(snap: SessionSnapshot, snap_dir: Path) -> Path:
    """Persist a snapshot to snap_dir and return the file path."""
    fname = f"{snap.timestamp.replace(':', '-').replace('+', 'Z')}_{snap.session_id}.json"
    p = snap_dir / fname
    p.write_text(json.dumps(snap.__dict__))
    return p


# ---------------------------------------------------------------------------
# Part 1: Snapshot capture + loading
# ---------------------------------------------------------------------------


class TestCaptureSnapshot:
    def test_capture_snapshot_creates_file(self, tmp_path):
        """capture_snapshot saves a JSON file in the snapshot dir."""
        with (
            patch("session_delta._collect_emos", return_value={"ecmwf": 500}),
            patch("session_delta._collect_batch", return_value={"failed": 10}),
            patch("session_delta._goals_checksum", return_value="aabbcc"),
            patch("session_delta._collect_git_status", return_value=["M foo.py"]),
            patch("session_delta._collect_last_commit", return_value="abc123"),
            patch("session_delta._collect_bridge_status", return_value="healthy"),
        ):
            capture_snapshot(snapshot_dir=tmp_path)

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

        data = json.loads(files[0].read_text())
        assert data["emos"] == {"ecmwf": 500}
        assert data["batch"] == {"failed": 10}
        assert data["goals_checksum"] == "aabbcc"
        assert data["last_commit"] == "abc123"
        assert data["bridge_status"] == "healthy"
        assert isinstance(data["session_id"], str)

    def test_capture_snapshot_returns_snapshot_object(self, tmp_path):
        """capture_snapshot returns a SessionSnapshot dataclass."""
        with (
            patch("session_delta._collect_emos", return_value={}),
            patch("session_delta._collect_batch", return_value={}),
            patch("session_delta._goals_checksum", return_value=""),
            patch("session_delta._collect_git_status", return_value=[]),
            patch("session_delta._collect_last_commit", return_value=""),
            patch("session_delta._collect_bridge_status", return_value="down"),
        ):
            snap = capture_snapshot(snapshot_dir=tmp_path)

        assert isinstance(snap, SessionSnapshot)
        assert snap.bridge_status == "down"


class TestLoadLatestSnapshot:
    def test_load_latest_snapshot_returns_most_recent(self, tmp_path):
        """create 3 snapshot files with different timestamps, verify latest returned."""
        s1 = _make_snapshot(hours_ago=10, session_id="old00001")
        s2 = _make_snapshot(hours_ago=5, session_id="mid00002")
        s3 = _make_snapshot(hours_ago=1, session_id="new00003")

        _write_snapshot(s1, tmp_path)
        _write_snapshot(s2, tmp_path)
        _write_snapshot(s3, tmp_path)

        latest = load_latest_snapshot(snapshot_dir=tmp_path)
        assert latest is not None
        assert latest.session_id == "new00003"

    def test_load_latest_snapshot_returns_none_when_empty(self, tmp_path):
        result = load_latest_snapshot(snapshot_dir=tmp_path)
        assert result is None

    def test_load_latest_snapshot_returns_none_for_missing_dir(self, tmp_path):
        missing = tmp_path / "nonexistent"
        result = load_latest_snapshot(snapshot_dir=missing)
        assert result is None

    def test_load_latest_snapshot_skips_corrupt_files(self, tmp_path):
        """Corrupt JSON file is skipped; valid file is still returned."""
        (tmp_path / "2026-01-01T00-00-00Z_bad.json").write_text("NOT JSON")
        s = _make_snapshot(hours_ago=2, session_id="good0001")
        _write_snapshot(s, tmp_path)

        latest = load_latest_snapshot(snapshot_dir=tmp_path)
        assert latest is not None
        assert latest.session_id == "good0001"


class TestLoadSnapshotHistory:
    def test_load_snapshot_history_filters_by_days(self, tmp_path):
        """Snapshots older than N days are excluded."""
        old = _make_snapshot(hours_ago=200, session_id="verold01")  # ~8 days
        recent = _make_snapshot(hours_ago=24, session_id="recent01")

        _write_snapshot(old, tmp_path)
        _write_snapshot(recent, tmp_path)

        history = load_snapshot_history(days=7, snapshot_dir=tmp_path)
        ids = [s.session_id for s in history]
        assert "recent01" in ids
        assert "verold01" not in ids

    def test_load_snapshot_history_sorted_oldest_first(self, tmp_path):
        """History is sorted oldest to newest."""
        s1 = _make_snapshot(hours_ago=6, session_id="first001")
        s2 = _make_snapshot(hours_ago=3, session_id="second01")
        s3 = _make_snapshot(hours_ago=1, session_id="third001")

        _write_snapshot(s3, tmp_path)
        _write_snapshot(s1, tmp_path)
        _write_snapshot(s2, tmp_path)

        history = load_snapshot_history(days=7, snapshot_dir=tmp_path)
        ids = [s.session_id for s in history]
        assert ids == ["first001", "second01", "third001"]

    def test_load_snapshot_history_empty_dir(self, tmp_path):
        history = load_snapshot_history(days=7, snapshot_dir=tmp_path)
        assert history == []


# ---------------------------------------------------------------------------
# Part 2: Delta computation
# ---------------------------------------------------------------------------


class TestComputeDelta:
    def test_compute_delta_emos_increase(self):
        """Positive EMOS delta correctly computed."""
        prev = _make_snapshot(hours_ago=8, emos={"ecmwf": 473, "gfs": 416})
        curr = _make_snapshot(hours_ago=0, emos={"ecmwf": 504, "gfs": 444})

        delta = compute_delta(curr, prev)

        assert delta.emos_delta["ecmwf"] == 31
        assert delta.emos_delta["gfs"] == 28
        assert delta.hours_since == pytest.approx(8.0, abs=0.1)

    def test_compute_delta_no_change(self):
        """Identical snapshots produce zero deltas."""
        snap = _make_snapshot(
            emos={"ecmwf": 473},
            batch={"failed": 100},
            goals_checksum="same",
            last_commit="abc",
            test_counts={"cortex": 1341},
        )
        prev = _make_snapshot(
            hours_ago=4,
            emos={"ecmwf": 473},
            batch={"failed": 100},
            goals_checksum="same",
            last_commit="abc",
            test_counts={"cortex": 1341},
        )

        delta = compute_delta(snap, prev)

        assert delta.emos_delta["ecmwf"] == 0
        assert delta.batch_delta["failed"] == 0
        assert delta.goals_changed is False
        assert delta.new_commits == 0
        assert delta.files_changed is False
        assert delta.bridge_transition is None
        assert delta.test_delta["cortex"] == 0

    def test_compute_delta_new_commits(self):
        """New commits between two hashes are counted."""
        prev = _make_snapshot(hours_ago=2, last_commit="aaa111")
        curr = _make_snapshot(hours_ago=0, last_commit="bbb222")

        mock_output = "bbb222 feat: something\naaa333 fix: another thing"
        with patch("session_delta._run", return_value=mock_output):
            delta = compute_delta(curr, prev)

        assert delta.new_commits == 2
        assert len(delta.new_commit_messages) == 2

    def test_compute_delta_goals_changed(self):
        """goals_changed is True when checksums differ."""
        prev = _make_snapshot(goals_checksum="old_hash")
        curr = _make_snapshot(goals_checksum="new_hash")

        delta = compute_delta(curr, prev)
        assert delta.goals_changed is True

    def test_compute_delta_bridge_transition(self):
        """bridge_transition is set when status changes."""
        prev = _make_snapshot(bridge_status="degraded")
        curr = _make_snapshot(bridge_status="healthy")

        delta = compute_delta(curr, prev)
        assert delta.bridge_transition == "degraded→healthy"

    def test_compute_delta_no_bridge_transition_when_same(self):
        prev = _make_snapshot(bridge_status="healthy")
        curr = _make_snapshot(bridge_status="healthy")

        delta = compute_delta(curr, prev)
        assert delta.bridge_transition is None


# ---------------------------------------------------------------------------
# Part 2b: format_delta
# ---------------------------------------------------------------------------


class TestFormatDelta:
    def _delta(self, **kwargs) -> SessionDelta:
        defaults = dict(
            hours_since=4.0,
            emos_delta={"ecmwf": 0, "gfs": 0},
            batch_delta={},
            goals_changed=False,
            new_commits=0,
            new_commit_messages=[],
            files_changed=False,
            bridge_transition=None,
            test_delta={},
        )
        defaults.update(kwargs)
        return SessionDelta(**defaults)

    def test_format_delta_shows_changes(self):
        """When EMOS increased, delta is shown in output."""
        delta = self._delta(emos_delta={"ecmwf": 31, "gfs": 28})
        out = format_delta(delta)
        assert "ECMWF +31" in out
        assert "GFS +28" in out
        assert "Since last session" in out

    def test_format_delta_no_changes(self):
        """When nothing changed, shows 'No changes' message."""
        delta = self._delta()
        out = format_delta(delta)
        assert "No changes since last session" in out

    def test_format_delta_shows_new_commits(self):
        delta = self._delta(
            new_commits=2,
            new_commit_messages=["feat: thing", "fix: bug"],
            emos_delta={},
        )
        out = format_delta(delta)
        assert "New commits: 2" in out

    def test_format_delta_shows_goals_changed(self):
        delta = self._delta(goals_changed=True, emos_delta={})
        out = format_delta(delta)
        assert "GOALS.md: changed" in out

    def test_format_delta_shows_bridge_transition(self):
        delta = self._delta(bridge_transition="down→healthy", emos_delta={})
        out = format_delta(delta)
        assert "down→healthy" in out

    def test_format_delta_hours_displayed(self):
        delta = self._delta(emos_delta={"ecmwf": 5})
        out = format_delta(delta)
        assert "4.0h" in out


# ---------------------------------------------------------------------------
# Part 3: Projections
# ---------------------------------------------------------------------------


class TestProjectMetric:
    def _ts(self, days_ago: float) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

    def test_project_metric_on_track(self):
        """Steady increase projects a future date."""
        history = [
            (self._ts(7), 100),
            (self._ts(6), 200),
            (self._ts(5), 300),
            (self._ts(0), 800),
        ]
        proj = project_metric("emos_ecmwf", current=800, target=2000, history=history)
        assert proj.status == "on_track"
        assert proj.rate_per_day > 0
        assert proj.estimated_date is not None

    def test_project_metric_stalled(self):
        """No growth => stalled."""
        history = [
            (self._ts(5), 500),
            (self._ts(0), 500),
        ]
        proj = project_metric("emos_gfs", current=500, target=2000, history=history)
        assert proj.status == "stalled"
        assert proj.estimated_date is None

    def test_project_metric_ready(self):
        """current >= target => ready."""
        history = [(self._ts(3), 1800), (self._ts(0), 2100)]
        proj = project_metric("emos_hrrr", current=2100, target=2000, history=history)
        assert proj.status == "ready"
        assert proj.estimated_date is None

    def test_project_metric_insufficient_data(self):
        """Single data point => insufficient_data."""
        history = [(self._ts(0), 400)]
        proj = project_metric("emos_ecmwf", current=400, target=2000, history=history)
        assert proj.status == "insufficient_data"

    def test_project_metric_empty_history(self):
        """Empty history => insufficient_data."""
        proj = project_metric("emos_ecmwf", current=400, target=2000, history=[])
        assert proj.status == "insufficient_data"

    def test_project_metric_correct_rate(self):
        """Rate computation is accurate (100 units over 10 days = 10/day)."""
        ts_old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        ts_new = datetime.now(timezone.utc).isoformat()
        history = [(ts_old, 0), (ts_new, 100)]
        proj = project_metric("emos_ecmwf", current=100, target=2000, history=history)
        assert proj.rate_per_day == pytest.approx(10.0, abs=0.5)


class TestProjectEmos:
    def _make_history_snaps(self) -> list[SessionSnapshot]:
        snaps = []
        for i in range(5):
            hours = (4 - i) * 24
            snaps.append(
                _make_snapshot(
                    hours_ago=float(hours),
                    emos={
                        "ecmwf": 300 + i * 50,
                        "gfs": 200 + i * 40,
                        "hrrr": 2100,  # already done
                        "ensemble": 20 + i * 5,
                    },
                    session_id=f"hist{i:04d}",
                )
            )
        return snaps

    def test_project_emos_returns_four_models(self):
        history = self._make_history_snaps()
        projs = project_emos(history, target=2000)
        metric_names = [p.metric for p in projs]
        assert "emos_ecmwf" in metric_names
        assert "emos_gfs" in metric_names
        assert "emos_hrrr" in metric_names
        assert "emos_ensemble" in metric_names

    def test_project_emos_hrrr_is_ready(self):
        history = self._make_history_snaps()
        projs = project_emos(history, target=2000)
        hrrr = next(p for p in projs if p.metric == "emos_hrrr")
        assert hrrr.status == "ready"


class TestFormatProjections:
    def test_format_projections_shows_dates(self):
        """On-track metrics include their estimated date."""
        from datetime import date

        future_date = (date.today() + timedelta(days=5)).isoformat()
        projs = [
            Projection(
                metric="emos_ecmwf",
                current=940,
                target=2000,
                rate_per_day=68.0,
                estimated_date=future_date,
                status="on_track",
            )
        ]
        out = format_projections(projs)
        assert future_date in out
        assert "ECMWF" in out
        assert "+68/day" in out

    def test_format_projections_shows_ready(self):
        projs = [
            Projection(
                metric="emos_hrrr",
                current=2100,
                target=2000,
                rate_per_day=0.0,
                estimated_date=None,
                status="ready",
            )
        ]
        out = format_projections(projs)
        assert "READY" in out
        assert "HRRR" in out

    def test_format_projections_shows_stalled(self):
        projs = [
            Projection(
                metric="emos_gfs",
                current=500,
                target=2000,
                rate_per_day=0.0,
                estimated_date=None,
                status="stalled",
            )
        ]
        out = format_projections(projs)
        assert "STALLED" in out

    def test_format_projections_empty_list(self):
        out = format_projections([])
        assert out == ""


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


class TestGetSessionDeltaReport:
    def test_get_session_delta_report_first_session(self, tmp_path):
        """No previous snapshot — returns graceful first-session message."""
        with (
            patch("session_delta._collect_emos", return_value={}),
            patch("session_delta._collect_batch", return_value={}),
            patch("session_delta._goals_checksum", return_value=""),
            patch("session_delta._collect_git_status", return_value=[]),
            patch("session_delta._collect_last_commit", return_value=""),
            patch("session_delta._collect_bridge_status", return_value="down"),
        ):
            report = get_session_delta_report(snapshot_dir=tmp_path)

        # Should not crash
        assert isinstance(report, str)
        # Only one snapshot exists so only projections (if any) or first-session message
        assert "first session" in report.lower() or "EMOS" in report or "No changes" in report

    def test_get_session_delta_report_with_previous(self, tmp_path):
        """With a previous snapshot, delta is included in output."""
        # Write a previous snapshot manually
        prev = _make_snapshot(
            hours_ago=8,
            emos={"ecmwf": 400, "gfs": 350},
            session_id="prevtest",
        )
        _write_snapshot(prev, tmp_path)

        with (
            patch("session_delta._collect_emos", return_value={"ecmwf": 450, "gfs": 380}),
            patch("session_delta._collect_batch", return_value={}),
            patch("session_delta._goals_checksum", return_value="checksum"),
            patch("session_delta._collect_git_status", return_value=[]),
            patch("session_delta._collect_last_commit", return_value="newcommit"),
            patch("session_delta._collect_bridge_status", return_value="healthy"),
            patch("session_delta._run", return_value=""),  # no new commits
        ):
            report = get_session_delta_report(snapshot_dir=tmp_path)

        assert isinstance(report, str)
        # EMOS delta should appear since it changed
        assert "ECMWF" in report or "ecmwf" in report.lower()

    def test_get_session_delta_report_never_raises(self, tmp_path):
        """Even if internals fail, report is returned as string."""
        with patch("session_delta.capture_snapshot", side_effect=RuntimeError("boom")):
            report = get_session_delta_report(snapshot_dir=tmp_path)
        assert isinstance(report, str)
        assert "unavailable" in report.lower()
