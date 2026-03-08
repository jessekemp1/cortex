"""Tests for WorkIntake — multi-source work item discovery.

Covers: CLI intake, GOALS.md parsing (all priority levels), taskboard
filtering, recommendation mapping, and discover_all aggregation pipeline.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from supervisor.intake import WorkIntake, _infer_task_type, _similarity
from supervisor.models import WorkItem, WorkItemPriority


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def intake(tmp_path):
    """WorkIntake with root_dir pointing to a temp directory."""
    return WorkIntake(root_dir=tmp_path)


@pytest.fixture
def goals_file(tmp_path):
    """Create a realistic GOALS.md in tmp_path."""
    content = """\
# Strategic Goals

## Immediate Actions (Week: Mar 7-14)

1. **Cortex OSS Launch (Goal 5)** — Zenodo DOI + public GitHub repo
2. **Pupil Nowcasting Phase 2 (Goal 8)** — Retrieve batch results, validate hindcast
3. **Vortex V4 Post-Ship Hardening** — Alembic migration, GRIB test xfail

---

## Backlog (Prioritized)

### High Priority (Next 2 months)
1. **Kempion Research Site** — Deploy to Vercel
2. **DJ-CoPilot** — STEM workflow documented

### Medium Priority (Q2 2026)
3. **CNN-LSTM Spatial Nowcaster** — Resume Phase 4B-2
4. **Databricks Optimization** - Data platform improvements

