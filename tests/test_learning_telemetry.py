"""Tests for intelligence.learning_telemetry."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


# Ensure the cortex root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.learning_telemetry import LearningTelemetry, PipelineRun, StageEvent


class TestRecordStage:
    """Test that record_stage writes valid JSONL."""

    def test_record_stage_writes_jsonl(self, tmp_path):
        log_path = tmp_path / "pipeline" / "stage_log.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        event = StageEvent(
            run_id="abc123",
            name="capture",
            status="complete",
            started_at=datetime.now().isoformat(),
            items_in=10,
            items_out=10,
            duration_s=0.5,
        )
        telemetry.record_stage(event)

        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["run_id"] == "abc123"
        assert data["name"] == "capture"
        assert data["status"] == "complete"
        assert data["items_in"] == 10
        assert data["items_out"] == 10
        assert data["duration_s"] == 0.5

    def test_record_stage_appends(self, tmp_path):
        log_path = tmp_path / "stage_log.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        for i in range(3):
            telemetry.record_stage(StageEvent(run_id="run1", name=f"stage{i}", status="complete"))

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 3


class TestGetRecentRuns:
    """Test grouping stage events into pipeline runs."""

    def test_get_recent_runs_groups_by_run_id(self, tmp_path):
        log_path = tmp_path / "stage_log.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        now = datetime.now().isoformat()

        # Two runs, each with two stages
        for name in ["capture", "extract"]:
            telemetry.record_stage(
                StageEvent(
                    run_id="run_a",
                    name=name,
                    status="complete",
                    started_at=now,
                    items_in=5,
                    items_out=3,
                )
            )
        for name in ["capture", "extract"]:
            telemetry.record_stage(
                StageEvent(
                    run_id="run_b",
                    name=name,
                    status="complete",
                    started_at=now,
                    items_in=8,
                    items_out=6,
                )
            )

        runs = telemetry.get_recent_runs(limit=10)
        assert len(runs) == 2
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run_a", "run_b"}

        # Each run should have 2 stages
        for run in runs:
            assert len(run.stages) == 2

    def test_get_recent_runs_respects_limit(self, tmp_path):
        log_path = tmp_path / "stage_log.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        now = datetime.now().isoformat()
        for i in range(10):
            telemetry.record_stage(
                StageEvent(run_id=f"run_{i}", name="capture", status="complete", started_at=now)
            )

        runs = telemetry.get_recent_runs(limit=3)
        assert len(runs) == 3

    def test_empty_log_returns_empty(self, tmp_path):
        log_path = tmp_path / "nonexistent.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        runs = telemetry.get_recent_runs()
        assert runs == []


class TestFormatPipelineAscii:
    """Test ASCII visualization rendering."""

    def test_format_pipeline_ascii_renders_stages(self, tmp_path):
        log_path = tmp_path / "stage_log.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        now = datetime.now().isoformat()
        stages = [
            StageEvent(
                run_id="r1",
                name="capture",
                status="complete",
                started_at=now,
                items_in=12,
                items_out=12,
                duration_s=0.3,
            ),
            StageEvent(
                run_id="r1",
                name="extract",
                status="complete",
                started_at=now,
                items_in=12,
                items_out=8,
                duration_s=1.2,
            ),
            StageEvent(
                run_id="r1",
                name="store",
                status="complete",
                started_at=now,
                items_in=8,
                items_out=8,
                duration_s=0.1,
            ),
            StageEvent(
                run_id="r1",
                name="index",
                status="complete",
                started_at=now,
                items_in=8,
                items_out=8,
                duration_s=0.2,
            ),
        ]

        run = PipelineRun(run_id="r1", stages=stages, started_at=now, total_items=12)
        output = telemetry.format_pipeline_ascii([run])

        assert "LEARNING PIPELINE" in output
        assert "CAPTURE" in output
        assert "EXTRACT" in output
        assert "STORE" in output
        assert "INDEX" in output
        assert "12 interactions processed" in output

    def test_empty_log_shows_helpful_message(self, tmp_path):
        telemetry = LearningTelemetry(log_path=tmp_path / "empty.jsonl")
        output = telemetry.format_pipeline_ascii([])

        assert "No pipeline runs recorded" in output

    def test_failed_stage_shows_marker(self, tmp_path):
        telemetry = LearningTelemetry(log_path=tmp_path / "x.jsonl")
        now = datetime.now().isoformat()

        stages = [
            StageEvent(run_id="r2", name="capture", status="complete", started_at=now),
            StageEvent(run_id="r2", name="extract", status="failed", started_at=now),
        ]
        run = PipelineRun(run_id="r2", stages=stages, started_at=now, total_items=5)
        output = telemetry.format_pipeline_ascii([run])

        assert "EXTRACT!" in output


class TestPipelineFlagIntegration:
    """Test CLI integration with --pipeline flag."""

    def test_pipeline_flag_integration(self, tmp_path, capsys):
        """Simulate what cmd_learn does when --pipeline is set."""
        log_path = tmp_path / "stage_log.jsonl"
        telemetry = LearningTelemetry(log_path=log_path)

        now = datetime.now().isoformat()
        telemetry.record_stage(
            StageEvent(
                run_id="test_run",
                name="capture",
                status="complete",
                started_at=now,
                items_in=5,
                items_out=5,
                duration_s=0.2,
            )
        )

        # Simulate the cmd_learn --pipeline path
        runs = telemetry.get_recent_runs(limit=5)
        output = telemetry.format_pipeline_ascii(runs)
        print(output)

        captured = capsys.readouterr()
        assert "LEARNING PIPELINE" in captured.out
        assert "CAPTURE" in captured.out
        assert "test_run" in captured.out


class TestPipelineRunAgeLabel:
    """Test age label formatting."""

    def test_seconds_ago(self):
        run = PipelineRun(
            run_id="x",
            started_at=(datetime.now() - timedelta(seconds=30)).isoformat(),
        )
        assert "s ago" in run.age_label

    def test_minutes_ago(self):
        run = PipelineRun(
            run_id="x",
            started_at=(datetime.now() - timedelta(minutes=5)).isoformat(),
        )
        assert "m ago" in run.age_label

    def test_no_started_at(self):
        run = PipelineRun(run_id="x")
        assert run.age_label == "unknown"
