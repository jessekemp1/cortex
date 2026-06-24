"""Tests for supervisor/local_provider.py — all external calls mocked."""

from unittest.mock import MagicMock, patch

import pytest

from supervisor.local_provider import (
    MLXProvider,
    OllamaProvider,
    get_local_provider,
    probe_all_local,
)


# ---------------------------------------------------------------------------
# OllamaProvider.is_available()
# ---------------------------------------------------------------------------


def test_ollama_available_when_running():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("supervisor.local_provider.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_resp
        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
        assert provider.is_available() is True
        mock_httpx.get.assert_called_once()


def test_ollama_unavailable_when_connection_refused():
    with patch("supervisor.local_provider.httpx") as mock_httpx:
        mock_httpx.get.side_effect = ConnectionRefusedError("refused")
        provider = OllamaProvider()
        assert provider.is_available() is False


def test_ollama_unavailable_on_non_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch("supervisor.local_provider.httpx") as mock_httpx:
        mock_httpx.get.return_value = mock_resp
        provider = OllamaProvider()
        assert provider.is_available() is False


# ---------------------------------------------------------------------------
# OllamaProvider.complete()
# ---------------------------------------------------------------------------


def test_ollama_complete_returns_text_and_tokens():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "hello world", "eval_count": 3}
    mock_resp.raise_for_status = MagicMock()

    with patch("supervisor.local_provider.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.HTTPStatusError = Exception  # so the except branch is never hit
        provider = OllamaProvider(model="llama3.2")
        text, tokens = provider.complete("Say hello.", max_tokens=64)

    assert text == "hello world"
    assert tokens == 3


def test_ollama_complete_estimates_tokens_when_missing():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "a" * 40}  # no eval_count
    mock_resp.raise_for_status = MagicMock()

    with patch("supervisor.local_provider.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.HTTPStatusError = Exception
        provider = OllamaProvider()
        text, tokens = provider.complete("test")

    assert text == "a" * 40
    assert tokens >= 1  # estimated, not zero


def test_ollama_complete_raises_on_network_error():
    with patch("supervisor.local_provider.httpx") as mock_httpx:
        # HTTPStatusError must be a distinct exception class so isinstance check works
        mock_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
        mock_httpx.post.side_effect = OSError("no route to host")
        provider = OllamaProvider()
        with pytest.raises(RuntimeError, match="Ollama request failed"):
            provider.complete("hello")


def test_ollama_complete_includes_system_in_payload():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": "ok", "eval_count": 1}
    mock_resp.raise_for_status = MagicMock()

    with patch("supervisor.local_provider.httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        mock_httpx.HTTPStatusError = Exception
        provider = OllamaProvider()
        provider.complete("prompt text", system="you are helpful", max_tokens=128)

    call_kwargs = mock_httpx.post.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
    assert payload.get("system") == "you are helpful"


# ---------------------------------------------------------------------------
# MLXProvider.is_available()
# ---------------------------------------------------------------------------


def test_mlx_unavailable_on_non_apple_silicon():
    with patch("supervisor.local_provider.platform") as mock_platform:
        mock_platform.processor.return_value = "x86_64"
        provider = MLXProvider()
        assert provider.is_available() is False


def test_mlx_unavailable_when_mlx_lm_not_installed():
    with patch("supervisor.local_provider.platform") as mock_platform:
        mock_platform.processor.return_value = "arm"
        with patch("supervisor.local_provider.importlib.util.find_spec", return_value=None):
            provider = MLXProvider()
            assert provider.is_available() is False


def test_mlx_available_on_apple_silicon_with_mlx_lm():
    mock_spec = MagicMock()
    with patch("supervisor.local_provider.platform") as mock_platform:
        mock_platform.processor.return_value = "arm"
        with patch("supervisor.local_provider.importlib.util.find_spec", return_value=mock_spec):
            provider = MLXProvider()
            assert provider.is_available() is True


def test_mlx_complete_raises_when_unavailable():
    with patch("supervisor.local_provider.platform") as mock_platform:
        mock_platform.processor.return_value = "x86_64"
        provider = MLXProvider()
        with pytest.raises(RuntimeError, match="not available"):
            provider.complete("hello")


# ---------------------------------------------------------------------------
# get_local_provider factory
# ---------------------------------------------------------------------------


def test_get_local_provider_returns_ollama_by_default():
    provider = get_local_provider()
    assert isinstance(provider, OllamaProvider)


def test_get_local_provider_returns_mlx():
    provider = get_local_provider(backend="mlx")
    assert isinstance(provider, MLXProvider)


def test_get_local_provider_passes_model():
    provider = get_local_provider(backend="ollama", model="mistral")
    assert isinstance(provider, OllamaProvider)
    assert provider._model == "mistral"


# ---------------------------------------------------------------------------
# probe_all_local()
# ---------------------------------------------------------------------------


def test_probe_all_local_returns_both_keys():
    with patch.object(OllamaProvider, "is_available", return_value=False):
        with patch.object(MLXProvider, "is_available", return_value=False):
            result = probe_all_local()
    assert "ollama" in result
    assert "mlx" in result
    assert result["ollama"]["available"] is False
    assert result["mlx"]["available"] is False


def test_probe_all_local_ollama_available():
    with patch.object(OllamaProvider, "is_available", return_value=True):
        with patch.object(MLXProvider, "is_available", return_value=False):
            result = probe_all_local()
    assert result["ollama"]["available"] is True
    assert result["ollama"]["backend"] == "ollama"
