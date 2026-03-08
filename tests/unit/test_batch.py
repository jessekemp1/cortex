"""Unit tests for Cortex Batch Processing.

Tests the batch API client and related components including:
- BatchRequest and BatchResult data classes
- BatchAPIClient methods (with mocked Anthropic API)
- Error handling and retry logic
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBatchRequest:
    """Test BatchRequest data class."""

    def test_batch_request_creation(self):
        """BatchRequest should be creatable with custom_id and params."""
        from cortex.batch.batch_api_client import BatchRequest

        request = BatchRequest(
            custom_id="test_001",
            params={
                "messages": [{"role": "user", "content": "Hello"}],
                "system": "You are a helpful assistant",
            },
        )

        assert request.custom_id == "test_001"
        assert "messages" in request.params
        assert len(request.params["messages"]) == 1

    def test_batch_request_params_flexibility(self):
        """BatchRequest params should accept arbitrary keys."""
        from cortex.batch.batch_api_client import BatchRequest

        request = BatchRequest(
            custom_id="test_002",
            params={
                "messages": [],
                "temperature": 0.5,
                "max_tokens": 1000,
                "custom_field": "value",
            },
        )

        assert request.params["temperature"] == 0.5
        assert request.params["custom_field"] == "value"


class TestBatchResult:
    """Test BatchResult data class."""

    def test_batch_result_creation(self):
        """BatchResult should be creatable with required fields."""
        from cortex.batch.batch_api_client import BatchResult

        result = BatchResult(
            custom_id="test_001",
            result={"message": {"content": [{"text": "Response"}]}},
            status="succeeded",
        )

        assert result.custom_id == "test_001"
        assert result.status == "succeeded"
        assert "message" in result.result

    def test_batch_result_error_status(self):
        """BatchResult should handle error status."""
        from cortex.batch.batch_api_client import BatchResult

        result = BatchResult(
            custom_id="test_002",
            result={"error": {"message": "Rate limited"}},
            status="errored",
        )

        assert result.status == "errored"
        assert "error" in result.result


class TestBatchAPIErrors:
    """Test batch API exception classes."""

    def test_batch_api_error_hierarchy(self):
        """Batch errors should inherit from BatchAPIError."""
        from cortex.batch.batch_api_client import (
            BatchAPIError,
            BatchResultError,
            BatchSubmissionError,
            BatchTimeoutError,
        )

        assert issubclass(BatchSubmissionError, BatchAPIError)
        assert issubclass(BatchTimeoutError, BatchAPIError)
        assert issubclass(BatchResultError, BatchAPIError)

    def test_batch_submission_error(self):
        """BatchSubmissionError should be raisable with message."""
        from cortex.batch.batch_api_client import BatchSubmissionError

        with pytest.raises(BatchSubmissionError) as exc_info:
            raise BatchSubmissionError("Failed to submit batch")

        assert "Failed to submit batch" in str(exc_info.value)

    def test_batch_timeout_error(self):
        """BatchTimeoutError should be raisable with message."""
        from cortex.batch.batch_api_client import BatchTimeoutError

        with pytest.raises(BatchTimeoutError) as exc_info:
            raise BatchTimeoutError("Batch timed out")

        assert "timed out" in str(exc_info.value)


class TestBatchAPIClientInit:
    """Test BatchAPIClient initialization."""

    def test_client_requires_anthropic_sdk(self):
        """BatchAPIClient should require anthropic SDK."""
        # This test verifies the import check behavior
        from cortex.batch.batch_api_client import BatchAPIClient

        # If anthropic is available, client should initialize
        # If not, ImportError should be raised
        # We test that the class exists and has expected attributes
        assert hasattr(BatchAPIClient, "submit_batch")
        assert hasattr(BatchAPIClient, "get_batch_status")
        assert hasattr(BatchAPIClient, "poll_results")

    @patch("cortex.batch.batch_api_client.anthropic", None)
    def test_client_raises_without_anthropic(self):
        """BatchAPIClient should raise ImportError without anthropic."""
        # Re-import to trigger the check

        import cortex.batch.batch_api_client as batch_module

        # Save original
        original_anthropic = batch_module.anthropic

        try:
            batch_module.anthropic = None

            with pytest.raises(ImportError):
                batch_module.BatchAPIClient()
        finally:
            batch_module.anthropic = original_anthropic


class TestBatchAPIClientSubmit:
    """Test BatchAPIClient submit_batch method."""

    def test_submit_batch_validates_empty_requests(self):
        """submit_batch should reject empty request list."""
        from cortex.batch.batch_api_client import BatchAPIClient

        # Mock anthropic client
        with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = MagicMock()

            client = BatchAPIClient()

            with pytest.raises(ValueError, match="at least 1 request"):
                client.submit_batch([])

    def test_submit_batch_validates_max_requests(self):
        """submit_batch should reject more than 10000 requests."""
        from cortex.batch.batch_api_client import BatchAPIClient, BatchRequest

        with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = MagicMock()

            client = BatchAPIClient()

            # Create 10001 requests
            requests = [
                BatchRequest(custom_id=f"req_{i}", params={"messages": []}) for i in range(10001)
            ]

            with pytest.raises(ValueError, match="10,000"):
                client.submit_batch(requests)

    def test_submit_batch_saves_metadata(self):
        """submit_batch should save metadata locally."""
        from cortex.batch.batch_api_client import BatchAPIClient, BatchRequest

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
                # Mock the client and batch response
                mock_client = MagicMock()
                mock_anthropic.Anthropic.return_value = mock_client

                mock_batch = MagicMock()
                mock_batch.id = "batch_test_123"
                mock_batch.processing_status = "in_progress"
                mock_client.messages.batches.create.return_value = mock_batch

                client = BatchAPIClient()
                # Override batch_dir to use temp directory
                client.batch_dir = Path(tmpdir)

                requests = [BatchRequest(custom_id="test_1", params={"messages": []})]

                batch_id = client.submit_batch(requests, description="Test batch")

                assert batch_id == "batch_test_123"

                # Check metadata file was created
                metadata_file = Path(tmpdir) / "batch_test_123_metadata.json"
                assert metadata_file.exists()

                metadata = json.loads(metadata_file.read_text())
                assert metadata["batch_id"] == "batch_test_123"
                assert metadata["description"] == "Test batch"
                assert metadata["request_count"] == 1


class TestBatchAPIClientStatus:
    """Test BatchAPIClient get_batch_status method."""

    def test_get_batch_status_returns_progress(self):
        """get_batch_status should return progress information."""
        from cortex.batch.batch_api_client import BatchAPIClient

        with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            # Mock batch status response
            mock_batch = MagicMock()
            mock_batch.id = "batch_123"
            mock_batch.processing_status = "processing"
            mock_batch.request_counts = MagicMock()
            mock_batch.request_counts.processing = 5
            mock_batch.request_counts.succeeded = 3
            mock_batch.request_counts.errored = 1
            mock_batch.request_counts.expired = 0

            mock_client.messages.batches.retrieve.return_value = mock_batch

            client = BatchAPIClient()
            status = client.get_batch_status("batch_123")

            assert status["id"] == "batch_123"
            assert status["status"] == "processing"
            assert status["request_counts"]["processing"] == 5
            assert status["request_counts"]["succeeded"] == 3
            assert "progress_percentage" in status
            assert "error_rate" in status

    def test_get_batch_status_calculates_progress_percentage(self):
        """get_batch_status should calculate correct progress percentage."""
        from cortex.batch.batch_api_client import BatchAPIClient

        with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            mock_batch = MagicMock()
            mock_batch.id = "batch_456"
            mock_batch.processing_status = "processing"
            mock_batch.request_counts = MagicMock()
            # 10 total, 5 completed (50%)
            mock_batch.request_counts.processing = 5
            mock_batch.request_counts.succeeded = 4
            mock_batch.request_counts.errored = 1
            mock_batch.request_counts.expired = 0

            mock_client.messages.batches.retrieve.return_value = mock_batch

            client = BatchAPIClient()
            status = client.get_batch_status("batch_456")

            # (4 + 1 + 0) / 10 = 50%
            assert status["progress_percentage"] == 50.0
            # 1 / 10 = 10%
            assert status["error_rate"] == 10.0


class TestBatchAPIClientList:
    """Test BatchAPIClient list_batches method."""

    def test_list_batches_returns_list(self):
        """list_batches should return list of batch info."""
        from cortex.batch.batch_api_client import BatchAPIClient

        with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            # Mock batch list response
            mock_batch1 = MagicMock()
            mock_batch1.id = "batch_1"
            mock_batch1.processing_status = "completed"
            mock_batch1.created_at = "2025-01-27T10:00:00Z"
            mock_batch1.request_counts = MagicMock()
            mock_batch1.request_counts.processing = 0
            mock_batch1.request_counts.succeeded = 10
            mock_batch1.request_counts.errored = 0
            mock_batch1.request_counts.expired = 0

            mock_client.messages.batches.list.return_value = [mock_batch1]

            client = BatchAPIClient()
            batches = client.list_batches(limit=5)

            assert isinstance(batches, list)
            assert len(batches) == 1
            assert batches[0]["id"] == "batch_1"
            assert batches[0]["status"] == "completed"


class TestBatchAPIClientMetadata:
    """Test BatchAPIClient metadata persistence methods."""

    def test_save_and_load_metadata(self):
        """_save_batch_metadata and _load_batch_metadata should work together."""
        from cortex.batch.batch_api_client import BatchAPIClient

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = MagicMock()

                client = BatchAPIClient()
                client.batch_dir = Path(tmpdir)

                metadata = {
                    "batch_id": "test_batch",
                    "created_at": "2025-01-27T10:00:00",
                    "description": "Test description",
                    "request_count": 5,
                }

                client._save_batch_metadata("test_batch", metadata)
                loaded = client._load_batch_metadata("test_batch")

                assert loaded == metadata

    def test_load_missing_metadata_returns_empty(self):
        """_load_batch_metadata should return empty dict for missing batch."""
        from cortex.batch.batch_api_client import BatchAPIClient

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("cortex.batch.batch_api_client.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = MagicMock()

                client = BatchAPIClient()
                client.batch_dir = Path(tmpdir)

                loaded = client._load_batch_metadata("nonexistent_batch")

                assert loaded == {}
