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
from typing import Dict, List, Optional, Tuple

from intelligence.analysis.project_profiler import ProjectProfiler
from intelligence.memory.pattern_memory import PatternMemory

# Import for domain expert warnings
try:
    from intelligence.domains.base_expert import DomainInsight
except ImportError:
    # Fallback if import fails
    DomainInsight = None

# Import for process monitoring
try:
    from intelligence.process_monitor import ProcessMonitor
except ImportError:
    ProcessMonitor = None


@dataclass
class InjectionContext:
    """Complete context for injection."""

    project_name: str
    tech_stack: str = ""  # Compact: "Python/FastAPI/PostgreSQL"
    coverage: Optional[str] = None  # "45% test coverage"
    warnings: List[str] = field(default_factory=list)
    pattern_hint: Optional[str] = None
    domain_insight: Optional[str] = None
    process_context: Optional[str] = None  # "CPU:45% avail | Alert: High memory"

    def to_string(self, max_chars: int = 400) -> str:
        """Format to context string with all available intelligence."""
        lines = []

        # Line 1: Project with tech stack
        line1 = f"Project: {self.project_name}"
        if self.tech_stack:
            line1 += f" ({self.tech_stack})"
        if self.coverage:
            line1 += f", {self.coverage}"
        lines.append(line1)

        # Prioritize: Warnings > Patterns > Domain Insights

        # Warnings (most important - show up to 2)
        if self.warnings:
            for warning in self.warnings[:2]:
                # Remove emoji prefix if present (to save space)
                warning_text = warning.replace("⚠️ ", "").strip()
                lines.append(f"Warning: {warning_text}")
                # Check if we're approaching char limit
                current_length = len("\n".join(lines))
                if current_length > max_chars * 0.7:  # Use 70% of budget for warnings
                    break

        # Pattern hint (if space available)
        if self.pattern_hint:
            current_length = len("\n".join(lines))
            remaining = (
                max_chars - current_length - 20
            )  # Reserve 20 chars for newline and "Pattern: "
            if remaining > 20:  # Only add if we have reasonable space
                pattern_line = f"Pattern: {self.pattern_hint}"
                if len(pattern_line) <= remaining:
                    lines.append(pattern_line)
                else:
                    # Truncate pattern hint to fit
                    truncated = self.pattern_hint[: remaining - 13] + "..."
                    lines.append(f"Pattern: {truncated}")

        # Domain insight (if space available)
        if self.domain_insight:
            current_length = len("\n".join(lines))
            remaining = max_chars - current_length - 5  # Reserve 5 chars for newline
            if remaining > 10:  # Only add if we have reasonable space
                if len(self.domain_insight) <= remaining:
                    lines.append(self.domain_insight)
                else:
                    # Truncate domain insight to fit
                    truncated = self.domain_insight[: remaining - 3] + "..."
                    lines.append(truncated)

        # Process context (if space available)
        if self.process_context:
            current_length = len("\n".join(lines))
            remaining = max_chars - current_length - 15  # Reserve 15 chars for "Resource: " prefix
            if remaining > 20:  # Only add if we have reasonable space
                process_line = f"Resource: {self.process_context}"
                if len(process_line) <= remaining:
                    lines.append(process_line)
                else:
                    # Truncate to fit
                    truncated = self.process_context[: remaining - 15] + "..."
                    lines.append(f"Resource: {truncated}")

        result = "\n".join(lines)

        # Final truncation if still over limit
        if len(result) > max_chars:
            result = result[: max_chars - 3] + "..."

        return result


