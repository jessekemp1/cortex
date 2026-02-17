"""Unit tests for provider clients — NO live API calls, all httpx mocked."""

import json
from unittest.mock import MagicMock, patch

import pytest

from cortex.conductor.providers.base import (
    BaseProvider,
    ChatMessage,
    CompletionResponse,
    ProviderError,
)
from cortex.conductor.providers.groq_provider import GroqProvider
from cortex.conductor.providers.xai_provider import XAIProvider
from cortex.conductor.providers.minimax_provider import MiniMaxProvider
from cortex.conductor.providers.openai_provider import OpenAIProvider
from cortex.conductor.providers.anthropic_provider import AnthropicProvider


# ---------------------------------------------------------------------------
# Fixtures: realistic API response shapes
# ---------------------------------------------------------------------------

OPENAI_COMPAT_RESPONSE = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1708000000,
    "model": "test-model",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello from the model."},
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 25,
        "completion_tokens": 10,
        "total_tokens": 35,
    },
}

ANTHROPIC_RESPONSE = {
    "id": "msg_abc123",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-20250514",
    "content": [
        {"type": "text", "text": "Hello from Claude."},
    ],
    "stop_reason": "end_turn",
    "usage": {
        "input_tokens": 30,
        "output_tokens": 12,
    },
}

SAMPLE_MESSAGES = [
    ChatMessage(role="system", content="You are helpful."),
    ChatMessage(role="user", content="Say hello."),
]


def _mock_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


def _mock_error_response(status_code: int, message: str) -> MagicMock:
    """Build a mock httpx error response."""
    body = {"error": {"message": message, "type": "error"}}
    return _mock_response(status_code, body)


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------


class TestCostCalculation:
    def test_cost_basic(self):
        """1M input tokens at $1/MTok + 500k output at $2/MTok = $2.00."""
        provider = GroqProvider(api_key="test-key")
        cost = provider._calculate_cost(
            input_tokens=1_000_000,
            output_tokens=500_000,
            input_cost_per_mtok=1.0,
            output_cost_per_mtok=2.0,
        )
        assert cost == pytest.approx(2.0)

    def test_cost_zero_tokens(self):
        provider = GroqProvider(api_key="test-key")
        cost = provider._calculate_cost(0, 0, 1.0, 1.0)
        assert cost == 0.0

    def test_cost_realistic_groq(self):
        """25 input + 10 output at Groq llama-3.1-8b pricing."""
        provider = GroqProvider(api_key="test-key")
        cost = provider._calculate_cost(25, 10, 0.05, 0.08)
        # (25 * 0.05 + 10 * 0.08) / 1_000_000 = (1.25 + 0.8) / 1_000_000
        expected = 2.05 / 1_000_000
        assert cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Groq provider
# ---------------------------------------------------------------------------


