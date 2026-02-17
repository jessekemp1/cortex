#!/usr/bin/env python3
"""
Tests for the Conductor router and registry.

Covers:
- Routing table completeness (all use cases mapped)
- Use case classification via keywords
- Context-token-based routing (>200K -> long_context)
- Batch routing
- Cost estimation accuracy
- Fallback provider validation
- Provider/model config integrity
"""

import pytest

from cortex.conductor.models import RoutingDecision, RoutingRequest
from cortex.conductor.registry import (
    get_all_providers,
    get_model_spec,
    get_provider,
    list_all_models,
    list_providers,
)
from cortex.conductor.router import (
    BATCH_ROUTING_TABLE,
    LONG_CONTEXT_THRESHOLD,
    ROUTING_TABLE,
    VALID_USE_CASES,
    ConductorRouter,
    UseCaseClassifier,
)


# ── Registry Tests ────────────────────────────────────────────────────


class TestRegistry:
    """Tests for the provider registry."""

    def test_all_providers_exist(self):
        """All expected providers are registered."""
        expected = {"groq", "xai", "minimax", "anthropic", "openai", "deepseek"}
        actual = set(get_all_providers().keys())
        assert actual == expected

    def test_list_providers_sorted(self):
        """list_providers returns sorted names."""
        providers = list_providers()
        assert providers == sorted(providers)
        assert len(providers) == 6

    def test_get_provider_valid(self):
        """get_provider returns config for known providers."""
        for name in ["groq", "xai", "minimax", "anthropic", "openai", "deepseek"]:
            provider = get_provider(name)
            assert provider.name == name
            assert provider.api_key_env  # Non-empty
            assert provider.base_url.startswith("https://")
            assert len(provider.models) >= 1

    def test_get_provider_unknown_raises(self):
        """get_provider raises KeyError for unknown provider."""
        with pytest.raises(KeyError, match="Unknown provider 'nonexistent'"):
            get_provider("nonexistent")

    def test_get_model_spec_valid(self):
        """get_model_spec returns spec for known provider+model."""
        spec = get_model_spec("anthropic", "claude-opus-4-6")
        assert spec.display_name == "Opus 4.6"
        assert spec.input_cost_per_mtok == 15.0
        assert spec.output_cost_per_mtok == 75.0

    def test_get_model_spec_unknown_model_raises(self):
        """get_model_spec raises KeyError for unknown model."""
        with pytest.raises(KeyError, match="Unknown model 'fake-model'"):
            get_model_spec("anthropic", "fake-model")

    def test_all_providers_have_valid_configs(self):
        """Every provider has required fields populated correctly."""
        for name, provider in get_all_providers().items():
            assert provider.name == name
            assert provider.api_key_env.endswith("_API_KEY"), (
                f"{name}: api_key_env should end with '_API_KEY', got '{provider.api_key_env}'"
            )
            assert provider.base_url.startswith("https://"), (
                f"{name}: base_url must start with https://"
            )
            assert provider.max_context > 0
            assert isinstance(provider.supports_batch, bool)

    def test_all_models_have_valid_specs(self):
        """Every model in every provider has valid pricing and limits."""
        for name, provider in get_all_providers().items():
            for model_id, spec in provider.models.items():
                assert spec.model_id == model_id, f"{name}/{model_id}: model_id mismatch"
                assert spec.display_name, f"{name}/{model_id}: missing display_name"
                assert spec.input_cost_per_mtok >= 0, f"{name}/{model_id}: negative input cost"
                assert spec.output_cost_per_mtok >= 0, f"{name}/{model_id}: negative output cost"
                assert spec.max_context > 0, f"{name}/{model_id}: zero max_context"
                assert spec.max_output > 0, f"{name}/{model_id}: zero max_output"
                assert spec.speed_tier in ("fast", "medium", "slow"), (
                    f"{name}/{model_id}: invalid speed_tier '{spec.speed_tier}'"
                )
                assert isinstance(spec.strengths, list), (
                    f"{name}/{model_id}: strengths must be a list"
                )

    def test_model_context_within_provider_max(self):
        """No model's context exceeds its provider's max_context."""
        for name, provider in get_all_providers().items():
            for model_id, spec in provider.models.items():
                assert spec.max_context <= provider.max_context, (
                    f"{name}/{model_id}: model max_context ({spec.max_context}) "
                    f"exceeds provider max_context ({provider.max_context})"
                )

    def test_list_all_models(self):
        """list_all_models returns tuples of (provider, model_id, display_name)."""
        models = list_all_models()
        assert len(models) >= 10  # We have 11 models across all providers
        for provider, model_id, display_name in models:
            assert provider in get_all_providers()
            assert display_name  # Non-empty

    def test_provider_to_dict(self):
        """ProviderConfig.to_dict serializes without errors."""
        provider = get_provider("groq")
        d = provider.to_dict()
        assert d["name"] == "groq"
        assert "models" in d
        assert isinstance(d["models"], dict)


