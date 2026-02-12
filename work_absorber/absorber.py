"""
Work Absorber - Core absorption engine.

Orchestrates the detection, consolidation, and correlation of work
across all projects in the portfolio.
"""

import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .correlator import DriftAnalyzer, PlanCorrelator
from .detectors.base import SignalDetector
from .detectors.batch_detector import BatchResultDetector
from .detectors.doc_detector import CompletionDocDetector
from .detectors.git_detector import GitSignalDetector
from .models import (
    AbsorptionReport,
    PlanDrift,
    WorkItem,
    WorkSignal,
    WorkStatus,
)
from .storage import WorkAbsorberStorage

logger = logging.getLogger(__name__)


class WorkAbsorber:
    """
    Core absorption engine that consolidates work signals.

    Pipeline:
    1. Detect signals from all sources (git, docs, batch)
    2. Merge and deduplicate signals
    3. Build or update work items
    4. Correlate with plans
    5. Detect drift
    6. Persist results
    """

    def __init__(
        self,
        storage: Optional[WorkAbsorberStorage] = None,
        detectors: Optional[List[SignalDetector]] = None,
        dev_dir: Optional[Path] = None,
    ):
        """
        Initialize the absorber.

        Args:
            storage: Storage backend (defaults to SQLite)
            detectors: List of signal detectors (defaults to all)
            dev_dir: Development root directory
        """
        self.storage = storage or WorkAbsorberStorage()
        self.dev_dir = dev_dir or Path.home() / "Dev"
        self.detectors = detectors or self._default_detectors()
        self.correlator = PlanCorrelator(dev_dir=self.dev_dir)
        self.drift_analyzer = DriftAnalyzer(self.correlator)

    def _default_detectors(self) -> List[SignalDetector]:
        """Get default set of signal detectors."""
        return [
            GitSignalDetector(),
            CompletionDocDetector(),
            BatchResultDetector(),
        ]

    def absorb(
        self,
        projects: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        incremental: bool = True,
    ) -> AbsorptionReport:
        """
        Run absorption cycle to detect and consolidate work.

        Args:
            projects: Projects to absorb (None = all in dev_dir)
            since: Start of time range (None = last absorption or 7 days)
            until: End of time range (None = now)
            incremental: Only process new signals since last run

        Returns:
            AbsorptionReport with statistics
        """
        report = AbsorptionReport(
            id=f"absorb-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            started_at=datetime.now(),
            completed_at=datetime.now(),  # Updated at end
        )

        try:
            # Determine time range
            if since is None and incremental:
                since = self.storage.get_last_absorption_time()
            if since is None:
                since = datetime.now() - timedelta(days=7)

            until = until or datetime.now()

            logger.info(f"Starting absorption from {since} to {until}")

            # Get project list
            project_list = projects or self._discover_projects()
            logger.info(f"Absorbing {len(project_list)} projects")

            # Phase 1: Detect signals from all sources
            all_signals = self._detect_all_signals(project_list, since, until)
            report.signals_detected = len(all_signals)

            # Phase 2: Merge and deduplicate
            merged_signals = self._merge_signals(all_signals)
            logger.info(f"Merged {len(all_signals)} signals into {len(merged_signals)}")

            # Phase 3: Build work items
            work_items, created, updated = self._build_work_items(merged_signals)
            report.work_items_created = created
            report.work_items_updated = updated

            # Phase 4: Correlate with plans
            correlations = self._correlate_with_plans(work_items)
            report.correlations_made = len(correlations)

            # Phase 5: Detect drift
            drifts = self._detect_drift(work_items)
            report.drifts_detected = len(drifts)

            # Phase 6: Persist everything
            self._persist_results(merged_signals, work_items, drifts)
            report.signals_absorbed = len(merged_signals)

            # Update last absorption time
            self.storage.set_last_absorption_time(datetime.now())

            # Calculate per-project stats
            for project in project_list:
                project_signals = [s for s in merged_signals if s.project == project]
                project_items = [w for w in work_items if w.project == project]
                project_correlations = sum(1 for w in project_items if w.plan_step_id)

                report.add_project_stats(
                    project,
                    len(project_signals),
                    len(project_items),
                    project_correlations,
                )

        except Exception as e:
            logger.error(f"Absorption failed: {e}")
            report.errors.append(str(e))

        report.completed_at = datetime.now()
        self.storage.save_report(report)

        return report

    def _discover_projects(self) -> List[str]:
        """Discover all projects in dev directory."""
        projects = []

        # Skip these common non-project directories
        skip = {
            "node_modules",
            "venv",
            "__pycache__",
            ".git",
            "logs",
            "reports",
            "sandbox",
            "archive",
            "_meta",
            "_tools",
            "dataset",
            "scripts",
            "Docs",
            "production",
        }

        def is_project_dir(item: Path) -> bool:
            """Check if directory looks like a project."""
            if not item.is_dir():
                return False
            # Has its own .git (standalone repo or submodule)
            if (item / ".git").exists():
                return True
            # Has common project files
            if (
                (item / "package.json").exists()
                or (item / "pyproject.toml").exists()
                or (item / "setup.py").exists()
                or (item / "requirements.txt").exists()
                or (item / "Cargo.toml").exists()
            ):
                return True
            # Has a src or app directory (common project structure)
            if (item / "src").is_dir() or (item / "app").is_dir():
                return True
            # Has Python files in root (simple Python project)
            if list(item.glob("*.py"))[:1]:
                return True
            return False

        for item in self.dev_dir.iterdir():
            if not item.is_dir():
                continue

            # Skip hidden directories
            if item.name.startswith("."):
                continue

            # Skip common non-project directories
            if item.name in skip:
                continue

            # Check if top-level is a project
            if is_project_dir(item):
                projects.append(item.name)

            # Also check one level deeper for nested projects (e.g., Vortex/VortexV2)
            if item.is_dir() and item.name not in skip:
                for subitem in item.iterdir():
                    if subitem.name.startswith(".") or subitem.name in skip:
                        continue
                    if is_project_dir(subitem):
                        # Use nested name like "Vortex/VortexV2"
                        projects.append(f"{item.name}/{subitem.name}")

        return projects

    def _detect_all_signals(
        self,
        projects: List[str],
        since: datetime,
        until: datetime,
    ) -> List[WorkSignal]:
        """Run all detectors and collect signals."""
        all_signals = []

        for project in projects:
            project_path = self.dev_dir / project

            if not project_path.exists():
                logger.warning(f"Project path not found: {project_path}")
                continue

            for detector in self.detectors:
                try:
                    signals = detector.detect(
                        project=project,
                        project_path=project_path,
                        since=since,
                        until=until,
                    )
                    all_signals.extend(signals)
                    logger.debug(f"{detector.name} found {len(signals)} signals for {project}")

                except Exception as e:
                    logger.warning(f"Detector {detector.name} failed for {project}: {e}")

        return all_signals

    def _merge_signals(self, signals: List[WorkSignal]) -> List[WorkSignal]:
        """Merge and deduplicate signals."""
        # Group by ID (deterministic IDs handle deduplication)
        by_id: Dict[str, WorkSignal] = {}

        for signal in signals:
            if signal.id in by_id:
                # Merge metadata from duplicate
                existing = by_id[signal.id]
                existing.metadata.update(signal.metadata)

                # Merge files
                for f in signal.files_changed:
                    if f not in existing.files_changed:
                        existing.files_changed.append(f)

                # Merge achievements
                for a in signal.achievements:
                    if a not in existing.achievements:
                        existing.achievements.append(a)
            else:
                by_id[signal.id] = signal

        return list(by_id.values())

    def _build_work_items(
        self,
        signals: List[WorkSignal],
    ) -> tuple[List[WorkItem], int, int]:
        """Build or update work items from signals."""
        created = 0
        updated = 0

        # Group signals by similarity for consolidation
        groups = self._group_related_signals(signals)

        work_items = []

        for group in groups:
            # Check if we have an existing work item for this group
            existing = self._find_existing_work_item(group)

            if existing:
                # Update existing item
                for signal in group:
                    existing.add_signal(signal)
                existing.status = WorkStatus.ABSORBED
                work_items.append(existing)
                updated += 1
            else:
                # Create new work item
                work_item = self._create_work_item(group)
                work_items.append(work_item)
                created += 1

        return work_items, created, updated

    def _group_related_signals(
        self,
        signals: List[WorkSignal],
    ) -> List[List[WorkSignal]]:
        """Group related signals for consolidation into work items."""
        # Simple grouping by project + scope + day
        groups: Dict[str, List[WorkSignal]] = defaultdict(list)

        for signal in signals:
            # Create group key
            date_key = signal.timestamp.strftime("%Y-%m-%d")
            scope_key = signal.scope or "misc"
            group_key = f"{signal.project}:{scope_key}:{date_key}"

            groups[group_key].append(signal)

        return list(groups.values())

    def _find_existing_work_item(
        self,
        signals: List[WorkSignal],
    ) -> Optional[WorkItem]:
        """Find existing work item that matches these signals."""
        if not signals:
            return None

        # Look for work item with overlapping signal IDs
        for signal in signals:
            if signal.absorbed_into:
                existing = self.storage.get_work_item(signal.absorbed_into)
                if existing:
                    return existing

        # Try to find by title similarity
        primary = signals[0]
        project_items = self.storage.get_work_items_by_project(primary.project)

        for item in project_items:
            # Check if titles are very similar
            if self._titles_match(item.title, primary.title):
                return item

        return None

    def _titles_match(self, title1: str, title2: str) -> bool:
        """Check if two titles are similar enough to be the same work."""
        # Normalize
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()

        # Exact match
        if t1 == t2:
            return True

        # One contains the other
        if t1 in t2 or t2 in t1:
            return True

        # High similarity
        from difflib import SequenceMatcher

        ratio = SequenceMatcher(None, t1, t2).ratio()
        return ratio > 0.8

    def _create_work_item(self, signals: List[WorkSignal]) -> WorkItem:
        """Create a new work item from a group of signals."""
        if not signals:
            raise ValueError("Cannot create work item from empty signals")

        primary = signals[0]

        # Generate ID from primary signal
        item_id = f"work-{hashlib.sha256(primary.id.encode()).hexdigest()[:8]}"

        # Build title from primary signal
        title = primary.title

        # Collect all files
        all_files = []
        for signal in signals:
            all_files.extend(signal.files_changed)
        all_files = list(set(all_files))

        # Estimate effort (heuristic: ~0.5h per file changed)
        effort = len(all_files) * 0.5

        # Collect tags
        tags = set()
        for signal in signals:
            if signal.scope:
                tags.add(signal.scope)

        work_item = WorkItem(
            id=item_id,
            project=primary.project,
            title=title,
            description=primary.description,
            first_seen=min(s.timestamp for s in signals),
            last_activity=max(s.timestamp for s in signals),
            signal_ids=[s.id for s in signals],
            signal_count=len(signals),
            status=WorkStatus.ABSORBED,
            files_touched=all_files,
            estimated_effort_hours=effort,
            tags=list(tags),
            scope=primary.scope,
        )

        return work_item

    def _correlate_with_plans(
        self,
        work_items: List[WorkItem],
    ) -> Dict[str, tuple[str, float]]:
        """Correlate work items with plan steps."""
        correlations = {}

        for item in work_items:
            result = self.correlator.correlate(item)

            if result:
                plan_step_id, confidence = result
                item.plan_step_id = plan_step_id
                item.correlation_confidence = confidence
                item.status = WorkStatus.CORRELATED
                correlations[item.id] = result
            else:
                item.status = WorkStatus.ORPHANED

        return correlations

    def _detect_drift(self, work_items: List[WorkItem]) -> List[PlanDrift]:
        """Detect plan drift from work items."""
        return self.drift_analyzer.analyze(work_items)

    def _persist_results(
        self,
        signals: List[WorkSignal],
        work_items: List[WorkItem],
        drifts: List[PlanDrift],
    ) -> None:
        """Persist all results to storage."""
        # Save signals
        saved = self.storage.save_signals_batch(signals)
        logger.info(f"Saved {saved} signals")

        # Save work items
        for item in work_items:
            self.storage.save_work_item(item)

        # Mark signals as processed
        for item in work_items:
            for signal_id in item.signal_ids:
                self.storage.mark_signal_processed(signal_id, item.id)

        # Save drifts
        for drift in drifts:
            self.storage.save_drift(drift)

        logger.info(f"Persisted {len(work_items)} work items, {len(drifts)} drifts")

    # ─────────────────────────────────────────────────────────────────
    # Query Methods
    # ─────────────────────────────────────────────────────────────────

    def get_recent_work(
        self,
        days: int = 7,
        project: Optional[str] = None,
    ) -> List[WorkItem]:
        """Get recent work items."""
        since = datetime.now() - timedelta(days=days)
        items = self.storage.get_work_items_since(since)

        if project:
            items = [i for i in items if i.project.lower() == project.lower()]

        return items

    def get_unplanned_work(self) -> List[WorkItem]:
        """Get work items not correlated to any plan."""
        return self.storage.get_orphaned_work_items()

    def get_drift_summary(self, project: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of plan drift."""
        drifts = self.storage.get_unresolved_drifts(project)

        summary = {
            "total": len(drifts),
            "by_type": defaultdict(int),
            "by_severity": defaultdict(int),
            "drifts": drifts[:10],  # Top 10
        }

        for drift in drifts:
            summary["by_type"][drift.drift_type.value] += 1
            summary["by_severity"][drift.severity] += 1

        return summary

    def get_status(self) -> Dict[str, Any]:
        """Get overall absorber status."""
        stats = self.storage.get_stats()
        latest = self.storage.get_latest_report()

        return {
            "storage": stats,
            "last_absorption": (
                {
                    "id": latest.id if latest else None,
                    "time": latest.completed_at.isoformat() if latest else None,
                    "signals": latest.signals_absorbed if latest else 0,
                    "items": (
                        latest.work_items_created + latest.work_items_updated if latest else 0
                    ),
                    "drifts": latest.drifts_detected if latest else 0,
                }
                if latest
                else None
            ),
        }
