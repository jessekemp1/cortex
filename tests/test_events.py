import pytest

from events import EventStore, EventWriteError, InvalidVisibilityError


def test_event_append_returns_envelope(tmp_path):
    store = EventStore(config_dir=tmp_path)
    event = store.append("kempos", "evidence", {"signal": "test"})

    assert event["id"].startswith("evt_")
    assert event["namespace"] == "kempos"
    assert event["type"] == "evidence"
    assert event["visibility"] == "private"
    assert event["payload"] == {"signal": "test"}


def test_event_list_filters_by_type_newest_first(tmp_path):
    store = EventStore(config_dir=tmp_path)
    first = store.append("kempos", "evidence", {"n": 1})
    second = store.append("kempos", "review", {"n": 2})
    third = store.append("kempos", "evidence", {"n": 3})

    evidence = store.list("kempos", event_type="evidence")
    assert [e["id"] for e in evidence] == [third["id"], first["id"]]

    all_events = store.list("kempos")
    assert [e["id"] for e in all_events] == [third["id"], second["id"], first["id"]]


def test_event_get_by_id(tmp_path):
    store = EventStore(config_dir=tmp_path)
    event = store.append("kempos", "evidence", {"signal": "test"})

    assert store.get("kempos", event["id"])["payload"]["signal"] == "test"
    assert store.get("kempos", "evt_missing") is None


def test_event_rejects_invalid_visibility(tmp_path):
    store = EventStore(config_dir=tmp_path)
    with pytest.raises(InvalidVisibilityError):
        store.append("kempos", "evidence", {}, visibility="secret")


def test_event_append_failure_raises(tmp_path):
    config_file = tmp_path / "not_a_dir"
    config_file.write_text("x")
    store = EventStore(config_dir=config_file)

    with pytest.raises(EventWriteError):
        store.append("kempos", "evidence", {"signal": "test"})
