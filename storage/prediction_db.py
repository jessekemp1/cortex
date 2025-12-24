"""
Cortex Prediction Database - Unified prediction tracking across all domains

SQLite-based storage for:
- Prediction outcomes (weather, trading, dev)
- Confidence states per domain
- Learning history
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()


class PredictionDB:
    """SQLite database for unified prediction tracking"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Default: ~/.cortex/predictions.db
            db_path = Path.home() / ".cortex" / "predictions.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()

        logger.info("prediction_db_initialized", db_path=str(self.db_path))

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("db_transaction_failed", error=str(e))
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Predictions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,           -- 'weather', 'trading', 'dev'
                    timestamp DATETIME NOT NULL,
                    prediction_type TEXT NOT NULL,  -- 'wind_speed', 'trade_direction', 'task_estimate'
                    predicted_value REAL,
                    actual_value REAL,
                    confidence REAL,
                    outcome_quality REAL,           -- Calculated: how good was prediction
                    metadata TEXT                   -- JSON for additional context
                )
            """)

            # Confidence state per domain
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS confidence_state (
                    domain TEXT PRIMARY KEY,
                    current_confidence REAL NOT NULL,
                    recent_accuracy REAL NOT NULL,
                    prediction_count INTEGER DEFAULT 0,
                    last_updated DATETIME NOT NULL
                )
            """)

            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_domain
                ON predictions(domain, timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_type
                ON predictions(domain, prediction_type, timestamp DESC)
            """)

            logger.debug("db_schema_initialized")

    def log_prediction_outcome(
        self,
        domain: str,
        prediction_type: str,
        predicted_value: float,
        actual_value: float,
        confidence: float,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Log a prediction outcome for learning

        Args:
            domain: 'weather', 'trading', 'dev'
            prediction_type: Specific prediction (e.g., 'wind_speed', 'trade_pnl')
            predicted_value: What was predicted
            actual_value: What actually happened
            confidence: Original confidence in prediction (0-1)
            metadata: Additional context (JSON-serializable dict)

        Returns:
            Prediction ID
        """
        import json

        # Calculate outcome quality (inverse of normalized error)
        error = abs(predicted_value - actual_value)
        normalized_error = error / max(abs(actual_value), 1.0)
        outcome_quality = max(0.0, 1.0 - normalized_error)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictions
                (domain, timestamp, prediction_type, predicted_value,
                 actual_value, confidence, outcome_quality, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    domain,
                    datetime.now().isoformat(),
                    prediction_type,
                    predicted_value,
                    actual_value,
                    confidence,
                    outcome_quality,
                    json.dumps(metadata) if metadata else None,
                ),
            )

            prediction_id = cursor.lastrowid

            # Update confidence state for this domain
            self._update_confidence_state(conn, domain)

            logger.info(
                "prediction_logged",
                domain=domain,
                type=prediction_type,
                outcome_quality=f"{outcome_quality:.2f}",
                prediction_id=prediction_id,
            )

            return prediction_id

    def _update_confidence_state(self, conn: sqlite3.Connection, domain: str):
        """Update confidence state based on recent predictions"""
        cursor = conn.cursor()

        # Get recent predictions (last 20)
        cursor.execute(
            """
            SELECT confidence, outcome_quality
            FROM predictions
            WHERE domain = ?
            ORDER BY timestamp DESC
            LIMIT 20
        """,
            (domain,),
        )

        rows = cursor.fetchall()

        if not rows:
            return

        # Calculate recent accuracy (average outcome quality)
        recent_accuracy = sum(row["outcome_quality"] for row in rows) / len(rows)

        # Calculate calibrated confidence
        # If accuracy is low, reduce confidence; if high, maintain
        avg_confidence = sum(row["confidence"] for row in rows) / len(rows)
        current_confidence = (recent_accuracy + avg_confidence) / 2

        # Get total prediction count
        cursor.execute(
            "SELECT COUNT(*) as count FROM predictions WHERE domain = ?", (domain,)
        )
        prediction_count = cursor.fetchone()["count"]

        # Upsert confidence state
        cursor.execute(
            """
            INSERT OR REPLACE INTO confidence_state
            (domain, current_confidence, recent_accuracy, prediction_count, last_updated)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                domain,
                current_confidence,
                recent_accuracy,
                prediction_count,
                datetime.now().isoformat(),
            ),
        )

        logger.debug(
            "confidence_state_updated",
            domain=domain,
            confidence=f"{current_confidence:.2f}",
            accuracy=f"{recent_accuracy:.2f}",
        )

    def get_confidence_state(self, domain: str) -> Optional[Dict]:
        """
        Get current confidence state for a domain

        Returns:
            Dict with confidence, accuracy, count, or None if no data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM confidence_state WHERE domain = ?", (domain,)
            )
            row = cursor.fetchone()

            if row:
                return {
                    "domain": row["domain"],
                    "current_confidence": row["current_confidence"],
                    "recent_accuracy": row["recent_accuracy"],
                    "prediction_count": row["prediction_count"],
                    "last_updated": row["last_updated"],
                }
            return None

    def get_all_confidence_states(self) -> Dict[str, Dict]:
        """Get confidence states for all domains"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM confidence_state")
            rows = cursor.fetchall()

            states = {}
            for row in rows:
                states[row["domain"]] = {
                    "current_confidence": row["current_confidence"],
                    "recent_accuracy": row["recent_accuracy"],
                    "prediction_count": row["prediction_count"],
                    "last_updated": row["last_updated"],
                }

            return states

    def get_recent_predictions(
        self, domain: str, limit: int = 10, prediction_type: Optional[str] = None
    ) -> List[Dict]:
        """Get recent predictions for a domain"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if prediction_type:
                cursor.execute(
                    """
                    SELECT * FROM predictions
                    WHERE domain = ? AND prediction_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (domain, prediction_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM predictions
                    WHERE domain = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (domain, limit),
                )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_prediction_stats(
        self, domain: str, days: int = 7
    ) -> Dict[str, float]:
        """
        Get prediction statistics for a domain over last N days

        Returns:
            Dict with accuracy, confidence, count, trend
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get predictions from last N days
            cursor.execute(
                """
                SELECT
                    AVG(outcome_quality) as avg_accuracy,
                    AVG(confidence) as avg_confidence,
                    COUNT(*) as count
                FROM predictions
                WHERE domain = ?
                  AND timestamp >= datetime('now', '-' || ? || ' days')
            """,
                (domain, days),
            )

            row = cursor.fetchone()

            if row["count"] == 0:
                return {
                    "avg_accuracy": 0.0,
                    "avg_confidence": 0.0,
                    "count": 0,
                    "trend": "no_data",
                }

            # Calculate trend (compare first half vs second half of period)
            cursor.execute(
                """
                SELECT
                    AVG(outcome_quality) as first_half_accuracy
                FROM predictions
                WHERE domain = ?
                  AND timestamp >= datetime('now', '-' || ? || ' days')
                  AND timestamp < datetime('now', '-' || ? || ' days')
            """,
                (domain, days, days // 2),
            )

            first_half = cursor.fetchone()
            first_half_accuracy = first_half["first_half_accuracy"] or 0.0

            cursor.execute(
                """
                SELECT
                    AVG(outcome_quality) as second_half_accuracy
                FROM predictions
                WHERE domain = ?
                  AND timestamp >= datetime('now', '-' || ? || ' days')
            """,
                (domain, days // 2),
            )

            second_half = cursor.fetchone()
            second_half_accuracy = second_half["second_half_accuracy"] or 0.0

            # Determine trend
            if second_half_accuracy > first_half_accuracy + 0.05:
                trend = "improving"
            elif second_half_accuracy < first_half_accuracy - 0.05:
                trend = "declining"
            else:
                trend = "stable"

            return {
                "avg_accuracy": row["avg_accuracy"],
                "avg_confidence": row["avg_confidence"],
                "count": row["count"],
                "trend": trend,
                "first_half_accuracy": first_half_accuracy,
                "second_half_accuracy": second_half_accuracy,
            }


# Singleton instance
_db_instance = None


def get_prediction_db() -> PredictionDB:
    """Get singleton prediction database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = PredictionDB()
    return _db_instance
