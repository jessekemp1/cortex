import json


def test_event_adapter_normalizes_claude_and_codex():
    from intelligence.bandwidth.event_adapter import (
        normalize_claude_event,
        normalize_codex_event,
    )

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
                json.dumps({"type": "prompt_received", "session_id": "s2", "prompt": "new"}) + "\n"
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
    from datetime import datetime

    from intelligence.bandwidth.contracts import (
        ContractMetricsStore,
        ContractSessionMetrics,
    )

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


def test_queue_slo_thresholds(tmp_path):
    from intelligence.bandwidth.queue_slo import check_queue_slo

    queue = tmp_path / "interaction_queue.jsonl"
    proc = tmp_path / "interaction_queue.processing.jsonl"
    queue.write_text("\n".join(["x"] * 12))
    proc.write_text("\n".join(["x"] * 3))

    status = check_queue_slo(
        queue_file=queue, processing_file=proc, backlog_warn=10, backlog_crit=20
    )
    assert status["total_lines"] == 15
    assert status["status"] == "warning"


def test_baseline_report_generation(tmp_path):
    from datetime import datetime

    from intelligence.bandwidth.baseline_report import generate_baseline_report
    from intelligence.bandwidth.contracts import (
        ContractMetricsStore,
        ContractSessionMetrics,
    )
    from intelligence.bandwidth.meter import BandwidthMeter, BandwidthMetrics

    contracts = ContractMetricsStore(storage_dir=tmp_path / "bandwidth")
    contracts.record(
        ContractSessionMetrics(
            timestamp=datetime.now(),
            session_id="s1",
            project="cortex",
            source="claude",
            override_rate=0.2,
            autonomy_level=0.8,
            novelty_score=4.0,
        )
    )

    meter = BandwidthMeter(storage_dir=tmp_path / "bandwidth")
    meter.record(
        BandwidthMetrics(
            timestamp=datetime.now(),
            session_id="s1",
            project="cortex",
            tokens_in=1000,
            tokens_out=500,
            tokens_useful=350,
            corrections=1,
            iterations=4,
            time_to_productive_seconds=120,
            files_modified=2,
        )
    )

    report = generate_baseline_report(
        output_dir=tmp_path / "reports",
        project="cortex",
        days=7,
        storage_dir=tmp_path / "bandwidth",
    )
    assert report["window"]["frozen"] is True
    assert (tmp_path / "reports" / "baseline_report.json").exists()
    assert (tmp_path / "reports" / "baseline_report.md").exists()


def test_prediction_identity_fields(tmp_path):
    from intelligence.bandwidth.predictions import PredictionTracker

    tracker = PredictionTracker(storage_dir=tmp_path / "bandwidth")
    pred = tracker.record_prediction(
        prediction_id="p1",
        confidence=0.8,
        domain="code",
        description="identity test",
        source="codex",
        session_id="sess-123",
    )
    assert pred.source == "codex"
    assert pred.session_id == "sess-123"
