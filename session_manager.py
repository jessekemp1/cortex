# ~/Dev/cortex/session_manager.py

import json
import logging
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import TieredMemory for session-aware memory tracking
try:
    from intelligence.memory.tiered_memory import MemoryItem, TieredMemory

    TIERED_MEMORY_AVAILABLE = True
except ImportError:
    TIERED_MEMORY_AVAILABLE = False
    TieredMemory = None
    MemoryItem = None

logger = logging.getLogger(__name__)

CORTEX_DIR = Path("~/.cortex").expanduser()
SESSION_METRICS_FILE = CORTEX_DIR / "session_metrics.jsonl"


@dataclass
class SessionProductivityMetrics:
    """Productivity metrics for Exponential Collaboration research (Goal 9).

    Research question: Does persistent context make session N+1 measurably
    more productive than session N?
    """

    session_id: str
    session_start: str  # ISO timestamp
    session_end: str  # ISO timestamp
    session_duration_seconds: float
    context_questions_asked: int = 0  # proxy: clarifying "?" interactions
    time_to_first_useful_output: Optional[float] = None  # seconds, if trackable
    delegation_rate: float = 0.0  # fraction of tasks where review_required=False
    corrections_received: int = 0  # correction signals from FeedbackLogger
    outcomes_recorded: int = 0  # outcomes logged this session
    domain: Optional[str] = None  # cortex domain tag (aidev/databricks)
    extra: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """
    Git-based automatic session context generation

    Generates context from:
    - Current git repository
    - Recent commits
    - Active branch
    - Git status (modified files)
    - Recent goals (from commit messages and specs)
    """

    def __init__(self, workspace_root: str = "~/Dev", enable_tiered_memory: bool = True):
        self.workspace_root = Path(workspace_root).expanduser()

        # Initialize tiered memory if available and enabled
        self.tiered_memory: Optional[TieredMemory] = None
        if enable_tiered_memory and TIERED_MEMORY_AVAILABLE:
            try:
                self.tiered_memory = TieredMemory()
                logger.debug("TieredMemory initialized for session tracking")
            except Exception as e:
                logger.warning(f"Failed to initialize TieredMemory: {e}")

    def get_context(self, format: str = "terminal") -> str:
        """
        Get current session context

        Args:
            format: 'terminal' (human-readable) or 'structured' (JSON)
        """
        context = self._build_context()

        if format == "structured":
            return json.dumps(context, indent=2)
        else:
            return self._format_terminal(context)

    def _build_context(self) -> Dict:
        """Build session context from git"""
        current_dir = Path.cwd()

        # Detect current project
        project_info = self._detect_project(current_dir)

        # Get git context if in repo
        git_context = {}
        if project_info["is_git_repo"]:
            git_context = {
                "branch": self._get_current_branch(),
                "recent_commits": self._get_recent_commits(limit=3),
                "status": self._get_git_status(),
                "recent_files": self._get_recently_modified_files(),
            }

        # Extract goals from recent work
        goals = self._extract_goals(git_context)

        # Build context (always fresh - no caching)
        context = {
            "timestamp": datetime.now().isoformat(),
            "current_directory": str(current_dir),
            "project": project_info,
            "git": git_context,
            "goals": goals,
            "focus": self._infer_focus(git_context),
        }

        return context

    def _detect_project(self, path: Path) -> Dict:
        """Detect project from path"""
        # Walk up until we find .git or hit workspace root
        current = path
        while current >= self.workspace_root:
            if (current / ".git").exists():
                return {"name": current.name, "path": str(current), "is_git_repo": True}
            current = current.parent

        return {"name": "unknown", "path": str(path), "is_git_repo": False}

    def _run_git(self, args: List[str], cwd: str = None) -> str:
        """Run git command and return output"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd or Path.cwd(),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_current_branch(self) -> str:
        """Get current git branch"""
        return self._run_git(["branch", "--show-current"])

    def _get_recent_commits(self, limit: int = 3) -> List[Dict]:
        """Get recent commits"""
        log_format = "--pretty=format:%h|%an|%ar|%s"
        output = self._run_git(["log", log_format, f"-{limit}"])

        commits = []
        for line in output.split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "time": parts[2],
                            "message": parts[3],
                        }
                    )
        return commits

    def _get_git_status(self) -> Dict:
        """Get git status summary"""
        status_output = self._run_git(["status", "--porcelain"])

        modified = []
        untracked = []

        for line in status_output.split("\n"):
            if line:
                status = line[:2]
                filepath = line[3:]

                if status == "??":
                    untracked.append(filepath)
                else:
                    modified.append(filepath)

        return {
            "modified": modified,
            "untracked": untracked,
            "is_clean": len(modified) == 0 and len(untracked) == 0,
        }

    def _get_recently_modified_files(self, days: int = 7) -> List[str]:
        """Get files modified in last N days"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        output = self._run_git(
            [
                "log",
                "--since",
                since,
                "--name-only",
                "--pretty=format:",
                "--diff-filter=AM",  # Added or Modified
            ]
        )

        files = set(line for line in output.split("\n") if line)
        return sorted(files)[:10]  # Top 10

    def _extract_goals(self, git_context: Dict) -> List[str]:
        """Extract goals from recent commit messages"""
        goals = []

        if "recent_commits" in git_context:
            for commit in git_context["recent_commits"]:
                msg = commit["message"]

                # Look for goal indicators
                if any(word in msg.lower() for word in ["add", "implement", "build", "create"]):
                    goals.append(f"Continue work on: {msg}")

        return goals[:3]  # Top 3 goals

    def _infer_focus(self, git_context: Dict) -> str:
        """Infer current focus from recent activity"""
        if not git_context:
            return "Unknown"

        # Recent commits indicate focus
        if git_context.get("recent_commits"):
            latest = git_context["recent_commits"][0]["message"]

            # Extract focus from commit message
            if "test" in latest.lower():
                return "Testing"
            elif "fix" in latest.lower() or "bug" in latest.lower():
                return "Bug fixing"
            elif "doc" in latest.lower():
                return "Documentation"
            elif "refactor" in latest.lower():
                return "Refactoring"
            else:
                return "Feature development"

        return "Unknown"

    def _format_terminal(self, context: Dict) -> str:
        """Format context for terminal display"""
        output = []

        output.append("=== Cortex Session Intelligence ===\n")

        # Project
        project = context["project"]
        output.append(f"Project: {project['name']}")
        output.append(f"Path: {project['path']}\n")

        # Git status
        if context["git"]:
            git = context["git"]
            output.append(f"Branch: {git.get('branch', 'unknown')}")
            output.append(f"Focus: {context.get('focus', 'unknown')}\n")

            # Recent work
            if git.get("recent_commits"):
                output.append("Recent commits:")
                for commit in git["recent_commits"][:3]:
                    output.append(f"  [{commit['hash']}] {commit['message']} ({commit['time']})")
                output.append("")

            # Status
            status = git.get("status", {})
            if not status.get("is_clean"):
                output.append(f"Modified files: {len(status.get('modified', []))}")
                output.append(f"Untracked files: {len(status.get('untracked', []))}\n")

        # Goals
        if context.get("goals"):
            output.append("Active goals:")
            for goal in context["goals"]:
                output.append(f"  • {goal}")
            output.append("")

        output.append("===================================")

        return "\n".join(output)

    # --- Tiered Memory Integration ---

    def record_context(
        self,
        content: Dict[str, Any],
        context_type: str = "session_context",
        source: Optional[str] = None,
    ) -> Optional[str]:
        """
        Record context to tiered memory for session-aware tracking.

        Args:
            content: Context content to record
            context_type: Type of context (session_context, recommendation, query, etc.)
            source: Source identifier (file, api, etc.)

        Returns:
            Memory item ID if recorded, None if tiered memory unavailable
        """
        if not self.tiered_memory or not MemoryItem:
            return None

        try:
            item_id = f"{context_type}:{uuid.uuid4().hex[:8]}"
            now = datetime.now()

            item = MemoryItem(
                id=item_id,
                content={"type": context_type, "source": source, "data": content},
                created_at=now,
                last_accessed=now,
                access_count=1,
            )

            self.tiered_memory.record(item)
            logger.debug(f"Recorded context item {item_id} to tiered memory")
            return item_id

        except Exception as e:
            logger.warning(f"Failed to record context: {e}")
            return None

    def update_outcome(self, item_id: str, outcome: str, quality_score: float) -> bool:
        """
        Update outcome for a recorded context item.

        Args:
            item_id: Memory item ID from record_context()
            outcome: Outcome value ("success", "partial", "failed")
            quality_score: Quality score (0.0-1.0)

        Returns:
            True if updated, False if tiered memory unavailable or item not found
        """
        if not self.tiered_memory:
            return False

        try:
            self.tiered_memory.update_outcome(item_id, outcome, quality_score)
            logger.debug(f"Updated outcome for {item_id}: {outcome} (quality={quality_score})")
            return True
        except Exception as e:
            logger.warning(f"Failed to update outcome: {e}")
            return False

    def query_memory(
        self,
        query: str,
        tiers: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Query tiered memory for relevant context.

        Args:
            query: Search query
            tiers: List of tiers to search (default: all)
            limit: Maximum results

        Returns:
            List of matching items with scores and tier info
        """
        if not self.tiered_memory:
            return []

        try:
            results = self.tiered_memory.query(query, tiers=tiers, limit=limit)
            return [
                {
                    "item": item.to_dict() if hasattr(item, "to_dict") else item,
                    "score": score,
                    "tier": tier,
                }
                for item, score, tier in results
            ]
        except Exception as e:
            logger.warning(f"Failed to query memory: {e}")
            return []

    def end_session(self) -> Dict[str, Any]:
        """
        End session: promote frequently accessed items, cleanup expired.

        Call this when session ends (e.g., on exit, after idle timeout).

        Returns:
            Session summary with stats
        """
        summary = {
            "session_ended": datetime.now().isoformat(),
            "tiered_memory_available": self.tiered_memory is not None,
        }

        if self.tiered_memory:
            try:
                # Get stats before cleanup
                pre_stats = self.tiered_memory.get_stats()
                summary["pre_cleanup_stats"] = pre_stats

                # Perform session end processing
                self.tiered_memory.end_session()

                # Get stats after cleanup
                post_stats = self.tiered_memory.get_stats()
                summary["post_cleanup_stats"] = post_stats

                logger.info("Session ended, tiered memory consolidated")
            except Exception as e:
                logger.warning(f"Failed to end session cleanly: {e}")
                summary["error"] = str(e)

        return summary

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get tiered memory statistics."""
        if not self.tiered_memory:
            return {"available": False, "reason": "TieredMemory not initialized"}

        try:
            return {"available": True, "stats": self.tiered_memory.get_stats()}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def record_session_metrics(
        self,
        session_start: datetime,
        *,
        context_questions_asked: int = 0,
        time_to_first_useful_output: Optional[float] = None,
        domain: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> SessionProductivityMetrics:
        """Record productivity metrics at session end for Exponential Collaboration research.

        Calculates delegation_rate via TrustAutonomyBridge and corrections_received
        via FeedbackLogger, then appends a SessionProductivityMetrics record to
        ~/.cortex/session_metrics.jsonl.

        Args:
            session_start: datetime when the session began
            context_questions_asked: count of clarifying questions asked this session
            time_to_first_useful_output: seconds to first substantive response, if known
            domain: cortex domain tag (aidev/databricks), defaults to CORTEX_DOMAIN env var
            extra: any additional key/value pairs to persist

        Returns:
            The SessionProductivityMetrics written to disk.
        """
        import os

        now = datetime.now(tz=timezone.utc)
        session_end_str = now.isoformat()
        session_start_utc = (
            session_start.astimezone(timezone.utc)
            if session_start.tzinfo
            else session_start.replace(tzinfo=timezone.utc)
        )
        duration = (now - session_start_utc).total_seconds()

        # --- delegation_rate via TrustAutonomyBridge ---
        delegation_rate = 0.0
        try:
            try:
                from cortex.engines.workstream_orchestrator import TrustAutonomyBridge
            except ImportError:
                from engines.workstream_orchestrator import TrustAutonomyBridge
            bridge = TrustAutonomyBridge()
            policies = bridge.get_all_policies()
            if policies:
                autonomous = sum(1 for p in policies.values() if not p.review_required)
                delegation_rate = autonomous / len(policies)
        except Exception as e:
            logger.debug(f"TrustAutonomyBridge unavailable for delegation_rate: {e}")

        # --- outcomes_recorded this session (entries since session_start) ---
        outcomes_recorded = 0
        try:
            outcomes_file = CORTEX_DIR / "outcomes.jsonl"
            if outcomes_file.exists():
                cutoff = session_start_utc.isoformat()
                with open(outcomes_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            ts = entry.get("timestamp", "")
                            if ts >= cutoff:
                                outcomes_recorded += 1
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.debug(f"Could not count outcomes: {e}")

        # --- corrections_received via FeedbackLogger feedback.json ---
        corrections_received = 0
        try:
            feedback_file = CORTEX_DIR / "feedback.json"
            if feedback_file.exists():
                cutoff = session_start_utc.isoformat()
                with open(feedback_file) as f:
                    entries = json.load(f)
                for entry in entries:
                    ts = entry.get("timestamp", "")
                    if ts >= cutoff and not entry.get("useful", True):
                        corrections_received += 1
        except Exception as e:
            logger.debug(f"Could not count corrections: {e}")

        resolved_domain = domain or os.environ.get("CORTEX_DOMAIN")

        metrics = SessionProductivityMetrics(
            session_id=uuid.uuid4().hex,
            session_start=session_start_utc.isoformat(),
            session_end=session_end_str,
            session_duration_seconds=round(duration, 2),
            context_questions_asked=context_questions_asked,
            time_to_first_useful_output=time_to_first_useful_output,
            delegation_rate=round(delegation_rate, 4),
            corrections_received=corrections_received,
            outcomes_recorded=outcomes_recorded,
            domain=resolved_domain,
            extra=extra or {},
        )

        # Append to ~/.cortex/session_metrics.jsonl
        try:
            SESSION_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SESSION_METRICS_FILE, "a") as f:
                f.write(json.dumps(asdict(metrics)) + "\n")
            logger.info(
                f"Session metrics written: {metrics.session_id} ({duration:.0f}s, delegation={delegation_rate:.0%})"
            )
        except Exception as e:
            logger.warning(f"Failed to write session metrics: {e}")

        return metrics
