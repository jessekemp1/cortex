"""
Trust Autonomy Bridge

The ONE novel concept from the Exponential Collaboration research:
Trust levels that actually change AI behavior.

NOT duplicated elsewhere in Cortex:
- learning.py tracks outcomes but doesn't gate autonomy
- feedback.py records implicit signals but doesn't adjust behavior
- absorber.py ingests signals but doesn't calibrate confidence

This module bridges the gap: observed outcomes → trust level → autonomy policy.

Usage:
    bridge = TrustAutonomyBridge()
    bridge.record_outcome("test_writing", success=True)
    policy = bridge.get_autonomy_policy("test_writing")
    # policy.review_required == False (Level 3+)
    # policy.confidence_display == "[L3:94%]"
    # policy.delegation_hint == "Act, report post-hoc"
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TrustLevel(IntEnum):
    VERIFY_ALL = 0  # Human checks everything
    SPOT_CHECK = 1  # Human samples ~20%
    TRUST_VERIFY = 2  # Human reviews summaries
    AUTONOMOUS = 3  # AI acts, human reviews post-hoc
    FULL_AUTONOMY = 4  # AI acts independently


# ═══════════════════════════════════════════════════════════
# Backward-compatible exports (used by universal_signal_bus.py, engines/__init__.py)
# These are thin wrappers — the real signal pipeline is in engines/absorber.py
# ═══════════════════════════════════════════════════════════


class WorkstreamPhase(str, Enum):
    """Phases of work within a project."""

    PLAN = "plan"
    BUILD = "build"
    TEST = "test"
    SHIP = "ship"
    RESEARCH = "research"


class SignalSource(str, Enum):
    """Sources of workspace signals."""

    CLAUDE_CODE = "claude_code"
    CLAUDE_CHAT = "claude_chat"
    CURSOR = "cursor"
    COWORKER = "coworker"
    ITERM = "iterm"
    GIT = "git"
    MANUAL = "manual"


@dataclass
class WorkspaceSignal:
    """A signal from any tool in the workspace."""

    source: SignalSource
    timestamp: datetime
    project: str
    workstream: WorkstreamPhase
    content_type: str
    content: str
    context: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    signal_id: str = ""

    def __post_init__(self):
        if not self.signal_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S")
            self.signal_id = f"sig_{self.source.value}_{ts}_{hash(self.content) % 10000:04d}"


class WorkstreamOrchestrator:
    """Thin wrapper for backward compatibility.

    The trust logic lives in TrustAutonomyBridge below.
    Signal recording delegates to the universal signal bus.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "orchestrator.db"
        self._trust_bridge = TrustAutonomyBridge()
        self._signals: List[WorkspaceSignal] = []

    def record_signal(self, signal: WorkspaceSignal) -> None:
        self._signals.append(signal)

    def get_recent_signals(
        self, project: Optional[str] = None, limit: int = 20
    ) -> List[WorkspaceSignal]:
        signals = self._signals
        if project:
            signals = [s for s in signals if s.project == project]
        return signals[-limit:]

    def get_trust_summary(self) -> Dict[str, Any]:
        return {"bridge": self._trust_bridge.get_all_policies()}


# ═══════════════════════════════════════════════════════════
# Novel code: Trust Autonomy Bridge
# ═══════════════════════════════════════════════════════════


