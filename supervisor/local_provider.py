"""
Local inference providers — Ollama (cross-platform) and MLX (Apple Silicon).

Both implement the LocalProvider interface:
    is_available() -> bool          (fast health check, <1s timeout)
    complete(prompt, system, max_tokens) -> tuple[str, int]   (text, token_estimate)

Usage::

    from supervisor.local_provider import OllamaProvider, get_local_provider

    provider = get_local_provider(base_url="http://localhost:11434", model="llama3.2")
    if provider.is_available():
        text, tokens = provider.complete("Summarise this session.", max_tokens=256)

These are opt-in. If not configured or unavailable, callers should fall back to
the Anthropic API tier. No exceptions are raised for unavailability — only for
unexpected errors during completion.
"""

from __future__ import annotations

import importlib.util
import logging
import platform
from abc import ABC, abstractmethod
from typing import Optional

try:
    import httpx as httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

# Timeout for availability probes (seconds)
_PROBE_TIMEOUT = 2.0
# Rough token estimate: 1 token ≈ 4 chars
_CHARS_PER_TOKEN = 4


class LocalProvider(ABC):
    """Base class for local inference providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is reachable and ready."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
    ) -> tuple[str, int]:
        """
        Run inference. Returns (text, estimated_token_count).

        Raises RuntimeError on API/subprocess failure.
        Does NOT raise on unavailability — check is_available() first.
        """

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // _CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------


class OllamaProvider(LocalProvider):
    """
    Ollama local inference via its REST API.

    Requires Ollama running: `brew install ollama && ollama serve`
    Pull the model first: `ollama pull llama3.2`
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def is_available(self) -> bool:
        """Probe /api/tags — returns True if Ollama is running."""
        if httpx is None:
            return False
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=_PROBE_TIMEOUT)
            return resp.status_code == 200
        except Exception:
            return False

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
    ) -> tuple[str, int]:
        """
        POST to /api/generate (non-streaming).

        Returns (response_text, estimated_tokens).
        Raises RuntimeError on network or API error.
        """
        if httpx is None:
            raise RuntimeError("httpx is required for OllamaProvider — pip install httpx")

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if system:
            payload["system"] = system

        try:
            resp = httpx.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            # Catch httpx.HTTPStatusError (if httpx is available) and all other errors
            if httpx is not None and isinstance(exc, httpx.HTTPStatusError):
                raise RuntimeError(
                    f"Ollama API error {exc.response.status_code}: {exc.response.text[:200]}"
                ) from exc
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        text = data.get("response", "")
        # Ollama returns eval_count (output tokens) if available
        tokens = data.get("eval_count", self._estimate_tokens(prompt + text))
        log.debug("OllamaProvider: model=%s tokens=%d", self._model, tokens)
        return text, tokens


# ---------------------------------------------------------------------------
# MLX provider (Apple Silicon only)
# ---------------------------------------------------------------------------


class MLXProvider(LocalProvider):
    """
    MLX-LM local inference for Apple Silicon Macs.

    Requires: pip install mlx-lm
    Model pulls automatically on first use.
    """

    def __init__(
        self,
        model: str = "mlx-community/Llama-3.2-3B-Instruct-4bit",
    ) -> None:
        self._model = model

    def is_available(self) -> bool:
        """True only on Apple Silicon with mlx_lm installed."""
        if platform.processor() != "arm":
            return False
        if importlib.util.find_spec("mlx_lm") is None:
            return False
        return True

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
    ) -> tuple[str, int]:
        """
        Run inference via mlx_lm.generate().

        Returns (text, estimated_tokens).
        """
        if not self.is_available():
            raise RuntimeError(
                "MLXProvider is not available on this platform or mlx_lm is not installed"
            )

        try:
            from mlx_lm import generate, load  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("mlx_lm not installed — pip install mlx-lm") from exc

        try:
            model_obj, tokenizer = load(self._model)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            text = generate(
                model_obj, tokenizer, prompt=full_prompt, max_tokens=max_tokens, verbose=False
            )
            tokens = self._estimate_tokens(full_prompt + text)
            log.debug("MLXProvider: model=%s tokens=%d", self._model, tokens)
            return text, tokens
        except Exception as exc:
            raise RuntimeError(f"MLX inference failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_local_provider(
    backend: str = "ollama",
    base_url: str = "http://localhost:11434",
    model: Optional[str] = None,
) -> LocalProvider:
    """
    Return the appropriate LocalProvider for the given backend.

    Args:
        backend:  "ollama" or "mlx"
        base_url: Ollama base URL (ignored for MLX)
        model:    Model name. Defaults per backend if None.
    """
    if backend == "mlx":
        return MLXProvider(model=model or "mlx-community/Llama-3.2-3B-Instruct-4bit")
    # Default: ollama
    return OllamaProvider(base_url=base_url, model=model or "llama3.2")


def probe_all_local() -> dict:
    """
    Probe all known local backends. Returns availability dict.

    Returns::
        {
            "ollama": {"available": True, "model": "llama3.2", "backend": "ollama"},
            "mlx":    {"available": False, "reason": "not Apple Silicon"},
        }
    """
    result: dict = {}

    ollama = OllamaProvider()
    result["ollama"] = {
        "available": ollama.is_available(),
        "backend": "ollama",
        "model": ollama._model,
        "base_url": ollama._base_url,
    }

    mlx = MLXProvider()
    mlx_available = mlx.is_available()
    mlx_entry: dict = {"available": mlx_available, "backend": "mlx", "model": mlx._model}
    if not mlx_available:
        if platform.processor() != "arm":
            mlx_entry["reason"] = "not Apple Silicon"
        elif importlib.util.find_spec("mlx_lm") is None:
            mlx_entry["reason"] = "mlx_lm not installed"
    result["mlx"] = mlx_entry

    return result
