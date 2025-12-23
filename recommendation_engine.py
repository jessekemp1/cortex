#!/usr/bin/env python3
"""
Recommendation Engine - Generates strategic recommendations for Cortex

Combines project activity and goals to produce prioritized recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class Recommendation:
    """A strategic recommendation."""

    id: str
    title: str
    type: (
        str  # "blocker_resolution", "goal_progress", "project_health", "momentum", etc.
    )
    priority: str  # "high", "medium", "low"
    estimated_impact: str  # "high", "medium", "low"
    confidence: float  # 0.0 - 1.0
    rationale: str
    related_projects: List[str] = field(default_factory=list)
    related_goals: List[str] = field(default_factory=list)
    description: str = ""  # Detailed description with actions
    estimated_effort: str = ""  # e.g., "1-2h", "30min"
    prerequisites: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class RecommendationEngine:
    """Generates strategic recommendations based on project activity and goals."""

    def __init__(self, root_dir: Optional[Path] = None, enable_learning: bool = True, enable_pattern_memory: bool = True):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir
        self.enable_learning = enable_learning
        self.enable_pattern_memory = enable_pattern_memory

        # Initialize learning system if enabled
        if enable_learning:
            try:
                from learning import LearningSystem

                self.learning_system = LearningSystem()
            except ImportError:
                self.learning_system = None
                self.learning_system = None

        # Initialize Semantic Recommender
        try:
            from cortex.semantic_recommender import SemanticRecommender

            self.semantic_recommender = SemanticRecommender(self.root_dir)
        except ImportError:
            self.semantic_recommender = None

        # Initialize Pattern Memory (Layer 2)
        if enable_pattern_memory:
            try:
                from intelligence.memory.pattern_memory import PatternMemory

                self.pattern_memory = PatternMemory(self.root_dir)
            except ImportError:
                self.pattern_memory = None
        else:
            self.pattern_memory = None

    def generate_recommendations(
        self,
        project_activity: Optional[List[Any]] = None,
        goals: Optional[List[Any]] = None,
        limit: int = 5,
    ) -> List[Recommendation]:
        """
        Generate prioritized recommendations.

        Args:
            project_activity: List of ProjectActivity objects
            goals: List of Goal objects
            limit: Maximum number of recommendations

        Returns:
            List of Recommendation objects, sorted by priority
        """
        recommendations = []

        # 1. Blocker resolution recommendations (highest priority)
        if project_activity:
            recommendations.extend(
                self._generate_blocker_recommendations(project_activity)
            )

        # 2. Goal progress recommendations
        if goals:
            recommendations.extend(
                self._generate_goal_recommendations(goals, project_activity)
            )

        # 3. Project health recommendations
        if project_activity:
            recommendations.extend(
                self._generate_health_recommendations(project_activity)
            )

        # 4. Momentum recommendations (maintain active projects)
        if project_activity:
            recommendations.extend(
                self._generate_momentum_recommendations(project_activity)
            )

        # 5. External recommendations (injected by Antigravity/Agents)
        recommendations.extend(self._generate_external_recommendations())

        # 6. Semantic Strategy (ACTION_PLAN.md)
        if self.semantic_recommender:
            recommendations.extend(self._generate_semantic_recommendations())

        # Apply learning-based confidence adjustments
        if self.learning_system:
            recommendations = self._apply_learning_adjustments(recommendations)

        # Enrich recommendations with pattern memory (Layer 2)
        if self.pattern_memory:
            recommendations = self._enrich_with_patterns(recommendations)

        # Sort by priority score (combines priority, impact, confidence)
        recommendations.sort(key=lambda r: self._priority_score(r), reverse=True)

        # Deduplicate by similar titles
        recommendations = self._deduplicate(recommendations)

        return recommendations[:limit]

    def _apply_learning_adjustments(
        self, recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """
        Adjust recommendation confidence based on historical outcomes.

        Args:
            recommendations: List of recommendations to adjust

        Returns:
            List of recommendations with adjusted confidence scores
        """
        for rec in recommendations:
            base_confidence = rec.confidence
            adjusted_confidence, explanation = (
                self.learning_system.adjust_confidence_based_on_history(
                    recommendation_type=rec.type, base_confidence=base_confidence
                )
            )

            # Update confidence
            rec.confidence = adjusted_confidence

            # Append explanation to rationale if significantly adjusted
            if abs(adjusted_confidence - base_confidence) > 0.1:
                rec.rationale += f" {explanation}"

        return recommendations

    def _enrich_with_patterns(
        self, recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """
        Enrich recommendations with similar patterns from pattern memory.

        Args:
            recommendations: List of recommendations to enrich

        Returns:
            List of recommendations with pattern-based context added
        """
        for rec in recommendations:
            # Skip if no pattern memory available
            if not self.pattern_memory:
                continue

            # Find similar work for this recommendation
            similar_work = self.pattern_memory.find_similar_solutions(
                task=rec.title + " " + rec.description,
                current_project=rec.related_projects[0] if rec.related_projects else "",
                limit=3,
            )

            # Add similar work to description
            if similar_work and rec.description:
                pattern_context = "\n\n**Similar work from pattern memory:**\n"
                for work in similar_work[:2]:  # Limit to 2 most relevant
                    pattern_context += f"- [{work.project}] {work.title}\n"
                    if work.files_changed:
                        files = ", ".join(work.files_changed[:2])
                        pattern_context += f"  Files: {files}\n"

                rec.description += pattern_context

        return recommendations

    def _generate_blocker_recommendations(
        self, project_activity: List[Any]
    ) -> List[Recommendation]:
        """Generate recommendations for resolving blockers."""
        recommendations = []

        for project in project_activity:
            if not hasattr(project, "blockers") or not project.blockers:
                continue

            for blocker in project.blockers:
                rec_id = f"blocker_{project.name}_{hash(blocker) % 10000}"

                # Determine actions based on blocker type
                actions = self._get_blocker_actions(blocker)
                estimated_time = self._estimate_blocker_time(blocker)

                # Build description from actions
                action_text = "\n".join(f"• {a}" for a in actions)
                description = f"Next steps:\n{action_text}"

                recommendations.append(
                    Recommendation(
                        id=rec_id,
                        title=f"Resolve blocker in {project.name}: {blocker}",
                        type="blocker_resolution",
                        priority="high",
                        estimated_impact="high",
                        confidence=0.85,
                        rationale=f"Blockers prevent progress. {blocker} is blocking {project.name}.",
                        related_projects=[project.name],
                        description=description,
                        estimated_effort=estimated_time,
                    )
                )

        return recommendations

    def _generate_goal_recommendations(
        self, goals: List[Any], project_activity: Optional[List[Any]] = None
    ) -> List[Recommendation]:
        """Generate recommendations based on goals."""
        recommendations = []

        # Create project lookup for activity data
        project_lookup = {}
        if project_activity:
            project_lookup = {p.name.lower(): p for p in project_activity}

        for goal in goals:
            # Skip completed goals
            if hasattr(goal, "status") and goal.status == "completed":
                continue

            priority = getattr(goal, "priority", "B")
            status = getattr(goal, "status", "pending")
            project = getattr(goal, "project", None)

            # Determine recommendation priority based on goal priority
            rec_priority = {"A": "high", "B": "medium", "C": "low"}.get(
                priority, "medium"
            )

            # Check if goal's project is active
            project_active = False
            if project and project.lower() in project_lookup:
                proj = project_lookup[project.lower()]
                project_active = getattr(proj, "status", "") == "active"

            # Generate recommendation
            rec_id = f"goal_{hash(goal.title) % 10000}"

            if status == "in_progress":
                title = f"Continue progress on: {goal.title}"
                confidence = 0.9 if project_active else 0.75
                rationale = f"Priority {priority} goal already in progress."
            else:
                title = f"Start work on: {goal.title}"
                confidence = 0.8 if priority == "A" else 0.7
                rationale = f"Priority {priority} goal ready to start."

            # Add project context to rationale
            if project:
                if project_active:
                    rationale += f" {project} is currently active."
                else:
                    rationale += f" Related project: {project}."

            # Build description from goal actions
            goal_actions = getattr(goal, "actions", [])[:3]
            if goal_actions:
                action_text = "\n".join(f"• {a}" for a in goal_actions)
                description = f"Next steps:\n{action_text}"
            else:
                description = ""

            recommendations.append(
                Recommendation(
                    id=rec_id,
                    title=title,
                    type="goal_progress",
                    priority=rec_priority,
                    estimated_impact=rec_priority,  # Goal impact matches priority
                    confidence=confidence,
                    rationale=rationale,
                    related_projects=[project] if project else [],
                    related_goals=[goal.title],
                    description=description,
                    estimated_effort=self._estimate_goal_time(priority),
                )
            )

        return recommendations

    def _generate_health_recommendations(
        self, project_activity: List[Any]
    ) -> List[Recommendation]:
        """Generate recommendations for project health."""
        recommendations = []

        for project in project_activity:
            uncommitted = getattr(project, "uncommitted_changes", 0)
            status = getattr(project, "status", "dormant")

            # Large uncommitted changes (not already in blockers)
            if uncommitted > 10 and uncommitted <= 20:
                rec_id = f"health_uncommitted_{project.name}"
                description = """Next steps:
