"""
Unit tests for Cortex batch API integration

Tests core functionality of batch API client, config, and fallback mechanisms.
"""

import json
import os

# Import modules to test
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from batch_api_client import (
    BatchAPIClient,
    BatchRequest,
    BatchResult,
)
from batch_config import BatchConfig
from batch_fallback import BatchFallback


class TestBatchConfig:
    """Test configuration management"""

    def test_batch_disabled_by_default(self):
        """Test that batch is disabled by default"""
        with patch.dict(os.environ, {}, clear=True):
            assert not BatchConfig.is_batch_enabled("research")
            assert not BatchConfig.is_batch_enabled("recommendations")
            assert not BatchConfig.is_batch_enabled("learning")

    def test_batch_enabled_when_set(self):
        """Test enabling batch for specific feature"""
        with patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": "true"}):
            assert BatchConfig.is_batch_enabled("research")

        with patch.dict(os.environ, {"CORTEX_BATCH_RECOMMENDATIONS_ENABLED": "true"}):
            assert BatchConfig.is_batch_enabled("recommendations")

    def test_batch_disabled_case_insensitive(self):
        """Test that false/False/FALSE all disable"""
        for value in ["false", "False", "FALSE", "0", ""]:
            with patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": value}):
                assert not BatchConfig.is_batch_enabled("research")

    def test_get_config_values(self):
        """Test getting configuration values"""
        with patch.dict(
            os.environ,
            {
                "CORTEX_BATCH_MAX_REQUESTS": "5000",
                "CORTEX_BATCH_TIMEOUT_MINUTES": "60",
                "CORTEX_BATCH_RETRY_ATTEMPTS": "2",
            },
        ):
            assert BatchConfig.get_max_requests() == 5000
            assert BatchConfig.get_timeout_minutes() == 60
            assert BatchConfig.get_retry_attempts() == 2

    def test_config_defaults(self):
        """Test default configuration values"""
        with patch.dict(os.environ, {}, clear=True):
            assert BatchConfig.get_max_requests() <= 10000
            assert BatchConfig.get_timeout_minutes() >= 1440
            assert BatchConfig.get_retry_attempts() >= 1
            assert BatchConfig.should_fallback_on_error() is True

    def test_is_any_batch_enabled(self):
        """Test checking if any batch feature is enabled"""
        with patch.dict(os.environ, {}, clear=True):
            assert not BatchConfig.is_any_batch_enabled()

        with patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": "true"}):
            assert BatchConfig.is_any_batch_enabled()


class TestBatchFallback:
    """Test fallback mechanism"""

    def test_fallback_batch_disabled(self):
        """Test sequential used when batch disabled"""
        batch_called = False
        sequential_called = False

        def batch_func(items):
            nonlocal batch_called
            batch_called = True
            return {"method": "batch"}

        def sequential_func(items):
            nonlocal sequential_called
            sequential_called = True
            return {"method": "sequential"}

        with patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": "false"}):
            result = BatchFallback.process_with_fallback(
                [], batch_func, sequential_func, "research"
            )

        assert not batch_called
        assert sequential_called
        assert result["method"] == "sequential"

    def test_fallback_batch_success(self):
        """Test batch used when succeeds"""

        def batch_func(items):
            return {"method": "batch", "status": "success"}

        def sequential_func(items):
            return {"method": "sequential"}

        with patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": "true"}):
            result = BatchFallback.process_with_fallback(
                [], batch_func, sequential_func, "research"
            )

        assert result["method"] == "batch"
        assert result["status"] == "success"

    def test_fallback_batch_fails(self):
        """Test fallback to sequential when batch fails"""

        def batch_func(items):
            raise Exception("Batch API error")

        def sequential_func(items):
            return {"method": "sequential", "status": "success"}

        with patch.dict(
            os.environ,
            {
                "CORTEX_BATCH_RESEARCH_ENABLED": "true",
                "CORTEX_BATCH_FALLBACK_ON_ERROR": "true",
            },
        ):
            result = BatchFallback.process_with_fallback(
                [], batch_func, sequential_func, "research"
            )

        assert result["method"] == "sequential"
        assert result["status"] == "success"

    def test_fallback_both_fail(self):
        """Test exception when both batch and sequential fail"""

        def batch_func(items):
            raise Exception("Batch error")

        def sequential_func(items):
            raise Exception("Sequential error")

        with patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": "true"}):
            with pytest.raises(Exception, match="Sequential error"):
                BatchFallback.process_with_fallback(
                    [], batch_func, sequential_func, "research"
                )

    def test_fallback_disabled_no_fallback(self):
        """Test no fallback when fallback is disabled"""

        def batch_func(items):
            raise Exception("Batch error")

        def sequential_func(items):
            return {"method": "sequential"}

        with patch.dict(
            os.environ,
            {
                "CORTEX_BATCH_RESEARCH_ENABLED": "true",
                "CORTEX_BATCH_FALLBACK_ON_ERROR": "false",
            },
        ):
            with pytest.raises(Exception, match="Batch error"):
                BatchFallback.process_with_fallback(
                    [], batch_func, sequential_func, "research"
                )


