"""Unit tests for Cortex Intelligence components.

Tests the intelligence models and query system including:
- Data models (SessionContext, IntelligenceResult, Pattern, Lesson, etc.)
- IntelligenceQueryType enum
- Intelligence query methods on CortexBridge
"""

from dataclasses import asdict

import pytest


class TestIntelligenceQueryType:
    """Test IntelligenceQueryType enum."""

    def test_query_type_values(self):
        """IntelligenceQueryType should have expected values."""
        from cortex.intelligence.models import IntelligenceQueryType

        assert IntelligenceQueryType.spec.value == "spec"
        assert IntelligenceQueryType.architecture.value == "architecture"
        assert IntelligenceQueryType.implementation.value == "implementation"
        assert IntelligenceQueryType.research.value == "research"

    def test_query_type_from_string(self):
        """IntelligenceQueryType should be constructible from string."""
        from cortex.intelligence.models import IntelligenceQueryType

        spec_type = IntelligenceQueryType("spec")
        assert spec_type == IntelligenceQueryType.spec

        impl_type = IntelligenceQueryType("implementation")
        assert impl_type == IntelligenceQueryType.implementation

    def test_query_type_invalid_raises(self):
        """IntelligenceQueryType should raise for invalid values."""
        from cortex.intelligence.models import IntelligenceQueryType

        with pytest.raises(ValueError):
            IntelligenceQueryType("invalid_type")


class TestSessionContext:
    """Test SessionContext data model."""

    def test_session_context_creation(self):
        """SessionContext should be creatable with required fields."""
        from cortex.intelligence.models import SessionContext

        context = SessionContext(
            project="test_project",
            working_directory="/path/to/project",
            recent_work=[{"hash": "abc123", "summary": "Test commit"}],
            active_goals=["Goal 1", "Goal 2"],
            current_focus="Testing session context",
            last_updated="2025-01-27T10:00:00",
        )

        assert context.project == "test_project"
        assert context.working_directory == "/path/to/project"
        assert len(context.recent_work) == 1
        assert len(context.active_goals) == 2
        assert context.current_focus == "Testing session context"

    def test_session_context_to_dict(self):
        """SessionContext should be convertible to dict."""
        from cortex.intelligence.models import SessionContext

        context = SessionContext(
            project="test",
            working_directory="/test",
            recent_work=[],
            active_goals=[],
            current_focus="focus",
            last_updated="2025-01-27T10:00:00",
        )

        data = asdict(context)
        assert data["project"] == "test"
        assert data["current_focus"] == "focus"


class TestSimilarWork:
    """Test SimilarWork data model."""

    def test_similar_work_creation(self):
        """SimilarWork should be creatable with required fields."""
        from cortex.intelligence.models import SimilarWork

        similar = SimilarWork(
            id="sw_001",
            title="Similar Project Work",
            type="spec",
            similarity_score=0.85,
            project="VortexV2",
            summary="A similar implementation",
            key_patterns=["async_pattern", "retry_pattern"],
            lessons_learned=["Lesson 1"],
            reference_path="/path/to/spec.md",
        )

        assert similar.id == "sw_001"
        assert similar.similarity_score == 0.85
        assert len(similar.key_patterns) == 2

    def test_similar_work_default_scores(self):
        """SimilarWork should have default confidence and relevance scores."""
        from cortex.intelligence.models import SimilarWork

        similar = SimilarWork(
            id="test",
            title="Test",
            type="spec",
            similarity_score=0.5,
            project="test",
            summary="test",
            key_patterns=[],
            lessons_learned=[],
            reference_path="/test",
        )

        assert similar.confidence_score == 0.0
        assert similar.relevance_score == 0.0


class TestPattern:
    """Test Pattern data model."""

    def test_pattern_creation(self):
        """Pattern should be creatable with required fields."""
        from cortex.intelligence.models import Pattern

        pattern = Pattern(
            name="async_fastapi",
            description="Async FastAPI pattern for high-throughput APIs",
            projects=["VortexV2", "cortex"],
            reference="/patterns/async_fastapi.md",
        )

        assert pattern.name == "async_fastapi"
        assert len(pattern.projects) == 2
        assert pattern.confidence_score == 0.0  # Default

    def test_pattern_with_scores(self):
        """Pattern should accept custom confidence and relevance scores."""
        from cortex.intelligence.models import Pattern

        pattern = Pattern(
            name="test_pattern",
            description="Test",
            projects=["test"],
            reference="/test",
            confidence_score=0.9,
            relevance_score=0.8,
        )

        assert pattern.confidence_score == 0.9
        assert pattern.relevance_score == 0.8


class TestLesson:
    """Test Lesson data model."""

    def test_lesson_creation(self):
        """Lesson should be creatable with required fields."""
        from cortex.intelligence.models import Lesson

        lesson = Lesson(
            id="lesson_001",
            project="cortex",
            category="testing",
            lesson="Always mock external APIs in unit tests",
            context="Found during test flakiness investigation",
            frequency=5,
            first_seen="2025-01-01",
            last_seen="2025-01-27",
        )

        assert lesson.id == "lesson_001"
        assert lesson.category == "testing"
        assert lesson.frequency == 5


class TestWarning:
    """Test Warning data model."""

    def test_warning_creation(self):
        """Warning should be creatable with required fields."""
        from cortex.intelligence.models import Warning

        warning = Warning(
            type="repeated_mistake",
            severity="high",
            message="Circular import detected",
            occurrences=3,
            prevention="Import inside functions, not at module level",
            past_examples=["alpha_arena/model.py", "cortex/bridge.py"],
        )

        assert warning.type == "repeated_mistake"
        assert warning.severity == "high"
        assert warning.occurrences == 3
        assert len(warning.past_examples) == 2


