"""
Unit tests for briefing batch processor

Tests recommendation and insight batching functionality.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from briefing_batcher import (
    RecommendationBatcher,
    InsightBatcher,
    BriefingContext,
)
from batch_config import BatchConfig


class TestBriefingContext:
    """Test briefing context data structure"""

    def test_context_creation(self):
        """Test creating a briefing context"""
        context = BriefingContext(
            portfolio_pulse={"projects": 3},
            system_health={"status": "healthy"},
            execution_history={"completed": 5},
            goals_context={"primary": "feature delivery"},
            context_id="briefing_001",
        )

        assert context.context_id == "briefing_001"
        assert context.portfolio_pulse["projects"] == 3
        assert context.system_health["status"] == "healthy"

    def test_context_default_id(self):
        """Test context with default ID"""
        context = BriefingContext(
            portfolio_pulse={},
            system_health={},
            execution_history={},
            goals_context={},
        )

        assert context.context_id == "briefing_001"


class TestRecommendationBatcher:
    """Test recommendation batching"""

    def test_batcher_initialization(self):
        """Test initializing recommendation batcher"""
        batcher = RecommendationBatcher()
        assert batcher.client is not None
        assert batcher.system_prompt is not None
        assert "strategic advisor" in batcher.system_prompt.lower()

    def test_empty_context_list(self):
        """Test processing empty context list"""
        batcher = RecommendationBatcher()
        result = batcher.process_batch([])

        assert result["submitted_count"] == 0
        assert result["completed_count"] == 0
        assert result["failed_count"] == 0
        assert len(result["results"]) == 0

    def test_build_recommendation_requests(self):
        """Test building batch requests from contexts"""
        batcher = RecommendationBatcher()

        contexts = [
            BriefingContext(
                portfolio_pulse={"projects": 1},
                system_health={"status": "ok"},
                execution_history={"tasks": 1},
                goals_context={"goal": "test"},
                context_id="test_001",
            ),
            BriefingContext(
                portfolio_pulse={"projects": 2},
                system_health={"status": "good"},
                execution_history={"tasks": 2},
                goals_context={"goal": "test2"},
                context_id="test_002",
            ),
        ]

        requests = batcher._build_recommendation_requests(contexts)

        assert len(requests) == 2
        assert requests[0].custom_id == "test_001"
        assert requests[1].custom_id == "test_002"
        assert "model" in requests[0].params
        assert "messages" in requests[0].params

    def test_parse_recommendations(self):
        """Test parsing recommendation text"""
        text = """
PRIORITY_ACTIONS:
- Implement API endpoint
- Write documentation
- Review code

BLOCKERS:
- Missing test data

RECOMMENDED_FOCUS: Feature delivery

ALTERNATIVE_APPROACHES:
- Use existing service
- Build custom solution
"""

        parsed = RecommendationBatcher._parse_recommendations(text)

        assert len(parsed["priority_actions"]) == 3
        assert "Implement API endpoint" in parsed["priority_actions"]
        assert len(parsed["blockers"]) == 1
        assert "Missing test data" in parsed["blockers"]
        assert parsed["recommended_focus"] == "Feature delivery"
        assert len(parsed["alternative_approaches"]) == 2

    @patch("briefing_batcher.BatchAPIClient")
    def test_process_recommendation_result(self, mock_client):
        """Test processing recommendation API result"""
        batcher = RecommendationBatcher()

        result = {
            "message": {
                "content": [
                    {
                        "text": """
PRIORITY_ACTIONS:
- Task 1
- Task 2

BLOCKERS:
- Issue 1

RECOMMENDED_FOCUS: Goal

