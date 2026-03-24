"""Tests for the Consolidated Outcome Store."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Create a ConsolidatedOutcomeStore with temp path."""
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

    return ConsolidatedOutcomeStore(db_path=tmp_path / "test_outcomes.db")


class TestConsolidatedStoreInit:
    def test_creates_database(self, store, tmp_path):
        assert (tmp_path / "test_outcomes.db").exists()

    def test_schema_version_recorded(self, store):
        with sqlite3.connect(store.db_path) as conn:
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()[0]
            assert version == 2

    def test_all_tables_created(self, store):
        with sqlite3.connect(store.db_path) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        expected = [
            "recommendation_outcomes",
            "model_outcomes",
            "workflow_outcomes",
            "session_outcomes",
            "implicit_signals",
            "command_metrics",
            "feedback_entries",
            "schema_version",
        ]
        for table in expected:
            assert table in tables, f"Missing table: {table}"


class TestRecommendationOutcomes:
    def test_log_and_load(self, store):
        row_id = store.log_recommendation_outcome(
            recommendation_id="rec_001",
            recommendation_title="Fix auth bug",
            recommendation_type="bug_fix",
            priority="A",
            confidence=0.85,
            followed=True,
            outcome="success",
            notes="Worked great",
            context={"project": "cortex"},
        )
        assert row_id > 0

        outcomes = store.load_recommendation_outcomes(days=1)
        assert len(outcomes) == 1
        assert outcomes[0]["recommendation_id"] == "rec_001"
        assert outcomes[0]["outcome"] == "success"
        assert outcomes[0]["followed"] == 1

    def test_filter_by_type(self, store):
        store.log_recommendation_outcome(
            recommendation_id="r1",
            recommendation_title="T1",
            recommendation_type="bug_fix",
            priority="A",
            confidence=0.8,
            followed=True,
            outcome="success",
        )
        store.log_recommendation_outcome(
            recommendation_id="r2",
            recommendation_title="T2",
            recommendation_type="feature",
            priority="B",
            confidence=0.6,
            followed=False,
            outcome="pending",
        )

        bug_fixes = store.load_recommendation_outcomes(
            days=1, recommendation_type="bug_fix"
        )
        assert len(bug_fixes) == 1
        assert bug_fixes[0]["recommendation_type"] == "bug_fix"


class TestModelOutcomes:
    def test_log_and_load(self, store):
        row_id = store.log_model_outcome(
            task_id="task_001",
            task_type="implementation",
            task_description="Build user auth",
            model_used="sonnet",
            outcome="success",
            tokens_used=2500,
            time_seconds=180,
        )
        assert row_id > 0

        outcomes = store.load_model_outcomes(days=1)
        assert len(outcomes) == 1
        assert outcomes[0]["model_used"] == "sonnet"
        assert outcomes[0]["tokens_used"] == 2500

    def test_filter_by_task_type(self, store):
        store.log_model_outcome(
            task_id="t1",
            task_type="bug_fix",
            task_description="Fix it",
            model_used="sonnet",
            outcome="success",
        )
        store.log_model_outcome(
            task_id="t2",
            task_type="research",
            task_description="Find it",
            model_used="haiku",
            outcome="success",
        )

        bug_fixes = store.load_model_outcomes(days=1, task_type="bug_fix")
        assert len(bug_fixes) == 1


class TestCommandMetrics:
    def test_log_and_load(self, store):
        row_id = store.log_command_metric(
            command="next",
            duration_ms=1234.5,
            success=True,
            tokens_used=500,
        )
        assert row_id > 0

        metrics = store.load_command_metrics(days=1)
        assert len(metrics) == 1
        assert metrics[0]["command"] == "next"
        assert metrics[0]["duration_ms"] == 1234.5

    def test_log_failure(self, store):
        store.log_command_metric(
            command="deep",
            duration_ms=500.0,
            success=False,
            error_message="Module not found",
        )

        metrics = store.load_command_metrics(days=1, command="deep")
        assert len(metrics) == 1
        assert metrics[0]["success"] == 0
        assert metrics[0]["error_message"] == "Module not found"

    def test_get_command_stats(self, store):
        for _ in range(3):
            store.log_command_metric(command="next", duration_ms=100, success=True)
        store.log_command_metric(command="next", duration_ms=200, success=False)
        store.log_command_metric(command="status", duration_ms=50, success=True)

        stats = store.get_command_stats(days=1)
        assert "next" in stats
        assert stats["next"]["total"] == 4
        assert stats["next"]["successes"] == 3
        assert "status" in stats
        assert stats["status"]["total"] == 1


class TestImplicitSignals:
    def test_log_signal(self, store):
        row_id = store.log_implicit_signal(
            recommendation_id="rec_001",
            signal_type="followed",
            similarity=0.85,
            time_to_action=12.5,
        )
        assert row_id > 0


class TestFeedbackEntries:
    def test_log_and_stats(self, store):
        store.log_feedback(action_title="Fix bug", useful=True)
        store.log_feedback(action_title="Add test", useful=True)
        store.log_feedback(action_title="Refactor", useful=False)

        stats = store.get_feedback_stats()
        assert stats["total_entries"] == 3
        assert stats["useful_count"] == 2
        assert stats["not_useful_count"] == 1
        assert abs(stats["useful_rate"] - 2 / 3) < 0.01


class TestStorageInfo:
    def test_get_info(self, store):
        store.log_command_metric(command="test", duration_ms=1, success=True)

        info = store.get_storage_info()
        assert info["backend"] == "sqlite"
        assert info["schema_version"] == 2
        assert info["tables"]["command_metrics"] == 1


class TestLegacyMigration:
    def test_migrate_feedback_json(self, store, tmp_path, monkeypatch):
        # Create legacy feedback.json
        cortex_dir = tmp_path
        feedback_file = cortex_dir / "feedback.json"
        feedback_data = [
            {
                "timestamp": "2024-01-01T00:00:00",
                "action_id": "a1",
                "action_title": "Fix bug",
                "useful": True,
                "notes": "Worked",
            },
            {
                "timestamp": "2024-01-02T00:00:00",
                "action_id": "a2",
                "action_title": "Add test",
                "useful": False,
            },
        ]
        with open(feedback_file, "w") as f:
            json.dump(feedback_data, f)

        monkeypatch.setenv("CORTEX_STATE_DIR", str(cortex_dir))
        counts = store.migrate_legacy_data()
        assert counts.get("feedback", 0) == 2

    def test_migrate_outcomes_jsonl(self, store, tmp_path, monkeypatch):
        cortex_dir = tmp_path
        outcomes_file = cortex_dir / "outcomes.jsonl"
        entries = [
            {
                "recommendation_id": "r1",
                "recommendation_title": "Fix it",
                "recommendation_type": "bug_fix",
                "priority": "A",
                "confidence": 0.8,
                "followed": True,
                "outcome": "success",
            }
        ]
        with open(outcomes_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        monkeypatch.setenv("CORTEX_STATE_DIR", str(cortex_dir))
        counts = store.migrate_legacy_data()
        assert counts.get("recommendation_outcomes", 0) == 1
