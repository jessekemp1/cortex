"""
Planner - Converts recommendations into executable plans.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from intelligence.planning.models import (
    Plan,
    PlanStep,
    PlanStatus,
    StepStatus,
    PlanPriority
)


class Planner:
    """
    Converts recommendations into actionable execution plans.

    Takes high-level recommendations and breaks them down into
    concrete steps with dependencies, time estimates, and validation criteria.
    """

    def __init__(self):
        """Initialize the planner."""
        pass

    def create_plan_from_recommendations(
        self,
        recommendations: List[Any],
        title: str = None,
        description: str = None,
        priority: PlanPriority = PlanPriority.MEDIUM
    ) -> Plan:
        """
        Create a plan from a list of recommendations.

        Args:
            recommendations: List of Recommendation objects
            title: Plan title (auto-generated if None)
            description: Plan description (auto-generated if None)
            priority: Plan priority

        Returns:
            Plan object with steps
        """
        if not recommendations:
            raise ValueError("Cannot create plan from empty recommendations")

        # Auto-generate title and description if not provided
        if title is None:
            if len(recommendations) == 1:
                title = f"Execute: {recommendations[0].title}"
            else:
                title = f"Execute {len(recommendations)} recommendations"

        if description is None:
            rec_titles = [r.title for r in recommendations[:3]]
            if len(recommendations) > 3:
                rec_titles.append(f"and {len(recommendations) - 3} more")
            description = "Plan to execute:\n" + "\n".join(f"- {t}" for t in rec_titles)

        # Determine overall priority from recommendations
        if hasattr(recommendations[0], 'priority'):
            max_priority = max(r.priority for r in recommendations if hasattr(r, 'priority'))
            if max_priority >= 90:
                priority = PlanPriority.CRITICAL
            elif max_priority >= 70:
                priority = PlanPriority.HIGH
            elif max_priority >= 40:
                priority = PlanPriority.MEDIUM
            else:
                priority = PlanPriority.LOW

        # Create plan
        plan = Plan(
            id=self._generate_plan_id(),
            title=title,
            description=description,
            priority=priority,
            status=PlanStatus.DRAFT,
        )

        # Convert each recommendation to steps
        for i, rec in enumerate(recommendations):
            steps = self._recommendation_to_steps(rec, prefix=f"{i+1}")
            for step in steps:
                plan.add_step(step)

        return plan

    def create_custom_plan(
        self,
        title: str,
        description: str,
        steps_config: List[Dict[str, Any]],
        priority: PlanPriority = PlanPriority.MEDIUM,
        tags: List[str] = None
    ) -> Plan:
        """
        Create a custom plan from step configurations.

        Args:
            title: Plan title
            description: Plan description
            steps_config: List of step configurations (dicts)
            priority: Plan priority
            tags: Plan tags

        Returns:
            Plan object
        """
        plan = Plan(
            id=self._generate_plan_id(),
            title=title,
            description=description,
            priority=priority,
            status=PlanStatus.DRAFT,
            tags=tags or [],
        )

        for i, step_config in enumerate(steps_config):
            step = PlanStep(
                id=step_config.get('id', f"step-{i+1}"),
                title=step_config['title'],
                description=step_config.get('description', ''),
                estimated_time=step_config.get('estimated_time'),
                dependencies=step_config.get('dependencies', []),
                files=step_config.get('files', []),
                validation=step_config.get('validation'),
                notes=step_config.get('notes', ''),
            )
            plan.add_step(step)

        return plan

    def _recommendation_to_steps(
        self,
        recommendation: Any,
        prefix: str = ""
    ) -> List[PlanStep]:
        """
        Convert a single recommendation to plan steps.

        Args:
            recommendation: Recommendation object
            prefix: Step ID prefix

        Returns:
            List of PlanStep objects
        """
        steps = []

        # If recommendation already has steps, use them
        if hasattr(recommendation, 'steps') and recommendation.steps:
            for i, step_desc in enumerate(recommendation.steps):
                step_id = f"{prefix}.{i+1}" if prefix else f"step-{i+1}"
                steps.append(
                    PlanStep(
                        id=step_id,
                        title=f"{recommendation.title} - Step {i+1}",
                        description=step_desc,
                        estimated_time=self._estimate_step_time(step_desc),
                        files=recommendation.files if hasattr(recommendation, 'files') else [],
                    )
                )
        else:
            # Create a single step from the recommendation
            step_id = f"{prefix}.1" if prefix else "step-1"
            steps.append(
                PlanStep(
                    id=step_id,
                    title=recommendation.title,
                    description=recommendation.description if hasattr(recommendation, 'description') else recommendation.title,
                    estimated_time=self._estimate_step_time(recommendation.title),
                    files=recommendation.files if hasattr(recommendation, 'files') else [],
                )
            )

        return steps

    def _estimate_step_time(self, description: str) -> int:
        """
        Estimate time for a step based on description.

        Args:
            description: Step description

        Returns:
            Estimated time in minutes
        """
        # Simple heuristic-based estimation
        desc_lower = description.lower()

        # Keywords indicating complexity/time
        if any(word in desc_lower for word in ['refactor', 'migrate', 'redesign', 'rebuild']):
            return 120  # 2 hours
        elif any(word in desc_lower for word in ['implement', 'create', 'add', 'build']):
            return 60   # 1 hour
        elif any(word in desc_lower for word in ['update', 'modify', 'change', 'fix']):
            return 30   # 30 minutes
        elif any(word in desc_lower for word in ['test', 'verify', 'validate']):
            return 15   # 15 minutes
        else:
            return 45   # Default: 45 minutes

    def _generate_plan_id(self) -> str:
        """Generate a unique plan ID."""
        timestamp = datetime.now().strftime('%Y%m%d')
        unique = str(uuid.uuid4())[:8]
        return f"plan-{timestamp}-{unique}"

    def add_validation_criteria(self, plan: Plan, validations: Dict[str, str]):
        """
        Add validation criteria to plan steps.

        Args:
            plan: Plan to update
            validations: Dict mapping step IDs to validation criteria
        """
        for step in plan.steps:
            if step.id in validations:
                step.validation = validations[step.id]

    def add_dependencies(self, plan: Plan, dependencies: Dict[str, List[str]]):
        """
        Add dependencies between steps.

        Args:
            plan: Plan to update
            dependencies: Dict mapping step IDs to lists of dependency IDs
        """
        for step in plan.steps:
            if step.id in dependencies:
                step.dependencies = dependencies[step.id]

    def optimize_plan_order(self, plan: Plan):
        """
        Optimize step order based on dependencies and priorities.

        This reorders steps to maximize parallel execution opportunities
        while respecting dependencies.

        Args:
            plan: Plan to optimize
        """
        # Build dependency graph
        dep_graph = {step.id: set(step.dependencies) for step in plan.steps}

        # Topological sort with priority consideration
        ordered_steps = []
        available = [s for s in plan.steps if not s.dependencies]
        remaining = [s for s in plan.steps if s.dependencies]

        while available:
            # Sort available by estimated time (shortest first for quick wins)
            available.sort(key=lambda s: s.estimated_time or 0)
            current = available.pop(0)
            ordered_steps.append(current)

            # Update remaining steps
            new_available = []
            new_remaining = []

            for step in remaining:
                if current.id in step.dependencies:
                    step.dependencies.remove(current.id)

                if not step.dependencies:
                    new_available.append(step)
                else:
                    new_remaining.append(step)

            available.extend(new_available)
            remaining = new_remaining

        plan.steps = ordered_steps

    def estimate_completion_date(self, plan: Plan, hours_per_day: int = 4) -> datetime:
        """
        Estimate when the plan will be completed.

        Args:
            plan: Plan to estimate
            hours_per_day: Available work hours per day

        Returns:
            Estimated completion datetime
        """
        total_minutes = plan.estimated_total_time or 0
        total_hours = total_minutes / 60
        days_needed = total_hours / hours_per_day

        from datetime import timedelta
        completion_date = datetime.now() + timedelta(days=days_needed)

        return completion_date
