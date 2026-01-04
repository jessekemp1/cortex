"""
Cortex V2 Bridge - Unified interface for V2 intelligence features.

Integrates:
- Graph Memory (relationships between memories)
- Outcome Detection (automatic learning from git/CI/tests)
- Typed Memory Store (patterns, incidents, skills, decisions)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory.graph import GraphMemory
from .memory.store import TypedMemoryStore
from .memory.types import Pattern, Incident, Skill, Decision
from .memory.models import MemoryType, RelationType
from .learning.outcomes import OutcomeDetector, OutcomeType, OutcomeSource
from .learning.calibration import ConfidenceCalibrator
from .learning.skills import SkillExtractor
from .memory.decay import TemporalDecay
from .integrations.git_hooks import GitHookInstaller


class CortexV2Bridge:
    """Unified interface for Cortex V2 intelligence features.

    Features:
    - Graph-based memory with relationships
    - Automatic outcome detection from git/CI/tests
    - Intent-aware typed memory retrieval
    - Pattern-outcome correlation
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize V2 Bridge.

        Args:
            data_dir: Directory for V2 data. Defaults to ~/.claude/v2/
        """
        if data_dir is None:
            data_dir = Path.home() / ".claude" / "v2"

        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir

        # Initialize components
        self.graph = GraphMemory(db_path=data_dir / "graph.db")
        self.store = TypedMemoryStore(data_dir=data_dir)
        self.outcomes = OutcomeDetector(data_dir=data_dir)
        self.hook_installer = GitHookInstaller(cortex_path=data_dir.parent)

        # Tier 2 components
        self.decay = TemporalDecay()
        self.calibrator = ConfidenceCalibrator(graph=self.graph, outcomes=self.outcomes)
        self.skill_extractor = SkillExtractor(detector=self.outcomes, store=self.store)

    # === Memory Operations ===

    def add_pattern(
        self,
        title: str,
        problem: str,
        solution: str,
        projects: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        context: str = ""
    ) -> Dict[str, Any]:
        """Add a pattern to memory.

        Args:
            title: Pattern title
            problem: Problem it solves
            solution: How it solves it
            projects: Associated projects
            tags: Tags for categorization
            context: Additional context

        Returns:
            Created pattern with ID
        """
        pattern = Pattern.create(
            title=title,
            problem=problem,
            solution=solution,
            projects=projects or [],
            tags=tags or [],
            context=context
        )

        self.store.add(pattern)

        # Add to graph
        node = self.graph.add_node(
            type=MemoryType.PATTERN,
            name=title,
            data=pattern.to_dict()
        )

        # Link to projects
        for project in (projects or []):
            self._ensure_project_node(project)
            project_nodes = self.graph.find_nodes(
                type=MemoryType.PROJECT,
                name_contains=project
            )
            if project_nodes:
                self.graph.add_edge(
                    from_id=project_nodes[0].id,
                    to_id=node.id,
                    relation=RelationType.USES
                )

        return {
            "id": pattern.id,
            "graph_node_id": node.id,
            "title": title,
            "success": True
        }

    def add_incident(
        self,
        title: str,
        what_happened: str,
        root_cause: str,
        resolution: str,
        severity: str = "minor",
        projects: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add an incident to memory.

        Args:
            title: Incident title
            what_happened: What happened
            root_cause: Root cause analysis
            resolution: How it was resolved
            severity: critical/major/minor
            projects: Affected projects

        Returns:
            Created incident with ID
        """
        incident = Incident.create(
            title=title,
            what_happened=what_happened,
            root_cause=root_cause,
            resolution=resolution,
            severity=severity,
            projects=projects or []
        )

        self.store.add(incident)

        # Add to graph
        node = self.graph.add_node(
            type=MemoryType.INCIDENT,
            name=title,
            data=incident.to_dict()
        )

        return {
            "id": incident.id,
            "graph_node_id": node.id,
            "title": title,
            "success": True
        }

    def add_skill(
        self,
        title: str,
        steps: List[str],
        projects: Optional[List[str]] = None,
        prerequisites: Optional[List[str]] = None,
        difficulty: str = "medium",
        estimated_time: str = ""
    ) -> Dict[str, Any]:
        """Add a skill (how-to) to memory.

        Args:
            title: Skill title
            steps: Steps to perform
            projects: Associated projects
            prerequisites: Required prerequisites
            difficulty: easy/medium/hard
            estimated_time: Estimated time

        Returns:
            Created skill with ID
        """
        skill = Skill.create(
            title=title,
            steps=steps,
            projects=projects or [],
            prerequisites=prerequisites or [],
            difficulty=difficulty,
            estimated_time=estimated_time
        )

        self.store.add(skill)

        # Add to graph
        node = self.graph.add_node(
            type=MemoryType.SKILL,
            name=title,
            data=skill.to_dict()
        )

        return {
            "id": skill.id,
            "graph_node_id": node.id,
            "title": title,
            "success": True
        }

    def add_decision(
        self,
        title: str,
        question: str,
        chosen_option: str,
        alternatives: List[str],
        rationale: str,
        projects: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Add a decision to memory.

        Args:
            title: Decision title
            question: The question being decided
            chosen_option: What was chosen
            alternatives: Options considered
            rationale: Why this was chosen
            projects: Associated projects

        Returns:
            Created decision with ID
        """
        decision = Decision.create(
            title=title,
            question=question,
            chosen_option=chosen_option,
            alternatives=alternatives,
            rationale=rationale,
            projects=projects or []
        )

        self.store.add(decision)

        # Add to graph
        node = self.graph.add_node(
            type=MemoryType.DECISION,
            name=title,
            data=decision.to_dict()
        )

        return {
            "id": decision.id,
            "graph_node_id": node.id,
            "title": title,
            "success": True
        }

    # === Query Operations ===

    def query(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Smart query with intent detection.

        The query is analyzed to determine what type of memory to search:
        - "how do I..." -> skills, patterns
        - "why did we..." -> decisions, incidents
        - "what went wrong..." -> incidents
        - "best way to..." -> patterns

        Args:
            query: Natural language query
            project: Optional project filter
            limit: Maximum results

        Returns:
            List of matching memories
        """
        results = self.store.query(
            query=query,
            projects=[project] if project else None,
            limit=limit
        )

        return [m.to_dict() for m in results]

    def find_pattern(self, problem: str, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a pattern that solves a problem."""
        pattern = self.store.find_pattern(problem, project)
        return pattern.to_dict() if pattern else None

    def find_skill(self, task: str, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a skill for a task."""
        skill = self.store.find_skill(task, project)
        return skill.to_dict() if skill else None

    def find_incident(self, symptom: str, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a past incident by symptom."""
        incident = self.store.find_incident(symptom, project)
        return incident.to_dict() if incident else None

    def find_decision(self, topic: str, project: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a past decision on a topic."""
        decision = self.store.find_decision(topic, project)
        return decision.to_dict() if decision else None

    # === Relationship Operations ===

    def link_memories(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        weight: float = 1.0
    ) -> Dict[str, Any]:
        """Link two memories with a relationship.

        Args:
            from_id: Source memory graph node ID
            to_id: Target memory graph node ID
            relation: Relationship type (uses, similar_to, validates, caused_by, etc.)
            weight: Relationship strength (0-1)

        Returns:
            Created edge info
        """
        relation_type = RelationType(relation)
        edge = self.graph.add_edge(
            from_id=from_id,
            to_id=to_id,
            relation=relation_type,
            weight=weight
        )

        return {
            "edge_id": edge.id,
            "from_id": from_id,
            "to_id": to_id,
            "relation": relation,
            "success": True
        }

    def get_related(
        self,
        memory_id: str,
        relation: Optional[str] = None,
        direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """Get memories related to a given memory.

        Args:
            memory_id: Graph node ID
            relation: Optional relation type filter
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of related memories
        """
        relation_type = RelationType(relation) if relation else None

        results = self.graph.get_related(
            node_id=memory_id,
            relation=relation_type,
            direction=direction
        )

        return [
            {
                "node": r.node.__dict__,
                "path": [e.__dict__ for e in r.path] if r.path else [],
                "distance": r.distance,
                "relevance": r.relevance
            }
            for r in results
        ]

    def get_patterns_for_project(self, project: str) -> List[Dict[str, Any]]:
        """Get all patterns used by a project."""
        project_nodes = self.graph.find_nodes(
            type=MemoryType.PROJECT,
            name_contains=project
        )

        if not project_nodes:
            return []

        patterns = self.graph.get_patterns_for_project(project_nodes[0].id)
        return [p.__dict__ for p in patterns]

    # === Outcome Operations ===

    def record_git_outcome(
        self,
        commit_hash: str,
        message: str,
        branch: str,
        files_changed: int,
        project: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a git commit outcome.

        Automatically detects success/failure/WIP from commit message.
        """
        outcome = self.outcomes.record_git_outcome(
            commit_hash=commit_hash,
            message=message,
            branch=branch,
            files_changed=files_changed,
            project=project
        )

        return outcome.to_dict()

    def record_ci_outcome(
        self,
        repo: str,
        workflow: str,
        conclusion: str,
        commit: str,
        branch: str,
        duration_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """Record a CI/CD pipeline outcome."""
        outcome = self.outcomes.record_ci_outcome(
            repo=repo,
            workflow=workflow,
            conclusion=conclusion,
            commit=commit,
            branch=branch,
            duration_ms=duration_ms
        )

        return outcome.to_dict()

    def record_test_outcome(
        self,
        project: str,
        passed: int,
        failed: int,
        skipped: int = 0,
        duration_seconds: float = 0,
        commit: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a test run outcome."""
        outcome = self.outcomes.record_test_outcome(
            project=project,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration_seconds,
            commit=commit
        )

        return outcome.to_dict()

    def detect_outcomes_from_git(
        self,
        repo_path: Path,
        since_days: int = 7
    ) -> List[Dict[str, Any]]:
        """Detect outcomes from recent git history."""
        outcomes = self.outcomes.detect_from_git_log(
            repo_path=repo_path,
            since_days=since_days
        )

        return [o.to_dict() for o in outcomes]

    def get_recent_outcomes(
        self,
        project: Optional[str] = None,
        days: int = 7,
        outcome_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent detected outcomes."""
        ot = OutcomeType(outcome_type) if outcome_type else None

        outcomes = self.outcomes.get_recent_outcomes(
            project=project,
            days=days,
            outcome_type=ot
        )

        return [o.to_dict() for o in outcomes]

    def get_outcome_stats(
        self,
        project: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get outcome statistics."""
        return self.outcomes.get_outcome_stats(project=project, days=days)

    def correlate_outcome_to_pattern(self, outcome_id: str) -> Optional[str]:
        """Try to correlate an outcome to a known pattern.

        Returns pattern ID if correlation found.
        """
        # Find the outcome
        for outcome in self.outcomes._outcomes:
            if outcome.id == outcome_id:
                return self.outcomes.correlate_to_pattern(outcome, self.graph)
        return None

    # === Git Hook Operations ===

    def install_git_hooks(self, repo_path: Path, force: bool = False) -> Dict[str, Any]:
        """Install git hooks for automatic outcome detection."""
        success = self.hook_installer.install(repo_path, force=force)
        return {
            "success": success,
            "repo": str(repo_path),
            "message": "Git hooks installed" if success else "Failed to install hooks"
        }

    def install_all_git_hooks(self, root_dir: Path, force: bool = False) -> Dict[str, Any]:
        """Install git hooks in all repositories under a directory."""
        results = self.hook_installer.install_all(root_dir, force=force)
        return {
            "installed": results["installed"],
            "skipped": results["skipped"],
            "failed": results["failed"],
            "total": results["installed"] + results["skipped"] + results["failed"]
        }

    # === Tier 2: Temporal Decay ===

    def get_stale_memories(
        self,
        threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Get memories that have decayed below a threshold.

        Args:
            threshold: Decay factor threshold (0-1). Memories with decay < threshold are stale.

        Returns:
            List of stale memories with their decay factors
        """
        all_memories = (
            self.store.patterns +
            self.store.incidents +
            self.store.skills +
            self.store.decisions
        )

        stale = self.decay.get_stale_memories(all_memories, threshold=threshold)

        results = []
        for memory in stale:
            result = self.decay.calculate_decay_result(memory)
            results.append({
                "id": memory.id,
                "title": memory.title,
                "type": memory.__class__.__name__.lower(),
                "decay_factor": result.decay_factor,
                "days_since_use": result.days_since_use,
                "use_count": memory.use_count,
                "recommendation": result.recommendation
            })

        return results

    def apply_decay_to_query(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Query with temporal decay applied.

        Fresh, frequently-used memories rank higher than old, unused ones.
        """
        results = self.store.query(
            query=query,
            projects=[project] if project else None,
            limit=limit,
            apply_decay=True
        )

        return [
            {
                **m.to_dict(),
                "effective_confidence": m.effective_confidence
            }
            for m in results
        ]

    # === Tier 2: ML Confidence Calibration ===

    def recalibrate_confidence(
        self,
        project: Optional[str] = None
    ) -> Dict[str, Any]:
        """Recalibrate confidence for all patterns based on outcomes.

        Uses Bayesian Beta-Binomial model to adjust confidence based on
        actual success/failure rates.

        Args:
            project: Optional project filter

        Returns:
            Calibration results with old/new confidence values
        """
        results = self.calibrator.recalibrate_all(project=project)

        return {
            "calibrated": len(results),
            "patterns": [
                {
                    "id": r.pattern_id,
                    "name": r.pattern_name,
                    "old_confidence": r.old_confidence,
                    "new_confidence": r.new_confidence,
                    "delta": r.delta,
                    "certainty": r.certainty,
                    "outcomes": r.outcome_stats.total
                }
                for r in results.values()
            ]
        }

    def get_confidence_report(
        self,
        project: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a confidence calibration report.

        Shows distribution of pattern confidence and recommendations.
        """
        return self.calibrator.get_confidence_report(project=project)

    def get_pattern_confidence(
        self,
        pattern_id: str,
        project: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get calibrated confidence for a specific pattern.

        Args:
            pattern_id: Pattern graph node ID
            project: Optional project filter

        Returns:
            Confidence data with certainty and outcome stats
        """
        result = self.calibrator.calculate_for_pattern(pattern_id, project)
        return {
            "pattern_id": result.pattern_id,
            "pattern_name": result.pattern_name,
            "confidence": result.new_confidence,
            "certainty": result.certainty,
            "outcomes": {
                "successes": result.outcome_stats.successes,
                "failures": result.outcome_stats.failures,
                "partial": result.outcome_stats.partial,
                "total": result.outcome_stats.total
            }
        }

    # === Tier 2: Skill Extraction ===

    def extract_skills(
        self,
        days: int = 7,
        project: Optional[str] = None,
        save: bool = False
    ) -> List[Dict[str, Any]]:
        """Extract skills from recent successful outcome sequences.

        Analyzes commit sequences to find repeatable patterns of work.

        Args:
            days: Look back this many days
            project: Optional project filter
            save: If True, save extracted skills to store

        Returns:
            List of extracted skills
        """
        skills = self.skill_extractor.extract_from_recent(days=days, project=project)

        results = []
        for skill in skills:
            if save:
                saved = self.skill_extractor.save_as_skill(skill)
                results.append({
                    **skill.to_dict(),
                    "saved": True,
                    "stored_id": saved.id
                })
            else:
                results.append(skill.to_dict())

        return results

    # === Statistics ===

    def stats(self) -> Dict[str, Any]:
        """Get comprehensive V2 statistics."""
        store_stats = self.store.stats()
        graph_stats = self.graph.stats()
        outcome_stats = self.outcomes.get_outcome_stats()

        return {
            "memory": store_stats,
            "graph": graph_stats,
            "outcomes": outcome_stats,
            "data_dir": str(self.data_dir)
        }

    # === Helper Methods ===

    def _ensure_project_node(self, project: str):
        """Ensure a project node exists in the graph."""
        existing = self.graph.find_nodes(
            type=MemoryType.PROJECT,
            name_contains=project
        )

        if not existing:
            self.graph.add_node(
                type=MemoryType.PROJECT,
                name=project,
                data={"created_at": datetime.utcnow().isoformat()}
            )


def main():
    """CLI for V2 Bridge."""
    import argparse

    parser = argparse.ArgumentParser(description="Cortex V2 Bridge CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # query
    query_parser = subparsers.add_parser("query", help="Smart query")
    query_parser.add_argument("query", help="Natural language query")
    query_parser.add_argument("--project", help="Filter by project")
    query_parser.add_argument("--limit", type=int, default=10)

    # add-pattern
    pattern_parser = subparsers.add_parser("add-pattern", help="Add a pattern")
    pattern_parser.add_argument("--title", required=True)
    pattern_parser.add_argument("--problem", required=True)
    pattern_parser.add_argument("--solution", required=True)
    pattern_parser.add_argument("--projects", nargs="+", default=[])

    # add-skill
    skill_parser = subparsers.add_parser("add-skill", help="Add a skill")
    skill_parser.add_argument("--title", required=True)
    skill_parser.add_argument("--steps", nargs="+", required=True)
    skill_parser.add_argument("--projects", nargs="+", default=[])

    # add-incident
    incident_parser = subparsers.add_parser("add-incident", help="Add an incident")
    incident_parser.add_argument("--title", required=True)
    incident_parser.add_argument("--what-happened", required=True)
    incident_parser.add_argument("--root-cause", required=True)
    incident_parser.add_argument("--resolution", required=True)
    incident_parser.add_argument("--severity", default="medium")
    incident_parser.add_argument("--projects", nargs="+", default=[])

    # add-decision
    decision_parser = subparsers.add_parser("add-decision", help="Add a decision")
    decision_parser.add_argument("--title", required=True)
    decision_parser.add_argument("--question", required=True)
    decision_parser.add_argument("--chosen", required=True)
    decision_parser.add_argument("--alternatives", nargs="+", required=True)
    decision_parser.add_argument("--rationale", required=True)
    decision_parser.add_argument("--projects", nargs="+", default=[])

    # outcomes
    outcomes_parser = subparsers.add_parser("outcomes", help="Outcome operations")
    outcomes_sub = outcomes_parser.add_subparsers(dest="outcomes_cmd")

    # outcomes recent
    recent_parser = outcomes_sub.add_parser("recent", help="Get recent outcomes")
    recent_parser.add_argument("--project", help="Filter by project")
    recent_parser.add_argument("--days", type=int, default=7)

    # outcomes stats
    stats_parser = outcomes_sub.add_parser("stats", help="Get outcome stats")
    stats_parser.add_argument("--project", help="Filter by project")

    # outcomes detect
    detect_parser = outcomes_sub.add_parser("detect", help="Detect from git")
    detect_parser.add_argument("repo_path", help="Repository path")
    detect_parser.add_argument("--days", type=int, default=7)

    # hooks
    hooks_parser = subparsers.add_parser("hooks", help="Git hook operations")
    hooks_sub = hooks_parser.add_subparsers(dest="hooks_cmd")

    # hooks install
    install_parser = hooks_sub.add_parser("install", help="Install git hooks")
    install_parser.add_argument("repo_path", help="Repository path")
    install_parser.add_argument("--force", action="store_true")

    # hooks install-all
    install_all_parser = hooks_sub.add_parser("install-all", help="Install in all repos")
    install_all_parser.add_argument("root_dir", help="Root directory")
    install_all_parser.add_argument("--force", action="store_true")

    # stats
    subparsers.add_parser("stats", help="Get V2 statistics")

    args = parser.parse_args()
    bridge = CortexV2Bridge()

    if args.command == "query":
        result = bridge.query(args.query, project=args.project, limit=args.limit)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "add-pattern":
        result = bridge.add_pattern(
            title=args.title,
            problem=args.problem,
            solution=args.solution,
            projects=args.projects
        )
        print(json.dumps(result, indent=2))

    elif args.command == "add-skill":
        result = bridge.add_skill(
            title=args.title,
            steps=args.steps,
            projects=args.projects
        )
        print(json.dumps(result, indent=2))

    elif args.command == "add-incident":
        result = bridge.add_incident(
            title=args.title,
            what_happened=args.what_happened,
            root_cause=args.root_cause,
            resolution=args.resolution,
            severity=args.severity,
            projects=args.projects
        )
        print(json.dumps(result, indent=2))

    elif args.command == "add-decision":
        result = bridge.add_decision(
            title=args.title,
            question=args.question,
            chosen_option=args.chosen,
            alternatives=args.alternatives,
            rationale=args.rationale,
            projects=args.projects
        )
        print(json.dumps(result, indent=2))

    elif args.command == "outcomes":
        if args.outcomes_cmd == "recent":
            result = bridge.get_recent_outcomes(
                project=args.project,
                days=args.days
            )
            print(json.dumps(result, indent=2, default=str))
        elif args.outcomes_cmd == "stats":
            result = bridge.get_outcome_stats(project=args.project)
            print(json.dumps(result, indent=2))
        elif args.outcomes_cmd == "detect":
            result = bridge.detect_outcomes_from_git(
                repo_path=Path(args.repo_path),
                since_days=args.days
            )
            print(json.dumps(result, indent=2, default=str))

    elif args.command == "hooks":
        if args.hooks_cmd == "install":
            result = bridge.install_git_hooks(
                repo_path=Path(args.repo_path),
                force=args.force
            )
            print(json.dumps(result, indent=2))
        elif args.hooks_cmd == "install-all":
            result = bridge.install_all_git_hooks(
                root_dir=Path(args.root_dir),
                force=args.force
            )
            print(json.dumps(result, indent=2))

    elif args.command == "stats":
        result = bridge.stats()
        print(json.dumps(result, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