# ── Classification Tests ──────────────────────────────────────────────


class TestUseCaseClassifier:
    """Tests for the keyword-based use case classifier."""

    @pytest.fixture
    def classifier(self):
        return UseCaseClassifier()

    @pytest.mark.parametrize(
        "description, expected_use_case",
        [
            ("Design the system architecture for the new microservice", "architecture"),
            ("Implement a new feature for the user profile page", "interactive_coding"),
            ("Classify these customer support tickets by category", "classification"),
            ("Read the entire codebase and all files in the full repository", "long_context"),
            ("Research the pros and cons of Redis vs Memcached", "research"),
            ("What is a Python decorator?", "quick_qa"),
            ("Review this pull request for code quality", "code_review"),
            ("Write unit tests for the auth module", "test_generation"),
            ("Write documentation for the API endpoints", "documentation"),
            ("Security audit for SQL injection vulnerabilities", "security_audit"),
            ("Extract patterns from these log entries", "pattern_learning"),
        ],
    )
    def test_classification_keywords(self, classifier, description, expected_use_case):
        """Classifier maps known keyword-rich descriptions to correct use case."""
        use_case, confidence = classifier.classify(description)
        assert use_case == expected_use_case, (
            f"Expected '{expected_use_case}' for '{description}', got '{use_case}'"
        )
        assert 0.0 < confidence <= 1.0

    def test_classification_no_keywords_defaults_to_quick_qa(self, classifier):
        """Descriptions with no matching keywords default to quick_qa."""
        use_case, confidence = classifier.classify("asdfghjkl zxcvbnm")
        assert use_case == "quick_qa"
        assert confidence == 0.3

    def test_classification_confidence_increases_with_more_keywords(self, classifier):
        """More keyword hits in one category yield higher confidence."""
        # Ambiguous: "pattern" (pattern_learning) + "analyze" (research) split across categories
        _, conf_low = classifier.classify("analyze this pattern")
        # Dominant: 4+ keywords in one category (research), no other category matches
        _, conf_high = classifier.classify(
            "research and investigate, compare options, evaluate the benchmark"
        )
        assert conf_high > conf_low

    def test_classification_returns_valid_use_case(self, classifier):
        """Classifier always returns a use case from the valid set."""
        descriptions = [
            "Build a REST API",
            "Fix the database connection",
            "Deploy to production",
            "",
            "a",
            "the quick brown fox",
        ]
        for desc in descriptions:
            use_case, confidence = classifier.classify(desc)
            assert use_case in VALID_USE_CASES, (
                f"Classifier returned invalid use_case '{use_case}' for '{desc}'"
            )
            assert 0.0 <= confidence <= 1.0


# ── Router Tests ──────────────────────────────────────────────────────


