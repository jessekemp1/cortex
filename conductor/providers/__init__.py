"""Provider clients for multi-provider AI model conductor."""

from .base import BaseProvider, ChatMessage, CompletionResponse, ProviderError
from .openai_compat import OpenAICompatProvider
from .anthropic_provider import AnthropicProvider

# Backward-compat aliases — all OpenAI-compatible providers use the same class.
# Construct via create_provider() or directly with OpenAICompatProvider().
GroqProvider = OpenAICompatProvider
XAIProvider = OpenAICompatProvider
MiniMaxProvider = OpenAICompatProvider
OpenAIProvider = OpenAICompatProvider

__all__ = [
    "BaseProvider",
    "ChatMessage",
    "CompletionResponse",
    "ProviderError",
    "OpenAICompatProvider",
    "AnthropicProvider",
    # Backward-compat aliases
    "GroqProvider",
    "XAIProvider",
    "MiniMaxProvider",
    "OpenAIProvider",
]
