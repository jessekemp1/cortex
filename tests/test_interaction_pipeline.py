import json
from pathlib import Path


def test_event_adapter_normalizes_claude_and_codex():
    from intelligence.bandwidth.event_adapter import normalize_claude_event, normalize_codex_event

    claude = normalize_claude_event(
        "prompt",
        {"session_id": "s1", "cwd": "/tmp/project", "prompt": "hello"},
    )
    codex = normalize_codex_event(
        {"event": "prompt", "session_id": "s2", "cwd": "/tmp/project2", "prompt": "hi"},
    )

    assert claude["type"] == "prompt_received"
    assert codex["type"] == "prompt_received"
    assert claude["source"] == "claude"
    assert codex["source"] == "codex"
    assert "captured_at" in claude
    assert "captured_at" in codex


def test_interaction_learner_snapshot_is_replay_safe(tmp_path):
    from engines.interaction_learner import InteractionLearner
    from intelligence.bandwidth.contracts import ContractMetricsStore

    queue_file = tmp_path / "interaction_queue.jsonl"
    state_file = tmp_path / "interaction_learning_state.json"

    first = {"type": "prompt_received", "session_id": "s1", "prompt": "hello"}
    queue_file.write_text(json.dumps(first) + "\n")

    learner = InteractionLearner(
        queue_file=queue_file,
        state_file=state_file,
        contract_store=ContractMetricsStore(storage_dir=tmp_path / "bandwidth"),
    )
    inserted = {"done": False}

    def _analyze_and_append(session_id, interactions):
        if not inserted["done"]:
            queue_file.write_text(
                json.dumps({"type": "prompt_received", "session_id": "s2", "prompt": "new"})
                + "\n"
            )
            inserted["done"] = True
        return []

    learner._analyze_session = _analyze_and_append  # type: ignore[method-assign]
    learner._generate_insights = lambda *_args, **_kwargs: []  # type: ignore[method-assign]
    learner._update_learning_system = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    learner._update_session_patterns = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

    result = learner.process_queue()

    assert result["status"] == "success"
    assert result["processed"] == 1
    assert queue_file.exists()

    remaining = [line for line in queue_file.read_text().splitlines() if line.strip()]
    assert len(remaining) == 1
    assert json.loads(remaining[0])["session_id"] == "s2"

    processing_file = queue_file.with_name("interaction_queue.processing.jsonl")
    assert not processing_file.exists()


def test_contract_metrics_store_aggregate(tmp_path):
    from intelligence.bandwidth.contracts import ContractMetricsStore, ContractSessionMetrics
    from datetime import datetime

    store = ContractMetricsStore(storage_dir=tmp_path / "bandwidth")
    store.record(
        ContractSessionMetrics(
            timestamp=datetime.now(),
            session_id="s1",
            project="cortex",
            source="claude",
            override_rate=0.2,
            autonomy_level=0.7,
            novelty_score=4.0,
        )
    )
    store.record(
        ContractSessionMetrics(
            timestamp=datetime.now(),
            session_id="s2",
            project="cortex",
            source="codex",
            override_rate=0.1,
            autonomy_level=0.9,
            novelty_score=6.0,
        )
    )

    agg = store.aggregate(days=7, project="cortex")
    assert agg["sessions"] == 2
    assert agg["override_rate"] == 0.15
    assert agg["autonomy_level"] == 0.8
    assert agg["novelty_score"] == 5.0
