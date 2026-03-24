"""Tests for command metrics tracking."""

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    from intelligence.storage.consolidated_store import (
        ConsolidatedOutcomeStore,
        set_consolidated_store,
    )

    s = ConsolidatedOutcomeStore(db_path=tmp_path / "test.db")
    set_consolidated_store(s)
    return s


class TestTrackCommandDecorator:
    def test_tracks_successful_command(self, store):
        from intelligence.command_metrics import track_command

        @track_command("test_cmd")
        def my_command():
            return 42

        result = my_command()
        assert result == 42

        metrics = store.load_command_metrics(days=1)
        assert len(metrics) == 1
        assert metrics[0]["command"] == "test_cmd"
        assert metrics[0]["success"] == 1

    def test_tracks_failed_command(self, store):
        from intelligence.command_metrics import track_command

        @track_command("failing_cmd")
        def bad_command():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            bad_command()

        metrics = store.load_command_metrics(days=1)
        assert len(metrics) == 1
        assert metrics[0]["command"] == "failing_cmd"
        assert metrics[0]["success"] == 0
        assert "boom" in metrics[0]["error_message"]

    def test_auto_detects_name(self, store):
        from intelligence.command_metrics import track_command

        @track_command()
        def cmd_status():
            pass

        cmd_status()

        metrics = store.load_command_metrics(days=1)
        assert metrics[0]["command"] == "status"

    def test_measures_duration(self, store):
        import time

        from intelligence.command_metrics import track_command

        @track_command("slow_cmd")
        def slow():
            time.sleep(0.05)

        slow()

        metrics = store.load_command_metrics(days=1)
        assert metrics[0]["duration_ms"] >= 40  # At least 40ms
