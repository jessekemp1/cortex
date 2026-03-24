#!/usr/bin/env python3
"""
Request Routing Framework

Classifies incoming requests to determine whether they should be handled
interactively or batched. This is the decision brain for the flywheel.

Decision Tree:
1. Is it time-sensitive (< 2 hours)? → INTERACTIVE
2. Does it require iteration/dialog? → INTERACTIVE
3. Is it a known batch template? → SUGGEST BATCH
4. Is it > 10K tokens estimated? → OFFER BATCH
5. Default → INTERACTIVE

Usage:
    from routing_framework import RequestRouter

    router = RequestRouter()
    decision = router.classify("Review this PR for security issues")

    if decision.route == "batch":
        print(f"This could be batched (saves {decision.savings_pct}%)")
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class RouteType(Enum):
    """Request routing decision"""

    INTERACTIVE = "interactive"  # Must be real-time
    SUGGEST_BATCH = "suggest_batch"  # Recommend batch, user chooses
    OFFER_BATCH = "offer_batch"  # Large request, offer batch option
    FORCE_BATCH = "force_batch"  # Over budget, must batch


@dataclass
class RouteDecision:
    """Result of routing decision"""

    route: RouteType
    reason: str
    confidence: float  # 0.0-1.0

    # Batch-specific
    template_id: Optional[str] = None
    estimated_tokens: int = 0
    estimated_hours: float = 0.0
    savings_pct: int = 50  # Batch API discount

    # Interactive-specific
    requires_iteration: bool = False
    time_sensitive: bool = False


# Request patterns that indicate batch eligibility
BATCH_PATTERNS = {
    "code_review": {
        "patterns": [
            r"review\s+(this|the)?\s*(code|pr|pull\s*request|diff|changes)",
            r"(code|pr|security)\s+review",
            r"check\s+(this|the)?\s*(code|implementation)\s+for",
        ],
        "template": "code_review",
        "estimated_tokens": 25_000,
        "confidence": 0.85,
    },
    "documentation": {
        "patterns": [
            r"(write|generate|create|update)\s+(the)?\s*(documentation|docs|readme)",
            r"document\s+(this|the)?\s*(api|module|function|class)",
            r"add\s+docstrings",
        ],
        "template": "documentation",
        "estimated_tokens": 15_000,
        "confidence": 0.90,
    },
    "security_audit": {
        "patterns": [
            r"(security|vulnerability)\s+(scan|audit|check|review)",
            r"check\s+for\s+(security|vulnerabilities|exploits)",
            r"(owasp|cve)\s+scan",
        ],
        "template": "security_audit",
        "estimated_tokens": 30_000,
        "confidence": 0.95,
    },
    "test_coverage": {
        "patterns": [
            r"(test|coverage)\s+(analysis|report|gaps)",
            r"(find|identify)\s+(missing|untested)\s+(tests|coverage)",
            r"what\s+(needs|should)\s+tests",
        ],
        "template": "test_coverage",
        "estimated_tokens": 20_000,
        "confidence": 0.85,
    },
    "research": {
        "patterns": [
            r"research\s+(about|on|into)\s+",
            r"(compare|evaluate|analyze)\s+(different|various)\s+",
            r"what\s+are\s+(the\s+)?(best|recommended)\s+",
            r"(explain|describe)\s+(how|what|why)\s+",
        ],
        "template": "research",
        "estimated_tokens": 20_000,
        "confidence": 0.75,
    },
    "refactoring": {
        "patterns": [
            r"(refactor|restructure|reorganize)\s+(this|the)?",
            r"(suggest|recommend)\s+refactoring",
            r"how\s+(can|should|to)\s+refactor",
        ],
        "template": "refactoring",
        "estimated_tokens": 25_000,
        "confidence": 0.80,
    },
    "performance": {
        "patterns": [
            r"(performance|optimization)\s+(analysis|review|audit)",
            r"(find|identify)\s+(bottlenecks|slow|performance)",
            r"(analyze|check)\s+performance",
        ],
        "template": "performance",
        "estimated_tokens": 25_000,
        "confidence": 0.85,
    },
    "dependency_audit": {
        "patterns": [
            r"(dependency|package|library)\s+(audit|check|update)",
            r"(outdated|vulnerable)\s+(dependencies|packages)",
            r"check\s+(for\s+)?(dependency|package)\s+(issues|updates)",
        ],
        "template": "dependency_audit",
        "estimated_tokens": 15_000,
        "confidence": 0.90,
    },
}

# Patterns that indicate interactive-only requests
INTERACTIVE_PATTERNS = {
    "debugging": {
        "patterns": [
            r"(debug|fix)\s+(this|the)?\s*(bug|error|issue)",
            r"why\s+(is|does|doesn't)\s+",
            r"(help|stuck)\s+(with|on)\s+",
            r"(getting|seeing)\s+(an?\s+)?(error|exception)",
        ],
        "reason": "Active debugging requires real-time iteration",
    },
    "implementation": {
        "patterns": [
            r"(implement|write|create|build)\s+(a|the|this)?",
            r"(add|make)\s+(a|the)?\s*(feature|function|method)",
            r"can\s+you\s+(implement|write|create)",
        ],
        "reason": "Implementation requires file editing and context",
    },
    "urgent": {
        "patterns": [
            r"(urgent|asap|immediately|now|quick)",
            r"(need|want)\s+(this|it)\s+(now|fast|quickly)",
            r"(production|live|critical)\s+(issue|bug|problem)",
        ],
        "reason": "Time-sensitive request",
    },
    "interactive": {
        "patterns": [
            r"(show|tell)\s+me",
            r"what\s+(do|should)\s+(you|i)\s+think",
            r"(let's|shall\s+we)\s+",
            r"(can|could)\s+you\s+(help|explain)",
        ],
        "reason": "Request implies dialog/iteration",
    },
}


class RequestRouter:
    """
    Routes requests to batch or interactive processing.

    The router analyzes request text to determine the optimal
    processing path, balancing cost savings with user experience.
    """

    def __init__(self):
        self.batch_patterns = self._compile_patterns(BATCH_PATTERNS)
        self.interactive_patterns = self._compile_patterns(INTERACTIVE_PATTERNS)

    def _compile_patterns(self, pattern_dict: Dict) -> Dict:
        """Pre-compile regex patterns for performance"""
        compiled = {}
        for key, config in pattern_dict.items():
            compiled[key] = {
                **config,
                "compiled": [re.compile(p, re.IGNORECASE) for p in config["patterns"]],
            }
        return compiled

    def classify(
        self, request: str, force_time_sensitive: bool = False, budget_remaining_pct: float = 100.0
    ) -> RouteDecision:
        """
        Classify a request for routing.

        Args:
            request: The user's request text
            force_time_sensitive: Override to mark as time-sensitive
            budget_remaining_pct: Remaining daily budget percentage

        Returns:
            RouteDecision with routing recommendation
        """
        request_lower = request.lower()

        # Check if over budget - must batch
        if budget_remaining_pct <= 0:
            return RouteDecision(
                route=RouteType.FORCE_BATCH,
                reason="Daily interactive budget exhausted",
                confidence=1.0,
                estimated_tokens=self._estimate_tokens(request),
            )

        # Check for time-sensitive indicators
        if force_time_sensitive or self._is_time_sensitive(request_lower):
            return RouteDecision(
                route=RouteType.INTERACTIVE,
                reason="Time-sensitive request",
                confidence=0.95,
                time_sensitive=True,
            )

        # Check for interactive-only patterns
        interactive_match = self._match_patterns(request_lower, self.interactive_patterns)
        if interactive_match:
            return RouteDecision(
                route=RouteType.INTERACTIVE,
                reason=interactive_match["reason"],
                confidence=interactive_match.get("confidence", 0.85),
                requires_iteration=True,
            )

        # Check for batch-eligible patterns
        batch_match = self._match_patterns(request_lower, self.batch_patterns)
        if batch_match:
            return RouteDecision(
                route=RouteType.SUGGEST_BATCH,
                reason=f"Matches batch template: {batch_match.get('template', 'unknown')}",
                confidence=batch_match.get("confidence", 0.80),
                template_id=batch_match.get("template"),
                estimated_tokens=batch_match.get("estimated_tokens", 20_000),
                estimated_hours=batch_match.get("estimated_tokens", 20_000) / 50_000 * 0.5,
            )

        # Apply learned utilization policies — may suggest batch for requests
        # that aren't pattern-matched but where subscription is underutilized
        learned_decision = self._apply_learned_utilization(request_lower)
        if learned_decision:
            return learned_decision

        # Check token estimate for large requests
        estimated_tokens = self._estimate_tokens(request)
        if estimated_tokens > 10_000:
            return RouteDecision(
                route=RouteType.OFFER_BATCH,
                reason=f"Large request (~{estimated_tokens:,} tokens estimated)",
                confidence=0.70,
                estimated_tokens=estimated_tokens,
                estimated_hours=estimated_tokens / 50_000 * 0.5,
            )

        # Default: interactive
        return RouteDecision(
            route=RouteType.INTERACTIVE,
            reason="Standard request - interactive processing",
            confidence=0.60,
        )

    def _apply_learned_utilization(self, request_lower: str) -> Optional[RouteDecision]:
        """
        Check learned utilization policies for routing adjustments.

        Queries the UtilizationLearningEngine and SubscriptionOptimizer
        for policies that should influence this routing decision.
        Falls back gracefully if neither is configured.
        """
        try:
            from batch.utilization_learning import UtilizationLearningEngine

            engine = UtilizationLearningEngine()

            # Check if learned policies suggest batching for this request type
            for pattern_key, config in self.batch_patterns.items():
                for compiled_pattern in config["compiled"]:
                    if compiled_pattern.search(request_lower):
                        adjustment = engine.get_routing_adjustment(pattern_key)
                        if adjustment and adjustment.get("preferred_route") == "suggest_batch":
                            return RouteDecision(
                                route=RouteType.SUGGEST_BATCH,
                                reason=f"[LEARNED] {adjustment['reasoning']}",
                                confidence=min(0.90, adjustment.get("confidence", 0.7)),
                                template_id=config.get("template"),
                                estimated_tokens=config.get("estimated_tokens", 20_000),
                            )

            # Check if subscription underutilization should lower batch threshold
            adjustment = engine.get_routing_adjustment("__batch_aggressiveness__")
            if adjustment:
                threshold = adjustment.get("lower_token_threshold", 10_000)
                estimated_tokens = self._estimate_tokens(request_lower)
                if estimated_tokens > threshold:
                    return RouteDecision(
                        route=RouteType.OFFER_BATCH,
                        reason=f"[LEARNED] {adjustment['reasoning']}",
                        confidence=0.65,
                        estimated_tokens=estimated_tokens,
                    )

        except (ImportError, Exception):
            pass  # Learning engine is optional

        return None

    def _match_patterns(self, text: str, pattern_dict: Dict) -> Optional[Dict]:
        """Match text against pattern dictionary"""
        for key, config in pattern_dict.items():
            for pattern in config["compiled"]:
                if pattern.search(text):
                    return {
                        "key": key,
                        **{k: v for k, v in config.items() if k != "compiled" and k != "patterns"},
                    }
        return None

    def _is_time_sensitive(self, text: str) -> bool:
        """Check if request indicates time sensitivity"""
        time_indicators = [
            r"(urgent|asap|immediately|right\s+now)",
            r"(production|live|critical)\s+(issue|bug|problem)",
            r"(need|want)\s+(this|it)\s+(now|fast|quickly)",
            r"(before|by)\s+(the\s+)?(meeting|demo|deadline)",
        ]

        for pattern in time_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for request.

        Uses rough heuristics based on:
        - Request length
        - Complexity indicators
        - File references
        """
        # Base: ~4 chars per token for English
        base_tokens = len(text) // 4

        # Complexity multipliers
        multiplier = 1.0

        # File references suggest more context needed
        file_refs = len(re.findall(r"\b\w+\.(py|js|ts|go|rs|java|cpp|c|h)\b", text))
        multiplier += file_refs * 0.5

        # "All" or "every" suggests comprehensive analysis
        if re.search(r"\b(all|every|entire|whole)\b", text, re.IGNORECASE):
            multiplier += 1.0

        # Multiple items suggest more work
        list_items = len(re.findall(r"^\s*[-•*]\s+", text, re.MULTILINE))
        multiplier += list_items * 0.2

        return int(base_tokens * multiplier * 100)  # Scale up for actual LLM context

    def format_suggestion(self, decision: RouteDecision) -> str:
        """Format routing decision as user-friendly message"""
        if decision.route == RouteType.INTERACTIVE:
            return None  # No message needed for interactive

        if decision.route == RouteType.FORCE_BATCH:
            return (
                "⚠️ **Daily budget exhausted** - This request will be queued for batch processing.\n"
                f"Estimated completion: {decision.estimated_hours:.1f} hours\n"
                "Results will appear in tomorrow's /briefing."
            )

        if decision.route == RouteType.SUGGEST_BATCH:
            return (
                f"💡 **Batch suggestion** ({decision.savings_pct}% savings)\n"
                f"This looks like a `{decision.template_id}` task.\n"
                f"• Interactive: ~{decision.estimated_tokens:,} tokens now\n"
                f"• Batch: ~{decision.estimated_tokens // 2:,} tokens overnight\n\n"
                "Would you like to batch this? [Y/n]"
            )

        if decision.route == RouteType.OFFER_BATCH:
            return (
                f"💡 **Large request detected** (~{decision.estimated_tokens:,} tokens)\n"
                f"Batching would save {decision.savings_pct}% and free your session.\n\n"
                "Would you like to batch this? [Y/n]"
            )

        return None


def format_routing_prompt(request: str) -> Optional[str]:
    """
    Convenience function for session hook integration.

    Returns formatted suggestion if request should be batched,
    None otherwise.
    """
    router = RequestRouter()
    decision = router.classify(request)
    return router.format_suggestion(decision)


if __name__ == "__main__":
    # Demo: Classify sample requests
    router = RequestRouter()

    test_requests = [
        "Review this PR for security issues",
        "Fix the bug in the login page",
        "Generate documentation for the API module",
        "urgent - production is down!",
        "What are the best practices for caching?",
        "Implement a new user authentication system",
        "Analyze performance bottlenecks in the database queries",
    ]

    print("Request Routing Demo")
    print("=" * 60)

    for request in test_requests:
        decision = router.classify(request)
        print(f"\nRequest: {request}")
        print(f"  Route: {decision.route.value}")
        print(f"  Reason: {decision.reason}")
        print(f"  Confidence: {decision.confidence:.0%}")

        suggestion = router.format_suggestion(decision)
        if suggestion:
            print(f"\n  Suggestion:\n{suggestion}")
