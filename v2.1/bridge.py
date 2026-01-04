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
        from cortex.briefing import generate_daily_briefing, format_briefing, format_briefing_json

        # Generate V1 briefing
        briefing_data = generate_daily_briefing(root_dir=self.root_dir)

        # Enhance with V2 data
        outcome_stats = self.get_outcome_stats(days=7)
        confidence_report = self.get_confidence_report()

        # Add V2 insights to briefing
        if hasattr(briefing_data, 'v2_insights'):
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
        self,
        project: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get smart recommendations using patterns with calibrated confidence.

        Uses V2's Bayesian calibration and temporal decay to rank recommendations.

        Args:
            project: Filter by project (optional)
            limit: Maximum recommendations to return

        Returns:
            List of recommendations with calibrated confidence
        """
        from cortex.recommendation_engine import RecommendationEngine

        # Get V1 recommendations
        engine = RecommendationEngine(root_dir=self.root_dir)
        raw_recs = engine.get_prioritized(project=project, limit=limit * 2)

        # Enhance with V2 calibration
        enhanced = []
        for rec in raw_recs:
            # Try to find matching pattern
            patterns = self.find_pattern(rec.get("title", ""))

            if patterns:
                # Use calibrated confidence from pattern
                pattern = patterns[0]
                calibrated_conf = self.get_pattern_confidence(pattern["id"])
                rec["confidence"] = calibrated_conf.get("confidence", rec.get("confidence", 0.5))
                rec["certainty"] = calibrated_conf.get("certainty", 0.0)
                rec["calibrated"] = True
            else:
                rec["calibrated"] = False

            # Apply temporal decay to confidence
            if "last_used" in rec:
                decay_result = self.decay.calculate(
                    last_used=datetime.fromisoformat(rec["last_used"]),
                    use_count=rec.get("use_count", 0)
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
        from cortex.project_scanner import ProjectScanner

        scanner = ProjectScanner(root_dir=self.root_dir)
        projects = scanner.scan_projects()

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

    def analyze_project(
        self,
        project: str,
        quick: bool = False
    ) -> Dict[str, Any]:
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
        self,
        project: Optional[str] = None,
        severity: Optional[str] = None
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
                warnings.append({
                    "type": "low_confidence_pattern",
                    "severity": "minor",
                    "message": f"Pattern '{pattern['name']}' has low confidence ({pattern['confidence']:.0%})",
                    "recommendation": "Consider reviewing or deprecating",
                    "pattern_id": pattern["id"],
                })

        # Stale memories
        stale = self.get_stale_memories(threshold=0.1)
        for memory in stale:
            warnings.append({
                "type": "stale_memory",
                "severity": "minor",
                "message": f"Memory '{memory.get('title')}' is stale (relevance: {memory.get('effective_confidence', 0):.0%})",
                "recommendation": "Consider updating or archiving",
                "memory_id": memory.get("id"),
            })

        # Filter by severity if specified
        if severity:
            warnings = [w for w in warnings if w["severity"] == severity]

        return warnings

    def get_dependencies(self, project: str) -> Dict[str, Any]:
        """Get project dependency analysis.

        Args:
            project: Project name

        Returns:
            Dependency analysis
        """
        try:
            from cortex.dependency_analyzer import DependencyAnalyzer
            analyzer = DependencyAnalyzer(root_dir=self.root_dir)
            return analyzer.analyze(project)
        except ImportError:
            return {"error": "DependencyAnalyzer not available", "project": project}

    def find_circular_dependencies(self, project: str) -> List[List[str]]:
        """Find circular dependencies in project.

        Args:
            project: Project name

        Returns:
            List of circular dependency chains
        """
        try:
            from cortex.dependency_analyzer import DependencyAnalyzer
            analyzer = DependencyAnalyzer(root_dir=self.root_dir)
            return analyzer.find_circular(project)
        except ImportError:
            return []

    def export_dependency_graph(
        self,
        project: str,
        format: str = "json"
    ) -> str:
        """Export dependency graph.

        Args:
            project: Project name
            format: Output format (json, dot, mermaid)

        Returns:
            Dependency graph in specified format
        """
        try:
            from cortex.dependency_analyzer import DependencyAnalyzer
            analyzer = DependencyAnalyzer(root_dir=self.root_dir)
            return analyzer.export(project, format=format)
        except ImportError:
            return json.dumps({"error": "DependencyAnalyzer not available"})

    def submit_batch(
        self,
        items: List[Dict[str, Any]],
        batch_type: str = "research"
    ) -> str:
        """Submit items for batch processing.

        Args:
            items: Items to process
            batch_type: Type of batch (research, briefing)

        Returns:
            Batch ID
        """
        try:
            from cortex.batch.batcher import BatchProcessor
            processor = BatchProcessor()
            return processor.submit(items, batch_type=batch_type)
        except ImportError:
            # Return mock batch ID if batcher not available
            import uuid
            return f"batch_mock_{uuid.uuid4().hex[:8]}"

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get batch processing status.

        Args:
            batch_id: Batch ID

        Returns:
            Batch status
        """
        try:
            from cortex.batch.batcher import BatchProcessor
            processor = BatchProcessor()
            return processor.get_status(batch_id)
        except ImportError:
            return {"batch_id": batch_id, "status": "unknown", "error": "BatchProcessor not available"}

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