ALTERNATIVE_APPROACHES:
- Approach 1
"""
                    }
                ]
            }
        }

        processed = batcher._process_recommendation_result("test_001", result)

        assert processed["status"] == "success"
        assert processed["context_id"] == "test_001"
        assert len(processed["recommendations"]["priority_actions"]) == 2
        assert "Task 1" in processed["recommendations"]["priority_actions"]


class TestInsightBatcher:
    """Test insight batching"""

    def test_batcher_initialization(self):
        """Test initializing insight batcher"""
        batcher = InsightBatcher()
        assert batcher.client is not None
        assert batcher.system_prompt is not None
        assert "learning system" in batcher.system_prompt.lower()

    def test_empty_context_list(self):
        """Test processing empty context list"""
        batcher = InsightBatcher()
        result = batcher.process_batch([])

        assert result["submitted_count"] == 0
        assert result["completed_count"] == 0
        assert result["failed_count"] == 0
        assert len(result["results"]) == 0

    def test_build_insight_requests(self):
        """Test building insight batch requests"""
        batcher = InsightBatcher()

        contexts = [
            BriefingContext(
                portfolio_pulse={},
                system_health={},
                execution_history={"completed": 5},
                goals_context={"goal": "test"},
                context_id="insight_001",
            ),
        ]

        requests = batcher._build_insight_requests(contexts)

        assert len(requests) == 1
        assert requests[0].custom_id == "insight_001_insights"
        assert "model" in requests[0].params
        assert "messages" in requests[0].params

    def test_parse_insights(self):
        """Test parsing insight text"""
        text = """
KEY_LEARNINGS:
- Pattern 1
- Pattern 2
- Pattern 3

DECISION_POINTS:
- Decision 1
- Decision 2

CONFIDENCE_ASSESSMENT:
Success likelihood: 85%
Reasoning: Based on historical patterns

ADJUSTMENT_SUGGESTIONS:
- Adjust timeline
- Increase resources
"""

        parsed = InsightBatcher._parse_insights(text)

        assert len(parsed["key_learnings"]) == 3
        assert "Pattern 1" in parsed["key_learnings"]
        assert len(parsed["decision_points"]) == 2
        assert "85%" in parsed["confidence_assessment"]
        assert len(parsed["adjustment_suggestions"]) == 2

    @patch("briefing_batcher.BatchAPIClient")
    def test_process_insight_result(self, mock_client):
        """Test processing insight API result"""
        batcher = InsightBatcher()

        result = {
            "message": {
                "content": [
                    {
                        "text": """
KEY_LEARNINGS:
- Learning 1
- Learning 2

DECISION_POINTS:
- Decision 1

CONFIDENCE_ASSESSMENT:
Success likelihood: 90%
Reasoning: Test

ADJUSTMENT_SUGGESTIONS:
- Suggestion 1
"""
                    }
                ]
            }
        }

        processed = batcher._process_insight_result("insight_001", result)

        assert processed["status"] == "success"
        assert processed["context_id"] == "insight_001"
        assert len(processed["insights"]["key_learnings"]) == 2
        assert "Learning 1" in processed["insights"]["key_learnings"]


class TestIntegration:
    """Integration tests for briefing batchers"""

    def test_recommendation_requests_json_serializable(self):
        """Test that recommendation requests can be JSON serialized"""
        batcher = RecommendationBatcher()

        context = BriefingContext(
            portfolio_pulse={"test": "data"},
            system_health={"healthy": True},
            execution_history={"completed": 1},
            goals_context={"goal": "test"},
            context_id="test",
        )

        requests = batcher._build_recommendation_requests([context])

        # Should not raise
        json_str = json.dumps(requests[0].params)
        assert "test" in json_str

    def test_insight_requests_json_serializable(self):
        """Test that insight requests can be JSON serialized"""
        batcher = InsightBatcher()

        context = BriefingContext(
            portfolio_pulse={"test": "data"},
            system_health={"healthy": True},
            execution_history={"completed": 1},
            goals_context={"goal": "test"},
            context_id="test",
        )

        requests = batcher._build_insight_requests([context])

        # Should not raise
        json_str = json.dumps(requests[0].params)
        assert "test" in json_str

    def test_context_with_complex_data(self):
        """Test contexts with complex nested data"""
        context = BriefingContext(
            portfolio_pulse={
                "projects": [
                    {"name": "Project 1", "status": "active"},
                    {"name": "Project 2", "status": "planning"},
                ],
                "metrics": {"velocity": 10, "quality": 0.95},
            },
            system_health={
                "components": ["api", "db", "cache"],
                "uptime": 99.99,
            },
            execution_history={
                "last_7_days": [
                    {"day": "Mon", "tasks_completed": 5},
                    {"day": "Tue", "tasks_completed": 3},
                ],
                "success_rate": 0.9,
            },
            goals_context={
                "quarterly": "Ship 4 major features",
                "monthly": "Improve test coverage",
                "weekly": "Complete backlog",
            },
        )

        assert len(context.portfolio_pulse["projects"]) == 2
        assert context.system_health["uptime"] == 99.99
        assert context.execution_history["success_rate"] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
