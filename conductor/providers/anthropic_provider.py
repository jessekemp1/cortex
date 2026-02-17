"""Anthropic provider — uses the Messages API (NOT OpenAI-compatible)."""

import os
import time
from typing import Any, Dict, List, Tuple

import httpx

from .base import BaseProvider, ChatMessage, CompletionResponse, ProviderError

# Pricing: (input_cost_per_mtok, output_cost_per_mtok) in USD
PRICING: Dict[str, Tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-haiku-3-5-20241022": (0.80, 4.00),
    # Aliases
    "claude-sonnet-4-0": (3.00, 15.00),
    "claude-opus-4-0": (15.00, 75.00),
}

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    """Anthropic provider using the Messages API.

    Unlike other providers, Anthropic does NOT use the OpenAI chat completions
    format. Key differences:
    - Auth via x-api-key header (not Bearer token)
    - System messages are a top-level parameter, not in the messages array
    - Response shape differs: content is an array of content blocks
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            raise ProviderError("anthropic", 0, "ANTHROPIC_API_KEY not set")
        super().__init__(resolved_key, base_url)

    def name(self) -> str:
        return "anthropic"

    def complete(
        self,
        messages: List[ChatMessage],
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> CompletionResponse:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        # Anthropic requires system messages as a top-level param, not in messages
        system_text = None
        api_messages = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                api_messages.append({"role": m.role, "content": m.content})

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": api_messages,
            "temperature": temperature,
        }
        if system_text is not None:
            payload["system"] = system_text

        # Pass through any extra kwargs (e.g., top_p, stop_sequences)
        for k, v in kwargs.items():
            if k not in payload:
                payload[k] = v

        t0 = time.monotonic()
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
            )
        latency_ms = (time.monotonic() - t0) * 1000

        if resp.status_code != 200:
            self._raise_error(resp)

        data = resp.json()

        # Extract text from content blocks
        content_blocks = data.get("content", [])
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block["text"])
        content = "\n".join(text_parts) if text_parts else ""

        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        pricing = PRICING.get(model, (3.00, 15.00))
        cost = self._calculate_cost(input_tokens, output_tokens, pricing[0], pricing[1])

        return CompletionResponse(
            content=content,
            model=data.get("model", model),
            provider=self.name(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
        )

    def _raise_error(self, resp: httpx.Response) -> None:
        try:
            body = resp.json()
            err = body.get("error", {})
            msg = err.get("message", resp.text) if isinstance(err, dict) else resp.text
        except Exception:
            msg = resp.text
        raise ProviderError(self.name(), resp.status_code, msg)
