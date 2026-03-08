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
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
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

# Read-only tools available to dispatched agents.
AGENT_TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read a file from the project. Returns file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or project-relative file path",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_code",
        "description": "Search for a regex pattern in files. Returns matching lines with file paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: project root)",
                },
                "glob": {
                    "type": "string",
                    "description": "File pattern filter (e.g. '*.py')",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_files",
        "description": "List files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '**/*.py')",
                },
                "path": {
                    "type": "string",
                    "description": "Base directory",
                },
            },
            "required": ["pattern"],
        },
    },
]

_MAX_TOOL_TURNS = 10  # Safety limit for tool-use loops
_SEARCH_TIMEOUT = 10  # Seconds for grep subprocess
_MAX_SEARCH_LINES = 1000  # Truncate search results
_MAX_LIST_FILES = 100  # Limit file listing results
_MAX_READ_SIZE = 100_000  # Max file read size in bytes

# Re-export ModelSelection from router to maintain backwards compatibility.
# Previously duplicated here; now single source of truth in router.py.
from cortex.supervisor.router import ModelSelection  # noqa: E402


@dataclass
class DispatchResult:
    """Outcome of a single agent dispatch."""

    work_item_id: str
    success: bool
    output: str
    model_used: str
    tokens_used: int
    duration_seconds: float
    task_type: str = ""  # Propagated from WorkItem for outcome recording
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
        dry_run: bool = False,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._dry_run = dry_run

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
        # Dry-run: return synthetic result without calling API
        if self._dry_run:
            log.info(
                "DRY RUN: model=%s task=%s desc=%s",
                model_selection.model_id,
                work_item.task_type,
                work_item.description[:60],
            )
            return DispatchResult(
                work_item_id=work_item.id,
                success=True,
                output=f"[DRY RUN] Would dispatch to {model_selection.model_id}",
                model_used=model_selection.model_id,
                tokens_used=0,
                duration_seconds=0.0,
                task_type=work_item.task_type,
            )

        timeout = MODEL_TIMEOUTS.get(model_selection.model_tier, 120.0)
        prompt = self._build_prompt(work_item)
        system_prompt = self._build_system_prompt(work_item)
        project_root = self._resolve_project_root(work_item)

        start = time.monotonic()
        async with self._semaphore:
            try:
                output, tokens = await asyncio.wait_for(
                    self._run_dispatch(
                        model_selection.model_id,
                        system_prompt,
                        prompt,
                        project_root=project_root,
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
                    task_type=work_item.task_type,
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
                    task_type=work_item.task_type,
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
                    task_type=work_item.task_type,
                    error=str(exc),
                )

    def dispatch_and_record(
        self,
        work_item: WorkItem,
        model_selection: ModelSelection,
        router: Any = None,
    ) -> DispatchResult:
        """Dispatch and automatically record the outcome for learning.

        Convenience wrapper that calls :meth:`dispatch` then persists the
        outcome to the router's learning store.  Useful for ad-hoc dispatches
        outside the main ``tick()`` loop.
        """
        from supervisor.core import _estimate_quality

        result = self.dispatch(work_item, model_selection)

        if router is not None:
            quality = _estimate_quality(result)
            router.record_outcome(
                work_item_id=work_item.id,
                model_tier=model_selection.model_tier,
                success=result.success,
                quality_score=quality,
                task_type=work_item.task_type,
            )

        return result

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

    def _resolve_project_root(self, work_item: WorkItem) -> str:
        """Determine the project root directory for tool execution."""
        # Check metadata override first
        if work_item.metadata and work_item.metadata.get("project_root"):
            return str(work_item.metadata["project_root"])
        # Fall back to CORTEX_ROOT_DIR or cwd
        return os.environ.get("CORTEX_ROOT_DIR", os.getcwd())

    async def _run_dispatch(
        self,
        model_id: str,
        system_prompt: str,
        prompt: str,
        max_tokens: int = 4096,
        project_root: str = "",
    ) -> tuple[str, int]:
        """Execute via Anthropic SDK with multi-turn tool-use loop.

        Sends initial prompt, then loops:
        1. If response has tool_use blocks → execute tools, send results back
        2. If response has only text blocks → done, return text
        3. If max turns exceeded → return accumulated text
        """
        client = self._get_client()
        messages: list[dict] = [{"role": "user", "content": prompt}]
        total_tokens = 0

        for _turn in range(_MAX_TOOL_TURNS):
            response = await asyncio.to_thread(
                client.messages.create,
                model=model_id,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                tools=AGENT_TOOLS,
            )
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Check for tool_use blocks
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                # Final text response — no more tools needed
                text = "\n".join(b.text for b in response.content if b.type == "text")
                return text, total_tokens

            # Append assistant response, then execute tools and send results back
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tool_use in tool_uses:
                result_text = self._execute_tool(tool_use.name, tool_use.input, project_root)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_text,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        # Max turns exceeded — extract whatever text is available
        text_parts = [b.text for b in response.content if b.type == "text"]
        text = "\n".join(text_parts) if text_parts else "(max turns exceeded)"
        return text, total_tokens

    # ------------------------------------------------------------------
    # Tool execution (read-only)
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, tool_input: dict, project_root: str) -> str:
        """Execute a tool call and return the result as a string.

        All tools are read-only. Path traversal outside project_root is blocked.
        """
        root = Path(project_root).resolve() if project_root else Path.cwd().resolve()

        if tool_name == "read_file":
            return self._tool_read_file(tool_input, root)
        elif tool_name == "search_code":
            return self._tool_search_code(tool_input, root)
        elif tool_name == "list_files":
            return self._tool_list_files(tool_input, root)
        else:
            return f"Error: unknown tool '{tool_name}'"

    def _validate_path(self, raw_path: str, root: Path) -> tuple[Path | None, str]:
        """Validate a path is under the project root. Returns (resolved, error)."""
        try:
            target = (root / raw_path).resolve()
        except (ValueError, OSError) as exc:
            return None, f"Error: invalid path: {exc}"
        if not str(target).startswith(str(root)):
            return None, "Error: access denied — path outside project root"
        return target, ""

    def _tool_read_file(self, tool_input: dict, root: Path) -> str:
        """Read a file, with path safety checks."""
        raw_path = tool_input.get("path", "")
        target, err = self._validate_path(raw_path, root)
        if err:
            return err
        if not target.is_file():
            return f"Error: file not found: {raw_path}"
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            if len(content) > _MAX_READ_SIZE:
                content = content[:_MAX_READ_SIZE] + "\n... (truncated)"
            return content
        except OSError as exc:
            return f"Error reading file: {exc}"

    def _tool_search_code(self, tool_input: dict, root: Path) -> str:
        """Search for a pattern in files using grep."""
        pattern = tool_input.get("pattern", "")
        if not pattern:
            return "Error: pattern is required"

        search_path = tool_input.get("path", str(root))
        target, err = self._validate_path(search_path, root)
        if err:
            return err

        cmd = ["grep", "-rn", "--include=*.py", pattern, str(target)]
        glob_filter = tool_input.get("glob")
        if glob_filter:
            cmd = ["grep", "-rn", f"--include={glob_filter}", pattern, str(target)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=_SEARCH_TIMEOUT)
            output = result.stdout
            if len(output.splitlines()) > _MAX_SEARCH_LINES:
                lines = output.splitlines()[:_MAX_SEARCH_LINES]
                output = "\n".join(lines) + f"\n... ({len(output.splitlines())} total matches)"
            return output or "(no matches)"
        except subprocess.TimeoutExpired:
            return "Error: search timed out"
        except OSError as exc:
            return f"Error running search: {exc}"

    def _tool_list_files(self, tool_input: dict, root: Path) -> str:
        """List files matching a glob pattern."""
        pattern = tool_input.get("pattern", "*")
        base_path = tool_input.get("path", str(root))
        target, err = self._validate_path(base_path, root)
        if err:
            return err

        try:
            matches = sorted(target.glob(pattern))[:_MAX_LIST_FILES]
            if not matches:
                return "(no files match)"
            return "\n".join(str(m.relative_to(root)) for m in matches if m.is_file())
        except (OSError, ValueError) as exc:
            return f"Error listing files: {exc}"
