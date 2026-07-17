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
