"""Tests for intelligence/failure_emitter.py."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from intelligence import failure_emitter as fe


# ---------------------------------------------------------------------------


class TestCollectPytestFailures:
    def test_returns_signal_per_failing_nodeid(self, tmp_path):
        cache = tmp_path / "lastfailed"
        cache.write_text(
            json.dumps(
                {
                    "tests/test_a.py::TestX::test_one": True,
                    "tests/test_b.py::test_two": True,
                }
            )
        )
        sigs = fe.collect_pytest_failures(cache)
        assert len(sigs) == 2
        assert all(s.source == "pytest" for s in sigs)
        ids = {s.signal_id for s in sigs}
        assert "tests/test_a.py::TestX::test_one" in ids

    def test_missing_cache_returns_empty(self, tmp_path):
        assert fe.collect_pytest_failures(tmp_path / "nope") == []

    def test_unreadable_cache_returns_empty(self, tmp_path):
        bad = tmp_path / "lastfailed"
        bad.write_text("not json")
        assert fe.collect_pytest_failures(bad) == []


class TestCollectRestartFailures:
    def test_restart_within_window_emits_signal(self, tmp_path):
        log = tmp_path / "restart_history.jsonl"
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        log.write_text(
            json.dumps(
                {
                    "timestamp": recent,
                    "service": "vortex-backend",
                    "reason": "health check failed",
                }
            )
            + "\n"
        )
        sigs = fe.collect_restart_failures(log, lookback_minutes=60)
        assert len(sigs) == 1
        assert sigs[0].source == "restart"
        assert "vortex-backend" in sigs[0].title

    def test_old_restart_excluded(self, tmp_path):
        log = tmp_path / "restart_history.jsonl"
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        log.write_text(json.dumps({"timestamp": old, "service": "x"}) + "\n")
        assert fe.collect_restart_failures(log, lookback_minutes=60) == []


class TestCollectSchedulerFailures:
    def test_status_error_emits(self, tmp_path):
        log = tmp_path / "scheduler_jobs.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "job": "nightly_briefing",
                    "status": "error",
                    "error": "RuntimeError: boom",
                }
            )
            + "\n"
        )
        sigs = fe.collect_scheduler_failures(log)
        assert len(sigs) == 1
        assert sigs[0].source == "scheduler"

    def test_status_ok_skipped(self, tmp_path):
        log = tmp_path / "scheduler_jobs.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "job": "nightly_briefing",
                    "status": "ok",
                }
            )
            + "\n"
        )
        assert fe.collect_scheduler_failures(log) == []


class TestCollectAlertFailures:
    def test_critical_alert_emits(self, tmp_path):
        log = tmp_path / "alerts.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "severity": "critical",
                    "key": "cortex-runtime",
                    "title": "service down",
                    "message": "5xx",
                }
            )
            + "\n"
        )
        sigs = fe.collect_alert_failures(log)
        assert len(sigs) == 1
        assert sigs[0].source == "alert"

    def test_info_alert_skipped(self, tmp_path):
        log = tmp_path / "alerts.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "severity": "info",
                    "key": "x",
                }
            )
            + "\n"
        )
        assert fe.collect_alert_failures(log) == []


class TestCollectAnomalyFailures:
    def _make_db(self, tmp_path, rows):
        import sqlite3

        db = tmp_path / "orchestration.db"
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE anomalies (anomaly_id TEXT PRIMARY KEY, anomaly_type TEXT, "
            "severity TEXT, detected_at TEXT, title TEXT, description TEXT, "
            "metric_value REAL DEFAULT 0, threshold_value REAL DEFAULT 0, remediation TEXT DEFAULT '')"
        )
        conn.executemany(
            "INSERT INTO anomalies (anomaly_id, anomaly_type, severity, detected_at, title, description) "
            "VALUES (?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        return db

    def test_failure_anomaly_emits(self, tmp_path):
        ts = datetime.now(timezone.utc).isoformat()
        db = self._make_db(
            tmp_path,
            [("a1", "stuck_tasks", "CRITICAL", ts, "Task stuck in planning", "5h")],
        )
        sigs = fe.collect_anomaly_failures(db)
        assert len(sigs) == 1
        assert sigs[0].source == "anomaly"

    def test_context_switching_type_skipped(self, tmp_path):
        ts = datetime.now(timezone.utc).isoformat()
        db = self._make_db(
            tmp_path,
            [("a1", "context_switching_risk", "CRITICAL", ts, "8 projects", "noise")],
        )
        assert fe.collect_anomaly_failures(db) == []

    def test_old_anomaly_excluded(self, tmp_path):
        old = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
        db = self._make_db(
            tmp_path,
            [("a1", "stuck_tasks", "CRITICAL", old, "stuck", "x")],
        )
        assert fe.collect_anomaly_failures(db, lookback_minutes=60) == []

    def test_missing_db_returns_empty(self, tmp_path):
        assert fe.collect_anomaly_failures(tmp_path / "nope.db") == []


class TestCollapseRepeats:
    def test_repeats_collapse_to_one_weighted_signal(self):
        sigs = [
            fe.FailureSignal("restart", f"svc:{i}", "service restart: svc", "died", f"2026-07-2{i}")
            for i in range(5)
        ]
        collapsed = fe._collapse_repeats(sigs)
        assert len(collapsed) == 1
        assert "x5" in collapsed[0].title
        # The collapsed signal_id must be the stable family key (not the latest
        # timestamped id) so the emitter ledger dedups it across runs.
        assert collapsed[0].signal_id == "restart:service restart: svc"

    def test_distinct_failures_not_collapsed(self):
        sigs = [
            fe.FailureSignal("restart", "a:1", "service restart: a", "x", "2026-07-21"),
            fe.FailureSignal("restart", "b:1", "service restart: b", "x", "2026-07-21"),
        ]
        assert len(fe._collapse_repeats(sigs)) == 2

    def test_pytest_signals_kept_distinct(self):
        sigs = [
            fe.FailureSignal("pytest", "test_a", "pytest failure: test_a", "x", "2026-07-21"),
            fe.FailureSignal("pytest", "test_b", "pytest failure: test_b", "x", "2026-07-21"),
        ]
        assert len(fe._collapse_repeats(sigs)) == 2


class TestEmit:
    def test_emit_writes_ledger_entry_and_dedupes(self, tmp_path, monkeypatch):
        # Stub FeedbackLogger so we don't write to ~/.cortex/.
        calls = []

        class _StubFL:
            def log_outcome(self, **kwargs):
                calls.append(kwargs)

        monkeypatch.setattr(fe, "_load_ledger", lambda p: set())
        # Replace the import inside emit() by injecting a feedback module.
        import sys
        import types

        mod = types.ModuleType("feedback")
        mod.FeedbackLogger = _StubFL  # type: ignore
        monkeypatch.setitem(sys.modules, "feedback", mod)

        ledger = tmp_path / "ledger.jsonl"
        sigs = [
            fe.FailureSignal(
                source="pytest",
                signal_id="tests/test_a.py::test_one",
                title="t",
                detail="d",
                observed_at=datetime.now(timezone.utc).isoformat(),
            )
        ]

        n1 = fe.emit(sigs, ledger_path=ledger)
        assert n1 == 1
        assert len(calls) == 1
        assert calls[0]["outcome"] == "failed"
        # Ledger was written
        lines = ledger.read_text().strip().splitlines()
        assert len(lines) == 1

        # Second emit with same ledger state — should dedupe.
        # Restore real ledger loader to read what we just wrote.
        monkeypatch.setattr(
            fe,
            "_load_ledger",
            fe._load_ledger.__wrapped__
            if hasattr(fe._load_ledger, "__wrapped__")
            else fe._load_ledger,
        )
        # Re-read seen set the real way.
        seen = set()
        for line in lines:
            seen.add(json.loads(line)["id"])
        # Patch _load_ledger to return the seen set
        monkeypatch.setattr(fe, "_load_ledger", lambda p: seen)
        n2 = fe.emit(sigs, ledger_path=ledger)
        assert n2 == 0
        assert len(calls) == 1  # no new emissions


class TestSignalDataclass:
    def test_recommendation_id_is_stable(self):
        s = fe.FailureSignal(
            source="pytest", signal_id="x::y", title="t", detail="", observed_at=""
        )
        assert s.recommendation_id() == "failure:pytest:x::y"
        # Stable across constructions
        s2 = fe.FailureSignal(
            source="pytest", signal_id="x::y", title="other", detail="other", observed_at="z"
        )
        assert s.recommendation_id() == s2.recommendation_id()
