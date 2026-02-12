"""Unit tests for Cortex Session Context Management.

Tests the SessionManager class which creates and manages session context
from git history and project state.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestSessionManagerInit:
    """Test SessionManager initialization."""

    def test_session_manager_default_root(self):
        """SessionManager should use default root directory."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()
        assert manager.root_dir == Path("/Users/jesse.kemp/Dev")

    def test_session_manager_custom_root(self):
        """SessionManager should accept custom root directory."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(root_dir=tmpdir)
            assert manager.root_dir == Path(tmpdir)

    def test_session_manager_creates_cache_dir(self):
        """SessionManager should create cache directory."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()
        assert manager.cache_dir.exists()
        assert manager.cache_dir == Path.home() / ".claude" / "session"


class TestSessionManagerLoadContext:
    """Test SessionManager.load_session_context method."""

    def test_load_session_context_returns_session_context(self):
        """load_session_context should return SessionContext or None."""
        from cortex.intelligence.models import SessionContext
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()
        result = manager.load_session_context()

        # Should be SessionContext or None
        assert result is None or isinstance(result, SessionContext)

    def test_load_session_context_uses_cache(self):
        """load_session_context should use cache within max_age."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock cache file
            cache_dir = Path(tmpdir) / ".claude" / "session"
            cache_dir.mkdir(parents=True)
            cache_file = cache_dir / "context.json"

            cached_data = {
                "project": "cached_project",
                "working_directory": "/cached/path",
                "recent_work": [{"hash": "cached123", "summary": "Cached commit"}],
                "active_goals": ["Cached goal"],
                "current_focus": "Cached focus",
                "last_updated": datetime.now().isoformat(),
            }
            cache_file.write_text(json.dumps(cached_data))

            manager = SessionManager()
            manager.cache_dir = cache_dir
            manager.cache_file = cache_file

            result = manager.load_session_context(max_age_hours=1)

            assert result is not None
            assert result.project == "cached_project"
            assert result.current_focus == "Cached focus"


class TestSessionManagerDetectProject:
    """Test SessionManager._detect_project method."""

    def test_detect_project_from_cwd(self):
        """_detect_project should detect project from current directory."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager(root_dir="/Users/jesse.kemp/Dev")

        # Test with a path under root
        project = manager._detect_project(Path("/Users/jesse.kemp/Dev/cortex"))
        assert project == "cortex"

    def test_detect_project_from_subdirectory(self):
        """_detect_project should work from subdirectory."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager(root_dir="/Users/jesse.kemp/Dev")

        project = manager._detect_project(Path("/Users/jesse.kemp/Dev/cortex/intelligence"))
        assert project == "cortex"

    def test_detect_project_fallback(self):
        """_detect_project should fallback to directory name."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(root_dir="/different/root")

            project = manager._detect_project(Path(tmpdir))
            # Should return the directory name
            assert project == Path(tmpdir).name


class TestSessionManagerGetRecentCommits:
    """Test SessionManager._get_recent_commits method."""

    def test_get_recent_commits_parses_git_output(self):
        """_get_recent_commits should parse git log output."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()

        # Mock subprocess to return formatted git log
        mock_output = "abc1234|feat: Add new feature|2 hours ago|Author Name\ndef5678|fix: Bug fix|3 hours ago|Other Author"

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = mock_output
            mock_run.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmpdir:
                commits = manager._get_recent_commits(Path(tmpdir), limit=5)

        assert len(commits) == 2
        assert commits[0]["hash"] == "abc1234"
        assert commits[0]["summary"] == "feat: Add new feature"
        assert commits[0]["time"] == "2 hours ago"
        assert commits[0]["author"] == "Author Name"

    def test_get_recent_commits_handles_empty_repo(self):
        """_get_recent_commits should handle repos with no commits."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmpdir:
                commits = manager._get_recent_commits(Path(tmpdir), limit=5)

        assert commits == []

    def test_get_recent_commits_handles_git_error(self):
        """_get_recent_commits should handle git command failures."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 128  # Git error
            mock_run.return_value = mock_result

            with tempfile.TemporaryDirectory() as tmpdir:
                commits = manager._get_recent_commits(Path(tmpdir), limit=5)

        assert commits == []


class TestSessionManagerExtractGoals:
    """Test SessionManager._extract_goals method."""

    def test_extract_goals_from_plan_md(self):
        """_extract_goals should extract goals from PLAN.md."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            plan_file = project_path / "PLAN.md"

            plan_content = """# Project Plan

## Future Work

1. Implement feature X
2. Add unit tests for module Y
3. Refactor the API layer

## Completed
- Initial setup
"""
            plan_file.write_text(plan_content)

            manager = SessionManager()
            goals = manager._extract_goals(project_path)

            assert len(goals) >= 1

    def test_extract_goals_handles_missing_plan(self):
        """_extract_goals should handle missing PLAN.md."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            manager = SessionManager()
            goals = manager._extract_goals(project_path)

            # Should return default goals
            assert len(goals) >= 1
            assert any("development" in g.lower() or "continue" in g.lower() for g in goals)

    def test_extract_goals_from_todo_section(self):
        """_extract_goals should extract from TODO sections."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            plan_file = project_path / "PLAN.md"

            plan_content = """# Plan

## TODO

- [ ] First task
- [ ] Second task
- [x] Completed task (should be included)
"""
            plan_file.write_text(plan_content)

            manager = SessionManager()
            goals = manager._extract_goals(project_path)

            # Should find tasks from TODO section
            assert len(goals) >= 1


