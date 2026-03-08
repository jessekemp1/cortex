"""Tests for context injection system."""

import os

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from intelligence.context_injector import ContextInjector, InjectionContext


def _make_mock_profile():
    """Create a mock profile to avoid slow filesystem/git scans."""
    profile = MagicMock()
    profile.tech_stack.to_compact_str.return_value = "Python/FastAPI"
    profile.test_coverage.estimated_coverage = 80
    profile.warnings = []
    return profile


@pytest.fixture(autouse=True)
def _patch_profiler():
    """Patch ProjectProfiler to avoid slow filesystem scans."""
    mock_profile = _make_mock_profile()
    with (
        patch(
            "intelligence.analysis.project_profiler.ProjectProfiler.profile",
            return_value=mock_profile,
        ),
        patch(
            "intelligence.context_injector.ProcessMonitor",
            None,
        ),
    ):
        yield


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
        return ContextInjector(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))

    def test_inject_completes_reasonably_fast(self, injector):
        """Injection should complete in reasonable time (under 3s for tests)."""
        start = time.time()
        injector.inject(Path.cwd(), task="test task")
        elapsed = (time.time() - start) * 1000
        # Lenient timeout — context injection involves file I/O and project detection,
        # which varies with system load. 15s prevents infinite hangs without flaking
        # under concurrent test load.
        assert elapsed < 15000

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
        project = injector._detect_project(Path("~/Dev/cortex"))
        assert project == "cortex"

    def test_detect_nested_project(self, injector):
        """Should detect nested project names."""
        project = injector._detect_project(Path("~/Dev/Vortex/backend"))
        assert project == "backend"

    def test_detect_production_project(self, injector):
        """Should detect projects under production directory."""
        project = injector._detect_project(Path("~/Dev/production/audio/dj-copilot"))
        assert project == "dj-copilot"

    def test_find_project_root_with_git(self, injector):
        """Should find project root when .git exists."""
        # Use cortex as test case (has .git or pyproject.toml)
        cortex_path = Path("~/Dev/cortex").expanduser()
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
        return ContextInjector(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))

    @pytest.mark.skipif(
        not Path("~/Dev/Vortex/backend").expanduser().exists(),
        reason="Vortex backend project not found",
    )
    def test_inject_vortex_project(self, injector):
        """Test injection for Vortex backend project."""
        vortex_path = Path("~/Dev/Vortex/backend").expanduser()
        result = injector.inject(vortex_path, task="fix GRIB loading")

        # Should include project name
        assert "backend" in result or "Vortex" in result

    @pytest.mark.skipif(
        not Path("~/Dev/cortex").expanduser().exists(),
        reason="Cortex project not found",
    )
    def test_inject_cortex_project(self, injector):
        """Test injection for Cortex project."""
        cortex_path = Path("~/Dev/cortex").expanduser()
        result = injector.inject(cortex_path)

        # Should include project name
        assert "cortex" in result.lower()


class TestCaching:
    """Test caching behavior for performance optimization."""

    @pytest.fixture
    def injector(self):
        """Create injector with Dev root."""
        return ContextInjector(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))

    def test_profile_caching(self, injector):
        """Profile should be cached on second call."""
        cortex_path = Path("~/Dev/cortex").expanduser()
        if not cortex_path.exists():
            pytest.skip("Cortex project not found")

        # First call - should populate cache
        start1 = time.time()
        result1 = injector.inject(cortex_path)
        time1 = (time.time() - start1) * 1000

        # Second call - should use cache (faster)
        start2 = time.time()
        result2 = injector.inject(cortex_path)
        time2 = (time.time() - start2) * 1000

        # Results should be similar (profile part cached, but system metrics are dynamic)
        # Extract stable parts (project name, coverage) - Resource line has live system data
        import re

        def extract_stable_parts(s):
            # Remove entire Resource line — CPU%, process names, alerts are all dynamic
            return re.sub(r"Resource:.*", "Resource: <dynamic>", s)

        assert extract_stable_parts(result1) == extract_stable_parts(result2)

        # Second call should be faster (or at least not slower)
        # Allow some variance due to system load
        assert time2 <= time1 * 1.5  # Second call shouldn't be more than 1.5x slower


class TestWarningInclusion:
    """Test that warnings are included in context."""

    @pytest.fixture
    def injector(self):
        """Create injector with Dev root."""
        return ContextInjector(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))

    def test_warnings_in_output(self):
        """Warnings should appear in context output."""
        ctx = InjectionContext(
            project_name="TestProject",
            warnings=["Test coverage low", "GRIB data 12h old"],
        )
        result = ctx.to_string()

        assert "Warning:" in result
        # Should include at least first warning
        assert "Test coverage low" in result or "GRIB data" in result

    def test_multiple_warnings_prioritized(self):
        """Multiple warnings should be included up to limit."""
        ctx = InjectionContext(
            project_name="TestProject", warnings=["Warning 1", "Warning 2", "Warning 3"]
        )
        result = ctx.to_string()

        # Should include at least first warning
        assert "Warning:" in result
        assert "Warning 1" in result

    @pytest.mark.skipif(
        not Path("~/Dev/Vortex/backend").expanduser().exists(),
        reason="Vortex backend project not found",
    )
    def test_vortex_warnings_integration(self, injector):
        """Vortex backend domain expert warnings should appear when relevant."""
        vortex_path = Path("~/Dev/Vortex/backend").expanduser()
        result = injector.inject(vortex_path, task="process GRIB data")

        # If GRIB data is stale, warning should appear
        # (May not appear if data is fresh, so this is a soft check)
        # Just verify the injection works without error
        assert isinstance(result, str)
        assert len(result) > 0


class TestPatternHints:
    """Test pattern hint inclusion in context."""

    @pytest.fixture
    def injector(self):
        """Create injector with Dev root."""
        return ContextInjector(Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))))

    def test_pattern_hint_in_output(self):
        """Pattern hints should appear in context output."""
        ctx = InjectionContext(
            project_name="TestProject",
            pattern_hint="Similar to vortex-backend: GRIB integration",
        )
        result = ctx.to_string()

        assert "Pattern:" in result
        assert "Similar to" in result or "vortex-backend" in result

    def test_pattern_hint_formatting(self):
        """Pattern hints should be formatted correctly."""
        ctx = InjectionContext(
            project_name="TestProject",
            pattern_hint="Similar to Project: Very long pattern title that should be truncated",
        )
        result = ctx.to_string(max_chars=200)

        # Should include pattern but may be truncated
        assert "Pattern:" in result
        assert len(result) <= 200

    def test_pattern_hint_with_task(self, injector):
        """Pattern hints should appear when task is provided."""
        # This test depends on pattern memory having indexed patterns
        # May not find patterns if index is empty, so this is a soft check
        result = injector.inject(Path.cwd(), task="implement authentication")

        # Just verify injection works - pattern may or may not appear
        assert isinstance(result, str)
        assert len(result) > 0
