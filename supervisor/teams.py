"""
Team-of-Teams orchestration — Opus-lead delegation pattern.

Opus handles the THINKING (decompose + synthesize). Cheaper models handle
the EXECUTION (sub-tasks). This is the highest-leverage cost optimization:
Opus only runs 2 calls (~10K tokens) while sonnet/haiku handle 2-5 sub-tasks.

Design constraint: ONE LEVEL DEEP. Teams cannot spawn teams.

Flow:
  1. should_use_team(work_item) → Optional[team_name]
  2. Opus decomposes into 2-5 typed, dependency-aware sub-tasks (LLM call)
  3. Independent sub-tasks run in parallel at assigned tier; dependent ones wait
  4. Opus synthesizes results into coherent response (LLM call)
  5. Budget enforced at each step — hard stop on exceed
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Valid task types for sub-tasks
_VALID_TASK_TYPES = {
    "research",
    "implement",
    "test",
    "review",
    "classify",
    "validate",
    "format",
    "fix",
    "refactor",
    "analyze",
}

# Max sub-tasks per opus decomposition call to prevent cost explosion
_MAX_OPUS_SUBTASKS = 1

# ---------------------------------------------------------------------------
# Prompts — the core of the Opus-lead pattern
# ---------------------------------------------------------------------------

DECOMPOSITION_SYSTEM = """\
You are a senior technical lead decomposing a complex task into parallelizable sub-tasks.

RULES:
1. Output ONLY a JSON array. No prose before or after.
2. Each sub-task must be independently executable — include ALL context needed.
   The executing model sees ONLY its own description, not the parent task.
3. Assign the CHEAPEST tier that can handle each sub-task:
   - haiku: extraction, classification, formatting, simple search, validation
   - sonnet: implementation, testing, research, code review, analysis
   - opus: ONLY for sub-tasks requiring deep reasoning across multiple domains
4. Mark dependencies explicitly. Independent tasks MUST have empty depends_on.
5. Produce 2-5 sub-tasks. Prefer fewer, broader sub-tasks over many narrow ones.
6. Maximize parallelism — minimize sequential dependencies.
7. Include specific files relevant to each sub-task (not all files)."""

DECOMPOSITION_USER = """\
TASK: {description}
PROJECT: {project}
FILES: {files}
PRIORITY: {priority}

Decompose into 2-5 sub-tasks. Output JSON array:
[
  {{
    "description": "Detailed, self-contained instruction for this sub-task",
    "task_type": "research|implement|test|review|classify|validate|format",
    "required_tier": "haiku|sonnet|opus",
    "depends_on": [],
    "estimated_tokens": 3000,
    "files": ["specific/file.py"],
    "rationale": "Why this tier, why this ordering"
  }}
]"""

SYNTHESIS_SYSTEM = """\
You are a senior technical lead synthesizing work from your team into a single
coherent deliverable. Your team completed sub-tasks independently — they could
not see each other's work.

RULES:
1. Integrate results into ONE unified response. Do NOT list sub-task outputs.
2. Resolve contradictions between sub-task outputs (prefer the more specific one).
3. Fill gaps — if a sub-task was skipped or failed, address what's missing.
4. Quality-check: if a sub-task output is clearly wrong, note it and correct.
5. Match the format the original task expects (code, analysis, plan, etc.).
6. Be concise. The sub-tasks did the heavy lifting — you are editing, not rewriting."""

SYNTHESIS_USER = """\
ORIGINAL TASK: {description}

SUB-TASK RESULTS:
{formatted_results}

FAILED/SKIPPED:
{failed_summary}

Synthesize into a single, coherent response to the original task."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TeamDefinition:
    """Defines a specialized team with its agents and budget."""

    name: str  # "research", "implementation", "architecture"
    lead_agent: str  # AgentProfile name from registry
    member_agents: List[str]  # AgentProfile names
    max_concurrent: int = 3
    token_budget: int = 500_000
    cost_budget_usd: float = 5.0
    allowed_providers: List[str] = field(default_factory=lambda: ["anthropic"])


@dataclass
class TeamTask:
    """A sub-task within a team decomposition."""

    parent_id: str  # Original WorkItem.id
    sub_task_id: str  # Unique sub-task identifier
    description: str
    task_type: str  # research, implement, test, review, classify
    sequence: int  # Execution order hint
    depends_on: List[int] = field(default_factory=list)  # Indices of dependencies
    estimated_tokens: int = 3000
    required_tier: str = "sonnet"
    files: List[str] = field(default_factory=list)  # Specific files for this sub-task
    rationale: str = ""  # Why this tier/ordering (from Opus decomposition)