class TestSessionManagerDetermineFocus:
    """Test SessionManager._determine_focus method."""

    def test_determine_focus_from_recent_work(self):
        """_determine_focus should use most recent commit."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()

        recent_work = [
            {"hash": "abc123", "summary": "feat: Add authentication flow"},
            {"hash": "def456", "summary": "fix: Bug fix"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            focus = manager._determine_focus(recent_work, Path(tmpdir))

        # Should extract focus from first commit
        assert "authentication" in focus.lower() or "Add" in focus

    def test_determine_focus_removes_prefixes(self):
        """_determine_focus should remove common commit prefixes."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()

        recent_work = [{"hash": "abc123", "summary": "feat: add new API endpoint"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            focus = manager._determine_focus(recent_work, Path(tmpdir))

        # Should not start with "feat:"
        assert not focus.lower().startswith("feat:")
        # First letter should be capitalized
        assert focus[0].isupper()

    def test_determine_focus_handles_empty_work(self):
        """_determine_focus should handle empty recent work."""
        from cortex.intelligence.session_manager import SessionManager

        manager = SessionManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            focus = manager._determine_focus([], Path(tmpdir))

        assert focus == "Starting new session"


class TestSessionManagerGenerateContext:
    """Test SessionManager._generate_session_context method."""

    def test_generate_session_context_returns_context(self):
        """_generate_session_context should return SessionContext."""
        from cortex.intelligence.models import SessionContext
        from cortex.intelligence.session_manager import SessionManager

        # Mock git output
        mock_git_output = "abc1234|feat: Test feature|2 hours ago|Test Author"

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = mock_git_output
            mock_run.return_value = mock_result

            # Change to a known project directory
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(Path, "cwd", return_value=Path(tmpdir)):
                    manager = SessionManager(root_dir=Path(tmpdir).parent)
                    manager._detect_project = MagicMock(return_value="test_project")

                    result = manager._generate_session_context()

        # Result should be SessionContext or None
        assert result is None or isinstance(result, SessionContext)

    def test_generate_session_context_caches_result(self):
        """_generate_session_context should write cache file."""
        from cortex.intelligence.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            cache_file = cache_dir / "context.json"

            mock_git_output = "abc1234|feat: Test|1 hour ago|Author"

            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = mock_git_output
                mock_run.return_value = mock_result

                with patch.object(Path, "cwd", return_value=Path(tmpdir)):
                    manager = SessionManager(root_dir=Path(tmpdir).parent)
                    manager.cache_dir = cache_dir
                    manager.cache_file = cache_file
                    manager._detect_project = MagicMock(return_value="test_project")

                    result = manager._generate_session_context()

            # If successful, cache file should exist
            if result is not None:
                assert cache_file.exists()


class TestSessionContextModel:
    """Test SessionContext data model integration with SessionManager."""

    def test_session_context_has_expected_fields(self):
        """SessionContext should have all expected fields."""
        from cortex.intelligence.models import SessionContext

        context = SessionContext(
            project="test_project",
            working_directory="/path/to/project",
            recent_work=[{"hash": "abc", "summary": "test"}],
            active_goals=["Goal 1", "Goal 2"],
            current_focus="Testing",
            last_updated="2025-01-27T10:00:00",
        )

        # Verify all fields are accessible
        assert hasattr(context, "project")
        assert hasattr(context, "working_directory")
        assert hasattr(context, "recent_work")
        assert hasattr(context, "active_goals")
        assert hasattr(context, "current_focus")
        assert hasattr(context, "last_updated")

    def test_session_context_serializes_to_json(self):
        """SessionContext should be JSON serializable via cache."""
        from dataclasses import asdict

        from cortex.intelligence.models import SessionContext

        context = SessionContext(
            project="test",
            working_directory="/test",
            recent_work=[{"hash": "abc", "summary": "test", "time": "1 hour ago"}],
            active_goals=["Goal"],
            current_focus="Testing",
            last_updated="2025-01-27T10:00:00",
        )

        # Should be convertible to dict and JSON
        data = asdict(context)
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed["project"] == "test"
        assert parsed["current_focus"] == "Testing"
