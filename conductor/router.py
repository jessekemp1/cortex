#!/usr/bin/env python3
"""
Conductor Router.

Routes AI requests to the optimal provider+model based on use case,
cost, context size, and batch eligibility. Reads all configuration
from config.py (single source of truth).
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple

try:
    from cortex.conductor.config import (
        BATCH_ROUTING_TABLE,
        LONG_CONTEXT_THRESHOLD,
        ROUTING_TABLE,
        VALID_USE_CASES,
    )
    from cortex.conductor.models import RoutingDecision, RoutingRequest
    from cortex.conductor.registry import get_all_providers, get_model_spec
except ImportError:
    from .config import (  # type: ignore[no-redef]
        BATCH_ROUTING_TABLE,
        LONG_CONTEXT_THRESHOLD,
        ROUTING_TABLE,
        VALID_USE_CASES,
    )
    from .models import RoutingDecision, RoutingRequest  # type: ignore[no-redef]
    from .registry import get_all_providers, get_model_spec  # type: ignore[no-redef]


class _Route(NamedTuple):
    """Internal routing table entry."""

    primary_provider: str
    primary_model: str
    fallback_provider: str
    fallback_model: str


# Convert config tuples to _Route NamedTuples for attribute access
_ROUTES: Dict[str, _Route] = {k: _Route(*v) for k, v in ROUTING_TABLE.items()}
_BATCH_ROUTES: Dict[str, _Route] = {k: _Route(*v) for k, v in BATCH_ROUTING_TABLE.items()}


class UseCaseClassifier:
    """Classify a task description into a use case via keyword matching."""

    KEYWORD_MAP: Dict[str, List[str]] = {
        "architecture": [
            "architect",
            "architecture",
            "system design",
            "design system",
            "design pattern",
            "high-level design",
            "microservice",
            "monolith",
            "decompose",
            "component diagram",
            "tech stack",
        ],
        "security_audit": [
            "security audit",
            "vulnerability",
            "penetration",
            "cve",
            "exploit",
            "injection",
            "xss",
            "csrf",
            "auth bypass",
            "security review",
            "threat model",
            "owasp",
        ],
        "interactive_coding": [
            "implement",
            "write code",
            "build a",
            "create a function",
            "add feature",
            "coding",
            "develop",
            "program",
            "scaffold",
            "boilerplate",
        ],
        "code_review": [
            "code review",
            "review code",
            "review this",
            "review the",
            "pull request",
            "pr review",
            "diff review",
            "review my",
            "code quality",
            "lint",
        ],
        "test_generation": [
            "write test",
            "generate test",
            "test case",
            "unit test",
            "integration test",
            "test suite",
            "test coverage",
            "add tests",
            "create tests",
            "e2e test",
        ],
        "documentation": [
            "document",
            "documentation",
            "write docs",
            "api docs",
            "docstring",
            "readme",
            "changelog",
            "jsdoc",
            "sphinx",
            "mkdocs",
        ],
        "research": [
            "research",
            "investigate",
            "analyze",
            "compare",
            "evaluate",
            "benchmark",
            "study",
            "literature",
            "state of the art",
            "pros and cons",
            "trade-off",
        ],
        "classification": [
            "classify",
            "categorize",
            "label",
            "tag",
            "sentiment",
            "detect",
            "identify type",
            "sort into",
            "bucket",
            "triage",
        ],
        "pattern_learning": [
            "pattern",
            "learn from",
            "extract pattern",
            "recurring",
            "trend",
            "anomaly",
            "cluster",
            "correlation",
            "signal",
        ],
        "long_context": [
            "entire codebase",
            "full repository",
            "whole file",
            "large document",
            "book",
            "long transcript",
            "entire conversation",
            "all files",
            "complete history",
        ],
        "quick_qa": [
            "what is",
            "what does",
            "how do",
            "how to",
            "explain",
            "why does",
            "tell me",
            "quick question",
            "help me understand",
            "what's the difference",
            "summarize",
            "tldr",
        ],
    }

    def classify(self, task_description: str) -> tuple[str, float]:
        """Classify a task description into a use case.

        Returns:
            Tuple of (use_case, confidence 0.0-1.0)
        """
        desc_lower = task_description.lower()

        scores: Dict[str, int] = {}
        for use_case, keywords in self.KEYWORD_MAP.items():
            hits = sum(1 for kw in keywords if kw in desc_lower)
            if hits > 0:
                scores[use_case] = hits

        if not scores:
            return ("quick_qa", 0.3)

        best_use_case = max(scores, key=scores.__getitem__)
        best_hits = scores[best_use_case]
        total_hits = sum(scores.values())

        if total_hits == 0:
            confidence = 0.3
        else:
            dominance = best_hits / total_hits
            confidence = min(0.95, 0.5 + dominance * 0.45)

        if best_hits >= 3:
            confidence = min(0.95, confidence + 0.1)

        return (best_use_case, confidence)


class ConductorRouter:
    """Routes AI requests to the optimal provider+model."""

    def __init__(self) -> None:
        self.registry = get_all_providers()
        self.classifier = UseCaseClassifier()

    def route(self, request: RoutingRequest) -> RoutingDecision:
        """Route a request to the optimal provider+model."""
        # Step 1: Determine use case
        if request.use_case and request.use_case in VALID_USE_CASES:
            use_case = request.use_case
            classification_confidence = 1.0
            classification_reasoning = f"Explicit use_case='{use_case}'"
        else:
            use_case, classification_confidence = self.classifier.classify(request.task_description)
            classification_reasoning = (
                f"Classified as '{use_case}' (confidence={classification_confidence:.0%})"
            )

        # Step 2: Context-token override
        context_override = False
        if request.context_tokens > LONG_CONTEXT_THRESHOLD:
            if use_case != "long_context":
                use_case = "long_context"
                context_override = True
                classification_reasoning += (
                    f" -> overridden to 'long_context' "
                    f"({request.context_tokens:,} tokens > {LONG_CONTEXT_THRESHOLD:,} threshold)"
                )

        # Step 3: Select routing table (batch vs. standard)
        if request.batch_eligible and use_case in _BATCH_ROUTES:
            route = _BATCH_ROUTES[use_case]
            batch_note = " [batch-eligible]"
        else:
            route = _ROUTES[use_case]
            batch_note = ""

        # Step 4: Verify context capacity
        primary_spec = get_model_spec(route.primary_provider, route.primary_model)
        if request.context_tokens > primary_spec.max_context:
            upgraded = self._find_context_capable_model(request.context_tokens)
            if upgraded:
                route = _Route(
                    upgraded[0], upgraded[1], route.fallback_provider, route.fallback_model
                )
                classification_reasoning += (
                    f" -> upgraded to {upgraded[0]}/{upgraded[1]} for context capacity"
                )

        # Step 5: Cost estimate (assume 1000 output tokens)
        estimated_cost = self._estimate_cost(
            route.primary_provider,
            route.primary_model,
            request.context_tokens,
            1000,
        )

        # Step 6: Build reasoning
        primary_spec = get_model_spec(route.primary_provider, route.primary_model)
        reasoning = (
            f"{classification_reasoning}{batch_note}. "
            f"Routed to {primary_spec.display_name} ({route.primary_provider}) "
            f"via {use_case} table entry."
        )

        # Step 7: Confidence
        confidence = classification_confidence
        if context_override:
            confidence = min(confidence, 0.8)

        return RoutingDecision(
            provider=route.primary_provider,
            model_id=route.primary_model,
            display_name=primary_spec.display_name,
            reasoning=reasoning,
            estimated_cost=estimated_cost,
            fallback_provider=route.fallback_provider,
            fallback_model_id=route.fallback_model,
            confidence=round(confidence, 2),
        )

    def _estimate_cost(
        self,
        provider: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int = 1000,
    ) -> float:
        """Calculate estimated cost in USD."""
        spec = get_model_spec(provider, model_id)
        input_cost = (input_tokens / 1_000_000) * spec.input_cost_per_mtok
        output_cost = (output_tokens / 1_000_000) * spec.output_cost_per_mtok
        return round(input_cost + output_cost, 6)

    def _find_context_capable_model(self, required_context: int) -> tuple[str, str] | None:
        """Find the cheapest model that can handle the required context."""
        candidates: list[tuple[float, str, str]] = []
        for provider_name, provider in self.registry.items():
            for model_id, spec in provider.models.items():
                if spec.max_context >= required_context:
                    candidates.append((spec.input_cost_per_mtok, provider_name, model_id))

        if not candidates:
            return None

        candidates.sort()
        _, provider_name, model_id = candidates[0]
        return (provider_name, model_id)

    def list_use_cases(self) -> list[str]:
        """Return all valid use cases."""
        return sorted(VALID_USE_CASES)

    def explain_route(self, use_case: str) -> str:
        """Explain the routing for a given use case."""
        if use_case not in _ROUTES:
            return f"Unknown use case: '{use_case}'"

        route = _ROUTES[use_case]
        primary = get_model_spec(route.primary_provider, route.primary_model)
        fallback = get_model_spec(route.fallback_provider, route.fallback_model)

        lines = [
            f"Use Case: {use_case}",
            f"  Primary:  {primary.display_name} ({route.primary_provider}/{route.primary_model})",
            f"            ${primary.input_cost_per_mtok}/MTok in, ${primary.output_cost_per_mtok}/MTok out",
            f"            Context: {primary.max_context:,} | Speed: {primary.speed_tier}",
            f"  Fallback: {fallback.display_name} ({route.fallback_provider}/{route.fallback_model})",
            f"            ${fallback.input_cost_per_mtok}/MTok in, ${fallback.output_cost_per_mtok}/MTok out",
            f"            Context: {fallback.max_context:,} | Speed: {fallback.speed_tier}",
        ]
        return "\n".join(lines)
