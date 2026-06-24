"""
Session Productivity Metrics — The research instrument for Experiment C.

Tracks three numbers per session to answer: does session N+1 get better over time?

Metrics:
    1. time_to_first_useful_output — minutes from session start to first productive action
    2. corrections_needed — count of human corrections during session
    3. context_questions_asked — count of "what is X?" questions (lower = better context)

Data stored in ~/.cortex/session_metrics.jsonl (append-only, one JSON line per event).

Usage:
    metrics = SessionMetrics()
    metrics.session_start("vortex")
    metrics.mark_first_output()          # Call when first useful thing happens
    metrics.record_correction()          # Call when human corrects AI
    metrics.record_context_question()    # Call when AI asks "what is X?"
    metrics.session_end()

    # Analysis
    trend = metrics.get_trend(last_n=20)
    # trend.slope < 0 means compounding (sessions getting more productive)
"""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class SessionRecord:
    """One completed session's metrics."""

    session_id: str
    project: str
    started_at: str
    ended_at: str
    duration_minutes: float
    time_to_first_output_minutes: Optional[float]  # None if never marked
    corrections: int
    context_questions: int


@dataclass
class Trend:
    """Linear regression over session productivity."""

    sessions_analyzed: int
    slope: float  # Negative = improving (good)
    p_value: Optional[float]  # < 0.05 = statistically significant
    first_session_score: float
    last_session_score: float
    improving: bool


class SessionMetrics:
    """Lightweight session productivity tracker."""

    def __init__(self, metrics_file: Optional[Path] = None):
        self.metrics_file = metrics_file or Path.home() / ".cortex" / "session_metrics.jsonl"
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Current session state (in-memory only)
        self._session_id: Optional[str] = None
        self._project: Optional[str] = None
        self._start_time: Optional[float] = None
        self._first_output_time: Optional[float] = None
        self._corrections: int = 0
        self._context_questions: int = 0

    def session_start(self, project: str) -> str:
        """Start tracking a new session. Returns session_id."""
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._project = project
        self._start_time = time.time()
        self._first_output_time = None
        self._corrections = 0
        self._context_questions = 0
        return self._session_id

    def mark_first_output(self) -> Optional[float]:
        """Mark the first useful output. Returns minutes elapsed, or None if no session."""
        if self._start_time is None:
            return None
        if self._first_output_time is None:
            self._first_output_time = time.time()
        elapsed = (self._first_output_time - self._start_time) / 60.0
        return round(elapsed, 2)

    def record_correction(self) -> int:
        """Record a human correction. Returns running count."""
        self._corrections += 1
        return self._corrections

    def record_context_question(self) -> int:
        """Record an AI context question. Returns running count."""
        self._context_questions += 1
        return self._context_questions

    def session_end(self) -> Optional[SessionRecord]:
        """End session and persist metrics. Returns the record."""
        if self._start_time is None or self._project is None:
            return None

        end_time = time.time()
        duration = (end_time - self._start_time) / 60.0

        ttfo = None
        if self._first_output_time is not None:
            ttfo = round((self._first_output_time - self._start_time) / 60.0, 2)

        record = SessionRecord(
            session_id=self._session_id or "",
            project=self._project,
            started_at=datetime.fromtimestamp(self._start_time).isoformat(),
            ended_at=datetime.fromtimestamp(end_time).isoformat(),
            duration_minutes=round(duration, 2),
            time_to_first_output_minutes=ttfo,
            corrections=self._corrections,
            context_questions=self._context_questions,
        )

        # Append to JSONL
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

        # Reset
        self._session_id = None
        self._project = None
        self._start_time = None
        self._first_output_time = None
        self._corrections = 0
        self._context_questions = 0

        return record

    def load_records(self) -> List[SessionRecord]:
        """Load all session records from disk."""
        if not self.metrics_file.exists():
            return []

        records = []
        for line in self.metrics_file.read_text().strip().split("\n"):
            if line:
                try:
                    data = json.loads(line)
                    records.append(SessionRecord(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        return records

    def get_trend(self, last_n: int = 20) -> Optional[Trend]:
        """Compute productivity trend over last N sessions.

        Uses a composite score: lower = more productive.
        Score = time_to_first_output + (corrections * 2) + (context_questions * 1)

        Returns None if fewer than 3 sessions.
        """
        records = self.load_records()[-last_n:]

        # Filter to records with time_to_first_output
        scored = []
        for r in records:
            if r.time_to_first_output_minutes is not None:
                score = (
                    r.time_to_first_output_minutes + (r.corrections * 2) + (r.context_questions * 1)
                )
                scored.append(score)

        if len(scored) < 3:
            return None

        # Simple linear regression: y = mx + b
        n = len(scored)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(scored) / n

        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, scored))
        denominator = sum((xi - x_mean) ** 2 for xi in x)

        if denominator == 0:
            return Trend(
                sessions_analyzed=n,
                slope=0.0,
                p_value=None,
                first_session_score=scored[0],
                last_session_score=scored[-1],
                improving=False,
            )

        slope = numerator / denominator

        # p-value via t-statistic (optional, skip if scipy unavailable)
        p_value = None
        try:
            from scipy import stats

            _, p_value = stats.linregress(x, scored)[3:5]
            p_value = p_value
        except ImportError:
            # Rough approximation: if |slope| > std/sqrt(n), probably significant
            std = (sum((y - y_mean) ** 2 for y in scored) / (n - 1)) ** 0.5
            if std > 0:
                t_stat = abs(slope) / (std / n**0.5)
                p_value = (
                    0.01
                    if t_stat > 2.5
                    else 0.05
                    if t_stat > 2.0
                    else 0.10
                    if t_stat > 1.5
                    else 0.50
                )

        return Trend(
            sessions_analyzed=n,
            slope=round(slope, 4),
            p_value=round(p_value, 4) if p_value else None,
            first_session_score=round(scored[0], 2),
            last_session_score=round(scored[-1], 2),
            improving=slope < 0,
        )
