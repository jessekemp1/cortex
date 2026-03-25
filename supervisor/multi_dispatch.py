"""
Multi-provider dispatcher — routes to correct provider with fallback.

Wraps the existing AgentDispatcher (Anthropic-only) and adds LiteLLM routing
for open-source models. Falls back gracefully:
  1. Try selected provider/model
  2. On failure → next cheapest model in same tier
  3. All API providers fail → detect connectivity → enter offline mode
  4. No providers available → return failure with helpful message

LiteLLM is imported lazily — system works without it (Anthropic-only).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List

from cortex.supervisor.dispatch import AgentDispatcher, DispatchResult, ModelSelection
from cortex.supervisor.models import WorkItem
from cortex.supervisor.providers import ProviderRegistry

log = logging.getLogger(__name__)

# Lazy LiteLLM import
_litellm = None
_LITELLM_AVAILABLE = False


def _get_litellm():
    """Lazy-import litellm to avoid startup cost when not needed."""
    global _litellm, _LITELLM_AVAILABLE
    if _litellm is not None:
        return _litellm
    try:
        import litellm

        litellm.drop_params = True  # Silently drop unsupported params per provider
        _litellm = litellm
        _LITELLM_AVAILABLE = True
        return litellm
    except ImportError:
        _LITELLM_AVAILABLE = False
        return None


class MultiProviderDispatcher:
    """Routes dispatch to correct provider. Falls back on failure.

    When model_id starts with "claude-" → delegates to existing AgentDispatcher.
    Otherwise → uses LiteLLM for cross-provider dispatch.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        anthropic_dispatcher: AgentDispatcher,
    ) -> None:
        self._registry = registry
        self._anthropic = anthropic_dispatcher

    # ------------------------------------------------------------------
    # Delegation methods: expose same interface as AgentDispatcher
    # so MultiProviderDispatcher is a drop-in replacement in core.py
    # ------------------------------------------------------------------

    def dispatch(self, work_item: WorkItem, model_selection: ModelSelection) -> DispatchResult:
        """Sync dispatch — delegates to Anthropic dispatcher for now.

        The multi-provider path uses dispatch_async(). Sync callers
        (single-dispatch path in core.py) go through this method.
        """
        provider = self._resolve_provider(model_selection.model_id)
        if provider == "anthropic" or not _LITELLM_AVAILABLE:
            result = self._anthropic.dispatch(work_item, model_selection)
            result.provider = getattr(result, "provider", "anthropic")
            return result
        # Non-Anthropic: run async dispatch in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, self.dispatch_async(work_item, model_selection)
                    )
                    return future.result()
            return asyncio.run(self.dispatch_async(work_item, model_selection))
        except Exception as exc:
            log.warning("Async dispatch failed (%s), falling back to Anthropic", exc)
            return self._anthropic.dispatch(work_item, model_selection)

    def submit_batch(self, batch_pairs: list) -> str:
        """Delegate batch submission to Anthropic dispatcher."""
        return self._anthropic.submit_batch(batch_pairs)

    def retrieve_batch(self, batch_id: str, **kwargs) -> list:
        """Delegate batch retrieval to Anthropic dispatcher."""
        return self._anthropic.retrieve_batch(batch_id, **kwargs)

    def _resolve_provider(self, model_id: str) -> str:
        """Determine which provider owns a model ID."""
        # Claude models → Anthropic
        if model_id.startswith("claude-"):
            return "anthropic"
        # Check registry for explicit match
        for pname, pconfig in self._registry.get_all_providers().items():
            for spec in pconfig.models.values():
                if spec.model_id == model_id:
                    return pname
        # LiteLLM prefix convention: "provider/model"
        if "/" in model_id:
            return model_id.split("/")[0]
        return "unknown"

    async def dispatch_async(
        self,
        work_item: WorkItem,
        model_selection: ModelSelection,
    ) -> DispatchResult:
        """Dispatch with automatic provider selection and fallback.

        Tries:
        1. Selected model → via Anthropic SDK or LiteLLM
        2. On failure → next cheapest model in same tier
        3. Tier exhausted → escalate to next tier (haiku→sonnet→opus)
        4. All failed → return DispatchResult(success=False)
        """
        model_id = model_selection.model_id
        provider = self._resolve_provider(model_id)

        # Anthropic models → use existing dispatcher (preserves all existing behavior)
        if provider == "anthropic" and model_id.startswith("claude-"):
            result = await self._anthropic.dispatch_async(work_item, model_selection)
            if result.success:
                self._registry.mark_success("anthropic", model_id)
            else:
                self._registry.mark_failure("anthropic", model_id, result.error or "unknown")
            result.provider = "anthropic"
            result.cost_usd = self._registry.estimate_cost(
                "anthropic", model_id, result.tokens_used // 2, result.tokens_used // 2
            )
            return result

        # Non-Anthropic → LiteLLM dispatch with fallback chain
        return await self._dispatch_with_fallback(work_item, model_selection)

    async def _dispatch_with_fallback(
        self,
        work_item: WorkItem,
        model_selection: ModelSelection,
    ) -> DispatchResult:
        """Try selected model, then fallback through tier candidates."""
        tier = model_selection.model_tier
        model_id = model_selection.model_id
        errors: List[str] = []

        # Build candidate list: selected model first, then other models in tier by cost
        candidates = self._registry.get_models_for_tier(tier)
        ordered = []
        rest = []
        for pname, spec in candidates:
            if spec.model_id == model_id:
                ordered.insert(0, (pname, spec))
            else:
                rest.append((pname, spec))
        ordered.extend(rest)

        for pname, spec in ordered:
            # Check tool support requirement
            needs_tools = bool(work_item.command)
            if needs_tools and not spec.supports_tools:
                continue

            try:
                result = await self._dispatch_litellm(
                    provider=pname,
                    model_id=spec.model_id,
                    work_item=work_item,
                    max_tokens=spec.max_tokens,
                )
                self._registry.mark_success(pname, spec.model_id)
                return result
            except Exception as exc:
                error_msg = f"{pname}/{spec.model_id}: {exc}"
                errors.append(error_msg)
                log.warning("Dispatch failed: %s", error_msg)
                self._registry.mark_failure(pname, spec.model_id, str(exc))
                continue

        # All candidates in tier exhausted — try escalating tier
        tier_order = ["haiku", "sonnet", "opus"]
        current_idx = tier_order.index(tier) if tier in tier_order else 0
        for next_idx in range(current_idx + 1, len(tier_order)):
            next_tier = tier_order[next_idx]
            escalated_candidates = self._registry.get_models_for_tier(next_tier)
            for pname, spec in escalated_candidates:
                try:
                    result = await self._dispatch_litellm(
                        provider=pname,
                        model_id=spec.model_id,
                        work_item=work_item,
                        max_tokens=spec.max_tokens,
                    )
                    self._registry.mark_success(pname, spec.model_id)
                    log.info(
                        "Escalated %s → %s/%s after %d failures in %s tier",
                        work_item.id[:8],
                        pname,
                        spec.model_id,
                        len(errors),
                        tier,
                    )
                    return result
                except Exception as exc:
                    errors.append(f"{pname}/{spec.model_id}: {exc}")
                    self._registry.mark_failure(pname, spec.model_id, str(exc))

        # Check if we should enter offline mode
        if not self._registry.offline_mode and not self._registry.detect_connectivity():
            self._registry.enter_offline_mode()
            # Retry with local providers
            local_candidates = self._registry.get_models_for_tier(tier)
            if local_candidates:
                pname, spec = local_candidates[0]
                try:
                    return await self._dispatch_litellm(
                        provider=pname,
                        model_id=spec.model_id,
                        work_item=work_item,
                        max_tokens=spec.max_tokens,
                    )
                except Exception as exc:
                    errors.append(f"offline/{pname}: {exc}")

        # Total failure
        return DispatchResult(
            work_item_id=work_item.id,
            success=False,
            output="",
            model_used=model_selection.model_id,
            tokens_used=0,
            duration_seconds=0.0,
            task_type=work_item.task_type,
            error=f"All providers failed: {'; '.join(errors[:3])}",
            provider="none",
            cost_usd=0.0,
        )

    async def _dispatch_litellm(
        self,
        provider: str,
        model_id: str,
        work_item: WorkItem,
        max_tokens: int = 4096,
    ) -> DispatchResult:
        """Dispatch via LiteLLM (single-turn completion)."""
        litellm = _get_litellm()
        if litellm is None:
            raise RuntimeError("litellm not installed. Install with: pip install litellm")

        prompt = self._anthropic._build_prompt(work_item)
        system_prompt = self._anthropic._build_system_prompt(work_item)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        start = time.monotonic()

        response = await asyncio.to_thread(
            litellm.completion,
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
        )

        output = response.choices[0].message.content or ""
        usage = response.usage
        total_tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
        elapsed = time.monotonic() - start

        cost = self._registry.estimate_cost(
            provider, model_id, usage.prompt_tokens or 0, usage.completion_tokens or 0
        )

        return DispatchResult(
            work_item_id=work_item.id,
            success=True,
            output=output,
            model_used=model_id,
            tokens_used=total_tokens,
            duration_seconds=round(elapsed, 3),
            task_type=work_item.task_type,
            provider=provider,
            cost_usd=cost,
        )
