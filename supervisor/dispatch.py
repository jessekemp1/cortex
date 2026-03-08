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

from cortex.supervisor.models import WorkItem

try:
    import anthropic  # noqa: F401

    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    ANTHROPIC_SDK_AVAILABLE = False

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
                output, tokens = await asyncio.wait_for(
                    self._run_dispatch(
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
        """Construct a system prompt with project context.

        Uses agent profiles from the registry when available for the
        work item's task type, providing specialized instructions instead
        of the generic fallback.
        """
        if work_item.system_prompt:
            return work_item.system_prompt

        # Try to use a registered agent profile for better prompts
        from cortex.supervisor.agents import get_agent_for_task

        agent = get_agent_for_task(work_item.task_type)
        if agent:
            return agent.build_system_prompt(
                project=work_item.project or "",
                context=work_item.description,
            )

        # Fallback for unmatched task types
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

    def _get_client(self) -> Any:
        """Get an Anthropic client instance."""
        if not ANTHROPIC_SDK_AVAILABLE:
            raise RuntimeError("anthropic SDK not installed. Install with: pip install anthropic")
        return anthropic.Anthropic(api_key=self._api_key or None)

    async def _run_dispatch(
        self,
        model_id: str,
        system_prompt: str,
        prompt: str,
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        """Execute via Anthropic SDK and return (output, tokens_used).

        Uses the official ``anthropic`` package which handles auth,
        retries, and streaming correctly.
        """
        client = self._get_client()
        response = await asyncio.to_thread(
            client.messages.create,
            model=model_id,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response content blocks.
        output = "\n".join(block.text for block in response.content if block.type == "text")
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return output, tokens
