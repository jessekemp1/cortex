"""
Smart Recommendation Generator - Layer 4 of Cortex Intelligence Stack.

Integrates Layers 1, 2, 3 to generate actionable, context-aware recommendations.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class RecommendationType(Enum):
    """Types of recommendations."""

    ALERT_RESPONSE = "alert_response"
    GOAL_PROGRESS = "goal_progress"
    HEALTH_IMPROVEMENT = "health_improvement"
    PATTERN_BASED = "pattern_based"
    PROACTIVE = "proactive"


class Priority(Enum):
    """Recommendation priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Confidence(Enum):
    """Confidence levels for recommendations."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FileGuidance:
    """Guidance for specific files."""

    file_path: str
    action: str  # "modify", "create", "review", "delete"
    reason: str
    priority: Priority = Priority.MEDIUM
    estimated_effort: str = "unknown"
    related_files: List[str] = field(default_factory=list)


@dataclass
class Step:
    """A concrete action step."""

    order: int
    description: str
    command: Optional[str] = None
    success_criteria: Optional[str] = None
    estimated_time: Optional[str] = None


@dataclass
class SimilarWork:
    """Reference to similar past work."""

    pattern_id: str
    description: str
    files_changed: List[str]
    lessons: List[str]
    relevance_score: float


@dataclass
class Recommendation:
    """A smart recommendation with full context."""

    id: str
    type: RecommendationType
    title: str
    description: str
    priority: Priority
    confidence: Confidence

    # Actionable guidance
    steps: List[Step] = field(default_factory=list)
    file_guidance: List[FileGuidance] = field(default_factory=list)

    # Intelligence context
    similar_work: List[SimilarWork] = field(default_factory=list)
    intelligence_context: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    source_alerts: List[str] = field(default_factory=list)
    source_goals: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    # Tracking
    estimated_impact: str = "unknown"
    tags: List[str] = field(default_factory=list)


@dataclass
class Alert:
    """Represents an alert from Layer 3."""

    id: str
    type: str
    severity: str
    message: str
    project_id: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Goal:
    """Represents a project goal."""

    id: str
    name: str
    target_value: float
    current_value: float
    metric_type: str
    deadline: Optional[datetime] = None


@dataclass
class ProjectActivity:
    """Recent project activity data."""

    project_id: str
    recent_commits: List[Dict[str, Any]] = field(default_factory=list)
    recent_files: List[str] = field(default_factory=list)
    critical_files: List[str] = field(default_factory=list)
    active_branches: List[str] = field(default_factory=list)


class SmartRecommendationGenerator:
    """
    Generates intelligent recommendations by integrating all Cortex layers.

    Layer 1: Project intelligence (tech stack, coverage, quality tools)
    Layer 2: Pattern matching (similar work, historical patterns)
    Layer 3: Active alerts and monitoring
    """

    def __init__(
        self,
        layer1_client: Optional[Any] = None,
        layer2_client: Optional[Any] = None,
        layer3_client: Optional[Any] = None,
        file_selector: Optional[Any] = None,
    ):
        """Initialize with optional layer clients."""
        self.layer1 = layer1_client
        self.layer2 = layer2_client
        self.layer3 = layer3_client
        self.file_selector = file_selector

        # Step templates for different recommendation types
        self._step_templates = self._initialize_step_templates()

    def _initialize_step_templates(self) -> Dict[str, List[Dict[str, str]]]:
        """Initialize step templates for different scenarios."""
        return {
            "coverage_improvement": [
                {
                    "description": "Identify untested code paths using coverage report",
                    "command": "pytest --cov={module} --cov-report=html",
                    "success_criteria": "Coverage report generated in htmlcov/",
                },
                {
                    "description": "Create test file for uncovered module",
                    "command": "touch tests/test_{module}.py",
                    "success_criteria": "Test file exists and is importable",
                },
                {
                    "description": "Write unit tests for critical functions",
                    "command": None,
                    "success_criteria": "All critical functions have at least one test",
                },
                {
                    "description": "Run tests and verify coverage increase",
                    "command": "pytest --cov={module} --cov-fail-under={target}",
                    "success_criteria": "Coverage meets or exceeds target",
                },
            ],
            "security_fix": [
                {
                    "description": "Review security alert details and affected code",
                    "command": None,
                    "success_criteria": "Vulnerability scope is understood",
                },
                {
                    "description": "Update vulnerable dependency",
                    "command": "pip install --upgrade {package}",
                    "success_criteria": "Dependency updated to secure version",
                },
                {
                    "description": "Run security scan to verify fix",
                    "command": "safety check",
                    "success_criteria": "No security vulnerabilities detected",
                },
                {
                    "description": "Run full test suite to ensure compatibility",
                    "command": "pytest",
                    "success_criteria": "All tests pass",
                },
            ],
            "performance_optimization": [
                {
                    "description": "Profile the slow code path",
                    "command": "python -m cProfile -o profile.stats {script}",
                    "success_criteria": "Profile data collected",
                },
                {
                    "description": "Identify bottlenecks in profile",
                    "command": "python -c \"import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)\"",
                    "success_criteria": "Top bottlenecks identified",
                },
                {
                    "description": "Implement optimization for identified bottleneck",
                    "command": None,
                    "success_criteria": "Code refactored with optimization",
                },
                {
                    "description": "Benchmark before and after",
                    "command": "pytest --benchmark-only",
                    "success_criteria": "Performance improvement measured",
                },
            ],
            "documentation_update": [
                {
                    "description": "Identify outdated or missing documentation",
                    "command": "find . -name '*.py' -exec grep -l 'TODO.*doc' {} \\;",
                    "success_criteria": "Documentation gaps identified",
                },
                {
                    "description": "Update docstrings for public APIs",
                    "command": None,
                    "success_criteria": "All public functions have docstrings",
                },
                {
                    "description": "Generate API documentation",
                    "command": "sphinx-apidoc -o docs/api {module}",
                    "success_criteria": "API docs generated",
                },
                {
                    "description": "Review and publish documentation",
                    "command": "make -C docs html",
                    "success_criteria": "Documentation builds without warnings",
                },
            ],
            "code_quality": [
                {
                    "description": "Run linting tools to identify issues",
                    "command": "ruff check {path} --output-format=json",
                    "success_criteria": "Linting report generated",
                },
                {
                    "description": "Fix auto-fixable issues",
                    "command": "ruff check {path} --fix",
                    "success_criteria": "Auto-fixable issues resolved",
                },
                {
                    "description": "Manually address remaining issues",
                    "command": None,
                    "success_criteria": "All linting issues resolved",
                },
                {
                    "description": "Run type checker",
                    "command": "mypy {path}",
                    "success_criteria": "No type errors",
                },
            ],
        }

    def _generate_id(self, *args) -> str:
        """Generate a unique recommendation ID."""
        content = "|".join(str(a) for a in args)
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def gather_project_intelligence(self, project_id: str) -> Dict[str, Any]:
        """
        Gather comprehensive intelligence about a project from all layers.

        Returns:
            Dict containing:
            - layer1: tech stack, coverage, quality tools
            - layer2: similar patterns
            - layer3: active alerts
            - git: recent files, critical files
        """
        intelligence = {
            "project_id": project_id,
            "gathered_at": datetime.now().isoformat(),
            "layer1": {},
            "layer2": {},
            "layer3": {},
            "git": {},
        }

        # Layer 1: Project fundamentals
        if self.layer1:
            try:
                intelligence["layer1"] = {
                    "tech_stack": self.layer1.get_tech_stack(project_id),
                    "coverage": self.layer1.get_coverage_data(project_id),
                    "quality_tools": self.layer1.get_quality_tools(project_id),
                    "dependencies": self.layer1.get_dependencies(project_id),
                }
            except Exception as e:
                intelligence["layer1"]["error"] = str(e)
        else:
            # Mock data for standalone operation
            intelligence["layer1"] = {
                "tech_stack": ["python", "pytest", "fastapi"],
                "coverage": {"overall": 75.5, "by_module": {}},
                "quality_tools": ["ruff", "mypy", "pytest"],
                "dependencies": {"total": 45, "outdated": 3, "vulnerable": 1},
            }

        # Layer 2: Pattern intelligence
        if self.layer2:
            try:
                intelligence["layer2"] = {
                    "recent_patterns": self.layer2.get_recent_patterns(project_id),
                    "common_changes": self.layer2.get_common_change_patterns(project_id),
                    "similar_projects": self.layer2.find_similar_projects(project_id),
                }
            except Exception as e:
                intelligence["layer2"]["error"] = str(e)
        else:
            intelligence["layer2"] = {
                "recent_patterns": [],
                "common_changes": [],
                "similar_projects": [],
            }

        # Layer 3: Active monitoring
        if self.layer3:
            try:
                intelligence["layer3"] = {
                    "active_alerts": self.layer3.get_active_alerts(project_id),
                    "health_score": self.layer3.get_health_score(project_id),
                    "trend": self.layer3.get_health_trend(project_id),
                }
            except Exception as e:
                intelligence["layer3"]["error"] = str(e)
        else:
            intelligence["layer3"] = {
                "active_alerts": [],
                "health_score": 85,
                "trend": "stable",
            }

        # Git intelligence
        if self.file_selector:
            try:
                intelligence["git"] = {
                    "recent_files": self.file_selector.get_recent_files(project_id),
                    "critical_files": self.file_selector.get_critical_files(project_id),
                    "hot_spots": self.file_selector.get_change_hotspots(project_id),
                }
            except Exception as e:
                intelligence["git"]["error"] = str(e)
        else:
            intelligence["git"] = {
                "recent_files": [],
                "critical_files": [],
                "hot_spots": [],
            }

        return intelligence

    def generate_steps(self, recommendation_type: str, context: Dict[str, Any]) -> List[Step]:
        """
        Generate concrete, actionable steps for a recommendation.

        Args:
            recommendation_type: Type of recommendation (maps to templates)
            context: Context for variable substitution

        Returns:
            List of 3-5 concrete steps with commands and success criteria
        """
        template_key = self._map_to_template(recommendation_type)
        templates = self._step_templates.get(template_key, [])

        steps = []
        for i, template in enumerate(templates, 1):
            # Substitute context variables
            description = self._substitute_variables(template["description"], context)
            command = None
            if template.get("command"):
                command = self._substitute_variables(template["command"], context)

            success_criteria = self._substitute_variables(
                template.get("success_criteria", ""), context
            )

            steps.append(
                Step(
                    order=i,
                    description=description,
                    command=command,
                    success_criteria=success_criteria if success_criteria else None,
                    estimated_time=self._estimate_step_time(template_key, i),
                )
            )

        # Add context-specific steps if needed
        steps.extend(
            self._generate_context_specific_steps(recommendation_type, context, len(steps))
        )

        return steps[:5]  # Limit to 5 steps

    def _map_to_template(self, recommendation_type: str) -> str:
        """Map recommendation type to template key."""
        mapping = {
            "coverage": "coverage_improvement",
            "security": "security_fix",
            "performance": "performance_optimization",
            "documentation": "documentation_update",
            "quality": "code_quality",
            "test_coverage": "coverage_improvement",
            "vulnerability": "security_fix",
            "slow_test": "performance_optimization",
            "missing_docs": "documentation_update",
            "lint_error": "code_quality",
        }
        return mapping.get(recommendation_type, "code_quality")

    def _substitute_variables(self, text: str, context: Dict[str, Any]) -> str:
        """Substitute variables in text with context values."""
        if not text:
            return text

        result = text
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        return result

    def _estimate_step_time(self, template_key: str, step_order: int) -> str:
        """Estimate time for a step based on template and order."""
        time_estimates = {
            "coverage_improvement": ["5 min", "2 min", "30 min", "5 min"],
            "security_fix": ["10 min", "5 min", "5 min", "10 min"],
            "performance_optimization": ["15 min", "10 min", "45 min", "10 min"],
            "documentation_update": ["10 min", "30 min", "5 min", "10 min"],
            "code_quality": ["5 min", "2 min", "20 min", "5 min"],
        }

        estimates = time_estimates.get(template_key, ["10 min"] * 5)
        if step_order <= len(estimates):
            return estimates[step_order - 1]
        return "10 min"

    def _generate_context_specific_steps(
        self, recommendation_type: str, context: Dict[str, Any], current_count: int
    ) -> List[Step]:
        """Generate additional context-specific steps."""
        steps = []

        # Add file-specific steps if files are in context
        if "files" in context and current_count < 4:
            files = context["files"][:3]  # Limit to 3 files
            for i, file_path in enumerate(files, current_count + 1):
                steps.append(
                    Step(
                        order=i,
                        description=f"Review and update: {file_path}",
                        command=None,
                        success_criteria=f"Changes to {file_path} complete and tested",
                        estimated_time="15 min",
                    )
                )

        return steps

    def _find_similar_patterns(
        self, recommendation_type: str, context: Dict[str, Any]
    ) -> List[SimilarWork]:
        """Find similar work patterns from Layer 2."""
        similar_work = []

        if self.layer2:
            try:
                patterns = self.layer2.find_similar_patterns(
                    pattern_type=recommendation_type, context=context
                )
                for pattern in patterns[:3]:  # Limit to 3 similar patterns
                    similar_work.append(
                        SimilarWork(
                            pattern_id=pattern.get("id", "unknown"),
                            description=pattern.get("description", ""),
                            files_changed=pattern.get("files", []),
                            lessons=pattern.get("lessons", []),
                            relevance_score=pattern.get("score", 0.5),
                        )
                    )
            except Exception:
                pass

        # Generate mock similar work if none found
        if not similar_work:
            similar_work = self._generate_mock_similar_work(recommendation_type)

        return similar_work

    def _generate_mock_similar_work(self, recommendation_type: str) -> List[SimilarWork]:
        """Generate mock similar work for demonstration."""
        mock_patterns = {
            "coverage": [
                SimilarWork(
                    pattern_id="pat_cov_001",
                    description="Previous coverage improvement in auth module",
                    files_changed=["src/auth/login.py", "tests/test_login.py"],
                    lessons=[
                        "Focus on edge cases first",
                        "Mock external services for faster tests",
                    ],
                    relevance_score=0.85,
                )
            ],
            "security": [
                SimilarWork(
                    pattern_id="pat_sec_001",
                    description="SQL injection fix in query builder",
                    files_changed=["src/db/query.py", "tests/test_query_security.py"],
                    lessons=[
                        "Always use parameterized queries",
                        "Add security-focused tests",
                    ],
                    relevance_score=0.90,
                )
            ],
        }

        return mock_patterns.get(recommendation_type, [])

    def _generate_file_guidance(
        self,
        recommendation_type: str,
        context: Dict[str, Any],
        intelligence: Dict[str, Any],
    ) -> List[FileGuidance]:
        """Generate file-level guidance for a recommendation."""
        guidance = []

        # Get files from file selector if available
        if self.file_selector:
            try:
                selected_files = self.file_selector.select_for_recommendation_type(
                    rec_type=recommendation_type, context=context
                )
                for file_info in selected_files:
                    guidance.append(
                        FileGuidance(
                            file_path=file_info["path"],
                            action=file_info.get("action", "modify"),
                            reason=file_info.get("reason", "Identified for improvement"),
                            priority=Priority(file_info.get("priority", "medium")),
                            estimated_effort=file_info.get("effort", "unknown"),
                            related_files=file_info.get("related", []),
                        )
                    )
            except Exception:
                pass

        # Add guidance based on intelligence
        if "git" in intelligence:
            critical_files = intelligence["git"].get("critical_files", [])
            for file_path in critical_files[:2]:
                if not any(g.file_path == file_path for g in guidance):
                    guidance.append(
                        FileGuidance(
                            file_path=file_path,
                            action="review",
                            reason="Critical file - high impact changes",
                            priority=Priority.HIGH,
                        )
                    )

        # Add test file suggestions
        if recommendation_type in ["coverage", "test_coverage"]:
            source_files = context.get("source_files", [])
            for src_file in source_files[:2]:
                test_file = self._suggest_test_file(src_file)
                guidance.append(
                    FileGuidance(
                        file_path=test_file,
                        action="create",
                        reason=f"Test file for {src_file}",
                        priority=Priority.MEDIUM,
                        related_files=[src_file],
                    )
                )

        return guidance

    def _suggest_test_file(self, source_file: str) -> str:
        """Suggest a test file path for a source file."""
        if source_file.startswith("src/"):
            # src/module/file.py -> tests/module/test_file.py
            parts = source_file.replace("src/", "tests/").rsplit("/", 1)
            if len(parts) == 2:
                return f"{parts[0]}/test_{parts[1]}"

        # Default: tests/test_<filename>
        filename = source_file.rsplit("/", 1)[-1]
        return f"tests/test_{filename}"

    def enrich_with_intelligence(self, recommendation: Recommendation) -> Recommendation:
        """
        Enrich a recommendation with additional intelligence.

        Adds:
        - Similar work patterns from Layer 2
        - Additional context from Layer 1
        - Related alerts from Layer 3
        """
        project_id = recommendation.intelligence_context.get("project_id", "unknown")

        # Gather fresh intelligence
        intelligence = self.gather_project_intelligence(project_id)

        # Add similar work if not already present
        if not recommendation.similar_work:
            recommendation.similar_work = self._find_similar_patterns(
                recommendation.type.value, recommendation.intelligence_context
            )

        # Enrich context
        recommendation.intelligence_context.update(
            {
                "layer1_summary": self._summarize_layer1(intelligence.get("layer1", {})),
                "health_score": intelligence.get("layer3", {}).get("health_score"),
                "related_patterns": len(recommendation.similar_work),
            }
        )

        # Add tags based on intelligence
        if intelligence.get("layer3", {}).get("health_score", 100) < 70:
            recommendation.tags.append("health_critical")

        if recommendation.similar_work:
            recommendation.tags.append("has_precedent")

        return recommendation

    def _summarize_layer1(self, layer1_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of Layer 1 intelligence."""
        return {
            "tech_stack_count": len(layer1_data.get("tech_stack", [])),
            "coverage": layer1_data.get("coverage", {}).get("overall", 0),
            "has_quality_tools": bool(layer1_data.get("quality_tools")),
            "vulnerable_deps": layer1_data.get("dependencies", {}).get("vulnerable", 0),
        }

    def generate_alert_recommendations(self, alerts: List[Alert]) -> List[Recommendation]:
        """
        Generate recommendations based on active alerts.

        Args:
            alerts: List of alerts from Layer 3

        Returns:
            List of recommendations addressing the alerts
        """
        recommendations = []

        # Group alerts by type for consolidated recommendations
        alerts_by_type: Dict[str, List[Alert]] = {}
        for alert in alerts:
            alert_type = alert.type
            if alert_type not in alerts_by_type:
                alerts_by_type[alert_type] = []
            alerts_by_type[alert_type].append(alert)

        for alert_type, type_alerts in alerts_by_type.items():
            # Get the highest severity alert
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            type_alerts.sort(key=lambda a: severity_order.get(a.severity, 4))
            primary_alert = type_alerts[0]

            # Gather intelligence for context
            intelligence = self.gather_project_intelligence(primary_alert.project_id)

            # Determine priority based on severity
            priority_map = {
                "critical": Priority.CRITICAL,
                "high": Priority.HIGH,
                "medium": Priority.MEDIUM,
                "low": Priority.LOW,
            }
            priority = priority_map.get(primary_alert.severity, Priority.MEDIUM)

            # Build context for step generation
            context = {
                "alert_type": alert_type,
                "alert_count": len(type_alerts),
                "project_id": primary_alert.project_id,
                "module": primary_alert.context.get("module", "unknown"),
                "path": primary_alert.context.get("path", "."),
                "package": primary_alert.context.get("package", "unknown"),
                **primary_alert.context,
            }

            # Generate steps
            steps = self.generate_steps(alert_type, context)

            # Generate file guidance
            file_guidance = self._generate_file_guidance(alert_type, context, intelligence)

            # Find similar work
            similar_work = self._find_similar_patterns(alert_type, context)

            recommendation = Recommendation(
                id=self._generate_id("alert", alert_type, primary_alert.project_id),
                type=RecommendationType.ALERT_RESPONSE,
                title=f"Address {alert_type} alert{'s' if len(type_alerts) > 1 else ''}",
                description=self._build_alert_description(type_alerts),
                priority=priority,
                confidence=Confidence.HIGH,
                steps=steps,
                file_guidance=file_guidance,
                similar_work=similar_work,
                intelligence_context={
                    "project_id": primary_alert.project_id,
                    "alert_type": alert_type,
                    "alert_count": len(type_alerts),
                    **intelligence,
                },
                source_alerts=[a.id for a in type_alerts],
                estimated_impact=self._estimate_alert_impact(type_alerts),
                tags=[alert_type, primary_alert.severity],
            )

            recommendations.append(self.enrich_with_intelligence(recommendation))

        return recommendations

    def _build_alert_description(self, alerts: List[Alert]) -> str:
        """Build a description from multiple alerts."""
        if len(alerts) == 1:
            return alerts[0].message

        description = f"Multiple related alerts detected ({len(alerts)} total):\n"
        for alert in alerts[:3]:
            description += f"- {alert.message}\n"

        if len(alerts) > 3:
            description += f"... and {len(alerts) - 3} more"

        return description

    def _estimate_alert_impact(self, alerts: List[Alert]) -> str:
        """Estimate the impact of addressing alerts."""
        severity_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        total_score = sum(severity_scores.get(a.severity, 1) for a in alerts)

        if total_score >= 8:
            return "high"
        elif total_score >= 4:
            return "medium"
        return "low"

    def generate_goal_recommendations(
        self, goals: List[Goal], project_activity: ProjectActivity
    ) -> List[Recommendation]:
        """
        Generate recommendations to help achieve project goals.

        Args:
            goals: List of project goals
            project_activity: Recent project activity

        Returns:
            List of recommendations for goal progress
        """
        recommendations = []

        for goal in goals:
            # Calculate progress
            progress = (
                (goal.current_value / goal.target_value * 100) if goal.target_value > 0 else 0
            )
            gap = goal.target_value - goal.current_value

            # Skip goals that are already met
            if progress >= 100:
                continue

            # Determine priority based on deadline and gap
            priority = self._calculate_goal_priority(goal, progress)

            # Gather intelligence
            intelligence = self.gather_project_intelligence(project_activity.project_id)

            # Build context
            context = {
                "goal_name": goal.name,
                "metric_type": goal.metric_type,
                "current_value": goal.current_value,
                "target_value": goal.target_value,
                "gap": gap,
                "progress": progress,
                "module": self._identify_target_module(goal, intelligence),
                "target": goal.target_value,
                "files": project_activity.recent_files[:5],
            }

            # Generate steps based on metric type
            steps = self.generate_steps(goal.metric_type, context)

            # Generate file guidance
            file_guidance = self._generate_goal_file_guidance(goal, project_activity, intelligence)

            # Find similar work
            similar_work = self._find_similar_patterns(goal.metric_type, context)

            recommendation = Recommendation(
                id=self._generate_id("goal", goal.id, goal.metric_type),
                type=RecommendationType.GOAL_PROGRESS,
                title=f"Progress toward: {goal.name}",
                description=self._build_goal_description(goal, progress, gap),
                priority=priority,
                confidence=Confidence.MEDIUM,
                steps=steps,
                file_guidance=file_guidance,
                similar_work=similar_work,
                intelligence_context={
                    "project_id": project_activity.project_id,
                    "goal_id": goal.id,
                    "progress_percent": progress,
                    "gap": gap,
                    **intelligence,
                },
                source_goals=[goal.id],
                estimated_impact=self._estimate_goal_impact(goal, gap),
                tags=[goal.metric_type, f"progress_{int(progress)}"],
            )

            recommendations.append(self.enrich_with_intelligence(recommendation))

        return recommendations

    def _calculate_goal_priority(self, goal: Goal, progress: float) -> Priority:
        """Calculate priority based on goal deadline and progress."""
        if goal.deadline:
            days_remaining = (goal.deadline - datetime.now()).days
            if days_remaining < 7 and progress < 80:
                return Priority.CRITICAL
            elif days_remaining < 14 and progress < 60:
                return Priority.HIGH

        if progress < 30:
            return Priority.HIGH
        elif progress < 60:
            return Priority.MEDIUM
        return Priority.LOW

    def _identify_target_module(self, goal: Goal, intelligence: Dict[str, Any]) -> str:
        """Identify the target module for a goal."""
        # Try to find module from Layer 1 coverage data
        coverage_data = intelligence.get("layer1", {}).get("coverage", {})
        by_module = coverage_data.get("by_module", {})

        if goal.metric_type == "coverage" and by_module:
            # Find lowest coverage module
            lowest = min(by_module.items(), key=lambda x: x[1], default=("unknown", 0))
            return lowest[0]

        return "src"

    def _generate_goal_file_guidance(
        self, goal: Goal, activity: ProjectActivity, intelligence: Dict[str, Any]
    ) -> List[FileGuidance]:
        """Generate file guidance for goal achievement."""
        guidance = []

        if goal.metric_type in ["coverage", "test_coverage"]:
            # Suggest files that need tests
            for file_path in activity.critical_files[:3]:
                if not file_path.startswith("test"):
                    test_file = self._suggest_test_file(file_path)
                    guidance.append(
                        FileGuidance(
                            file_path=test_file,
                            action="create" if "create" in test_file else "modify",
                            reason=f"Increase coverage for {file_path}",
                            priority=Priority.MEDIUM,
                            estimated_effort="30 min",
                            related_files=[file_path],
                        )
                    )

        elif goal.metric_type == "documentation":
            # Suggest documentation files
            guidance.append(
                FileGuidance(
                    file_path="docs/api.md",
                    action="modify",
                    reason="Update API documentation",
                    priority=Priority.MEDIUM,
                    estimated_effort="1 hour",
                )
            )

        return guidance

    def _build_goal_description(self, goal: Goal, progress: float, gap: float) -> str:
        """Build a description for a goal recommendation."""
        description = f"Goal: {goal.name}\n"
        description += f"Current: {goal.current_value:.1f} / Target: {goal.target_value:.1f}\n"
        description += f"Progress: {progress:.1f}% (Gap: {gap:.1f})\n"

        if goal.deadline:
            days = (goal.deadline - datetime.now()).days
            description += f"Deadline: {days} days remaining"

        return description

    def _estimate_goal_impact(self, goal: Goal, gap: float) -> str:
        """Estimate impact of achieving a goal."""
        if goal.metric_type in ["coverage", "security"]:
            return "high"
        elif gap > goal.target_value * 0.5:
            return "high"
        return "medium"

    def generate_health_recommendations(
        self, project_activity: ProjectActivity
    ) -> List[Recommendation]:
        """
        Generate proactive health improvement recommendations.

        Args:
            project_activity: Recent project activity

        Returns:
            List of health improvement recommendations
        """
        recommendations = []

        # Gather comprehensive intelligence
        intelligence = self.gather_project_intelligence(project_activity.project_id)

        # Check various health aspects
        health_checks = [
            self._check_coverage_health(intelligence, project_activity),
            self._check_dependency_health(intelligence, project_activity),
            self._check_code_quality_health(intelligence, project_activity),
            self._check_documentation_health(intelligence, project_activity),
            self._check_hotspot_health(intelligence, project_activity),
        ]

        for check_result in health_checks:
            if check_result:
                recommendation = self.enrich_with_intelligence(check_result)
                recommendations.append(recommendation)

        return recommendations

    def _check_coverage_health(
        self, intelligence: Dict[str, Any], activity: ProjectActivity
    ) -> Optional[Recommendation]:
        """Check test coverage health."""
        coverage = intelligence.get("layer1", {}).get("coverage", {})
        overall = coverage.get("overall", 100)

        if overall < 70:
            context = {
                "module": "src",
                "target": 80,
                "current": overall,
                "files": activity.recent_files,
            }

            return Recommendation(
                id=self._generate_id("health", "coverage", activity.project_id),
                type=RecommendationType.HEALTH_IMPROVEMENT,
                title="Improve Test Coverage",
                description=f"Test coverage is at {overall:.1f}%, below recommended 70% threshold.",
                priority=Priority.HIGH if overall < 50 else Priority.MEDIUM,
                confidence=Confidence.HIGH,
                steps=self.generate_steps("coverage", context),
                file_guidance=self._generate_file_guidance("coverage", context, intelligence),
                similar_work=self._find_similar_patterns("coverage", context),
                intelligence_context={
                    "project_id": activity.project_id,
                    "current_coverage": overall,
                    **intelligence,
                },
                estimated_impact="high",
                tags=["coverage", "testing", "quality"],
            )

        return None

    def _check_dependency_health(
        self, intelligence: Dict[str, Any], activity: ProjectActivity
    ) -> Optional[Recommendation]:
        """Check dependency health."""
        deps = intelligence.get("layer1", {}).get("dependencies", {})
        vulnerable = deps.get("vulnerable", 0)
        outdated = deps.get("outdated", 0)

        if vulnerable > 0:
            context = {"package": "vulnerable-package", "vulnerable_count": vulnerable}

            return Recommendation(
                id=self._generate_id("health", "security", activity.project_id),
                type=RecommendationType.HEALTH_IMPROVEMENT,
                title="Address Security Vulnerabilities",
                description=f"Found {vulnerable} vulnerable dependencies that need updating.",
                priority=Priority.CRITICAL,
                confidence=Confidence.HIGH,
                steps=self.generate_steps("security", context),
                file_guidance=[
                    FileGuidance(
                        file_path="requirements.txt",
                        action="modify",
                        reason="Update vulnerable dependencies",
                        priority=Priority.CRITICAL,
                    )
                ],
                similar_work=self._find_similar_patterns("security", context),
                intelligence_context={
                    "project_id": activity.project_id,
                    "vulnerable_count": vulnerable,
                    **intelligence,
                },
                estimated_impact="high",
                tags=["security", "dependencies", "critical"],
            )

        if outdated > 5:
            return Recommendation(
                id=self._generate_id("health", "deps", activity.project_id),
                type=RecommendationType.HEALTH_IMPROVEMENT,
                title="Update Outdated Dependencies",
                description=f"Found {outdated} outdated dependencies.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
                steps=[
                    Step(
                        1,
                        "Review outdated dependencies",
                        "pip list --outdated",
                        "List generated",
                    ),
                    Step(
                        2,
                        "Update dependencies incrementally",
                        "pip install --upgrade <package>",
                        "Package updated",
                    ),
                    Step(3, "Run tests after each update", "pytest", "All tests pass"),
                ],
                intelligence_context={
                    "project_id": activity.project_id,
                    **intelligence,
                },
                estimated_impact="low",
                tags=["dependencies", "maintenance"],
            )

        return None

    def _check_code_quality_health(
        self, intelligence: Dict[str, Any], activity: ProjectActivity
    ) -> Optional[Recommendation]:
        """Check code quality health."""
        quality_tools = intelligence.get("layer1", {}).get("quality_tools", [])

        if not quality_tools:
            return Recommendation(
                id=self._generate_id("health", "quality", activity.project_id),
                type=RecommendationType.HEALTH_IMPROVEMENT,
                title="Set Up Code Quality Tools",
                description="No code quality tools detected. Consider adding linting and type checking.",
                priority=Priority.MEDIUM,
                confidence=Confidence.MEDIUM,
                steps=[
                    Step(
                        1,
                        "Install ruff for linting",
                        "pip install ruff",
                        "Ruff installed",
                    ),
                    Step(
                        2,
                        "Install mypy for type checking",
                        "pip install mypy",
                        "Mypy installed",
                    ),
                    Step(
                        3,
                        "Create configuration",
                        "touch pyproject.toml",
                        "Config file created",
                    ),
                    Step(
                        4,
                        "Run initial quality check",
                        "ruff check . && mypy .",
                        "No critical issues",
                    ),
                ],
                file_guidance=[
                    FileGuidance(
                        file_path="pyproject.toml",
                        action="create",
                        reason="Configure quality tools",
                        priority=Priority.MEDIUM,
                    )
                ],
                intelligence_context={
                    "project_id": activity.project_id,
                    **intelligence,
                },
                estimated_impact="medium",
                tags=["quality", "tooling", "setup"],
            )

        return None

    def _check_documentation_health(
        self, intelligence: Dict[str, Any], activity: ProjectActivity
    ) -> Optional[Recommendation]:
        """Check documentation health."""
        # This would typically check for README, docs folder, docstrings, etc.
        git_info = intelligence.get("git", {})
        recent_files = git_info.get("recent_files", [])

        # Check if docs are being updated with code
        code_changes = [f for f in recent_files if f.endswith(".py")]
        doc_changes = [f for f in recent_files if "doc" in f.lower() or f.endswith(".md")]

        if len(code_changes) > 5 and len(doc_changes) == 0:
            context = {"module": "src"}

            return Recommendation(
                id=self._generate_id("health", "docs", activity.project_id),
                type=RecommendationType.HEALTH_IMPROVEMENT,
                title="Update Documentation",
                description="Recent code changes detected without corresponding documentation updates.",
                priority=Priority.LOW,
                confidence=Confidence.MEDIUM,
                steps=self.generate_steps("documentation", context),
                file_guidance=[
                    FileGuidance(
                        file_path="README.md",
                        action="modify",
                        reason="Update with recent changes",
                        priority=Priority.LOW,
                    ),
                    FileGuidance(
                        file_path="docs/changelog.md",
                        action="modify",
                        reason="Document recent changes",
                        priority=Priority.LOW,
                    ),
                ],
                intelligence_context={
                    "project_id": activity.project_id,
                    **intelligence,
                },
                estimated_impact="low",
                tags=["documentation", "maintenance"],
            )

        return None

    def _check_hotspot_health(
        self, intelligence: Dict[str, Any], activity: ProjectActivity
    ) -> Optional[Recommendation]:
        """Check for code hotspots that may need refactoring."""
        hotspots = intelligence.get("git", {}).get("hot_spots", [])

        if len(hotspots) > 3:
            return Recommendation(
                id=self._generate_id("health", "hotspots", activity.project_id),
                type=RecommendationType.HEALTH_IMPROVEMENT,
                title="Review Code Hotspots",
                description=f"Detected {len(hotspots)} files with frequent changes. Consider refactoring.",
                priority=Priority.LOW,
                confidence=Confidence.LOW,
                steps=[
                    Step(
                        1,
                        "Analyze change frequency",
                        "git log --format='%H' --follow -- <file> | wc -l",
                        "Change count obtained",
                    ),
                    Step(
                        2,
                        "Review hotspot complexity",
                        None,
                        "Complexity issues identified",
                    ),
                    Step(
                        3,
                        "Plan refactoring if needed",
                        None,
                        "Refactoring plan created",
                    ),
                ],
                file_guidance=[
                    FileGuidance(
                        file_path=hotspot,
                        action="review",
                        reason="Frequent changes - potential refactoring candidate",
                        priority=Priority.LOW,
                    )
                    for hotspot in hotspots[:3]
                ],
                intelligence_context={
                    "project_id": activity.project_id,
                    "hotspots": hotspots,
                    **intelligence,
                },
                estimated_impact="medium",
                tags=["refactoring", "maintenance", "hotspots"],
            )

        return None

    def generate_all_recommendations(
        self,
        project_id: str,
        alerts: Optional[List[Alert]] = None,
        goals: Optional[List[Goal]] = None,
        activity: Optional[ProjectActivity] = None,
    ) -> List[Recommendation]:
        """
        Generate all types of recommendations for a project.

        Args:
            project_id: Project identifier
            alerts: Optional list of alerts
            goals: Optional list of goals
            activity: Optional project activity

        Returns:
            Consolidated list of all recommendations, sorted by priority
        """
        all_recommendations = []

        # Default activity if not provided
        if activity is None:
            activity = ProjectActivity(project_id=project_id)

        # Generate alert recommendations
        if alerts:
            all_recommendations.extend(self.generate_alert_recommendations(alerts))

        # Generate goal recommendations
        if goals:
            all_recommendations.extend(self.generate_goal_recommendations(goals, activity))

        # Generate health recommendations
        all_recommendations.extend(self.generate_health_recommendations(activity))

        # Sort by priority
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }

        all_recommendations.sort(
            key=lambda r: (priority_order.get(r.priority, 4), -len(r.similar_work))
        )

        return all_recommendations

    def format_recommendation(self, recommendation: Recommendation) -> str:
        """Format a recommendation for display."""
        lines = [
            f"{'='*60}",
            f"[{recommendation.priority.value.upper()}] {recommendation.title}",
            f"{'='*60}",
            f"Type: {recommendation.type.value}",
            f"Confidence: {recommendation.confidence.value}",
            f"Impact: {recommendation.estimated_impact}",
            "",
            recommendation.description,
            "",
        ]

        if recommendation.steps:
            lines.append("Steps:")
            for step in recommendation.steps:
                lines.append(f"  {step.order}. {step.description}")
                if step.command:
                    lines.append(f"     $ {step.command}")
                if step.success_criteria:
                    lines.append(f"     ✓ {step.success_criteria}")

        if recommendation.file_guidance:
            lines.append("")
            lines.append("Files to work on:")
            for fg in recommendation.file_guidance:
                lines.append(f"  [{fg.action.upper()}] {fg.file_path}")
                lines.append(f"    Reason: {fg.reason}")

        if recommendation.similar_work:
            lines.append("")
            lines.append("Similar work:")
            for sw in recommendation.similar_work:
                lines.append(f"  - {sw.description}")
                lines.append(f"    Files: {', '.join(sw.files_changed[:3])}")
                if sw.lessons:
                    lines.append(f"    Lessons: {sw.lessons[0]}")

        if recommendation.tags:
            lines.append("")
            lines.append(f"Tags: {', '.join(recommendation.tags)}")

        return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":
    # Create generator
    generator = SmartRecommendationGenerator()

    # Test with sample alerts
    alerts = [
        Alert(
            id="alert_001",
            type="coverage",
            severity="high",
            message="Test coverage dropped below 70%",
            project_id="project_123",
            context={"module": "auth", "current": 65, "threshold": 70},
        ),
        Alert(
            id="alert_002",
            type="security",
            severity="critical",
            message="Vulnerable dependency detected: requests<2.28.0",
            project_id="project_123",
            context={"package": "requests", "current_version": "2.25.0"},
        ),
    ]

    # Test with sample goals
    goals = [
        Goal(
            id="goal_001",
            name="Achieve 80% test coverage",
            target_value=80.0,
            current_value=65.0,
            metric_type="coverage",
        )
    ]

    # Test with sample activity
    activity = ProjectActivity(
        project_id="project_123",
        recent_files=["src/auth/login.py", "src/api/routes.py"],
        critical_files=["src/core/engine.py"],
        active_branches=["main", "feature/new-auth"],
    )

    # Generate all recommendations
    recommendations = generator.generate_all_recommendations(
        project_id="project_123", alerts=alerts, goals=goals, activity=activity
    )

    # Display recommendations
    print(f"\nGenerated {len(recommendations)} recommendations:\n")
    for rec in recommendations:
        print(generator.format_recommendation(rec))
        print()
