#!/usr/bin/env python3
"""
Temporal Horizon Router

Vortex Principle: Different models for different prediction durations.

In Vortex, short-term forecasts (1-3 hours) use fundamentally different
models than long-term forecasts (7+ days). The models that are best at
"right now" predictions are often worst at strategic predictions, and
vice versa.

Cortex applies this by recognizing that decisions have temporal scopes:

    IMMEDIATE  (< 1 session)  → Optimize for speed + cost
                                 Haiku for classification, Sonnet for execution
                                 Full context not needed, pattern-match routing

    SESSION    (1 session)    → Optimize for quality + context
                                 Sonnet for most work, Opus for complex
                                 Full project context, memory retrieval

    STRATEGIC  (multi-session) → Optimize for learning + compounding
                                 Opus for analysis, calibration-weighted decisions
                                 Portfolio-wide context, cross-project patterns

The router classifies temporal scope, then adjusts model selection,
context window, and learning strategy accordingly.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TemporalHorizon(str, Enum):
    """The time scope of a decision or task."""

    IMMEDIATE = "immediate"  # < 1 session, fast response needed
    SESSION = "session"  # Within current session, quality matters
    STRATEGIC = "strategic"  # Multi-session, compounding matters


@dataclass
class TemporalProfile:
    """
    Characterizes a task's temporal nature and the optimal strategy.

    This is what the router produces — a complete prescription for
    how to handle this task given its temporal scope.
    """

    horizon: TemporalHorizon
    confidence: float

    # Model strategy
    preferred_model_tier: str  # haiku, sonnet, opus
    model_reasoning: str

    # Context strategy
    context_depth: str  # "minimal", "project", "portfolio"
    context_reasoning: str

    # Learning strategy — how should the outcome feed back?
    learning_weight: float  # 0.0-1.0, how much to weight this outcome in learning
    learning_reasoning: str

    # Timing strategy
    batch_eligible: bool
    urgency: str  # "immediate", "today", "this_cycle"


# ── Classification signals ──

IMMEDIATE_SIGNALS = {
    "keywords": [
        "fix this", "what is", "explain", "quick", "help",
        "error", "broken", "crash", "failing", "debug",
        "typo", "rename", "format",
    ],
    "task_types": [
        "quick_qa", "classification", "debugging", "formatting",
    ],
    "max_files": 3,
    "max_tokens": 10_000,
}

SESSION_SIGNALS = {
    "keywords": [
        "implement", "add feature", "refactor", "write tests",
        "code review", "fix bug", "update", "migrate",
    ],
    "task_types": [
        "implementation", "bug_fix", "refactoring", "code_review",
        "test_generation",
    ],
    "max_files": 20,
    "max_tokens": 100_000,
}

STRATEGIC_SIGNALS = {
    "keywords": [
        "architecture", "redesign", "strategy", "roadmap", "plan",
        "audit all", "analyze codebase", "portfolio", "cross-project",
        "long-term", "technical debt", "migration plan",
    ],
    "task_types": [
        "architecture", "security_audit", "planning", "research",
        "dependency_audit", "performance_analysis",
    ],
}


class TemporalHorizonRouter:
    """
    Routes tasks to the right model/context/learning strategy
    based on their temporal horizon.

    Key insight from Vortex: the best model for "right now" is
    often the wrong model for "over the next month." Cortex
    respects this by never using one-size-fits-all.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "ensemble" / "temporal.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS temporal_classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    task_type TEXT,
                    horizon TEXT,
                    confidence REAL,
                    preferred_model TEXT,
                    outcome TEXT DEFAULT 'pending',
                    actual_horizon TEXT DEFAULT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS horizon_performance (
                    horizon TEXT,
                    model_tier TEXT,
                    total INTEGER DEFAULT 0,
                    successes INTEGER DEFAULT 0,
                    avg_tokens REAL DEFAULT 0,
                    PRIMARY KEY (horizon, model_tier)
                )
            """
            )
            conn.commit()

    def classify(self, task_context: Dict[str, Any]) -> TemporalProfile:
        """
        Classify a task's temporal horizon and generate a full strategy.

        Args:
            task_context: Dict with task_type, request_text, token_estimate,
                         file_count, active_signals, etc.

        Returns:
            TemporalProfile with model/context/learning strategy
        """
        horizon, confidence = self._detect_horizon(task_context)
        profile = self._build_profile(horizon, confidence, task_context)

        # Adjust based on learned performance
        profile = self._apply_learned_adjustments(profile)

        # Record for learning
        self._record_classification(task_context, profile)

        return profile

    def _detect_horizon(self, ctx: Dict) -> tuple:
        """Classify temporal horizon from task signals."""
        request = ctx.get("request_text", "").lower()
        task_type = ctx.get("task_type", "")
        token_estimate = ctx.get("token_estimate", 5000)
        file_count = ctx.get("file_count", 1)

        scores = {
            TemporalHorizon.IMMEDIATE: 0.0,
            TemporalHorizon.SESSION: 0.0,
            TemporalHorizon.STRATEGIC: 0.0,
        }

        # Keyword signals
        for kw in IMMEDIATE_SIGNALS["keywords"]:
            if kw in request:
                scores[TemporalHorizon.IMMEDIATE] += 0.2
        for kw in SESSION_SIGNALS["keywords"]:
            if kw in request:
                scores[TemporalHorizon.SESSION] += 0.2
        for kw in STRATEGIC_SIGNALS["keywords"]:
            if kw in request:
                scores[TemporalHorizon.STRATEGIC] += 0.25

        # Task type signals
        if task_type in IMMEDIATE_SIGNALS["task_types"]:
            scores[TemporalHorizon.IMMEDIATE] += 0.35
        if task_type in SESSION_SIGNALS["task_types"]:
            scores[TemporalHorizon.SESSION] += 0.35
        if task_type in STRATEGIC_SIGNALS["task_types"]:
            scores[TemporalHorizon.STRATEGIC] += 0.35

        # Scale signals
        if token_estimate > 50_000:
            scores[TemporalHorizon.STRATEGIC] += 0.15
        elif token_estimate < 5_000:
            scores[TemporalHorizon.IMMEDIATE] += 0.15

        if file_count > 10:
            scores[TemporalHorizon.STRATEGIC] += 0.10
        elif file_count <= 2:
            scores[TemporalHorizon.IMMEDIATE] += 0.10

        # Time sensitivity is a hard override — immediate always wins
        if ctx.get("time_sensitive"):
            return TemporalHorizon.IMMEDIATE, 0.90

        # Pick highest
        horizon = max(scores, key=scores.get)
        total = sum(scores.values()) or 1
        confidence = min(0.95, scores[horizon] / total)

        # Default to session if no clear signal
        if max(scores.values()) < 0.1:
            horizon = TemporalHorizon.SESSION
            confidence = 0.50

        return horizon, confidence

    def _build_profile(
        self, horizon: TemporalHorizon, confidence: float, ctx: Dict
    ) -> TemporalProfile:
        """Build a full temporal profile from the detected horizon."""

        if horizon == TemporalHorizon.IMMEDIATE:
            return TemporalProfile(
                horizon=horizon,
                confidence=confidence,
                preferred_model_tier="haiku",
                model_reasoning="Immediate tasks optimize for speed — Haiku responds fastest",
                context_depth="minimal",
                context_reasoning="Only include directly relevant files, skip portfolio context",
                learning_weight=0.3,
                learning_reasoning="Immediate tasks have noisy outcomes — weight lightly in learning",
                batch_eligible=False,
                urgency="immediate",
            )

        elif horizon == TemporalHorizon.SESSION:
            complexity = ctx.get("complexity", "moderate")
            model = "opus" if complexity == "complex" else "sonnet"
            return TemporalProfile(
                horizon=horizon,
                confidence=confidence,
                preferred_model_tier=model,
                model_reasoning=f"Session-scope tasks optimize for quality — {model} for {complexity} work",
                context_depth="project",
                context_reasoning="Full project context needed for coherent session-scope work",
                learning_weight=0.7,
                learning_reasoning="Session outcomes are reliable signal — weight heavily in learning",
                batch_eligible=ctx.get("token_estimate", 0) > 20_000,
                urgency="today",
            )

        else:  # STRATEGIC
            return TemporalProfile(
                horizon=horizon,
                confidence=confidence,
                preferred_model_tier="opus",
                model_reasoning="Strategic tasks need Opus for architectural reasoning and long-horizon planning",
                context_depth="portfolio",
                context_reasoning="Cross-project context needed for strategic decisions",
                learning_weight=1.0,
                learning_reasoning="Strategic outcomes are highest-signal — full weight in learning. These compound.",
                batch_eligible=True,
                urgency="this_cycle",
            )

    def _apply_learned_adjustments(self, profile: TemporalProfile) -> TemporalProfile:
        """Adjust profile based on historical performance per horizon."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT model_tier, total, successes
                FROM horizon_performance
                WHERE horizon = ? AND total >= 5
                ORDER BY CAST(successes AS REAL) / total DESC
            """,
                (profile.horizon.value,),
            ).fetchall()

        if not rows:
            return profile

        # If a different model has >15% better success rate for this horizon,
        # consider overriding (but respect the temporal strategy)
        best = rows[0]
        current_row = next(
            (r for r in rows if r["model_tier"] == profile.preferred_model_tier),
            None,
        )

        if current_row:
            current_rate = current_row["successes"] / max(1, current_row["total"])
            best_rate = best["successes"] / max(1, best["total"])

            if best["model_tier"] != profile.preferred_model_tier and (best_rate - current_rate) > 0.15:
                profile.preferred_model_tier = best["model_tier"]
                profile.model_reasoning = (
                    f"[LEARNED] {best['model_tier']} outperforms for {profile.horizon.value} "
                    f"tasks: {best_rate:.0%} vs {current_rate:.0%} "
                    f"(n={best['total']})"
                )

        return profile

    def record_outcome(
        self,
        horizon: TemporalHorizon,
        model_tier: str,
        success: bool,
        tokens_used: int = 0,
    ):
        """Record a task outcome to improve future temporal routing."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO horizon_performance (horizon, model_tier, total, successes, avg_tokens)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(horizon, model_tier) DO UPDATE SET
                    total = total + 1,
                    successes = successes + ?,
                    avg_tokens = (avg_tokens * total + ?) / (total + 1)
            """,
                (
                    horizon.value,
                    model_tier,
                    int(success),
                    tokens_used,
                    int(success),
                    tokens_used,
                ),
            )
            conn.commit()

    def _record_classification(self, ctx: Dict, profile: TemporalProfile):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO temporal_classifications
                (timestamp, task_type, horizon, confidence, preferred_model)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().isoformat(),
                    ctx.get("task_type", ""),
                    profile.horizon.value,
                    profile.confidence,
                    profile.preferred_model_tier,
                ),
            )
            conn.commit()

    def get_horizon_stats(self) -> str:
        """Show performance stats per temporal horizon."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT horizon, model_tier, total, successes,
                       ROUND(CAST(successes AS REAL) / MAX(1, total) * 100, 1) as success_pct,
                       ROUND(avg_tokens) as avg_tokens
                FROM horizon_performance
                ORDER BY horizon, success_pct DESC
            """
            ).fetchall()

        if not rows:
            return "No temporal horizon data yet."

        lines = ["=== Temporal Horizon Performance ===", ""]

        current_horizon = None
        for row in rows:
            if row["horizon"] != current_horizon:
                current_horizon = row["horizon"]
                lines.append(f"--- {current_horizon.upper()} ---")

            bar = "█" * int(row["success_pct"] / 10) + "░" * (10 - int(row["success_pct"] / 10))
            lines.append(
                f"  [{bar}] {row['success_pct']}% "
                f"{row['model_tier']:8} (n={row['total']}, "
                f"~{int(row['avg_tokens']):,} tokens)"
            )

        lines.append("")
        return "\n".join(lines)
