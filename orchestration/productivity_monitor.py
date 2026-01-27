"""
Productivity Intelligence & Mentorship System for Cortex.

Monitors user activity, focus patterns, planning behaviors, and provides
mentor-style recommendations to optimize productivity and results.

Design Philosophy:
- Non-intrusive monitoring (passive observation)
- Pattern-based learning (improve over time)
- Actionable recommendations (specific, not generic)
- Privacy-preserving (local data only)
"""

import json
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from .database import OrchestrationDatabase


class ActivityType(str, Enum):
    """Types of activities tracked."""
    GIT_COMMIT = "git_commit"
    FILE_EDIT = "file_edit"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    PHASE_CHANGE = "phase_change"
    CONTEXT_SWITCH = "context_switch"
    COMMAND_RUN = "command_run"
    BREAK_TAKEN = "break_taken"


class FocusState(str, Enum):
    """States of focus during work."""
    DEEP_WORK = "deep_work"          # Focused on single task >25min
    SHALLOW_WORK = "shallow_work"    # Quick tasks, admin, switching
    PLANNING = "planning"             # Investigation, design, thinking
    LEARNING = "learning"             # Research, reading, exploring
    BREAK = "break"                   # Rest, recovery
    INTERRUPTED = "interrupted"       # Context switch before completion


@dataclass
class ActivityEvent:
    """Single activity event."""
    event_id: str
    timestamp: datetime
    activity_type: ActivityType
    project: str
    task_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    duration_minutes: Optional[float] = None
    focus_state: Optional[FocusState] = None


@dataclass
class WorkSession:
    """A continuous work session (until break or context switch)."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    project: str
    task_id: Optional[str] = None
    activities: List[ActivityEvent] = field(default_factory=list)
    context_switches: int = 0
    deep_work_minutes: float = 0
    shallow_work_minutes: float = 0

    @property
    def duration_minutes(self) -> float:
        """Total session duration in minutes."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0

    @property
    def focus_ratio(self) -> float:
        """Ratio of deep work to total work."""
        total = self.deep_work_minutes + self.shallow_work_minutes
        if total == 0:
            return 0
        return self.deep_work_minutes / total


@dataclass
class ProductivityPattern:
    """Detected productivity pattern."""
    pattern_id: str
    pattern_type: str
    description: str
    frequency: int
    confidence: float  # 0.0 to 1.0
    recommendation: str
    detected_at: datetime


@dataclass
class MentorRecommendation:
    """Mentor-style recommendation for improvement."""
    recommendation_id: str
    category: str  # focus, planning, execution, recovery, learning
    priority: str  # immediate, high, medium, low
    title: str
    description: str
    why: str  # Why this matters
    how: str  # How to implement
    evidence: List[str]  # Supporting data points
    created_at: datetime


