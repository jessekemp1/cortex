"""
Tests for the orchestration pipeline wiring (supervisor/pipeline.py).

Tests:
  - run_pipeline() with dry_run returns routing decisions without dispatch
  - run_pipeline() with pre-built work items skips discovery
  - run_pipeline() with project_filter narrows results
  - WorkIntake.from_batch_jobs() scans JSON files
  - PipelineResult serialization
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add cortex directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supervisor.intake import WorkIntake
from supervisor.models import WorkItem, WorkItemPriority
from supervisor.pipeline import PipelineResult, RoutingDecision, run_pipeline


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_work_item(
    description: str = "Fix authentication bug",
    task_type: str = "fix",
    project: str = "cortex",
    priority: WorkItemPriority = WorkItemPriority.MEDIUM,
) -> WorkItem:
    return WorkItem(
        id="wi_test_001",
        source="test",
        task_type=task_type,
        description=description,
        project=project,
        priority=priority,
        confidence=0.8,
    )


@pytest.fixture(autouse=True)
def _patch_slow_operations():
    """Patch operations that hit the filesystem or network."""
    mock_pm = MagicMock()
    mock_pm.alert_generator.generate_alerts.return_value = []

    with patch(
        "supervisor.intake.WorkIntake.from_recommendations_api",
        return_value=[],
    ):
        yield


# ── WorkIntake.from_batch_jobs ────────────────────────────────────────


class TestFromBatchJobs:
    """Tests for batch job scanning."""

    def test_returns_empty_when_no_directory(self, tmp_path: Path):
        """No batch dir -> empty list."""
        intake = WorkIntake()
        items = intake.from_batch_jobs(batch_dir=tmp_path / "nonexistent")
        assert items == []

    def test_scans_pending_json_files(self, tmp_path: Path):
        """Picks up pending jobs from JSON files."""
        job = {
            "id": "batch_001",
            "status": "pending",
            "description": "Run test suite for vortex",
            "command": "pytest Vortex/backend/tests/ -v",
            "project": "vortex",
            "priority": "high",
        }
        (tmp_path / "job1.json").write_text(json.dumps(job))

        intake = WorkIntake()
        items = intake.from_batch_jobs(batch_dir=tmp_path)

        assert len(items) == 1
        assert items[0].id == "batch_001"
        assert items[0].source == "batch"
        assert items[0].task_type == "test"
        assert items[0].command == "pytest Vortex/backend/tests/ -v"
        assert items[0].priority == WorkItemPriority.HIGH

    def test_skips_done_status(self, tmp_path: Path):
        """Done/completed jobs are not picked up."""
        job = {"status": "done", "description": "Already finished"}
        (tmp_path / "done.json").write_text(json.dumps(job))

        intake = WorkIntake()
        items = intake.from_batch_jobs(batch_dir=tmp_path)
        assert items == []

    def test_handles_list_format(self, tmp_path: Path):
        """JSON files can contain a list of jobs."""
        jobs = [
            {"status": "pending", "description": "Task A"},
            {"status": "done", "description": "Task B"},
            {"status": "queued", "description": "Task C"},
        ]
        (tmp_path / "batch.json").write_text(json.dumps(jobs))

        intake = WorkIntake()
        items = intake.from_batch_jobs(batch_dir=tmp_path)
        assert len(items) == 2  # pending + queued, not done

    def test_skips_malformed_json(self, tmp_path: Path):
        """Malformed JSON files are skipped gracefully."""
        (tmp_path / "bad.json").write_text("not valid json {{{")
        intake = WorkIntake()
        items = intake.from_batch_jobs(batch_dir=tmp_path)
        assert items == []

    def test_metadata_includes_batch_file(self, tmp_path: Path):
        """Metadata includes the source batch file name."""
        job = {"status": "pending", "description": "Test task", "extra_field": "value"}
        (tmp_path / "my_batch.json").write_text(json.dumps(job))

        intake = WorkIntake()
        items = intake.from_batch_jobs(batch_dir=tmp_path)
        assert len(items) == 1
        assert items[0].metadata["batch_file"] == "my_batch.json"
        assert items[0].metadata["extra_field"] == "value"


# ── Pipeline: dry run ─────────────────────────────────────────────────


class TestPipelineDryRun:
    """Tests for dry-run mode (routing without dispatch)."""

    def test_dry_run_routes_without_dispatching(self):
        """Dry run should route items but not call dispatch."""
        items = [_make_work_item()]
        result = run_pipeline(work_items=items, dry_run=True)

        assert result.dry_run is True
        assert result.items_discovered == 1
        assert len(result.routing_decisions) == 1
        assert result.items_dispatched == 0
        assert result.items_succeeded == 0
        assert result.items_failed == 0

    def test_dry_run_routing_decision_fields(self):
        """Routing decisions have all expected fields populated."""
        items = [_make_work_item(description="Redesign auth system", task_type="architecture")]
        result = run_pipeline(work_items=items, dry_run=True)

        rd = result.routing_decisions[0]
        assert rd.model_tier in ("opus", "sonnet", "haiku")
        assert rd.model_id  # non-empty
        assert rd.complexity_score >= 0.0
        assert rd.confidence >= 0.0
        assert rd.reasoning  # non-empty

    def test_dry_run_architecture_routes_to_opus(self):
        """Architecture tasks should route to opus (highest complexity)."""
        items = [
            _make_work_item(
                description="Redesign the entire authentication system",
                task_type="architecture",
                priority=WorkItemPriority.CRITICAL,
            )
        ]
        result = run_pipeline(work_items=items, dry_run=True)

        rd = result.routing_decisions[0]
        assert rd.model_tier == "opus"

    def test_dry_run_classify_routes_to_haiku(self):
        """Classification tasks should route to haiku (lowest complexity)."""
        items = [
            _make_work_item(
                description="Classify this issue",
                task_type="classify",
                priority=WorkItemPriority.LOW,
            )
        ]
        result = run_pipeline(work_items=items, dry_run=True)

        rd = result.routing_decisions[0]
        assert rd.model_tier == "haiku"

    def test_dry_run_multiple_items(self):
        """Multiple items are all routed."""
        items = [
            _make_work_item(description="Fix bug A", task_type="fix"),
            _make_work_item(description="Plan architecture B", task_type="architecture"),
            _make_work_item(description="Classify issue C", task_type="classify"),
        ]
        # Give each a unique ID
        for i, item in enumerate(items):
            item.id = f"wi_test_{i:03d}"

        result = run_pipeline(work_items=items, dry_run=True)
        assert len(result.routing_decisions) == 3


# ── Pipeline: discovery ───────────────────────────────────────────────


class TestPipelineDiscovery:
    """Tests for work discovery integration."""

    def test_empty_discovery_returns_no_work(self, tmp_path: Path):
        """When no sources have work, result shows zero items."""
        # Point intake at empty goals file and empty batch dir
        goals = tmp_path / "GOALS.md"
        goals.write_text("# Goals\nNothing actionable here.")

        with (
            patch.object(WorkIntake, "from_taskboard", return_value=[]),
            patch.object(WorkIntake, "from_workflow_definitions", return_value=[]),
            patch.object(WorkIntake, "from_research_agent", return_value=[]),
        ):
            result = run_pipeline(
                dry_run=True,
                goals_path=goals,
            )

        assert result.items_discovered == 0
        assert result.routing_decisions == []

    def test_project_filter_narrows_results(self):
        """Project filter excludes items from other projects."""
        items = [
            _make_work_item(description="Fix vortex bug", project="vortex"),
            _make_work_item(description="Fix cortex bug", project="cortex"),
        ]
        items[0].id = "wi_vortex"
        items[1].id = "wi_cortex"

        result = run_pipeline(
            work_items=items,
            dry_run=True,
            project_filter="cortex",
        )

        assert result.items_discovered == 1
        assert len(result.routing_decisions) == 1
        assert result.routing_decisions[0].work_item.project == "cortex"


# ── Pipeline: dispatch ────────────────────────────────────────────────


class TestPipelineDispatch:
    """Tests for dispatch execution (mocked API)."""

    def test_dispatch_calls_dispatcher(self):
        """When not dry_run, dispatcher.dispatch() is called."""
        items = [_make_work_item()]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Task completed successfully with code changes"
        mock_result.error = None
        mock_result.work_item_id = "wi_test_001"
        mock_result.model_used = "claude-sonnet-4-6"
        mock_result.tokens_used = 500
        mock_result.duration_seconds = 2.0
        mock_result.task_type = "fix"
        mock_result.checkpoint_id = None

        with (
            patch("supervisor.dispatch.AgentDispatcher") as MockDispatcher,
            patch("supervisor.collector.ResultCollector") as MockCollector,
        ):
            dispatcher_instance = MockDispatcher.return_value
            dispatcher_instance.dispatch.return_value = mock_result

            collector_instance = MockCollector.return_value
            collector_instance.get_summary.return_value = MagicMock(
                succeeded=1, total=1, total_tokens=500
            )

            result = run_pipeline(work_items=items, dry_run=False)

        assert result.items_dispatched == 1
        assert result.items_succeeded == 1
        assert result.items_failed == 0
        dispatcher_instance.dispatch.assert_called_once()

    def test_dispatch_failure_recorded(self):
        """Failed dispatches are counted and errors recorded."""
        items = [_make_work_item()]

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.output = ""
        mock_result.error = "API timeout"
        mock_result.work_item_id = "wi_test_001"
        mock_result.model_used = "claude-sonnet-4-6"
        mock_result.tokens_used = 0
        mock_result.duration_seconds = 30.0
        mock_result.task_type = "fix"
        mock_result.checkpoint_id = None

        with (
            patch("supervisor.dispatch.AgentDispatcher") as MockDispatcher,
            patch("supervisor.collector.ResultCollector") as MockCollector,
        ):
            dispatcher_instance = MockDispatcher.return_value
            dispatcher_instance.dispatch.return_value = mock_result

            collector_instance = MockCollector.return_value
            collector_instance.get_summary.return_value = MagicMock(
                succeeded=0, total=1, total_tokens=0
            )

            result = run_pipeline(work_items=items, dry_run=False)

        assert result.items_failed == 1
        assert any("API timeout" in e for e in result.errors)


# ── PipelineResult serialization ──────────────────────────────────────


class TestPipelineResultSerialization:
    """Tests for PipelineResult.to_dict() and summary()."""

    def test_to_dict_is_json_serializable(self):
        """to_dict() output can be serialized to JSON."""
        items = [_make_work_item()]
        result = run_pipeline(work_items=items, dry_run=True)

        data = result.to_dict()
        json_str = json.dumps(data)  # Should not raise
        parsed = json.loads(json_str)
        assert parsed["items_discovered"] == 1
        assert parsed["dry_run"] is True
        assert len(parsed["routing_decisions"]) == 1

    def test_summary_string(self):
        """summary() returns a human-readable one-liner."""
        result = PipelineResult(
            items_discovered=5,
            routing_decisions=[],
            dry_run=True,
        )
        s = result.summary()
        assert "discovered=5" in s
        assert "dry_run=True" in s

    def test_summary_with_dispatch(self):
        """summary() includes dispatch counts when not dry_run."""
        result = PipelineResult(
            items_discovered=3,
            items_dispatched=2,
            items_succeeded=1,
            items_failed=1,
            dry_run=False,
        )
        s = result.summary()
        assert "dispatched=2" in s
        assert "succeeded=1" in s
        assert "failed=1" in s


# ── Config dry_run flag ───────────────────────────────────────────────


class TestConfigDryRun:
    """Tests that config.dry_run is respected."""

    def test_config_dry_run_overrides(self):
        """SupervisorConfig.dry_run=True forces dry run even without flag."""
        from supervisor.config import SupervisorConfig

        config = SupervisorConfig(dry_run=True)
        items = [_make_work_item()]

        result = run_pipeline(work_items=items, config=config)
        assert result.dry_run is True
        assert result.items_dispatched == 0

    def test_explicit_dry_run_overrides_config(self):
        """dry_run=True parameter overrides config.dry_run=False."""
        from supervisor.config import SupervisorConfig

        config = SupervisorConfig(dry_run=False)
        items = [_make_work_item()]

        result = run_pipeline(work_items=items, dry_run=True, config=config)
        assert result.dry_run is True
        assert result.items_dispatched == 0