class TestConductorRouter:
    """Tests for the ConductorRouter."""

    @pytest.fixture
    def router(self):
        return ConductorRouter()

    def test_routing_table_covers_all_use_cases(self):
        """Every valid use case has a routing table entry."""
        for use_case in VALID_USE_CASES:
            assert use_case in ROUTING_TABLE, f"Use case '{use_case}' missing from ROUTING_TABLE"

    def test_routing_table_providers_exist_in_registry(self):
        """All providers referenced in routing table exist in registry."""
        providers = get_all_providers()
        for use_case, (primary_prov, _, fb_prov, _) in ROUTING_TABLE.items():
            assert primary_prov in providers, (
                f"{use_case}: primary provider '{primary_prov}' not in registry"
            )
            assert fb_prov in providers, (
                f"{use_case}: fallback provider '{fb_prov}' not in registry"
            )

    def test_routing_table_models_exist_in_registry(self):
        """All models referenced in routing table exist in their provider."""
        for use_case, (p_prov, p_model, fb_prov, fb_model) in ROUTING_TABLE.items():
            # Primary
            spec = get_model_spec(p_prov, p_model)
            assert spec is not None, (
                f"{use_case}: primary model '{p_model}' not found in '{p_prov}'"
            )
            # Fallback
            spec = get_model_spec(fb_prov, fb_model)
            assert spec is not None, (
                f"{use_case}: fallback model '{fb_model}' not found in '{fb_prov}'"
            )

    def test_fallback_providers_exist(self):
        """Fallback providers and models are valid for all routes."""
        for use_case, (_, _, fb_prov, fb_model) in ROUTING_TABLE.items():
            provider = get_provider(fb_prov)
            assert fb_model in provider.models, (
                f"{use_case}: fallback model '{fb_model}' not in fallback provider '{fb_prov}'"
            )

    def test_explicit_use_case_routing(self, router):
        """Explicit use_case in request routes to the correct entry."""
        for use_case in VALID_USE_CASES:
            request = RoutingRequest(
                task_description="test task",
                use_case=use_case,
            )
            decision = router.route(request)
            p_prov, p_model, fb_prov, fb_model = ROUTING_TABLE[use_case]

            assert decision.provider == p_prov
            assert decision.model_id == p_model
            assert decision.fallback_provider == fb_prov
            assert decision.fallback_model_id == fb_model
            assert decision.confidence == 1.0

    def test_classified_routing(self, router):
        """Without explicit use_case, classifier determines routing."""
        request = RoutingRequest(
            task_description="Review this pull request for code quality issues",
        )
        decision = router.route(request)
        # Should classify as code_review
        assert decision.provider == "minimax"
        assert decision.model_id == "MiniMax-M1"

    def test_context_token_override_forces_long_context(self, router):
        """Requests with >200K tokens get routed to long_context provider."""
        request = RoutingRequest(
            task_description="Classify these tickets",
            use_case="classification",
            context_tokens=300_000,
        )
        decision = router.route(request)

        # Should override classification -> long_context
        assert decision.provider == "xai"
        assert decision.model_id == "grok-3-fast"
        assert "overridden to 'long_context'" in decision.reasoning
        assert decision.confidence <= 0.8  # Penalty for override

    def test_context_tokens_below_threshold_no_override(self, router):
        """Requests under 200K tokens keep their original routing."""
        request = RoutingRequest(
            task_description="Classify these tickets",
            use_case="classification",
            context_tokens=100_000,
        )
        decision = router.route(request)
        assert decision.provider == "groq"
        assert decision.model_id == "llama-3.1-8b-instant"

    def test_batch_eligible_routing(self, router):
        """Batch-eligible requests use batch routing table when available."""
        request = RoutingRequest(
            task_description="Security audit for vulnerabilities",
            use_case="security_audit",
            batch_eligible=True,
        )
        decision = router.route(request)
        assert "[batch-eligible]" in decision.reasoning

    def test_batch_routing_falls_back_to_standard(self, router):
        """Batch-eligible but non-batch use case uses standard table."""
        request = RoutingRequest(
            task_description="What is Python?",
            use_case="quick_qa",
            batch_eligible=True,
        )
        decision = router.route(request)
        # quick_qa is not in BATCH_ROUTING_TABLE
        assert (
            "batch" not in decision.reasoning.lower() or "batch-eligible" not in decision.reasoning
        )

    def test_routing_decision_has_all_fields(self, router):
        """RoutingDecision has all required fields populated."""
        request = RoutingRequest(
            task_description="Design the API architecture",
            use_case="architecture",
            context_tokens=5000,
        )
        decision = router.route(request)

        assert isinstance(decision, RoutingDecision)
        assert decision.provider  # Non-empty
        assert decision.model_id  # Non-empty
        assert decision.display_name  # Non-empty
        assert decision.reasoning  # Non-empty
        assert decision.estimated_cost >= 0.0
        assert decision.fallback_provider  # Non-empty
        assert decision.fallback_model_id  # Non-empty
        assert 0.0 <= decision.confidence <= 1.0

    def test_routing_decision_to_dict(self, router):
        """RoutingDecision serializes to dict."""
        request = RoutingRequest(
            task_description="test",
            use_case="quick_qa",
        )
        decision = router.route(request)
        d = decision.to_dict()
        assert isinstance(d, dict)
        assert d["provider"] == decision.provider
        assert d["model_id"] == decision.model_id
        assert "estimated_cost" in d


# ── Cost Estimation Tests ─────────────────────────────────────────────


