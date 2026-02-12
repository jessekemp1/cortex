"""
Cortex V2.1 Bridge - Unified Intelligence System

Extends V2 with:
- Daily briefings (from V1)
- Smart recommendations (calibrated)
- Project analysis
- Dependency analysis
- Batch processing
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import V2 as foundation
from cortex.v2.bridge import CortexV2Bridge


class CortexV2_1Bridge(CortexV2Bridge):
    """V2.1 Bridge = V2 Foundation + V1 Intelligence.

    Inherits all 36 V2 methods:
    - Memory operations (add_pattern, add_incident, add_skill, add_decision)
    - Query operations (query, find_pattern, find_skill, find_incident, find_decision)
    - Relationship operations (link_memories, get_related, get_patterns_for_project)
    - Outcome operations (record_*, detect_*, get_*, correlate_*)
    - Temporal decay (get_stale_memories, apply_decay_to_query)
    - Confidence calibration (recalibrate_*, get_confidence_*, get_pattern_confidence)
    - Skill extraction (extract_skills)
    - Stats (stats)

    Adds V2.1 intelligence methods:
    - briefing() - Daily briefing with calibrated confidence
    - get_recommendations() - Smart recommendations using patterns
    - get_portfolio_health() - Portfolio health from outcomes
    - analyze_project() - Deep project analysis
    - get_project_profile() - Project tech stack
    - get_warnings() - Project warnings
    - get_dependencies() - Dependency analysis
    - submit_batch() - Batch processing
    """

    def __init__(self, data_dir: Optional[Path] = None, root_dir: Optional[Path] = None):
        """Initialize V2.1 Bridge.

        Args:
            data_dir: Directory for V2 data. Defaults to ~/.claude/v2/
            root_dir: Root directory for project scanning. Defaults to ~/Dev
        """
        super().__init__(data_dir=data_dir)

        self.root_dir = root_dir or Path.home() / "Dev"

        # Lazy-load V1 components to avoid circular imports
        self._briefing_generator = None
        self._project_scanner = None
        self._recommendation_engine = None

    # === V2.1 Intelligence Methods ===

    def briefing(self, format: str = "text", use_color: bool = True) -> str:
        """Generate daily briefing with calibrated confidence.

        Combines V1 briefing format with V2 outcome data and confidence.

        Args:
            format: Output format ("text" or "json")
            use_color: Use ANSI colors in text output

        Returns:
            Formatted briefing string
        """
        from cortex.briefing import (
            format_briefing,
            format_briefing_json,
            generate_daily_briefing,
        )

        # Generate V1 briefing
        briefing_data = generate_daily_briefing(root_dir=self.root_dir)

        # Enhance with V2 data
        outcome_stats = self.get_outcome_stats(days=7)
        confidence_report = self.get_confidence_report()

        # Add V2 insights to briefing
        if hasattr(briefing_data, "v2_insights"):
            briefing_data.v2_insights = {
                "outcomes_7d": outcome_stats.get("total", 0),
                "success_rate": outcome_stats.get("success_rate", 0),
                "patterns_calibrated": confidence_report.get("total_patterns", 0),
                "high_confidence_patterns": confidence_report.get("high_confidence", 0),
            }

        if format == "json":
            output = format_briefing_json(briefing_data)
            # Inject V2 insights into JSON
            data = json.loads(output)
            data["v2_insights"] = {
                "outcomes_7d": outcome_stats.get("total", 0),
                "success_rate": outcome_stats.get("success_rate", 0),
                "patterns_calibrated": confidence_report.get("total_patterns", 0),
            }
            return json.dumps(data, indent=2, default=str)
        else:
            return format_briefing(briefing_data, use_color=use_color)

    def get_recommendations(
        self, project: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get smart recommendations using patterns with calibrated confidence.

        Uses V2's Bayesian calibration and temporal decay to rank recommendations.

        Args:
            project: Filter by project (optional)
            limit: Maximum recommendations to return

        Returns:
            List of recommendations with calibrated confidence
        """
        raw_recs = []

        # Try V1 recommendation engine
        try:
            import sys

            # Add cortex to path for intelligence imports
            cortex_path = str(Path(__file__).parent.parent)
            if cortex_path not in sys.path:
                sys.path.insert(0, cortex_path)

            from cortex.recommendation_engine import RecommendationEngine

            engine = RecommendationEngine(root_dir=self.root_dir)
            raw_recs = engine.get_prioritized(project=project, limit=limit * 2)
        except (ImportError, Exception):
            # Fallback: Generate recommendations from V2 patterns
            patterns = self.store.patterns  # Access patterns list
            for pattern in patterns[: limit * 2]:
                if project and project not in pattern.projects:
                    continue
                raw_recs.append(
                    {
                        "title": pattern.title,
                        "priority": "MEDIUM",
                        "project": (pattern.projects[0] if pattern.projects else "unknown"),
                        "rationale": pattern.problem,
                        "confidence": pattern.confidence,
                        "source": "v2_pattern",
                    }
                )

        # Enhance with V2 calibration
        enhanced = []
        for rec in raw_recs:
            # Try to find matching pattern
            pattern = self.find_pattern(rec.get("title", ""))

            if pattern:
                # Use calibrated confidence from pattern
                try:
                    calibrated_conf = self.get_pattern_confidence(pattern["id"])
                    rec["confidence"] = calibrated_conf.get(
                        "confidence", rec.get("confidence", 0.5)
                    )
                    rec["certainty"] = calibrated_conf.get("certainty", 0.0)
                    rec["calibrated"] = True
                except (ValueError, Exception):
                    # Pattern not in graph, use original confidence
                    rec["calibrated"] = False
            else:
                rec["calibrated"] = False

            # Apply temporal decay to confidence
            if "last_used" in rec:
                decay_result = self.decay.calculate(
                    last_used=datetime.fromisoformat(rec["last_used"]),
                    use_count=rec.get("use_count", 0),
                )
                rec["relevance"] = decay_result.relevance

            enhanced.append(rec)

        # Sort by calibrated confidence
        enhanced.sort(key=lambda r: r.get("confidence", 0), reverse=True)

        return enhanced[:limit]

    def get_portfolio_health(self) -> Dict[str, Any]:
        """Get portfolio health summary from outcome stats.

        Combines V1 project scanning with V2 outcome analysis.

        Returns:
            Portfolio health summary
        """
        projects = []

        try:
            from cortex.project_scanner import ProjectScanner

            scanner = ProjectScanner(root_dir=self.root_dir)
            projects = scanner.scan_projects()
        except (ImportError, Exception):
            # Fallback: Use projects from V2 memory
            from cortex.v2.memory.models import MemoryType

            project_nodes = self.graph.find_nodes(type=MemoryType.PROJECT)
            projects = [{"name": n.name} for n in project_nodes]

        # Get outcome stats per project
        health = {
            "total_projects": len(projects),
            "projects": [],
            "overall_success_rate": 0.0,
            "total_outcomes": 0,
        }

        total_successes = 0
        total_outcomes = 0

        for project in projects:
            project_name = project.get("name", "unknown")
            outcome_stats = self.get_outcome_stats(project=project_name, days=30)

            project_health = {
                "name": project_name,
                "outcomes_30d": outcome_stats.get("total", 0),
                "success_rate": outcome_stats.get("success_rate", 0.5),
                "patterns": len(self.get_patterns_for_project(project_name)),
            }
            health["projects"].append(project_health)

            total_outcomes += outcome_stats.get("total", 0)
            if outcome_stats.get("by_type"):
                total_successes += outcome_stats["by_type"].get("success", 0)

        health["total_outcomes"] = total_outcomes
        if total_outcomes > 0:
            health["overall_success_rate"] = total_successes / total_outcomes

        return health

    def analyze_project(self, project: str, quick: bool = False) -> Dict[str, Any]:
        """Perform deep project analysis.

        Args:
            project: Project name or path
            quick: Quick analysis (skip deep scans)

        Returns:
            Analysis results
        """
        from cortex.project_analyzer import ProjectAnalyzer

        analyzer = ProjectAnalyzer(root_dir=self.root_dir)
        analysis = analyzer.analyze(project, quick=quick)

        # Enhance with V2 pattern data
        patterns = self.get_patterns_for_project(project)
        outcome_stats = self.get_outcome_stats(project=project, days=30)

        analysis["v2_insights"] = {
            "patterns_count": len(patterns),
            "outcomes_30d": outcome_stats.get("total", 0),
            "success_rate": outcome_stats.get("success_rate", 0),
        }

        return analysis

    def get_project_profile(self, project: str) -> Dict[str, Any]:
        """Get project tech stack profile.

        Args:
            project: Project name

        Returns:
            Project profile with tech stack
        """
        from cortex.project_scanner import ProjectScanner

        scanner = ProjectScanner(root_dir=self.root_dir)
        profile = scanner.get_project_profile(project)

        # Add V2 pattern info
        patterns = self.get_patterns_for_project(project)
        profile["v2_patterns"] = [p.get("title") for p in patterns]

        return profile

    def get_warnings(
        self, project: Optional[str] = None, severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get project warnings.

        Args:
            project: Filter by project
            severity: Filter by severity (critical, major, minor)

        Returns:
            List of warnings
        """
        # Check for patterns with low confidence
        confidence_report = self.get_confidence_report(project=project)

        warnings = []

        # Low confidence patterns
        for pattern in confidence_report.get("patterns", []):
            if pattern.get("confidence", 0.5) < 0.4:
                warnings.append(
                    {
                        "type": "low_confidence_pattern",
                        "severity": "minor",
                        "message": f"Pattern '{pattern['name']}' has low confidence ({pattern['confidence']:.0%})",
                        "recommendation": "Consider reviewing or deprecating",
                        "pattern_id": pattern["id"],
                    }
                )

        # Stale memories
        stale = self.get_stale_memories(threshold=0.1)
        for memory in stale:
            warnings.append(
                {
                    "type": "stale_memory",
                    "severity": "minor",
                    "message": f"Memory '{memory.get('title')}' is stale (relevance: {memory.get('effective_confidence', 0):.0%})",
                    "recommendation": "Consider updating or archiving",
                    "memory_id": memory.get("id"),
                }
            )

        # Filter by severity if specified
        if severity:
            warnings = [w for w in warnings if w["severity"] == severity]

        return warnings

    # === Goal Tracking Methods ===

    def add_goal(
        self,
        title: str,
        description: str = "",
        deadline: Optional[str] = None,
        success_criteria: Optional[List[str]] = None,
        projects: Optional[List[str]] = None,
        progress: int = 0,
    ) -> Dict[str, Any]:
        """Add a new goal to track.

        Args:
            title: Goal title
            description: Goal description
            deadline: Target deadline (ISO date string)
            success_criteria: List of success criteria
            projects: Associated projects
            progress: Initial progress (0-100)

        Returns:
            Created goal with ID
        """
        from cortex.v2.memory.models import MemoryType
        from cortex.v2.memory.types import Goal

        goal = Goal.create(
            title=title,
            description=description,
            deadline=deadline,
            success_criteria=success_criteria or [],
            projects=projects or [],
            progress=progress,
        )

        self.store.add(goal)

        # Add to graph
        node = self.graph.add_node(type=MemoryType.GOAL, name=title, data=goal.to_dict())

        return {
            "id": goal.id,
            "graph_node_id": node.id,
            "title": title,
            "status": goal.status,
            "progress": goal.progress,
            "success": True,
        }

    def update_goal(
        self,
        goal_id: str,
        progress: Optional[int] = None,
        status: Optional[str] = None,
        blockers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update a goal's progress or status.

        Args:
            goal_id: Goal ID
            progress: New progress (0-100)
            status: New status (active, completed, blocked, abandoned)
            blockers: List of blockers

        Returns:
            Updated goal
        """
        # Find goal in store
        for mem in self.store.goals:
            if mem.id == goal_id:
                if progress is not None:
                    mem.progress = min(100, max(0, progress))
                if status is not None:
                    mem.status = status
                if blockers is not None:
                    mem.blockers = blockers
                if progress == 100 and status is None:
                    mem.status = "completed"
                mem.mark_used()
                # Save goals
                self.store._save_memories(self.store.goals_file, self.store.goals)
                return mem.to_dict()

        return {"error": f"Goal not found: {goal_id}"}

    def get_goals(
        self, status: Optional[str] = None, project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all goals, optionally filtered.

        Args:
            status: Filter by status (active, completed, blocked, abandoned)
            project: Filter by project

        Returns:
            List of goals
        """
        goals = []
        for mem in self.store.goals:
            if status and mem.status != status:
                continue
            if project and project not in mem.projects:
                continue
            goals.append(mem.to_dict())

        # Sort by progress (active goals first, then by progress)
        goals.sort(key=lambda g: (0 if g["status"] == "active" else 1, -g["progress"]))

        return goals

    def get_goal_summary(self) -> Dict[str, Any]:
        """Get summary of all goals.

        Returns:
            Goal summary with counts and progress
        """
        goals = self.get_goals()

        summary = {
            "total": len(goals),
            "by_status": {},
            "avg_progress": 0,
            "blocked_count": 0,
            "active_goals": [],
        }

        total_progress = 0
        for goal in goals:
            status = goal["status"]
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            total_progress += goal["progress"]
            if goal.get("blockers"):
                summary["blocked_count"] += 1
            if status == "active":
                summary["active_goals"].append(
                    {
                        "id": goal["id"],
                        "title": goal["title"],
                        "progress": goal["progress"],
                        "deadline": goal.get("deadline"),
                    }
                )

        if goals:
            summary["avg_progress"] = total_progress / len(goals)

        return summary

    def get_dependencies(self, project: str) -> Dict[str, Any]:
        """Get project dependency analysis.

        Note: DependencyAnalyzer is planned for future implementation.
        Currently returns project info from graph if available.

        Args:
            project: Project name

        Returns:
            Dependency analysis or status
        """
        # Return what we know from the graph
        from cortex.v2.memory.models import MemoryType

        project_nodes = self.graph.find_nodes(type=MemoryType.PROJECT)
        project_data = None
        for node in project_nodes:
            if node.name.lower() == project.lower():
                project_data = node
                break

        if project_data:
            # Get patterns linked to this project
            patterns = self.get_patterns_for_project(project)
            return {
                "project": project,
                "status": "partial",
                "patterns_count": len(patterns),
                "note": "Full dependency analysis not yet implemented",
            }

        return {
            "project": project,
            "status": "not_found",
            "note": "Project not in knowledge graph",
        }

    def find_circular_dependencies(self, project: str) -> List[List[str]]:
        """Find circular dependencies in project.

        Note: Not yet implemented. Returns empty list.

        Args:
            project: Project name

        Returns:
            List of circular dependency chains (currently empty)
        """
        return []

    def export_dependency_graph(self, project: str, format: str = "json") -> str:
        """Export dependency graph.

        Note: Returns graph data for project from knowledge graph.

        Args:
            project: Project name
            format: Output format (json, dot, mermaid)

        Returns:
            Dependency graph in specified format
        """
        deps = self.get_dependencies(project)

        if format == "json":
            return json.dumps(deps, indent=2)
        elif format == "mermaid":
            patterns = self.get_patterns_for_project(project)
            lines = ["graph TD", f"    {project}[{project}]"]
            for i, p in enumerate(patterns[:10]):  # Limit to 10
                lines.append(f"    P{i}[{p.get('title', 'Pattern')}]")
                lines.append(f"    {project} --> P{i}")
            return "\n".join(lines)
        else:
            return json.dumps(deps)

    def submit_batch(self, items: List[Dict[str, Any]], batch_type: str = "research") -> str:
        """Submit items for batch processing.

        Supports batch types:
        - "research": Research queue items via ResearchBatcher
        - "learning": Learning insights via LearningBatcher
        - "generic": Raw batch requests via BatchAPIClient

        Args:
            items: Items to process (format depends on batch_type)
            batch_type: Type of batch (research, learning, generic)

        Returns:
            Batch ID for tracking
        """
        import uuid

        # Check if anthropic SDK is available first
        try:
            import anthropic
        except ImportError:
            return f"batch_queued_{uuid.uuid4().hex[:8]}_install_anthropic_sdk"

        try:
            from cortex.batch import BatchAPIClient, BatchRequest

            # Build requests based on batch type
            if batch_type == "research":
                # Research batch - format items for research prompt
                from cortex.batch.research_batcher import ResearchBatcher

                requests = []
                for i, item in enumerate(items):
                    req = BatchRequest(
                        custom_id=item.get("id", f"research_{i}"),
                        params={
                            "messages": [
                                {
                                    "role": "user",
                                    "content": ResearchBatcher.RESEARCH_USER_PROMPT_TEMPLATE.format(
                                        topic=item.get("topic", "unknown"),
                                        context=item.get("context", ""),
                                        priority=item.get("priority", "medium"),
                                    ),
                                }
                            ],
                            "system": ResearchBatcher.RESEARCH_SYSTEM_PROMPT,
                        },
                    )
                    requests.append(req)

            elif batch_type == "learning":
                # Learning batch - format for learning prompts
                requests = [
                    BatchRequest(
                        custom_id=item.get("id", f"learning_{i}"),
                        params=item.get(
                            "params",
                            {"messages": [{"role": "user", "content": str(item)}]},
                        ),
                    )
                    for i, item in enumerate(items)
                ]

            else:
                # Generic batch
                requests = [
                    BatchRequest(
                        custom_id=item.get("id", f"req_{i}"),
                        params=item.get(
                            "params",
                            {"messages": [{"role": "user", "content": str(item)}]},
                        ),
                    )
                    for i, item in enumerate(items)
                ]

            # Submit batch (non-blocking - returns immediately)
            client = BatchAPIClient()
            return client.submit_batch(requests, description=f"V2.1 {batch_type} batch")

        except ImportError:
            return f"batch_pending_{uuid.uuid4().hex[:8]}_missing_module"
        except Exception as e:
            return f"batch_error_{uuid.uuid4().hex[:8]}_{str(e)[:20]}"

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get batch processing status.

        Args:
            batch_id: Batch ID from submit_batch

        Returns:
            Batch status with progress info
        """
        # Handle queued/pending/error batch IDs (not yet submitted to API)
        if any(batch_id.startswith(p) for p in ["batch_queued_", "batch_pending_", "batch_error_"]):
            return {
                "batch_id": batch_id,
                "status": "queued",
                "note": "Batch queued locally - requires anthropic SDK for submission",
            }

        try:
            from cortex.batch import BatchAPIClient

            client = BatchAPIClient()
            return client.get_batch_status(batch_id)
        except ImportError:
            return {
                "batch_id": batch_id,
                "status": "unknown",
                "error": "anthropic SDK not installed",
            }
        except Exception as e:
            return {"batch_id": batch_id, "status": "error", "error": str(e)}

    def poll_batch_results(self, batch_id: str, timeout_minutes: int = 60) -> List[Dict[str, Any]]:
        """Poll for batch results until complete.

        Args:
            batch_id: Batch ID from submit_batch
            timeout_minutes: Max wait time

        Returns:
            List of results
        """
        try:
            from cortex.batch import BatchAPIClient

            client = BatchAPIClient()
            results = client.poll_results(batch_id, timeout_minutes=timeout_minutes)
            return [
                {"custom_id": r.custom_id, "result": r.result, "status": r.status} for r in results
            ]
        except ImportError:
            return [{"error": "anthropic SDK not installed"}]
        except Exception as e:
            return [{"error": str(e)}]

    def stats(self) -> Dict[str, Any]:
        """Get comprehensive V2.1 statistics.

        Extends V2 stats with V1 portfolio data.

        Returns:
            Complete system statistics
        """
        # Get V2 stats
        v2_stats = super().stats()

        # Add V2.1 portfolio stats
        try:
            portfolio_health = self.get_portfolio_health()
            v2_stats["portfolio"] = {
                "total_projects": portfolio_health.get("total_projects", 0),
                "overall_success_rate": portfolio_health.get("overall_success_rate", 0),
                "total_outcomes": portfolio_health.get("total_outcomes", 0),
            }
        except Exception:
            v2_stats["portfolio"] = {"error": "Could not load portfolio stats"}

        v2_stats["version"] = "2.1"

        return v2_stats
