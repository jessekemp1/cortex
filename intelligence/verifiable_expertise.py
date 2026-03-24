#!/usr/bin/env python3
"""
Verifiable Expertise System

Vortex Principle: Build a verifiable, expert-level co-navigator.

Not a tool that responds to commands, but a collaborator whose expertise
is *provable* through a measurable track record. Trust is earned, not
assumed. Every prediction, recommendation, and decision is:

    1. LOGGED    — with predicted outcome and confidence
    2. VERIFIED  — against actual outcome when observed
    3. SCORED    — using proper scoring rules (Brier, calibration)
    4. SURFACED  — so the user can see exactly where Cortex is
                   an expert and where it's still learning

The system maintains a "credential" per domain (model selection, routing,
context sizing, etc.) that shows:
    - Accuracy: What % of predictions were correct?
    - Calibration: When Cortex says 80% confident, is it right 80% of the time?
    - Track record: Trend over time — improving or degrading?
    - Expertise level: Novice → Competent → Expert → Master

This is what makes Cortex a *partner* rather than a tool. A partner
you can trust because you can verify their competence.
"""

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ExpertiseLevel(str, Enum):
    """Earned expertise levels based on track record."""

    NOVICE = "novice"  # < 10 predictions OR accuracy < 50%
    COMPETENT = "competent"  # 10-50 predictions AND accuracy 50-70%
    EXPERT = "expert"  # 50+ predictions AND accuracy 70-85%
    MASTER = "master"  # 100+ predictions AND accuracy > 85% AND calibrated


class Domain(str, Enum):
    """Domains where Cortex can develop verifiable expertise."""

    MODEL_SELECTION = "model_selection"
    ROUTING = "routing"
    CONTEXT_SIZING = "context_sizing"
    PRIORITY_ASSESSMENT = "priority_assessment"
    COST_ESTIMATION = "cost_estimation"
    TIME_ESTIMATION = "time_estimation"
    COMPLEXITY_CLASSIFICATION = "complexity_classification"


@dataclass
class Prediction:
    """A recorded prediction with its confidence and eventual outcome."""

    id: int
    domain: str
    predicted_value: str
    confidence: float  # 0.0-1.0, Cortex's stated confidence
    task_context_summary: str  # Brief description for audit trail
    timestamp: str
    actual_value: Optional[str] = None  # Filled in when outcome observed
    was_correct: Optional[bool] = None
    resolved_at: Optional[str] = None


@dataclass
class DomainCredential:
    """Cortex's earned credential in a specific domain."""

    domain: Domain
    level: ExpertiseLevel
    accuracy: float  # Overall accuracy
    calibration_error: float  # Mean absolute calibration error
    brier_score: float  # Brier score (lower = better)
    total_predictions: int
    recent_accuracy: float  # Last 30 days
    trend: str  # "improving", "stable", "degrading"
    confidence_bins: Dict[str, Dict]  # Calibration breakdown