• Review changes: git status
• Stage changes: git add -A
• Commit with message: git commit -m 'description'"""
                recommendations.append(
                    Recommendation(
                        id=rec_id,
                        title=f"Commit changes in {project.name} ({uncommitted} files)",
                        type="project_health",
                        priority="medium",
                        estimated_impact="medium",
                        confidence=0.8,
                        rationale=f"{project.name} has {uncommitted} uncommitted changes. Regular commits help track progress.",
                        related_projects=[project.name],
                        description=description,
                        estimated_effort="15-30min",
                    )
                )

            # Dormant but important projects (check if in known important projects)
            if status == "dormant" and self._is_important_project(project.name):
                rec_id = f"health_dormant_{project.name}"
                description = """Next steps:
• Review project README and status
• Check for open issues or PRs
• Decide: continue, pause, or archive"""
                recommendations.append(
                    Recommendation(
                        id=rec_id,
                        title=f"Review dormant project: {project.name}",
                        type="project_health",
                        priority="low",
                        estimated_impact="medium",
                        confidence=0.6,
                        rationale=f"{project.name} has no recent activity. Consider if it needs attention or archiving.",
                        related_projects=[project.name],
                        description=description,
                        estimated_effort="15-30min",
                    )
                )

        return recommendations

    def _generate_momentum_recommendations(
        self, project_activity: List[Any]
    ) -> List[Recommendation]:
        """Generate recommendations to maintain momentum on active projects."""
        recommendations = []

        active_projects = [
            p for p in project_activity if getattr(p, "status", "") == "active"
        ]

        for project in active_projects[:3]:  # Limit to top 3 active
            commits_7d = getattr(project, "commits_7d", 0)
            last_msg = getattr(project, "last_commit_msg", "")

            rec_id = f"momentum_{project.name}"

            title = f"Continue momentum on {project.name}"
            rationale = f"{project.name} is active with {commits_7d} commits this week."

            if last_msg:
                rationale += (
                    f" Last: '{last_msg[:50]}...'"
                    if len(last_msg) > 50
                    else f" Last: '{last_msg}'"
                )

            description = """Next steps:
