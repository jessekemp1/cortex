#!/usr/bin/env python3
"""
Data models for model selection and orchestration.

This module defines the core data structures used throughout the
intelligent orchestration system.
"""

from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional


@dataclass
class ModelOutcomeEntry:
    """
    Track model performance for learning-based selection.

    Logged after each task to build historical performance data.
    Used by ModelPerformanceLearner to recommend optimal models.
    """

    timestamp: str
    task_id: str  # Unique task identifier
    task_type: str  # "explore", "implement", "debug", "search", etc.
    task_description: str  # First 200 chars of prompt

    # Model selection
    model_used: str  # "haiku" | "sonnet" | "opus"
    model_recommended_by: str  # "rules" | "learned" | "user_override"
    complexity_classified: str  # "simple" | "moderate" | "complex"
    confidence: float  # 0.0-1.0 confidence in recommendation

    # Performance metrics
    outcome: str  # "success" | "partial" | "failed" | "retry_needed"
    tokens_used: int
    time_seconds: float
    error_count: int  # Number of corrections needed

    # Cost analysis
    estimated_cost_usd: float
    alternative_models: List[Dict[str, Any]] = field(default_factory=list)

    # Context
    project_name: str = ""
    files_touched: List[str] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class WorkflowOutcomeEntry:
    """
    Track workflow-level outcomes.

    A workflow is a sequence of related tasks (e.g., "fix bug" workflow
    might include: search code, read files, make changes, run tests).
    """

    timestamp: str
    workflow_id: str
    workflow_type: str  # "bug_fix", "feature_implementation", "refactor", etc.
    priority: str  # "high" | "medium" | "low"

    # Planning
    estimated_tasks: int
    estimated_time_minutes: float
    estimated_cost: float

    # Execution
    actual_tasks_completed: int
    actual_time_minutes: float
    actual_cost: float

    # Quality
    success_rate: float  # % of subtasks that succeeded
    retry_count: int
    model_upgrades: int  # How many times upgraded model

    # Outcome
    outcome: str  # "completed" | "partial" | "failed" | "skipped"
    user_satisfaction: Optional[int] = None  # 1-5 rating
    notes: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class SessionOutcomeEntry:
    """
    Track orchestration session outcomes.

    A session is a complete work period with time and cost budgets.
    Tracks overall productivity and resource utilization.
    """

    timestamp: str
    session_id: str

    # Constraints
    time_budget_minutes: float
    cost_budget: float

    # Plan
    planned_workflows: int
    planned_tasks: int
    planned_cost: float

    # Actual
    completed_workflows: int
    completed_tasks: int
    actual_cost: float
    actual_time_minutes: float

    # Efficiency
    budget_utilization: float  # % of budget used
    time_utilization: float  # % of time used
    tasks_per_dollar: float  # Productivity metric

    # Quality
    high_priority_completed: int
    total_retries: int
    total_model_upgrades: int

    # Outcome
    outcome: str  # "success" | "partial" | "budget_exceeded" | "time_exceeded"
    user_satisfaction: Optional[int] = None
    notes: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ModelRecommendation:
    """
    A model recommendation with reasoning and alternatives.

    Returned by ContextAwareModelRecommender to suggest which model
    (Haiku, Sonnet, Opus) to use for a task.
    """

    model: str  # "haiku" | "sonnet" | "opus"
    confidence: float  # 0.0-1.0
    reasoning: str  # Human-readable explanation

    # Performance predictions
    estimated_success_rate: float  # Based on historical data
    estimated_tokens: int
    estimated_cost_usd: float

    # Historical evidence
    similar_tasks_count: int  # How many similar tasks in history
    historical_success_rate: float  # For this model + task type combo

    # Alternatives
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class OrchestrationContext:
    """
    Context passed to model recommender during orchestration.

    Provides situational awareness for context-aware recommendations.
    """

    # Budget/time constraints
    remaining_budget: float
    remaining_time: timedelta

    # Task metadata
    task_priority: str  # "high" | "medium" | "low"
    is_retry: bool = False
    previous_model: Optional[str] = None

    # Project context
    project: str = ""
    files: List[str] = field(default_factory=list)

    # Parallel load
    parallel_tasks: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert timedelta to seconds for serialization
        data["remaining_time"] = self.remaining_time.total_seconds()
        return data


@dataclass
class RecoveryAction:
    """
    A recovery action for handling task failures.

    Returned by IntelligentFailureHandler to specify how to recover
    from a task failure.
    """

    action: str  # "retry_upgraded" | "retry_context" | "ask_user" | "skip"
    new_model: Optional[str] = None
    estimated_additional_cost: float = 0.0
    reasoning: str = ""
    user_prompt: Optional[str] = None
    options: List[str] = field(default_factory=list)
    additional_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# Type aliases for clarity
TaskType = str  # "explore" | "search" | "implement" | "debug" | "refactor" | etc.
Complexity = str  # "simple" | "moderate" | "complex"
Model = str  # "haiku" | "sonnet" | "opus"
Outcome = str  # "success" | "partial" | "failed" | "retry_needed"
Priority = str  # "high" | "medium" | "low"