class VerifiableExpertise:
    """
    Tracks Cortex's predictions and verifies them against reality.

    Every time Cortex makes a decision (model choice, routing, priority),
    this system records what Cortex predicted and how confident it was.
    When the outcome is observed, it scores the prediction.

    Over time, this builds a provable track record that shows exactly
    where Cortex is trustworthy and where it needs more learning.
    """

    # Calibration bins: group predictions by confidence level
    CALIBRATION_BINS = [
        (0.0, 0.2, "very_low"),
        (0.2, 0.4, "low"),
        (0.4, 0.6, "medium"),
        (0.6, 0.8, "high"),
        (0.8, 1.01, "very_high"),
    ]

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "ensemble" / "expertise.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT,
                    predicted_value TEXT,
                    confidence REAL,
                    task_context_summary TEXT,
                    timestamp TEXT,
                    actual_value TEXT DEFAULT NULL,
                    was_correct INTEGER DEFAULT NULL,
                    resolved_at TEXT DEFAULT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_predictions_domain
                ON predictions(domain)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_predictions_resolved
                ON predictions(was_correct)
            """
            )
            conn.commit()

    # ──────────────────────────────────────────────
    # RECORD: Log predictions as they're made
    # ──────────────────────────────────────────────

    def record_prediction(
        self,
        domain: str,
        predicted_value: str,
        confidence: float,
        task_summary: str = "",
    ) -> int:
        """
        Record a prediction that Cortex is making right now.

        Returns:
            prediction_id for later resolution
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO predictions
                (domain, predicted_value, confidence, task_context_summary, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """,
                (domain, predicted_value, confidence, task_summary, datetime.now().isoformat()),
            )
            conn.commit()
            return cursor.lastrowid

    def resolve_prediction(
        self, prediction_id: int, actual_value: str
    ) -> bool:
        """
        Record the actual outcome for a prediction.

        Returns:
            True if prediction was correct
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT predicted_value FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()

            if not row:
                return False

            was_correct = row["predicted_value"] == actual_value
            conn.execute(
                """
                UPDATE predictions
                SET actual_value = ?, was_correct = ?, resolved_at = ?
                WHERE id = ?
            """,
                (actual_value, int(was_correct), datetime.now().isoformat(), prediction_id),
            )
            conn.commit()
            return was_correct

    def resolve_batch(self, resolutions: List[Tuple[int, str]]):
        """Resolve multiple predictions at once."""
        for pred_id, actual_value in resolutions:
            self.resolve_prediction(pred_id, actual_value)

    # ──────────────────────────────────────────────
    # VERIFY: Score predictions against reality
    # ──────────────────────────────────────────────

    def get_credential(self, domain: str, lookback_days: int = 90) -> DomainCredential:
        """
        Compute Cortex's verified credential in a domain.

        Uses proper scoring rules:
        - Accuracy: % of correct predictions
        - Brier Score: Mean squared error of probabilistic predictions
        - Calibration: When Cortex says X% confident, is it right X% of the time?
        """
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            all_resolved = conn.execute(
                """
                SELECT confidence, was_correct
                FROM predictions
                WHERE domain = ? AND was_correct IS NOT NULL AND timestamp >= ?
                ORDER BY timestamp
            """,
                (domain, cutoff),
            ).fetchall()

            recent_resolved = conn.execute(
                """
                SELECT was_correct
                FROM predictions
                WHERE domain = ? AND was_correct IS NOT NULL
                    AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 30
            """,
                (domain, (datetime.now() - timedelta(days=30)).isoformat()),
            ).fetchall()

        total = len(all_resolved)
        if total == 0:
            return DomainCredential(
                domain=Domain(domain) if domain in Domain.__members__.values() else Domain.MODEL_SELECTION,
                level=ExpertiseLevel.NOVICE,
                accuracy=0.0,
                calibration_error=0.0,
                brier_score=1.0,
                total_predictions=0,
                recent_accuracy=0.0,
                trend="insufficient_data",
                confidence_bins={},
            )

        # Accuracy
        correct = sum(1 for r in all_resolved if r["was_correct"])
        accuracy = correct / total

        # Brier Score: mean of (confidence - outcome)^2
        brier = sum(
            (r["confidence"] - r["was_correct"]) ** 2
            for r in all_resolved
        ) / total

        # Calibration: group by confidence bins
        bins = {}
        for low, high, label in self.CALIBRATION_BINS:
            bin_preds = [
                r for r in all_resolved
                if low <= r["confidence"] < high
            ]
            if bin_preds:
                expected = sum(r["confidence"] for r in bin_preds) / len(bin_preds)
                observed = sum(r["was_correct"] for r in bin_preds) / len(bin_preds)
                bins[label] = {
                    "count": len(bin_preds),
                    "expected_accuracy": round(expected, 3),
                    "observed_accuracy": round(observed, 3),
                    "calibration_gap": round(abs(expected - observed), 3),
                }
            else:
                bins[label] = {"count": 0, "expected_accuracy": 0, "observed_accuracy": 0, "calibration_gap": 0}

        # Mean absolute calibration error
        cal_errors = [b["calibration_gap"] for b in bins.values() if b["count"] > 0]
        calibration_error = sum(cal_errors) / len(cal_errors) if cal_errors else 0

        # Recent accuracy (last 30 days)
        recent_accuracy = (
            sum(r["was_correct"] for r in recent_resolved) / len(recent_resolved)
            if recent_resolved
            else accuracy
        )

        # Trend detection
        if len(recent_resolved) < 5:
            trend = "insufficient_data"
        elif recent_accuracy > accuracy + 0.05:
            trend = "improving"
        elif recent_accuracy < accuracy - 0.05:
            trend = "degrading"
        else:
            trend = "stable"

        # Expertise level
        level = self._compute_level(total, accuracy, calibration_error)

        return DomainCredential(
            domain=Domain(domain) if domain in [d.value for d in Domain] else Domain.MODEL_SELECTION,
            level=level,
            accuracy=round(accuracy, 3),
            calibration_error=round(calibration_error, 3),
            brier_score=round(brier, 4),
            total_predictions=total,
            recent_accuracy=round(recent_accuracy, 3),
            trend=trend,
            confidence_bins=bins,
        )

    @staticmethod
    def _compute_level(
        total: int, accuracy: float, calibration_error: float
    ) -> ExpertiseLevel:
        """Compute expertise level from metrics."""
        if total < 10 or accuracy < 0.50:
            return ExpertiseLevel.NOVICE
        if total < 50 or accuracy < 0.70:
            return ExpertiseLevel.COMPETENT
        if total < 100 or accuracy < 0.85:
            return ExpertiseLevel.EXPERT
        if accuracy >= 0.85 and calibration_error < 0.10:
            return ExpertiseLevel.MASTER
        return ExpertiseLevel.EXPERT

    def get_all_credentials(self) -> List[DomainCredential]:
        """Get credentials across all domains."""
        with sqlite3.connect(self.db_path) as conn:
            domains = conn.execute(
                "SELECT DISTINCT domain FROM predictions WHERE was_correct IS NOT NULL"
            ).fetchall()

        return [self.get_credential(d[0]) for d in domains]

    # ──────────────────────────────────────────────
    # SURFACE: Show the track record
    # ──────────────────────────────────────────────

    def format_expertise_card(self) -> str:
        """
        Format Cortex's expertise card — a verifiable credential
        showing where Cortex is trustworthy and where it's learning.

        This is what makes Cortex a co-navigator, not just a tool.
        """
        credentials = self.get_all_credentials()

        if not credentials:
            return (
                "=== Cortex Expertise Card ===\n\n"
                "No verified predictions yet. Expertise is earned through\n"
                "making predictions and having them verified against reality.\n"
                "Begin using Cortex and credentials will accumulate."
            )

        level_icons = {
            ExpertiseLevel.NOVICE: "○",
            ExpertiseLevel.COMPETENT: "◑",
            ExpertiseLevel.EXPERT: "●",
            ExpertiseLevel.MASTER: "★",
        }

        trend_icons = {
            "improving": "↑",
            "stable": "→",
            "degrading": "↓",
            "insufficient_data": "·",
        }

        lines = [
            "=== Cortex Expertise Card ===",
            "Verifiable track record — trust earned through results",
            "",
        ]

        # Sort by expertise level then accuracy
        level_rank = {ExpertiseLevel.MASTER: 4, ExpertiseLevel.EXPERT: 3,
                      ExpertiseLevel.COMPETENT: 2, ExpertiseLevel.NOVICE: 1}
        credentials.sort(
            key=lambda c: (level_rank.get(c.level, 0), c.accuracy),
            reverse=True,
        )

        for cred in credentials:
            icon = level_icons.get(cred.level, "?")
            trend = trend_icons.get(cred.trend, "?")

            acc_bar = "█" * int(cred.accuracy * 10) + "░" * (10 - int(cred.accuracy * 10))
            domain_label = cred.domain.value.replace("_", " ").title()

            lines.append(
                f"  {icon} {domain_label:25} "
                f"[{acc_bar}] {cred.accuracy:.0%} "
                f"({cred.level.value}) {trend}"
            )
            lines.append(
                f"    Predictions: {cred.total_predictions:>5}  "
                f"Brier: {cred.brier_score:.3f}  "
                f"Calibration: ±{cred.calibration_error:.1%}"
            )

        lines.extend(["", "--- Calibration Detail ---"])

        # Show calibration for the most active domain
        most_active = max(credentials, key=lambda c: c.total_predictions)
        if most_active.confidence_bins:
            lines.append(f"  Domain: {most_active.domain.value}")
            lines.append(f"  {'Confidence':15} {'Expected':>10} {'Observed':>10} {'Gap':>8} {'n':>5}")
            for label, data in most_active.confidence_bins.items():
                if data["count"] > 0:
                    gap_indicator = "✓" if data["calibration_gap"] < 0.10 else "✗"
                    lines.append(
                        f"  {label:15} "
                        f"{data['expected_accuracy']:>9.0%} "
                        f"{data['observed_accuracy']:>9.0%} "
                        f"{data['calibration_gap']:>7.1%} {gap_indicator} "
                        f"{data['count']:>4}"
                    )

        lines.extend([
            "",
            "Legend: ○ Novice  ◑ Competent  ● Expert  ★ Master",
            "        ↑ Improving  → Stable  ↓ Degrading",
        ])

        return "\n".join(lines)

    def format_domain_deep_dive(self, domain: str) -> str:
        """Deep dive into one domain's track record."""
        cred = self.get_credential(domain)

        lines = [
            f"=== {domain.replace('_', ' ').title()} — Deep Dive ===",
            "",
            f"Expertise Level: {cred.level.value.upper()}",
            f"Total Predictions: {cred.total_predictions}",
            f"Overall Accuracy: {cred.accuracy:.1%}",
            f"Recent Accuracy (30d): {cred.recent_accuracy:.1%}",
            f"Trend: {cred.trend}",
            "",
            f"Brier Score: {cred.brier_score:.4f} (lower = better, perfect = 0)",
            f"Calibration Error: ±{cred.calibration_error:.1%}",
            "",
        ]

        # Recent predictions
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            recent = conn.execute(
                """
                SELECT predicted_value, actual_value, confidence, was_correct,
                       task_context_summary, timestamp
                FROM predictions
                WHERE domain = ? AND was_correct IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 10
            """,
                (domain,),
            ).fetchall()

        if recent:
            lines.append("Recent Predictions:")
            for r in recent:
                marker = "✓" if r["was_correct"] else "✗"
                lines.append(
                    f"  {marker} [{r['confidence']:.0%}] "
                    f"Predicted: {r['predicted_value']} "
                    f"Actual: {r['actual_value']}"
                )
                if r["task_context_summary"]:
                    lines.append(f"    └ {r['task_context_summary'][:80]}")

        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # Integration helpers
    # ──────────────────────────────────────────────

    def should_trust(self, domain: str, confidence: float) -> Tuple[bool, str]:
        """
        Should the user trust Cortex's prediction in this domain
        at this confidence level?

        Uses calibration data to answer: "When Cortex says it's X%
        confident in domain Y, how often is it actually right?"

        Returns:
            (should_trust, reasoning)
        """
        cred = self.get_credential(domain)

        if cred.total_predictions < 10:
            return False, (
                f"Insufficient track record in {domain} "
                f"({cred.total_predictions} predictions). "
                f"Not enough data to verify expertise."
            )

        # Find the calibration bin for this confidence level
        for low, high, label in self.CALIBRATION_BINS:
            if low <= confidence < high:
                bin_data = cred.confidence_bins.get(label, {})
                if bin_data.get("count", 0) < 3:
                    return False, (
                        f"Too few predictions at {confidence:.0%} confidence "
                        f"in {domain} to verify."
                    )
                observed = bin_data["observed_accuracy"]
                gap = bin_data["calibration_gap"]

                if gap < 0.10:
                    return True, (
                        f"Cortex is well-calibrated at {confidence:.0%} confidence "
                        f"in {domain}: observed accuracy {observed:.0%} "
                        f"(±{gap:.0%} calibration gap, n={bin_data['count']})"
                    )
                elif observed > confidence:
                    return True, (
                        f"Cortex is actually MORE accurate than claimed: "
                        f"observed {observed:.0%} at stated {confidence:.0%} "
                        f"in {domain} (conservative — can trust)"
                    )
                else:
                    return False, (
                        f"Cortex is overconfident at {confidence:.0%} in {domain}: "
                        f"observed accuracy only {observed:.0%} "
                        f"(gap {gap:.0%}, n={bin_data['count']}). "
                        f"Treat with caution."
                    )

        return False, f"Confidence {confidence:.0%} outside calibration range."