@dataclass
class AutonomyPolicy:
    """What the AI should do at a given trust level."""

    level: TrustLevel
    review_required: bool
    confidence_display: str  # e.g., "[L3:94%]"
    delegation_hint: str  # Human-readable guidance
    max_blast_radius: str  # "file" | "module" | "project" | "deploy"

    @staticmethod
    def for_level(level: TrustLevel, accuracy: float) -> "AutonomyPolicy":
        pct = f"{accuracy * 100:.0f}%"
        policies = {
            TrustLevel.VERIFY_ALL: AutonomyPolicy(
                level=level,
                review_required=True,
                confidence_display=f"[L0:{pct}]",
                delegation_hint="Propose, wait for approval",
                max_blast_radius="file",
            ),
            TrustLevel.SPOT_CHECK: AutonomyPolicy(
                level=level,
                review_required=True,
                confidence_display=f"[L1:{pct}]",
                delegation_hint="Act on small changes, flag large ones",
                max_blast_radius="file",
            ),
            TrustLevel.TRUST_VERIFY: AutonomyPolicy(
                level=level,
                review_required=False,
                confidence_display=f"[L2:{pct}]",
                delegation_hint="Act, provide summary for review",
                max_blast_radius="module",
            ),
            TrustLevel.AUTONOMOUS: AutonomyPolicy(
                level=level,
                review_required=False,
                confidence_display=f"[L3:{pct}]",
                delegation_hint="Act, report post-hoc",
                max_blast_radius="project",
            ),
            TrustLevel.FULL_AUTONOMY: AutonomyPolicy(
                level=level,
                review_required=False,
                confidence_display=f"[L4:{pct}]",
                delegation_hint="Full autonomy in domain",
                max_blast_radius="deploy",
            ),
        }
        return policies[level]


class TrustAutonomyBridge:
    """
    Bridges Cortex's existing outcome tracking → actionable autonomy policies.

    Reads from: learning.py outcome patterns (don't duplicate)
    Produces: AutonomyPolicy per domain (new capability)

    Integration points:
    - Cortex Conductor: route tasks to haiku/sonnet/opus based on trust level
    - Shell prompt: display [L2:87%] badge
    - Session context: include autonomy hints in injected context
    """

    # Thresholds for level advancement (outcomes_needed, max_error_rate)
    THRESHOLDS = {
        TrustLevel.SPOT_CHECK: (10, 0.15),
        TrustLevel.TRUST_VERIFY: (25, 0.10),
        TrustLevel.AUTONOMOUS: (50, 0.05),
        TrustLevel.FULL_AUTONOMY: (100, 0.03),
    }

    def evaluate_level(self, outcomes: int, error_rate: float) -> TrustLevel:
        """Pure function: given outcomes and error rate, what trust level?"""
        for level in reversed(list(TrustLevel)):
            if level == TrustLevel.VERIFY_ALL:
                continue
            needed, max_err = self.THRESHOLDS[level]
            if outcomes >= needed and error_rate <= max_err:
                return level
        return TrustLevel.VERIFY_ALL

    def get_autonomy_policy(self, domain: str) -> AutonomyPolicy:
        """Get the autonomy policy for a domain.

        Reads from Cortex LearningSystem if available, falls back to defaults.

        LearningSystem.get_outcome_patterns() returns:
            {"recommendation_type": {"total": N, "followed": N, "success_rate": 0.X, "avg_confidence": 0.X}}

        We map recommendation_type → domain for trust tracking.
        """
        outcomes = 0
        error_rate = 1.0

        try:
            # Try package import first, then direct
            try:
                from cortex.learning import LearningSystem
            except ImportError:
                from learning import LearningSystem

            ls = LearningSystem()
            patterns = ls.get_outcome_patterns()

            # Match domain to recommendation type(s)
            domain_data = patterns.get(domain, {})
            if domain_data:
                outcomes = domain_data.get("total", 0)
                success_rate = domain_data.get("success_rate", 0.0)
                error_rate = 1.0 - success_rate
            else:
                # Aggregate across all types as fallback
                total = sum(p.get("total", 0) for p in patterns.values())
                if total > 0:
                    weighted_sr = (
                        sum(p.get("success_rate", 0) * p.get("total", 0) for p in patterns.values())
                        / total
                    )
                    outcomes = total
                    error_rate = 1.0 - weighted_sr
        except Exception:
            pass  # No learning data — stays at VERIFY_ALL

        level = self.evaluate_level(outcomes, error_rate)
        accuracy = 1.0 - error_rate
        return AutonomyPolicy.for_level(level, accuracy)

    def get_all_policies(self) -> dict:
        """Get autonomy policies for all known domains.

        Returns dict of domain → AutonomyPolicy.
        """
        policies = {}
        try:
            try:
                from cortex.learning import LearningSystem
            except ImportError:
                from learning import LearningSystem

            ls = LearningSystem()
            patterns = ls.get_outcome_patterns()

            for domain in patterns:
                policies[domain] = self.get_autonomy_policy(domain)
        except Exception:
            pass

        return policies
