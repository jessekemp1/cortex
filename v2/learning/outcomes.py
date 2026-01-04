"""Automated outcome detection from git, CI, and tests."""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


class OutcomeType(Enum):
    """Types of detected outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    IN_PROGRESS = "in_progress"
    UNKNOWN = "unknown"


class OutcomeSource(Enum):
    """Sources of outcome detection."""
    GIT_COMMIT = "git_commit"
    GIT_MERGE = "git_merge"
    CI_PIPELINE = "ci_pipeline"
    TEST_RUN = "test_run"
    MANUAL = "manual"


@dataclass
class DetectedOutcome:
    """An automatically detected outcome."""
    id: str
    source: OutcomeSource
    outcome_type: OutcomeType
    confidence: float  # 0-1, how confident are we in this detection
    project: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    pattern_id: Optional[str] = None  # Linked pattern if correlated

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source": self.source.value,
            "outcome_type": self.outcome_type.value,
            "confidence": self.confidence,
            "project": self.project,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "pattern_id": self.pattern_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DetectedOutcome":
        """Create from dictionary."""
        return cls(
            id=d["id"],
            source=OutcomeSource(d["source"]),
            outcome_type=OutcomeType(d["outcome_type"]),
            confidence=d["confidence"],
            project=d["project"],
            context=d.get("context", {}),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            pattern_id=d.get("pattern_id"),
        )


class OutcomeDetector:
    """Detects outcomes from various sources automatically.

    Sources:
    - Git commits (message analysis)
    - Git merges (PR completion)
    - CI pipelines (GitHub Actions, etc.)
    - Test runs (pytest, jest, etc.)
    """

    # Patterns for detecting outcome type from commit messages
    SUCCESS_PATTERNS = [
        r"\b(fix|resolve|close|complete|finish|implement|add|ship)\b",
        r"\b(done|ready|working|passes)\b",
        r"(?:close|fix|resolve)[sd]?\s+#\d+",  # Closes #123
    ]

    FAILURE_PATTERNS = [
        r"\b(revert|rollback|broken|fail|bug|error)\b",
        r"\b(todo|fixme|hack)\b",  # WIP moved to PARTIAL_PATTERNS
        r"\b(undo|remove|delete)\s+.*\b(feature|implementation)\b",
    ]

    PARTIAL_PATTERNS = [
        r"\b(wip|progress|partial|initial|draft)\b",
        r"\b(part\s*\d+|step\s*\d+)\b",
    ]

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize outcome detector.

        Args:
            data_dir: Directory to store outcomes. Defaults to ~/.claude/v2/
        """
        if data_dir is None:
            data_dir = Path.home() / ".claude" / "v2"

        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir
        self.outcomes_file = data_dir / "outcomes.json"
        self._outcomes: List[DetectedOutcome] = self._load_outcomes()

    def _load_outcomes(self) -> List[DetectedOutcome]:
        """Load outcomes from storage."""
        if self.outcomes_file.exists():
            try:
                with open(self.outcomes_file) as f:
                    data = json.load(f)
                    return [DetectedOutcome.from_dict(o) for o in data.get("outcomes", [])]
            except (json.JSONDecodeError, KeyError):
                return []
        return []

    def _save_outcomes(self):
        """Save outcomes to storage."""
        with open(self.outcomes_file, "w") as f:
            json.dump({
                "version": "2.0",
                "outcomes": [o.to_dict() for o in self._outcomes]
            }, f, indent=2)

    # === Git-based Detection ===

    def record_git_outcome(
        self,
        commit_hash: str,
        message: str,
        branch: str,
        files_changed: int,
        project: Optional[str] = None,
        repo_path: Optional[Path] = None
    ) -> DetectedOutcome:
        """Record an outcome from a git commit.

        Args:
            commit_hash: Git commit SHA
            message: Commit message
            branch: Branch name
            files_changed: Number of files changed
            project: Project name (auto-detected if not provided)
            repo_path: Repository path for project detection
        """
        # Detect project from repo path if not provided
        if project is None and repo_path:
            project = repo_path.name
        elif project is None:
            project = "unknown"

        # Analyze commit message for outcome signals
        outcome_type, confidence = self._analyze_commit_message(message)

        # Boost confidence for certain signals
        if branch in ("main", "master") and outcome_type == OutcomeType.SUCCESS:
            confidence = min(1.0, confidence + 0.2)

        if files_changed > 20:  # Large commits are often milestones
            confidence = min(1.0, confidence + 0.1)

        outcome = DetectedOutcome(
            id=f"git_{commit_hash[:8]}",
            source=OutcomeSource.GIT_COMMIT,
            outcome_type=outcome_type,
            confidence=confidence,
            project=project,
            context={
                "commit_hash": commit_hash,
                "message": message,
                "branch": branch,
                "files_changed": files_changed,
            }
        )

        self._outcomes.append(outcome)
        self._save_outcomes()
        return outcome

    def _analyze_commit_message(self, message: str) -> tuple[OutcomeType, float]:
        """Analyze commit message to detect outcome type.

        Returns:
            Tuple of (OutcomeType, confidence)
        """
        message_lower = message.lower()

        # Check success patterns
        success_matches = sum(
            1 for pattern in self.SUCCESS_PATTERNS
            if re.search(pattern, message_lower)
        )

        # Check failure patterns
        failure_matches = sum(
            1 for pattern in self.FAILURE_PATTERNS
            if re.search(pattern, message_lower)
        )

        # Check partial patterns
        partial_matches = sum(
            1 for pattern in self.PARTIAL_PATTERNS
            if re.search(pattern, message_lower)
        )

        # Determine outcome based on matches
        if failure_matches > success_matches and failure_matches > partial_matches:
            return OutcomeType.FAILURE, min(0.9, 0.5 + failure_matches * 0.15)

        if partial_matches > success_matches and partial_matches > failure_matches:
            return OutcomeType.IN_PROGRESS, min(0.9, 0.5 + partial_matches * 0.15)

        if success_matches > 0:
            return OutcomeType.SUCCESS, min(0.9, 0.5 + success_matches * 0.15)

        return OutcomeType.UNKNOWN, 0.3

    def detect_from_git_log(
        self,
        repo_path: Path,
        since_days: int = 7,
        limit: int = 50
    ) -> List[DetectedOutcome]:
        """Detect outcomes from recent git history.

        Args:
            repo_path: Path to git repository
            since_days: Look back this many days
            limit: Maximum commits to analyze
        """
        try:
            result = subprocess.run(
                [
                    "git", "-C", str(repo_path), "log",
                    f"--since={since_days} days ago",
                    f"--max-count={limit}",
                    "--pretty=format:%H|%s|%D",
                    "--name-only"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return []

            outcomes = []
            current_commit = None
            current_files = []

            for line in result.stdout.split("\n"):
                if "|" in line:
                    # Save previous commit
                    if current_commit:
                        hash_, msg, refs = current_commit.split("|", 2)
                        branch = self._extract_branch(refs)
                        outcome = self.record_git_outcome(
                            commit_hash=hash_,
                            message=msg,
                            branch=branch,
                            files_changed=len(current_files),
                            repo_path=repo_path
                        )
                        outcomes.append(outcome)

                    current_commit = line
                    current_files = []
                elif line.strip():
                    current_files.append(line.strip())

            # Handle last commit
            if current_commit:
                hash_, msg, refs = current_commit.split("|", 2)
                branch = self._extract_branch(refs)
                outcome = self.record_git_outcome(
                    commit_hash=hash_,
                    message=msg,
                    branch=branch,
                    files_changed=len(current_files),
                    repo_path=repo_path
                )
                outcomes.append(outcome)

            return outcomes

        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

    def _extract_branch(self, refs: str) -> str:
        """Extract branch name from git refs."""
        if not refs:
            return "unknown"

        # Look for HEAD -> branch pattern
        match = re.search(r"HEAD -> ([^,\s]+)", refs)
        if match:
            return match.group(1)

        # Look for origin/branch pattern
        match = re.search(r"origin/([^,\s]+)", refs)
        if match:
            return match.group(1)

        return "unknown"

    # === CI/CD Detection ===

    def record_ci_outcome(
        self,
        repo: str,
        workflow: str,
        conclusion: str,
        commit: str,
        branch: str,
        duration_ms: Optional[int] = None
    ) -> DetectedOutcome:
        """Record an outcome from CI/CD pipeline.

        Args:
            repo: Repository name (owner/repo)
            workflow: Workflow/pipeline name
            conclusion: Result (success, failure, cancelled)
            commit: Commit SHA
            branch: Branch name
            duration_ms: Pipeline duration in milliseconds
        """
        # Map CI conclusion to outcome type
        if conclusion == "success":
            outcome_type = OutcomeType.SUCCESS
            confidence = 0.95  # CI results are reliable
        elif conclusion in ("failure", "timed_out"):
            outcome_type = OutcomeType.FAILURE
            confidence = 0.95
        elif conclusion == "cancelled":
            outcome_type = OutcomeType.PARTIAL
            confidence = 0.7
        else:
            outcome_type = OutcomeType.UNKNOWN
            confidence = 0.5

        # Extract project from repo name
        project = repo.split("/")[-1] if "/" in repo else repo

        outcome = DetectedOutcome(
            id=f"ci_{commit[:8]}_{uuid.uuid4().hex[:4]}",
            source=OutcomeSource.CI_PIPELINE,
            outcome_type=outcome_type,
            confidence=confidence,
            project=project,
            context={
                "repo": repo,
                "workflow": workflow,
                "conclusion": conclusion,
                "commit": commit,
                "branch": branch,
                "duration_ms": duration_ms,
            }
        )

        self._outcomes.append(outcome)
        self._save_outcomes()
        return outcome

    # === Test Run Detection ===

    def record_test_outcome(
        self,
        project: str,
        passed: int,
        failed: int,
        skipped: int = 0,
        duration_seconds: float = 0,
        commit: Optional[str] = None,
        test_framework: str = "unknown"
    ) -> DetectedOutcome:
        """Record an outcome from test execution.

        Args:
            project: Project name
            passed: Number of tests passed
            failed: Number of tests failed
            skipped: Number of tests skipped
            duration_seconds: Test duration
            commit: Associated commit SHA
            test_framework: pytest, jest, etc.
        """
        total = passed + failed + skipped

        if failed == 0 and passed > 0:
            outcome_type = OutcomeType.SUCCESS
            confidence = 0.9
        elif failed > 0 and passed > failed:
            outcome_type = OutcomeType.PARTIAL
            confidence = 0.8
        elif failed > passed:
            outcome_type = OutcomeType.FAILURE
            confidence = 0.85
        else:
            outcome_type = OutcomeType.UNKNOWN
            confidence = 0.5

        outcome = DetectedOutcome(
            id=f"test_{uuid.uuid4().hex[:8]}",
            source=OutcomeSource.TEST_RUN,
            outcome_type=outcome_type,
            confidence=confidence,
            project=project,
            context={
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "total": total,
                "pass_rate": passed / total if total > 0 else 0,
                "duration_seconds": duration_seconds,
                "commit": commit,
                "test_framework": test_framework,
            }
        )

        self._outcomes.append(outcome)
        self._save_outcomes()
        return outcome

    # === Pattern Correlation ===

    def correlate_to_pattern(
        self,
        outcome: DetectedOutcome,
        graph_memory: "GraphMemory"
    ) -> Optional[str]:
        """Try to correlate an outcome to a known pattern.

        Args:
            outcome: The detected outcome
            graph_memory: GraphMemory instance to search

        Returns:
            Pattern ID if correlated, None otherwise
        """
        from ..memory.models import MemoryType, RelationType

        # Get project node
        project_nodes = graph_memory.find_nodes(
            type=MemoryType.PROJECT,
            name_contains=outcome.project
        )

        if not project_nodes:
            return None

        project_node = project_nodes[0]

        # Get patterns used by this project
        patterns = graph_memory.get_patterns_for_project(project_node.id)

        if not patterns:
            return None

        # Simple heuristic: most recently updated pattern
        # TODO: Improve with semantic matching on commit message
        patterns_sorted = sorted(patterns, key=lambda p: p.updated_at, reverse=True)
        best_pattern = patterns_sorted[0]

        # Link outcome to pattern
        outcome.pattern_id = best_pattern.id

        # Add validation edge in graph
        outcome_node = graph_memory.add_node(
            type=MemoryType.OUTCOME,
            name=f"Outcome: {outcome.outcome_type.value} for {outcome.project}",
            data=outcome.to_dict()
        )

        graph_memory.add_edge(
            from_id=outcome_node.id,
            to_id=best_pattern.id,
            relation=RelationType.VALIDATES,
            weight=outcome.confidence,
            data={"outcome_type": outcome.outcome_type.value}
        )

        self._save_outcomes()
        return best_pattern.id

    # === Querying ===

    def get_recent_outcomes(
        self,
        project: Optional[str] = None,
        days: int = 7,
        outcome_type: Optional[OutcomeType] = None,
        source: Optional[OutcomeSource] = None
    ) -> List[DetectedOutcome]:
        """Get recent detected outcomes.

        Args:
            project: Filter by project
            days: Look back this many days
            outcome_type: Filter by outcome type
            source: Filter by detection source
        """
        cutoff = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)

        results = []
        for outcome in self._outcomes:
            if outcome.timestamp.timestamp() < cutoff:
                continue

            if project and outcome.project != project:
                continue

            if outcome_type and outcome.outcome_type != outcome_type:
                continue

            if source and outcome.source != source:
                continue

            results.append(outcome)

        return sorted(results, key=lambda o: o.timestamp, reverse=True)

    def get_outcome_stats(
        self,
        project: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get outcome statistics.

        Args:
            project: Filter by project
            days: Look back this many days
        """
        outcomes = self.get_recent_outcomes(project=project, days=days)

        if not outcomes:
            return {
                "total": 0,
                "by_type": {},
                "by_source": {},
                "success_rate": 0,
                "avg_confidence": 0,
            }

        by_type = {}
        by_source = {}
        total_confidence = 0

        for o in outcomes:
            by_type[o.outcome_type.value] = by_type.get(o.outcome_type.value, 0) + 1
            by_source[o.source.value] = by_source.get(o.source.value, 0) + 1
            total_confidence += o.confidence

        success_count = by_type.get("success", 0)
        failure_count = by_type.get("failure", 0)
        total_definitive = success_count + failure_count

        return {
            "total": len(outcomes),
            "by_type": by_type,
            "by_source": by_source,
            "success_rate": success_count / total_definitive if total_definitive > 0 else 0,
            "avg_confidence": total_confidence / len(outcomes),
        }