class TestCostEstimation:
    """Tests for cost estimation accuracy."""

    @pytest.fixture
    def router(self):
        return ConductorRouter()

    def test_zero_tokens_zero_cost(self, router):
        """Zero input tokens should yield minimal cost (output tokens only)."""
        cost = router._estimate_cost("groq", "llama-3.1-8b-instant", 0, 0)
        assert cost == 0.0

    def test_cost_scales_with_tokens(self, router):
        """Cost increases proportionally with token count."""
        cost_small = router._estimate_cost("anthropic", "claude-opus-4-6", 1_000, 100)
        cost_large = router._estimate_cost("anthropic", "claude-opus-4-6", 1_000_000, 100)
        assert cost_large > cost_small

    def test_cost_calculation_accuracy(self, router):
        """Verify exact cost calculation for known values."""
        # Opus 4.6: $15/MTok input, $75/MTok output
        # 1M input + 1M output = $15 + $75 = $90
        cost = router._estimate_cost("anthropic", "claude-opus-4-6", 1_000_000, 1_000_000)
        assert cost == 90.0

    def test_cost_groq_is_cheapest(self, router):
        """Groq models should be significantly cheaper than Anthropic."""
        cost_groq = router._estimate_cost("groq", "llama-3.1-8b-instant", 100_000, 1_000)
        cost_opus = router._estimate_cost("anthropic", "claude-opus-4-6", 100_000, 1_000)
        assert cost_groq < cost_opus
        assert cost_opus > 10 * cost_groq  # At least 10x more expensive

    def test_cost_included_in_routing_decision(self, router):
        """Routing decision includes a non-negative cost estimate."""
        request = RoutingRequest(
            task_description="Classify this text",
            use_case="classification",
            context_tokens=10_000,
        )
        decision = router.route(request)
        assert decision.estimated_cost >= 0.0
        assert isinstance(decision.estimated_cost, float)


# ── Specific Route Tests ──────────────────────────────────────────────


class TestSpecificRoutes:
    """Test the specific routing table entries match the spec."""

    @pytest.fixture
    def router(self):
        return ConductorRouter()

    def test_architecture_routes_to_opus(self, router):
        """Architecture use case routes to Opus 4.6."""
        request = RoutingRequest(task_description="test", use_case="architecture")
        decision = router.route(request)
        assert decision.provider == "anthropic"
        assert decision.model_id == "claude-opus-4-6"
        assert decision.fallback_provider == "openai"
        assert decision.fallback_model_id == "gpt-5"

    def test_interactive_coding_routes_to_sonnet(self, router):
        """Interactive coding routes to Sonnet 4.5."""
        request = RoutingRequest(task_description="test", use_case="interactive_coding")
        decision = router.route(request)
        assert decision.provider == "anthropic"
        assert decision.model_id == "claude-sonnet-4-5-20250929"
        assert decision.fallback_provider == "xai"
        assert decision.fallback_model_id == "grok-code-fast-1"

    def test_classification_routes_to_groq(self, router):
        """Classification routes to Groq Llama 8B."""
        request = RoutingRequest(task_description="test", use_case="classification")
        decision = router.route(request)
        assert decision.provider == "groq"
        assert decision.model_id == "llama-3.1-8b-instant"
        assert decision.fallback_provider == "openai"
        assert decision.fallback_model_id == "gpt-5-nano"

    def test_long_context_routes_to_xai(self, router):
        """Long context routes to Grok 4.1 Fast."""
        request = RoutingRequest(task_description="test", use_case="long_context")
        decision = router.route(request)
        assert decision.provider == "xai"
        assert decision.model_id == "grok-3-fast"
        assert decision.fallback_provider == "minimax"
        assert decision.fallback_model_id == "MiniMax-M1"

    def test_research_routes_to_xai(self, router):
        """Research routes to Grok 4.1 Fast."""
        request = RoutingRequest(task_description="test", use_case="research")
        decision = router.route(request)
        assert decision.provider == "xai"
        assert decision.model_id == "grok-3-fast"
        assert decision.fallback_provider == "deepseek"
        assert decision.fallback_model_id == "deepseek-chat"

    def test_quick_qa_routes_to_groq(self, router):
        """Quick Q&A routes to Groq GPT-OSS 20B."""
        request = RoutingRequest(task_description="test", use_case="quick_qa")
        decision = router.route(request)
        assert decision.provider == "groq"
        assert decision.model_id == "openai/gpt-oss-20b"
        assert decision.fallback_provider == "anthropic"
        assert decision.fallback_model_id == "claude-haiku-4-5-20251001"

    def test_code_review_routes_to_minimax(self, router):
        """Code review routes to MiniMax M2.5."""
        request = RoutingRequest(task_description="test", use_case="code_review")
        decision = router.route(request)
        assert decision.provider == "minimax"
        assert decision.model_id == "MiniMax-M1"
        assert decision.fallback_provider == "anthropic"
        assert decision.fallback_model_id == "claude-sonnet-4-5-20250929"

    def test_test_generation_routes_to_minimax(self, router):
        """Test generation routes to MiniMax M2.5."""
        request = RoutingRequest(task_description="test", use_case="test_generation")
        decision = router.route(request)
        assert decision.provider == "minimax"
        assert decision.model_id == "MiniMax-M1"

    def test_documentation_routes_to_deepseek(self, router):
        """Documentation routes to DeepSeek V3.2."""
        request = RoutingRequest(task_description="test", use_case="documentation")
        decision = router.route(request)
        assert decision.provider == "deepseek"
        assert decision.model_id == "deepseek-chat"

    def test_security_audit_routes_to_opus(self, router):
        """Security audit routes to Opus Batch."""
        request = RoutingRequest(task_description="test", use_case="security_audit")
        decision = router.route(request)
        assert decision.provider == "anthropic"
        assert decision.model_id == "claude-opus-4-6"
        assert decision.fallback_provider == "openai"
        assert decision.fallback_model_id == "gpt-5"

    def test_pattern_learning_routes_to_deepseek(self, router):
        """Pattern learning routes to DeepSeek V3.2."""
        request = RoutingRequest(task_description="test", use_case="pattern_learning")
        decision = router.route(request)
        assert decision.provider == "deepseek"
        assert decision.model_id == "deepseek-chat"


