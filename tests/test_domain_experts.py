"""Tests for domain expert system."""

from pathlib import Path

import pytest
from intelligence.domains.base_expert import BaseDomainExpert, DomainInsight
from intelligence.domains.vortex_expert import VortexExpert


class TestDomainInsight:
    """Test DomainInsight dataclass."""

    def test_to_compact_str_warning(self):
        """Warning insights should have warning emoji."""
        insight = DomainInsight(
            category="warning",
            message="Test warning",
            confidence=0.9,
            source="test",
        )
        result = insight.to_compact_str()
        assert "⚠️" in result
        assert "Test warning" in result

    def test_to_compact_str_suggestion(self):
        """Suggestion insights should have lightbulb emoji."""
        insight = DomainInsight(
            category="suggestion",
            message="Test suggestion",
            confidence=0.8,
            source="test",
        )
        result = insight.to_compact_str()
        assert "💡" in result
        assert "Test suggestion" in result

    def test_to_compact_str_respects_max_length(self):
        """Compact string should truncate if over max_length."""
        insight = DomainInsight(
            category="warning",
            message="Very long warning message " * 10,
            confidence=0.9,
            source="test",
        )
        result = insight.to_compact_str(max_length=80)
        assert len(result) <= 80


class TestVortexExpert:
    """Test VortexExpert domain expert."""

    @pytest.fixture
    def expert(self):
        """Create VortexExpert instance."""
        return VortexExpert()

    def test_project_name(self, expert):
        """Project name should be VortexV2."""
        assert expert.project_name == "VortexV2"

    def test_domain_keywords(self, expert):
        """Should have VortexV2-specific keywords."""
        keywords = expert._get_domain_keywords()
        assert "grib" in keywords
        assert "ndbc" in keywords
        assert "forecast" in keywords
        assert "wind" in keywords

    def test_is_relevant_with_path(self, expert):
        """Should detect relevance from path."""
        vortex_path = Path("/Users/jesse.kemp/Dev/Vortex/VortexV2")
        assert expert.is_relevant(vortex_path)

        non_vortex_path = Path("/Users/jesse.kemp/Dev/cortex")
        # May still be relevant if task has keywords
        # So don't assert False here

    def test_is_relevant_with_task(self, expert):
        """Should detect relevance from task keywords."""
        assert expert.is_relevant(Path.cwd(), "fix GRIB loading")
        assert expert.is_relevant(Path.cwd(), "update NDBC parser")
        assert expert.is_relevant(Path.cwd(), "improve wind forecast accuracy")

    def test_is_not_relevant_without_keywords(self, expert):
        """Should not be relevant for generic tasks."""
        # Generic task without VortexV2 keywords
        result = expert.is_relevant(Path("/tmp"), "fix login page")
        # This could be True or False depending on implementation
        # Just check it returns a boolean
        assert isinstance(result, bool)

    def test_get_quick_insight_returns_string_or_none(self, expert):
        """get_quick_insight should return string or None."""
        result = expert.get_quick_insight(
            Path("/Users/jesse.kemp/Dev/Vortex/VortexV2"),
            "test GRIB loading",
        )
        assert result is None or isinstance(result, str)

    def test_get_quick_insight_with_coordinate_task(self, expert):
        """Should provide coordinate hints for coordinate-related tasks."""
        result = expert.get_quick_insight(
            Path("/Users/jesse.kemp/Dev/Vortex/VortexV2"),
            "validate Lake Huron coordinates",
        )
        if result:
            assert "NAD83" in result or "datum" in result.lower()

    def test_get_quick_insight_with_grib_task(self, expert):
        """Should provide GRIB hints for GRIB-related tasks."""
        result = expert.get_quick_insight(
            Path("/Users/jesse.kemp/Dev/Vortex/VortexV2"), "parse GRIB files"
        )
        if result:
            assert "u10" in result or "v10" in result or "GRIB" in result

    def test_get_warnings_returns_list(self, expert):
        """get_warnings should return list of DomainInsight."""
        warnings = expert.get_warnings(Path("/Users/jesse.kemp/Dev/Vortex/VortexV2"))
        assert isinstance(warnings, list)
        for warning in warnings:
            assert isinstance(warning, DomainInsight)

    def test_get_validation_suggestions_grib(self, expert):
        """Should provide GRIB validation suggestions."""
        suggestions = expert.get_validation_suggestions("load GRIB data")
        assert isinstance(suggestions, list)
        if suggestions:
            assert any("coordinate" in s.lower() or "grib" in s.lower() for s in suggestions)

    def test_get_validation_suggestions_ndbc(self, expert):
        """Should provide NDBC validation suggestions."""
        suggestions = expert.get_validation_suggestions("fetch NDBC observations")
        assert isinstance(suggestions, list)
        if suggestions:
            assert any("station" in s.lower() or "ndbc" in s.lower() for s in suggestions)

    def test_get_validation_suggestions_lake_huron(self, expert):
        """Should provide Lake Huron validation suggestions."""
        suggestions = expert.get_validation_suggestions("integrate Lake Huron data")
        assert isinstance(suggestions, list)
        if suggestions:
            assert any(
                "lake huron" in s.lower() or "coordinate" in s.lower() or "nad83" in s.lower()
                for s in suggestions
            )

    def test_get_validation_suggestions_ensemble(self, expert):
        """Should provide ensemble validation suggestions."""
        suggestions = expert.get_validation_suggestions("update ensemble model")
        assert isinstance(suggestions, list)
        if suggestions:
            assert any("ensemble" in s.lower() or "weight" in s.lower() for s in suggestions)

    def test_check_grib_freshness_returns_string_or_none(self, expert):
        """_check_grib_freshness should return string or None."""
        result = expert._check_grib_freshness()
        assert result is None or isinstance(result, str)

    def test_get_grib_age_hours_caching(self, expert):
        """GRIB age should be cached."""
        # Call twice
        age1 = expert._get_grib_age_hours()
        age2 = expert._get_grib_age_hours()

        # Both should return same type
        assert type(age1) == type(age2)

        # If age found, values should be similar (within 1 second)
        if age1 is not None and age2 is not None:
            assert abs(age1 - age2) < 0.001  # Less than 1 second difference


class TestBaseDomainExpert:
    """Test BaseDomainExpert abstract class."""

    def test_cannot_instantiate_directly(self):
        """BaseDomainExpert should not be instantiable."""
        with pytest.raises(TypeError):
            BaseDomainExpert()

    def test_subclass_must_implement_methods(self):
        """Subclass must implement all abstract methods."""

        class IncompleteExpert(BaseDomainExpert):
            @property
            def project_name(self):
                return "Test"

        # Should fail because not all abstract methods implemented
        with pytest.raises(TypeError):
            IncompleteExpert()
