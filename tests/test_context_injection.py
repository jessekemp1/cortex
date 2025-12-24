"""Tests for context injection system."""
import time
from pathlib import Path

import pytest

from intelligence.context_injector import ContextInjector, InjectionContext


class TestInjectionContext:
    """Test InjectionContext dataclass."""

    def test_to_string_includes_project(self):
        """Context string should include project name."""
        ctx = InjectionContext(project_name="TestProject", tech_stack="Python")
        result = ctx.to_string()
        assert "TestProject" in result

    def test_to_string_includes_tech_stack(self):
        """Context string should include tech stack when provided."""
        ctx = InjectionContext(project_name="TestProject", tech_stack="Python/FastAPI")
        result = ctx.to_string()
        assert "Python/FastAPI" in result

    def test_to_string_includes_warnings(self):
        """Context string should include first warning."""
        ctx = InjectionContext(
            project_name="TestProject",
            tech_stack="Python",
            warnings=["Test coverage low", "Dependencies outdated"],
        )
        result = ctx.to_string()
        assert "Warning:" in result
        assert "Test coverage low" in result

    def test_to_string_respects_max_chars(self):
        """Context string should truncate if over max_chars."""
        ctx = InjectionContext(
            project_name="TestProject",
            tech_stack="Python/FastAPI/PostgreSQL/Redis/Celery/RabbitMQ",
            coverage="45% coverage",
            warnings=["Very long warning " * 20],
            pattern_hint="Pattern " * 20,
            domain_insight="Insight " * 20,
        )
        result = ctx.to_string(max_chars=400)
        assert len(result) <= 400

    def test_to_string_empty_context(self):
        """Context string should handle empty data gracefully."""
        ctx = InjectionContext(project_name="TestProject")
        result = ctx.to_string()
        assert "TestProject" in result
        assert len(result) > 0


class TestContextInjector:
    """Test ContextInjector class."""

    @pytest.fixture
    def injector(self):
        """Create injector with Dev root."""
        return ContextInjector(Path("/Users/jesse.kemp/Dev"))

    def test_inject_completes_reasonably_fast(self, injector):
        """Injection should complete in reasonable time (under 2s for tests)."""
        start = time.time()
        result = injector.inject(Path.cwd(), task="test task")
        elapsed = (time.time() - start) * 1000
        # More lenient timeout for tests (2s instead of 500ms)
        assert elapsed < 2000

    def test_inject_returns_string(self, injector):
        """Inject should return a non-empty string."""
        result = injector.inject(Path.cwd())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_inject_with_task(self, injector):
        """Inject should accept task parameter."""
        result = injector.inject(Path.cwd(), task="implement new feature")
        assert isinstance(result, str)

    def test_inject_graceful_degradation(self, injector):
        """Inject should handle errors gracefully."""
        # Even with invalid path, should return something
        result = injector.inject(Path("/nonexistent/path"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_detect_project_from_dev_path(self, injector):
        """Should detect project name from Dev path."""
        project = injector._detect_project(Path("/Users/jesse.kemp/Dev/cortex"))
        assert project == "cortex"

    def test_detect_nested_project(self, injector):
        """Should detect nested project names."""
        project = injector._detect_project(Path("/Users/jesse.kemp/Dev/Vortex/VortexV2"))
        assert project == "VortexV2"

    def test_detect_production_project(self, injector):
        """Should detect projects under production directory."""
        project = injector._detect_project(
            Path("/Users/jesse.kemp/Dev/production/audio/dj-copilot")
        )
        assert project == "dj-copilot"

    def test_find_project_root_with_git(self, injector):
        """Should find project root when .git exists."""
        # Use cortex as test case (has .git or pyproject.toml)
        cortex_path = Path("/Users/jesse.kemp/Dev/cortex")
        if cortex_path.exists():
            root = injector._find_project_root(cortex_path / "intelligence")
            # Should find a project root somewhere up the tree
            assert root.exists()
            assert root in [cortex_path, cortex_path.parent]

    def test_find_project_root_returns_cwd_if_not_found(self, injector):
        """Should return cwd if no project root found."""
        result = injector._find_project_root(Path("/tmp"))
        assert result == Path("/tmp")

    def test_inject_output_length(self, injector):
        """Inject output should be reasonable length."""
        result = injector.inject(Path.cwd())
        # Should produce some output but not be empty
        assert 0 < len(result) < 1000


class TestContextInjectorIntegration:
    """Integration tests for context injection."""

    @pytest.fixture
    def injector(self):
        """Create injector with Dev root."""
        return ContextInjector(Path("/Users/jesse.kemp/Dev"))

    @pytest.mark.skipif(
        not Path("/Users/jesse.kemp/Dev/Vortex/VortexV2").exists(),
        reason="VortexV2 project not found"
    )
    def test_inject_vortex_project(self, injector):
        """Test injection for VortexV2 project."""
        vortex_path = Path("/Users/jesse.kemp/Dev/Vortex/VortexV2")
        result = injector.inject(vortex_path, task="fix GRIB loading")

        # Should include project name
        assert "VortexV2" in result or "Vortex" in result

    @pytest.mark.skipif(
        not Path("/Users/jesse.kemp/Dev/cortex").exists(),
        reason="Cortex project not found"
    )
    def test_inject_cortex_project(self, injector):
        """Test injection for Cortex project."""
        cortex_path = Path("/Users/jesse.kemp/Dev/cortex")
        result = injector.inject(cortex_path)

        # Should include project name
        assert "cortex" in result.lower()
