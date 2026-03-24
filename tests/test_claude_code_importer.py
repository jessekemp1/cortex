"""Tests for Claude Code data importer."""

import json

import pytest


@pytest.fixture
def importer(tmp_path):
    from intelligence.claude_code_importer import ClaudeCodeImporter

    claude_dir = tmp_path / ".claude"
    cortex_dir = tmp_path / ".cortex"
    claude_dir.mkdir()
    cortex_dir.mkdir()
    return ClaudeCodeImporter(claude_dir=claude_dir, cortex_dir=cortex_dir)


class TestImportProjectPatterns:
    def test_imports_project_index(self, importer, tmp_path):
        # Create project index
        portfolio_dir = importer.claude_dir / "portfolio"
        portfolio_dir.mkdir()
        projects = [
            {"name": "cortex", "language": "python", "active": True, "commits_7d": 5},
            {"name": "vortex", "language": "go", "active": False, "commits_7d": 0},
        ]
        with open(portfolio_dir / "project_index.json", "w") as f:
            json.dump(projects, f)

        result = importer.import_project_patterns()
        assert result["status"] == "imported"
        assert result["projects"] == 2
        assert result["active"] == 1
        assert "python" in result["languages"]

    def test_skips_when_no_index(self, importer):
        result = importer.import_project_patterns()
        assert result["status"] == "skipped"


class TestImportAntiPatterns:
    def test_extracts_anti_patterns_from_markdown(self, importer):
        memories_dir = importer.claude_dir / "memories"
        memories_dir.mkdir()
        content = """# Anti-Patterns

- Don't commit .env files to git
- Never use eval() on user input
- Avoid using global state for configuration
- Always validate input at system boundaries
"""
        (memories_dir / "anti-patterns.md").write_text(content)

        result = importer.import_anti_patterns()
        assert result["status"] == "imported"
        assert result["count"] >= 3

    def test_skips_when_no_files(self, importer):
        result = importer.import_anti_patterns()
        assert result["status"] == "skipped"


class TestImportToolPreferences:
    def test_imports_settings(self, importer):
        settings = {
            "permissions": {"allow": ["Bash(npm *)", "Bash(git *)"]},
            "model": "opus",
            "env": {"DEBUG": "1", "NODE_ENV": "development"},
        }
        with open(importer.claude_dir / "settings.json", "w") as f:
            json.dump(settings, f)

        result = importer.import_tool_preferences()
        assert result["status"] == "imported"
        assert "auto_approved_tools" in result["keys"]
        assert "preferred_model" in result["keys"]

    def test_skips_when_no_settings(self, importer):
        result = importer.import_tool_preferences()
        assert result["status"] == "skipped"


class TestImportSessionTopics:
    def test_imports_session_data(self, importer):
        sessions_dir = importer.claude_dir / "conversations"
        sessions_dir.mkdir()

        for i, topic in enumerate(["fix the auth bug", "implement user search", "debug the crash"]):
            session = {"messages": [{"role": "user", "content": topic}]}
            with open(sessions_dir / f"session_{i}.json", "w") as f:
                json.dump(session, f)

        result = importer.import_session_topics()
        assert result["status"] == "imported"
        assert result["sessions_analyzed"] == 3

    def test_skips_when_no_sessions(self, importer):
        result = importer.import_session_topics()
        assert result["status"] == "skipped"


class TestImportAll:
    def test_returns_error_when_no_claude_dir(self, tmp_path):
        from intelligence.claude_code_importer import ClaudeCodeImporter

        importer = ClaudeCodeImporter(
            claude_dir=tmp_path / "nonexistent",
            cortex_dir=tmp_path / ".cortex",
        )
        result = importer.import_all()
        assert "error" in result

    def test_runs_all_importers(self, importer):
        result = importer.import_all()
        assert "project_patterns" in result
        assert "anti_patterns" in result
        assert "tool_preferences" in result
        assert "session_topics" in result


class TestImportStatus:
    def test_no_imports(self, importer):
        status = importer.get_import_status()
        assert status["status"] == "no_imports"

    def test_after_import(self, importer):
        # Create project index
        portfolio_dir = importer.claude_dir / "portfolio"
        portfolio_dir.mkdir()
        with open(portfolio_dir / "project_index.json", "w") as f:
            json.dump([{"name": "test", "active": True}], f)

        importer.import_project_patterns()

        status = importer.get_import_status()
        assert status["status"] == "imported"
        assert "project_patterns" in status["files"]
