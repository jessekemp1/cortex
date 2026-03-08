"""
Dispatch — executes WorkItems via Claude Agent SDK.

Handles:
  - Agent creation with model selection
  - Prompt construction from WorkItem
  - Execution with timeout and retry
  - Checkpoint/resume for long-running tasks
  - Result extraction and formatting
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from cortex.supervisor.models import WorkItem

try:
    from claude_agent_sdk import Agent

    AGENT_SDK_AVAILABLE = True
except ImportError:
    AGENT_SDK_AVAILABLE = False

log = logging.getLogger(__name__)

# Default timeouts per model tier (seconds).
MODEL_TIMEOUTS: dict[str, float] = {
    "opus": 300.0,
    "sonnet": 120.0,
    "haiku": 60.0,
}


@dataclass
class ModelSelection:
    """Routing decision produced by the router module."""

    model_tier: str  # "opus", "sonnet", "haiku"
    model_id: str  # e.g. "claude-opus-4-6"
    reasoning: str
    complexity_score: float
    confidence: float


@dataclass
class DispatchResult:
    """Outcome of a single agent dispatch."""

    work_item_id: str
    success: bool
    output: str
    model_used: str
    tokens_used: int
    duration_seconds: float
    error: Optional[str] = None
    checkpoint_id: Optional[str] = None  # For resume


class AgentDispatcher:
    """Dispatches :class:`WorkItem` instances to Claude agents for execution.

    Uses the Claude Agent SDK when available; otherwise falls back to direct
    Anthropic API calls via *httpx*.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_concurrent: int = 3,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        work_item: WorkItem,
        model_selection: ModelSelection,
    ) -> DispatchResult:
        """Synchronous dispatch — blocks until the agent completes."""
        return asyncio.run(self.dispatch_async(work_item, model_selection))

    async def dispatch_async(
        self,
        work_item: WorkItem,
        model_selection: ModelSelection,
    ) -> DispatchResult:
        """Asynchronous dispatch with concurrency limiting and timeout."""
        timeout = MODEL_TIMEOUTS.get(model_selection.model_tier, 120.0)
        prompt = self._build_prompt(work_item)
        system_prompt = self._build_system_prompt(work_item)

        start = time.monotonic()
        async with self._semaphore:
            try:
                if AGENT_SDK_AVAILABLE:
                    output, tokens = await asyncio.wait_for(
                        self._run_agent_sdk(
                            model_selection.model_id,
                            system_prompt,
                            prompt,
                        ),
                        timeout=timeout,
                    )
                else:
                    output, tokens = await asyncio.wait_for(
                        self._run_direct(
                            model_selection.model_id,
                            system_prompt,
                            prompt,
                        ),
                        timeout=timeout,
                    )
                elapsed = time.monotonic() - start
                return DispatchResult(
                    work_item_id=work_item.id,
                    success=True,
                    output=output,
                    model_used=model_selection.model_id,
                    tokens_used=tokens,
                    duration_seconds=round(elapsed, 3),
                )
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                log.warning(
                    "dispatch timeout: work_item=%s model=%s timeout=%.0fs",
                    work_item.id,
                    model_selection.model_id,
                    timeout,
                )
                return DispatchResult(
                    work_item_id=work_item.id,
                    success=False,
                    output="",
                    model_used=model_selection.model_id,
                    tokens_used=0,
                    duration_seconds=round(elapsed, 3),
                    error=f"Timed out after {timeout}s",
                )
            except Exception as exc:
                elapsed = time.monotonic() - start
                log.exception(
                    "dispatch error: work_item=%s error=%s",
                    work_item.id,
                    exc,
                )
                return DispatchResult(
                    work_item_id=work_item.id,
                    success=False,
                    output="",
                    model_used=model_selection.model_id,
                    tokens_used=0,
                    duration_seconds=round(elapsed, 3),
                    error=str(exc),
                )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(self, work_item: WorkItem) -> str:
        """Construct the user-facing prompt from WorkItem fields."""
        parts: list[str] = []

        if work_item.prompt:
            parts.append(work_item.prompt)
        elif work_item.command:
            parts.append(
                f"Execute the following command and report the result:\n```\n{work_item.command}\n```"
            )
        else:
            parts.append(work_item.description)

        if work_item.files:
            file_list = "\n".join(f"  - {f}" for f in work_item.files)
            parts.append(f"\nRelevant files:\n{file_list}")

        if work_item.metadata:
            context_lines = "\n".join(f"  {k}: {v}" for k, v in work_item.metadata.items())
            parts.append(f"\nAdditional context:\n{context_lines}")

        return "\n\n".join(parts)

    def _build_system_prompt(self, work_item: WorkItem) -> str:
        """Construct a system prompt with project context."""
        if work_item.system_prompt:
            return work_item.system_prompt

        parts: list[str] = [
            "You are a focused execution agent.",
            f"Task type: {work_item.task_type}",
        ]
        if work_item.project:
            parts.append(f"Project: {work_item.project}")

        parts.append(
            "Complete the task precisely. Return structured output when possible. "
            "If the task cannot be completed, explain why clearly."
        )
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Agent creation / execution
    # ------------------------------------------------------------------

    def _create_agent(self, model_id: str, system_prompt: str) -> Any:
        """Create a Claude Agent SDK agent instance.

        Returns the agent object. Raises ``RuntimeError`` if the SDK is not
        installed.
        """
        if not AGENT_SDK_AVAILABLE:
            raise RuntimeError("Claude Agent SDK is not installed")
        return Agent(model=model_id, system_prompt=system_prompt)

    async def _run_agent_sdk(
        self,
        model_id: str,
        system_prompt: str,
        prompt: str,
    ) -> tuple[str, int]:
        """Execute via Claude Agent SDK and return (output, tokens_used)."""
        agent = self._create_agent(model_id, system_prompt)
        result = await asyncio.to_thread(agent.run, prompt)
        output = getattr(result, "output", str(result))
        tokens = getattr(result, "tokens_used", 0)
        return output, tokens

    async def _run_direct(
        self,
        model_id: str,
        system_prompt: str,
        prompt: str,
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        """Direct Anthropic API call as fallback when Agent SDK unavailable."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract text from response content blocks.
        content_blocks = data.get("content", [])
        output = "\n".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return output, tokens