class TestBatchRequest:
    """Test batch request data structure"""

    def test_batch_request_creation(self):
        """Test creating batch requests"""
        request = BatchRequest(
            custom_id="test_1",
            params={
                "messages": [{"role": "user", "content": "test"}],
                "system": "You are helpful",
            },
        )

        assert request.custom_id == "test_1"
        assert "messages" in request.params
        assert "system" in request.params

    def test_batch_result_creation(self):
        """Test creating batch results"""
        result = BatchResult(
            custom_id="test_1",
            result={"message": {"content": [{"text": "Response"}]}},
            status="succeeded",
        )

        assert result.custom_id == "test_1"
        assert result.status == "succeeded"
        assert "message" in result.result


class TestBatchAPIClient:
    """Test batch API client (with mocks)"""

    @patch("batch_api_client.anthropic")
    def test_client_initialization(self, mock_anthropic):
        """Test initializing batch API client"""
        mock_anthropic.Anthropic.return_value = MagicMock()

        client = BatchAPIClient()
        assert client.batch_dir.exists()

    @patch("batch_api_client.anthropic")
    def test_submit_batch_empty_raises(self, mock_anthropic):
        """Test that empty batch raises ValueError"""
        mock_anthropic.Anthropic.return_value = MagicMock()

        client = BatchAPIClient()
        with pytest.raises(ValueError, match="at least 1"):
            client.submit_batch([])

    @patch("batch_api_client.anthropic")
    def test_submit_batch_too_large_raises(self, mock_anthropic):
        """Test that batch >10K requests raises ValueError"""
        mock_anthropic.Anthropic.return_value = MagicMock()

        client = BatchAPIClient()
        requests = [BatchRequest(f"req{i}", {}) for i in range(10001)]
        with pytest.raises(ValueError, match="10,000"):
            client.submit_batch(requests)

    @patch("batch_api_client.anthropic")
    def test_batch_metadata_saved(self, mock_anthropic):
        """Test that batch metadata is saved locally"""
        # Setup
        mock_client = MagicMock()
        mock_batch = MagicMock()
        mock_batch.id = "batch_123"
        mock_batch.processing_status = "processing"
        mock_client.beta.messages.batches.create.return_value = mock_batch
        mock_anthropic.Anthropic.return_value = mock_client

        client = BatchAPIClient()

        # Execute
        requests = [BatchRequest("req1", {})]
        client.submit_batch(requests, "Test batch")

        # Verify metadata saved
        metadata_file = client.batch_dir / "batch_123_metadata.json"
        assert metadata_file.exists()

        metadata = json.loads(metadata_file.read_text())
        assert metadata["batch_id"] == "batch_123"
        assert metadata["request_count"] == 1
        assert metadata["description"] == "Test batch"


class TestIntegration:
    """Integration tests for batch components"""

    def test_batch_request_json_serializable(self):
        """Test that batch requests can be serialized to JSON"""
        request = BatchRequest(
            custom_id="test_1",
            params={
                "messages": [{"role": "user", "content": "test"}],
                "system": "helpful",
            },
        )

        # This should not raise
        json_str = json.dumps(request.params)
        assert "test" in json_str

    @patch.dict(os.environ, {"CORTEX_BATCH_RESEARCH_ENABLED": "true"})
    def test_fallback_with_config(self):
        """Test fallback respects configuration"""

        def batch_func(items):
            return {"source": "batch"}

        def sequential_func(items):
            return {"source": "sequential"}

        result = BatchFallback.process_with_fallback(
            [], batch_func, sequential_func, "research"
        )

        assert result["source"] == "batch"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
