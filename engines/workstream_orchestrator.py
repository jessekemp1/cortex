"""
Workstream Orchestrator Engine

Manages multi-workstream orchestration for exponential collaboration.
Tracks workstream state, context flow between tools, and orchestration
metrics across 5+ concurrent projects.

Part of the Exponential Collaboration research project.

Architecture:
    WorkstreamOrchestrator
    ├── WorkstreamRegistry    (tracks active workstreams + their state)
    ├── ContextRouter         (routes context between tools/sessions)
    ├── ToilTracker           (measures toil vs creative time)
    └── TrustTracker          (domain-specific trust levels)

Integration:
    - Shell hooks inject workstream context on profile activation
    - Cortex bridge exposes orchestration queries
    - Batch system runs async analysis overnight
    - iTerm Python API scripts use this for window management

Usage:
    orchestrator = WorkstreamOrchestrator()
    orchestrator.activate_workstream("vortex", "build")
    context = orchestrator.get_active_context()
    orchestrator.record_signal(WorkspaceSignal(...))
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class WorkstreamPhase(str, Enum):
    """Phases of work within a project."""

    PLAN = "plan"
    DESIGN = "design"
    BUILD = "build"
    TEST = "test"
    VERIFY = "verify"
    SHIP = "ship"
    CONNECT = "connect"
    RESEARCH = "research"


class SignalSource(str, Enum):
    """Sources of workspace signals."""

    CLAUDE_CODE = "claude_code"
    CLAUDE_CHAT = "claude_chat"
    CURSOR = "cursor"
    COWORKER = "coworker"
    ITERM = "iterm"
    GIT = "git"
    CI_CD = "ci_cd"
    MANUAL = "manual"


class TrustLevel(int, Enum):
    """Trust levels for AI collaboration."""

    VERIFY_EVERYTHING = 0
    SPOT_CHECK = 1
    TRUST_BUT_VERIFY = 2
    AUTONOMOUS_WITH_GUARDRAILS = 3
    FULL_AUTONOMY = 4


class TimeCategory(str, Enum):
    """Categories for time tracking."""

    TOIL = "toil"
    CREATIVE = "creative"
    STRATEGIC = "strategic"
    LEARNING = "learning"


@dataclass
class WorkspaceSignal:
    """A signal from any tool in the workspace."""

    source: SignalSource
    timestamp: datetime
    project: str
    workstream: WorkstreamPhase
    content_type: str  # "idea" | "decision" | "code" | "test" | "insight" | "error"
    content: str
    context: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    signal_id: str = ""

    def __post_init__(self):
        if not self.signal_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S")
            self.signal_id = f"sig_{self.source.value}_{ts}_{hash(self.content) % 10000:04d}"


@dataclass
class WorkstreamState:
    """Current state of a workstream."""

    project: str
    phase: WorkstreamPhase
    active: bool = False
    activated_at: Optional[datetime] = None
    last_signal_at: Optional[datetime] = None
    signal_count: int = 0
    active_task: str = ""
    blockers: List[str] = field(default_factory=list)
    decisions: List[Dict[str, str]] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    trust_overrides: Dict[str, int] = field(default_factory=dict)


@dataclass
class TrustDomain:
    """Trust tracking for a specific domain."""

    domain: str
    level: TrustLevel
    outcomes_total: int = 0
    outcomes_success: int = 0
    outcomes_failure: int = 0
    error_rate: float = 0.0
    streak_current: int = 0
    streak_best: int = 0
    last_outcome_at: Optional[datetime] = None
    level_history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        if self.outcomes_total == 0:
            return 0.0
        return self.outcomes_success / self.outcomes_total

    def record_outcome(self, success: bool) -> Optional[TrustLevel]:
        """Record an outcome and potentially advance trust level.

        Returns new trust level if advanced, None otherwise.
        """
        self.outcomes_total += 1
        self.last_outcome_at = datetime.now()

        if success:
            self.outcomes_success += 1
            self.streak_current += 1
            self.streak_best = max(self.streak_best, self.streak_current)
        else:
            self.outcomes_failure += 1
            self.streak_current = 0

        self.error_rate = self.outcomes_failure / self.outcomes_total

        # Check for level advancement
        new_level = self._evaluate_level()
        if new_level != self.level:
            old_level = self.level
            self.level = new_level
            self.level_history.append(
                {
                    "from": old_level.value,
                    "to": new_level.value,
                    "at": datetime.now().isoformat(),
                    "outcomes": self.outcomes_total,
                    "accuracy": self.accuracy,
                }
            )
            return new_level
        return None

    def _evaluate_level(self) -> TrustLevel:
        """Evaluate what trust level current metrics warrant."""
        if self.outcomes_total < 10:
            return TrustLevel.VERIFY_EVERYTHING

        if self.outcomes_total >= 100 and self.error_rate < 0.03 and self.streak_current >= 20:
            return TrustLevel.FULL_AUTONOMY

        if self.outcomes_total >= 50 and self.error_rate < 0.05:
            return TrustLevel.AUTONOMOUS_WITH_GUARDRAILS

        if self.outcomes_total >= 25 and self.error_rate < 0.10:
            return TrustLevel.TRUST_BUT_VERIFY

        if self.outcomes_total >= 10 and self.error_rate < 0.15:
            return TrustLevel.SPOT_CHECK

        return TrustLevel.VERIFY_EVERYTHING


@dataclass
class ToilEntry:
    """A time entry for toil tracking."""

    timestamp: datetime
    project: str
    phase: WorkstreamPhase
    category: TimeCategory
    duration_minutes: float
    description: str
    automated: bool = False  # Was this toil eliminated by automation?


@dataclass
class AugmentationResult:
    """Result from an idea augmentation cycle."""

    seed: str
    protocol: str
    expanded_ideas: List[Dict[str, Any]]
    cross_insights: List[Dict[str, Any]]
    provenance: List[str]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    outcome: Optional[str] = None  # "implemented" | "deferred" | "rejected"


# Task categorization for toil detection
TASK_CATEGORIES: Dict[str, TimeCategory] = {
    # Toil — repetitive, automatable
    "context_setup": TimeCategory.TOIL,
    "test_iteration": TimeCategory.TOIL,
    "deployment_steps": TimeCategory.TOIL,
    "status_updates": TimeCategory.TOIL,
    "dependency_install": TimeCategory.TOIL,
    "log_reading": TimeCategory.TOIL,
    "config_management": TimeCategory.TOIL,
    # Creative — generates new value
    "architecture": TimeCategory.CREATIVE,
    "ideation": TimeCategory.CREATIVE,
    "problem_solving": TimeCategory.CREATIVE,
    "algorithm_design": TimeCategory.CREATIVE,
    "ui_design": TimeCategory.CREATIVE,
    # Strategic — high-leverage decisions
    "verification": TimeCategory.STRATEGIC,
    "customer_connect": TimeCategory.STRATEGIC,
    "planning": TimeCategory.STRATEGIC,
    "prioritization": TimeCategory.STRATEGIC,
    "review": TimeCategory.STRATEGIC,
    # Learning — investment in capability
    "research": TimeCategory.LEARNING,
    "experimentation": TimeCategory.LEARNING,
    "documentation": TimeCategory.LEARNING,
}


class WorkstreamOrchestrator:
    """
    Central orchestrator for multi-workstream collaboration.

    Manages:
    - Active workstream tracking and context
    - Signal ingestion from all tools
    - Trust level tracking per domain
    - Toil measurement and elimination targeting
    - Cross-project context routing

    Usage:
        orchestrator = WorkstreamOrchestrator()
        orchestrator.activate_workstream("vortex", "build")
        orchestrator.record_signal(signal)
        context = orchestrator.get_active_context()
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "orchestrator.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory state
        self._workstreams: Dict[str, WorkstreamState] = {}
        self._trust_domains: Dict[str, TrustDomain] = {}
        self._signal_buffer: List[WorkspaceSignal] = []
        self._toil_entries: List[ToilEntry] = []

        # Initialize persistence
        self._init_db()
        self._load_trust_domains()

    # ─── Workstream Management ──────────────────────────────────

    def activate_workstream(self, project: str, phase: str) -> WorkstreamState:
        """Activate a workstream, deactivating others.

        Args:
            project: Project name (e.g., "vortex", "cortex", "pupil")
            phase: Work phase (e.g., "build", "test", "plan")

        Returns:
            The activated WorkstreamState
        """
        phase_enum = WorkstreamPhase(phase)
        key = f"{project}:{phase}"

        # Deactivate current
        for ws in self._workstreams.values():
            ws.active = False

        # Activate or create
        if key not in self._workstreams:
            self._workstreams[key] = WorkstreamState(
                project=project,
                phase=phase_enum,
                active=True,
                activated_at=datetime.now(),
            )
        else:
            self._workstreams[key].active = True
            self._workstreams[key].activated_at = datetime.now()

        return self._workstreams[key]

    def get_active_workstream(self) -> Optional[WorkstreamState]:
        """Get the currently active workstream."""
        for ws in self._workstreams.values():
            if ws.active:
                return ws
        return None

    def get_active_context(self) -> Dict[str, Any]:
        """Get rich context for the active workstream.

        Returns context suitable for injection into any tool.
        """
        active = self.get_active_workstream()
        if not active:
            return {"status": "no_active_workstream"}

        # Recent signals for this workstream
        recent_signals = [s for s in self._signal_buffer[-50:] if s.project == active.project]

        # Trust levels for relevant domains
        relevant_trust = {
            domain: {
                "level": td.level.value,
                "level_name": td.level.name,
                "accuracy": round(td.accuracy, 3),
                "streak": td.streak_current,
            }
            for domain, td in self._trust_domains.items()
        }

        # Toil ratio
        toil_stats = self._calculate_toil_ratio(active.project)

        return {
            "workstream": {
                "project": active.project,
                "phase": active.phase.value,
                "active_task": active.active_task,
                "blockers": active.blockers,
                "open_questions": active.open_questions,
                "signal_count": active.signal_count,
            },
            "recent_signals": [
                {
                    "source": s.source.value,
                    "type": s.content_type,
                    "content": s.content[:200],
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in recent_signals[-5:]
            ],
            "trust": relevant_trust,
            "toil": toil_stats,
            "all_workstreams": [
                {
                    "project": ws.project,
                    "phase": ws.phase.value,
                    "active": ws.active,
                    "signals": ws.signal_count,
                }
                for ws in self._workstreams.values()
            ],
        }

    # ─── Signal Processing ──────────────────────────────────────

    def record_signal(self, signal: WorkspaceSignal) -> None:
        """Record a workspace signal from any tool.

        Signals are buffered in memory and periodically flushed to DB.
        """
        self._signal_buffer.append(signal)

        # Update workstream state
        key = f"{signal.project}:{signal.workstream.value}"
        if key in self._workstreams:
            ws = self._workstreams[key]
            ws.last_signal_at = signal.timestamp
            ws.signal_count += 1

        # Persist if buffer is large
        if len(self._signal_buffer) > 100:
            self._flush_signals()

    def get_recent_signals(
        self, project: Optional[str] = None, limit: int = 20
    ) -> List[WorkspaceSignal]:
        """Get recent signals, optionally filtered by project."""
        signals = self._signal_buffer
        if project:
            signals = [s for s in signals if s.project == project]
        return signals[-limit:]

    # ─── Trust Tracking ─────────────────────────────────────────

    def get_trust_level(self, domain: str) -> TrustDomain:
        """Get trust tracking for a domain."""
        if domain not in self._trust_domains:
            self._trust_domains[domain] = TrustDomain(
                domain=domain, level=TrustLevel.VERIFY_EVERYTHING
            )
        return self._trust_domains[domain]

    def record_trust_outcome(self, domain: str, success: bool) -> Optional[TrustLevel]:
        """Record an outcome for trust tracking.

        Returns new trust level if level changed, None otherwise.
        """
        td = self.get_trust_level(domain)
        new_level = td.record_outcome(success)

        # Persist
        self._save_trust_domain(td)

        return new_level

    def get_trust_summary(self) -> Dict[str, Any]:
        """Get summary of trust across all domains."""
        domains = {}
        for name, td in self._trust_domains.items():
            domains[name] = {
                "level": td.level.value,
                "level_name": td.level.name,
                "accuracy": round(td.accuracy, 3),
                "outcomes": td.outcomes_total,
                "streak": td.streak_current,
                "error_rate": round(td.error_rate, 3),
            }

        # Aggregate stats
        if domains:
            avg_level = sum(d["level"] for d in domains.values()) / len(domains)
            avg_accuracy = sum(d["accuracy"] for d in domains.values()) / len(domains)
        else:
            avg_level = 0
            avg_accuracy = 0

        return {
            "domains": domains,
            "aggregate": {
                "avg_trust_level": round(avg_level, 1),
                "avg_accuracy": round(avg_accuracy, 3),
                "total_outcomes": sum(d["outcomes"] for d in domains.values()),
                "domains_tracked": len(domains),
            },
        }

    # ─── Toil Tracking ──────────────────────────────────────────

    def record_time(
        self,
        project: str,
        phase: str,
        task_type: str,
        duration_minutes: float,
        description: str,
        automated: bool = False,
    ) -> ToilEntry:
        """Record a time entry for toil analysis.

        Args:
            project: Project name
            phase: Work phase
            task_type: Task type (must be in TASK_CATEGORIES)
            duration_minutes: Time spent
            description: What was done
            automated: Whether this was automated (toil eliminated)

        Returns:
            The created ToilEntry
        """
        category = TASK_CATEGORIES.get(task_type, TimeCategory.CREATIVE)
        entry = ToilEntry(
            timestamp=datetime.now(),
            project=project,
            phase=WorkstreamPhase(phase),
            category=category,
            duration_minutes=duration_minutes,
            description=description,
            automated=automated,
        )
        self._toil_entries.append(entry)
        self._persist_toil_entry(entry)
        return entry

    def get_toil_report(self, days: int = 7) -> Dict[str, Any]:
        """Get toil analysis for the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [e for e in self._toil_entries if e.timestamp >= cutoff]

        if not recent:
            return {"message": "No time entries in period", "days": days}

        by_category: Dict[str, float] = {}
        by_project: Dict[str, float] = {}
        total_minutes = 0

        for entry in recent:
            cat = entry.category.value
            by_category[cat] = by_category.get(cat, 0) + entry.duration_minutes
            by_project[entry.project] = by_project.get(entry.project, 0) + entry.duration_minutes
            total_minutes += entry.duration_minutes

        toil_minutes = by_category.get("toil", 0)
        creative_minutes = by_category.get("creative", 0)
        strategic_minutes = by_category.get("strategic", 0)
        learning_minutes = by_category.get("learning", 0)

        return {
            "period_days": days,
            "total_minutes": round(total_minutes, 1),
            "total_hours": round(total_minutes / 60, 1),
            "breakdown": {
                "toil": {
                    "minutes": round(toil_minutes, 1),
                    "pct": round(toil_minutes / total_minutes * 100, 1) if total_minutes else 0,
                },
                "creative": {
                    "minutes": round(creative_minutes, 1),
                    "pct": round(creative_minutes / total_minutes * 100, 1) if total_minutes else 0,
                },
                "strategic": {
                    "minutes": round(strategic_minutes, 1),
                    "pct": round(strategic_minutes / total_minutes * 100, 1)
                    if total_minutes
                    else 0,
                },
                "learning": {
                    "minutes": round(learning_minutes, 1),
                    "pct": round(learning_minutes / total_minutes * 100, 1) if total_minutes else 0,
                },
            },
            "by_project": by_project,
            "toil_ratio": round(toil_minutes / total_minutes, 3) if total_minutes else 0,
            "target_toil_ratio": 0.20,  # North star: <20% toil
            "entries": len(recent),
        }

    # ─── Handoff Protocol ────────────────────────────────────────

    def create_handoff(self, project: str, phase: str) -> Dict[str, Any]:
        """Create a structured handoff for session/tool transition.

        Captures everything needed to resume work in a new context.
        """
        ws_key = f"{project}:{phase}"
        ws = self._workstreams.get(ws_key)

        recent_signals = [s for s in self._signal_buffer[-30:] if s.project == project]

        handoff = {
            "schema_version": "2.0",
            "timestamp": datetime.now().isoformat(),
            "project": project,
            "workstream": phase,
            "context": {
                "active_task": ws.active_task if ws else "",
                "blockers": ws.blockers if ws else [],
                "decisions_made": ws.decisions if ws else [],
                "open_questions": ws.open_questions if ws else [],
            },
            "artifacts": {
                "files_modified": ws.artifacts if ws else [],
            },
            "recent_activity": [
                {
                    "source": s.source.value,
                    "type": s.content_type,
                    "content": s.content[:300],
                    "at": s.timestamp.isoformat(),
                }
                for s in recent_signals[-10:]
            ],
            "trust_context": {domain: td.level.name for domain, td in self._trust_domains.items()},
            "continuity": {
                "next_action": "",  # Filled by caller
                "suggested_prompt": "",  # Filled by caller
                "confidence": 0.0,
            },
        }

        return handoff

    def resume_from_handoff(self, handoff: Dict[str, Any]) -> WorkstreamState:
        """Resume a workstream from a handoff document."""
        project = handoff["project"]
        phase = handoff["workstream"]
        ws = self.activate_workstream(project, phase)

        ctx = handoff.get("context", {})
        ws.active_task = ctx.get("active_task", "")
        ws.blockers = ctx.get("blockers", [])
        ws.decisions = ctx.get("decisions_made", [])
        ws.open_questions = ctx.get("open_questions", [])
        ws.artifacts = handoff.get("artifacts", {}).get("files_modified", [])

        return ws

    # ─── Persistence ─────────────────────────────────────────────

    def _init_db(self) -> None:
        """Initialize SQLite database for persistence."""
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                project TEXT NOT NULL,
                workstream TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT DEFAULT '{}',
                confidence REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS trust_domains (
                domain TEXT PRIMARY KEY,
                level INTEGER NOT NULL DEFAULT 0,
                outcomes_total INTEGER DEFAULT 0,
                outcomes_success INTEGER DEFAULT 0,
                outcomes_failure INTEGER DEFAULT 0,
                error_rate REAL DEFAULT 0.0,
                streak_current INTEGER DEFAULT 0,
                streak_best INTEGER DEFAULT 0,
                last_outcome_at TEXT,
                level_history TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS toil_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project TEXT NOT NULL,
                phase TEXT NOT NULL,
                category TEXT NOT NULL,
                duration_minutes REAL NOT NULL,
                description TEXT NOT NULL,
                automated INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project TEXT NOT NULL,
                phase TEXT NOT NULL,
                handoff_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_signals_project ON signals(project);
            CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
            CREATE INDEX IF NOT EXISTS idx_toil_timestamp ON toil_entries(timestamp);
            """
        )
        conn.close()

    def _load_trust_domains(self) -> None:
        """Load trust domains from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT * FROM trust_domains")
        for row in cursor.fetchall():
            domain = row[0]
            self._trust_domains[domain] = TrustDomain(
                domain=domain,
                level=TrustLevel(row[1]),
                outcomes_total=row[2],
                outcomes_success=row[3],
                outcomes_failure=row[4],
                error_rate=row[5],
                streak_current=row[6],
                streak_best=row[7],
                last_outcome_at=datetime.fromisoformat(row[8]) if row[8] else None,
                level_history=json.loads(row[9]) if row[9] else [],
            )
        conn.close()

    def _save_trust_domain(self, td: TrustDomain) -> None:
        """Persist a trust domain to database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO trust_domains
            (domain, level, outcomes_total, outcomes_success, outcomes_failure,
             error_rate, streak_current, streak_best, last_outcome_at, level_history)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                td.domain,
                td.level.value,
                td.outcomes_total,
                td.outcomes_success,
                td.outcomes_failure,
                td.error_rate,
                td.streak_current,
                td.streak_best,
                td.last_outcome_at.isoformat() if td.last_outcome_at else None,
                json.dumps(td.level_history),
            ),
        )
        conn.commit()
        conn.close()

    def _flush_signals(self) -> None:
        """Flush signal buffer to database."""
        if not self._signal_buffer:
            return

        conn = sqlite3.connect(self.db_path)
        for signal in self._signal_buffer:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO signals
                    (signal_id, source, timestamp, project, workstream,
                     content_type, content, context, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal.signal_id,
                        signal.source.value,
                        signal.timestamp.isoformat(),
                        signal.project,
                        signal.workstream.value,
                        signal.content_type,
                        signal.content,
                        json.dumps(signal.context),
                        signal.confidence,
                    ),
                )
            except sqlite3.IntegrityError:
                pass  # Duplicate signal, skip
        conn.commit()
        conn.close()

    def _persist_toil_entry(self, entry: ToilEntry) -> None:
        """Save a toil entry to database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO toil_entries
            (timestamp, project, phase, category, duration_minutes, description, automated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.timestamp.isoformat(),
                entry.project,
                entry.phase.value,
                entry.category.value,
                entry.duration_minutes,
                entry.description,
                1 if entry.automated else 0,
            ),
        )
        conn.commit()
        conn.close()

    def _calculate_toil_ratio(self, project: str) -> Dict[str, Any]:
        """Calculate toil ratio for a project over last 7 days."""
        cutoff = datetime.now() - timedelta(days=7)
        project_entries = [
            e for e in self._toil_entries if e.project == project and e.timestamp >= cutoff
        ]

        total = sum(e.duration_minutes for e in project_entries)
        toil = sum(e.duration_minutes for e in project_entries if e.category == TimeCategory.TOIL)

        return {
            "total_minutes": round(total, 1),
            "toil_minutes": round(toil, 1),
            "toil_ratio": round(toil / total, 3) if total > 0 else 0,
            "target": 0.20,
        }
