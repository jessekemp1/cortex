"""
Cortex Universal Bridge - The Neural Bus for AI Agents

This module provides a unified interface for ANY AI agent (Antigravity, Cursor, Claude Code)
to interact with the Cortex system. It replaces specific adapters.

Capabilities:
1. Context Retrieval (read_context)
2. Strategy Injection (inject_recommendation)
3. Action Triggering (trigger_action)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path to import Cortex modules
CORTEX_ROOT = Path(__file__).parent.parent.resolve()
if str(CORTEX_ROOT) not in sys.path:
    sys.path.insert(0, str(CORTEX_ROOT))

# Import Cortex modules - import separately so failures don't cascade
try:
    from cortex.context_intelligence import ContextIntelligence
except ImportError:
    ContextIntelligence = None

try:
    from cortex.integration.local_orchestrator import CortexLocalOrchestratorIntegration
except ImportError:
    CortexLocalOrchestratorIntegration = None

try:
    from cortex.portfolio_memory import PortfolioMemory
except ImportError:
    PortfolioMemory = None

try:
    from cortex.intelligence.models import IntelligenceQueryType
except ImportError:
    IntelligenceQueryType = None

try:
    from cortex.intelligence.spec_knowledge_base import SpecKnowledgeBase
except ImportError:
    SpecKnowledgeBase = None

try:
    from cortex.intelligence.session_manager import SessionManager
except ImportError:
    SessionManager = None

try:
    from cortex.intelligence.unified_intelligence import UnifiedIntelligence
except ImportError:
    UnifiedIntelligence = None

# Adaptive Latency (Deep Mode) imports
try:
    from cortex.intelligence.adaptive_latency import (
        DEEP_MODE,
        FAST_MODE,
        AdaptiveLatencyManager,
        AnalysisMode,
        SessionContext,
    )
except ImportError:
    AdaptiveLatencyManager = None
    AnalysisMode = None
    SessionContext = None
    DEEP_MODE = None
    FAST_MODE = None

try:
    from cortex.intelligence.deep_analysis import DeepAnalyzer, DeepIntelligence
except ImportError:
    DeepAnalyzer = None
    DeepIntelligence = None

# Phase 1: Advanced Intelligence imports
try:
    from prompts.registry import get_registry
except ImportError:
    get_registry = None

try:
    from intelligence.defensive_prompting import DefensivePrompting
except ImportError:
    DefensivePrompting = None

# AI Engineering: Context Optimizer
try:
    from intelligence.context_optimizer import (
        CategoryType,
        ContextItem,
        ContextOptimizer,
        optimize_prompt_context,
    )

    CONTEXT_OPTIMIZER_AVAILABLE = True
except ImportError:
    CONTEXT_OPTIMIZER_AVAILABLE = False
    optimize_prompt_context = None
    ContextOptimizer = None
    ContextItem = None
    CategoryType = None

# AI Engineering: Implicit Feedback
try:
    from intelligence.feedback.implicit_collector import ImplicitFeedbackCollector

    IMPLICIT_FEEDBACK_AVAILABLE = True
except ImportError:
    IMPLICIT_FEEDBACK_AVAILABLE = False
    ImplicitFeedbackCollector = None

# AI Engineering: Tiered Memory
try:
    from intelligence.memory.tiered_memory import MemoryItem, TieredMemory

    TIERED_MEMORY_AVAILABLE = True
except ImportError:
    TIERED_MEMORY_AVAILABLE = False
    TieredMemory = None
    MemoryItem = None

# AI Engineering: Hybrid Retriever
try:
    from intelligence.memory.hybrid_retriever import HybridRetriever

    HYBRID_RETRIEVER_AVAILABLE = True
except ImportError:
    HYBRID_RETRIEVER_AVAILABLE = False
    HybridRetriever = None

try:
    from config import load_config
except ImportError:
    load_config = None

# Synthetic Data Engine
try:
    from synthetic.generator import SyntheticGenerator
    from synthetic.schemas import GenerationRequest

    SYNTHETIC_AVAILABLE = True
except ImportError:
    SYNTHETIC_AVAILABLE = False
    SyntheticGenerator = None
    GenerationRequest = None

# V2 Prime: Engine imports
try:
    from cortex.engines.absorber import ContextAbsorber, Signal, SignalType
    from cortex.engines.broker import (
        ActionBroker,
        Intervention,
        InterventionType,
        Severity,
    )
    from cortex.engines.synthesis import (
        ContextGraph,
        Edge,
        EdgeType,
        Node,
        NodeType,
        SynthesisCore,
    )

    V2_PRIME_AVAILABLE = True
except ImportError:
    V2_PRIME_AVAILABLE = False
    ContextAbsorber = None
    SynthesisCore = None
    ContextGraph = None
    ActionBroker = None

# V2 Prime: Protocol imports
try:
    from cortex.protocols.iap import (
        Agent,
        AgentRole,
        IAPHandler,
        IAPMessage,
        MessageType,
    )

    IAP_AVAILABLE = True
except ImportError:
    IAP_AVAILABLE = False
    IAPHandler = None


try:
    from cortex.bridge_intelligence import IntelligenceMixin
    from cortex.bridge_system import SystemMixin
    from cortex.bridge_kempos import KempOSContractsMixin
except ImportError:
    from bridge_intelligence import IntelligenceMixin  # type: ignore[no-redef]
    from bridge_system import SystemMixin  # type: ignore[no-redef]
    from bridge_kempos import KempOSContractsMixin  # type: ignore[no-redef]


class CortexBridge(KempOSContractsMixin, IntelligenceMixin, SystemMixin):
    """Universal interface for AI agents to interact with Cortex.

    Composed from domain mixins for maintainability:
    - KempOSContractsMixin: capabilities, namespace doctor, events, namespaced recommendations
    - IntelligenceMixin: Context, recommendations, specs, feedback, analysis
    - SystemMixin: V2 Prime, health, dependencies, batch, planning, warnings

    See bridge_kempos.py, bridge_intelligence.py, and bridge_system.py for method implementations.
    """

    def __init__(self, root_dir: Optional[str | Path] = None):
        if root_dir is None:
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", Path.cwd()))
        self.root_dir = Path(root_dir)

        # Load configuration
        self.config = load_config() if load_config else None

        # Initialize sub-systems
        self.context_intel = ContextIntelligence(self.root_dir) if ContextIntelligence else None
        self.orchestrator = (
            CortexLocalOrchestratorIntegration(self.root_dir)
            if CortexLocalOrchestratorIntegration
            else None
        )
        self.portfolio = PortfolioMemory() if PortfolioMemory else None

        # Intelligence enhancements
        self.unified_intel = UnifiedIntelligence(self.root_dir) if UnifiedIntelligence else None

        # SpecKnowledgeBase may fail during init if chromadb not available
        try:
            self.spec_kb = SpecKnowledgeBase() if SpecKnowledgeBase else None
        except (ImportError, Exception):
            self.spec_kb = None

        self.session_mgr = SessionManager(self.root_dir) if SessionManager else None

        # Adaptive Latency: Deep Mode components
        self.latency_manager = AdaptiveLatencyManager() if AdaptiveLatencyManager else None
        self.deep_analyzer = DeepAnalyzer(self.root_dir) if DeepAnalyzer else None

        # Phase 1: Advanced Intelligence components
        self.prompt_registry = get_registry() if get_registry else None
        self.defensive = DefensivePrompting() if DefensivePrompting else None

        # AI Engineering: Context Optimizer
        self.context_optimizer = None
        if CONTEXT_OPTIMIZER_AVAILABLE and self.config and self.config.context_optimizer_enabled:
            try:
                self.context_optimizer = ContextOptimizer()
            except Exception:
                self.context_optimizer = None

        # AI Engineering: Implicit Feedback Collector
        self.implicit_feedback = None
        if IMPLICIT_FEEDBACK_AVAILABLE and self.config and self.config.implicit_feedback_enabled:
            try:
                self.implicit_feedback = ImplicitFeedbackCollector()
            except Exception:
                self.implicit_feedback = None

        # AI Engineering: Tiered Memory
        self.tiered_memory = None
        if TIERED_MEMORY_AVAILABLE and self.config and self.config.tiered_memory_enabled:
            try:
                pattern_memory = getattr(getattr(self, "portfolio", None), "pattern_memory", None)
                self.tiered_memory = TieredMemory(
                    short_term_max=50,
                    working_retention_days=7,
                    pattern_memory=pattern_memory,
                )
            except Exception:
                self.tiered_memory = None

        # AI Engineering: Hybrid Retriever
        self.hybrid_retriever = None
        if HYBRID_RETRIEVER_AVAILABLE and self.config and self.config.hybrid_retrieval_enabled:
            try:
                # Priority 1: Reuse TieredMemory's existing hybrid retriever (already has 397+ patterns)
                if (
                    self.tiered_memory
                    and hasattr(self.tiered_memory, "long_term")
                    and hasattr(self.tiered_memory.long_term, "pattern_memory")
                ):
                    pm = self.tiered_memory.long_term.pattern_memory
                    if hasattr(pm, "hybrid_retriever") and pm.hybrid_retriever:
                        self.hybrid_retriever = pm.hybrid_retriever

                # Priority 2: Create new retriever from TieredMemory patterns
                if not self.hybrid_retriever and self.tiered_memory:
                    if hasattr(self.tiered_memory.long_term, "pattern_memory"):
                        pm = self.tiered_memory.long_term.pattern_memory
                        if hasattr(pm, "patterns") and pm.patterns:
                            self.hybrid_retriever = HybridRetriever(patterns=pm.patterns)

                # Priority 3: Fall back to portfolio patterns
                if not self.hybrid_retriever and self.portfolio:
                    if hasattr(self.portfolio, "get_patterns"):
                        patterns = self.portfolio.get_patterns()
                        if patterns:
                            self.hybrid_retriever = HybridRetriever(patterns=patterns)
            except Exception:
                self.hybrid_retriever = None

        # Synthetic Data Engine
        self.synthetic_generator = None
        if SYNTHETIC_AVAILABLE:
            try:
                self.synthetic_generator = SyntheticGenerator()
            except Exception:
                self.synthetic_generator = None

        # V2 Prime: Engine initialization
        self._init_v2_prime()

    def _init_v2_prime(self) -> None:
        """Initialize V2 Prime engines."""
        self.v2_available = V2_PRIME_AVAILABLE

        if not V2_PRIME_AVAILABLE:
            self.absorber = None
            self.synthesis = None
            self.broker = None
            self.iap = None
            return

        try:
            # Engine A: Context Absorber
            self.absorber = ContextAbsorber(self.root_dir)

            # Engine B: Synthesis Core with Context Graph
            self.graph = ContextGraph()
            self.synthesis = SynthesisCore(self.graph)

            # Engine C: Action Broker
            self.broker = ActionBroker()

            # Engine D: Universal Signal Bus (connects A-C)
            from cortex.engines.universal_signal_bus import UniversalSignalBus

            self.signal_bus = UniversalSignalBus()

            # IAP Handler
            if IAP_AVAILABLE:
                self.iap = IAPHandler(synthesis_core=self.synthesis, action_broker=self.broker)
            else:
                self.iap = None

        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"V2 Prime init failed: {e}")
            self.absorber = None
            self.synthesis = None
            self.broker = None
            self.signal_bus = None
            self.iap = None

    def end_session(self) -> None:
        """
        End session and consolidate memory.

        Cleans up AI Engineering modules:
        - TieredMemory: Consolidate and promote frequently accessed items
        - ImplicitFeedback: End session tracking
        """
        if self.tiered_memory:
            try:
                self.tiered_memory.end_session()
            except Exception:
                pass

        if self.implicit_feedback:
            try:
                self.implicit_feedback.session_end()
            except Exception:
                pass

    def _detect_current_project(self) -> str:
        """
        Auto-detect current project from git repo.

        Returns:
            Project name. Falls back to CORTEX_DEFAULT_PROJECT, then the
            workspace root's directory name, then "unknown" — never a
            hardcoded author project.
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=1,
                cwd=self.root_dir,
            )
            if result.returncode == 0:
                repo_path = Path(result.stdout.strip())
                return repo_path.name
        except Exception:
            pass

        # Derived fallback (not a literal author project).
        return os.environ.get("CORTEX_DEFAULT_PROJECT") or self.root_dir.name or "unknown"

    def _build_session_context(self, project: str):
        """
        Build SessionContext for adaptive mode selection.

        Args:
            project: Project name

        Returns:
            SessionContext object with current state
        """
        if not SessionContext:
            return None

        project_path = self.root_dir / project

        # Check for uncommitted changes
        has_uncommitted = False
        branch_is_stale = False

        try:
            import subprocess

            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=2,
            )
            has_uncommitted = len(status_result.stdout.strip()) > 0
        except Exception:
            pass

        return SessionContext(
            last_session_time=None,  # TODO: Track last session time
            time_since_last_session=None,
            project_name=project,
            has_uncommitted_changes=has_uncommitted,
            branch_is_stale=branch_is_stale,
            user_preference=None,
        )

    def _serialize_deep_intelligence(self, intelligence) -> Dict[str, Any]:
        """
        Convert DeepIntelligence object to JSON-serializable dict.

        Args:
            intelligence: DeepIntelligence object

        Returns:
            JSON-serializable dictionary
        """
        try:
            return {
                "timestamp": intelligence.timestamp.isoformat(),
                "project": intelligence.project,
                "mode": intelligence.mode,
                "latency_ms": intelligence.latency_ms,
                "health": {
                    "score": intelligence.health.score,
                    "assessment": intelligence.health.assessment,
                    "trend": intelligence.health.trend,
                    "commits_7d": intelligence.health.commits_7d,
                    "commits_30d": intelligence.health.commits_30d,
                    "uncommitted_files": intelligence.health.uncommitted_files,
                    "warnings": intelligence.health.warnings,
                },
                "git": {
                    "commit_count": intelligence.git.commit_count,
                    "authors": intelligence.git.authors,
                    "current_branch": intelligence.git.current_branch,
                    "stale_branches": intelligence.git.stale_branches,
                    "uncommitted_files": intelligence.git.uncommitted_files,
                },
                "quality": {
                    "todos": intelligence.quality.todos,
                    "fixmes": intelligence.quality.fixmes,
                    "tech_debt_markers": intelligence.quality.tech_debt_markers,
                },
                "warnings": intelligence.warnings,
                "recommendations": intelligence.recommendations,
                "next_actions": intelligence.next_actions,
                "analysis_config": intelligence.analysis_config,
            }
        except Exception as e:
            return {"error": f"Serialization failed: {str(e)}"}


def main():
    """CLI Interface for the Bridge (fallback if MCP not used)."""
    import argparse

    parser = argparse.ArgumentParser(description="Cortex Universal Bridge CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # context
    ctx_parser = subparsers.add_parser("context", help="Get context")
    ctx_parser.add_argument("query")
    ctx_parser.add_argument("--project", help="Filter by project")

    # inject
    inj_parser = subparsers.add_parser("inject", help="Inject recommendation")
    inj_parser.add_argument("title")
    inj_parser.add_argument("rationale")
    inj_parser.add_argument("--priority", default="medium")

    # trigger
    trig_parser = subparsers.add_parser("trigger", help="Trigger agent")
    trig_parser.add_argument("agent")
