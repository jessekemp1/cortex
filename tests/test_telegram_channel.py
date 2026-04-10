"""
Tests for cortex/notifications/telegram_channel.py
"""

from unittest.mock import MagicMock, patch

from notifications.telegram_channel import (
    format_alert,
    is_configured,
    send_message,
)


# ── is_configured ─────────────────────────────────────────────────────────────


def test_is_configured_false(monkeypatch):
    """No env vars → not configured."""
    monkeypatch.delenv("CORTEX_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("CORTEX_TELEGRAM_CHAT_ID", raising=False)
    # Prevent .env file reads from interfering
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = is_configured()
    assert result is False


def test_is_configured_true(monkeypatch):
    """Both env vars set → configured."""
    monkeypatch.setenv("CORTEX_TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("CORTEX_TELEGRAM_CHAT_ID", "12345")
    result = is_configured()
    assert result is True


# ── send_message ──────────────────────────────────────────────────────────────


def test_send_message_not_configured(monkeypatch):
    """No config → send_message returns False without making requests."""
    monkeypatch.delenv("CORTEX_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("CORTEX_TELEGRAM_CHAT_ID", raising=False)
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = send_message("hello")
    assert result is False


def test_send_message_success(monkeypatch):
    """Configured + HTTP 200 → returns True."""
    monkeypatch.setenv("CORTEX_TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("CORTEX_TELEGRAM_CHAT_ID", "12345")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("notifications.telegram_channel.urllib.request.urlopen", return_value=mock_response):
        result = send_message("test message")

    assert result is True


def test_send_message_network_error(monkeypatch):
    """Network error → returns False, does not raise."""
    import urllib.error

    monkeypatch.setenv("CORTEX_TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("CORTEX_TELEGRAM_CHAT_ID", "12345")

    with patch(
        "notifications.telegram_channel.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        result = send_message("test message")

    assert result is False


# ── format_alert ──────────────────────────────────────────────────────────────


def test_format_alert_critical():
    """CRITICAL alert has red emoji and correct HTML tags."""
    text = format_alert("CRITICAL", "Bridge Down", "Bridge is unreachable")
    assert "🔴" in text
    assert "<b>CORTEX CRITICAL</b>" in text
    assert "<b>Bridge Down</b>" in text
    assert "Bridge is unreachable" in text


def test_format_alert_with_source():
    """Source line is included when provided."""
    text = format_alert(
        "WARNING", "High Failures", "100 batch failures", source="threshold_detector"
    )
    assert "🟡" in text
    assert "<i>Source: threshold_detector</i>" in text


def test_format_alert_no_source():
    """No source line when source is empty."""
    text = format_alert("INFO", "Test", "Something happened")
    assert "<i>Source:" not in text
    assert "🔵" in text
