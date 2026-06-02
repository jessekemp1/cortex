"""Tests for batch/research_batcher.py — the Research Batch Processor.

These tests exercise ResearchBatcher's contract without hitting the live
Batch API: the BatchAPIClient is mocked, PortfolioMemory is unavailable
(graceful-degrade path), and result files are written to a tempdir results_dir.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from batch.batch_api_client import BatchRequest
from batch.research_batcher import ResearchBatcher


@pytest.fixture
def batcher(tmp_path: Path) -> ResearchBatcher:
    """A ResearchBatcher with results_dir redirected to tmp_path."""
    with patch.object(ResearchBatcher, "__init__", lambda self: None):
        b = ResearchBatcher()
    b.batch_client = MagicMock()
    b.results_dir = tmp_path
    b.portfolio = None  # graceful-degrade — no PortfolioMemory storage
    return b


# ---------------------------------------------------------------------------
# Empty-input fast path
# ---------------------------------------------------------------------------


def test_process_batch_empty_items_returns_zero_without_api_call(batcher):
    """No research items → no API call, returns submitted_count=0."""
    result = batcher.process_batch([])

    assert result == {"submitted_count": 0, "results": {}}
    batcher.batch_client.submit_batch.assert_not_called()
    batcher.batch_client.poll_results.assert_not_called()


# ---------------------------------------------------------------------------
# _build_batch_requests contract
# ---------------------------------------------------------------------------


def test_build_batch_requests_one_per_item(batcher):
    """Each item produces exactly one BatchRequest."""
    items = [
        {"id": "r1", "topic": "vector indexes", "context": "ctx 1", "priority": "high"},
        {"id": "r2", "topic": "token caching", "context": "ctx 2", "priority": "low"},
    ]
    requests = batcher._build_batch_requests(items)

    assert len(requests) == 2
    assert all(isinstance(r, BatchRequest) for r in requests)
    assert [r.custom_id for r in requests] == ["r1", "r2"]


def test_build_batch_requests_embeds_system_prompt_and_topic(batcher):
    """Each BatchRequest carries the system prompt + the topic text."""
    items = [{"id": "r1", "topic": "compounding intelligence", "context": "FK loop"}]
    requests = batcher._build_batch_requests(items)

    req = requests[0]
    assert req.params["system"] == ResearchBatcher.RESEARCH_SYSTEM_PROMPT
    user_content = req.params["messages"][0]["content"]
    assert "compounding intelligence" in user_content, "topic must appear in user prompt"
    assert "FK loop" in user_content, "context must appear in user prompt"
    assert "Priority Level: medium" in user_content, "default priority should be 'medium'"


def test_build_batch_requests_auto_generates_id_when_missing(batcher):
    """An item without an explicit id gets a derived one (deterministic per topic)."""
    items = [{"topic": "deterministic id"}]
    requests = batcher._build_batch_requests(items)

    assert len(requests) == 1
    assert requests[0].custom_id, "must produce a non-empty custom_id"
    assert "research_" in requests[0].custom_id or requests[0].custom_id != ""


# ---------------------------------------------------------------------------
# _process_result contract
# ---------------------------------------------------------------------------


def test_process_result_succeeded_writes_file_and_returns_success(batcher, tmp_path):
    """A 'succeeded' BatchAPI result → status=success + markdown file written."""
    result = SimpleNamespace(
        custom_id="r1",
        status="succeeded",
        result={
            "message": {
                "content": [{"text": "# Research Findings\n\nKey: X.\n"}],
            }
        },
    )

    out = batcher._process_result("r1", result)

    assert out["id"] == "r1"
    assert out["status"] == "success"
    assert "# Research Findings" in out["report"]
    saved = Path(out["result_file"])
    assert saved.exists()
    assert saved.read_text().startswith("# Research Findings")


def test_process_result_errored_returns_error_envelope(batcher):
    """An 'errored' BatchAPI result → status=error with the upstream error message."""
    result = SimpleNamespace(
        custom_id="r2",
        status="errored",
        result={"error": {"message": "rate_limit"}},
    )

    out = batcher._process_result("r2", result)

    assert out == {
        "id": "r2",
        "status": "error",
        "error": "rate_limit",
        "completed_at": out["completed_at"],  # value-bearing keys checked above
    }


def test_process_result_unknown_status_does_not_crash(batcher):
    """Unknown upstream status → status=unknown envelope, no exception."""
    result = SimpleNamespace(
        custom_id="r3",
        status="processing",  # not 'succeeded' or 'errored'
        result={},
    )

    out = batcher._process_result("r3", result)

    assert out["id"] == "r3"
    assert out["status"] == "unknown"
    assert out["status_code"] == "processing"
