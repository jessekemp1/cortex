from pathlib import Path

from bridge import CortexBridge


class DummyConfig:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.context_optimizer_enabled = False
        self.implicit_feedback_enabled = False
        self.tiered_memory_enabled = False
        self.hybrid_retrieval_enabled = False
        self.defensive_prompting_enabled = False
        self.prompt_versioning_enabled = False


def make_bridge(tmp_path):
    bridge = CortexBridge(root_dir=tmp_path)
    bridge.config = DummyConfig(tmp_path / ".cortex")
    return bridge


def test_bridge_appends_and_lists_events(tmp_path):
    bridge = make_bridge(tmp_path)

    event = bridge.append_event("kempos", "evidence", {"signal": "test"})
    events = bridge.list_events("kempos", event_type="evidence")

    assert event["namespace"] == "kempos"
    assert events[0]["id"] == event["id"]


def test_bridge_capabilities_include_events(tmp_path):
    bridge = make_bridge(tmp_path)
    report = bridge.capabilities()

    assert report["events.write"]["status"] == "available"
    assert report["events.read"]["status"] == "available"


def test_bridge_doctor_namespace(tmp_path):
    bridge = make_bridge(tmp_path)
    report = bridge.doctor_namespace("kempos")

    assert report["status"] == "healthy"
    assert report["namespace"] == "kempos"


def test_bridge_namespaced_recommendation_writes_namespace_file(tmp_path):
    bridge = make_bridge(tmp_path)

    ok = bridge.inject_recommendation(
        title="Ship one small artifact",
        rationale="KempOS weekly loop requires visible evidence.",
        type="kempos_next_action",
        namespace="kempos",
        visibility="private",
    )

    assert ok is True
    rec_path = tmp_path / ".cortex" / "namespaces" / "kempos" / "recommendations.json"
    assert rec_path.exists()
    assert "Ship one small artifact" in rec_path.read_text()


def test_bridge_invalid_namespace_rejected_for_events(tmp_path):
    bridge = make_bridge(tmp_path)

    try:
        bridge.append_event("../kempos", "evidence", {})
    except Exception as exc:
        assert "Namespace" in str(exc) or "namespace" in str(exc)
    else:
        raise AssertionError("invalid namespace should have been rejected")
