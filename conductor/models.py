#!/usr/bin/env python3
"""
Conductor data models.

Core data structures for multi-provider AI model routing.
Defines provider configs, model specs, routing requests, and decisions.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class ModelSpec:
    """
    Specification for a single AI model offered by a provider.

    Contains pricing, capability, and performance metadata used by
    the router to make cost-aware, capability-matched routing decisions.
    """

    model_id: str  # Full model ID for API calls (e.g., "claude-opus-4-6")
    display_name: str  # Human-readable name (e.g., "Opus 4.6")
    input_cost_per_mtok: float  # $ per million input tokens
    output_cost_per_mtok: float  # $ per million output tokens
    max_context: int  # Max context window in tokens
    max_output: int  # Max output tokens
    speed_tier: str  # "fast", "medium", "slow"
    strengths: List[str] = field(default_factory=list)  # e.g., ["classification", "code"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ProviderConfig:
    """
    Configuration for an AI provider (Groq, xAI, Anthropic, etc.).

    Each provider hosts one or more models accessible via a common
    base URL and authenticated by an API key stored in an env var.
    """

    name: str  # "groq", "xai", "minimax", "anthropic", "openai", "deepseek"
    api_key_env: str  # Env var name for API key (e.g., "GROQ_API_KEY")
    base_url: str  # API base URL
    models: Dict[str, ModelSpec]  # model_id -> ModelSpec
    max_context: int  # Max context window across all models
    supports_batch: bool  # Whether provider has a formal batch API

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        return data

    def get_model(self, model_id: str) -> ModelSpec | None:
        """Look up a model by its ID. Returns None if not found."""
        return self.models.get(model_id)

    def list_models(self) -> List[str]:
        """Return all model IDs available from this provider."""
        return list(self.models.keys())


@dataclass
class RoutingRequest:
    """
    A request to the conductor router for model selection.

    Callers specify their use case and constraints; the router
    returns a RoutingDecision with optimal provider+model.
    """

    task_description: str  # Free-text description of the task
    use_case: str = ""  # Explicit use case (overrides classification if set)
    # Values: "architecture", "interactive_coding",
    # "classification", "long_context", "research",
    # "quick_qa", "code_review", "test_generation",
    # "documentation", "security_audit", "pattern_learning"
    context_tokens: int = 0  # Estimated input context size in tokens
    batch_eligible: bool = False  # Whether this can run as a batch job
    priority: str = "medium"  # "high", "medium", "low"
    project: str = ""  # Project name for context-aware routing

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RoutingDecision:
    """
    The router's decision: which provider+model to use.

    Includes reasoning, cost estimate, and fallback path.
    """

    provider: str  # Provider name (e.g., "groq", "xai")
    model_id: str  # Full model ID for API calls
    display_name: str  # Human-readable model name
    reasoning: str  # Why this choice was made
    estimated_cost: float  # Estimated cost in USD for this request
    fallback_provider: str  # Fallback provider if primary fails
    fallback_model_id: str  # Fallback model ID
    confidence: float  # 0.0-1.0 confidence in routing decision

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# Type aliases
UseCase = str  # "architecture" | "interactive_coding" | "classification" | ...
SpeedTier = str  # "fast" | "medium" | "slow"
Priority = str  # "high" | "medium" | "low"
