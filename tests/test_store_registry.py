"""The store registry must name a maintainer for every store it lists."""

from __future__ import annotations

import time

from store_registry import Store, WRITER_NONE, evaluate, registry


def test_registry_lists_the_live_stores():
    names = {s.name for s in registry()}
    assert {"decisions", "outcomes", "embedding_index", "project_index"} <= names


def test_every_store_declares_a_writer():
    """A store nothing maintains is the exact failure project_index.json was."""
    for s in registry():
        assert s.writer and s.writer != WRITER_NONE, f"{s.name} has no writer"


def test_writer_none_is_a_hard_problem(tmp_path):
    orphan = Store(
        name="orphan",
        path=tmp_path / "x.json",
        writer=WRITER_NONE,
        consumers="something",
        event_driven=True,
    )
    (tmp_path / "x.json").write_text("{}")
    st = evaluate([orphan])[0]
    assert not st.ok
    assert any("no writer" in p for p in st.problems)


def test_event_driven_store_has_no_age_sla(tmp_path):
    """A quiet journal is not rot. Alerting on it is the false positive we fight."""
    p = tmp_path / "decisions.jsonl"
    p.write_text("{}")
    old = time.time() - 400 * 86400
    import os

    os.utime(p, (old, old))
    s = Store("j", p, writer="w", consumers="c", event_driven=True)
    st = evaluate([s])[0]
    assert st.ok, st.problems
    assert st.age_days and st.age_days > 90


def test_scheduled_store_past_sla_is_a_hard_problem(tmp_path):
    """A store its scheduler should keep fresh is stale -> the scheduler broke."""
    p = tmp_path / "index.json"
    p.write_text("{}")
    old = time.time() - 40 * 86400
    import os

    os.utime(p, (old, old))
    s = Store("idx", p, writer="w", consumers="c", event_driven=False, max_age_days=30, scheduled=True)
    st = evaluate([s])[0]
    assert not st.ok
    assert any("stale" in p_ and "scheduler" in p_ for p_ in st.problems)


def test_unscheduled_store_past_sla_warns_with_action_not_fails(tmp_path):
    """No scheduler by design: staleness is expected maintenance, so WARN with the
    exact command — not a hard FAIL that sits red until it is ignored."""
    p = tmp_path / "index.json"
    p.write_text("{}")
    old = time.time() - 40 * 86400
    import os

    os.utime(p, (old, old))
    s = Store("idx", p, writer="portfolio_memory.refresh_index", consumers="c",
              event_driven=False, max_age_days=30, scheduled=False)
    st = evaluate([s])[0]
    assert st.ok, "unscheduled-by-design staleness must not hard-fail"
    assert any("stale" in w and "refresh_index" in w for w in st.warnings)


def test_regenerated_within_sla_is_ok(tmp_path):
    p = tmp_path / "index.json"
    p.write_text("{}")  # fresh
    s = Store("idx", p, writer="w", consumers="c", event_driven=False, max_age_days=30, scheduled=True)
    st = evaluate([s])[0]
    assert st.ok


def test_unscheduled_store_warns_within_sla_but_does_not_fail(tmp_path):
    """project_index.json: real drift risk, not yet materialised. Warn, don't fail."""
    p = tmp_path / "index.json"
    p.write_text("{}")  # fresh, within SLA
    s = Store("idx", p, writer="w", consumers="c", event_driven=False, max_age_days=30, scheduled=False)
    st = evaluate([s])[0]
    assert st.ok, "within-SLA store must not hard-fail"
    assert st.warnings and any("scheduler" in w for w in st.warnings)


def test_missing_store_is_a_problem(tmp_path):
    s = Store("gone", tmp_path / "nope.json", writer="w", consumers="c", event_driven=True)
    st = evaluate([s])[0]
    assert not st.ok
    assert not st.exists
    assert any("missing" in p for p in st.problems)


def test_project_index_is_unscheduled_regenerated():
    """It has no scheduler (auto-refresh was rejected as unsafe under launchd),
    so scheduled=False is honest; it is regenerated, so the age SLA applies as a
    WARN telling the human to refresh, never a silent green."""
    pi = next(s for s in registry() if s.name == "project_index")
    assert pi.scheduled is False
    assert not pi.event_driven
    assert pi.max_age_days is not None
