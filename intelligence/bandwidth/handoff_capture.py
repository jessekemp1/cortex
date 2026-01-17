"""
Session Handoff Capture - Preserve context across AI sessions.

The key insight: Most context loss happens at session boundaries.
By capturing structured handoffs, we can dramatically reduce
"cold start" time in new sessions.

Schema based on: cortex/docs/research/HUMAN_AI_BANDWIDTH.md
"""

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class WorkstreamType(str, Enum):
    """Workstream categories for context routing."""

    PLANNING = "planning"  # Architecture, design, strategy
    BUILDING = "building"  # Implementation, coding
    TESTING = "testing"  # Verification, debugging
    SHIPPING = "shipping"  # Deployment, release
    RESEARCH = "research"  # Exploration, learning


@dataclass
class Decision:
    """A decision made during the session."""

    decision: str
    rationale: str
    confidence: float = 0.8  # How confident in this decision

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SessionHandoff:
    """
    Structured session context for handoff.

    This captures everything needed to resume work in a new session
    without losing momentum or repeating context setup.
    """

    # Core identity
    timestamp: datetime
    session_id: str  # Unique identifier for this session
    project: str  # Primary project being worked on

    # Workstream context
    workstream: WorkstreamType
    active_task: str  # What we were working on
    task_status: str  # "in_progress", "blocked", "completed"

    # Progress
    blockers: List[str] = field(default_factory=list)
    decisions_made: List[Decision] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

    # Artifacts
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    tests_status: Optional[Dict[str, int]] = None  # {passed, failed, skipped}

    # Continuity
    next_action: str = ""
    suggested_prompt: str = ""  # Prompt for next session
    confidence: float = 0.7  # Confidence in next action recommendation

    # Metadata
    duration_minutes: float = 0.0
    model_used: str = ""  # claude-opus-4-5-20251101, etc.
    tool: str = "claude-code"  # claude-code, chat, cursor

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["workstream"] = self.workstream.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionHandoff":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["workstream"] = WorkstreamType(data["workstream"])
        if data.get("decisions_made"):
            data["decisions_made"] = [
                Decision(**d) if isinstance(d, dict) else d for d in data["decisions_made"]
            ]
        return cls(**data)


class HandoffStorage:
    """JSONL storage for session handoffs."""

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".cortex" / "research" / "bandwidth"

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.handoffs_file = self.storage_dir / "sessions.jsonl"

    def save(self, handoff: SessionHandoff) -> None:
        """Save a session handoff."""
        with open(self.handoffs_file, "a") as f:
            f.write(json.dumps(handoff.to_dict()) + "\n")

    def load_recent(self, limit: int = 10, project: Optional[str] = None) -> List[SessionHandoff]:
        """Load recent handoffs, optionally filtered by project."""
        if not self.handoffs_file.exists():
            return []

        handoffs = []
        try:
            with open(self.handoffs_file, "r") as f:
                lines = f.readlines()

            # Read in reverse (most recent first)
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue

                data = json.loads(line)

                # Filter by project if specified
                if project and data.get("project") != project:
                    continue

                handoffs.append(SessionHandoff.from_dict(data))

                if len(handoffs) >= limit:
                    break

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Error loading handoffs: {e}")

        return handoffs

    def get_last_handoff(self, project: Optional[str] = None) -> Optional[SessionHandoff]:
        """Get the most recent handoff."""
        recent = self.load_recent(limit=1, project=project)
        return recent[0] if recent else None


def capture_handoff(
    project: str,
    active_task: str,
    workstream: WorkstreamType = WorkstreamType.BUILDING,
    blockers: Optional[List[str]] = None,
    decisions: Optional[List[Dict[str, str]]] = None,
    open_questions: Optional[List[str]] = None,
    next_action: str = "",
    confidence: float = 0.7,
) -> SessionHandoff:
    """
    Capture a session handoff with auto-detected context.

    This function auto-detects:
    - Files modified in current git working tree
    - Model being used (from env)
    - Session ID from Claude Code session file

    Args:
        project: Project name
        active_task: What you were working on
        workstream: Type of work (planning, building, testing, shipping)
        blockers: List of blockers
        decisions: List of decisions made (each with 'decision' and 'rationale')
        open_questions: Questions that need answers
        next_action: Recommended next action
        confidence: Confidence in next_action (0-1)

    Returns:
        Captured SessionHandoff
    """
    # Auto-detect files modified
    files_modified = _detect_modified_files(project)

    # Auto-detect session ID
    session_id = _get_session_id()

    # Auto-detect model
    model_used = os.environ.get("ANTHROPIC_MODEL", "unknown")

    # Convert decisions to Decision objects
    decision_objs = []
    if decisions:
        for d in decisions:
            if isinstance(d, dict):
                decision_objs.append(
                    Decision(
                        decision=d.get("decision", ""),
                        rationale=d.get("rationale", ""),
                        confidence=d.get("confidence", 0.8),
                    )
                )

    # Create handoff
    handoff = SessionHandoff(
        timestamp=datetime.now(),
        session_id=session_id,
        project=project,
        workstream=workstream,
        active_task=active_task,
        task_status="in_progress",
        blockers=blockers or [],
        decisions_made=decision_objs,
        open_questions=open_questions or [],
        files_modified=files_modified,
        files_created=[],
        next_action=next_action,
        confidence=confidence,
        model_used=model_used,
    )

    # Save to storage
    storage = HandoffStorage()
    storage.save(handoff)

    return handoff


def get_recent_handoffs(limit: int = 10, project: Optional[str] = None) -> List[SessionHandoff]:
    """Get recent session handoffs."""
    storage = HandoffStorage()
    return storage.load_recent(limit=limit, project=project)


def _detect_modified_files(project: str) -> List[str]:
    """Detect files modified in current git working tree."""
    try:
        # Try project-specific path first
        project_path = Path.home() / "Dev" / project
        if not project_path.exists():
            project_path = Path.cwd()

        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return []


def _get_session_id() -> str:
    """Get current Claude Code session ID or generate one."""
    # Check for Claude Code session file
    claude_session_dir = Path.home() / ".claude" / "sessions"

    if claude_session_dir.exists():
        # Get most recent session file
        sessions = sorted(claude_session_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if sessions:
            return sessions[-1].stem

    # Generate a unique session ID
    return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
