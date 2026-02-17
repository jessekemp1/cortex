"""
Unified OpenAI-compatible provider.

Works for Groq, xAI, MiniMax, OpenAI, DeepSeek — any API that speaks
the /chat/completions protocol. Replaces 4 separate provider files.
"""

import os
import time
from typing import Any, Dict, List, Tuple

import httpx

from .base import BaseProvider, ChatMessage, CompletionResponse, ProviderError


class OpenAICompatProvider(BaseProvider):
    """Universal provider for any OpenAI-compatible chat completions API.

    Parameterized at construction — provider name, base URL, pricing, and
    timeout are all configuration, not code.
    """

    def __init__(
        self,
        provider_name: str,
        api_key: str | None = None,
        env_var: str = "OPENAI_API_KEY",
        base_url: str = "https://api.openai.com/v1",
        pricing: Dict[str, Tuple[float, float]] | None = None,
        timeout: float = 120.0,
    ):
        self._provider_name = provider_name
        self._pricing = pricing or {}
        self._timeout = timeout

        resolved_key = api_key or os.environ.get(env_var, "")
        if not resolved_key:
            raise ProviderError(provider_name, 0, f"{env_var} not set")
        super().__init__(resolved_key, base_url)

    def name(self) -> str:
        return self._provider_name

    def complete(
        self,
        messages: List[ChatMessage],
        model: str = "",
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
        with httpx.Client(timeout=self._timeout) as client:
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

        default_pricing = (1.0, 3.0)
        pricing = self._pricing.get(model, default_pricing)
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

    async def async_complete(
        self,
        messages: List[ChatMessage],
        model: str = "",
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
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
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

        default_pricing = (1.0, 3.0)
        pricing = self._pricing.get(model, default_pricing)
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
