#!/usr/bin/env python3
"""
Interactive Budget Enforcer

Tracks daily interactive token usage and enforces budget limits.
When budget is exceeded, routes requests to batch processing.

Key Features:
- Daily token budget tracking (100K default)
- Warning at 80% usage
- Hard stop at 100% (force batch mode)
- Session-aware tracking
- Integration with routing framework

Usage:
    from budget_enforcer import BudgetEnforcer

    enforcer = BudgetEnforcer()

    # Check before processing
    status = enforcer.check_budget()
    if status.over_budget:
        print("Must use batch processing")
    elif status.warning:
        print(f"Warning: {status.usage_pct}% of budget used")

    # Record usage after processing
    enforcer.record_usage(tokens_used=5000)
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


@dataclass
class BudgetStatus:
    """Current budget status"""

    date: str
    tokens_used: int
    tokens_remaining: int
    daily_budget: int
    usage_pct: float
    warning: bool
    over_budget: bool
    sessions_today: int
    avg_tokens_per_session: float


@dataclass
class BudgetConfig:
    """Budget enforcer configuration"""

    # Token limits
    daily_budget_tokens: int = 100_000  # ~6-8 hours of work
    warning_threshold_pct: float = 0.80

    # Rolling average for recommendations
    lookback_days: int = 7

    # Paths
    db_path: Path = Path.home() / ".cortex" / "budget" / "usage.db"

    def __post_init__(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


class BudgetEnforcer:
    """
    Enforces daily interactive token budget.

    Tracks usage across sessions and provides budget status
    for routing decisions. When over budget, forces batch mode.
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for usage tracking"""
        with sqlite3.connect(self.config.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                    date TEXT PRIMARY KEY,
                    tokens_used INTEGER DEFAULT 0,
                    sessions INTEGER DEFAULT 0,
                    peak_hour INTEGER,
                    created_at TEXT,
                    updated_at TEXT
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_usage (
                    session_id TEXT PRIMARY KEY,
                    date TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    start_time TEXT,
                    end_time TEXT,
                    requests INTEGER DEFAULT 0,

                    FOREIGN KEY (date) REFERENCES daily_usage(date)
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_date
                ON session_usage(date)
            """
            )

            conn.commit()

    def check_budget(self) -> BudgetStatus:
        """
        Check current budget status.

        Returns:
            BudgetStatus with current usage and warnings
        """
        today = datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(self.config.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get today's usage
            row = conn.execute("SELECT * FROM daily_usage WHERE date = ?", (today,)).fetchone()

            tokens_used = row["tokens_used"] if row else 0
            sessions = row["sessions"] if row else 0

        tokens_remaining = max(0, self.config.daily_budget_tokens - tokens_used)
        usage_pct = (tokens_used / self.config.daily_budget_tokens) * 100

        return BudgetStatus(
            date=today,
            tokens_used=tokens_used,
            tokens_remaining=tokens_remaining,
            daily_budget=self.config.daily_budget_tokens,
            usage_pct=usage_pct,
            warning=usage_pct >= self.config.warning_threshold_pct * 100,
            over_budget=tokens_remaining <= 0,
            sessions_today=sessions,
            avg_tokens_per_session=tokens_used / sessions if sessions > 0 else 0,
        )

    def record_usage(self, tokens_used: int, session_id: Optional[str] = None):
        """
        Record token usage for today.

        Args:
            tokens_used: Number of tokens used in this request
            session_id: Optional session identifier for tracking
        """
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()
        current_hour = datetime.now().hour

        with sqlite3.connect(self.config.db_path) as conn:
            # Update daily usage
            conn.execute(
                """
                INSERT INTO daily_usage (date, tokens_used, sessions, peak_hour, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    tokens_used = tokens_used + ?,
                    sessions = CASE
                        WHEN ? IS NOT NULL THEN sessions + 1
                        ELSE sessions
                    END,
                    peak_hour = CASE
                        WHEN ? > tokens_used THEN ?
                        ELSE peak_hour
                    END,
                    updated_at = ?
            """,
                (
                    today,
                    tokens_used,
                    current_hour,
                    now,
                    now,
                    tokens_used,
                    session_id,
                    tokens_used,
                    current_hour,
                    now,
                ),
            )

            # Update session usage if session_id provided
            if session_id:
                conn.execute(
                    """
                    INSERT INTO session_usage (session_id, date, tokens_used, start_time, requests)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(session_id) DO UPDATE SET
                        tokens_used = tokens_used + ?,
                        requests = requests + 1,
                        end_time = ?
                """,
                    (session_id, today, tokens_used, now, tokens_used, now),
                )

            conn.commit()

    def get_weekly_stats(self) -> dict:
        """
        Get usage statistics for the past week.

        Returns:
            Dict with weekly usage patterns
        """
        cutoff = (datetime.now() - timedelta(days=self.config.lookback_days)).strftime("%Y-%m-%d")

        with sqlite3.connect(self.config.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Daily totals
            rows = conn.execute(
                """
                SELECT date, tokens_used, sessions
                FROM daily_usage
                WHERE date >= ?
                ORDER BY date DESC
            """,
                (cutoff,),
            ).fetchall()

            if not rows:
                return {
                    "days": 0,
                    "total_tokens": 0,
                    "avg_daily_tokens": 0,
                    "avg_sessions_per_day": 0,
                    "peak_day": None,
                    "trend": "unknown",
                }

            total_tokens = sum(r["tokens_used"] for r in rows)
            total_sessions = sum(r["sessions"] for r in rows)
            days = len(rows)

            # Find peak day
            peak_day = max(rows, key=lambda r: r["tokens_used"])

            # Calculate trend (comparing last 3 days to previous 3)
            if days >= 6:
                recent = sum(r["tokens_used"] for r in rows[:3])
                previous = sum(r["tokens_used"] for r in rows[3:6])
                if previous > 0:
                    change_pct = ((recent - previous) / previous) * 100
                    if change_pct > 10:
                        trend = "increasing"
                    elif change_pct < -10:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                else:
                    trend = "new"
            else:
                trend = "insufficient_data"

            return {
                "days": days,
                "total_tokens": total_tokens,
                "avg_daily_tokens": total_tokens // days,
                "avg_sessions_per_day": total_sessions / days,
                "peak_day": {"date": peak_day["date"], "tokens": peak_day["tokens_used"]},
                "trend": trend,
                "budget_utilization_pct": (total_tokens / days / self.config.daily_budget_tokens)
                * 100,
            }

    def suggest_batch_alternatives(self, request_type: str) -> List[str]:
        """
        Suggest batch alternatives for a request type.

        Args:
            request_type: Type of request (review, docs, research, etc.)

        Returns:
            List of batch command suggestions
        """
        suggestions = {
            "review": [
                "/batch-submit review <file>",
                "/batch-orchestrate (includes automated reviews)",
            ],
            "documentation": [
                "/batch-submit docs <module>",
                "Queue for overnight with /batch-orchestrate",
            ],
            "research": [
                '/batch-submit research "<question>"',
                "Add to overnight queue for comprehensive analysis",
            ],
            "security": [
                "/batch-submit security",
                "Full security audit runs overnight via /batch-orchestrate",
            ],
            "refactoring": [
                "/batch-submit refactor <file>",
                "Large refactoring analysis overnight",
            ],
            "performance": ["/batch-submit performance", "Performance analysis runs overnight"],
        }

        return suggestions.get(
            request_type,
            ["/batch-submit <type> <target>", "Check /batch-orchestrate for overnight processing"],
        )

    def format_budget_warning(self) -> Optional[str]:
        """
        Format budget warning message if applicable.

        Returns:
            Warning message string or None if no warning needed
        """
        status = self.check_budget()

        if status.over_budget:
            return (
                "🔴 **Daily Interactive Budget Exhausted**\n"
                f"   Used: {status.tokens_used:,} / {status.daily_budget:,} tokens\n\n"
                "All requests will be routed to batch processing.\n"
                "Results available in tomorrow's /briefing.\n\n"
                "To continue interactively, wait until tomorrow or use:\n"
                "  `/batch-submit <type> <target>` for specific tasks"
            )

        if status.warning:
            remaining_pct = 100 - status.usage_pct
            return (
                f"🟡 **Budget Warning: {status.usage_pct:.0f}% used**\n"
                f"   Remaining: {status.tokens_remaining:,} tokens ({remaining_pct:.0f}%)\n\n"
                "Consider batching non-urgent work:\n"
                "  `/batch-orchestrate` - Queue overnight analysis\n"
                "  `/batch-submit review <file>` - Batch code review"
            )

        return None

    def format_session_start_status(self) -> str:
        """
        Format budget status for session start hook.

        Returns:
            Formatted status string for session context
        """
        status = self.check_budget()
        weekly = self.get_weekly_stats()

        # Budget bar visualization
        bar_width = 20
        filled = int((status.usage_pct / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            "=== Interactive Budget ===",
            f"Today: [{bar}] {status.usage_pct:.0f}%",
            f"  {status.tokens_used:,} / {status.daily_budget:,} tokens",
        ]

        if status.over_budget:
            lines.append("  ⚠️  OVER BUDGET - Batch mode active")
        elif status.warning:
            lines.append(f"  ⚠️  Warning: {status.tokens_remaining:,} remaining")

        # Weekly trend
        if weekly["days"] >= 3:
            trend_icons = {
                "increasing": "📈",
                "decreasing": "📉",
                "stable": "➡️",
                "unknown": "❓",
                "new": "🆕",
                "insufficient_data": "📊",
            }
            icon = trend_icons.get(weekly["trend"], "📊")
            lines.append(
                f"\nWeekly: {icon} {weekly['avg_daily_tokens']:,}/day avg ({weekly['budget_utilization_pct']:.0f}% of budget)"
            )

        # Subscription utilization (if configured)
        try:
            from batch.subscription_optimizer import check_utilization

            utilization_warning = check_utilization()
            if utilization_warning:
                lines.append(f"\n{utilization_warning}")
        except ImportError:
            pass

        return "\n".join(lines)


def check_and_warn() -> Optional[str]:
    """
    Convenience function for session integration.

    Returns warning message if budget is low/exhausted, None otherwise.
    """
    enforcer = BudgetEnforcer()
    return enforcer.format_budget_warning()


def record_session_usage(tokens: int, session_id: str = None):
    """
    Convenience function to record usage.

    Args:
        tokens: Tokens used
        session_id: Optional session identifier
    """
    enforcer = BudgetEnforcer()
    enforcer.record_usage(tokens, session_id)


if __name__ == "__main__":
    # Demo: Show current budget status
    enforcer = BudgetEnforcer()

    print("Budget Enforcer Demo")
    print("=" * 60)

    # Show current status
    status = enforcer.check_budget()
    print("\nCurrent Status:")
    print(f"  Date: {status.date}")
    print(f"  Tokens Used: {status.tokens_used:,}")
    print(f"  Tokens Remaining: {status.tokens_remaining:,}")
    print(f"  Usage: {status.usage_pct:.1f}%")
    print(f"  Warning: {status.warning}")
    print(f"  Over Budget: {status.over_budget}")

    # Show weekly stats
    weekly = enforcer.get_weekly_stats()
    print("\nWeekly Stats:")
    print(f"  Days Tracked: {weekly['days']}")
    print(f"  Avg Daily: {weekly['avg_daily_tokens']:,} tokens")
    print(f"  Trend: {weekly['trend']}")

    # Show session start format
    print("\nSession Start Display:")
    print(enforcer.format_session_start_status())

    # Show warning if applicable
    warning = enforcer.format_budget_warning()
    if warning:
        print(f"\n{warning}")
