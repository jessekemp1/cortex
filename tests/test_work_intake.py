"""Tests for WorkIntake — multi-source work item discovery."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from supervisor.intake import WorkIntake
from supervisor.models import WorkItem, WorkItemPriority


@pytest.fixture
def intake():
    return WorkIntake()


@pytest.fixture
def sample_goals(tmp_path):
    goals = tmp_path / "GOALS.md"
    goals.write_text("""\
# Strategic Goals

## Immediate Actions (Week: Mar 8-14)

- [ ] Fix ECMWF naming bug in emos_auto_fit.py
- [ ] Wire ICON downloader into scheduler
- [ ] Run HRRR hindcast pairs (39K threshold crossed)

## Backlog

### High Priority (Next 2 weeks)
1. Cortex OSS Launch — CONTRIBUTING.md, CI, Zenodo
2. Pupil batch retrieval — check stale Feb 26 batches
""")
    return goals


@pytest.fixture
def sample_taskboard(tmp_path):
    tb = tmp_path / "taskboard.json"
    tb.write_text(
        json.dumps(
            [
                {
                    "id": "t1",
                    "title": "Fix ECMWF naming",
                    "status": "todo",
                    "project": "vortex",
                    "priority": "high",
                },
                {
                    "id": "t2",
                    "title": "Run HRRR refit",
                    "status": "in_progress",
                    "project": "vortex",
                    "priority": "medium",
                },
                {
                    "id": "t3",
                    "title": "Deploy Cortex OSS",
                    "status": "done",
                    "project": "cortex",
                    "priority": "high",
                },
            ]
        )
    )
    return tb


class TestFromCLI:
    def test_creates_work_item(self, intake):
        wi = intake.from_cli("Fix the ECMWF naming bug", project="vortex", priority="high")
        assert isinstance(wi, WorkItem)
        assert wi.description == "Fix the ECMWF naming bug"
        assert wi.project == "vortex"
        assert wi.priority == WorkItemPriority.HIGH
        assert wi.source == "cli"

    def test_default_priority_is_medium(self, intake):
        wi = intake.from_cli("Some task")
        assert wi.priority == WorkItemPriority.MEDIUM

    def test_infers_task_type_fix(self, intake):
        wi = intake.from_cli("Fix the broken ECMWF naming bug")
        assert wi.task_type == "fix"

    def test_infers_task_type_test(self, intake):
        wi = intake.from_cli("Write tests for the new module")
        assert wi.task_type == "test"

    def test_infers_task_type_research(self, intake):
        wi = intake.from_cli("Research Copernicus API options")
        assert wi.task_type == "research"

    def test_infers_task_type_feature(self, intake):
        wi = intake.from_cli("Build the boat simulator")
        assert wi.task_type == "feature"

    def test_infers_task_type_deploy(self, intake):
        wi = intake.from_cli("Deploy Cortex to production")
        assert wi.task_type == "deploy"

    def test_unique_id_generated(self, intake):
        wi1 = intake.from_cli("Task 1")
        wi2 = intake.from_cli("Task 2")
        assert wi1.id != wi2.id

    def test_created_at_is_recent(self, intake):
        wi = intake.from_cli("Test task")
        assert (datetime.now() - wi.created_at).total_seconds() < 5


class TestFromGoals:
    def test_parses_immediate_actions(self, intake, sample_goals):
        items = intake.from_goals(sample_goals)
        assert len(items) >= 3
        descriptions = [wi.description for wi in items]
        assert any("ECMWF" in d for d in descriptions)
        assert any("ICON" in d for d in descriptions)
        assert any("HRRR" in d for d in descriptions)

    def test_items_have_goals_source(self, intake, sample_goals):
        items = intake.from_goals(sample_goals)
        assert all(wi.source == "goals" for wi in items)

    def test_items_have_priority(self, intake, sample_goals):
        items = intake.from_goals(sample_goals)
        assert all(isinstance(wi.priority, WorkItemPriority) for wi in items)

    def test_empty_goals_returns_empty(self, intake, tmp_path):
        empty = tmp_path / "GOALS.md"
        empty.write_text("# Goals\n\nNothing here.\n")
        items = intake.from_goals(empty)
        assert items == []

    def test_missing_file_returns_empty(self, intake, tmp_path):
        missing = tmp_path / "GOALS.md"
        items = intake.from_goals(missing)
        assert items == []


class TestFromTaskboard:
    def test_filters_completed(self, intake, sample_taskboard, monkeypatch):
        import supervisor.intake as intake_mod

        monkeypatch.setattr(intake_mod, "_TASKBOARD_PATH", sample_taskboard)
        items = intake.from_taskboard()
        # t3 has status "done" — should be excluded
        assert len(items) == 2

    def test_preserves_project(self, intake, sample_taskboard, monkeypatch):
        import supervisor.intake as intake_mod

        monkeypatch.setattr(intake_mod, "_TASKBOARD_PATH", sample_taskboard)
        items = intake.from_taskboard()
        assert all(wi.project is not None for wi in items)

    def test_maps_priority(self, intake, sample_taskboard, monkeypatch):
        import supervisor.intake as intake_mod

        monkeypatch.setattr(intake_mod, "_TASKBOARD_PATH", sample_taskboard)
        items = intake.from_taskboard()
        high_items = [wi for wi in items if wi.priority == WorkItemPriority.HIGH]
        assert len(high_items) >= 1

    def test_missing_taskboard_returns_empty(self, intake, tmp_path, monkeypatch):
        import supervisor.intake as intake_mod

        monkeypatch.setattr(intake_mod, "_TASKBOARD_PATH", tmp_path / "nonexistent.json")
        items = intake.from_taskboard()
        assert items == []


class TestDiscoverAll:
    def test_combines_sources(self, intake, sample_goals, sample_taskboard, monkeypatch):
        import supervisor.intake as intake_mod

        monkeypatch.setattr(intake_mod, "_TASKBOARD_PATH", sample_taskboard)
        items = intake.discover_all(goals_path=sample_goals)
        sources = {wi.source for wi in items}
        assert "goals" in sources
        assert "taskboard" in sources

    def test_sorted_by_priority_score(self, intake, sample_goals, sample_taskboard, monkeypatch):
        import supervisor.intake as intake_mod

        monkeypatch.setattr(intake_mod, "_TASKBOARD_PATH", sample_taskboard)
        items = intake.discover_all(goals_path=sample_goals)
        if len(items) >= 2:
            scores = [wi.priority_score for wi in items]
            assert scores == sorted(scores, reverse=True)
