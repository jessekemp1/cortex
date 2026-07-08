"""Learning metrics split human-confirmed from auto-confirmed outcomes.

The old headline (95%+ "success rate") counted implicit-approval entries the
system wrote about itself. Quality claims must come from human-confirmed
outcomes only; auto-confirmed volume is throughput.
"""

from __future__ import annotations

import pytest

from feedback import FeedbackLogger, OutcomeEntry
from learning import LearningSystem


@pytest.fixture()
def system(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    logger = FeedbackLogger(
        log_file=tmp_path / "feedback.json", outcomes_file=tmp_path / "outcomes.jsonl"
    )
    ls = LearningSystem()
    ls.feedback_logger = logger
    return logger, ls


def _log(logger, rec_id, rec_type, outcome, source):
    logger.log_outcome(
        recommendation_id=rec_id,
        recommendation_title=rec_id,
        recommendation_type=rec_type,
        priority="B",
        confidence=0.9,
        followed=True,
        outcome=outcome,
        source=source,
    )


def test_split_counts_and_human_rate(system):
    logger, ls = system
    _log(logger, "r1", "next_action", "success", "human")
    _log(logger, "r2", "next_action", "failed", "human")
    _log(logger, "r3", "implicit_approval", "success", "auto")
    _log(logger, "r4", "implicit_approval", "success", "auto")
    _log(logger, "r5", "failure:pytest", "failed", "auto")

    m = ls.get_learning_metrics()
    assert m.total_outcomes == 5
    assert m.human_confirmed == 2
    assert m.auto_confirmed == 3
    assert m.human_success_rate == pytest.approx(0.5)  # 1 of 2 human succeeded
    # The all-outcome rate is diluted by auto successes — that's why it's
    # not the headline anymore.
    assert m.success_rate == pytest.approx(3 / 5)


def _legacy(rec_id, rec_type):
    """A pre-source record as the loader yields it (source='' = unknown)."""
    return OutcomeEntry(
        timestamp="2026-01-01T00:00:00",
        recommendation_id=rec_id,
        recommendation_title=rec_id,
        recommendation_type=rec_type,
        priority="B",
        confidence=0.9,
        followed=True,
        outcome="success",
        source="",
    )


def test_legacy_records_classified_by_machine_markers():
    # The real store is dominated by git-activity automation.
    assert LearningSystem.outcome_source(_legacy("git_abc123", "feature_implementation")) == "auto"
    assert LearningSystem.outcome_source(_legacy("commit_abc", "bug_fix")) == "auto"
    assert LearningSystem.outcome_source(_legacy("implicit_x", "implicit_approval")) == "auto"
    assert LearningSystem.outcome_source(_legacy("sig_1", "failure:pytest")) == "auto"
    # Genuinely human-shaped legacy feedback stays human.
    assert LearningSystem.outcome_source(_legacy("next_1", "next_action")) == "human"


def test_loader_marks_legacy_source_unknown(system, tmp_path):
    logger, ls = system
    # A raw legacy line without the source key...
    import json

    (tmp_path / "outcomes.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00",
                "recommendation_id": "git_deadbeef",
                "recommendation_title": "t",
                "recommendation_type": "feature_implementation",
                "priority": "B",
                "confidence": 0.9,
                "followed": True,
                "outcome": "success",
            }
        )
        + "\n"
    )
    (entry,) = logger.load_outcomes()
    assert entry.source == ""  # not laundered into "human"
    assert LearningSystem.outcome_source(entry) == "auto"
