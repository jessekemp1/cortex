#!/usr/bin/env python3
"""
Context Injector - Aggregates intelligence for Claude Code injection.

Layer 5 of Cortex Intelligence Stack: Context Synthesis

Aggregates:
- Layer 1: Project profiler (tech stack, coverage, warnings)
- Layer 2: Pattern memory (similar solutions)
- Layer 3: Domain experts (project-specific intelligence)

Target: 200-400 chars, under 500ms injection time
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from intelligence.analysis.project_profiler import ProjectProfiler
from intelligence.memory.pattern_memory import PatternMemory


@dataclass
class InjectionContext:
    """Complete context for injection."""

    project_name: str
    tech_stack: str = ""  # Compact: "Python/FastAPI/PostgreSQL"
    coverage: Optional[str] = None  # "45% test coverage"
    warnings: List[str] = field(default_factory=list)
    pattern_hint: Optional[str] = None
    domain_insight: Optional[str] = None

    def to_string(self, max_chars: int = 400) -> str:
        """Format to context string."""
        lines = []

        # Line 1: Project with tech stack
        line1 = f"Project: {self.project_name}"
        if self.tech_stack:
            line1 += f" ({self.tech_stack})"
        if self.coverage:
            line1 += f", {self.coverage}"
        lines.append(line1)

        # Line 2: Warnings (most important)
        if self.warnings:
            # Take first warning only to save space
            warning = self.warnings[0]
            lines.append(f"Warning: {warning}")

        # Line 3: Pattern hint
        if self.pattern_hint:
            lines.append(f"Pattern: {self.pattern_hint}")

        # Line 4: Domain insight
        if self.domain_insight:
            lines.append(self.domain_insight)

        result = "\n".join(lines)

        # Truncate if needed
        if len(result) > max_chars:
            result = result[: max_chars - 3] + "..."

        return result


class ContextInjector:
    """Main context injection engine."""

    MAX_TIME_MS = 500
    MAX_CHARS = 400

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)

        # Lazy initialization for performance
        self._pattern_memory: Optional[PatternMemory] = None
        self._domain_experts: Dict[str, "BaseDomainExpert"] = {}

    def inject(self, cwd: Path, task: str = "") -> str:
        """
        Generate context string for injection.

        Args:
            cwd: Current working directory
            task: Optional task description

        Returns:
            Context string (max 400 chars, generated in under 500ms)
        """
        start = time.time()

        # Detect project
        project_name = self._detect_project(cwd)

        context = InjectionContext(project_name=project_name)

        # 1. Get project profile (under 200ms)
        try:
            self._add_profile(context, cwd, quick=True)
        except Exception:
            pass  # Graceful degradation

        # Check time budget
        elapsed = (time.time() - start) * 1000
        remaining = self.MAX_TIME_MS - elapsed

        # 2. Get pattern hint if we have time and task (under 150ms)
        if remaining > 150 and task:
            try:
                self._add_patterns(context, task, project_name)
            except Exception:
                pass  # Graceful degradation

        # Check time budget
        elapsed = (time.time() - start) * 1000
        remaining = self.MAX_TIME_MS - elapsed

        # 3. Get domain insight if we have time (under 150ms)
        if remaining > 100:
            try:
                self._add_domain_insight(context, cwd, task, project_name)
            except Exception:
                pass  # Graceful degradation

        return context.to_string(self.MAX_CHARS)

    def _detect_project(self, cwd: Path) -> str:
        """Detect project name from path."""
        # Check if in Dev directory structure
        dev_root = self.root_dir
        if str(dev_root) in str(cwd):
            try:
                # Find the project directory (first child of Dev or nested like Vortex/VortexV2)
                rel_path = cwd.relative_to(dev_root)
                parts = rel_path.parts
                if parts:
                    # Handle nested projects like Vortex/VortexV2 or production/audio/dj-copilot
                    if len(parts) >= 2 and parts[0] in ["Vortex", "production"]:
                        # Return deepest non-category directory
                        return parts[-1] if parts[-1] not in ["audio", "weather", "health"] else parts[-2]
                    return parts[0]
            except ValueError:
                pass

        return cwd.name

    def _add_profile(self, context: InjectionContext, cwd: Path, quick: bool = True):
        """Add project profile to context."""
        # Find project root
        project_root = self._find_project_root(cwd)
        profiler = ProjectProfiler(project_root)
        profile = profiler.profile(quick=quick)

        # Add to context
        context.tech_stack = profile.tech_stack.to_compact_str()

        # Add coverage if low
        if profile.test_coverage.estimated_coverage < 70:
            coverage_pct = int(profile.test_coverage.estimated_coverage)
            context.coverage = f"{coverage_pct}% test coverage"

        # Add warnings (max 2)
        if profile.warnings:
            context.warnings = profile.warnings[:2]

    def _add_patterns(self, context: InjectionContext, task: str, project: str):
        """Add pattern hints to context."""
        if self._pattern_memory is None:
            self._pattern_memory = PatternMemory(self.root_dir)

        similar = self._pattern_memory.find_similar_solutions(
            task=task, current_project=project, limit=1
        )

        if similar:
            top = similar[0]
            hint = f"Similar to {top.project}: {top.title[:40]}"
            if len(hint) > 60:
                hint = hint[:57] + "..."
            context.pattern_hint = hint

    def _add_domain_insight(
        self, context: InjectionContext, cwd: Path, task: str, project: str
    ):
        """Add domain expert insight."""
        expert = self._get_domain_expert(project)
        if expert:
            insight = expert.get_quick_insight(cwd, task)
            if insight:
                context.domain_insight = insight

    def _get_domain_expert(self, project: str) -> Optional["BaseDomainExpert"]:
        """Get domain expert for project."""
        if project in self._domain_experts:
            return self._domain_experts[project]

        # Try to load domain expert
        try:
            if project.lower() in ["vortexv2", "vortex"]:
                from intelligence.domains.vortex_expert import VortexExpert

                self._domain_experts[project] = VortexExpert()
                return self._domain_experts[project]
        except ImportError:
            pass

        return None

    def _find_project_root(self, cwd: Path) -> Path:
        """Find project root directory (has .git or pyproject.toml)."""
        current = cwd
        while current != current.parent:
            if (current / ".git").exists() or (current / "pyproject.toml").exists():
                return current
            current = current.parent
        return cwd
