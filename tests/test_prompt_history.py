"""Tests for prompt_history intelligence module."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _recent_iso(days_ago: int = 1, hours_offset: int = 0) -> str:
    """Return an ISO timestamp N days ago (always within lookback window)."""
    dt = datetime.now() - timedelta(days=days_ago, hours=-hours_offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


@pytest.fixture
def sessions_dir(tmp_path):
    """Create a fake sessions directory with JSONL conversations."""
    project_dir = tmp_path / "-home-user-cortex"
    project_dir.mkdir()

    messages = [
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "ph-test-001",
            "gitBranch": "main",
            "message": {"role": "user", "content": "fix the urgent authentication bug"},
            "uuid": "ph-001",
            "timestamp": _recent_iso(days_ago=2),
        },
        {
            "type": "assistant",
            "cwd": "/home/user/cortex",
            "sessionId": "ph-test-001",
            "gitBranch": "main",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll fix the auth bug."},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/auth.py"}},
                ],
            },
            "uuid": "ph-002",
            "timestamp": _recent_iso(days_ago=2, hours_offset=1),
        },
        {
            "type": "user",
            "cwd": "/home/user/cortex",
            "sessionId": "ph-test-001",
            "gitBranch": "main",
            "message": {"role": "user", "content": "add tests for the fix"},
            "uuid": "ph-003",
            "timestamp": _recent_iso(days_ago=2, hours_offset=2),
        },
    ]

    conv_file = project_dir / "ph-test-001.jsonl"
    with open(conv_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return tmp_path


class TestPromptHistoryAnalyzer:
    def test_detect_sessions_dir(self):
        from intelligence.prompt_history import PromptHistoryAnalyzer

        analyzer = PromptHistoryAnalyzer()
        # Should resolve to a real path (even if empty)
        assert analyzer.sessions_dir is not None

    def test_extract_sessions_from_jsonl(self, sessions_dir):
        from intelligence.prompt_history import PromptHistoryAnalyzer

        analyzer = PromptHistoryAnalyzer(sessions_dir=sessions_dir)
        sessions = analyzer.extract_sessions(days_back=30)

        assert len(sessions) >= 1
        session = sessions[0]
        assert session["session_id"] == "ph-test-001"
        assert len(session["prompts"]) == 2
        assert "Edit" in session["tools_used"]

    def test_analyze_patterns(self, sessions_dir):
        from intelligence.prompt_history import PromptHistoryAnalyzer

        analyzer = PromptHistoryAnalyzer(sessions_dir=sessions_dir)
        sessions = analyzer.extract_sessions(days_back=30)
        patterns = analyzer.analyze_prompt_patterns(sessions, min_frequency=1)

        assert len(patterns) >= 1
        # Should find topics from our prompts
        all_keywords = []
        for p in patterns:
            all_keywords.extend(p.keywords)

    def test_analyze_priorities(self, sessions_dir):
        from intelligence.prompt_history import PromptHistoryAnalyzer

        analyzer = PromptHistoryAnalyzer(sessions_dir=sessions_dir)
        sessions = analyzer.extract_sessions(days_back=30)
        priorities = analyzer.analyze_priorities(sessions)

        # Should detect "fix" category from "fix the authentication bug"
        categories = [p.category for p in priorities]
        assert "fix" in categories or "test" in categories

    def test_calculate_urgency(self):
        from intelligence.prompt_history import PromptHistoryAnalyzer

        analyzer = PromptHistoryAnalyzer()
        assert analyzer._calculate_urgency("fix the urgent bug") >= 0.9
        assert analyzer._calculate_urgency("add a feature") == 0.0

    def test_categorize_prompt(self):
        from intelligence.prompt_history import PromptHistoryAnalyzer

        analyzer = PromptHistoryAnalyzer()
        assert "fix" in analyzer._categorize_prompt("fix the authentication bug")
        assert "feature" in analyzer._categorize_prompt("add a new feature")
        assert "test" in analyzer._categorize_prompt("test the endpoint")
        assert "refactor" in analyzer._categorize_prompt("refactor the module")
