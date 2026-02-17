#!/usr/bin/env python3
"""Tests for the Edit-without-Read Guardian hook.

Verifies:
- Session state management (clear on start, track on read)
- Blind edit detection (warn when file not read)
- Read-verified pass (silent when file was read)
- Telemetry logging
- Path normalization
"""

# We need to import from the hook file which lives at .claude/hooks/
# Use importlib to handle the non-standard location
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parents[3]
    / ".claude"
    / "hooks"
    / "archive"
    / "edit_without_read_guard.py"
)


@pytest.fixture
def hook_module():
    """Import the hook module from its non-standard location."""
    spec = importlib.util.spec_from_file_location("edit_without_read_guard", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def state_dir(tmp_path, hook_module):
    """Override state directory to use a temp directory for test isolation."""
    test_state_dir = tmp_path / ".cortex-lean"
    test_state_dir.mkdir()

    with patch.object(hook_module, "STATE_DIR", test_state_dir):
        with patch.object(hook_module, "SESSION_READS", test_state_dir / "session_reads.jsonl"):
            with patch.object(hook_module, "GUARDIAN_LOG", test_state_dir / "guardian_log.jsonl"):
                yield test_state_dir


class TestSessionStart:
    """Test session state initialization."""

    def test_clears_session_reads(self, hook_module, state_dir):
        """handle_session_start creates an empty session_reads file."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("/some/old/file.py\n/another/stale/file.py\n")

        hook_module.handle_session_start()

        assert reads_file.read_text() == ""

    def test_creates_state_dir_if_missing(self, hook_module, tmp_path):
        """handle_session_start creates ~/.cortex-lean/ if it does not exist."""
        new_dir = tmp_path / "new-lean-dir"
        with patch.object(hook_module, "STATE_DIR", new_dir):
            with patch.object(hook_module, "SESSION_READS", new_dir / "session_reads.jsonl"):
                hook_module.handle_session_start()

        assert new_dir.exists()
        assert (new_dir / "session_reads.jsonl").exists()


class TestPostRead:
    """Test read tracking via PostToolUse:Read."""

    def test_tracks_file_path(self, hook_module, state_dir):
        """handle_post_read appends resolved file path to session state."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("")

        hook_module.handle_post_read({"file_path": "/Users/dev/project/main.py"})

        content = reads_file.read_text().strip()
        assert "/Users/dev/project/main.py" in content

    def test_ignores_empty_file_path(self, hook_module, state_dir):
        """handle_post_read does nothing when file_path is empty."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("")

        hook_module.handle_post_read({"file_path": ""})

        assert reads_file.read_text() == ""

    def test_accumulates_multiple_reads(self, hook_module, state_dir):
        """Multiple reads are all tracked in session state."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("")

        hook_module.handle_post_read({"file_path": "/project/a.py"})
        hook_module.handle_post_read({"file_path": "/project/b.py"})
        hook_module.handle_post_read({"file_path": "/project/c.py"})

        lines = [l for l in reads_file.read_text().strip().split("\n") if l]
        assert len(lines) == 3


class TestPreEdit:
    """Test blind edit detection via PreToolUse:Edit."""

    def test_warns_on_blind_edit(self, hook_module, state_dir, capsys):
        """Editing a file not Read this session produces a warning."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("")

        hook_module.handle_pre_edit({"file_path": "/project/unread.py"})

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "hookSpecificOutput" in output
        assert "Guardian" in output["hookSpecificOutput"]["userMessage"]
        assert "unread.py" in output["hookSpecificOutput"]["userMessage"]

    def test_passes_when_file_was_read(self, hook_module, state_dir, capsys):
        """Editing a file that was Read this session produces no output."""
        reads_file = state_dir / "session_reads.jsonl"
        resolved = str(Path("/project/read_first.py").resolve())
        reads_file.write_text(resolved + "\n")

        hook_module.handle_pre_edit({"file_path": "/project/read_first.py"})

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_ignores_empty_file_path(self, hook_module, state_dir, capsys):
        """handle_pre_edit does nothing when file_path is empty."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("")

        hook_module.handle_pre_edit({"file_path": ""})

        captured = capsys.readouterr()
        assert captured.out == ""


class TestTelemetry:
    """Test guardian telemetry logging."""

    def test_log_event_writes_entry(self, hook_module, state_dir):
        """log_event appends a JSON entry to guardian_log.jsonl."""
        hook_module.log_event("/project/file.py", "warn_blind_edit")

        log_file = state_dir / "guardian_log.jsonl"
        assert log_file.exists()

        entries = [json.loads(line) for line in log_file.read_text().strip().split("\n") if line]
        assert len(entries) == 1
        assert entries[0]["file_path"] == "/project/file.py"
        assert entries[0]["event"] == "warn_blind_edit"
        assert "timestamp" in entries[0]

    def test_log_event_includes_session_id(self, hook_module, state_dir):
        """log_event records the CLAUDE_SESSION_ID from environment."""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-42"}):
            hook_module.log_event("/project/file.py", "pass_read_verified")

        log_file = state_dir / "guardian_log.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert entry["session_id"] == "test-session-42"


class TestLoadReadFiles:
    """Test session state loading."""

    def test_returns_empty_set_when_no_file(self, hook_module, state_dir):
        """load_read_files returns empty set when session file is missing."""
        reads_file = state_dir / "session_reads.jsonl"
        if reads_file.exists():
            reads_file.unlink()

        result = hook_module.load_read_files()
        assert result == set()

    def test_returns_paths_from_file(self, hook_module, state_dir):
        """load_read_files returns set of paths from session state."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("/project/a.py\n/project/b.py\n")

        result = hook_module.load_read_files()
        assert result == {"/project/a.py", "/project/b.py"}

    def test_ignores_blank_lines(self, hook_module, state_dir):
        """load_read_files skips blank lines in session state."""
        reads_file = state_dir / "session_reads.jsonl"
        reads_file.write_text("/project/a.py\n\n\n/project/b.py\n\n")

        result = hook_module.load_read_files()
        assert len(result) == 2


class TestEndToEnd:
    """Integration-style tests for the full read-then-edit flow."""

    def test_read_then_edit_passes(self, hook_module, state_dir, capsys):
        """Full flow: session start -> read file -> edit file = no warning."""
        hook_module.handle_session_start()
        hook_module.handle_post_read({"file_path": "/project/target.py"})
        hook_module.handle_pre_edit({"file_path": "/project/target.py"})

        captured = capsys.readouterr()
        # Should NOT contain a warning JSON output
        if captured.out.strip():
            output = json.loads(captured.out)
            # If there is output, it should not be a warning
            assert "Guardian" not in output.get("hookSpecificOutput", {}).get("userMessage", "")

    def test_edit_without_read_warns(self, hook_module, state_dir, capsys):
        """Full flow: session start -> edit file (no read) = warning."""
        hook_module.handle_session_start()
        hook_module.handle_pre_edit({"file_path": "/project/target.py"})

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "Guardian" in output["hookSpecificOutput"]["userMessage"]

    def test_session_restart_clears_state(self, hook_module, state_dir, capsys):
        """Session restart clears tracked reads, requiring re-reads."""
        # First session: read a file
        hook_module.handle_session_start()
        hook_module.handle_post_read({"file_path": "/project/target.py"})

        # New session: state should be cleared
        hook_module.handle_session_start()
        hook_module.handle_pre_edit({"file_path": "/project/target.py"})

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "Guardian" in output["hookSpecificOutput"]["userMessage"]
