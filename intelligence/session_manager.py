"""Session Manager - Creates and manages session context from git history."""

import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SessionContext

# Import TieredMemory for session-aware memory tracking
try:
    from intelligence.memory.tiered_memory import MemoryItem, TieredMemory

    TIERED_MEMORY_AVAILABLE = True
except ImportError:
    TIERED_MEMORY_AVAILABLE = False
    TieredMemory = None
    MemoryItem = None

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session context derived from git history and project state."""

    def __init__(
        self, root_dir: Path = Path("/Users/jesse.kemp/Dev"), enable_tiered_memory: bool = True
    ):
        self.root_dir = Path(root_dir)
        self.cache_dir = Path.home() / ".claude" / "session"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "context.json"

        # Initialize tiered memory if available and enabled
        self.tiered_memory: Optional[TieredMemory] = None
        if enable_tiered_memory and TIERED_MEMORY_AVAILABLE:
            try:
                self.tiered_memory = TieredMemory()
                logger.debug("TieredMemory initialized for session tracking")
            except Exception as e:
                logger.warning(f"Failed to initialize TieredMemory: {e}")

    def load_session_context(self, max_age_hours: int = 1) -> Optional[SessionContext]:
        """
        Load session context from cache or regenerate if stale.

        Args:
            max_age_hours: Regenerate if cache older than this

        Returns:
            SessionContext or None if unavailable
        """
        # Try to load from cache
        if self.cache_file.exists():
            cache_age = datetime.now().timestamp() - self.cache_file.stat().st_mtime
            if cache_age < max_age_hours * 3600:
                try:
                    data = json.loads(self.cache_file.read_text())
                    return SessionContext(**data)
                except Exception:
                    pass  # Fall through to regenerate

        # Regenerate from git history
        return self._generate_session_context()

    def _generate_session_context(self) -> Optional[SessionContext]:
        """Generate session context from git history."""
        try:
            # Detect current project
            cwd = Path.cwd()
            project = self._detect_project(cwd)

            if not project:
                return None

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = cwd

            # Get recent commits
            recent_work = self._get_recent_commits(project_path, limit=5)

            # Extract goals and focus from commits and files
            active_goals = self._extract_goals(project_path)
            current_focus = self._determine_focus(recent_work, project_path)

            # Extract keywords from commit messages and current focus
            keywords = self._extract_keywords_from_commits(project_path)
            if current_focus:
                # Add keywords from focus
                focus_keywords = self._extract_keywords_from_text(current_focus)
                keywords.extend(focus_keywords)
            # Deduplicate and limit
            keywords = list(dict.fromkeys(keywords))[:10]  # Preserve order, limit to 10

            context = SessionContext(
                project=project,
                working_directory=str(cwd),
                recent_work=recent_work,
                active_goals=active_goals,
                current_focus=current_focus,
                last_updated=datetime.now().isoformat(),
            )

            # Store keywords in context metadata (extend recent_work with keywords)
            # Note: SessionContext model doesn't have keywords field, so we'll store in recent_work metadata
            if keywords and recent_work:
                # Add keywords to the most recent work item as metadata
                if recent_work and len(recent_work) > 0:
                    recent_work[0]["keywords"] = keywords

            # Cache for next time
            self.cache_file.write_text(
                json.dumps(
                    {
                        "project": context.project,
                        "working_directory": context.working_directory,
                        "recent_work": context.recent_work,
                        "active_goals": context.active_goals,
                        "current_focus": context.current_focus,
                        "last_updated": context.last_updated,
                    },
                    indent=2,
                )
            )

            return context

        except Exception as e:
            print(f"Error generating session context: {e}")
            return None

    def _detect_project(self, cwd: Path) -> Optional[str]:
        """Detect project name from current directory."""
        # Check if we're in a known project directory
        if self.root_dir in cwd.parents or cwd == self.root_dir:
            # Find the immediate child of root_dir
            for parent in [cwd] + list(cwd.parents):
                if parent.parent == self.root_dir:
                    return parent.name

        # Fallback to directory name
        return cwd.name if cwd != Path.home() else None

    def _get_recent_commits(self, project_path: Path, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent git commits."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%h|%s|%ar|%an"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 4:
                    commits.append(
                        {
                            "hash": parts[0],
                            "summary": parts[1],
                            "time": parts[2],
                            "author": parts[3],
                            "commit": parts[1],  # Backward compat
                        }
                    )

            return commits

        except Exception:
            return []

    def _extract_goals(self, project_path: Path) -> List[str]:
        """Extract active goals from PLAN.md or TODO files."""
        goals = []

        # Check PLAN.md
        plan_file = project_path / "PLAN.md"
        if plan_file.exists():
            try:
                content = plan_file.read_text()
                lines = content.split("\n")

                # Track which section we're in
                in_goal_section = False
                current_section = ""

                for line in lines:
                    stripped = line.strip()

                    # Track section headers to know context
                    if stripped.startswith("#"):
                        current_section = stripped.lower()
                        # Enable goal extraction in relevant sections
                        in_goal_section = any(
                            keyword in current_section
                            for keyword in [
                                "future work",
                                "next steps",
                                "todo",
                                "priority",
                                "remaining",
                                "pending",
                            ]
                        )
                        continue

                    # Only extract goals from relevant sections
                    if not in_goal_section:
                        continue

                    # Look for actual task items
                    if any(marker in line.lower() for marker in ["- [ ]", "todo:"]):
                        goal = stripped.lstrip("-*").strip()
                        goal = goal.replace("[ ]", "").replace("[x]", "").strip()
                        if goal and len(goal) < 100:
                            goals.append(goal)
                            if len(goals) >= 5:
                                break
                    # Look for numbered items (1., 2., etc.)
                    elif stripped and stripped[0].isdigit() and "." in stripped[:4]:
                        parts = stripped.split(".", 1)
                        if len(parts) > 1:
                            goal = parts[1].strip()
                            # Remove markdown formatting like **text**
                            goal = goal.replace("**", "").strip()
                            # Remove time estimates in parentheses
                            if "(" in goal and goal.endswith(")"):
                                goal = goal[: goal.rindex("(")].strip()
                            # Skip if this looks like a sub-item (starts with -)
                            if goal.startswith("-"):
                                continue
                            if goal and len(goal) < 100:
                                goals.append(goal)
                                if len(goals) >= 5:
                                    break
            except Exception:
                pass

        # If no goals found, use generic project focus
        if not goals:
            goals = ["Continue development", "Address recent changes"]

        return goals[:5]

    def _extract_keywords_from_commits(self, project_path: Path, limit: int = 10) -> List[str]:
        """Extract keywords from recent commit messages."""
        try:
            from cortex.context_intelligence import ContextIntelligence

            context_intel = ContextIntelligence(root_dir=self.root_dir)
            return context_intel.extract_keywords_from_commits(project_path, limit=limit)
        except Exception:
            return []

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract keywords from text."""
        try:
            from cortex.context_intelligence import ContextIntelligence

            context_intel = ContextIntelligence(root_dir=self.root_dir)
            return context_intel.extract_keywords_from_task(text)
        except Exception:
            return []

    def _determine_focus(self, recent_work: List[Dict[str, Any]], project_path: Path) -> str:
        """Determine current focus from recent commits and files."""
        if not recent_work:
            return "Starting new session"

        # Use most recent commit summary as focus
        latest = recent_work[0].get("summary", "")

        # Try to extract meaningful focus from commit message
        # Remove common prefixes
        for prefix in ["feat:", "fix:", "chore:", "docs:", "refactor:", "test:"]:
            if latest.lower().startswith(prefix):
                latest = latest[len(prefix) :].strip()

        # Capitalize first letter
        if latest:
            latest = latest[0].upper() + latest[1:]

        return latest or "Recent development work"

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