# ── Edge Cases ────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.fixture
    def router(self):
        return ConductorRouter()

    def test_empty_task_description(self, router):
        """Empty description still routes (defaults to quick_qa)."""
        request = RoutingRequest(task_description="")
        decision = router.route(request)
        assert isinstance(decision, RoutingDecision)
        assert decision.provider  # Non-empty

    def test_invalid_use_case_falls_back_to_classifier(self, router):
        """Unknown use_case triggers classifier instead of crashing."""
        request = RoutingRequest(
            task_description="What is Python?",
            use_case="nonexistent_use_case",
        )
        decision = router.route(request)
        assert isinstance(decision, RoutingDecision)
        # Classifier should route this to quick_qa
        assert decision.provider in get_all_providers()

    def test_very_large_context_tokens(self, router):
        """Extremely large context tokens handled gracefully."""
        request = RoutingRequest(
            task_description="Read entire codebase",
            use_case="research",
            context_tokens=1_500_000,
        )
        decision = router.route(request)
        # Should be routed to a model that can handle 1.5M tokens
        spec = get_model_spec(decision.provider, decision.model_id)
        assert spec.max_context >= 1_500_000

    def test_context_at_exact_threshold(self, router):
        """Context exactly at 200K threshold should NOT trigger long_context override."""
        # Use architecture (Anthropic, 200K context) so the model can handle it
        request = RoutingRequest(
            task_description="Design the system",
            use_case="architecture",
            context_tokens=LONG_CONTEXT_THRESHOLD,
        )
        decision = router.route(request)
        # Exactly at threshold, not over -- should stay on architecture route
        assert decision.provider == "anthropic"
        assert decision.model_id == "claude-opus-4-6"
        assert "overridden" not in decision.reasoning

    def test_context_just_above_threshold(self, router):
        """Context at 200,001 tokens should trigger long_context override."""
        request = RoutingRequest(
            task_description="Classify this",
            use_case="classification",
            context_tokens=LONG_CONTEXT_THRESHOLD + 1,
        )
        decision = router.route(request)
        assert "overridden to 'long_context'" in decision.reasoning

    def test_list_use_cases(self, router):
        """list_use_cases returns all valid use cases sorted."""
        use_cases = router.list_use_cases()
        assert use_cases == sorted(use_cases)
        assert set(use_cases) == VALID_USE_CASES

    def test_explain_route_valid(self, router):
        """explain_route returns readable output for valid use case."""
        explanation = router.explain_route("architecture")
        assert "architecture" in explanation.lower()
        assert "Opus 4.6" in explanation
        assert "GPT-5" in explanation

    def test_explain_route_invalid(self, router):
        """explain_route handles unknown use case gracefully."""
        explanation = router.explain_route("nonexistent")
        assert "Unknown" in explanation

    def test_routing_request_to_dict(self):
        """RoutingRequest serializes to dict."""
        request = RoutingRequest(
            task_description="test task",
            use_case="research",
            context_tokens=5000,
            batch_eligible=True,
            priority="high",
            project="vortex",
        )
        d = request.to_dict()
        assert d["task_description"] == "test task"
        assert d["use_case"] == "research"
        assert d["context_tokens"] == 5000
        assert d["batch_eligible"] is True
        assert d["priority"] == "high"
        assert d["project"] == "vortex"