class TestGroqProvider:
    def test_name(self):
        p = GroqProvider(api_key="test-key")
        assert p.name() == "groq"

    def test_correct_headers(self):
        p = GroqProvider(api_key="gsk_test123")
        with patch("cortex.conductor.providers.groq_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES, model="llama-3.1-8b-instant")

            call_kwargs = mock_client.post.call_args
            headers = call_kwargs.kwargs["headers"]
            assert headers["Authorization"] == "Bearer gsk_test123"
            assert headers["Content-Type"] == "application/json"

    def test_parses_response(self):
        p = GroqProvider(api_key="test-key")
        with patch("cortex.conductor.providers.groq_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            result = p.complete(SAMPLE_MESSAGES, model="llama-3.1-8b-instant")

            assert isinstance(result, CompletionResponse)
            assert result.content == "Hello from the model."
            assert result.provider == "groq"
            assert result.input_tokens == 25
            assert result.output_tokens == 10
            assert result.total_tokens == 35
            assert result.cost_usd > 0

    def test_correct_url(self):
        p = GroqProvider(api_key="test-key")
        with patch("cortex.conductor.providers.groq_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            url = mock_client.post.call_args.args[0]
            assert url == "https://api.groq.com/openai/v1/chat/completions"

    def test_missing_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ProviderError, match="GROQ_API_KEY not set"):
                GroqProvider(api_key=None)


# ---------------------------------------------------------------------------
# xAI provider
# ---------------------------------------------------------------------------


class TestXAIProvider:
    def test_name(self):
        p = XAIProvider(api_key="test-key")
        assert p.name() == "xai"

    def test_correct_headers(self):
        p = XAIProvider(api_key="xai-test456")
        with patch("cortex.conductor.providers.xai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES, model="grok-3-fast")

            headers = mock_client.post.call_args.kwargs["headers"]
            assert headers["Authorization"] == "Bearer xai-test456"

    def test_parses_response(self):
        p = XAIProvider(api_key="test-key")
        with patch("cortex.conductor.providers.xai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            result = p.complete(SAMPLE_MESSAGES, model="grok-3-fast")

            assert result.content == "Hello from the model."
            assert result.provider == "xai"
            assert result.total_tokens == 35

    def test_correct_url(self):
        p = XAIProvider(api_key="test-key")
        with patch("cortex.conductor.providers.xai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            url = mock_client.post.call_args.args[0]
            assert url == "https://api.x.ai/v1/chat/completions"


# ---------------------------------------------------------------------------
# MiniMax provider
# ---------------------------------------------------------------------------


class TestMiniMaxProvider:
    def test_name(self):
        p = MiniMaxProvider(api_key="test-key")
        assert p.name() == "minimax"

    def test_parses_response(self):
        p = MiniMaxProvider(api_key="test-key")
        with patch("cortex.conductor.providers.minimax_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            result = p.complete(SAMPLE_MESSAGES, model="MiniMax-M1-80k")

            assert result.content == "Hello from the model."
            assert result.provider == "minimax"

    def test_correct_url(self):
        p = MiniMaxProvider(api_key="test-key")
        with patch("cortex.conductor.providers.minimax_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            url = mock_client.post.call_args.args[0]
            assert url == "https://api.minimax.chat/v1/chat/completions"


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class TestOpenAIProvider:
    def test_name_openai(self):
        p = OpenAIProvider(api_key="test-key")
        assert p.name() == "openai"

    def test_name_deepseek(self):
        p = OpenAIProvider(api_key="test-key", base_url="https://api.deepseek.com")
        assert p.name() == "deepseek"

    def test_parses_response(self):
        p = OpenAIProvider(api_key="test-key")
        with patch("cortex.conductor.providers.openai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            result = p.complete(SAMPLE_MESSAGES, model="gpt-4o-mini")

            assert result.content == "Hello from the model."
            assert result.provider == "openai"
            assert result.input_tokens == 25
            assert result.output_tokens == 10

    def test_correct_url_openai(self):
        p = OpenAIProvider(api_key="test-key")
        with patch("cortex.conductor.providers.openai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            url = mock_client.post.call_args.args[0]
            assert url == "https://api.openai.com/v1/chat/completions"

    def test_correct_url_deepseek(self):
        p = OpenAIProvider(api_key="test-key", base_url="https://api.deepseek.com")
        with patch("cortex.conductor.providers.openai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES, model="deepseek-chat")

            url = mock_client.post.call_args.args[0]
            assert url == "https://api.deepseek.com/chat/completions"

    def test_cost_gpt4o_mini(self):
        """Verify gpt-4o-mini cost at known pricing."""
        p = OpenAIProvider(api_key="test-key")
        with patch("cortex.conductor.providers.openai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            result = p.complete(SAMPLE_MESSAGES, model="gpt-4o-mini")

            # 25 input * $0.15/MTok + 10 output * $0.60/MTok = (3.75 + 6.0) / 1M
            expected_cost = (25 * 0.15 + 10 * 0.60) / 1_000_000
            assert result.cost_usd == pytest.approx(expected_cost)


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    def test_name(self):
        p = AnthropicProvider(api_key="test-key")
        assert p.name() == "anthropic"

    def test_correct_headers_not_bearer(self):
        """Anthropic uses x-api-key, NOT Authorization: Bearer."""
        p = AnthropicProvider(api_key="sk-ant-test789")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            headers = mock_client.post.call_args.kwargs["headers"]
            assert headers["x-api-key"] == "sk-ant-test789"
            assert headers["anthropic-version"] == "2023-06-01"
            assert "Authorization" not in headers

    def test_system_message_extraction(self):
        """System messages should be a top-level param, not in messages array."""
        p = AnthropicProvider(api_key="test-key")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            payload = mock_client.post.call_args.kwargs["json"]
            # System should be top-level, not in messages
            assert payload["system"] == "You are helpful."
            # Messages should only contain user/assistant, not system
            assert all(m["role"] != "system" for m in payload["messages"])
            assert len(payload["messages"]) == 1
            assert payload["messages"][0]["role"] == "user"

    def test_parses_content_blocks(self):
        """Anthropic returns content as an array of typed blocks."""
        p = AnthropicProvider(api_key="test-key")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            result = p.complete(SAMPLE_MESSAGES)

            assert result.content == "Hello from Claude."
            assert result.provider == "anthropic"
            assert result.input_tokens == 30
            assert result.output_tokens == 12
            assert result.total_tokens == 42

    def test_multiple_content_blocks(self):
        """Multiple text blocks should be joined with newlines."""
        multi_block_response = {
            **ANTHROPIC_RESPONSE,
            "content": [
                {"type": "text", "text": "Part 1."},
                {"type": "text", "text": "Part 2."},
            ],
        }
        p = AnthropicProvider(api_key="test-key")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, multi_block_response)

            result = p.complete(SAMPLE_MESSAGES)
            assert result.content == "Part 1.\nPart 2."

    def test_correct_url(self):
        """Anthropic uses /messages, not /chat/completions."""
        p = AnthropicProvider(api_key="test-key")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            url = mock_client.post.call_args.args[0]
            assert url == "https://api.anthropic.com/v1/messages"

    def test_no_system_message(self):
        """When no system message, payload should not include system key."""
        p = AnthropicProvider(api_key="test-key")
        messages_no_sys = [ChatMessage(role="user", content="Hi")]
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            p.complete(messages_no_sys)

            payload = mock_client.post.call_args.kwargs["json"]
            assert "system" not in payload


# ---------------------------------------------------------------------------
# Error handling (all providers)
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling across all providers."""

    @pytest.fixture(
        params=[
            ("groq", GroqProvider, "cortex.conductor.providers.groq_provider.httpx.Client"),
            ("xai", XAIProvider, "cortex.conductor.providers.xai_provider.httpx.Client"),
            (
                "minimax",
                MiniMaxProvider,
                "cortex.conductor.providers.minimax_provider.httpx.Client",
            ),
            ("openai", OpenAIProvider, "cortex.conductor.providers.openai_provider.httpx.Client"),
            (
                "anthropic",
                AnthropicProvider,
                "cortex.conductor.providers.anthropic_provider.httpx.Client",
            ),
        ]
    )
    def provider_setup(self, request):
        name, cls, patch_target = request.param
        return cls(api_key="test-key"), patch_target, name

    def test_401_unauthorized(self, provider_setup):
        provider, patch_target, name = provider_setup
        with patch(patch_target) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_error_response(401, "Invalid API key")

            with pytest.raises(ProviderError) as exc_info:
                provider.complete(SAMPLE_MESSAGES)

            assert exc_info.value.status_code == 401
            assert exc_info.value.provider == name
            assert "Invalid API key" in str(exc_info.value)

    def test_429_rate_limit(self, provider_setup):
        provider, patch_target, name = provider_setup
        with patch(patch_target) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_error_response(429, "Rate limit exceeded")

            with pytest.raises(ProviderError) as exc_info:
                provider.complete(SAMPLE_MESSAGES)

            assert exc_info.value.status_code == 429

    def test_500_server_error(self, provider_setup):
        provider, patch_target, name = provider_setup
        with patch(patch_target) as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_error_response(500, "Internal server error")

            with pytest.raises(ProviderError) as exc_info:
                provider.complete(SAMPLE_MESSAGES)

            assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# ProviderError structure
# ---------------------------------------------------------------------------


class TestProviderError:
    def test_error_attributes(self):
        err = ProviderError("groq", 429, "Rate limited")
        assert err.provider == "groq"
        assert err.status_code == 429
        assert err.message == "Rate limited"

    def test_error_str(self):
        err = ProviderError("anthropic", 401, "Invalid key")
        assert "[anthropic] HTTP 401: Invalid key" in str(err)

    def test_error_is_exception(self):
        err = ProviderError("openai", 500, "Server error")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------


class TestMessageConstruction:
    def test_openai_compat_message_format(self):
        """OpenAI-compatible providers send messages as list of dicts."""
        p = GroqProvider(api_key="test-key")
        with patch("cortex.conductor.providers.groq_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["messages"] == [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Say hello."},
            ]

    def test_anthropic_message_format(self):
        """Anthropic filters system messages out of messages array."""
        p = AnthropicProvider(api_key="test-key")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            p.complete(SAMPLE_MESSAGES)

            payload = mock_client.post.call_args.kwargs["json"]
            # System is top-level
            assert payload["system"] == "You are helpful."
            # Only non-system messages in array
            assert payload["messages"] == [
                {"role": "user", "content": "Say hello."},
            ]


# ---------------------------------------------------------------------------
# Temperature and max_tokens pass-through
# ---------------------------------------------------------------------------


class TestParameterPassthrough:
    def test_temperature_and_max_tokens(self):
        p = OpenAIProvider(api_key="test-key")
        with patch("cortex.conductor.providers.openai_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, OPENAI_COMPAT_RESPONSE)

            p.complete(SAMPLE_MESSAGES, model="gpt-4o", max_tokens=8192, temperature=0.7)

            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["max_tokens"] == 8192
            assert payload["temperature"] == 0.7
            assert payload["model"] == "gpt-4o"

    def test_anthropic_temperature_and_max_tokens(self):
        p = AnthropicProvider(api_key="test-key")
        with patch("cortex.conductor.providers.anthropic_provider.httpx.Client") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = _mock_response(200, ANTHROPIC_RESPONSE)

            p.complete(
                SAMPLE_MESSAGES,
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                temperature=0.5,
            )

            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["max_tokens"] == 2048
            assert payload["temperature"] == 0.5
            assert payload["model"] == "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# Base URL trailing slash normalization
# ---------------------------------------------------------------------------


class TestBaseURLNormalization:
    def test_trailing_slash_stripped(self):
        p = GroqProvider(api_key="test-key", base_url="https://api.groq.com/openai/v1/")
        assert p.base_url == "https://api.groq.com/openai/v1"

    def test_no_trailing_slash(self):
        p = XAIProvider(api_key="test-key", base_url="https://api.x.ai/v1")
        assert p.base_url == "https://api.x.ai/v1"
