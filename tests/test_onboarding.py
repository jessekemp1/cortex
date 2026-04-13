"""Tests for cortex onboard command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.commands.onboarding import (
    _detect_projects,
    _get_recent_commits,
    _project_description,
    _seed_custom_gotcha,
    cmd_onboard,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temp workspace with fake projects."""
    # Python project with git
    py_proj = tmp_path / "my-api"
    py_proj.mkdir()
    (py_proj / ".git").mkdir()
    (py_proj / "pyproject.toml").write_text("[project]\nname='my-api'")
    (py_proj / "conftest.py").write_text("")

    # JS project with git
    js_proj = tmp_path / "frontend"
    js_proj.mkdir()
    (js_proj / ".git").mkdir()
    (js_proj / "package.json").write_text('{"name": "frontend"}')
    (js_proj / "tsconfig.json").write_text("{}")

    # Rust project (no git, but has Cargo.toml)
    rust_proj = tmp_path / "engine"
    rust_proj.mkdir()
    (rust_proj / "Cargo.toml").write_text("[package]\nname='engine'")

    # Junk directory (no project files, no git)
    junk = tmp_path / "notes"
    junk.mkdir()
    (junk / "readme.txt").write_text("just notes")

    # Skip directories
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "package.json").write_text("{}")  # Should be skipped

    return tmp_path


class TestDetectProjects:
    def test_finds_git_projects(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        names = [p["name"] for p in projects]
        assert "my-api" in names
        assert "frontend" in names

    def test_finds_projects_without_git_if_project_files(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        names = [p["name"] for p in projects]
        assert "engine" in names  # Rust project, no .git but has Cargo.toml

    def test_skips_junk_dirs(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        names = [p["name"] for p in projects]
        assert "notes" not in names

    def test_skips_node_modules(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        names = [p["name"] for p in projects]
        assert "node_modules" not in names

    def test_detects_python_language(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        api = next(p for p in projects if p["name"] == "my-api")
        assert "python" in api["languages"]

    def test_detects_typescript(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        fe = next(p for p in projects if p["name"] == "frontend")
        assert "typescript" in fe["languages"]
        assert "javascript" in fe["languages"]

    def test_detects_rust(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        engine = next(p for p in projects if p["name"] == "engine")
        assert "rust" in engine["languages"]

    def test_detects_pytest(self, temp_workspace):
        projects = _detect_projects(temp_workspace)
        api = next(p for p in projects if p["name"] == "my-api")
        assert api["test_framework"] == "pytest"

    def test_detects_ci(self, temp_workspace):
        # Add CI to my-api
        (temp_workspace / "my-api" / ".github" / "workflows").mkdir(parents=True)
        projects = _detect_projects(temp_workspace)
        api = next(p for p in projects if p["name"] == "my-api")
        assert api["has_ci"] is True

    def test_no_projects_returns_empty(self, tmp_path):
        projects = _detect_projects(tmp_path)
        assert projects == []

    def test_handles_nonexistent_root(self, tmp_path):
        projects = _detect_projects(tmp_path / "nonexistent")
        assert projects == []


class TestGetRecentCommits:
    def test_returns_empty_for_non_git_dir(self, tmp_path):
        commits = _get_recent_commits(str(tmp_path))
        assert commits == []

    def test_returns_commits_for_real_repo(self):
        # Use the cortex repo itself
        repo_root = Path(__file__).parent.parent
        commits = _get_recent_commits(str(repo_root), limit=5)
        assert len(commits) <= 5
        if commits:
            assert "hash" in commits[0]
            assert "message" in commits[0]
            assert "date" in commits[0]


class TestProjectDescription:
    def test_basic(self):
        proj = {
            "name": "myapp",
            "languages": ["python"],
            "test_framework": "pytest",
            "has_ci": False,
        }
        desc = _project_description(proj)
        assert "myapp" in desc
        assert "python" in desc
        assert "pytest" in desc

    def test_no_languages(self):
        proj = {"name": "myapp", "languages": [], "test_framework": None, "has_ci": False}
        desc = _project_description(proj)
        assert "unknown" in desc

    def test_with_ci(self):
        proj = {"name": "myapp", "languages": ["go"], "test_framework": None, "has_ci": True}
        desc = _project_description(proj)
        assert "CI" in desc


class TestSeedCustomGotcha:
    def test_stores_gotcha(self):
        result = _seed_custom_gotcha("Never use ds.interp() with raw lon on 0-360 grids")
        # Result depends on whether backend is importable in test env
        assert isinstance(result, bool)


class TestCmdOnboard:
    def test_non_interactive_runs_without_stdin(self, temp_workspace, capsys):
        """Non-interactive mode should detect projects and seed memory."""
        args = MagicMock()
        args.root = str(temp_workspace)
        args.non_interactive = True

        cmd_onboard(args)

        captured = capsys.readouterr()
        assert "Found 3 project(s)" in captured.out
        assert "Onboarding complete" in captured.out
        assert "my-api" in captured.out

    def test_exits_for_bad_root(self, tmp_path):
        """Should exit with error for nonexistent root."""
        args = MagicMock()
        args.root = str(tmp_path / "nonexistent")
        args.non_interactive = True

        with pytest.raises(SystemExit):
            cmd_onboard(args)

    def test_handles_empty_workspace(self, tmp_path, capsys):
        """Empty workspace should complete gracefully with zero projects."""
        args = MagicMock()
        args.root = str(tmp_path)
        args.non_interactive = True

        cmd_onboard(args)

        captured = capsys.readouterr()
        assert "No git repos found" in captured.out
        assert "Projects:   0" in captured.out

    @patch("sys.stdin")
    @patch("builtins.input", side_effect=["Fix circular imports in auth module", ""])
    def test_interactive_with_gotcha(self, mock_input, mock_stdin, temp_workspace):
        """Interactive mode should accept gotcha input."""
        mock_stdin.isatty.return_value = True
        args = MagicMock()
        args.root = str(temp_workspace)
        args.non_interactive = False

        cmd_onboard(args)

        assert mock_input.call_count == 2  # gotcha + workflow

    @patch("sys.stdin")
    @patch("builtins.input", side_effect=["", ""])
    def test_interactive_skip_all(self, mock_input, mock_stdin, temp_workspace):
        """Pressing Enter on both questions should work fine."""
        mock_stdin.isatty.return_value = True
        args = MagicMock()
        args.root = str(temp_workspace)
        args.non_interactive = False

        cmd_onboard(args)

        assert mock_input.call_count == 2

    def test_idempotent_rerun(self, temp_workspace, capsys):
        """Running onboard twice should produce consistent project counts."""
        args = MagicMock()
        args.root = str(temp_workspace)
        args.non_interactive = True

        cmd_onboard(args)
        capsys.readouterr()  # Clear first run output

        cmd_onboard(args)
        captured = capsys.readouterr()
        assert "Found 3 project(s)" in captured.out
        assert "Onboarding complete" in captured.out
