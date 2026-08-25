"""The briefing must not assert a metric it did not measure.

This is the surface that fires at every session start, so it shapes sessions
whether or not anyone asked it a question. It spent a month reporting "No
commits in analysis period" against a live workspace because a failed lookup and
a measured zero were the same value by the time the threshold saw them.

The distinction these tests pin: a MEASURED zero still alerts (that is real
signal), an UNAVAILABLE metric alerts about instrumentation instead (never about
the world).
"""

from __future__ import annotations

import pytest

from metric_result import mark_unavailable
from recommendations import PortfolioRecommender


class _FakePortfolio:
    """Stands in for PortfolioMemory with a caller-supplied summary."""

    def __init__(self, summary):
        self._summary = summary

    def get_portfolio_health_summary(self, days: int = 7):
        return self._summary


@pytest.fixture()
def recommender(monkeypatch, tmp_path):
    def _build(summary):
        r = PortfolioRecommender(dev_path=tmp_path)
        r.portfolio = _FakePortfolio(summary)
        # Dependency health is a separate producer; hold it constant.
        monkeypatch.setattr(r, "_get_dependency_health", lambda project: None)
        # GOALS.md parsing is unrelated to health honesty.
        monkeypatch.setattr(r, "_parse_goals", lambda: {"high": [], "medium": [], "completed": []})
        return r

    return _build


def _types(alerts):
    return [a["type"] for a in alerts]


def test_measured_zero_commits_still_alerts(recommender):
    """A real zero is signal and must survive the fix."""
    r = recommender({"overall": {"score": 80, "commits": 0, "uncommitted": 2}, "projects": {"a": {}}})
    alerts = r.get_risk_alerts()
    assert "activity" in _types(alerts)
    assert "instrumentation" not in _types(alerts)


def test_unavailable_commits_does_not_alert_about_activity(recommender):
    """The month-long false alert. Absent != zero."""
    overall = mark_unavailable({"score": 80, "commits": 0, "uncommitted": 2}, "commits", "git unreadable")
    r = recommender({"overall": overall, "projects": {"a": {}}})
    alerts = r.get_risk_alerts()
    assert "activity" not in _types(alerts)
    assert "instrumentation" in _types(alerts)
    msg = next(a["message"] for a in alerts if a["type"] == "instrumentation")
    assert "commits" in msg and "git unreadable" in msg


def test_unavailable_score_does_not_claim_critical_health(recommender):
    """The old `else 0` on an empty score produced 'health is critical: 0/100'
    about repos that were merely quiet."""
    overall = mark_unavailable({"commits": 5, "uncommitted": 1}, "score", "no active repo to score")
    r = recommender({"overall": overall, "projects": {"a": {}}})
    alerts = r.get_risk_alerts()
    assert "health" not in _types(alerts)
    assert "instrumentation" in _types(alerts)


def test_unavailable_score_does_not_get_optimistic_pass(recommender):
    """`.get("score", 100)` failed the other way: a missing score silently
    suppressed the alert with no trace. Now it is reported."""
    overall = mark_unavailable({"commits": 5, "uncommitted": 1}, "score", "unreadable")
    r = recommender({"overall": overall, "projects": {"a": {}}})
    assert any(a["type"] == "instrumentation" for a in r.get_risk_alerts())


def test_measured_low_score_still_alerts(recommender):
    r = recommender({"overall": {"score": 30, "commits": 5, "uncommitted": 1}, "projects": {"a": {}}})
    alerts = r.get_risk_alerts()
    assert "health" in _types(alerts)
    assert "30/100" in next(a["message"] for a in alerts if a["type"] == "health")


def test_total_outage_reports_instrumentation_only(recommender):
    """get_portfolio_health_summary returns {"error"} when nothing measured."""
    r = recommender({"error": "No project health could be measured (no repos resolved)"})
    alerts = r.get_risk_alerts()
    assert _types(alerts) == ["instrumentation"]
