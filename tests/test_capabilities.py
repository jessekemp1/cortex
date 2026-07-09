import pytest

from capabilities import CapabilityRegistry


def test_capability_registry_returns_explicit_statuses(tmp_path):
    registry = CapabilityRegistry(config_dir=tmp_path)
    report = registry.list()

    assert report["events.write"]["status"] == "available"
    assert report["events.read"]["status"] == "available"
    assert report["namespace.isolation"]["status"] == "available"
    assert report["health.doctor"]["status"] == "available"
    assert report["memory.read"]["status"] == "degraded"
    assert report["memory.write"]["status"] == "degraded"
    assert report["scheduler.run"]["status"] == "missing"


def test_require_allows_degraded_but_not_missing(tmp_path):
    registry = CapabilityRegistry(config_dir=tmp_path)

    assert registry.require("events.write").status == "available"
    assert registry.require("memory.write").status == "degraded"

    with pytest.raises(RuntimeError):
        registry.require("scheduler.run")


def test_unknown_capability_missing(tmp_path):
    registry = CapabilityRegistry(config_dir=tmp_path)
    status = registry.get("does.not.exist")

    assert status.status == "missing"
    assert status.reason == "unknown capability"
