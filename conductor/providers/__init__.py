"""Provider clients for multi-provider AI model conductor."""

from .base import BaseProvider, ChatMessage, CompletionResponse, ProviderError
from .groq_provider import GroqProvider
from .xai_provider import XAIProvider
from .minimax_provider import MiniMaxProvider
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider

# DeepSeek uses OpenAI-compatible API — instantiate OpenAIProvider with:
#   OpenAIProvider(api_key=key, base_url="https://api.deepseek.com")
# and call with model="deepseek-chat"

__all__ = [
    "BaseProvider",
    "ChatMessage",
    "CompletionResponse",
    "ProviderError",
    "GroqProvider",
    "XAIProvider",
    "MiniMaxProvider",
    "AnthropicProvider",
    "OpenAIProvider",
]
