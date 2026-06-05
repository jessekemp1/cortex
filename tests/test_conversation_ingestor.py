"""Tests for conversation_ingestor engine."""

import json
from datetime import datetime
from pathlib import Path

import pytest

# Conversation ingestor's digest-to-pattern path requires sklearn for embedding
# similarity. Skip the affected tests when sklearn isn't installed instead of
# erroring at collection time.
sklearn = pytest.importorskip("sklearn", reason="conversation ingestor digest path requires scikit-learn (optional)")


@pytest.fixture
def tmp_conversation(tmp_path):
    """Create a minimal Claude Code conversation JSONL file."""
    session_id = "test-session-001"
    messages = [
        {
            "type": "last-prompt",
            "lastPrompt": "fix the bug",
            "sessionId": session_id,
        },
        {
            "type": "user",
            "parentUuid": "root",
            "isSidechain": False,
            "userType": "external",
            "cwd": "/path/to/Vortex/backend",
            "sessionId": session_id,
            "version": "2.1.71",
            "gitBranch": "main",
            "slug": "test-slug",
            "message": {"role": "user", "content": "fix the authentication bug in the API"},
            "uuid": "msg-001",
            "timestamp": "2026-03-10T10:00:00.000Z",
        },
        {
            "type": "assistant",
            "parentUuid": "msg-001",
            "isSidechain": False,
            "userType": "external",
            "cwd": "/path/to/Vortex/backend",
            "sessionId": session_id,
            "version": "2.1.71",
            "gitBranch": "main",
            "slug": "test-slug",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll fix the auth bug."},
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/path/to/Vortex/backend/app/auth.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/path/to/Vortex/backend/app/auth.py"},
                    },
                ],
            },
            "uuid": "msg-002",
            "timestamp": "2026-03-10T10:01:00.000Z",
        },
        {
            "type": "user",
            "parentUuid": "msg-002",
            "isSidechain": False,
            "userType": "external",
            "cwd": "/path/to/Vortex/backend",
            "sessionId": session_id,
            "version": "2.1.71",
            "gitBranch": "main",
            "slug": "test-slug",
            "message": {"role": "user", "content": "looks good, commit this"},
            "uuid": "msg-003",
            "timestamp": "2026-03-10T10:05:00.000Z",
        },
    ]

    conv_file = tmp_path / f"{session_id}.jsonl"
    with open(conv_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return conv_file


@pytest.fixture
def tmp_conversation_with_corrections(tmp_path):
    """Conversation with user corrections."""
    messages = [
        {
            "type": "last-prompt",
            "lastPrompt": "no, revert that",
            "sessionId": "test-corrections",
        },
        {
            "type": "user",
            "cwd": "/path/to/cortex",
            "sessionId": "test-corrections",
            "gitBranch": "feat/test",
            "message": {"role": "user", "content": "add logging to the pipeline"},
            "uuid": "c-001",
            "timestamp": "2026-03-10T10:00:00.000Z",
        },
        {
            "type": "assistant",
            "cwd": "/path/to/cortex",
            "sessionId": "test-corrections",
            "gitBranch": "feat/test",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/a.py"}},
                ],
            },
            "uuid": "c-002",
            "timestamp": "2026-03-10T10:01:00.000Z",
        },
        {
            "type": "user",
            "cwd": "/path/to/cortex",
            "sessionId": "test-corrections",
            "gitBranch": "feat/test",
            "message": {"role": "user", "content": "no, that's wrong. undo that"},
            "uuid": "c-003",
            "timestamp": "2026-03-10T10:02:00.000Z",
        },
        {
            "type": "user",
            "cwd": "/path/to/cortex",
            "sessionId": "test-corrections",
            "gitBranch": "feat/test",
            "message": {"role": "user", "content": "try again with the correct file"},
            "uuid": "c-004",
            "timestamp": "2026-03-10T10:03:00.000Z",
        },
    ]

    conv_file = tmp_path / "test-corrections.jsonl"
    with open(conv_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return conv_file


class TestConversationParser:
    def test_parse_valid_conversation(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser

        parser = ConversationParser(tmp_conversation)
        messages = parser.parse()

        assert len(messages) == 3  # 2 user + 1 assistant (last-prompt is metadata)
        assert messages[0]["type"] == "user"
        assert messages[1]["type"] == "assistant"

    def test_get_session_id(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser

        parser = ConversationParser(tmp_conversation)
        parser.parse()

        assert parser.get_session_id() == "test-session-001"

    def test_get_timestamps(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser

        parser = ConversationParser(tmp_conversation)
        parser.parse()
        first, last = parser.get_timestamps()

        assert "2026-03-10T10:00" in first
        assert "2026-03-10T10:05" in last

    def test_parse_empty_file(self, tmp_path):
        from engines.conversation_ingestor import ConversationParser

        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        parser = ConversationParser(empty)
        assert parser.parse() == []

    def test_parse_invalid_json_lines(self, tmp_path):
        from engines.conversation_ingestor import ConversationParser

        bad = tmp_path / "bad.jsonl"
        bad.write_text("not json\n{invalid}\n")
        parser = ConversationParser(bad)
        assert parser.parse() == []


class TestDigestExtractor:
    def test_extract_basic_digest(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser, DigestExtractor

        parser = ConversationParser(tmp_conversation)
        messages = parser.parse()

        extractor = DigestExtractor()
        digest = extractor.extract(
            messages, "test-session-001", tmp_conversation, parser.get_timestamps()
        )

        assert digest.session_id == "test-session-001"
        assert digest.project == "vortex-backend"
        assert digest.git_branch == "main"
        assert digest.user_prompt_count == 2
        assert digest.assistant_turn_count == 1
        assert digest.tool_use_count == 2
        assert digest.correction_count == 0
        assert digest.outcome == "success"  # ends with "commit"

    def test_extract_file_tracking(self, tmp_conversation, monkeypatch):
        # The ingestor normalizes paths by stripping the configured dev-root
        # prefix. The fixture uses /path/to/... as the prefix; set the env
        # var so the test exercises the normalization path.
        monkeypatch.setenv("CORTEX_DEV_ROOT", "/path/to")
        # Force re-evaluation of the module-level _DEV_ROOT
        import importlib

        from engines import conversation_ingestor as _ci

        importlib.reload(_ci)
        from engines.conversation_ingestor import ConversationParser, DigestExtractor

        parser = ConversationParser(tmp_conversation)
        messages = parser.parse()

        extractor = DigestExtractor()
        digest = extractor.extract(
            messages, "test-session-001", tmp_conversation, parser.get_timestamps()
        )

        assert "Vortex/backend/app/auth.py" in digest.files_read
        assert "Vortex/backend/app/auth.py" in digest.files_written

    def test_extract_corrections(self, tmp_conversation_with_corrections):
        from engines.conversation_ingestor import ConversationParser, DigestExtractor

        parser = ConversationParser(tmp_conversation_with_corrections)
        messages = parser.parse()

        extractor = DigestExtractor()
        digest = extractor.extract(
            messages,
            "test-corrections",
            tmp_conversation_with_corrections,
            parser.get_timestamps(),
        )

        assert digest.correction_count >= 2  # "that's wrong" + "try again"
        assert digest.project == "cortex"
        assert digest.git_branch == "feat/test"

    def test_extract_duration(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser, DigestExtractor

        parser = ConversationParser(tmp_conversation)
        messages = parser.parse()

        extractor = DigestExtractor()
        digest = extractor.extract(messages, "test", tmp_conversation, parser.get_timestamps())

        assert digest.duration_minutes == 5.0  # 10:00 to 10:05

    def test_extract_tool_summary(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser, DigestExtractor

        parser = ConversationParser(tmp_conversation)
        messages = parser.parse()

        extractor = DigestExtractor()
        digest = extractor.extract(messages, "test", tmp_conversation, parser.get_timestamps())

        assert "Read" in digest.tool_summary
        assert "Edit" in digest.tool_summary
        assert digest.tool_summary["Read"] == 1
        assert digest.tool_summary["Edit"] == 1

    def test_extract_topics(self, tmp_conversation):
        from engines.conversation_ingestor import ConversationParser, DigestExtractor

        parser = ConversationParser(tmp_conversation)
        messages = parser.parse()

        extractor = DigestExtractor()
        digest = extractor.extract(messages, "test", tmp_conversation, parser.get_timestamps())

        # Should extract meaningful words from prompts
        assert len(digest.topics) > 0
        # "authentication" and "bug" should appear
        topic_str = " ".join(digest.topics)
        assert "authentication" in topic_str or "bug" in topic_str


class TestConversationIngestor:
    def test_ingest_single(self, tmp_path, tmp_conversation):
        from engines.conversation_ingestor import ConversationIngestor

        digests_path = tmp_path / "digests.jsonl"
        state_path = tmp_path / "state.json"

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=digests_path,
            state_path=state_path,
        )

        digest = ingestor.ingest_single(tmp_conversation)
        assert digest is not None
        assert digest.session_id == "test-session-001"
        assert digests_path.exists()

        # Verify stored on disk
        stored = json.loads(digests_path.read_text().strip())
        assert stored["session_id"] == "test-session-001"

    def test_deduplication(self, tmp_path, tmp_conversation):
        from engines.conversation_ingestor import ConversationIngestor

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        # First ingest
        d1 = ingestor.ingest_single(tmp_conversation)
        assert d1 is not None

        # Second ingest (same file, unchanged) should be skipped
        d2 = ingestor.ingest_single(tmp_conversation)
        assert d2 is None

        # Verify only one digest stored
        lines = (tmp_path / "digests.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1

    def test_backfill(self, tmp_path, tmp_conversation):
        from engines.conversation_ingestor import ConversationIngestor

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        result = ingestor.backfill()
        assert result["total_files"] == 1
        assert result["ingested"] == 1
        assert result["errors"] == 0

    def test_get_stats(self, tmp_path, tmp_conversation):
        from engines.conversation_ingestor import ConversationIngestor

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        ingestor.ingest_single(tmp_conversation)
        stats = ingestor.get_stats()

        assert stats["total_conversations"] == 1
        assert "vortex-backend" in stats["by_project"]
        assert stats["total_prompts"] == 2

    def test_get_digests_filtered(
        self, tmp_path, tmp_conversation, tmp_conversation_with_corrections
    ):
        from engines.conversation_ingestor import ConversationIngestor

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        ingestor.ingest_single(tmp_conversation)
        ingestor.ingest_single(tmp_conversation_with_corrections)

        # Filter by project
        vortex = ingestor.get_digests(project="vortex-backend")
        assert len(vortex) == 1
        assert vortex[0]["project"] == "vortex-backend"

        cortex = ingestor.get_digests(project="cortex")
        assert len(cortex) == 1

    def test_invalid_path(self, tmp_path):
        from engines.conversation_ingestor import ConversationIngestor

        ingestor = ConversationIngestor(
            conversations_dir=tmp_path,
            digests_path=tmp_path / "digests.jsonl",
            state_path=tmp_path / "state.json",
        )

        result = ingestor.ingest_single("/nonexistent/file.jsonl")
        assert result is None


class TestDigestToPattern:
    """Test that digests integrate with HybridRetriever via Pattern conversion."""

    def test_load_digest_patterns(self, tmp_path):
        """Verify _load_digest_patterns produces valid Pattern objects."""
        # Create a minimal digest file
        digest = {
            "session_id": "test-pat-001",
            "project": "cortex",
            "git_branch": "main",
            "started_at": "2026-03-10T10:00:00.000Z",
            "ended_at": "2026-03-10T10:30:00.000Z",
            "duration_minutes": 30.0,
            "user_prompt_count": 5,
            "assistant_turn_count": 5,
            "tool_use_count": 20,
            "correction_count": 1,
            "slash_commands": ["/test", "/commit"],
            "files_read": ["cortex/core.py"],
            "files_written": ["cortex/engines/new_engine.py"],
            "tool_summary": {"Read": 8, "Edit": 6, "Bash": 6},
            "topics": ["engine", "pipeline", "learning"],
            "outcome": "success",
            "outcome_confidence": 0.8,
            "total_messages": 10,
            "has_subagents": False,
        }

        digests_file = tmp_path / "conversation_digests.jsonl"
        digests_file.write_text(json.dumps(digest) + "\n")

        # Monkey-patch the path
        import intelligence.memory.hybrid_retriever as hr

        original = hr._DIGESTS_PATH
        hr._DIGESTS_PATH = digests_file
        try:
            patterns = hr._load_digest_patterns()
            assert len(patterns) == 1

            p = patterns[0]
            assert p.id == "conversation:test-pat-001"
            assert p.project == "cortex"
            assert p.pattern_type == "conversation"
            assert "engine" in p.keywords
            assert "new_engine" in p.keywords  # from files_written basename
            assert "/test" in p.keywords
            assert "/commit" in p.keywords
        finally:
            hr._DIGESTS_PATH = original

    def test_digest_search_text(self):
        from engines.conversation_ingestor import ConversationDigest

        digest = ConversationDigest(
            session_id="test",
            project="vortex-backend",
            git_branch="main",
            started_at="",
            ended_at="",
            duration_minutes=10,
            user_prompt_count=3,
            assistant_turn_count=3,
            tool_use_count=5,
            correction_count=0,
            slash_commands=["/test"],
            files_read=[],
            files_written=["app/api.py"],
            tool_summary={},
            topics=["grib", "forecast"],
            outcome="success",
            outcome_confidence=0.8,
            total_messages=6,
            has_subagents=False,
        )

        text = digest.to_search_text()
        assert "vortex-backend" in text
        assert "grib" in text
        assert "forecast" in text
        assert "success" in text


class TestOutcomeHeuristic:
    """Test the outcome classification logic."""

    def test_empty_session(self):
        from engines.conversation_ingestor import DigestExtractor

        ext = DigestExtractor()
        outcome, conf = ext._compute_outcome([], 0, 0, 0)
        assert outcome == "abandoned"

    def test_positive_ending(self):
        from engines.conversation_ingestor import DigestExtractor

        ext = DigestExtractor()
        prompts = ["fix the bug", "looks good, ship it"]
        outcome, conf = ext._compute_outcome(prompts, 0, 5, 2)
        assert outcome == "success"
        assert conf >= 0.7

    def test_high_correction_rate(self):
        from engines.conversation_ingestor import DigestExtractor

        ext = DigestExtractor()
        prompts = ["do x", "no, that's wrong", "try again", "undo"]
        outcome, conf = ext._compute_outcome(prompts, 3, 5, 3)
        assert outcome == "partial"

    def test_abandoned_ending(self):
        from engines.conversation_ingestor import DigestExtractor

        ext = DigestExtractor()
        prompts = ["do something", "nevermind"]
        outcome, conf = ext._compute_outcome(prompts, 0, 1, 1)
        assert outcome == "abandoned"

    def test_tool_heavy_default(self):
        from engines.conversation_ingestor import DigestExtractor

        ext = DigestExtractor()
        prompts = ["implement feature", "add tests"]
        outcome, conf = ext._compute_outcome(prompts, 0, 10, 5)
        assert outcome == "success"