@dataclass
class BudgetTracker:
    """Enforces token and cost budgets per team execution."""

    token_limit: int
    cost_limit_usd: float
    tokens_spent: int = 0
    cost_spent_usd: float = 0.0

    def can_afford(self, estimated_tokens: int) -> bool:
        """Conservative: check both token and cost budgets."""
        return (
            self.tokens_spent + estimated_tokens <= self.token_limit
            and self.cost_spent_usd < self.cost_limit_usd
        )

    def record_spend(self, tokens: int, cost_usd: float) -> None:
        self.tokens_spent += tokens
        self.cost_spent_usd += cost_usd

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.token_limit - self.tokens_spent)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cost_limit_usd - self.cost_spent_usd)

    @property
    def budget_exhausted(self) -> bool:
        return self.tokens_spent >= self.token_limit or self.cost_spent_usd >= self.cost_limit_usd


@dataclass
class TeamExecution:
    """Result of a team-based execution."""

    parent_id: str
    team: str
    sub_results: List[Dict[str, Any]]  # Per sub-task results
    synthesized_output: str = ""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    budget_remaining_tokens: int = 0
    budget_remaining_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Team registry
# ---------------------------------------------------------------------------

TEAM_REGISTRY: Dict[str, TeamDefinition] = {
    "research": TeamDefinition(
        name="research",
        lead_agent="researcher",
        member_agents=["classifier", "code_reviewer"],
        token_budget=200_000,
        cost_budget_usd=2.0,
    ),
    "implementation": TeamDefinition(
        name="implementation",
        lead_agent="implementer",
        member_agents=["test_engineer", "code_reviewer"],
        token_budget=500_000,
        cost_budget_usd=5.0,
    ),
    "architecture": TeamDefinition(
        name="architecture",
        lead_agent="architect",
        member_agents=["researcher", "implementer"],
        token_budget=300_000,
        cost_budget_usd=3.0,
    ),
}


# ---------------------------------------------------------------------------
# Team orchestrator
# ---------------------------------------------------------------------------