class ContextInjector:
    """Main context injection engine."""

    MAX_TIME_MS = 500
    MAX_CHARS = 400
    PROFILE_CACHE_TTL = 300  # 5 minutes in seconds

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)

        # Lazy initialization for performance
        self._pattern_memory: Optional[PatternMemory] = None
        self._domain_experts: Dict[str, "BaseDomainExpert"] = {}
        self._process_monitor: Optional["ProcessMonitor"] = None

        # Profile cache: (project_root, quick_mode) -> (profile, timestamp)
        self._profile_cache: Dict[Tuple[Path, bool], Tuple[any, float]] = {}

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

        # 3. Get domain insight (always try - they're fast and cached)
        # Domain insights are typically <50ms due to caching, so we try even if over budget
        try:
            self._add_domain_insight(context, cwd, task, project_name)
        except Exception:
            pass  # Graceful degradation

        # 4. Get process context (fast, <50ms)
        try:
            self._add_process_context(context)
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
                        return (
                            parts[-1]
                            if parts[-1] not in ["audio", "weather", "health"]
                            else parts[-2]
                        )
                    return parts[0]
            except ValueError:
                pass

        return cwd.name

    def _add_profile(self, context: InjectionContext, cwd: Path, quick: bool = True):
        """Add project profile to context (with caching)."""
        # Find project root
        project_root = self._find_project_root(cwd)

        # Check cache
        cache_key = (project_root, quick)
        current_time = time.time()

        if cache_key in self._profile_cache:
            profile, cache_time = self._profile_cache[cache_key]
            age = current_time - cache_time
            if age < self.PROFILE_CACHE_TTL:
                # Use cached profile
                self._apply_profile_to_context(context, profile)
                return

        # Cache miss - generate profile
        profiler = ProjectProfiler(project_root)
        profile = profiler.profile(quick=quick)

        # Cache the profile
        self._profile_cache[cache_key] = (profile, current_time)

        # Apply to context
        self._apply_profile_to_context(context, profile)

    def _apply_profile_to_context(self, context: InjectionContext, profile):
        """Apply profile data to context."""
        # Add to context
        context.tech_stack = profile.tech_stack.to_compact_str()

        # Add coverage if low
        if profile.test_coverage.estimated_coverage < 70:
            coverage_pct = int(profile.test_coverage.estimated_coverage)
            context.coverage = f"{coverage_pct}% test coverage"

        # Add warnings (max 2)
        if profile.warnings:
            context.warnings.extend(profile.warnings[:2])

    def _add_patterns(self, context: InjectionContext, task: str, project: str):
        """Add pattern hints to context."""
        if not task:
            # No task provided, skip pattern search
            return

        if self._pattern_memory is None:
            self._pattern_memory = PatternMemory(self.root_dir)

        # Check if pattern memory has patterns loaded
        if not self._pattern_memory.searcher:
            # No patterns available, skip
            return

        try:
            similar = self._pattern_memory.find_similar_solutions(
                task=task, current_project=project, limit=1
            )

            if similar and len(similar) > 0:
                top = similar[0]
                # Format pattern hint more compactly
                hint = f"Similar to {top.project}: {top.title[:50]}"
                if len(hint) > 70:
                    hint = hint[:67] + "..."
                context.pattern_hint = hint
        except Exception:
            # Graceful degradation - if pattern search fails, continue without it
            pass

    def _add_domain_insight(self, context: InjectionContext, cwd: Path, task: str, project: str):
        """Add domain expert insight and warnings."""
        expert = self._get_domain_expert(project)
        if expert:
            # Get quick insight for domain-specific hints
            insight = expert.get_quick_insight(cwd, task)
            if insight:
                context.domain_insight = insight

            # Get warnings (e.g., GRIB data freshness)
            try:
                warnings = expert.get_warnings(cwd)
                if warnings:
                    # Add domain warnings to context warnings list
                    for warning in warnings:
                        if isinstance(warning, DomainInsight):
                            # Format as compact string
                            warning_str = warning.to_compact_str(max_length=80)
                            if warning_str:
                                context.warnings.append(warning_str)
                        elif isinstance(warning, str):
                            context.warnings.append(warning)
            except Exception:
                # Graceful degradation - if warnings fail, continue without them
                pass

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

    def _add_process_context(self, context: InjectionContext):
        """Add process monitoring context."""
        if ProcessMonitor is None:
            # Process monitoring not available
            return

        # Lazy initialize process monitor
        if self._process_monitor is None:
            self._process_monitor = ProcessMonitor()

        # Get compact context for injection
        try:
            process_ctx = self._process_monitor.get_context_for_injection()
            if process_ctx:
                context.process_context = process_ctx
        except Exception:
            # Graceful degradation
            pass

    def _find_project_root(self, cwd: Path) -> Path:
        """Find project root directory (has .git or pyproject.toml)."""
        current = cwd
        while current != current.parent:
            if (current / ".git").exists() or (current / "pyproject.toml").exists():
                return current
            current = current.parent
        return cwd
