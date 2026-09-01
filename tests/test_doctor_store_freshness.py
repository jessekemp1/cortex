"""cortex_doctor gains a store-freshness check that would have caught the rot.

project_index.json was read confidently for three months after its last write.
A doctor check over the store registry turns that class of silent rot into a
visible, dated failure.
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import mcp_server
import store_registry
from store_registry import Store


def _doctor_checks():
    return json.loads(mcp_server.cortex_doctor())["checks"]


def test_doctor_includes_a_store_check_per_registered_store():
    names = {c["check"] for c in _doctor_checks()}
    for store in store_registry.registry():
        assert f"store fresh: {store.name}" in names


def test_stale_regenerated_store_fails_doctor(tmp_path):
    p = tmp_path / "index.json"
    p.write_text("{}")
    old = time.time() - 200 * 86400
    import os

    os.utime(p, (old, old))
    stale = Store("rotted", p, writer="w", consumers="c", event_driven=False, max_age_days=30, scheduled=True)

    with patch.object(store_registry, "registry", return_value=[stale]):
        checks = _doctor_checks()
    row = next(c for c in checks if c["check"] == "store fresh: rotted")
    assert row["pass"] is False
    assert "stale" in row["detail"]


def test_fresh_store_passes_doctor(tmp_path):
    p = tmp_path / "index.json"
    p.write_text("{}")
    fresh = Store("good", p, writer="w", consumers="c", event_driven=False, max_age_days=30, scheduled=True)
    with patch.object(store_registry, "registry", return_value=[fresh]):
        checks = _doctor_checks()
    row = next(c for c in checks if c["check"] == "store fresh: good")
    assert row["pass"] is True


def test_unscheduled_store_passes_but_warns_in_detail(tmp_path):
    """The within-SLA project_index case: green, but the detail names the risk."""
    p = tmp_path / "index.json"
    p.write_text("{}")
    unsched = Store("drifter", p, writer="w", consumers="c", event_driven=False, max_age_days=30, scheduled=False)
    with patch.object(store_registry, "registry", return_value=[unsched]):
        checks = _doctor_checks()
    row = next(c for c in checks if c["check"] == "store fresh: drifter")
    assert row["pass"] is True
    assert "scheduler" in row["detail"]


def test_unscheduled_store_past_sla_warns_but_does_not_fail_doctor(tmp_path):
    """The project_index case once it crosses SLA: the doctor stays green (no
    broken pipeline) but the detail names the refresh action. Prevents the
    permanent-red-that-gets-ignored failure mode."""
    p = tmp_path / "index.json"
    p.write_text("{}")
    old = time.time() - 200 * 86400
    import os

    os.utime(p, (old, old))
    unsched = Store("drifted", p, writer="portfolio_memory.refresh_index", consumers="c",
                    event_driven=False, max_age_days=30, scheduled=False)
    with patch.object(store_registry, "registry", return_value=[unsched]):
        checks = _doctor_checks()
    row = next(c for c in checks if c["check"] == "store fresh: drifted")
    assert row["pass"] is True
    assert "stale" in row["detail"] and "refresh_index" in row["detail"]


def test_missing_store_fails_doctor(tmp_path):
    gone = Store("absent", tmp_path / "nope.json", writer="w", consumers="c", event_driven=True)
    with patch.object(store_registry, "registry", return_value=[gone]):
        checks = _doctor_checks()
    row = next(c for c in checks if c["check"] == "store fresh: absent")
    assert row["pass"] is False
    assert "missing" in row["detail"]
