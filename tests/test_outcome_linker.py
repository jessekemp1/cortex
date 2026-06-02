"""Integration tests for intelligence.outcome_linker — the FK contract.

These tests exercise the real `link_outcomes()` and `write_linked_outcomes()`
against synthesized real-shape interaction queues. They use tmp_path to keep
production ~/.cortex paths untouched and module-level QUEUE/OUTCOMES intact.

Together they prove the headline "compounding intelligence" claim is live in
this build: prompts → outcomes are joined by session_id within a 90-second
window, scored, and persisted idempotently.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import intelligence.outcome_linker as ol
from intelligence.outcome_linker import (
    link_outcomes,
    write_linked_outcomes,
    _existing_prompt_ids,
)


def _write_queue(queue_path: Path, events: list[dict]) -> None:
    with open(queue_path, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def _read_outcomes(outcomes_path: Path) -> list[dict]:
    if not outcomes_path.exists():
        return []
    return [json.loads(line) for line in outcomes_path.read_text().splitlines() if line]


def test_links_prompts_to_commits(tmp_path: Path) -> None:
    """3 prompts + 2 commits within 90s window → exactly 2 linked entries."""
    base = datetime.now(timezone.utc)
    queue_path = tmp_path / "interaction_queue.jsonl"
    outcomes_path = tmp_path / "prompt_outcomes.jsonl"

    events = [
        # Prompt 1, session A, at t=0
        {
            "type": "prompt_received",
            "session_id": "sess_A",
            "prompt": "Add idempotency to outcome_linker",
            "queued_at": base.isoformat(),
        },
        # Commit within 90s of prompt 1 — should attribute
        {
            "type": "git_commit",
            "session_id": "sess_A",
            "hash": "abc1234",
            "message": "feat: idempotent linker",
            "queued_at": (base + timedelta(seconds=30)).isoformat(),
        },
        # Prompt 2, session B, at t=200 (well past prompt 1's window)
        {
            "type": "prompt_received",
            "session_id": "sess_B",
            "prompt": "Score the FK loop",
            "queued_at": (base + timedelta(seconds=200)).isoformat(),
        },
        # Commit within 90s of prompt 2 — should attribute
        {
            "type": "git_commit",
            "session_id": "sess_B",
            "hash": "def5678",
            "message": "fix: tune score weights",
            "queued_at": (base + timedelta(seconds=240)).isoformat(),
        },
        # Prompt 3, session C, at t=400 (no outcome within 90s)
        {
            "type": "prompt_received",
            "session_id": "sess_C",
            "prompt": "Unrelated query, no outcome",
            "queued_at": (base + timedelta(seconds=400)).isoformat(),
        },
    ]
    _write_queue(queue_path, events)

    linked = link_outcomes(queue_path=queue_path)
    write_linked_outcomes(linked, outcomes_path=outcomes_path)

    # Exactly 2 linked (prompt 3 has no outcome → not in linked).
    assert len(linked) == 2, f"expected 2 linked, got {len(linked)}: {linked}"

    # Each linked entry must have all FK contract fields with the right shapes.
    prompts = [e["prompt_text"] for e in linked]
    assert prompts == [
        "Add idempotency to outcome_linker",
        "Score the FK loop",
    ], f"prompt order or text wrong: {prompts}"

    for entry in linked:
        assert entry["session_id"] in {"sess_A", "sess_B"}
        assert 0.0 <= entry["outcome_score"] <= 1.0
        assert entry["outcome_score"] == 0.8  # 0.4*0.5 (no tests) + 0.4 (commit) + 0.2
        assert len(entry["outcomes"]) == 1
        assert entry["outcomes"][0]["type"] == "git_commit"

    # Persistence: the outcomes file matches the in-memory linked list.
    on_disk = _read_outcomes(outcomes_path)
    assert len(on_disk) == 2
    assert {e["prompt_id"] for e in on_disk} == {e["prompt_id"] for e in linked}


def test_idempotent_write(tmp_path: Path) -> None:
    """Running the pipeline twice against the same queue adds 0 new entries."""
    base = datetime.now(timezone.utc)
    queue_path = tmp_path / "interaction_queue.jsonl"
    outcomes_path = tmp_path / "prompt_outcomes.jsonl"

    events = [
        {
            "type": "prompt_received",
            "session_id": "sess_X",
            "prompt": "Test idempotency",
            "queued_at": base.isoformat(),
        },
        {
            "type": "git_commit",
            "session_id": "sess_X",
            "hash": "hash_X",
            "message": "fix",
            "queued_at": (base + timedelta(seconds=15)).isoformat(),
        },
    ]
    _write_queue(queue_path, events)

    # First run: should write 1 entry.
    linked_1 = link_outcomes(queue_path=queue_path)
    write_linked_outcomes(linked_1, outcomes_path=outcomes_path)
    after_first = _read_outcomes(outcomes_path)
    assert len(after_first) == 1

    # Second run on same queue: link_outcomes returns the same candidate,
    # but the write is idempotent — file size on disk does not grow.
    linked_2 = link_outcomes(queue_path=queue_path)
    write_linked_outcomes(linked_2, outcomes_path=outcomes_path)
    after_second = _read_outcomes(outcomes_path)
    assert len(after_second) == 1, (
        f"idempotency broken — duplicate write produced {len(after_second)} entries"
    )
    assert after_second == after_first


def test_isolated_paths_do_not_touch_module_globals(tmp_path: Path) -> None:
    """Passing kwargs must not mutate ol.QUEUE / ol.OUTCOMES module globals."""
    captured_queue = ol.QUEUE
    captured_outcomes = ol.OUTCOMES

    queue_path = tmp_path / "interaction_queue.jsonl"
    outcomes_path = tmp_path / "prompt_outcomes.jsonl"

    base = datetime.now(timezone.utc)
    _write_queue(
        queue_path,
        [
            {
                "type": "prompt_received",
                "session_id": "sess_Y",
                "prompt": "isolation test",
                "queued_at": base.isoformat(),
            },
            {
                "type": "git_commit",
                "session_id": "sess_Y",
                "hash": "iso123",
                "message": "isolation",
                "queued_at": (base + timedelta(seconds=10)).isoformat(),
            },
        ],
    )

    linked = link_outcomes(queue_path=queue_path)
    write_linked_outcomes(linked, outcomes_path=outcomes_path)

    # Module globals must be unchanged after the call.
    assert ol.QUEUE is captured_queue, "ol.QUEUE was mutated"
    assert ol.OUTCOMES is captured_outcomes, "ol.OUTCOMES was mutated"

    # And the call still did real work.
    assert len(linked) == 1
    assert outcomes_path.exists()


def test_existing_prompt_ids_accepts_kwarg(tmp_path: Path) -> None:
    """The dedup helper must read from the provided path, not the module global."""
    outcomes_path = tmp_path / "prompt_outcomes.jsonl"
    outcomes_path.write_text(
        json.dumps({"prompt_id": "sess_K_0", "outcome_score": 1.0}) + "\n"
    )

    existing = _existing_prompt_ids(outcomes_path=outcomes_path)
    assert existing == {"sess_K_0"}


def test_empty_queue_returns_no_links(tmp_path: Path) -> None:
    """A nonexistent queue file is a clean no-op, not an error."""
    queue_path = tmp_path / "interaction_queue.jsonl"  # never written
    assert not queue_path.exists()

    linked = link_outcomes(queue_path=queue_path)
    assert linked == []
