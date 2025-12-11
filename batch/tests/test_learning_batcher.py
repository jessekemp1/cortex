"""
Unit tests for learning system batch processor

Tests learning analysis batching functionality.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import modules to test
from cortex.batch.learning_batcher import (
    LearningBatcher,
    LearningContext,
)
from cortex.batch.batch_config import BatchConfig


class TestLearningContext:
    """Test learning context data structure"""

    def test_context_creation(self):
        """Test creating a learning context"""
        context = LearningContext(
            execution_history={"completed": 10, "success_rate": 0.8},
            goals_context={"primary": "feature delivery"},
            metrics_data={
                "total_outcomes": 20,
                "followed_count": 15,
                "success_rate": 0.75
            },
            context_id="learning_001",
        )

        assert context.context_id == "learning_001"
        assert context.execution_history["completed"] == 10
        assert context.goals_context["primary"] == "feature delivery"
        assert context.metrics_data["total_outcomes"] == 20

    def test_context_default_id(self):
        """Test context with default ID"""
        context = LearningContext(
            execution_history={},
            goals_context={},
            metrics_data={},
        )

        assert context.context_id == "learning_001"

    def test_context_serialization(self):
        """Test that context data is JSON serializable"""
        context = LearningContext(
            execution_history={"tasks": [1, 2, 3]},
            goals_context={"goal": "test"},
            metrics_data={"count": 5},
            context_id="test_001",
        )

        # Should not raise
        json_str = json.dumps({
            "execution_history": context.execution_history,
            "goals_context": context.goals_context,
            "metrics_data": context.metrics_data,
        })
        assert "tasks" in json_str
        assert "count" in json_str


class TestLearningBatcher:
    """Test learning batcher"""

    def test_batcher_initialization(self):
        """Test initializing learning batcher"""
        batcher = LearningBatcher()
        assert batcher.client is not None
        assert batcher.system_prompt is not None
        assert "learning analysis system" in batcher.system_prompt.lower()

    def test_empty_context_list(self):
        """Test processing empty context list"""
        batcher = LearningBatcher()
        result = batcher.process_batch([])

        assert result["submitted_count"] == 0
        assert result["completed_count"] == 0
        assert result["failed_count"] == 0
        assert len(result["results"]) == 0

    def test_build_learning_requests(self):
        """Test building batch requests from contexts"""
        batcher = LearningBatcher()

        contexts = [
            LearningContext(
                execution_history={"completed": 5},
                goals_context={"goal": "test"},
                metrics_data={"total": 10},
                context_id="test_001",
            ),
            LearningContext(
                execution_history={"completed": 8},
                goals_context={"goal": "test2"},
                metrics_data={"total": 15},
                context_id="test_002",
            ),
        ]

        requests = batcher._build_learning_requests(contexts)

        assert len(requests) == 2
        assert requests[0].custom_id == "test_001"
        assert requests[1].custom_id == "test_002"
        assert "model" in requests[0].params
        assert "messages" in requests[0].params
        assert requests[0].params["max_tokens"] == 1500

    def test_parse_learning_insights(self):
        """Test parsing learning insights text"""
        text = """
KEY_INSIGHTS:
- Learning pattern 1
- Learning pattern 2
- Learning pattern 3

PATTERN_DISCOVERIES:
- Recurring pattern A
- Recurring pattern B

CONFIDENCE_ASSESSMENT:
Success likelihood: 85%
Reasoning: Based on 15 previous successful outcomes

ADJUSTMENT_SUGGESTIONS:
- Increase confidence for type X
- Reduce weight for type Y
"""

        parsed = LearningBatcher._parse_learning_insights(text)

        assert len(parsed["key_insights"]) == 3
        assert "Learning pattern 1" in parsed["key_insights"]
        assert len(parsed["pattern_discoveries"]) == 2
        assert "Recurring pattern A" in parsed["pattern_discoveries"]
        assert "85%" in parsed["confidence_assessment"]
        assert len(parsed["adjustment_suggestions"]) == 2
        assert "Increase confidence for type X" in parsed["adjustment_suggestions"]

    @patch("cortex.batch.learning_batcher.BatchAPIClient")
    def test_process_learning_result(self, mock_client):
        """Test processing learning API result"""
        batcher = LearningBatcher()

        result = {
            "message": {
                "content": [
                    {
                        "text": """
KEY_INSIGHTS:
- Insight 1
- Insight 2

PATTERN_DISCOVERIES:
- Pattern 1

CONFIDENCE_ASSESSMENT:
Success likelihood: 90%
Reasoning: High historical success

