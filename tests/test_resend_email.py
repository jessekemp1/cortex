"""Tests for the Resend email service."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from notifications.resend_email import (
    EmailMessage,
    EmailResult,
    send_email,
    send_briefing_email,
    _get_api_key,
)


class TestEmailMessage:
    def test_create_message(self):
        msg = EmailMessage(
            to=["test@example.com"],
            subject="Test",
            html="<p>Hello</p>",
        )
        assert msg.to == ["test@example.com"]
        assert msg.subject == "Test"
        assert msg.html == "<p>Hello</p>"
        assert msg.text is None

    def test_message_with_all_fields(self):
        msg = EmailMessage(
            to=["a@b.com", "c@d.com"],
            subject="Full",
            html="<p>Test</p>",
            text="Test",
            from_address="custom@sender.com",
            reply_to="reply@sender.com",
            tags=[{"name": "type", "value": "test"}],
        )
        assert len(msg.to) == 2
        assert msg.from_address == "custom@sender.com"
        assert msg.reply_to == "reply@sender.com"
        assert len(msg.tags) == 1


class TestEmailResult:
    def test_success_result(self):
        result = EmailResult(success=True, email_id="abc123", status_code=200)
        assert result.success is True
        assert result.email_id == "abc123"

    def test_failure_result(self):
        result = EmailResult(success=False, error="No API key")
        assert result.success is False
        assert "API key" in result.error


class TestGetApiKey:
    def test_from_environment(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key"}):
            key = _get_api_key()
            assert key == "re_test_key"

    def test_no_key_available(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                key = _get_api_key()
                assert key is None


class TestSendEmail:
    def test_no_api_key_returns_failure(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                msg = EmailMessage(to=["a@b.com"], subject="Test", html="<p>Hi</p>")
                result = send_email(msg)
                assert result.success is False
                assert "API key" in result.error

    def test_send_with_explicit_key(self):
        """Test that send_email constructs correct payload (mocked network)."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"id": "email_123"}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("notifications.resend_email.urlopen", return_value=mock_response) as mock_urlopen:
            msg = EmailMessage(
                to=["test@example.com"],
                subject="Test Send",
                html="<p>Hello</p>",
                text="Hello",
            )
            result = send_email(msg, api_key="re_test_key")

            assert result.success is True
            assert result.email_id == "email_123"

            # Verify the request was constructed correctly
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.get_header("Authorization") == "Bearer re_test_key"
            assert request.get_header("Content-type") == "application/json"

            body = json.loads(request.data.decode())
            assert body["to"] == ["test@example.com"]
            assert body["subject"] == "Test Send"
            assert body["html"] == "<p>Hello</p>"
            assert body["text"] == "Hello"

    def test_http_error_handled(self):
        from urllib.error import HTTPError
        import io

        error = HTTPError(
            url="https://api.resend.com/emails",
            code=422,
            msg="Unprocessable",
            hdrs={},
            fp=io.BytesIO(b'{"message":"Invalid email"}'),
        )

        with patch("notifications.resend_email.urlopen", side_effect=error):
            msg = EmailMessage(to=["bad"], subject="Test", html="<p>Hi</p>")
            result = send_email(msg, api_key="re_test")
            assert result.success is False
            assert result.status_code == 422
            assert "Invalid email" in result.error


class TestSendBriefingEmail:
    def test_convenience_function(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"id": "brief_001"}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("notifications.resend_email.urlopen", return_value=mock_response):
            result = send_briefing_email(
                to="jessekemp1@gmail.com",
                subject="Test Briefing",
                briefing_html="<p>Dawn briefing</p>",
                briefing_text="Dawn briefing",
                api_key="re_test",
            )
            assert result.success is True
            assert result.email_id == "brief_001"
