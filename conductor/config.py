"""
Single source of truth for all provider, model, and routing configuration.

Every other module reads from here. No provider/model data is duplicated elsewhere.
"""

from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Provider + Model Configuration
# ---------------------------------------------------------------------------
# api_type: "openai_compat" uses /chat/completions, "anthropic" uses /messages
# Models: input_cost/output_cost in $/MTok

PROVIDERS: Dict[str, dict] = {
    "groq": {
        "env_var": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "api_type": "openai_compat",
        "timeout": 60.0,
        "supports_batch": False,
        "models": {
            "llama-3.1-8b-instant": {
                "display_name": "Groq Llama 8B",
                "input_cost": 0.05,
                "output_cost": 0.08,
                "max_context": 131_072,
                "max_output": 8_192,
                "speed": "fast",
                "strengths": ["classification"],
            },
            "openai/gpt-oss-20b": {
                "display_name": "Groq GPT-OSS 20B",
                "input_cost": 0.075,
                "output_cost": 0.30,
                "max_context": 131_072,
                "max_output": 16_384,
                "speed": "fast",
                "strengths": ["qa", "classification"],
            },
        },
    },
    "xai": {
        "env_var": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "api_type": "openai_compat",
        "timeout": 120.0,
        "supports_batch": False,
        "models": {
            "grok-3-fast": {
                "display_name": "Grok 4.1 Fast",
                "input_cost": 0.20,
                "output_cost": 0.50,
                "max_context": 2_000_000,
                "max_output": 131_072,
                "speed": "fast",
                "strengths": ["long_context", "research"],
            },
            "grok-code-fast-1": {
                "display_name": "Grok Code Fast 1",
                "input_cost": 0.20,
                "output_cost": 1.50,
                "max_context": 131_072,
                "max_output": 131_072,
                "speed": "fast",
                "strengths": ["code", "interactive_coding", "test_generation"],
            },
        },
    },
    "minimax": {
        "env_var": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.io/v1",
        "api_type": "openai_compat",
        "timeout": 120.0,
        "supports_batch": True,
        "models": {
            "MiniMax-M1": {
                "display_name": "MiniMax M1",
                "input_cost": 0.30,
                "output_cost": 1.20,
                "max_context": 1_000_000,
                "max_output": 80_000,
                "speed": "slow",
                "strengths": ["long_context", "reasoning"],
            },
            "MiniMax-M2.1": {
                "display_name": "MiniMax M2.1 Coder",
                "input_cost": 0.30,
                "output_cost": 1.20,
                "max_context": 200_000,
                "max_output": 128_000,
                "speed": "medium",
                "strengths": ["code", "code_review", "test_generation", "interactive_coding"],
            },
        },
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "api_type": "anthropic",
        "timeout": 120.0,
        "supports_batch": True,
        "models": {
            "claude-opus-4-6": {
                "display_name": "Opus 4.6",
                "input_cost": 15.0,
                "output_cost": 75.0,
                "max_context": 200_000,
                "max_output": 32_000,
                "speed": "slow",
                "strengths": ["architecture", "security", "security_audit"],
            },
            "claude-sonnet-4-5-20250929": {
                "display_name": "Sonnet 4.5",
                "input_cost": 3.0,
                "output_cost": 15.0,
                "max_context": 200_000,
                "max_output": 16_384,
                "speed": "fast",
                "strengths": ["interactive_coding", "code"],
            },
            "claude-haiku-4-5-20251001": {
                "display_name": "Haiku 4.5",
                "input_cost": 1.0,
                "output_cost": 5.0,
                "max_context": 200_000,
                "max_output": 8_192,
                "speed": "fast",
                "strengths": ["qa", "quick_qa"],
            },
        },
    },
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "api_type": "openai_compat",
        "timeout": 120.0,
        "supports_batch": True,
        "models": {
            # NOTE: Verify model ID availability — may not be publicly released yet
            "gpt-5": {
                "display_name": "GPT-5",
                "input_cost": 2.50,
                "output_cost": 20.0,
                "max_context": 400_000,
                "max_output": 32_768,
                "speed": "medium",
                "strengths": ["reasoning", "research", "architecture"],
            },
            # NOTE: Verify model ID availability — may not be publicly released yet
            "gpt-5-nano": {
                "display_name": "GPT-5 Nano",
                "input_cost": 0.10,
                "output_cost": 0.80,
                "max_context": 128_000,
                "max_output": 16_384,
                "speed": "fast",
                "strengths": ["classification"],
            },
        },
    },
    "deepseek": {
        "env_var": "DEEPSEEK_API_KEY",
        "fallback_env": "OPENAI_API_KEY",
        "base_url": "https://api.deepseek.com",
        "api_type": "openai_compat",
        "timeout": 120.0,
        "supports_batch": False,
        "models": {
            "deepseek-chat": {
                "display_name": "DeepSeek V3.2",
                "input_cost": 0.28,
                "output_cost": 0.42,
                "max_context": 128_000,
                "max_output": 16_384,
                "speed": "medium",
                "strengths": ["pattern_learning", "research", "documentation"],
            },
            "deepseek-reasoner": {
                "display_name": "DeepSeek R1",
                "input_cost": 0.55,
                "output_cost": 2.19,
                "max_context": 128_000,
                "max_output": 16_384,
                "speed": "slow",
                "strengths": ["reasoning", "architecture", "research"],
            },
        },
    },
    "qwen": {
        "env_var": "QWEN_API_KEY",
        "fallback_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "api_type": "openai_compat",
        "timeout": 120.0,
        "supports_batch": False,
        "models": {
            "qwen-plus": {
                "display_name": "Qwen Plus",
                "input_cost": 0.80,
                "output_cost": 2.00,
                "max_context": 131_072,
                "max_output": 16_384,
                "speed": "fast",
                "strengths": ["code", "code_review", "research", "documentation"],
            },
            "qwen-turbo": {
                "display_name": "Qwen Turbo",
                "input_cost": 0.30,
                "output_cost": 0.60,
                "max_context": 1_000_000,
                "max_output": 16_384,
                "speed": "fast",
                "strengths": ["classification", "quick_qa", "documentation", "long_context"],
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Routing Tables
# ---------------------------------------------------------------------------
# use_case -> (primary_provider, primary_model, fallback_provider, fallback_model)

ROUTING_TABLE: Dict[str, Tuple[str, str, str, str]] = {
    "architecture": ("anthropic", "claude-opus-4-6", "openai", "gpt-5"),
    "interactive_coding": ("anthropic", "claude-sonnet-4-5-20250929", "xai", "grok-code-fast-1"),
    "classification": ("groq", "llama-3.1-8b-instant", "deepseek", "deepseek-chat"),
    "long_context": ("qwen", "qwen-turbo", "xai", "grok-3-fast"),
    "research": ("deepseek", "deepseek-chat", "xai", "grok-3-fast"),
    "quick_qa": ("groq", "openai/gpt-oss-20b", "anthropic", "claude-haiku-4-5-20251001"),
    "code_review": ("minimax", "MiniMax-M2.1", "anthropic", "claude-sonnet-4-5-20250929"),
    "test_generation": ("minimax", "MiniMax-M2.1", "xai", "grok-code-fast-1"),
    "documentation": ("deepseek", "deepseek-chat", "qwen", "qwen-turbo"),
    "security_audit": ("anthropic", "claude-opus-4-6", "openai", "gpt-5"),
    "pattern_learning": ("deepseek", "deepseek-chat", "groq", "llama-3.1-8b-instant"),
}

BATCH_ROUTING_TABLE: Dict[str, Tuple[str, str, str, str]] = {
    "code_review": ("minimax", "MiniMax-M2.1", "anthropic", "claude-sonnet-4-5-20250929"),
    "test_generation": ("minimax", "MiniMax-M2.1", "xai", "grok-code-fast-1"),
    "documentation": ("deepseek", "deepseek-chat", "qwen", "qwen-turbo"),
    "security_audit": ("anthropic", "claude-opus-4-6", "openai", "gpt-5"),
}

VALID_USE_CASES = set(ROUTING_TABLE.keys())

LONG_CONTEXT_THRESHOLD = 200_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_pricing(provider_name: str) -> Dict[str, Tuple[float, float]]:
    """Extract pricing dict for a provider (model_id -> (input, output) $/MTok)."""
    provider = PROVIDERS.get(provider_name, {})
    return {
        model_id: (m["input_cost"], m["output_cost"])
        for model_id, m in provider.get("models", {}).items()
    }