ADJUSTMENT_SUGGESTIONS:
- Suggestion 1
"""
                    }
                ]
            }
        }

        processed = batcher._process_learning_result("test_001", result)

        assert processed["status"] == "success"
        assert processed["context_id"] == "test_001"
        assert len(processed["insights"]["key_insights"]) == 2
        assert "Insight 1" in processed["insights"]["key_insights"]
        assert "90%" in processed["insights"]["confidence_assessment"]


class TestFileCaching:
    """Test file caching strategy"""

    def test_metrics_data_structure(self):
        """Test that metrics data structure supports caching"""
        metrics = {
            "total_outcomes": 50,
            "followed_count": 40,
            "success_rate": 0.8,
            "confidence_calibration": {
                "high (0.8-1.0)": 0.85,
                "medium (0.5-0.8)": 0.65,
            },
            "pattern_summary": {
                "goal_progress": {"total": 10, "success_rate": 0.9},
                "blocker_removal": {"total": 5, "success_rate": 0.7},
            }
        }

        # Should be JSON serializable
        json_str = json.dumps(metrics)
        assert "total_outcomes" in json_str
        assert "confidence_calibration" in json_str

        # Should deserialize correctly
        deserialized = json.loads(json_str)
        assert deserialized["total_outcomes"] == 50
        assert deserialized["confidence_calibration"]["high (0.8-1.0)"] == 0.85

    def test_context_contains_cached_metrics(self):
        """Test that context encapsulates cached metrics"""
        context = LearningContext(
            execution_history={"completed": 10},
            goals_context={"goal": "test"},
            metrics_data={
                "total_outcomes": 50,
                "followed_count": 40,
                "success_rate": 0.8,
                "confidence_calibration": {"high (0.8-1.0)": 0.85},
                "pattern_summary": {"type1": {"success_rate": 0.9}}
            },
        )

        # All metrics should be accessible from context
        assert context.metrics_data["total_outcomes"] == 50
        assert context.metrics_data["confidence_calibration"]["high (0.8-1.0)"] == 0.85
        assert context.metrics_data["pattern_summary"]["type1"]["success_rate"] == 0.9


class TestIntegration:
    """Integration tests for learning batcher"""

    def test_learning_requests_json_serializable(self):
        """Test that learning requests can be JSON serialized"""
        batcher = LearningBatcher()

        context = LearningContext(
            execution_history={"completed": 5, "tasks": ["task1", "task2"]},
            goals_context={"goal": "test", "priority": "high"},
            metrics_data={
                "total_outcomes": 20,
                "confidence_calibration": {"high": 0.9}
            },
            context_id="test",
        )

        requests = batcher._build_learning_requests([context])

        # Should not raise
        json_str = json.dumps(requests[0].params)
        assert "test" in json_str
        assert "completed" in json_str

    def test_context_with_complex_data(self):
        """Test contexts with complex nested data"""
        context = LearningContext(
            execution_history={
                "last_7_days": [
                    {"day": "Mon", "tasks_completed": 5, "success_rate": 0.8},
                    {"day": "Tue", "tasks_completed": 3, "success_rate": 0.9},
                ],
                "patterns": {
                    "morning": {"productivity": 0.9},
                    "afternoon": {"productivity": 0.7},
                },
            },
            goals_context={
                "quarterly": "Ship 4 major features",
                "monthly": "Improve test coverage",
                "weekly": ["Complete backlog", "Review PRs"],
            },
            metrics_data={
                "total_outcomes": 100,
                "by_type": {
                    "goal_progress": {
                        "total": 30,
                        "followed": 25,
                        "success_rate": 0.85,
                    },
                    "blocker_removal": {
                        "total": 20,
                        "followed": 18,
                        "success_rate": 0.75,
                    },
                },
                "confidence_calibration": {
                    "high (0.8-1.0)": 0.9,
                    "medium (0.5-0.8)": 0.7,
                    "low (0.0-0.5)": 0.5,
                },
            },
        )

        assert len(context.execution_history["last_7_days"]) == 2
        assert context.execution_history["patterns"]["morning"]["productivity"] == 0.9
        assert context.goals_context["quarterly"] == "Ship 4 major features"
        assert context.metrics_data["by_type"]["goal_progress"]["success_rate"] == 0.85

    def test_parse_partial_response(self):
        """Test parsing response with missing sections"""
        text = """
KEY_INSIGHTS:
- Only insight

CONFIDENCE_ASSESSMENT:
Success likelihood: 75%
Reasoning: Limited data
"""

        parsed = LearningBatcher._parse_learning_insights(text)

        assert len(parsed["key_insights"]) == 1
        assert len(parsed["pattern_discoveries"]) == 0  # Missing section
        assert "75%" in parsed["confidence_assessment"]
        assert len(parsed["adjustment_suggestions"]) == 0  # Missing section

    def test_parse_empty_response(self):
        """Test parsing empty response"""
        text = ""

        parsed = LearningBatcher._parse_learning_insights(text)

        assert len(parsed["key_insights"]) == 0
        assert len(parsed["pattern_discoveries"]) == 0
        assert parsed["confidence_assessment"] == ""
        assert len(parsed["adjustment_suggestions"]) == 0

    @patch("cortex.batch.learning_batcher.BatchAPIClient")
    def test_batch_error_handling(self, mock_client):
        """Test handling of batch processing errors"""
        batcher = LearningBatcher()

        # Mock client to raise error
        mock_client_instance = mock_client.return_value
        mock_client_instance.submit_batch.side_effect = Exception("API Error")

        context = LearningContext(
            execution_history={},
            goals_context={},
            metrics_data={},
        )

        with pytest.raises(Exception) as exc_info:
            batcher.process_batch([context])

        assert "API Error" in str(exc_info.value)

    @patch("cortex.batch.learning_batcher.BatchAPIClient")
    def test_result_processing_error(self, mock_client):
        """Test handling of individual result processing errors"""
        batcher = LearningBatcher()

        # Create a result with invalid structure
        result = {
            "message": {
                "content": []  # Empty content
            }
        }

        processed = batcher._process_learning_result("test_001", result)

        assert processed["status"] == "failed"
        assert "error" in processed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
