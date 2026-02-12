"""
Adaptive Latency - Intelligent mode selection for Cortex

Provides both fast and deep analysis modes, with adaptive selection
based on context and user preference.

Design Principle: Depth over speed (deep mode is default)
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class AnalysisMode(Enum):
    """Analysis depth modes"""

    FAST = "fast"  # Minimal analysis (~500ms)
    DEEP = "deep"  # Comprehensive analysis (2-5s) - DEFAULT
    AUTO = "auto"  # Adaptive based on context


@dataclass
class AnalysisConfig:
    """Configuration for each analysis mode"""

    # Git analysis
    git_days: int  # Days of git history to analyze
    git_include_stats: bool  # Include code churn stats

    # Spec search
    spec_search_enabled: bool  # Auto-search for relevant specs
    spec_limit: int  # Number of specs to retrieve

    # Pattern matching
    pattern_semantic: bool  # Use semantic embeddings vs keywords
    pattern_limit: int  # Number of patterns to match

    # Health analysis
    health_fresh: bool  # Fresh calculation vs cached
    health_trend_days: int  # Days for trend analysis

    # Code quality
    quality_enabled: bool  # Run code quality analysis
    quality_depth: str  # "basic" or "comprehensive"

    # Dependencies
    dependency_analysis: bool  # Analyze dependency graph

    # Model selection
    model: str  # "haiku", "sonnet", or "opus"
    use_batch_api: bool  # Use batch API for analysis

    # Expected performance
    expected_latency_ms: int  # Target latency

    @property
    def mode_name(self) -> str:
        """Human-readable mode name"""
        if self.expected_latency_ms < 1000:
            return "fast"
        elif self.expected_latency_ms < 3000:
            return "balanced"
        else:
            return "deep"


# Mode configurations
FAST_MODE = AnalysisConfig(
    git_days=7,
    git_include_stats=False,
    spec_search_enabled=False,
    spec_limit=0,
    pattern_semantic=False,
    pattern_limit=3,
    health_fresh=False,
    health_trend_days=7,
    quality_enabled=False,
    quality_depth="basic",
    dependency_analysis=False,
    model="haiku",
    use_batch_api=False,
    expected_latency_ms=500,
)

DEEP_MODE = AnalysisConfig(
    git_days=90,
    git_include_stats=True,
    spec_search_enabled=True,
    spec_limit=5,
    pattern_semantic=True,
    pattern_limit=10,
    health_fresh=True,
    health_trend_days=30,
    quality_enabled=True,
    quality_depth="comprehensive",
    dependency_analysis=True,
    model="opus",
    use_batch_api=True,
    expected_latency_ms=5000,
)

# Balanced mode (for auto-selection)
BALANCED_MODE = AnalysisConfig(
    git_days=30,
    git_include_stats=True,
    spec_search_enabled=True,
    spec_limit=3,
    pattern_semantic=True,
    pattern_limit=5,
    health_fresh=True,
    health_trend_days=14,
    quality_enabled=True,
    quality_depth="basic",
    dependency_analysis=False,
    model="sonnet",
    use_batch_api=True,
    expected_latency_ms=2000,
)


@dataclass
class SessionContext:
    """Context for adaptive mode selection"""

    last_session_time: Optional[datetime]
    time_since_last_session: Optional[timedelta]
    project_name: str
    has_uncommitted_changes: bool
    branch_is_stale: bool
    user_preference: Optional[AnalysisMode]


class AdaptiveLatencyManager:
    """
    Manages adaptive mode selection for Cortex analysis

    Design:
    - Default to DEEP mode (depth over speed)
    - FAST mode only on explicit request
    - AUTO mode learns from context and user behavior
    """

    def __init__(self, storage_dir: Path = Path.home() / ".cortex"):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.preference_file = storage_dir / "mode_preferences.json"
        self.preferences = self._load_preferences()

    def _load_preferences(self) -> Dict:
        """Load user mode preferences"""
        if not self.preference_file.exists():
            return {"default_mode": "deep", "project_overrides": {}}

        try:
            with open(self.preference_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"default_mode": "deep", "project_overrides": {}}

    def _save_preferences(self):
        """Save user mode preferences"""
        try:
            with open(self.preference_file, "w") as f:
                json.dump(self.preferences, f, indent=2)
        except IOError:
            pass  # Fail silently

    def select_mode(
        self,
        requested_mode: AnalysisMode,
        context: Optional[SessionContext] = None,
    ) -> AnalysisConfig:
        """
        Select analysis mode based on request and context

        Args:
            requested_mode: User-requested mode (FAST, DEEP, AUTO)
            context: Session context for adaptive selection

        Returns:
            AnalysisConfig for selected mode
        """
        # Direct requests always honored
        if requested_mode == AnalysisMode.FAST:
            return FAST_MODE

        if requested_mode == AnalysisMode.DEEP:
            return DEEP_MODE

        # AUTO mode: intelligent selection
        return self._select_auto_mode(context)

    def _select_auto_mode(self, context: Optional[SessionContext]) -> AnalysisConfig:
        """
        Intelligently select mode based on context

        Decision logic:
        1. Check project-specific preference
        2. Check time since last session
        3. Check repository state
        4. Default to DEEP (our strategic priority)
        """
        if context is None:
            return DEEP_MODE  # Default to deep when no context

        # 1. Project-specific override
        if context.project_name in self.preferences.get("project_overrides", {}):
            override = self.preferences["project_overrides"][context.project_name]
            if override == "fast":
                return FAST_MODE
            elif override == "balanced":
                return BALANCED_MODE

        # 2. User preference override
        if context.user_preference:
            if context.user_preference == AnalysisMode.FAST:
                return FAST_MODE
            elif context.user_preference == AnalysisMode.DEEP:
                return DEEP_MODE

        # 3. Time-based heuristic
        if context.time_since_last_session:
            # Quick check (< 5 minutes since last session)
            if context.time_since_last_session < timedelta(minutes=5):
                return BALANCED_MODE  # Likely context switch, balanced is fine

            # Fresh start (> 1 hour since last session)
            if context.time_since_last_session > timedelta(hours=1):
                return DEEP_MODE  # Definitely want comprehensive context

        # 4. Repository state heuristic
        if context.has_uncommitted_changes or context.branch_is_stale:
            # Active development or potential issues → deep analysis helpful
            return DEEP_MODE

        # 5. Default to DEEP (strategic priority)
        return DEEP_MODE

    def set_project_preference(self, project: str, mode: str):
        """
        Set project-specific mode preference

        Args:
            project: Project name
            mode: "fast", "balanced", or "deep"
        """
        if "project_overrides" not in self.preferences:
            self.preferences["project_overrides"] = {}

        self.preferences["project_overrides"][project] = mode
        self._save_preferences()

    def set_default_preference(self, mode: str):
        """
        Set default mode preference

        Args:
            mode: "fast", "balanced", or "deep"
        """
        self.preferences["default_mode"] = mode
        self._save_preferences()

    def get_mode_statistics(self) -> Dict:
        """
        Get statistics on mode usage

        Returns:
            Dict with mode usage stats
        """
        # TODO: Track mode selection and outcomes
        # This will enable learning which mode works best
        return {
            "default_mode": self.preferences.get("default_mode", "deep"),
            "project_overrides": len(self.preferences.get("project_overrides", {})),
        }

    def recommend_mode(self, context: SessionContext) -> str:
        """
        Recommend mode with explanation

        Args:
            context: Session context

        Returns:
            Human-readable recommendation
        """
        selected = self._select_auto_mode(context)
        mode_name = selected.mode_name

        reasons = []

        if context.time_since_last_session:
            if context.time_since_last_session < timedelta(minutes=5):
                reasons.append("recent context switch")
            elif context.time_since_last_session > timedelta(hours=1):
                reasons.append("fresh start needs comprehensive context")

        if context.has_uncommitted_changes:
            reasons.append("uncommitted work detected")

        if context.branch_is_stale:
            reasons.append("stale branch needs review")

        if not reasons:
            reasons.append("default depth-first strategy")

        reason_str = ", ".join(reasons)

        return f"Recommending {mode_name} mode ({selected.expected_latency_ms}ms): {reason_str}"


# Convenience functions
def get_fast_config() -> AnalysisConfig:
    """Get fast mode configuration"""
    return FAST_MODE


def get_deep_config() -> AnalysisConfig:
    """Get deep mode configuration (DEFAULT)"""
    return DEEP_MODE


def get_balanced_config() -> AnalysisConfig:
    """Get balanced mode configuration"""
    return BALANCED_MODE


# CLI helper
if __name__ == "__main__":
    import sys

    manager = AdaptiveLatencyManager()

    if len(sys.argv) < 2:
        print("Usage: python adaptive_latency.py <command>")
        print("\nCommands:")
        print("  show              - Show current preferences")
        print("  set-default MODE  - Set default mode (fast/balanced/deep)")
        print("  set-project PROJECT MODE - Set project-specific mode")
        print("  stats             - Show usage statistics")
        sys.exit(1)

    command = sys.argv[1]

    if command == "show":
        print(json.dumps(manager.preferences, indent=2))

    elif command == "set-default":
        if len(sys.argv) < 3:
            print("Error: mode required")
            sys.exit(1)
        mode = sys.argv[2]
        manager.set_default_preference(mode)
        print(f"Default mode set to: {mode}")

    elif command == "set-project":
        if len(sys.argv) < 4:
            print("Error: project and mode required")
            sys.exit(1)
        project = sys.argv[2]
        mode = sys.argv[3]
        manager.set_project_preference(project, mode)
        print(f"Project '{project}' mode set to: {mode}")

    elif command == "stats":
        stats = manager.get_mode_statistics()
        print(json.dumps(stats, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
