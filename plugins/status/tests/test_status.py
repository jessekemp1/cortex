#!/usr/bin/env python3
"""
Tests for Status Plugin
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cortex.plugins.status.plugin import StatusPlugin


class TestStatusPlugin:
    """Test suite for status plugin."""

    @pytest.fixture
    def plugin_dir(self):
        """Get plugin directory."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def plugin(self, plugin_dir):
        """Create plugin instance."""
        return StatusPlugin(plugin_dir)

    @pytest.fixture
    def temp_git_repo(self):
        """Create temporary git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # Initialize git repo
            import subprocess

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
            )
            # Create initial commit
            (repo_path / "test.txt").write_text("initial")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True
            )
            yield repo_path

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is loaded correctly."""
        assert plugin.metadata.name == "status"
        assert plugin.metadata.version == "1.0.0"
        assert "status" in plugin.metadata.description.lower()
        assert "core" in plugin.metadata.tags

    def test_plugin_help(self, plugin):
        """Test help() returns documentation."""
        help_text = plugin.help()
        assert "status" in help_text.lower()
        assert "Usage" in help_text
        assert "--quick" in help_text

    def test_execute_help(self, plugin, capsys):
        """Test --help flag."""
        result = plugin.execute(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Status Plugin" in captured.out

    def test_config_loading(self, plugin):
        """Test configuration loading."""
        config = plugin.config
        assert isinstance(config, dict)
        assert "show_git" in config
        assert "projects" in config

    def test_dependency_check(self, plugin):
        """Test dependency checking."""
        missing = plugin.check_dependencies()
        assert isinstance(missing, list)
        # Status has no required dependencies
        assert len(missing) == 0

    @patch("subprocess.run")
    def test_quick_status(self, mock_run, plugin, capsys):
        """Test --quick option."""
        # Mock git status
        mock_run.return_value = Mock(returncode=0, stdout="main\n", stderr="")

        result = plugin.execute(["--quick"], current_dir=Path.cwd())
        assert result == 0

        captured = capsys.readouterr()
        assert "Quick Status" in captured.out

    def test_get_git_status(self, plugin, temp_git_repo):
        """Test git status retrieval."""
        # Create a modified file
        (temp_git_repo / "modified.txt").write_text("changed")

        branch, modified, untracked = plugin._get_git_status(temp_git_repo)

        assert branch == "main" or branch == "master"  # Default branch name varies
        assert untracked == 1  # modified.txt is untracked

    def test_get_git_status_not_a_repo(self, plugin):
        """Test git status in non-git directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            branch, modified, untracked = plugin._get_git_status(Path(tmpdir))
            assert branch is None
            assert modified == 0
            assert untracked == 0

    @patch("subprocess.run")
    def test_is_port_in_use(self, mock_run, plugin):
        """Test port checking."""
        # Port in use
        mock_run.return_value = Mock(returncode=0, stdout="12345\n", stderr="")
        assert plugin._is_port_in_use(8000) is True

        # Port not in use
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
        assert plugin._is_port_in_use(9999) is False

    @patch("subprocess.run")
    def test_get_pid_for_port(self, mock_run, plugin):
        """Test getting PID for port."""
        # Port has PID
        mock_run.return_value = Mock(returncode=0, stdout="12345\n", stderr="")
        pid = plugin._get_pid_for_port(8000)
        assert pid == 12345

        # Port not in use
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
        pid = plugin._get_pid_for_port(9999)
        assert pid is None

    def test_get_recent_commits_data(self, plugin, temp_git_repo):
        """Test getting recent commits."""
        commits = plugin._get_recent_commits_data(temp_git_repo, 10)
        assert isinstance(commits, list)
        assert len(commits) >= 1  # At least the initial commit
        if commits:
            commit_hash, message, time_ago = commits[0]
            assert len(commit_hash) > 0
            assert "Initial commit" in message
            assert "ago" in time_ago

    def test_get_service_name(self, plugin):
        """Test service name mapping."""
        assert "VortexV2 API" in plugin._get_service_name("vortex", 8000)
        assert "Alpha Arena" in plugin._get_service_name("arena", 8502)

    @patch("subprocess.run")
    def test_get_intelligence_suggestions_not_found(self, mock_run, plugin):
        """Test intelligence suggestions when analyzer not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            suggestions = plugin._get_intelligence_suggestions(Path(tmpdir), verbose=False)
            assert suggestions == []

    @patch("subprocess.run")
    def test_get_intelligence_suggestions_success(self, mock_run, plugin, temp_git_repo):
        """Test intelligence suggestions with successful analyzer."""
        # Create fake analyzer
        analyzer_dir = temp_git_repo / "cortex" / "intelligence" / "status"
        analyzer_dir.mkdir(parents=True)
        analyzer_path = analyzer_dir / "analyze.py"
        analyzer_path.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps([]))")

        # Mock subprocess to return JSON
        mock_run.return_value = Mock(
            returncode=0,
            stdout='[{"title": "Test", "confidence": 95, "risk": "safe", "files": []}]',
            stderr="",
        )

        suggestions = plugin._get_intelligence_suggestions(temp_git_repo, verbose=False)
        assert isinstance(suggestions, list)

    def test_project_status_unknown_project(self, plugin, capsys):
        """Test project status with unknown project."""
        result = plugin.execute(["--project", "unknown"], current_dir=Path.cwd())
        assert result == 1
        captured = capsys.readouterr()
        assert "Unknown project" in captured.err

    @patch("subprocess.run")
    def test_full_status(self, mock_run, plugin, capsys):
        """Test full status execution."""

        # Mock git commands
        def mock_subprocess(*args, **kwargs):
            cmd = args[0]
            if "rev-parse" in cmd:
                return Mock(returncode=0, stdout="main\n", stderr="")
            elif "status" in cmd:
                return Mock(returncode=0, stdout="", stderr="")
            elif "log" in cmd:
                return Mock(returncode=0, stdout="abc123 Test commit (2 hours ago)\n", stderr="")
            elif "lsof" in cmd:
                return Mock(returncode=1, stdout="", stderr="")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_subprocess

        result = plugin.execute([], current_dir=Path.cwd())
        assert result == 0

        captured = capsys.readouterr()
        assert "Cortex Portfolio Status" in captured.out
        assert "Git Status" in captured.out


class TestStatusIntegration:
    """Integration tests for status plugin."""

    @pytest.fixture
    def plugin_dir(self):
        """Get plugin directory."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def plugin(self, plugin_dir):
        """Create plugin instance."""
        return StatusPlugin(plugin_dir)

    def test_full_workflow_in_real_repo(self, plugin):
        """Test full workflow in actual Dev repo."""
        # This tests against the real repository
        dev_dir = Path(__file__).parent.parent.parent.parent.parent
        assert dev_dir.name == "Dev"

        # Should not crash
        result = plugin.execute(["--quick"], current_dir=dev_dir)
        assert result == 0

    @patch("subprocess.run")
    def test_keyboard_interrupt(self, mock_run, plugin):
        """Test keyboard interrupt handling."""
        mock_run.side_effect = KeyboardInterrupt()

        result = plugin.execute([], current_dir=Path.cwd())
        assert result == 130


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
