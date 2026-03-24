"""End-to-end test: fake JSONL → hook → digest + content stored → queryable."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def e2e_env(tmp_path):
    """Set up temp environment with a fake conversation."""
    messages = [
        {
            "type": "last-prompt",
            "lastPrompt": "thanks",
            "sessionId": "e2e-test-001",
        },
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "e2e-test-001",
            "gitBranch": "main",
            "message": {"role": "user", "content": "implement the new feature"},
            "uuid": "e-001",
            "timestamp": "2026-03-20T14:00:00.000Z",
        },
        {
            "type": "assistant",
            "cwd": "/home/user/cortex",
            "sessionId": "e2e-test-001",
            "gitBranch": "main",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll implement the feature."},
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "/a.py"}},
                ],
            },
            "uuid": "e-002",
            "timestamp": "2026-03-20T14:05:00.000Z",
        },
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "e2e-test-001",
            "gitBranch": "main",
            "message": {"role": "user", "content": "thanks, looks great"},
            "uuid": "e-003",
            "timestamp": "2026-03-20T14:10:00.000Z",
        },
    ]

    conv_file = tmp_path / "e2e-test-001.jsonl"
    with open(conv_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return {
        "tmp_path": tmp_path,
        "conv_file": conv_file,
    }


class TestSessionIngestHookE2E:
    def test_hook_ingests_via_python(self, e2e_env):
        """Test the hook entry point processes a conversation correctly."""
        tmp_path = e2e_env["tmp_path"]
        conv_file = e2e_env["conv_file"]

        os.environ["CORTEX_STATE_DIR"] = str(tmp_path)

        from engines.conversation_ingestor import ConversationIngestor
        from intelligence.storage.consolidated_store import (
            ConsolidatedOutcomeStore,
            set_consolidated_store,
        )

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "test.db")
        set_consolidated_store(store)

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        # Simulate what the hook does
        digest = ingestor.ingest_single(conv_file)
        assert digest is not None
        assert digest.session_id == "e2e-test-001"
        assert digest.outcome == "success"  # ends with "thanks"
        assert digest.user_prompt_count == 2
        assert digest.tool_use_count == 1

        # Verify digest stored on disk
        assert (tmp_path / "digests.jsonl").exists()
        stored = json.loads((tmp_path / "digests.jsonl").read_text().strip())
        assert stored["session_id"] == "e2e-test-001"

        # Verify full content stored in SQLite
        content = store.get_session_content("e2e-test-001")
        assert len(content) >= 3  # 2 user + 1 assistant

        user_turns = [c for c in content if c["role"] == "user"]
        assert len(user_turns) == 2
        assert "implement" in user_turns[0]["content_text"]

    def test_hook_script_runs(self, e2e_env):
        """Test that the hook script can be invoked as a subprocess."""
        hook_script = Path(__file__).parent.parent / "hooks" / "session_ingest_hook.py"
        if not hook_script.exists():
            pytest.skip("Hook script not found")

        # Pass empty stdin — hook should handle gracefully
        result = subprocess.run(
            [sys.executable, str(hook_script)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).parent.parent),
        )
        # Should not crash
        assert result.returncode == 0

    def test_hook_with_transcript_path(self, e2e_env):
        """Test hook with explicit transcript_path in stdin."""
        tmp_path = e2e_env["tmp_path"]
        conv_file = e2e_env["conv_file"]

        hook_script = Path(__file__).parent.parent / "hooks" / "session_ingest_hook.py"
        if not hook_script.exists():
            pytest.skip("Hook script not found")

        hook_input = json.dumps({
            "transcript_path": str(conv_file),
            "session_id": "e2e-test-001",
        })

        env = os.environ.copy()
        env["CORTEX_STATE_DIR"] = str(tmp_path)

        result = subprocess.run(
            [sys.executable, str(hook_script)],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).parent.parent),
            env=env,
        )
        assert result.returncode == 0


class TestBackfillE2E:
    def test_backfill_multiple_conversations(self, tmp_path):
        """Test backfilling multiple conversation files."""
        os.environ["CORTEX_STATE_DIR"] = str(tmp_path)

        from engines.conversation_ingestor import ConversationIngestor
        from intelligence.storage.consolidated_store import (
            ConsolidatedOutcomeStore,
            set_consolidated_store,
        )

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "test.db")
        set_consolidated_store(store)

        # Create 3 fake conversations
        for i in range(3):
            messages = [
                {
                    "type": "user",
                    "cwd": f"/home/user/project{i}",
                    "sessionId": f"backfill-{i}",
                    "gitBranch": "main",
                    "message": {"role": "user", "content": f"task {i}"},
                    "uuid": f"b-{i}-001",
                    "timestamp": f"2026-03-{20+i}T10:00:00.000Z",
                },
                {
                    "type": "assistant",
                    "cwd": f"/home/user/project{i}",
                    "sessionId": f"backfill-{i}",
                    "gitBranch": "main",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": f"done {i}"}],
                    },
                    "uuid": f"b-{i}-002",
                    "timestamp": f"2026-03-{20+i}T10:05:00.000Z",
                },
            ]
            conv_file = tmp_path / f"backfill-{i}.jsonl"
            with open(conv_file, "w") as f:
                for msg in messages:
                    f.write(json.dumps(msg) + "\n")

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        result = ingestor.backfill()
        assert result["total_files"] == 3
        assert result["ingested"] == 3
        assert result["errors"] == 0

        # Verify all sessions stored
        stats = ingestor.get_stats()
        assert stats["total_conversations"] == 3
