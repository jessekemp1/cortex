#!/usr/bin/env python3
"""
Subscription Token Utilization Optimizer

Maximizes value from LLM subscription plans by tracking utilization rates,
detecting token waste, and proactively scheduling work to use unused capacity.

Most LLM subscriptions (Anthropic Pro, OpenAI Plus, etc.) provide monthly
token allowances that reset on a billing cycle. Unused tokens are lost.
This module ensures you get full value from what you're paying for.

Key Features:
- Subscription tier tracking (monthly allowance, reset dates, usage rates)
- Utilization gap detection (tokens paid for but not used)
- Token waste analysis (redundant context, verbose prompts, model mismatches)
- Proactive batch scheduling to fill unused capacity before reset
- ROI reporting (cost per useful output token)

Usage:
    from batch.subscription_optimizer import SubscriptionOptimizer

    optimizer = SubscriptionOptimizer()
    optimizer.configure_subscription(
        provider="anthropic",
        tier="pro",
        monthly_token_allowance=5_000_000,
        monthly_cost_usd=20.0,
        billing_reset_day=1,
    )

    status = optimizer.get_utilization_status()
    if status.utilization_pct < 60:
        suggestions = optimizer.suggest_capacity_fill()
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SubscriptionTier:
    """LLM subscription plan details."""

    provider: str  # "anthropic", "openai", etc.
    tier: str  # "pro", "team", "enterprise"
    monthly_token_allowance: int  # Total tokens per billing cycle
    monthly_cost_usd: float  # What you pay per month
    billing_reset_day: int  # Day of month the allowance resets (1-28)
    input_token_allowance: Optional[int] = None  # If input/output split separately
    output_token_allowance: Optional[int] = None
    rate_limit_rpm: Optional[int] = None  # Requests per minute
    rate_limit_tpm: Optional[int] = None  # Tokens per minute
    includes_batch: bool = True  # Whether batch API counts against allowance
    batch_discount_pct: float = 50.0  # Batch API discount percentage


@dataclass
class UtilizationStatus:
    """Current subscription utilization snapshot."""

    provider: str
    tier: str
    billing_period_start: str  # YYYY-MM-DD
    billing_period_end: str
    days_elapsed: int
    days_remaining: int

    # Token usage
    tokens_used: int
    tokens_allowance: int
    tokens_remaining: int
    utilization_pct: float

    # Projected usage
    projected_total_tokens: int  # At current burn rate
    projected_utilization_pct: float
    tokens_at_risk: int  # Tokens that will be wasted if pace doesn't change

    # Daily rates
    avg_daily_tokens: int
    required_daily_tokens: int  # To hit 100% utilization

    # Cost efficiency
    cost_per_1k_tokens_effective: float  # What you're actually paying per 1K tokens
    cost_per_1k_tokens_nominal: float  # What the plan nominally costs per 1K tokens

    # Recommendations
    status_level: str  # "underutilized", "on_track", "overutilized"
    recommendation: str


@dataclass
class TokenWasteReport:
    """Analysis of wasted tokens in recent usage."""

    period_days: int
    total_tokens_used: int

    # Waste categories
    redundant_context_tokens: int  # Repeated context across sessions
    oversized_prompt_tokens: int  # Prompts that could be more concise
    model_mismatch_tokens: int  # Tokens spent on wrong model tier
    failed_request_tokens: int  # Tokens consumed by failed/retried requests
    idle_capacity_tokens: int  # Allowance not used at all

    total_waste_tokens: int
    waste_pct: float

    # Actionable suggestions
    suggestions: List[str]


@dataclass
class CapacityFillSuggestion:
    """Suggestion for using unused subscription capacity."""

    task_type: str  # "code_review", "documentation", "research", etc.
    description: str
    estimated_tokens: int
    priority: str  # "high", "medium", "low"
    reason: str  # Why this is suggested now
    batch_eligible: bool


class SubscriptionOptimizer:
    """
    Optimizes token utilization across LLM subscriptions.

    Tracks subscription tiers, monitors usage against allowances,
    detects waste patterns, and proactively suggests work to
    maximize the value of paid subscriptions.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "subscriptions" / "utilization.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for subscription tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    provider TEXT,
                    tier TEXT,
                    monthly_token_allowance INTEGER,
                    monthly_cost_usd REAL,
                    billing_reset_day INTEGER,
                    input_token_allowance INTEGER,
                    output_token_allowance INTEGER,
                    rate_limit_rpm INTEGER,
                    rate_limit_tpm INTEGER,
                    includes_batch INTEGER DEFAULT 1,
                    batch_discount_pct REAL DEFAULT 50.0,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (provider, tier)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_token_usage (
                    date TEXT,
                    provider TEXT,
                    tokens_input INTEGER DEFAULT 0,
                    tokens_output INTEGER DEFAULT 0,
                    tokens_total INTEGER DEFAULT 0,
                    requests_count INTEGER DEFAULT 0,
                    failed_requests INTEGER DEFAULT 0,
                    batch_tokens INTEGER DEFAULT 0,
                    interactive_tokens INTEGER DEFAULT 0,
                    model_tier TEXT,
                    avg_prompt_tokens INTEGER DEFAULT 0,
                    avg_completion_tokens INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (date, provider)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS waste_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    provider TEXT,
                    waste_type TEXT,
                    tokens_wasted INTEGER,
                    description TEXT,
                    created_at TEXT
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_daily_usage_date
                ON daily_token_usage(date)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_waste_date
                ON waste_events(date)
            """
            )

            conn.commit()

    def configure_subscription(
        self,
        provider: str,
        tier: str,
        monthly_token_allowance: int,
        monthly_cost_usd: float,
        billing_reset_day: int = 1,
        **kwargs,
    ) -> SubscriptionTier:
        """
        Configure or update a subscription tier.

        Args:
            provider: LLM provider name
            tier: Subscription tier name
            monthly_token_allowance: Total tokens per billing cycle
            monthly_cost_usd: Monthly cost in USD
            billing_reset_day: Day of month allowance resets
            **kwargs: Additional SubscriptionTier fields

        Returns:
            Configured SubscriptionTier
        """
        now = datetime.now().isoformat()

        sub = SubscriptionTier(
            provider=provider,
            tier=tier,
            monthly_token_allowance=monthly_token_allowance,
            monthly_cost_usd=monthly_cost_usd,
            billing_reset_day=billing_reset_day,
            input_token_allowance=kwargs.get("input_token_allowance"),
            output_token_allowance=kwargs.get("output_token_allowance"),
            rate_limit_rpm=kwargs.get("rate_limit_rpm"),
            rate_limit_tpm=kwargs.get("rate_limit_tpm"),
            includes_batch=kwargs.get("includes_batch", True),
            batch_discount_pct=kwargs.get("batch_discount_pct", 50.0),
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO subscriptions (
                    provider, tier, monthly_token_allowance, monthly_cost_usd,
                    billing_reset_day, input_token_allowance, output_token_allowance,
                    rate_limit_rpm, rate_limit_tpm, includes_batch, batch_discount_pct,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, tier) DO UPDATE SET
                    monthly_token_allowance = ?,
                    monthly_cost_usd = ?,
                    billing_reset_day = ?,
                    input_token_allowance = ?,
                    output_token_allowance = ?,
                    rate_limit_rpm = ?,
                    rate_limit_tpm = ?,
                    includes_batch = ?,
                    batch_discount_pct = ?,
                    updated_at = ?
            """,
                (
                    provider,
                    tier,
                    monthly_token_allowance,
                    monthly_cost_usd,
                    billing_reset_day,
                    sub.input_token_allowance,
                    sub.output_token_allowance,
                    sub.rate_limit_rpm,
                    sub.rate_limit_tpm,
                    int(sub.includes_batch),
                    sub.batch_discount_pct,
                    now,
                    now,
                    # ON CONFLICT values
                    monthly_token_allowance,
                    monthly_cost_usd,
                    billing_reset_day,
                    sub.input_token_allowance,
                    sub.output_token_allowance,
                    sub.rate_limit_rpm,
                    sub.rate_limit_tpm,
                    int(sub.includes_batch),
                    sub.batch_discount_pct,
                    now,
                ),
            )
            conn.commit()

        return sub

    def record_usage(
        self,
        provider: str,
        tokens_input: int,
        tokens_output: int,
        is_batch: bool = False,
        model_tier: str = "sonnet",
        failed: bool = False,
    ):
        """
        Record token usage for a provider.

        Args:
            provider: LLM provider name
            tokens_input: Input tokens consumed
            tokens_output: Output tokens consumed
            is_batch: Whether this was a batch request
            model_tier: Model tier used (haiku/sonnet/opus)
            failed: Whether the request failed
        """
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        total = tokens_input + tokens_output

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO daily_token_usage (
                    date, provider, tokens_input, tokens_output, tokens_total,
                    requests_count, failed_requests, batch_tokens, interactive_tokens,
                    model_tier, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, provider) DO UPDATE SET
                    tokens_input = tokens_input + ?,
                    tokens_output = tokens_output + ?,
                    tokens_total = tokens_total + ?,
                    requests_count = requests_count + 1,
                    failed_requests = failed_requests + ?,
                    batch_tokens = batch_tokens + ?,
                    interactive_tokens = interactive_tokens + ?,
                    updated_at = ?
            """,
                (
                    today,
                    provider,
                    tokens_input,
                    tokens_output,
                    total,
                    int(failed),
                    total if is_batch else 0,
                    0 if is_batch else total,
                    model_tier,
                    now,
                    now,
                    # ON CONFLICT values
                    tokens_input,
                    tokens_output,
                    total,
                    int(failed),
                    total if is_batch else 0,
                    0 if is_batch else total,
                    now,
                ),
            )
            conn.commit()

        # Track waste from failed requests
        if failed and total > 0:
            self.record_waste(
                provider=provider,
                waste_type="failed_request",
                tokens_wasted=total,
                description=f"Failed request consumed {total:,} tokens",
            )

    def record_waste(
        self,
        provider: str,
        waste_type: str,
        tokens_wasted: int,
        description: str = "",
    ):
        """
        Record a token waste event.

        Args:
            provider: LLM provider
            waste_type: Category (redundant_context, oversized_prompt,
                        model_mismatch, failed_request, idle_capacity)
            tokens_wasted: Number of tokens wasted
            description: Human-readable description
        """
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO waste_events (date, provider, waste_type, tokens_wasted,
                                         description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (today, provider, waste_type, tokens_wasted, description, now),
            )
            conn.commit()

    def _get_subscription(self, provider: str) -> Optional[SubscriptionTier]:
        """Load subscription config for a provider."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE provider = ? ORDER BY updated_at DESC LIMIT 1",
                (provider,),
            ).fetchone()

            if not row:
                return None

            return SubscriptionTier(
                provider=row["provider"],
                tier=row["tier"],
                monthly_token_allowance=row["monthly_token_allowance"],
                monthly_cost_usd=row["monthly_cost_usd"],
                billing_reset_day=row["billing_reset_day"],
                input_token_allowance=row["input_token_allowance"],
                output_token_allowance=row["output_token_allowance"],
                rate_limit_rpm=row["rate_limit_rpm"],
                rate_limit_tpm=row["rate_limit_tpm"],
                includes_batch=bool(row["includes_batch"]),
                batch_discount_pct=row["batch_discount_pct"],
            )

    def _get_billing_period(self, reset_day: int) -> Tuple[datetime, datetime]:
        """Calculate current billing period start and end dates."""
        today = datetime.now()

        if today.day >= reset_day:
            period_start = today.replace(day=reset_day)
            # Next month
            if today.month == 12:
                period_end = today.replace(year=today.year + 1, month=1, day=reset_day)
            else:
                period_end = today.replace(month=today.month + 1, day=reset_day)
        else:
            # Previous month
            if today.month == 1:
                period_start = today.replace(year=today.year - 1, month=12, day=reset_day)
            else:
                period_start = today.replace(month=today.month - 1, day=reset_day)
            period_end = today.replace(day=reset_day)

        return period_start, period_end

    def _get_period_usage(self, provider: str, start_date: str, end_date: str) -> Dict[str, int]:
        """Get token usage for a billing period."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(tokens_total), 0) as total_tokens,
                    COALESCE(SUM(tokens_input), 0) as input_tokens,
                    COALESCE(SUM(tokens_output), 0) as output_tokens,
                    COALESCE(SUM(requests_count), 0) as total_requests,
                    COALESCE(SUM(failed_requests), 0) as failed_requests,
                    COALESCE(SUM(batch_tokens), 0) as batch_tokens,
                    COALESCE(SUM(interactive_tokens), 0) as interactive_tokens
                FROM daily_token_usage
                WHERE provider = ? AND date >= ? AND date < ?
            """,
                (provider, start_date, end_date),
            ).fetchone()

            return {
                "total_tokens": row["total_tokens"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "total_requests": row["total_requests"],
                "failed_requests": row["failed_requests"],
                "batch_tokens": row["batch_tokens"],
                "interactive_tokens": row["interactive_tokens"],
            }

    def get_utilization_status(self, provider: str = "anthropic") -> Optional[UtilizationStatus]:
        """
        Get current subscription utilization status.

        Args:
            provider: LLM provider to check

        Returns:
            UtilizationStatus with current metrics, or None if no subscription configured
        """
        sub = self._get_subscription(provider)
        if not sub:
            return None

        # Calculate billing period
        period_start, period_end = self._get_billing_period(sub.billing_reset_day)
        today = datetime.now()

        days_elapsed = max(1, (today - period_start).days)
        days_remaining = max(0, (period_end - today).days)
        total_days = days_elapsed + days_remaining

        # Get usage for this billing period
        usage = self._get_period_usage(
            provider,
            period_start.strftime("%Y-%m-%d"),
            period_end.strftime("%Y-%m-%d"),
        )

        tokens_used = usage["total_tokens"]
        tokens_remaining = max(0, sub.monthly_token_allowance - tokens_used)
        utilization_pct = (tokens_used / sub.monthly_token_allowance * 100) if sub.monthly_token_allowance > 0 else 0

        # Project total usage at current rate
        avg_daily = tokens_used // days_elapsed if days_elapsed > 0 else 0
        projected_total = avg_daily * total_days
        projected_utilization = (projected_total / sub.monthly_token_allowance * 100) if sub.monthly_token_allowance > 0 else 0

        # Tokens at risk of being wasted
        tokens_at_risk = max(0, sub.monthly_token_allowance - projected_total)

        # Required daily rate to use full allowance
        required_daily = tokens_remaining // days_remaining if days_remaining > 0 else 0

        # Cost efficiency
        cost_per_1k_nominal = (sub.monthly_cost_usd / sub.monthly_token_allowance * 1000) if sub.monthly_token_allowance > 0 else 0
        cost_per_1k_effective = (sub.monthly_cost_usd / tokens_used * 1000) if tokens_used > 0 else float("inf")

        # Determine status and recommendation
        if projected_utilization < 50:
            status_level = "underutilized"
            recommendation = (
                f"Projected to use only {projected_utilization:.0f}% of your allowance. "
                f"~{tokens_at_risk:,} tokens will be wasted. "
                f"Consider scheduling batch work to use {required_daily:,} tokens/day."
            )
        elif projected_utilization < 85:
            status_level = "on_track"
            recommendation = (
                f"Good utilization at {projected_utilization:.0f}% projected. "
                f"You have {tokens_remaining:,} tokens remaining over {days_remaining} days."
            )
        elif projected_utilization <= 100:
            status_level = "on_track"
            recommendation = (
                f"Excellent utilization at {projected_utilization:.0f}% projected. "
                f"Maximizing subscription value."
            )
        else:
            status_level = "overutilized"
            overage = projected_total - sub.monthly_token_allowance
            recommendation = (
                f"Projected to exceed allowance by {overage:,} tokens. "
                f"Consider routing low-priority work to batch or deferring to next cycle."
            )

        return UtilizationStatus(
            provider=provider,
            tier=sub.tier,
            billing_period_start=period_start.strftime("%Y-%m-%d"),
            billing_period_end=period_end.strftime("%Y-%m-%d"),
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            tokens_used=tokens_used,
            tokens_allowance=sub.monthly_token_allowance,
            tokens_remaining=tokens_remaining,
            utilization_pct=round(utilization_pct, 1),
            projected_total_tokens=projected_total,
            projected_utilization_pct=round(projected_utilization, 1),
            tokens_at_risk=tokens_at_risk,
            avg_daily_tokens=avg_daily,
            required_daily_tokens=required_daily,
            cost_per_1k_tokens_effective=round(cost_per_1k_effective, 4),
            cost_per_1k_tokens_nominal=round(cost_per_1k_nominal, 4),
            status_level=status_level,
            recommendation=recommendation,
        )

    def get_waste_report(self, provider: str = "anthropic", days: int = 30) -> TokenWasteReport:
        """
        Analyze token waste patterns over a period.

        Args:
            provider: LLM provider
            days: Number of days to analyze

        Returns:
            TokenWasteReport with waste breakdown and suggestions
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get total usage
            usage_row = conn.execute(
                """
                SELECT COALESCE(SUM(tokens_total), 0) as total_tokens,
                       COALESCE(SUM(failed_requests), 0) as failed_count
                FROM daily_token_usage
                WHERE provider = ? AND date >= ?
            """,
                (provider, cutoff),
            ).fetchone()

            total_tokens = usage_row["total_tokens"]

            # Get waste by type
            waste_rows = conn.execute(
                """
                SELECT waste_type, COALESCE(SUM(tokens_wasted), 0) as total_wasted
                FROM waste_events
                WHERE provider = ? AND date >= ?
                GROUP BY waste_type
            """,
                (provider, cutoff),
            ).fetchall()

        waste_by_type = {row["waste_type"]: row["total_wasted"] for row in waste_rows}

        redundant = waste_by_type.get("redundant_context", 0)
        oversized = waste_by_type.get("oversized_prompt", 0)
        mismatch = waste_by_type.get("model_mismatch", 0)
        failed = waste_by_type.get("failed_request", 0)

        # Calculate idle capacity (subscription allowance not used)
        sub = self._get_subscription(provider)
        idle = 0
        if sub:
            expected_tokens = sub.monthly_token_allowance * days / 30
            idle = max(0, int(expected_tokens) - total_tokens)

        total_waste = redundant + oversized + mismatch + failed + idle
        waste_pct = (total_waste / (total_tokens + idle) * 100) if (total_tokens + idle) > 0 else 0

        # Generate suggestions
        suggestions = []
        if idle > total_tokens * 0.2:
            suggestions.append(
                f"Schedule batch work to use {idle:,} idle tokens. "
                "Use /batch-orchestrate for overnight processing."
            )
        if redundant > total_tokens * 0.05:
            suggestions.append(
                f"Reduce redundant context ({redundant:,} tokens). "
                "Enable context deduplication in ContextOptimizer."
            )
        if oversized > total_tokens * 0.05:
            suggestions.append(
                f"Optimize prompt sizes ({oversized:,} tokens oversized). "
                "Use concise system prompts and trim unnecessary examples."
            )
        if mismatch > total_tokens * 0.05:
            suggestions.append(
                f"Fix model tier mismatches ({mismatch:,} tokens). "
                "Route simple tasks to Haiku instead of Sonnet/Opus."
            )
        if failed > total_tokens * 0.02:
            suggestions.append(
                f"Reduce failed requests ({failed:,} wasted tokens). "
                "Check for rate limiting, timeouts, or malformed prompts."
            )
        if not suggestions:
            suggestions.append("Token usage is efficient. No major waste detected.")

        return TokenWasteReport(
            period_days=days,
            total_tokens_used=total_tokens,
            redundant_context_tokens=redundant,
            oversized_prompt_tokens=oversized,
            model_mismatch_tokens=mismatch,
            failed_request_tokens=failed,
            idle_capacity_tokens=idle,
            total_waste_tokens=total_waste,
            waste_pct=round(waste_pct, 1),
            suggestions=suggestions,
        )

    def suggest_capacity_fill(
        self, provider: str = "anthropic", max_suggestions: int = 5
    ) -> List[CapacityFillSuggestion]:
        """
        Suggest work to fill unused subscription capacity.

        Analyzes remaining tokens in the billing period and suggests
        batch-eligible work to maximize utilization.

        Args:
            provider: LLM provider
            max_suggestions: Maximum number of suggestions

        Returns:
            List of CapacityFillSuggestion ordered by priority
        """
        status = self.get_utilization_status(provider)
        if not status or status.tokens_at_risk <= 0:
            return []

        available = status.tokens_at_risk
        suggestions = []

        # Prioritized list of batch-eligible work types
        work_types = [
            {
                "type": "security_audit",
                "description": "Run security audit on recent code changes",
                "tokens": 30_000,
                "priority": "high",
                "reason": "Security audits benefit from thorough analysis",
            },
            {
                "type": "code_review",
                "description": "Batch review of uncommitted or recent changes",
                "tokens": 25_000,
                "priority": "high",
                "reason": "Code reviews are non-urgent and batch-efficient",
            },
            {
                "type": "documentation",
                "description": "Generate or update module documentation",
                "tokens": 15_000,
                "priority": "medium",
                "reason": "Documentation improves long-term maintainability",
            },
            {
                "type": "test_coverage",
                "description": "Analyze test coverage gaps and suggest tests",
                "tokens": 20_000,
                "priority": "medium",
                "reason": "Test analysis is compute-intensive and batch-friendly",
            },
            {
                "type": "refactoring_analysis",
                "description": "Identify refactoring opportunities in codebase",
                "tokens": 25_000,
                "priority": "medium",
                "reason": "Refactoring analysis benefits from full-codebase context",
            },
            {
                "type": "dependency_audit",
                "description": "Audit dependencies for updates and vulnerabilities",
                "tokens": 15_000,
                "priority": "low",
                "reason": "Dependency checks are periodic maintenance tasks",
            },
            {
                "type": "performance_analysis",
                "description": "Analyze code for performance bottlenecks",
                "tokens": 25_000,
                "priority": "low",
                "reason": "Performance analysis runs well as background work",
            },
            {
                "type": "todo_resolution",
                "description": "Analyze and prioritize TODO/FIXME comments",
                "tokens": 10_000,
                "priority": "low",
                "reason": "Technical debt assessment uses spare capacity well",
            },
        ]

        # Reorder work types by learned acceptance rates (if available)
        work_types = self._reorder_by_learned_preference(work_types)

        tokens_allocated = 0
        for work in work_types:
            if len(suggestions) >= max_suggestions:
                break
            if tokens_allocated + work["tokens"] > available:
                continue

            suggestions.append(
                CapacityFillSuggestion(
                    task_type=work["type"],
                    description=work["description"],
                    estimated_tokens=work["tokens"],
                    priority=work["priority"],
                    reason=f"{work['reason']}. {status.days_remaining} days left in billing cycle.",
                    batch_eligible=True,
                )
            )
            tokens_allocated += work["tokens"]

        return suggestions

    @staticmethod
    def _reorder_by_learned_preference(work_types: List[Dict]) -> List[Dict]:
        """
        Reorder suggestions using learned acceptance rates from
        the UtilizationLearningEngine. Falls back to default order
        if no learned data is available.
        """
        try:
            from batch.utilization_learning import UtilizationLearningEngine

            engine = UtilizationLearningEngine()
            task_type_list = [w["type"] for w in work_types]
            ranking = engine.get_suggestion_ranking(task_type_list)

            if ranking:
                # Build lookup: task_type -> score
                scores = {task_type: score for task_type, score in ranking}
                # Sort work_types by learned score (highest first)
                return sorted(work_types, key=lambda w: scores.get(w["type"], 0.5), reverse=True)
        except (ImportError, Exception):
            pass  # Learning engine is optional

        return work_types

    def format_utilization_dashboard(self, provider: str = "anthropic") -> str:
        """
        Format a text dashboard showing subscription utilization.

        Args:
            provider: LLM provider

        Returns:
            Formatted dashboard string
        """
        status = self.get_utilization_status(provider)
        if not status:
            return f"No subscription configured for {provider}. Use configure_subscription() to set up."

        # Utilization bar
        bar_width = 30
        filled = int((status.utilization_pct / 100) * bar_width)
        bar = "█" * min(filled, bar_width) + "░" * max(0, bar_width - filled)

        # Status indicator
        status_icons = {
            "underutilized": "🟡",
            "on_track": "🟢",
            "overutilized": "🔴",
        }
        icon = status_icons.get(status.status_level, "⚪")

        lines = [
            f"=== {status.provider.upper()} Subscription Utilization ({status.tier}) ===",
            "",
            f"Billing Period: {status.billing_period_start} → {status.billing_period_end}",
            f"  Day {status.days_elapsed} of {status.days_elapsed + status.days_remaining} ({status.days_remaining} remaining)",
            "",
            f"Token Usage: [{bar}] {status.utilization_pct:.1f}%",
            f"  Used:      {status.tokens_used:>12,} tokens",
            f"  Remaining: {status.tokens_remaining:>12,} tokens",
            f"  Allowance: {status.tokens_allowance:>12,} tokens",
            "",
            f"Daily Rate:  {status.avg_daily_tokens:>12,} tokens/day (current)",
            f"  Required:  {status.required_daily_tokens:>12,} tokens/day (for 100%)",
            "",
            f"Projection:  {status.projected_utilization_pct:.1f}% by end of cycle",
        ]

        if status.tokens_at_risk > 0:
            lines.append(f"  At Risk:   {status.tokens_at_risk:>12,} tokens (will be wasted)")

        lines.extend([
            "",
            f"Cost Efficiency:",
            f"  Nominal:   ${status.cost_per_1k_tokens_nominal:.4f} / 1K tokens",
            f"  Effective: ${status.cost_per_1k_tokens_effective:.4f} / 1K tokens",
            "",
            f"{icon} Status: {status.status_level.upper()}",
            f"  {status.recommendation}",
        ])

        # Add capacity fill suggestions if underutilized
        if status.status_level == "underutilized":
            suggestions = self.suggest_capacity_fill(provider, max_suggestions=3)
            if suggestions:
                lines.extend(["", "Suggested work to fill capacity:"])
                for i, sug in enumerate(suggestions, 1):
                    lines.append(
                        f"  {i}. [{sug.priority.upper():6}] {sug.description} "
                        f"(~{sug.estimated_tokens:,} tokens)"
                    )

        return "\n".join(lines)

    def format_waste_dashboard(self, provider: str = "anthropic", days: int = 30) -> str:
        """
        Format a text dashboard showing token waste analysis.

        Args:
            provider: LLM provider
            days: Analysis period

        Returns:
            Formatted waste analysis string
        """
        report = self.get_waste_report(provider, days)

        lines = [
            f"=== Token Waste Analysis ({days} days) ===",
            "",
            f"Total Tokens Used: {report.total_tokens_used:,}",
            f"Total Waste:       {report.total_waste_tokens:,} ({report.waste_pct:.1f}%)",
            "",
            "Waste Breakdown:",
        ]

        categories = [
            ("Idle Capacity", report.idle_capacity_tokens),
            ("Redundant Context", report.redundant_context_tokens),
            ("Oversized Prompts", report.oversized_prompt_tokens),
            ("Model Mismatches", report.model_mismatch_tokens),
            ("Failed Requests", report.failed_request_tokens),
        ]

        for name, tokens in categories:
            if tokens > 0:
                pct = tokens / max(1, report.total_waste_tokens) * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"  {name:20} [{bar}] {tokens:>10,} ({pct:.0f}%)")

        lines.extend(["", "Recommendations:"])
        for i, sug in enumerate(report.suggestions, 1):
            lines.append(f"  {i}. {sug}")

        return "\n".join(lines)

    def get_all_subscriptions(self) -> List[SubscriptionTier]:
        """Get all configured subscriptions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM subscriptions ORDER BY provider").fetchall()

        return [
            SubscriptionTier(
                provider=row["provider"],
                tier=row["tier"],
                monthly_token_allowance=row["monthly_token_allowance"],
                monthly_cost_usd=row["monthly_cost_usd"],
                billing_reset_day=row["billing_reset_day"],
                input_token_allowance=row["input_token_allowance"],
                output_token_allowance=row["output_token_allowance"],
                rate_limit_rpm=row["rate_limit_rpm"],
                rate_limit_tpm=row["rate_limit_tpm"],
                includes_batch=bool(row["includes_batch"]),
                batch_discount_pct=row["batch_discount_pct"],
            )
            for row in rows
        ]


def check_utilization(provider: str = "anthropic") -> Optional[str]:
    """
    Convenience function for session hook integration.

    Returns utilization warning if subscription is underutilized or
    overutilized, None if on track.
    """
    optimizer = SubscriptionOptimizer()
    status = optimizer.get_utilization_status(provider)

    if not status:
        return None

    if status.status_level == "on_track":
        return None

    return optimizer.format_utilization_dashboard(provider)


if __name__ == "__main__":
    # Demo: Show subscription optimization
    optimizer = SubscriptionOptimizer()

    print("Subscription Token Utilization Optimizer")
    print("=" * 60)

    # Configure a sample subscription
    optimizer.configure_subscription(
        provider="anthropic",
        tier="pro",
        monthly_token_allowance=5_000_000,
        monthly_cost_usd=20.0,
        billing_reset_day=1,
    )

    # Record some sample usage
    for i in range(10):
        optimizer.record_usage(
            provider="anthropic",
            tokens_input=5000,
            tokens_output=2000,
            is_batch=(i % 3 == 0),
            model_tier="sonnet",
        )

    # Show dashboards
    print("\n" + optimizer.format_utilization_dashboard())
    print("\n" + optimizer.format_waste_dashboard())

    # Show capacity fill suggestions
    suggestions = optimizer.suggest_capacity_fill()
    if suggestions:
        print("\nCapacity Fill Suggestions:")
        for sug in suggestions:
            print(f"  - [{sug.priority}] {sug.description} (~{sug.estimated_tokens:,} tokens)")