### Low Priority (Backlog)
- AI Project Curator, Keto Tracker, Prompt Playground
- Dataset exploration projects
"""
    goals_path = tmp_path / "GOALS.md"
    goals_path.write_text(content)
    return goals_path


@pytest.fixture
def taskboard_file(tmp_path):
    """Create a taskboard JSON file."""
    tasks = [
        {
            "id": "task_001",
            "title": "Fix broken vortex tests",
            "status": "pending",
            "priority": "high",
            "project": "vortex",
        },
        {
            "id": "task_002",
            "title": "Research new ML models",
            "status": "pending",
            "priority": "medium",
            "project": "cortex",
        },
        {
            "id": "task_003",
            "title": "Deploy frontend updates",
            "status": "done",
            "priority": "high",
            "project": "vortex",
        },
        {
            "id": "task_004",
            "title": "Clean up old scripts",
            "status": "in_progress",
            "priority": "low",
            "project": "",
        },
    ]
    path = tmp_path / "taskboard.json"
    path.write_text(json.dumps(tasks))
    return path


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_root_dir_is_cwd(self):
        wi = WorkIntake()
        assert wi.root_dir == Path.cwd()

    def test_explicit_root_dir(self, tmp_path):
        wi = WorkIntake(root_dir=tmp_path)
        assert wi.root_dir == tmp_path

    def test_env_var_root_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CORTEX_ROOT_DIR", str(tmp_path))
        wi = WorkIntake()
        assert wi.root_dir == tmp_path


# ---------------------------------------------------------------------------
# from_cli tests
# ---------------------------------------------------------------------------


class TestFromCli:
    def test_creates_valid_workitem(self, intake):
        item = intake.from_cli("deploy the new API endpoint")
        assert isinstance(item, WorkItem)
        assert item.source == "cli"
        assert item.description == "deploy the new API endpoint"
        assert item.id.startswith("wi_")
        assert len(item.id) == 15  # "wi_" + 12 hex chars
        assert item.confidence == 0.9

    def test_infers_task_type(self, intake):
        """'run tests' -> task_type='test', etc."""
        assert intake.from_cli("run tests for the backend").task_type == "test"
        assert intake.from_cli("fix the broken endpoint").task_type == "fix"
        assert intake.from_cli("research caching strategies").task_type == "research"
        assert intake.from_cli("refactor the data pipeline").task_type == "refactor"
        assert intake.from_cli("deploy to production").task_type == "deploy"
        assert intake.from_cli("build new feature").task_type == "feature"
        assert intake.from_cli("review the PR").task_type == "review"
        assert intake.from_cli("update documentation").task_type == "docs"
        assert intake.from_cli("do something generic").task_type == "task"

    def test_with_project(self, intake):
        item = intake.from_cli("run tests", project="vortex")
        assert item.project == "vortex"

    def test_infers_project_from_description(self, intake):
        item = intake.from_cli("fix cortex bridge endpoint")
        assert item.project == "cortex"

    def test_unique_ids(self, intake):
        ids = {intake.from_cli(f"task {i}").id for i in range(10)}
        assert len(ids) == 10

    def test_created_at_is_recent(self, intake):
        item = intake.from_cli("test task")
        assert (datetime.now() - item.created_at).total_seconds() < 5


# ---------------------------------------------------------------------------
# from_goals tests
# ---------------------------------------------------------------------------


class TestFromGoals:
    def test_parses_high_priority(self, intake, goals_file):
        """High Priority goals -> WorkItemPriority.HIGH."""
        items = intake.from_goals(goals_file)
        high_items = [i for i in items if i.priority == WorkItemPriority.HIGH]
        # Immediate Actions (3) + High Priority backlog (2) = 5
        assert len(high_items) == 5
        assert all(i.source == "goals" for i in high_items)

    def test_parses_all_priorities(self, intake, goals_file):
        """All 3 priority levels are mapped correctly."""
        items = intake.from_goals(goals_file)
        priorities = {i.priority for i in items}
        assert WorkItemPriority.HIGH in priorities
        assert WorkItemPriority.MEDIUM in priorities
        assert WorkItemPriority.LOW in priorities

    def test_medium_priority_mapped(self, intake, goals_file):
        items = intake.from_goals(goals_file)
        medium_items = [i for i in items if i.priority == WorkItemPriority.MEDIUM]
        assert len(medium_items) == 2
        descriptions = " ".join(i.description for i in medium_items)
        assert "CNN-LSTM" in descriptions or "Databricks" in descriptions

    def test_low_priority_mapped(self, intake, goals_file):
        items = intake.from_goals(goals_file)
        low_items = [i for i in items if i.priority == WorkItemPriority.LOW]
        assert len(low_items) == 2

    def test_missing_file_returns_empty(self, intake, tmp_path):
        """Missing GOALS.md returns empty list, no crash."""
        missing = tmp_path / "nonexistent" / "GOALS.md"
        items = intake.from_goals(missing)
        assert items == []

    def test_default_path_uses_root_dir(self, intake, goals_file):
        """from_goals() with no args uses root_dir/GOALS.md."""
        items = intake.from_goals()
        assert len(items) > 0
        assert all(i.source == "goals" for i in items)

    def test_infers_task_type_from_goal_text(self, intake, goals_file):
        items = intake.from_goals(goals_file)
        # "Kempion Research Site — Deploy to Vercel" matches "research" first
        # because keyword order determines priority
        research_items = [i for i in items if i.task_type == "research"]
        assert len(research_items) >= 1

    def test_infers_project(self, intake, goals_file):
        items = intake.from_goals(goals_file)
        cortex_items = [i for i in items if i.project == "cortex"]
        assert len(cortex_items) >= 1

    def test_empty_goals_file(self, intake, tmp_path):
        empty = tmp_path / "GOALS.md"
        empty.write_text("# Goals\n\nNothing actionable here.\n")
        items = intake.from_goals(empty)
        assert items == []


# ---------------------------------------------------------------------------
# from_taskboard tests
# ---------------------------------------------------------------------------


class TestFromTaskboard:
    def test_filters_status_pending(self, intake, taskboard_file):
        items = intake.from_taskboard(status="pending", taskboard_path=taskboard_file)
        assert len(items) == 2
        ids = {i.id for i in items}
        assert "task_001" in ids
        assert "task_002" in ids
        assert "task_003" not in ids  # done
        assert "task_004" not in ids  # in_progress

    def test_filters_status_in_progress(self, intake, taskboard_file):
        items = intake.from_taskboard(status="in_progress", taskboard_path=taskboard_file)
        assert len(items) == 1
        assert items[0].id == "task_004"

    def test_no_status_filter_returns_all_non_done(self, intake, taskboard_file):
        items = intake.from_taskboard(status="", taskboard_path=taskboard_file)
        assert len(items) == 3  # pending(2) + in_progress(1), excludes done

    def test_missing_file_returns_empty(self, intake, tmp_path):
        """Missing taskboard returns empty list, no crash."""
        items = intake.from_taskboard(taskboard_path=tmp_path / "missing_taskboard.json")
        assert items == []

    def test_priority_mapping(self, intake, taskboard_file):
        items = intake.from_taskboard(status="", taskboard_path=taskboard_file)
        item_map = {i.id: i for i in items}
        assert item_map["task_001"].priority == WorkItemPriority.HIGH
        assert item_map["task_002"].priority == WorkItemPriority.MEDIUM
        assert item_map["task_004"].priority == WorkItemPriority.LOW

    def test_task_type_inferred(self, intake, taskboard_file):
        items = intake.from_taskboard(status="pending", taskboard_path=taskboard_file)
        item_map = {i.id: i for i in items}
        # "Fix broken vortex tests" — "test" keyword matched first
        assert item_map["task_001"].task_type == "test"
        assert item_map["task_002"].task_type == "research"  # "Research new..."

    def test_source_is_taskboard(self, intake, taskboard_file):
        items = intake.from_taskboard(status="pending", taskboard_path=taskboard_file)
        assert all(i.source == "taskboard" for i in items)

    def test_corrupt_json_returns_empty(self, intake, tmp_path):
        bad = tmp_path / "taskboard.json"
        bad.write_text("{broken json!!!")
        items = intake.from_taskboard(taskboard_path=bad)
        assert items == []


# ---------------------------------------------------------------------------
# from_recommendation tests
# ---------------------------------------------------------------------------


class TestFromRecommendation:
    def test_maps_fields(self, intake):
        rec = {
            "id": "rec_42",
            "title": "Add caching to bridge queries",
            "priority": "high",
            "project": "cortex",
            "confidence": 0.85,
        }
        item = intake.from_recommendation(rec)
        assert isinstance(item, WorkItem)
        assert item.source == "recommendation"
        assert item.description == "Add caching to bridge queries"
        assert item.priority == WorkItemPriority.HIGH
        assert item.project == "cortex"
        assert item.confidence == 0.85
        assert item.metadata["recommendation_id"] == "rec_42"
        assert item.task_type == "feature"  # "Add" -> feature

    def test_uses_description_fallback(self, intake):
        rec = {"description": "Investigate memory leak", "priority": "medium"}
        item = intake.from_recommendation(rec)
        assert item.description == "Investigate memory leak"
        assert item.task_type == "research"  # "Investigate" -> research

    def test_defaults(self, intake):
        rec = {"title": "Something generic"}
        item = intake.from_recommendation(rec)
        assert item.priority == WorkItemPriority.MEDIUM
        assert item.confidence == 0.6
        assert item.project == ""


# ---------------------------------------------------------------------------
# discover_all tests
# ---------------------------------------------------------------------------


class TestDiscoverAll:
    def test_combines_sources(self, intake, goals_file, taskboard_file):
        with patch.object(intake, "from_recommendations_api", return_value=[]):
            with patch.object(
                intake,
                "from_taskboard",
                return_value=intake.from_taskboard(status="", taskboard_path=taskboard_file),
            ):
                items = intake.discover_all(goals_path=goals_file)
                sources = {i.source for i in items}
                assert "goals" in sources
                assert "taskboard" in sources
                assert len(items) > 3

    def test_deduplicates(self, intake, tmp_path):
        """Similar descriptions from different sources get merged."""
        goals = tmp_path / "GOALS.md"
        goals.write_text("## Immediate Actions\n1. Fix broken vortex backend tests\n")

        tb = tmp_path / "taskboard.json"
        tb.write_text(
            json.dumps(
                [
                    {
                        "id": "tb_1",
                        "title": "Fix broken vortex backend tests",
                        "status": "pending",
                        "priority": "high",
                    }
                ]
            )
        )

        with patch.object(intake, "from_recommendations_api", return_value=[]):
            with patch.object(
                intake,
                "from_taskboard",
                return_value=intake.from_taskboard(status="", taskboard_path=tb),
            ):
                items = intake.discover_all(goals_path=goals)
                fix_items = [i for i in items if "broken vortex" in i.description.lower()]
                assert len(fix_items) == 1

    def test_sorted_by_priority(self, intake, tmp_path):
        """Items returned in priority_score descending order."""
        goals = tmp_path / "GOALS.md"
        goals.write_text(
            "### High Priority (Next 2 months)\n"
            "1. Important high priority task alpha\n"
            "### Medium Priority (Q2 2026)\n"
            "1. Medium priority task beta\n"
            "### Low Priority (Backlog)\n"
            "- Low priority cleanup task gamma\n"
        )

        with patch.object(intake, "from_recommendations_api", return_value=[]):
            with patch.object(intake, "from_taskboard", return_value=[]):
                items = intake.discover_all(goals_path=goals)
                assert len(items) == 3
                scores = [i.priority_score for i in items]
                assert scores == sorted(scores, reverse=True)
                assert items[0].priority == WorkItemPriority.HIGH
                assert items[1].priority == WorkItemPriority.MEDIUM
                assert items[2].priority == WorkItemPriority.LOW

    def test_includes_recommendations(self, intake, tmp_path):
        """Recommendations are included when available."""
        goals = tmp_path / "GOALS.md"
        goals.write_text("# Goals\nNothing here.\n")

        rec_item = intake.from_recommendation(
            {"title": "Optimize query performance", "priority": "high"}
        )

        with patch.object(intake, "from_recommendations_api", return_value=[rec_item]):
            with patch.object(intake, "from_taskboard", return_value=[]):
                items = intake.discover_all(goals_path=goals)
                assert len(items) == 1
                assert items[0].source == "recommendation"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_infer_task_type_all_keywords(self):
        assert _infer_task_type("run tests for backend") == "test"
        assert _infer_task_type("fix the crash on startup") == "fix"
        assert _infer_task_type("deploy to production") == "deploy"
        assert _infer_task_type("research ML approaches") == "research"
        assert _infer_task_type("refactor data layer") == "refactor"
        assert _infer_task_type("add new endpoint") == "feature"
        assert _infer_task_type("review the PR") == "review"
        assert _infer_task_type("update documentation") == "docs"
        assert _infer_task_type("something generic") == "task"

    def test_similarity_exact(self):
        assert _similarity("fix broken tests", "fix broken tests") == 1.0

    def test_similarity_none(self):
        assert _similarity("fix broken tests", "completely different words") == 0.0

    def test_similarity_empty(self):
        assert _similarity("", "anything") == 0.0

    def test_similarity_partial(self):
        score = _similarity("fix broken backend tests", "fix broken vortex tests")
        assert 0.5 < score < 1.0