class TeamOrchestrator:
    """Orchestrates complex tasks through Opus-lead delegation.

    Pattern: Opus thinks (decompose + synthesize), cheaper models execute.
    - Decomposition: Opus analyzes task, designs sub-task DAG, assigns tiers
    - Execution: sonnet/haiku handle bounded sub-tasks in parallel
    - Synthesis: Opus integrates results into coherent response
    """

    # Task types that should NEVER use teams (too simple or not decomposable)
    _NEVER_TEAM_TYPES = {"classify", "triage", "categorize", "tag", "docs", "format", "validate"}

    # Task types that benefit from team decomposition
    _TEAM_ELIGIBLE_TYPES = {
        "architecture": "architecture",
        "refactor": "implementation",
        "planning": "architecture",
        "security": "architecture",
        "implement": "implementation",
        "research": "research",
    }

    # Gate thresholds — delegation overhead recovered above these
    _COMPLEXITY_GATE = 0.7
    _TOKEN_GATE = 30_000  # Lowered from 50K — delegation breaks even at ~15K execution tokens

    def __init__(self, enabled: bool = False, dispatcher: Any = None) -> None:
        self._enabled = enabled
        self._dispatcher = dispatcher  # MultiProviderDispatcher or AgentDispatcher

    def should_use_team(
        self,
        work_item: Any,
        complexity_score: float = 0.0,
    ) -> Optional[str]:
        """Determine if team execution is beneficial.

        Returns team name or None.

        Decision matrix:
          - complexity >= 0.7 AND estimated_tokens > 30K AND eligible type → YES
          - Otherwise → NO
        """
        if not self._enabled:
            return None

        task_type = getattr(work_item, "task_type", "")
        estimated_tokens = getattr(work_item, "estimated_tokens", 0)
        files = getattr(work_item, "files", [])

        # Never use teams for simple task types
        if task_type in self._NEVER_TEAM_TYPES:
            return None

        # Check eligibility
        team_name = self._TEAM_ELIGIBLE_TYPES.get(task_type)
        if not team_name:
            return None

        # Complexity gate
        if complexity_score < self._COMPLEXITY_GATE:
            return None

        # Token gate (team overhead not worth it for small tasks)
        if estimated_tokens <= self._TOKEN_GATE:
            return None

        log.info(
            "Team recommended: %s for %s (complexity=%.2f, tokens=%d, files=%d)",
            team_name,
            task_type,
            complexity_score,
            estimated_tokens,
            len(files or []),
        )
        return team_name

    def get_team(self, team_name: str) -> Optional[TeamDefinition]:
        """Look up a team definition."""
        return TEAM_REGISTRY.get(team_name)

    async def execute_with_team(
        self,
        work_item: Any,
        team_name: str,
        dispatch_fn: Any = None,
    ) -> TeamExecution:
        """Execute a work item using Opus-lead delegation.

        Steps:
        1. Opus decomposes into typed, dependency-aware sub-tasks (LLM call)
        2. Sub-tasks executed at assigned tiers via DAG scheduler
        3. Opus synthesizes results into coherent response (LLM call)
        4. Budget enforced at each step — hard stop on exceed
        """
        team = TEAM_REGISTRY.get(team_name)
        if not team:
            return TeamExecution(
                parent_id=getattr(work_item, "id", "unknown"),
                team=team_name,
                sub_results=[],
                success=False,
                error=f"Unknown team: {team_name}",
            )

        budget = BudgetTracker(
            token_limit=team.token_budget,
            cost_limit_usd=team.cost_budget_usd,
        )

        parent_id = getattr(work_item, "id", "unknown")

        # Step 1: Decompose via Opus (falls back to default on failure)
        sub_tasks = await self._decompose(work_item, team, budget)

        # Step 2: Execute sub-tasks respecting dependency DAG
        sub_results = await self._execute_dag(sub_tasks, budget, dispatch_fn)

        # Step 3: Synthesize via Opus (falls back to concatenation on failure)
        synthesized = await self._synthesize(
            work_item,
            sub_tasks,
            sub_results,
            team,
            budget,
        )

        return TeamExecution(
            parent_id=parent_id,
            team=team_name,
            sub_results=sub_results,
            synthesized_output=synthesized,
            total_tokens=budget.tokens_spent,
            total_cost_usd=budget.cost_spent_usd,
            budget_remaining_tokens=budget.remaining_tokens,
            budget_remaining_usd=budget.remaining_usd,
            success=any(r.get("success") for r in sub_results),
        )

    # ------------------------------------------------------------------
    # Decomposition (Opus call)
    # ------------------------------------------------------------------

    async def _decompose(
        self,
        work_item: Any,
        team: TeamDefinition,
        budget: BudgetTracker,
    ) -> List[TeamTask]:
        """Call Opus to decompose task. Parse JSON. Validate. Fallback on failure."""
        # If no dispatcher or insufficient budget, use default
        if self._dispatcher is None or not budget.can_afford(5000):
            log.info("Using default decomposition (no dispatcher or budget tight)")
            return self._default_decomposition(work_item, team)

        parent_id = getattr(work_item, "id", "unknown")
        description = getattr(work_item, "description", "")
        project = getattr(work_item, "project", "") or "unknown"
        files = getattr(work_item, "files", []) or []
        priority = getattr(work_item, "priority", None)
        priority_str = priority.value if hasattr(priority, "value") else str(priority or "medium")

        prompt = DECOMPOSITION_USER.format(
            description=description,
            project=project,
            files=", ".join(files[:20]),  # Cap file list length
            priority=priority_str,
        )

        try:
            result = await self._dispatch_to_opus(
                item_id=f"{parent_id}-decompose",
                system_prompt=DECOMPOSITION_SYSTEM,
                user_prompt=prompt,
                task_type="planning",
                estimated_tokens=5000,
            )

            budget.record_spend(
                result.get("tokens_used", 0),
                result.get("cost_usd", 0.0),
            )

            if not result.get("success"):
                log.warning("Decomposition dispatch failed, using default")
                return self._default_decomposition(work_item, team)

            output = result.get("output", "")
            raw = json.loads(output)
            validated = self._validate_decomposition(raw, parent_id)
            log.info(
                "Opus decomposed into %d sub-tasks: %s",
                len(validated),
                ", ".join(f"{t.task_type}({t.required_tier})" for t in validated),
            )
            return validated

        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Bad decomposition output (%s), using default", exc)
            return self._default_decomposition(work_item, team)
        except Exception as exc:
            log.warning("Decomposition failed (%s), using default", exc)
            return self._default_decomposition(work_item, team)

    def _validate_decomposition(
        self,
        raw: Any,
        parent_id: str,
    ) -> List[TeamTask]:
        """Validate and convert Opus JSON output to TeamTask list."""
        if not isinstance(raw, list):
            raise ValueError("Decomposition must be a JSON array")
        if len(raw) < 2:
            raise ValueError(f"Expected 2+ sub-tasks, got {len(raw)}")

        # Truncate to 5
        raw = raw[:5]

        # Track opus sub-tasks — limit to prevent cost explosion
        opus_seen = 0

        tasks: List[TeamTask] = []
        for i, item in enumerate(raw):
            desc = item.get("description", "")
            if not desc or len(desc) < 20:
                raise ValueError(f"Sub-task {i} has empty/short description")

            task_type = item.get("task_type", "implement")
            if task_type not in _VALID_TASK_TYPES:
                task_type = "implement"

            tier = item.get("required_tier", "sonnet")
            if tier not in ("haiku", "sonnet", "opus"):
                tier = "sonnet"

            # Limit opus sub-tasks
            if tier == "opus":
                opus_seen += 1
                if opus_seen > _MAX_OPUS_SUBTASKS:
                    tier = "sonnet"
                    log.info(
                        "Downgraded sub-task %d from opus to sonnet (limit %d)",
                        i,
                        _MAX_OPUS_SUBTASKS,
                    )

            # Validate dependencies
            depends_on = item.get("depends_on", [])
            if not isinstance(depends_on, list):
                depends_on = []
            for dep in depends_on:
                if not isinstance(dep, int) or dep < 0 or dep >= i:
                    raise ValueError(
                        f"Sub-task {i} has invalid dependency {dep} (must be 0..{i - 1})"
                    )

            tasks.append(
                TeamTask(
                    parent_id=parent_id,
                    sub_task_id=f"{parent_id}-sub-{i}",
                    description=desc,
                    task_type=task_type,
                    sequence=i,
                    depends_on=depends_on,
                    estimated_tokens=item.get("estimated_tokens", 3000),
                    required_tier=tier,
                    files=item.get("files", []),
                    rationale=item.get("rationale", ""),
                )
            )

        return tasks

    def _default_decomposition(
        self,
        work_item: Any,
        team: TeamDefinition,
    ) -> List[TeamTask]:
        """Fallback decomposition: research → implement → review."""
        parent_id = getattr(work_item, "id", "unknown")
        description = getattr(work_item, "description", "")

        return [
            TeamTask(
                parent_id=parent_id,
                sub_task_id=f"{parent_id}-research",
                description=f"Research: {description[:200]}",
                task_type="research",
                sequence=0,
                depends_on=[],
                estimated_tokens=3000,
                required_tier="sonnet",
            ),
            TeamTask(
                parent_id=parent_id,
                sub_task_id=f"{parent_id}-implement",
                description=f"Implement: {description[:200]}",
                task_type="implement",
                sequence=1,
                depends_on=[0],
                estimated_tokens=5000,
                required_tier="sonnet",
            ),
            TeamTask(
                parent_id=parent_id,
                sub_task_id=f"{parent_id}-review",
                description=f"Review: {description[:200]}",
                task_type="review",
                sequence=2,
                depends_on=[1],
                estimated_tokens=3000,
                required_tier="sonnet",
            ),
        ]

    # ------------------------------------------------------------------
    # Synthesis (Opus call)
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        work_item: Any,
        sub_tasks: List[TeamTask],
        sub_results: List[Dict[str, Any]],
        team: TeamDefinition,
        budget: BudgetTracker,
    ) -> str:
        """Call Opus to synthesize sub-task outputs. Falls back to concat."""
        if self._dispatcher is None or not budget.can_afford(8000):
            return self._synthesize_fallback(work_item, sub_results, team)

        description = getattr(work_item, "description", "")
        parent_id = getattr(work_item, "id", "unknown")

        formatted = self._format_results_for_synthesis(sub_tasks, sub_results)
        failed = [
            f"Sub-task {i} ({sub_tasks[i].task_type}): {r.get('error', 'unknown')}"
            for i, r in enumerate(sub_results)
            if not r.get("success") and i < len(sub_tasks)
        ]

        prompt = SYNTHESIS_USER.format(
            description=description,
            formatted_results=formatted,
            failed_summary="\n".join(failed) if failed else "None",
        )

        try:
            result = await self._dispatch_to_opus(
                item_id=f"{parent_id}-synthesize",
                system_prompt=SYNTHESIS_SYSTEM,
                user_prompt=prompt,
                task_type="review",
                estimated_tokens=8000,
            )

            budget.record_spend(
                result.get("tokens_used", 0),
                result.get("cost_usd", 0.0),
            )

            if result.get("success"):
                return result.get("output", "")

        except Exception as exc:
            log.warning("Synthesis failed (%s), using fallback", exc)

        return self._synthesize_fallback(work_item, sub_results, team)

    def _format_results_for_synthesis(
        self,
        sub_tasks: List[TeamTask],
        sub_results: List[Dict[str, Any]],
    ) -> str:
        """Format sub-task results for the synthesis prompt.

        Each sub-task output is capped at 4000 chars to prevent one verbose
        sub-task from consuming the synthesis context window.
        """
        parts = []
        for i, r in enumerate(sub_results):
            task = sub_tasks[i] if i < len(sub_tasks) else None
            task_type = task.task_type if task else "unknown"
            tier = task.required_tier if task else "unknown"
            desc = task.description[:100] if task else "unknown"
            status = "SUCCESS" if r.get("success") else "FAILED"
            output = r.get("output", r.get("error", "no output"))

            parts.append(
                f"--- Sub-task {i}: {task_type} ({tier}) ---\n"
                f"Description: {desc}\n"
                f"Status: {status}\n"
                f"Output:\n{str(output)[:4000]}\n"
            )
        return "\n".join(parts)

    def _synthesize_fallback(
        self,
        work_item: Any,
        sub_results: List[Dict[str, Any]],
        team: TeamDefinition,
    ) -> str:
        """Simple concatenation fallback when Opus synthesis unavailable."""
        outputs = []
        for i, r in enumerate(sub_results):
            status = "✓" if r.get("success") else "✗"
            output = r.get("output", r.get("error", "no output"))
            outputs.append(f"[{status}] Sub-task {i}: {output[:200]}")
        return "\n".join(outputs)

    # ------------------------------------------------------------------
    # Opus dispatch helper
    # ------------------------------------------------------------------

    async def _dispatch_to_opus(
        self,
        item_id: str,
        system_prompt: str,
        user_prompt: str,
        task_type: str,
        estimated_tokens: int,
    ) -> Dict[str, Any]:
        """Dispatch a single call to Opus via the existing dispatcher.

        Creates a synthetic WorkItem + ModelSelection targeting Opus/Anthropic.
        """
        from cortex.supervisor.dispatch import ModelSelection
        from cortex.supervisor.models import WorkItem

        work_item = WorkItem(
            id=item_id,
            source="team_orchestrator",
            task_type=task_type,
            description=user_prompt,
            system_prompt=system_prompt,
            estimated_tokens=estimated_tokens,
        )

        selection = ModelSelection(
            model_tier="opus",
            model_id="claude-opus-4-6",
            reasoning="Team lead (Opus-level thinking)",
            complexity_score=1.0,
            confidence=1.0,
            provider="anthropic",
        )

        # Use sync dispatch (run in thread if called from async context)
        if hasattr(self._dispatcher, "dispatch"):
            result = await asyncio.to_thread(
                self._dispatcher.dispatch,
                work_item,
                selection,
            )
            return {
                "success": result.success,
                "output": result.output,
                "tokens_used": result.tokens_used,
                "cost_usd": getattr(result, "cost_usd", 0.0),
                "model_used": result.model_used,
            }

        return {
            "success": False,
            "error": "no dispatcher available",
            "tokens_used": 0,
            "cost_usd": 0.0,
        }

    # ------------------------------------------------------------------
    # DAG execution
    # ------------------------------------------------------------------

    async def _execute_dag(
        self,
        sub_tasks: List[TeamTask],
        budget: BudgetTracker,
        dispatch_fn: Any = None,
    ) -> List[Dict[str, Any]]:
        """Execute sub-tasks respecting dependency DAG.

        Algorithm:
        1. Build dependency graph
        2. Find tasks with no unmet dependencies → dispatch in parallel
        3. As tasks complete, unblock dependents → dispatch
        4. Budget check before each dispatch
        5. Failed task → mark dependents as skipped
        """
        results: Dict[int, Dict[str, Any]] = {}
        pending = set(range(len(sub_tasks)))

        while pending:
            # Find ready tasks (all dependencies satisfied)
            ready = [i for i in pending if all(d in results for d in sub_tasks[i].depends_on)]

            if not ready:
                # Deadlock or all remaining depend on failures
                for i in pending:
                    results[i] = {"success": False, "error": "dependency_deadlock"}
                break

            # Dispatch ready tasks (parallel where possible)
            coros = []
            ready_indices = []

            for i in list(ready):
                if not budget.can_afford(sub_tasks[i].estimated_tokens):
                    results[i] = {"success": False, "error": "budget_exceeded"}
                    pending.discard(i)
                    self._cascade_skip(i, sub_tasks, results, pending)
                    continue

                if dispatch_fn:
                    coros.append(dispatch_fn(sub_tasks[i]))
                    ready_indices.append(i)
                elif self._dispatcher and hasattr(self._dispatcher, "dispatch"):
                    coros.append(self._dispatch_sub_task(sub_tasks[i]))
                    ready_indices.append(i)
                else:
                    # Placeholder execution
                    results[i] = {
                        "success": True,
                        "output": f"[placeholder] {sub_tasks[i].description[:50]}",
                        "tokens_used": sub_tasks[i].estimated_tokens,
                        "cost_usd": 0.0,
                    }
                    pending.discard(i)

            # Execute ready tasks (parallel via gather)
            if coros:
                batch_results = await asyncio.gather(*coros, return_exceptions=True)
                for idx, batch_result in zip(ready_indices, batch_results):
                    if isinstance(batch_result, Exception):
                        results[idx] = {"success": False, "error": str(batch_result)}
                    elif isinstance(batch_result, dict):
                        results[idx] = batch_result
                    else:
                        results[idx] = {"success": False, "error": "unexpected result type"}
                    pending.discard(idx)

            # Record spend and cascade failures
            for i in ready_indices:
                if i in results:
                    tokens = results[i].get("tokens_used", 0)
                    cost = results[i].get("cost_usd", 0.0)
                    budget.record_spend(tokens, cost)

                    if not results[i].get("success"):
                        self._cascade_skip(i, sub_tasks, results, pending)

            # Handle non-coroutine placeholder results
            for i in list(ready):
                if i not in ready_indices and i in results:
                    tokens = results[i].get("tokens_used", 0)
                    cost = results[i].get("cost_usd", 0.0)
                    budget.record_spend(tokens, cost)

        return [
            results.get(i, {"success": False, "error": "not_reached"})
            for i in range(len(sub_tasks))
        ]

    async def _dispatch_sub_task(self, sub_task: TeamTask) -> Dict[str, Any]:
        """Dispatch a single sub-task at its assigned tier via the dispatcher."""
        from cortex.supervisor.dispatch import ModelSelection
        from cortex.supervisor.models import WorkItem

        _MODEL_MAP = {
            "opus": "claude-opus-4-6",
            "sonnet": "claude-sonnet-4-6",
            "haiku": "claude-haiku-4-5-20251001",
        }

        work_item = WorkItem(
            id=sub_task.sub_task_id,
            source="team_sub_task",
            task_type=sub_task.task_type,
            description=sub_task.description,
            files=sub_task.files,
            estimated_tokens=sub_task.estimated_tokens,
        )

        selection = ModelSelection(
            model_tier=sub_task.required_tier,
            model_id=_MODEL_MAP.get(sub_task.required_tier, "claude-sonnet-4-6"),
            reasoning=f"Team sub-task assigned to {sub_task.required_tier}",
            complexity_score=0.5,
            confidence=0.9,
        )

        result = await asyncio.to_thread(
            self._dispatcher.dispatch,
            work_item,
            selection,
        )

        return {
            "success": result.success,
            "output": result.output,
            "tokens_used": result.tokens_used,
            "cost_usd": getattr(result, "cost_usd", 0.0),
            "model_used": result.model_used,
        }

    def _cascade_skip(
        self,
        failed_idx: int,
        sub_tasks: List[TeamTask],
        results: Dict[int, Dict[str, Any]],
        pending: set,
    ) -> None:
        """Mark all tasks that depend on a failed task as skipped."""
        for i in list(pending):
            if failed_idx in sub_tasks[i].depends_on:
                results[i] = {
                    "success": False,
                    "error": f"dependency_failed:{failed_idx}",
                }
                pending.discard(i)
                # Recurse: skip tasks depending on this skipped task too
                self._cascade_skip(i, sub_tasks, results, pending)
