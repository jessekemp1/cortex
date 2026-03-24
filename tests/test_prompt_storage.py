"""Tests for conversation content storage and correction chain extraction."""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path):
    """Create a ConsolidatedOutcomeStore with temp DB."""
    os.environ["CORTEX_STATE_DIR"] = str(tmp_path)
    from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

    return ConsolidatedOutcomeStore(db_path=tmp_path / "test_prompts.db")


@pytest.fixture
def conversation_jsonl(tmp_path):
    """Create a conversation with corrections."""
    messages = [
        {
            "type": "last-prompt",
            "lastPrompt": "no fix the other file",
            "sessionId": "store-test-001",
        },
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "store-test-001",
            "gitBranch": "main",
            "message": {"role": "user", "content": "add error handling to the pipeline"},
            "uuid": "s-001",
            "timestamp": "2026-03-20T10:00:00.000Z",
        },
        {
            "type": "assistant",
            "cwd": "/home/user/cortex",
            "sessionId": "store-test-001",
            "gitBranch": "main",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll add error handling to pipeline.py."},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/home/user/cortex/engines/pipeline.py"},
                    },
                ],
            },
            "uuid": "s-002",
            "timestamp": "2026-03-20T10:01:00.000Z",
        },
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "store-test-001",
            "gitBranch": "main",
            "message": {
                "role": "user",
                "content": "no, that's wrong. I meant the ingestor pipeline not pipeline.py",
            },
            "uuid": "s-003",
            "timestamp": "2026-03-20T10:02:00.000Z",
        },
        {
            "type": "assistant",
            "cwd": "/home/user/cortex",
            "sessionId": "store-test-001",
            "gitBranch": "main",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "I see, let me fix the ingestor pipeline instead.",
                    },
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {
                            "file_path": "/home/user/cortex/engines/conversation_ingestor.py"
                        },
                    },
                ],
            },
            "uuid": "s-004",
            "timestamp": "2026-03-20T10:03:00.000Z",
        },
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "store-test-001",
            "gitBranch": "main",
            "message": {"role": "user", "content": "looks good, commit this"},
            "uuid": "s-005",
            "timestamp": "2026-03-20T10:05:00.000Z",
        },
    ]

    conv_file = tmp_path / "store-test-001.jsonl"
    with open(conv_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return conv_file


class TestConversationContentStore:
    def test_store_and_retrieve_turn(self, store):
        rid = store.store_conversation_turn(
            session_id="s1",
            message_index=0,
            role="user",
            content_text="fix the bug",
            project="cortex",
            git_branch="main",
        )
        assert rid > 0

        content = store.get_session_content("s1")
        assert len(content) == 1
        assert content[0]["role"] == "user"
        assert content[0]["content_text"] == "fix the bug"
        assert content[0]["project"] == "cortex"

    def test_store_correction(self, store):
        store.store_conversation_turn(
            session_id="s2",
            message_index=0,
            role="user",
            content_text="do X",
            project="cortex",
        )
        store.store_conversation_turn(
            session_id="s2",
            message_index=1,
            role="assistant",
            content_text="I did X",
            project="cortex",
        )
        store.store_conversation_turn(
            session_id="s2",
            message_index=2,
            role="user",
            content_text="no, that's wrong",
            project="cortex",
            is_correction=True,
            correction_target="I did X",
        )

        corrections = store.get_corrections(project="cortex")
        assert len(corrections) == 1
        assert corrections[0]["content_text"] == "no, that's wrong"
        assert corrections[0]["correction_target"] == "I did X"

    def test_get_corrections_all(self, store):
        for i, (proj, text) in enumerate(
            [("cortex", "no, revert"), ("vortex", "undo that"), ("cortex", "try again")]
        ):
            store.store_conversation_turn(
                session_id=f"s{i}",
                message_index=0,
                role="user",
                content_text=text,
                project=proj,
                is_correction=True,
            )

        all_corrections = store.get_corrections()
        assert len(all_corrections) == 3

        cortex_only = store.get_corrections(project="cortex")
        assert len(cortex_only) == 2

    def test_get_prompts_by_project(self, store):
        store.store_conversation_turn(
            "s1", 0, "user", "prompt 1", project="cortex"
        )
        store.store_conversation_turn(
            "s1", 1, "assistant", "response 1", project="cortex"
        )
        store.store_conversation_turn(
            "s2", 0, "user", "prompt 2", project="vortex"
        )

        cortex_prompts = store.get_prompts_by_project("cortex", role="user")
        assert len(cortex_prompts) == 1
        assert cortex_prompts[0]["content_text"] == "prompt 1"

    def test_session_content_ordering(self, store):
        for i in range(5):
            store.store_conversation_turn(
                "s1", i, "user" if i % 2 == 0 else "assistant", f"msg {i}"
            )

        content = store.get_session_content("s1")
        assert len(content) == 5
        assert [c["message_index"] for c in content] == [0, 1, 2, 3, 4]

    def test_tools_and_files_stored(self, store):
        store.store_conversation_turn(
            "s1",
            0,
            "assistant",
            "editing file",
            tools_used=["Edit", "Read"],
            files_touched=["app.py", "test.py"],
        )

        content = store.get_session_content("s1")
        assert json.loads(content[0]["tools_used_json"]) == ["Edit", "Read"]
        assert json.loads(content[0]["files_touched_json"]) == ["app.py", "test.py"]


class TestCorrectionChains:
    def test_store_and_retrieve_chain(self, store):
        rid = store.store_correction_chain(
            session_id="s1",
            wrong_approach="edited pipeline.py",
            user_correction="no, that's wrong. I meant the ingestor",
            correct_approach="edited conversation_ingestor.py",
            project="cortex",
            files_affected=["pipeline.py", "conversation_ingestor.py"],
            correction_type="wrong_file",
        )
        assert rid > 0

        chains = store.get_correction_chains(project="cortex")
        assert len(chains) == 1
        assert chains[0]["wrong_approach"] == "edited pipeline.py"
        assert chains[0]["user_correction"] == "no, that's wrong. I meant the ingestor"
        assert chains[0]["correction_type"] == "wrong_file"

    def test_filter_by_type(self, store):
        store.store_correction_chain("s1", "wrong", "fix", correction_type="wrong_file")
        store.store_correction_chain("s2", "broke", "undo", correction_type="broken")
        store.store_correction_chain("s3", "wrong2", "fix2", correction_type="wrong_file")

        wrong_file = store.get_correction_chains(correction_type="wrong_file")
        assert len(wrong_file) == 2

        broken = store.get_correction_chains(correction_type="broken")
        assert len(broken) == 1

    def test_filter_by_project(self, store):
        store.store_correction_chain("s1", "w", "c", project="cortex")
        store.store_correction_chain("s2", "w", "c", project="vortex")

        assert len(store.get_correction_chains(project="cortex")) == 1
        assert len(store.get_correction_chains(project="vortex")) == 1
        assert len(store.get_correction_chains()) == 2


class TestIngestorContentStorage:
    """Test that ConversationIngestor stores content alongside digests."""

    def test_ingest_stores_content(self, tmp_path, conversation_jsonl):
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

        digest = ingestor.ingest_single(conversation_jsonl)
        assert digest is not None

        # Verify content was stored
        content = store.get_session_content("store-test-001")
        assert len(content) >= 4  # at least user+assistant+user+assistant

        # Verify corrections detected
        corrections = store.get_corrections(project="cortex")
        assert len(corrections) >= 1
        assert "wrong" in corrections[0]["content_text"].lower()

    def test_ingest_stores_correction_chains(self, tmp_path, conversation_jsonl):
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

        digest = ingestor.ingest_single(conversation_jsonl)
        assert digest is not None

        chains = store.get_correction_chains(project="cortex")
        assert len(chains) >= 1
        # The correction was about wrong file
        chain = chains[0]
        assert "pipeline" in chain["wrong_approach"].lower()

    def test_ingest_dedup_content(self, tmp_path, conversation_jsonl):
        """Content is not re-stored on duplicate ingest."""
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

        # First ingest
        d1 = ingestor.ingest_single(conversation_jsonl)
        assert d1 is not None
        count1 = len(store.get_session_content("store-test-001"))

        # Re-ingest same file (should be skipped by digest dedup)
        d2 = ingestor.ingest_single(conversation_jsonl)
        assert d2 is None  # deduped at digest level

        count2 = len(store.get_session_content("store-test-001"))
        assert count2 == count1  # no duplicate content


class TestStorageInfo:
    def test_includes_new_tables(self, store):
        info = store.get_storage_info()
        assert "conversation_content" in info["tables"]
        assert "correction_chains" in info["tables"]
        assert info["schema_version"] == 2