• Review recent changes
• Identify next logical step
• Continue from last commit"""
            recommendations.append(
                Recommendation(
                    id=rec_id,
                    title=title,
                    type="momentum",
                    priority="medium",
                    estimated_impact="medium",
                    confidence=0.7,
                    rationale=rationale,
                    related_projects=[project.name],
                    description=description,
                    estimated_effort="1-2h",
                )
            )

        return recommendations

    def _generate_external_recommendations(self) -> List[Recommendation]:
        """Generate recommendations from external source (e.g. Antigravity)."""
        recommendations = []
        external_file = self.root_dir / "external_recommendations.json"

        if not external_file.exists():
            return recommendations

        try:
            import json

            content = external_file.read_text()
            if not content.strip():
                return recommendations

            data = json.loads(content)
            for item in data:
                # Validate required fields
                if not all(k in item for k in ["title", "type", "priority"]):
                    continue

                recommendations.append(
                    Recommendation(
                        id=item.get("id", f"ext_{hash(item['title'])}"),
                        title=item["title"],
                        type=item["type"],
                        priority=item["priority"],
                        estimated_impact=item.get("estimated_impact", "medium"),
                        confidence=item.get("confidence", 0.9),
                        rationale=item.get("rationale", "External recommendation"),
                        related_projects=item.get("related_projects", []),
                        related_goals=item.get("related_goals", []),
                        description=item.get("description", ""),
                        estimated_effort=item.get("estimated_effort", ""),
                    )
                )
        except Exception:
            # Silently fail on read errors to avoid disrupting main flow
            pass

        return recommendations

    def _generate_semantic_recommendations(self) -> List[Recommendation]:
        """Generate recommendations from Semantic Strategy (ACTION_PLAN.md)."""
        recommendations = []
        if not self.semantic_recommender:
            return recommendations

        plan_path = self.root_dir / "ACTION_PLAN.md"
        semantic_data = self.semantic_recommender.analyze_plan(plan_path)

        for data in semantic_data:
            recommendations.append(
                Recommendation(
                    id=data["id"],
                    title=data["title"],
                    type=data["type"],
                    priority=data["priority"],
                    estimated_impact=data["estimated_impact"],
                    confidence=data["confidence"],
                    rationale=data["rationale"],
                    related_projects=data["related_projects"],
                    description=data["description"],
                    estimated_effort=data["estimated_effort"],
                )
            )

        return recommendations

    def _get_blocker_actions(self, blocker: str) -> List[str]:
        """Get specific actions based on blocker type."""
        blocker_lower = blocker.lower()

        if "uncommitted" in blocker_lower:
            return [
                "Run: git status",
                "Review changes and stage: git add -A",
                "Commit: git commit -m 'description'",
            ]
        elif ".env" in blocker_lower:
            return [
                "Copy example: cp .env.example .env",
                "Fill in required values",
                "Verify configuration",
            ]
        elif "virtualenv" in blocker_lower or "venv" in blocker_lower:
            return [
                "Create venv: python -m venv venv",
                "Activate: source venv/bin/activate",
                "Install deps: pip install -r requirements.txt",
            ]
        elif "node_modules" in blocker_lower or "npm" in blocker_lower:
            return [
                "Install dependencies: npm install",
                "Verify installation",
                "Run: npm start (or npm test)",
            ]
        elif "merge conflict" in blocker_lower:
            return [
                "Identify conflicted files: git diff --name-only --diff-filter=U",
                "Resolve conflicts in each file",
                "Stage resolved files: git add <file>",
                "Complete merge: git commit",
            ]
        elif "detached" in blocker_lower:
            return [
                "Check current state: git status",
                "Create branch: git checkout -b branch-name",
                "Or return to main: git checkout main",
            ]
        else:
            return [
                f"Investigate: {blocker}",
                "Identify root cause",
                "Resolve and verify",
            ]

    def _estimate_blocker_time(self, blocker: str) -> str:
        """Estimate time to resolve a blocker."""
        blocker_lower = blocker.lower()

        if "uncommitted" in blocker_lower:
            return "15-30min"
        elif ".env" in blocker_lower:
            return "10-15min"
        elif "virtualenv" in blocker_lower or "venv" in blocker_lower:
            return "10-15min"
        elif "node_modules" in blocker_lower:
            return "5-10min"
        elif "merge conflict" in blocker_lower:
            return "30min-1h"
        else:
            return "30min-1h"

    def _estimate_goal_time(self, priority: str) -> str:
        """Estimate time for a goal based on priority."""
        return {"A": "2-4h", "B": "1-2h", "C": "30min-1h"}.get(priority, "1-2h")

    def _is_important_project(self, project_name: str) -> bool:
        """Check if project is in the important projects list."""
        important = {
            "vortexv2",
            "alpha_arena",
            "personal-ai-dataset",
            "cortex",
            "keto-tracker",
            "windfield",
            "vortex",
            "local-orchestrator",
        }
        return project_name.lower() in important

    def _priority_score(self, rec: Recommendation) -> float:
        """Calculate priority score for sorting."""
        priority_weight = {"high": 3.0, "medium": 2.0, "low": 1.0}
        impact_weight = {"high": 1.5, "medium": 1.0, "low": 0.5}

        base_score = priority_weight.get(rec.priority, 1.0)
        impact_score = impact_weight.get(rec.estimated_impact, 1.0)

        # Type weights (blockers are most important)
        type_weights = {
            "blocker_resolution": 2.0,
            "goal_progress": 1.5,
            "project_health": 1.0,
            "momentum": 0.8,
        }
        type_score = type_weights.get(rec.type, 1.0)

        return base_score * impact_score * type_score * rec.confidence

    def _deduplicate(
        self, recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """Remove duplicate recommendations based on similar titles."""
        seen = set()
        unique = []

        for rec in recommendations:
            # Create a simplified key from title
            key = rec.title.lower()[:50]  # First 50 chars

            if key not in seen:
                seen.add(key)
                unique.append(rec)

        return unique


def main():
    """CLI for testing recommendation engine."""
    import argparse
    import json

    # Import project scanner and goal parser for testing
    try:
        from ai_intelligence import ProjectScanner
        from goal_parser import GoalParser
    except ImportError:
        print("Warning: Could not import ai_intelligence or goal_parser")
        ProjectScanner = None
        GoalParser = None

    parser = argparse.ArgumentParser(description="Generate strategic recommendations")
    parser.add_argument(
        "--root", default="/Users/jesse.kemp/Dev", help="Root directory"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--limit", type=int, default=5, help="Max recommendations")
    args = parser.parse_args()

    # Get project activity
    project_activity = []
    if ProjectScanner:
        scanner = ProjectScanner(args.root)
        repos = scanner.find_git_repos()
        project_activity = [scanner.analyze_project(repo) for repo in repos]

    # Get goals
    goals = []
    if GoalParser:
        goal_parser = GoalParser()
        goals = goal_parser.parse()

    # Generate recommendations
    engine = RecommendationEngine(Path(args.root))
    recommendations = engine.generate_recommendations(
        project_activity=project_activity, goals=goals, limit=args.limit
    )

    if args.json:
        output = []
        for r in recommendations:
            output.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "priority": r.priority,
                    "estimated_impact": r.estimated_impact,
                    "confidence": r.confidence,
                    "rationale": r.rationale,
                    "related_projects": r.related_projects,
                    "related_goals": r.related_goals,
                    "description": r.description,
                    "estimated_effort": r.estimated_effort,
                }
            )
        print(json.dumps(output, indent=2))
    else:
        print(f"Generated {len(recommendations)} recommendations\n")

        for i, rec in enumerate(recommendations, 1):
            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                rec.priority, "⚪"
            )
            print(f"{i}. {priority_icon} {rec.title}")
            print(
                f"   Type: {rec.type} | Priority: {rec.priority} | Confidence: {rec.confidence:.0%}"
            )
            print(f"   Rationale: {rec.rationale}")
            if rec.description:
                print(f"   {rec.description}")
            if rec.estimated_effort:
                print(f"   Estimated: {rec.estimated_effort}")
            print()


if __name__ == "__main__":
    main()