class TestRecommendation:
    """Test Recommendation data model."""

    def test_recommendation_creation(self):
        """Recommendation should be creatable with required fields."""
        from cortex.intelligence.models import Recommendation

        rec = Recommendation(
            type="improvement",
            priority="high",
            title="Add retry logic",
            description="Add exponential backoff retry for API calls",
            rationale="Improves reliability under network issues",
            related_patterns=["retry_pattern", "circuit_breaker"],
        )

        assert rec.type == "improvement"
        assert rec.priority == "high"
        assert len(rec.related_patterns) == 2


class TestIntelligenceResult:
    """Test IntelligenceResult data model."""

    def test_intelligence_result_creation(self):
        """IntelligenceResult should be creatable with required fields."""
        from cortex.intelligence.models import IntelligenceQueryType, IntelligenceResult

        result = IntelligenceResult(
            query_timestamp="2025-01-27T10:00:00",
            query_type=IntelligenceQueryType.spec,
            project="cortex",
            similar_work=[],
            applicable_patterns=[],
            lessons=[],
            warnings=[],
            recommendations=[],
            project_context=None,
            session_context=None,
        )

        assert result.query_type == IntelligenceQueryType.spec
        assert result.project == "cortex"
        assert result.query_time_ms == 0.0

    def test_intelligence_result_to_dict(self):
        """IntelligenceResult.to_dict should convert to dictionary."""
        from cortex.intelligence.models import IntelligenceQueryType, IntelligenceResult

        result = IntelligenceResult(
            query_timestamp="2025-01-27T10:00:00",
            query_type=IntelligenceQueryType.implementation,
            project="VortexV2",
            similar_work=[],
            applicable_patterns=[],
            lessons=[],
            warnings=[],
            recommendations=[],
            project_context=None,
            session_context=None,
            reasoning="Test reasoning",
            overall_confidence=0.85,
        )

        data = result.to_dict()

        assert data["query_type"] == "implementation"
        assert data["project"] == "VortexV2"
        assert data["reasoning"] == "Test reasoning"
        assert data["overall_confidence"] == 0.85


class TestProjectContext:
    """Test ProjectContext data model."""

    def test_project_context_creation(self):
        """ProjectContext should be creatable with required fields."""
        from cortex.intelligence.models import ProjectContext

        ctx = ProjectContext(
            name="VortexV2",
            description="Weather forecasting API",
            tech_stack=["Python", "FastAPI", "GRIB"],
            status="active",
            patterns_used=["async_fastapi", "grib_processing"],
            related_projects=["cortex"],
            lessons_count=10,
            last_updated="2025-01-27",
        )

        assert ctx.name == "VortexV2"
        assert len(ctx.tech_stack) == 3
        assert ctx.lessons_count == 10
        assert ctx.health_data is None  # Optional field

    def test_project_context_with_health_data(self):
        """ProjectContext should accept optional health_data."""
        from cortex.intelligence.models import ProjectContext

        ctx = ProjectContext(
            name="test",
            description="test",
            tech_stack=[],
            status="active",
            patterns_used=[],
            related_projects=[],
            lessons_count=0,
            last_updated="2025-01-27",
            health_data={"score": 85, "status": "healthy"},
        )

        assert ctx.health_data is not None
        assert ctx.health_data["score"] == 85


class TestContextPrediction:
    """Test ContextPrediction data model."""

    def test_context_prediction_creation(self):
        """ContextPrediction should be creatable with required fields."""
        from cortex.intelligence.models import ContextPrediction

        pred = ContextPrediction(
            type="file",
            relevance_score=0.9,
            content="/path/to/relevant/file.py",
            source="git_history",
        )

        assert pred.type == "file"
        assert pred.relevance_score == 0.9
        assert pred.source == "git_history"


class TestBridgeIntelligenceQueries:
    """Test intelligence query methods on CortexBridge."""

    def test_query_intelligence_returns_dict(self):
        """query_intelligence should return result as dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.query_intelligence(
            request="test query",
            project="cortex",
            query_type="spec",
        )

        assert isinstance(result, dict)

    def test_query_intelligence_handles_missing_unified_intel(self):
        """query_intelligence should handle missing UnifiedIntelligence."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.unified_intel = None

        result = bridge.query_intelligence(
            request="test",
            project="test",
            query_type="spec",
        )

        assert "error" in result

    def test_find_similar_work_returns_list(self):
        """find_similar_work should return list of similar work."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.find_similar_work("test domain", "cortex")

        assert isinstance(result, list)

    def test_search_specs_returns_list(self):
        """search_specs should return list of matching specs."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.search_specs("API design", project="cortex")

        assert isinstance(result, list)

    def test_get_session_context_structured_format(self):
        """get_session_context should return structured dict by default."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_session_context(format="structured")

        assert isinstance(result, dict)

    def test_get_session_context_terminal_format(self):
        """get_session_context should support terminal format."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_session_context(format="terminal")

        assert isinstance(result, dict)
        # Terminal format wraps content in a dict with 'context' or 'error' key
        assert "context" in result or "error" in result

    def test_get_session_context_handles_missing_session_mgr(self):
        """get_session_context should handle missing SessionManager."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.session_mgr = None

        result = bridge.get_session_context()

        assert "error" in result