class ProductivityMonitor:
    """
    Monitors user productivity and provides mentor-style recommendations.

    Tracks:
    - Activity patterns (what, when, how long)
    - Focus states (deep work, shallow work, planning)
    - Context switching frequency
    - Planning vs execution balance
    - Task completion patterns

    Provides:
    - Real-time focus state detection
    - Productivity pattern recognition
    - Personalized recommendations
    - Mentor-style coaching
    """

    def __init__(self, db: OrchestrationDatabase, root_dir: Path):
        self.db = db
        self.root_dir = root_dir
        self.data_dir = Path.home() / ".cortex" / "productivity"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.events_file = self.data_dir / "activity_events.jsonl"
        self.sessions_file = self.data_dir / "work_sessions.jsonl"
        self.patterns_file = self.data_dir / "patterns.jsonl"

        self.current_session: Optional[WorkSession] = None

    # === Activity Tracking ===

    def log_activity(
        self,
        activity_type: ActivityType,
        project: str,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        duration_minutes: Optional[float] = None,
    ) -> ActivityEvent:
        """
        Log a user activity event.

        Args:
            activity_type: Type of activity
            project: Project name
            task_id: Optional task ID
            details: Additional details
            duration_minutes: Duration if known

        Returns:
            ActivityEvent
        """
        import uuid

        event = ActivityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            activity_type=activity_type,
            project=project,
            task_id=task_id,
            details=details or {},
            duration_minutes=duration_minutes,
            focus_state=self._detect_focus_state(activity_type, duration_minutes)
        )

        # Save to JSONL
        with open(self.events_file, 'a') as f:
            f.write(json.dumps(asdict(event), default=str) + '\n')

        # Update current session
        self._update_session(event)

        return event

    def _detect_focus_state(
        self,
        activity_type: ActivityType,
        duration_minutes: Optional[float]
    ) -> FocusState:
        """Detect focus state from activity."""
        if activity_type == ActivityType.BREAK_TAKEN:
            return FocusState.BREAK

        if activity_type in [ActivityType.TASK_START, ActivityType.PHASE_CHANGE]:
            # Check phase to determine state
            return FocusState.PLANNING  # Default

        if activity_type == ActivityType.CONTEXT_SWITCH:
            return FocusState.INTERRUPTED

        # Use duration to determine deep vs shallow work
        if duration_minutes and duration_minutes >= 25:
            return FocusState.DEEP_WORK
        elif duration_minutes and duration_minutes < 25:
            return FocusState.SHALLOW_WORK

        return FocusState.SHALLOW_WORK  # Default

    def _update_session(self, event: ActivityEvent):
        """Update current work session with new event."""
        # Start new session if none exists
        if self.current_session is None:
            import uuid
            self.current_session = WorkSession(
                session_id=str(uuid.uuid4()),
                start_time=event.timestamp,
                project=event.project,
                task_id=event.task_id
            )

        # Check if session should end (context switch or long break)
        if event.activity_type == ActivityType.CONTEXT_SWITCH:
            self._end_session(event.timestamp)
            # Start new session
            import uuid
            self.current_session = WorkSession(
                session_id=str(uuid.uuid4()),
                start_time=event.timestamp,
                project=event.project,
                task_id=event.task_id
            )
            self.current_session.context_switches += 1

        # Add event to session
        if self.current_session:
            self.current_session.activities.append(event)

            # Update work time
            if event.focus_state == FocusState.DEEP_WORK and event.duration_minutes:
                self.current_session.deep_work_minutes += event.duration_minutes
            elif event.focus_state == FocusState.SHALLOW_WORK and event.duration_minutes:
                self.current_session.shallow_work_minutes += event.duration_minutes

    def _end_session(self, end_time: datetime):
        """End current work session."""
        if self.current_session:
            self.current_session.end_time = end_time

            # Save to JSONL
            with open(self.sessions_file, 'a') as f:
                f.write(json.dumps(asdict(self.current_session), default=str) + '\n')

            self.current_session = None

    # === Git Activity Tracking ===

    def track_git_activity(self) -> List[ActivityEvent]:
        """Track recent git commits as activity events."""
        events = []

        try:
            # Get commits from last 24 hours
            result = subprocess.run(
                ["git", "log", "--since=24 hours ago", "--pretty=format:%H|%s|%an|%ar"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.root_dir
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue

                    parts = line.split('|')
                    if len(parts) >= 4:
                        commit_hash, message, author, time_ago = parts

                        # Determine project from commit message or current dir
                        project = self._infer_project_from_commit(message)

                        event = self.log_activity(
                            activity_type=ActivityType.GIT_COMMIT,
                            project=project,
                            details={
                                "commit_hash": commit_hash[:8],
                                "message": message,
                                "time_ago": time_ago
                            }
                        )
                        events.append(event)

        except Exception:
            pass  # Silently fail if git unavailable

        return events

    def _infer_project_from_commit(self, commit_message: str) -> str:
        """Infer project name from commit message."""
        # Look for patterns like "feat(project):" or "fix(project):"
        import re
        match = re.match(r'^\w+\(([^)]+)\):', commit_message)
        if match:
            return match.group(1)

        # Default to "unknown"
        return "unknown"

    # === Pattern Detection ===

    def detect_patterns(self, days: int = 7) -> List[ProductivityPattern]:
        """
        Detect productivity patterns from recent activity.

        Args:
            days: Number of days to analyze

        Returns:
            List of detected patterns
        """
        patterns = []
        events = self._load_recent_events(days)

        if not events:
            return patterns

        # Pattern 1: Context switching frequency
        context_switches = [e for e in events if e.activity_type == ActivityType.CONTEXT_SWITCH]
        if len(context_switches) > 10:  # High switching
            import uuid
            patterns.append(ProductivityPattern(
                pattern_id=str(uuid.uuid4()),
                pattern_type="context_switching",
                description=f"High context switching: {len(context_switches)} switches in {days} days",
                frequency=len(context_switches),
                confidence=0.9,
                recommendation="Consider blocking focus time and batching similar tasks",
                detected_at=datetime.now()
            ))

        # Pattern 2: Planning vs execution balance
        planning_time, execution_time = self._calculate_planning_execution_balance(events)
        ratio = planning_time / (execution_time + 0.1)  # Avoid division by zero

        if ratio < 0.1:  # < 10% planning
            import uuid
            patterns.append(ProductivityPattern(
                pattern_id=str(uuid.uuid4()),
                pattern_type="insufficient_planning",
                description=f"Low planning time: {planning_time:.1f}h vs {execution_time:.1f}h execution",
                frequency=1,
                confidence=0.8,
                recommendation="Spend more time in investigation/planning phases before implementing",
                detected_at=datetime.now()
            ))

        # Pattern 3: Deep work sessions
        sessions = self._load_recent_sessions(days)
        deep_work_sessions = [s for s in sessions if s.focus_ratio > 0.7]

        if len(deep_work_sessions) < 2:  # Less than 2 deep work sessions per week
            import uuid
            patterns.append(ProductivityPattern(
                pattern_id=str(uuid.uuid4()),
                pattern_type="insufficient_deep_work",
                description=f"Only {len(deep_work_sessions)} deep work sessions in {days} days",
                frequency=len(deep_work_sessions),
                confidence=0.85,
                recommendation="Schedule 2-3 deep work sessions per week (90-120 min each)",
                detected_at=datetime.now()
            ))

        # Save patterns
        with open(self.patterns_file, 'a') as f:
            for pattern in patterns:
                f.write(json.dumps(asdict(pattern), default=str) + '\n')

        return patterns

    def _calculate_planning_execution_balance(
        self,
        events: List[ActivityEvent]
    ) -> Tuple[float, float]:
        """Calculate hours spent planning vs executing."""
        planning_minutes = 0
        execution_minutes = 0

        for event in events:
            if not event.duration_minutes:
                continue

            if event.focus_state in [FocusState.PLANNING, FocusState.LEARNING]:
                planning_minutes += event.duration_minutes
            elif event.focus_state in [FocusState.DEEP_WORK, FocusState.SHALLOW_WORK]:
                execution_minutes += event.duration_minutes

        return planning_minutes / 60, execution_minutes / 60

    # === Mentor Recommendations ===

    def generate_recommendations(self) -> List[MentorRecommendation]:
        """
        Generate mentor-style recommendations based on patterns.

        Returns:
            List of actionable recommendations
        """
        recommendations = []
        patterns = self.detect_patterns(days=7)

        for pattern in patterns:
            if pattern.pattern_type == "context_switching":
                recommendations.append(self._recommend_focus_blocks(pattern))
            elif pattern.pattern_type == "insufficient_planning":
                recommendations.append(self._recommend_planning_time(pattern))
            elif pattern.pattern_type == "insufficient_deep_work":
                recommendations.append(self._recommend_deep_work(pattern))

        # Add time-based recommendations
        recommendations.extend(self._recommend_by_time_of_day())

        return recommendations

    def _recommend_focus_blocks(self, pattern: ProductivityPattern) -> MentorRecommendation:
        """Recommend focus blocks to reduce context switching."""
        import uuid
        return MentorRecommendation(
            recommendation_id=str(uuid.uuid4()),
            category="focus",
            priority="high",
            title="Block time for focused work",
            description="You're switching contexts frequently, which reduces deep work effectiveness",
            why="Context switching has a 15-25 minute cognitive cost. Frequent switching prevents entering flow state.",
            how="""
1. Block 2-hour focus sessions in calendar
2. Turn off notifications during blocks
3. Work on ONE project per block
4. Take 15-min breaks between blocks
            """.strip(),
            evidence=[
                f"Detected {pattern.frequency} context switches in last 7 days",
                "Average flow state requires 15-25 minutes of uninterrupted work",
                "Deep work sessions correlate with highest quality output"
            ],
            created_at=datetime.now()
        )

    def _recommend_planning_time(self, pattern: ProductivityPattern) -> MentorRecommendation:
        """Recommend more planning time."""
        import uuid
        return MentorRecommendation(
            recommendation_id=str(uuid.uuid4()),
            category="planning",
            priority="high",
            title="Invest more time in planning phases",
            description="Low planning-to-execution ratio detected - may cause rework",
            why="Every hour of planning saves 3-5 hours of execution. Insufficient planning leads to wrong solutions.",
            how="""
1. Start every task with INVESTIGATING phase
2. Spend 15-30% of estimated time on planning
3. Create written plans before coding
4. Review plan with fresh eyes before executing
            """.strip(),
            evidence=[
                f"Planning ratio: {pattern.description}",
                "PhaseVerifier enforces investigate → plan → build",
                "Planned tasks complete 2-3x faster than unplanned"
            ],
            created_at=datetime.now()
        )

    def _recommend_deep_work(self, pattern: ProductivityPattern) -> MentorRecommendation:
        """Recommend deep work sessions."""
        import uuid
        return MentorRecommendation(
            recommendation_id=str(uuid.uuid4()),
            category="focus",
            priority="immediate",
            title="Schedule deep work sessions",
            description="Insufficient deep work time detected - quality output requires sustained focus",
            why="Deep work produces breakthrough insights and complex problem-solving. Can't fake deep thinking.",
            how="""
1. Schedule 2-3 deep work blocks per week
2. Duration: 90-120 minutes minimum
3. No interruptions: phone off, notifications off
4. One complex problem per session
5. Track: Use timer, note flow state quality
            """.strip(),
            evidence=[
                f"Only {pattern.frequency} deep work sessions in last week",
                "Deep work sessions show 3-5x output quality",
                "Most valuable work happens during deep work"
            ],
            created_at=datetime.now()
        )

    def _recommend_by_time_of_day(self) -> List[MentorRecommendation]:
        """Recommend based on time patterns."""
        recommendations = []

        # Analyze when user is most productive
        events = self._load_recent_events(days=14)
        if not events:
            return recommendations

        # Group by hour of day
        productivity_by_hour = {}
        for event in events:
            hour = event.timestamp.hour
            if event.focus_state == FocusState.DEEP_WORK:
                productivity_by_hour[hour] = productivity_by_hour.get(hour, 0) + 1

        if productivity_by_hour:
            # Find peak hour
            peak_hour = max(productivity_by_hour.items(), key=lambda x: x[1])[0]

            import uuid
            recommendations.append(MentorRecommendation(
                recommendation_id=str(uuid.uuid4()),
                category="execution",
                priority="medium",
                title="Optimize schedule for peak hours",
                description=f"Your peak productivity is around {peak_hour}:00",
                why="Leverage natural energy cycles for maximum output with minimum effort.",
                how=f"""
1. Schedule hardest tasks for {peak_hour-1}:00-{peak_hour+2}:00
2. Use {peak_hour}:00 for deep work, complex problems
3. Reserve other times for meetings, admin, shallow work
4. Protect peak hours fiercely
                """.strip(),
                evidence=[
                    f"Most deep work happens around {peak_hour}:00",
                    f"Productivity peaks at {peak_hour}:00 consistently"
                ],
                created_at=datetime.now()
            ))

        return recommendations

    # === Data Loading ===

    def _load_recent_events(self, days: int) -> List[ActivityEvent]:
        """Load activity events from last N days."""
        if not self.events_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        events = []

        with open(self.events_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)
                event = ActivityEvent(**data)

                if event.timestamp >= cutoff:
                    events.append(event)

        return events

    def _load_recent_sessions(self, days: int) -> List[WorkSession]:
        """Load work sessions from last N days."""
        if not self.sessions_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        sessions = []

        with open(self.sessions_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)
                session = WorkSession(**data)

                if session.start_time >= cutoff:
                    sessions.append(session)

        return sessions

    # === Summary & Reporting ===

    def get_productivity_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get productivity summary for last N days.

        Returns:
            Dictionary with metrics and insights
        """
        events = self._load_recent_events(days)
        sessions = self._load_recent_sessions(days)
        patterns = self.detect_patterns(days)

        # Calculate metrics
        total_work_time = sum(s.duration_minutes for s in sessions)
        deep_work_time = sum(s.deep_work_minutes for s in sessions)
        shallow_work_time = sum(s.shallow_work_minutes for s in sessions)
        context_switches = sum(s.context_switches for s in sessions)

        planning_time, execution_time = self._calculate_planning_execution_balance(events)

        return {
            "period_days": days,
            "total_work_hours": total_work_time / 60,
            "deep_work_hours": deep_work_time / 60,
            "shallow_work_hours": shallow_work_time / 60,
            "deep_work_percentage": (deep_work_time / (total_work_time + 0.1)) * 100,
            "planning_hours": planning_time,
            "execution_hours": execution_time,
            "planning_ratio": planning_time / (execution_time + 0.1),
            "context_switches": context_switches,
            "work_sessions": len(sessions),
            "avg_session_duration_minutes": total_work_time / len(sessions) if sessions else 0,
            "patterns_detected": len(patterns),
            "patterns": [p.description for p in patterns],
        }


def format_mentor_recommendation(rec: MentorRecommendation) -> str:
    """Format recommendation for display."""
    priority_icon = {
        "immediate": "🔴",
        "high": "🟡",
        "medium": "🔵",
        "low": "⚪"
    }.get(rec.priority, "")

    return f"""
{priority_icon} {rec.title.upper()}
Category: {rec.category.title()} | Priority: {rec.priority.upper()}

{rec.description}

WHY THIS MATTERS:
{rec.why}

HOW TO IMPLEMENT:
{rec.how}

EVIDENCE:
{chr(10).join(f'  • {e}' for e in rec.evidence)}
    """.strip()
