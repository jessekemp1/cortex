"""Base provider interface and shared data structures."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class CompletionResponse:
    """Standardized response from any provider."""

    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float  # Calculated from token counts + pricing


class ProviderError(Exception):
    """Raised when a provider API call fails."""

    def __init__(
        self,
        provider: str,
        status_code: int,
        message: str,
        retry_after: Optional[float] = None,
    ):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after  # seconds, from Retry-After header
        super().__init__(f"[{provider}] HTTP {status_code}: {message}")


class BaseProvider(ABC):
    """Abstract base for all provider clients."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @abstractmethod
    def complete(
        self,
        messages: List[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Send chat completion request and return standardized response."""

    async def async_complete(
        self,
        messages: List[ChatMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Async chat completion. Default wraps sync; subclasses override with native async."""
        return await asyncio.to_thread(
            self.complete,
            messages,
            model,
            max_tokens,
            temperature,
            **kwargs,
        )

    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and cost tracking."""

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_mtok: float,
        output_cost_per_mtok: float,
    ) -> float:
        """Calculate cost in USD from token counts and per-million-token pricing."""
        return (
            input_tokens * input_cost_per_mtok + output_tokens * output_cost_per_mtok
        ) / 1_000_000
