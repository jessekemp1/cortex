"""Groq provider — OpenAI-compatible chat completions API."""

import os
import time
from typing import Any, Dict, List, Tuple

import httpx

from .base import BaseProvider, ChatMessage, CompletionResponse, ProviderError

# Pricing: (input_cost_per_mtok, output_cost_per_mtok) in USD
PRICING: Dict[str, Tuple[float, float]] = {
    "llama-3.1-8b-instant": (0.05, 0.08),
    "openai/gpt-oss-20b": (0.075, 0.30),
}

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(BaseProvider):
    """Groq cloud inference provider (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        resolved_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not resolved_key:
            raise ProviderError("groq", 0, "GROQ_API_KEY not set")
        super().__init__(resolved_key, base_url)

    def name(self) -> str:
        return "groq"

    def complete(
        self,
        messages: List[ChatMessage],
        model: str = "llama-3.1-8b-instant",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> CompletionResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        payload.update(kwargs)

        t0 = time.monotonic()
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        latency_ms = (time.monotonic() - t0) * 1000

        if resp.status_code != 200:
            self._raise_error(resp)

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        pricing = PRICING.get(model, (0.05, 0.08))
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
            msg = body.get("error", {}).get("message", resp.text)
        except Exception:
            msg = resp.text
        raise ProviderError(self.name(), resp.status_code, msg)
