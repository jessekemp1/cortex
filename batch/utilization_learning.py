#!/usr/bin/env python3
"""
Utilization Learning Engine

Closes the feedback loop for subscription token optimization.
Observes decisions, learns what works, and adapts routing/model
policies to compound improvements over time.

Design Rule: Every Cortex feature must tie into a learning loop.
This engine is the loop for subscription utilization.

Learning Cycle:
    OBSERVE → Track every routing decision, batch suggestion, waste event
    LEARN   → Analyze patterns: what days/times/task types waste tokens?
              Which suggestions get accepted? What's the optimal daily pace?
    ADAPT   → Generate learned policies (routing thresholds, model preferences,
              batch timing) that override defaults
    ACT     → Feed policies into RequestRouter, ModelRecommender, and
              CapacityFiller so the system improves autonomously

Usage:
    from batch.utilization_learning import UtilizationLearningEngine

    engine = UtilizationLearningEngine()

    # System records a routing decision
    engine.observe_routing_decision(
        request_type="code_review",
        route_chosen="batch",
        tokens_estimated=25000,
        utilization_pct=45.0,
    )

    # User accepts or rejects a capacity-fill suggestion
    engine.observe_suggestion_outcome(
        task_type="security_audit",
        accepted=True,
        tokens_used=28000,
    )

    # System learns and generates new policies
    policies = engine.learn()
    # policies now influence future routing/model/batch decisions
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LearnedPolicy:
    """A policy learned from historical patterns that adjusts system behavior."""

    policy_type: str  # "routing", "model_selection", "batch_timing", "pacing"
    key: str  # Specific policy identifier
    value: Any  # Policy value (threshold, weight, preference, etc.)
    confidence: float  # 0.0-1.0, how confident based on evidence
    evidence_count: int  # Number of observations supporting this
    reasoning: str  # Human-readable explanation
    created_at: str = ""
    expires_at: str = ""  # Policies decay — must be re-confirmed


@dataclass
class RoutingObservation:
    """An observed routing decision and its outcome."""

    timestamp: str
    request_type: str  # "code_review", "research", "implementation", etc.
    route_chosen: str  # "interactive", "batch", "suggest_batch"
    route_accepted: bool  # Did the user accept the routing suggestion?
    tokens_estimated: int
    tokens_actual: int  # 0 if not yet known
    utilization_pct: float  # Subscription utilization at decision time
    day_of_week: int  # 0=Monday, 6=Sunday
    hour_of_day: int
    outcome: str  # "success", "partial", "failed", "pending"


@dataclass
class PacingPolicy:
    """Learned daily pacing strategy for optimal utilization."""

    target_daily_tokens: int  # Learned optimal daily target
    weekday_multiplier: float  # Weekday vs weekend ratio
    weekend_multiplier: float
    ramp_up_factor: float  # How much to increase pace late in cycle
    batch_ratio: float  # Optimal % of tokens via batch
    confidence: float


class UtilizationLearningEngine:
    """
    Learns from utilization patterns to continuously improve token optimization.

    The engine maintains a SQLite database of observations and periodically
    analyzes them to generate learned policies. These policies are consumed
    by RequestRouter, ModelRecommender, and the batch scheduler.
    """

    # Minimum observations before generating a policy
    MIN_SAMPLES = 5
    # Policy expiry — must be re-confirmed by fresh data
    POLICY_TTL_DAYS = 30

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "subscriptions" / "learning.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize learning database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS routing_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    request_type TEXT,
                    route_chosen TEXT,
                    route_accepted INTEGER,
                    tokens_estimated INTEGER,
                    tokens_actual INTEGER DEFAULT 0,
                    utilization_pct REAL,
                    day_of_week INTEGER,
                    hour_of_day INTEGER,
                    outcome TEXT DEFAULT 'pending'
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS suggestion_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    task_type TEXT,
                    accepted INTEGER,
                    tokens_estimated INTEGER,
                    tokens_actual INTEGER DEFAULT 0,
                    utilization_pct_at_suggestion REAL,
                    days_remaining_in_cycle INTEGER,
                    outcome TEXT DEFAULT 'pending'
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_policies (
                    policy_type TEXT,
                    key TEXT,
                    value TEXT,
                    confidence REAL,
                    evidence_count INTEGER,
                    reasoning TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    PRIMARY KEY (policy_type, key)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_pacing (
                    date TEXT PRIMARY KEY,
                    target_tokens INTEGER,
                    actual_tokens INTEGER DEFAULT 0,
                    utilization_at_start REAL,
                    utilization_at_end REAL,
                    batch_tokens INTEGER DEFAULT 0,
                    interactive_tokens INTEGER DEFAULT 0,
                    suggestions_shown INTEGER DEFAULT 0,
                    suggestions_accepted INTEGER DEFAULT 0
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_routing_obs_type
                ON routing_observations(request_type)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_suggestion_obs_type
                ON suggestion_observations(task_type)
            """
            )

            conn.commit()

    # ──────────────────────────────────────────────
    # OBSERVE: Record decisions and outcomes
    # ──────────────────────────────────────────────

    def observe_routing_decision(
        self,
        request_type: str,
        route_chosen: str,
        tokens_estimated: int,
        utilization_pct: float,
        route_accepted: bool = True,
        tokens_actual: int = 0,
        outcome: str = "pending",
    ):
        """Record a routing decision for learning."""
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO routing_observations
                (timestamp, request_type, route_chosen, route_accepted,
                 tokens_estimated, tokens_actual, utilization_pct,
                 day_of_week, hour_of_day, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    now.isoformat(),
                    request_type,
                    route_chosen,
                    int(route_accepted),
                    tokens_estimated,
                    tokens_actual,
                    utilization_pct,
                    now.weekday(),
                    now.hour,
                    outcome,
                ),
            )
            conn.commit()

    def observe_suggestion_outcome(
        self,
        task_type: str,
        accepted: bool,
        tokens_estimated: int = 0,
        tokens_actual: int = 0,
        utilization_pct: float = 0.0,
        days_remaining: int = 0,
        outcome: str = "pending",
    ):
        """Record whether a capacity-fill suggestion was accepted."""
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO suggestion_observations
                (timestamp, task_type, accepted, tokens_estimated, tokens_actual,
                 utilization_pct_at_suggestion, days_remaining_in_cycle, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    now.isoformat(),
                    task_type,
                    int(accepted),
                    tokens_estimated,
                    tokens_actual,
                    utilization_pct,
                    days_remaining,
                    outcome,
                ),
            )
            conn.commit()

    def observe_daily_pacing(
        self,
        target_tokens: int,
        actual_tokens: int,
        utilization_start: float,
        utilization_end: float,
        batch_tokens: int = 0,
        interactive_tokens: int = 0,
        suggestions_shown: int = 0,
        suggestions_accepted: int = 0,
    ):
        """Record end-of-day pacing data."""
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO daily_pacing
                (date, target_tokens, actual_tokens, utilization_at_start,
                 utilization_at_end, batch_tokens, interactive_tokens,
                 suggestions_shown, suggestions_accepted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    actual_tokens = ?,
                    utilization_at_end = ?,
                    batch_tokens = ?,
                    interactive_tokens = ?,
                    suggestions_shown = ?,
                    suggestions_accepted = ?
            """,
                (
                    today,
                    target_tokens,
                    actual_tokens,
                    utilization_start,
                    utilization_end,
                    batch_tokens,
                    interactive_tokens,
                    suggestions_shown,
                    suggestions_accepted,
                    # ON CONFLICT
                    actual_tokens,
                    utilization_end,
                    batch_tokens,
                    interactive_tokens,
                    suggestions_shown,
                    suggestions_accepted,
                ),
            )
            conn.commit()

    # ──────────────────────────────────────────────
    # LEARN: Analyze patterns and generate policies
    # ──────────────────────────────────────────────

    def learn(self, lookback_days: int = 30) -> List[LearnedPolicy]:
        """
        Analyze historical observations and generate learned policies.

        This is the core learning method. It examines routing decisions,
        suggestion outcomes, and pacing data to produce policies that
        will influence future decisions.

        Returns:
            List of learned policies, sorted by confidence
        """
        policies = []

        policies.extend(self._learn_routing_preferences(lookback_days))
        policies.extend(self._learn_suggestion_acceptance(lookback_days))
        policies.extend(self._learn_pacing_strategy(lookback_days))
        policies.extend(self._learn_batch_timing(lookback_days))
        policies.extend(self._learn_waste_reduction(lookback_days))

        # Persist learned policies
        for policy in policies:
            self._save_policy(policy)

        return sorted(policies, key=lambda p: p.confidence, reverse=True)

    def _learn_routing_preferences(self, lookback_days: int) -> List[LearnedPolicy]:
        """Learn which request types users prefer to batch vs. interactive."""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        policies = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT request_type,
                       COUNT(*) as total,
                       SUM(CASE WHEN route_chosen = 'batch' AND route_accepted = 1 THEN 1 ELSE 0 END) as batch_accepted,
                       SUM(CASE WHEN route_chosen = 'batch' AND route_accepted = 0 THEN 1 ELSE 0 END) as batch_rejected,
                       SUM(CASE WHEN route_chosen = 'interactive' THEN 1 ELSE 0 END) as interactive,
                       AVG(tokens_estimated) as avg_tokens,
                       AVG(utilization_pct) as avg_utilization
                FROM routing_observations
                WHERE timestamp >= ?
                GROUP BY request_type
                HAVING COUNT(*) >= ?
            """,
                (cutoff, self.MIN_SAMPLES),
            ).fetchall()

        for row in rows:
            total = row["total"]
            batch_accepted = row["batch_accepted"]
            batch_rejected = row["batch_rejected"]
            batch_rate = batch_accepted / total if total > 0 else 0

            if batch_rate > 0.6:
                # User consistently accepts batch for this type
                policies.append(
                    LearnedPolicy(
                        policy_type="routing",
                        key=f"prefer_batch_{row['request_type']}",
                        value={"route": "suggest_batch", "confidence_boost": 0.2},
                        confidence=min(0.95, 0.6 + (total / 50)),
                        evidence_count=total,
                        reasoning=(
                            f"User accepts batch for '{row['request_type']}' "
                            f"{batch_rate:.0%} of the time (n={total}). "
                            f"Auto-suggesting batch routing."
                        ),
                    )
                )
            elif batch_rejected > batch_accepted and total >= self.MIN_SAMPLES:
                # User consistently rejects batch for this type
                policies.append(
                    LearnedPolicy(
                        policy_type="routing",
                        key=f"prefer_interactive_{row['request_type']}",
                        value={"route": "interactive", "confidence_boost": 0.15},
                        confidence=min(0.90, 0.5 + (total / 50)),
                        evidence_count=total,
                        reasoning=(
                            f"User rejects batch for '{row['request_type']}' — "
                            f"only {batch_rate:.0%} batch acceptance (n={total}). "
                            f"Defaulting to interactive."
                        ),
                    )
                )

        return policies

    def _learn_suggestion_acceptance(self, lookback_days: int) -> List[LearnedPolicy]:
        """Learn which capacity-fill suggestions users actually accept."""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        policies = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task_type,
                       COUNT(*) as total,
                       SUM(accepted) as accepted_count,
                       AVG(utilization_pct_at_suggestion) as avg_util,
                       AVG(days_remaining_in_cycle) as avg_days_left
                FROM suggestion_observations
                WHERE timestamp >= ?
                GROUP BY task_type
                HAVING COUNT(*) >= ?
            """,
                (cutoff, self.MIN_SAMPLES),
            ).fetchall()

        for row in rows:
            accept_rate = row["accepted_count"] / row["total"] if row["total"] > 0 else 0

            policies.append(
                LearnedPolicy(
                    policy_type="suggestion_priority",
                    key=f"accept_rate_{row['task_type']}",
                    value={
                        "accept_rate": round(accept_rate, 2),
                        "priority_boost": round(accept_rate - 0.5, 2),  # Positive = boost, negative = demote
                        "best_util_range": round(row["avg_util"], 1),
                        "best_days_remaining": round(row["avg_days_left"]),
                    },
                    confidence=min(0.90, 0.5 + (row["total"] / 40)),
                    evidence_count=row["total"],
                    reasoning=(
                        f"'{row['task_type']}' suggestions accepted {accept_rate:.0%} "
                        f"(n={row['total']}). Best when utilization ~{row['avg_util']:.0f}% "
                        f"with ~{row['avg_days_left']:.0f} days remaining."
                    ),
                )
            )

        return policies

    def _learn_pacing_strategy(self, lookback_days: int) -> List[LearnedPolicy]:
        """Learn optimal daily token pacing from historical data."""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        policies = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT date, target_tokens, actual_tokens,
                       utilization_at_start, utilization_at_end,
                       batch_tokens, interactive_tokens
                FROM daily_pacing
                WHERE date >= ?
                ORDER BY date
            """,
                (cutoff,),
            ).fetchall()

        if len(rows) < self.MIN_SAMPLES:
            return policies

        # Analyze weekday vs weekend patterns
        weekday_totals = []
        weekend_totals = []
        batch_ratios = []

        for row in rows:
            date = datetime.strptime(row["date"], "%Y-%m-%d")
            actual = row["actual_tokens"]
            if actual <= 0:
                continue

            if date.weekday() < 5:
                weekday_totals.append(actual)
            else:
                weekend_totals.append(actual)

            total = row["batch_tokens"] + row["interactive_tokens"]
            if total > 0:
                batch_ratios.append(row["batch_tokens"] / total)

        avg_weekday = sum(weekday_totals) / len(weekday_totals) if weekday_totals else 0
        avg_weekend = sum(weekend_totals) / len(weekend_totals) if weekend_totals else 0
        avg_batch_ratio = sum(batch_ratios) / len(batch_ratios) if batch_ratios else 0.25

        # Calculate ideal daily target
        avg_overall = sum(r["actual_tokens"] for r in rows if r["actual_tokens"] > 0)
        days_with_data = sum(1 for r in rows if r["actual_tokens"] > 0)
        avg_daily = avg_overall / days_with_data if days_with_data > 0 else 0

        # Calculate how much to ramp up late in billing cycle
        late_cycle = [r for r in rows if r["utilization_at_start"] and r["utilization_at_start"] < 70]
        early_cycle = [r for r in rows if r["utilization_at_start"] and r["utilization_at_start"] >= 70]
        ramp_up = 1.0
        if late_cycle and early_cycle:
            late_avg = sum(r["actual_tokens"] for r in late_cycle) / len(late_cycle)
            early_avg = sum(r["actual_tokens"] for r in early_cycle) / len(early_cycle)
            if early_avg > 0:
                ramp_up = late_avg / early_avg

        weekday_mult = avg_weekday / avg_daily if avg_daily > 0 else 1.2
        weekend_mult = avg_weekend / avg_daily if avg_daily > 0 else 0.5

        policies.append(
            LearnedPolicy(
                policy_type="pacing",
                key="daily_strategy",
                value={
                    "target_daily_tokens": int(avg_daily),
                    "weekday_multiplier": round(weekday_mult, 2),
                    "weekend_multiplier": round(weekend_mult, 2),
                    "ramp_up_factor": round(max(1.0, ramp_up), 2),
                    "batch_ratio": round(avg_batch_ratio, 2),
                },
                confidence=min(0.90, 0.5 + (days_with_data / 30)),
                evidence_count=days_with_data,
                reasoning=(
                    f"Learned from {days_with_data} days: avg {int(avg_daily):,} tokens/day, "
                    f"weekday {weekday_mult:.1f}x / weekend {weekend_mult:.1f}x, "
                    f"batch ratio {avg_batch_ratio:.0%}, "
                    f"ramp-up {ramp_up:.1f}x when behind pace."
                ),
            )
        )

        return policies

    def _learn_batch_timing(self, lookback_days: int) -> List[LearnedPolicy]:
        """Learn optimal time-of-day and day-of-week for batch submissions."""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        policies = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Batch success by hour
            hour_rows = conn.execute(
                """
                SELECT hour_of_day,
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
                       AVG(tokens_actual) as avg_tokens
                FROM routing_observations
                WHERE timestamp >= ? AND route_chosen = 'batch' AND tokens_actual > 0
                GROUP BY hour_of_day
                HAVING COUNT(*) >= 3
            """,
                (cutoff,),
            ).fetchall()

            # Batch success by day of week
            day_rows = conn.execute(
                """
                SELECT day_of_week,
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes
                FROM routing_observations
                WHERE timestamp >= ? AND route_chosen = 'batch' AND outcome != 'pending'
                GROUP BY day_of_week
                HAVING COUNT(*) >= 3
            """,
                (cutoff,),
            ).fetchall()

        if hour_rows:
            best_hours = sorted(hour_rows, key=lambda r: r["successes"] / max(1, r["total"]), reverse=True)
            top_hours = [r["hour_of_day"] for r in best_hours[:3]]
            total_obs = sum(r["total"] for r in hour_rows)

            policies.append(
                LearnedPolicy(
                    policy_type="batch_timing",
                    key="preferred_hours",
                    value={"hours": top_hours, "avoid_hours": [r["hour_of_day"] for r in best_hours[-2:]]},
                    confidence=min(0.85, 0.5 + (total_obs / 50)),
                    evidence_count=total_obs,
                    reasoning=f"Batch jobs succeed most at hours {top_hours} (n={total_obs}).",
                )
            )

        if day_rows:
            best_days = sorted(day_rows, key=lambda r: r["successes"] / max(1, r["total"]), reverse=True)
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            top_days = [day_names[r["day_of_week"]] for r in best_days[:3]]
            total_obs = sum(r["total"] for r in day_rows)

            policies.append(
                LearnedPolicy(
                    policy_type="batch_timing",
                    key="preferred_days",
                    value={"days": [r["day_of_week"] for r in best_days[:3]]},
                    confidence=min(0.80, 0.4 + (total_obs / 40)),
                    evidence_count=total_obs,
                    reasoning=f"Batch jobs succeed most on {', '.join(top_days)} (n={total_obs}).",
                )
            )

        return policies

    def _learn_waste_reduction(self, lookback_days: int) -> List[LearnedPolicy]:
        """Learn waste patterns and generate reduction policies."""
        policies = []

        try:
            from batch.subscription_optimizer import SubscriptionOptimizer

            optimizer = SubscriptionOptimizer()
            report = optimizer.get_waste_report("anthropic", days=lookback_days)
        except (ImportError, Exception):
            return policies

        if report.total_tokens_used <= 0:
            return policies

        # Learn: if model mismatches are high, policy to downgrade simple tasks
        if report.model_mismatch_tokens > report.total_tokens_used * 0.05:
            policies.append(
                LearnedPolicy(
                    policy_type="model_selection",
                    key="reduce_model_mismatch",
                    value={
                        "action": "downgrade_simple_tasks",
                        "threshold": "simple",
                        "preferred_model": "haiku",
                        "waste_pct": round(
                            report.model_mismatch_tokens / report.total_tokens_used * 100, 1
                        ),
                    },
                    confidence=0.75,
                    evidence_count=report.total_tokens_used,
                    reasoning=(
                        f"Model mismatches waste {report.model_mismatch_tokens:,} tokens "
                        f"({report.model_mismatch_tokens / report.total_tokens_used * 100:.1f}%). "
                        f"Route simple tasks to Haiku to reduce waste."
                    ),
                )
            )

        # Learn: if redundant context is high, enable deduplication
        if report.redundant_context_tokens > report.total_tokens_used * 0.05:
            policies.append(
                LearnedPolicy(
                    policy_type="context_optimization",
                    key="enable_deduplication",
                    value={
                        "action": "enable_context_dedup",
                        "dedup_threshold": 0.8,
                        "waste_pct": round(
                            report.redundant_context_tokens / report.total_tokens_used * 100, 1
                        ),
                    },
                    confidence=0.80,
                    evidence_count=report.total_tokens_used,
                    reasoning=(
                        f"Redundant context wastes {report.redundant_context_tokens:,} tokens "
                        f"({report.redundant_context_tokens / report.total_tokens_used * 100:.1f}%). "
                        f"Enable context deduplication at 0.8 threshold."
                    ),
                )
            )

        # Learn: if idle capacity is dominant waste, increase batch aggressiveness
        if report.idle_capacity_tokens > report.total_waste_tokens * 0.5:
            policies.append(
                LearnedPolicy(
                    policy_type="routing",
                    key="increase_batch_aggressiveness",
                    value={
                        "action": "lower_batch_threshold",
                        "new_token_threshold": 5_000,  # Down from 10K
                        "suggest_at_utilization_below": 70,
                    },
                    confidence=0.70,
                    evidence_count=report.total_tokens_used,
                    reasoning=(
                        f"Idle capacity ({report.idle_capacity_tokens:,} tokens) is the "
                        f"dominant waste source. Lowering batch suggestion threshold to "
                        f"capture more work."
                    ),
                )
            )

        return policies

    def _save_policy(self, policy: LearnedPolicy):
        """Persist a learned policy to the database."""
        now = datetime.now()
        expires = now + timedelta(days=self.POLICY_TTL_DAYS)
        policy.created_at = now.isoformat()
        policy.expires_at = expires.isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO learned_policies
                (policy_type, key, value, confidence, evidence_count,
                 reasoning, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(policy_type, key) DO UPDATE SET
                    value = ?, confidence = ?, evidence_count = ?,
                    reasoning = ?, created_at = ?, expires_at = ?
            """,
                (
                    policy.policy_type,
                    policy.key,
                    json.dumps(policy.value),
                    policy.confidence,
                    policy.evidence_count,
                    policy.reasoning,
                    policy.created_at,
                    policy.expires_at,
                    # ON CONFLICT
                    json.dumps(policy.value),
                    policy.confidence,
                    policy.evidence_count,
                    policy.reasoning,
                    policy.created_at,
                    policy.expires_at,
                ),
            )
            conn.commit()

    # ──────────────────────────────────────────────
    # ACT: Provide policies to decision-makers
    # ──────────────────────────────────────────────

    def get_active_policies(self, policy_type: Optional[str] = None) -> List[LearnedPolicy]:
        """
        Get all active (non-expired) learned policies.

        Args:
            policy_type: Filter by type ("routing", "model_selection",
                         "batch_timing", "pacing", "suggestion_priority",
                         "context_optimization"). None returns all.

        Returns:
            Active policies sorted by confidence
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if policy_type:
                rows = conn.execute(
                    """
                    SELECT * FROM learned_policies
                    WHERE policy_type = ? AND expires_at > ?
                    ORDER BY confidence DESC
                """,
                    (policy_type, now),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM learned_policies
                    WHERE expires_at > ?
                    ORDER BY confidence DESC
                """,
                    (now,),
                ).fetchall()

        return [
            LearnedPolicy(
                policy_type=row["policy_type"],
                key=row["key"],
                value=json.loads(row["value"]),
                confidence=row["confidence"],
                evidence_count=row["evidence_count"],
                reasoning=row["reasoning"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
            )
            for row in rows
        ]

    def get_routing_adjustment(self, request_type: str) -> Optional[Dict[str, Any]]:
        """
        Get learned routing adjustment for a request type.

        Called by RequestRouter to check if learned preferences
        should override default routing logic.

        Args:
            request_type: The type of request being routed

        Returns:
            Dict with routing adjustment or None if no learned preference
        """
        policies = self.get_active_policies("routing")

        for policy in policies:
            if request_type in policy.key:
                return {
                    "preferred_route": policy.value.get("route"),
                    "confidence_boost": policy.value.get("confidence_boost", 0),
                    "reasoning": policy.reasoning,
                    "confidence": policy.confidence,
                }

        # Check batch aggressiveness policy
        for policy in policies:
            if policy.key == "increase_batch_aggressiveness":
                return {
                    "lower_token_threshold": policy.value.get("new_token_threshold", 10_000),
                    "suggest_below_utilization": policy.value.get("suggest_at_utilization_below", 70),
                    "reasoning": policy.reasoning,
                    "confidence": policy.confidence,
                }

        return None

    def get_model_adjustment(self, task_type: str, complexity: str) -> Optional[Dict[str, Any]]:
        """
        Get learned model selection adjustment.

        Called by ContextAwareModelRecommender to check if learned
        waste patterns should influence model choice.

        Args:
            task_type: Type of task
            complexity: Classified complexity

        Returns:
            Dict with model adjustment or None
        """
        policies = self.get_active_policies("model_selection")

        for policy in policies:
            if policy.key == "reduce_model_mismatch":
                if complexity == policy.value.get("threshold", "simple"):
                    return {
                        "preferred_model": policy.value.get("preferred_model", "haiku"),
                        "reasoning": policy.reasoning,
                        "confidence": policy.confidence,
                    }

        return None

    def get_suggestion_ranking(self, task_types: List[str]) -> List[Tuple[str, float]]:
        """
        Rank capacity-fill suggestion types by learned acceptance rates.

        Called by SubscriptionOptimizer.suggest_capacity_fill() to
        prioritize suggestions the user is most likely to accept.

        Args:
            task_types: List of task types to rank

        Returns:
            List of (task_type, score) sorted by score descending
        """
        policies = self.get_active_policies("suggestion_priority")
        scores = {}

        for task_type in task_types:
            scores[task_type] = 0.5  # Default neutral score

            for policy in policies:
                if task_type in policy.key:
                    accept_rate = policy.value.get("accept_rate", 0.5)
                    scores[task_type] = accept_rate

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def get_pacing_target(self) -> Optional[PacingPolicy]:
        """
        Get learned daily pacing target.

        Called at session start to set the day's token budget target
        based on subscription utilization patterns.

        Returns:
            PacingPolicy or None if insufficient data
        """
        policies = self.get_active_policies("pacing")

        for policy in policies:
            if policy.key == "daily_strategy":
                v = policy.value
                return PacingPolicy(
                    target_daily_tokens=v.get("target_daily_tokens", 0),
                    weekday_multiplier=v.get("weekday_multiplier", 1.0),
                    weekend_multiplier=v.get("weekend_multiplier", 0.5),
                    ramp_up_factor=v.get("ramp_up_factor", 1.0),
                    batch_ratio=v.get("batch_ratio", 0.25),
                    confidence=policy.confidence,
                )

        return None

    # ──────────────────────────────────────────────
    # REPORT: Show what the engine has learned
    # ──────────────────────────────────────────────

    def format_learning_report(self) -> str:
        """Format a human-readable report of what the engine has learned."""
        policies = self.get_active_policies()

        if not policies:
            return (
                "=== Utilization Learning Engine ===\n\n"
                "No learned policies yet. The engine needs observations to learn from.\n"
                "Policies will emerge after routing decisions and suggestion outcomes\n"
                "are recorded (minimum 5 observations per pattern)."
            )

        lines = [
            "=== Utilization Learning Engine ===",
            f"Active Policies: {len(policies)}",
            "",
        ]

        # Group by type
        by_type: Dict[str, List[LearnedPolicy]] = {}
        for p in policies:
            by_type.setdefault(p.policy_type, []).append(p)

        type_labels = {
            "routing": "Routing Preferences",
            "model_selection": "Model Selection",
            "suggestion_priority": "Suggestion Ranking",
            "pacing": "Daily Pacing",
            "batch_timing": "Batch Timing",
            "context_optimization": "Context Optimization",
        }

        for ptype, type_policies in by_type.items():
            lines.append(f"--- {type_labels.get(ptype, ptype)} ---")
            for p in type_policies:
                conf_bar = "●" * int(p.confidence * 5) + "○" * (5 - int(p.confidence * 5))
                lines.append(f"  [{conf_bar}] {p.reasoning}")
                lines.append(f"           Evidence: {p.evidence_count} observations")
            lines.append("")

        return "\n".join(lines)
