"""A missing measurement must not be readable as a value."""

from __future__ import annotations

import pytest

from metric_result import (
    Measured,
    MetricUnavailable,
    Unavailable,
    is_available,
    mark_unavailable,
    require,
    unavailable_reasons,
    unwrap_or_report,
)


def test_unavailable_has_no_value_attribute():
    """The core guarantee: forgetting to branch raises, it does not render 0."""
    u = Unavailable("git failed")
    assert getattr(u, "value", "MISSING") == "MISSING"
    with pytest.raises(AttributeError):
        _ = u.value  # type: ignore[attr-defined]


def test_measured_carries_provenance():
    m = Measured(14, source="git:/repo")
    assert m.available is True
    assert m.value == 14
    assert m.source == "git:/repo"
    assert m.measured_at


def test_unwrap_or_report_distinguishes_the_two():
    assert unwrap_or_report(Measured(0)) == (0, None)
    assert unwrap_or_report(Unavailable("no repo")) == (None, "no repo")


def test_measured_zero_is_not_unavailable():
    """A real zero is a measurement. Conflating the two caused the false
    'No commits in analysis period' alert."""
    value, reason = unwrap_or_report(Measured(0))
    assert value == 0 and reason is None


def test_require_returns_measured_value_including_zero():
    assert require({"commits": 0}, "commits") == 0


def test_require_raises_on_missing_metric():
    with pytest.raises(MetricUnavailable):
        require({}, "commits")


def test_require_raises_on_metric_marked_unavailable():
    d = mark_unavailable({"commits": 99}, "commits", "git timed out")
    with pytest.raises(MetricUnavailable) as e:
        require(d, "commits")
    assert "git timed out" in str(e.value)


def test_mark_unavailable_drops_the_stale_value():
    """Leaving the old number beside the note is how stale data keeps shipping."""
    d = mark_unavailable({"commits": 99}, "commits", "unreadable")
    assert "commits" not in d
    assert unavailable_reasons(d) == {"commits": "unreadable"}


def test_is_available_matrix():
    assert is_available({"score": 41}, "score") is True
    assert is_available({}, "score") is False
    assert is_available(mark_unavailable({"score": 41}, "score", "x"), "score") is False
