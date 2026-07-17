"""Tests for Workstream B — value receipts (real data only).

Covers the honesty invariants that make `cortex stats` trustworthy:
  * empty state carries NO fabricated numbers in the receipts region
  * rates from n<10 samples render "n=X — too few to rate", never a %
  * rates from n>=10 samples render a real percentage
  * recall instrumentation appends a real event line
  * the surfaced-item counter counts decisions honestly

All state is redirected to a tmp dir via CORTEX_STATE_DIR/CORTEX_HOME so no
test touches the live ~/.cortex.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# Add cortex root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def cortex_home(tmp_path, monkeypatch):
    """Redirect the whole Cortex state store to a tmp dir."""
    state = tmp_path / ".cortex"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CORTEX_STATE_DIR", str(state))
    monkeypatch.setenv("CORTEX_HOME", str(state))
    monkeypatch.setenv("HOME", str(tmp_path))
    return state


# ── format_rate: the n<10 honesty gate ──────────────────────────────────────


def test_format_rate_refuses_below_threshold():
    from cli.commands.stats import MIN_RATE_SAMPLES, format_rate

    for n in range(0, MIN_RATE_SAMPLES):
        out = format_rate(n, n)
        assert out == f"n={n} — too few to rate", out
        # A refused rate must not contain a percent sign.
        assert "%" not in out


def test_format_rate_renders_percentage_at_threshold():
    from cli.commands.stats import MIN_RATE_SAMPLES, format_rate

    # n exactly at threshold → a real rate.
    out = format_rate(5, MIN_RATE_SAMPLES)
    assert "%" in out
    assert f"n={MIN_RATE_SAMPLES}" in out
    # 5/10 → 50%
    assert "50%" in out


# ── empty state: no fabricated numbers in the receipts region ────────────────


def test_empty_state_has_no_fabricated_metrics(cortex_home):
    """Day-1 report: the ONLY digits allowed are the anti-pattern count
    (a real fact in the header) and the 'n >= 10' checklist threshold.
    No receipt digits anywhere."""
    from cli.commands.stats import build_stats_report, render_stats

    report = build_stats_report()
    assert report["empty"] is True

    out = render_stats(report)
    # The checklist markers must be present.
    assert "No receipts yet" in out
    assert "cortex demo" in out
    assert "☐ First decision recorded" in out

    # Collect every integer in the rendered output. The only permitted values
    # are the real anti-pattern count and the checklist's "n >= 10" threshold.
    nums = {int(n) for n in re.findall(r"\d+", out)}
    permitted = {report["anti_patterns_active"], 10}
    fabricated = nums - permitted
    assert not fabricated, f"empty state leaked fabricated numbers: {fabricated}\n{out}"


def test_empty_state_anti_pattern_count_is_real(cortex_home):
    """The header count must equal the runtime seed count (not hardcoded)."""
    from intelligence.memory.seed_patterns import get_seed_patterns
    from cli.commands.stats import build_stats_report

    report = build_stats_report()
    assert report["anti_patterns_active"] == len(get_seed_patterns())


# ── populated state: real counts + gated follow-rate ─────────────────────────


def _seed_decisions(state: Path, n: int) -> None:
    import mcp_handlers

    for i in range(n):
        mcp_handlers.record_learning_decision(
            decision=f"decision {i}", context=f"ctx {i}", project="cortex"
        )


def _seed_feedback(state: Path, follows: int, ignores: int) -> None:
    from datetime import datetime

    from intelligence.feedback.implicit_collector import (
        ImplicitFeedbackCollector,
        ImplicitSignal,
    )

    collector = ImplicitFeedbackCollector(storage_path=state / "implicit_feedback.jsonl")
    for i in range(follows):
        collector._persist_signal(
            ImplicitSignal(
                timestamp=datetime.now().isoformat(),
                recommendation_id=f"f{i}",
                signal_type="followed",
                similarity=0.9,
            )
        )
    for i in range(ignores):
        collector._persist_signal(
            ImplicitSignal(
                timestamp=datetime.now().isoformat(),
                recommendation_id=f"i{i}",
                signal_type="ignored",
                similarity=0.0,
            )
        )


def test_populated_report_shows_real_decision_counts(cortex_home):
    from cli.commands.stats import build_stats_report

    _seed_decisions(cortex_home, 3)
    report = build_stats_report()
    assert report["empty"] is False
    assert report["decisions"]["total"] == 3
    assert report["decisions"]["recent_7d"] == 3


def test_follow_rate_gated_below_ten_samples(cortex_home):
    """6 signals (< 10) → follow-rate is refused, not a percentage."""
    from cli.commands.stats import build_stats_report, render_stats

    _seed_feedback(cortex_home, follows=3, ignores=3)
    report = build_stats_report()
    out = render_stats(report)

    m = re.search(r"Follow-rate\s*:\s*(.+)", out)
    assert m, out
    assert m.group(1).strip() == "n=6 — too few to rate"


def test_follow_rate_computed_at_ten_samples(cortex_home):
    """12 signals (>= 10) → a real percentage is shown."""
    from cli.commands.stats import build_stats_report, render_stats

    _seed_feedback(cortex_home, follows=6, ignores=6)
    report = build_stats_report()
    out = render_stats(report)

    m = re.search(r"Follow-rate\s*:\s*(.+)", out)
    assert m, out
    line = m.group(1).strip()
    assert "%" in line
    assert "n=12" in line
    assert "50%" in line


# ── recall instrumentation (B2) ──────────────────────────────────────────────


def test_record_recall_event_appends_line(cortex_home, monkeypatch):
    from intelligence.recall_events import read_recall_events, record_recall_event

    monkeypatch.setenv("CORTEX_SESSION_ID", "sess_unit")
    result = {
        "context_predictions": [
            {"type": "decision", "content": "x", "source": "decision:abc"},
            {"type": "pattern", "content": "y", "source": "seed"},
        ],
        "similar_work": [{"id": "decision:def", "title": "t", "type": "decision"}],
    }
    record_recall_event(result)

    events = read_recall_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["session_id"] == "sess_unit"
    # 2 predictions + 1 similar_work = 3 surfaced
    assert ev["n_predictions"] == 3
    # 2 of them are decisions
    assert ev["n_decisions_surfaced"] == 2
    assert "ts" in ev


def test_record_recall_event_skips_error_results(cortex_home):
    from intelligence.recall_events import read_recall_events, record_recall_event

    record_recall_event({"error": "boom"})
    assert read_recall_events() == []


def test_count_surfaced_handles_empty_and_missing():
    from intelligence.recall_events import count_surfaced

    assert count_surfaced({}) == {"n_predictions": 0, "n_decisions_surfaced": 0}
    assert count_surfaced({"context_predictions": []}) == {
        "n_predictions": 0,
        "n_decisions_surfaced": 0,
    }


def test_recall_summary_aggregates_real_events(cortex_home):
    from intelligence.recall_events import recall_summary, record_recall_event

    record_recall_event({"context_predictions": [{"type": "decision", "source": "decision:1"}]})
    record_recall_event({"similar_work": [{"id": "seed:2", "type": "pattern"}]})

    summ = recall_summary(7)
    assert summ["total_recalls"] == 2
    assert summ["recalls_7d"] == 2
    assert summ["decisions_resurfaced"] == 1
    assert summ["predictions_surfaced"] == 2


# ── B3 opportunistic linker (from stats) ─────────────────────────────────────


def test_opportunistic_linker_creates_real_fk_links(cortex_home):
    from datetime import datetime, timedelta, timezone

    from cli.commands.stats import _run_opportunistic_linker, build_stats_report

    base = datetime.now(timezone.utc)
    queue = cortex_home / "interaction_queue.jsonl"
    events = [
        {
            "type": "prompt_received",
            "session_id": "s1",
            "prompt": "add retry logic",
            "queued_at": base.isoformat(),
        },
        {
            "type": "git_commit",
            "session_id": "s1",
            "hash": "aa11bb2",
            "message": "feat: retry logic",
            "queued_at": (base + timedelta(seconds=30)).isoformat(),
        },
    ]
    with open(queue, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    summary = _run_opportunistic_linker()
    assert summary["new"] == 1

    report = build_stats_report()
    assert report["fk_outcome_links"] == 1


def test_opportunistic_linker_noop_without_queue(cortex_home):
    from cli.commands.stats import _run_opportunistic_linker

    # No interaction_queue.jsonl → nothing linked, nothing written.
    assert _run_opportunistic_linker() == {"linked": 0, "new": 0}
    assert not (cortex_home / "prompt_outcomes.jsonl").exists()


# ── B4 empty-state briefing ──────────────────────────────────────────────────


def test_empty_state_briefing_is_honest(cortex_home):
    from briefing_resilient import format_empty_state_briefing, is_empty_state

    assert is_empty_state() is True
    out = format_empty_state_briefing(use_color=False)
    assert "first run" in out
    assert "No receipts yet" in out
    assert "cortex demo" in out
    # Real anti-pattern count present.
    from intelligence.memory.seed_patterns import get_seed_patterns

    assert str(len(get_seed_patterns())) in out


def test_is_empty_state_false_after_a_decision(cortex_home):
    from briefing_resilient import is_empty_state

    _seed_decisions(cortex_home, 1)
    assert is_empty_state() is False
