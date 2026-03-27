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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
except ImportError:
    from bridge_intelligence import IntelligenceMixin  # type: ignore[no-redef]
    from bridge_system import SystemMixin  # type: ignore[no-redef]


class CortexBridge(IntelligenceMixin, SystemMixin):
    """Universal interface for AI agents to interact with Cortex.

    Composed from domain mixins for maintainability:
    - IntelligenceMixin: Context, recommendations, specs, feedback, analysis
    - SystemMixin: V2 Prime, health, dependencies, batch, planning, warnings

    See bridge_intelligence.py and bridge_system.py for method implementations.
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
            Project name (defaults to "cortex" if detection fails)
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

        return "cortex"  # Default fallback

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

    # portfolio
    port_parser = subparsers.add_parser("portfolio", help="Portfolio operations")
    port_sub = port_parser.add_subparsers(dest="subcommand", help="Portfolio subcommand")

    # portfolio patterns
    patterns_parser = port_sub.add_parser("patterns", help="Get cross-project patterns")
    patterns_parser.add_argument("--type", help="Pattern type filter")

    # portfolio lessons
    lessons_parser = port_sub.add_parser("lessons", help="Get lessons learned")
    lessons_parser.add_argument("--project", help="Filter by project")
    lessons_parser.add_argument("--pattern", help="Filter by pattern")

    # portfolio project
    project_parser = port_sub.add_parser("project", help="Get project context")
    project_parser.add_argument("name", help="Project name")

    # portfolio stats
    port_sub.add_parser("stats", help="Get portfolio statistics")

    # intelligence
    intel_parser = subparsers.add_parser("intelligence", help="Query unified intelligence")
    intel_parser.add_argument("request", help="User request")
    intel_parser.add_argument("--project", required=True, help="Project name")
    intel_parser.add_argument(
        "--type", default="spec", help="Query type (spec/impl/analysis/research)"
    )

    # similar-work
    similar_parser = subparsers.add_parser("similar-work", help="Find similar work")
    similar_parser.add_argument("domain", help="Domain/topic")
    similar_parser.add_argument("--project", required=True, help="Project name")
    similar_parser.add_argument("--limit", type=int, default=5, help="Max results")

    # session-context
    session_parser = subparsers.add_parser("session-context", help="Get session context")
    session_parser.add_argument(
        "--format",
        choices=["json", "terminal", "compact"],
        default="json",
        help="Output format",
    )
    session_parser.add_argument(
        "--max-chars", type=int, default=450, help="Max characters for compact format"
    )

    # index-spec
    index_parser = subparsers.add_parser("index-spec", help="Index a spec")
    index_parser.add_argument("path", help="Path to spec file")
    index_parser.add_argument("--project", required=True, help="Project name")
    index_parser.add_argument("--domain", help="Domain tag")

    # health - Project health analysis
    health_parser = subparsers.add_parser("health", help="Project health analysis")
    health_sub = health_parser.add_subparsers(dest="health_command", help="Health command")

    # health summary
    summary_parser = health_sub.add_parser("summary", help="Portfolio health summary")
    summary_parser.add_argument("--days", type=int, default=7, help="Days to analyze")

    # health project
    project_health_parser = health_sub.add_parser("project", help="Detailed project health")
    project_health_parser.add_argument("name", help="Project name")
    project_health_parser.add_argument("--days", type=int, default=7, help="Days to analyze")

    # health compare
    compare_parser = health_sub.add_parser("compare", help="Compare two projects")
    compare_parser.add_argument("project1", help="First project")
    compare_parser.add_argument("project2", help="Second project")
    compare_parser.add_argument("--days", type=int, default=7, help="Days to analyze")

    # health trends
    trends_parser = health_sub.add_parser("trends", help="Health trends for project")
    trends_parser.add_argument("name", help="Project name")

    # plan - Planning and execution
    plan_parser = subparsers.add_parser("plan", help="Plan creation and execution")
    plan_sub = plan_parser.add_subparsers(dest="plan_command", help="Plan command")

    # plan create
    create_plan_parser = plan_sub.add_parser("create", help="Create a plan from recommendations")
    create_plan_parser.add_argument("project", help="Project name")
    create_plan_parser.add_argument("--title", help="Plan title")

    # plan list
    list_plans_parser = plan_sub.add_parser("list", help="List all plans")
    list_plans_parser.add_argument(
        "--status",
        choices=["draft", "active", "completed", "cancelled"],
        help="Filter by status",
    )

    # plan show
    show_plan_parser = plan_sub.add_parser("show", help="Show plan details")
    show_plan_parser.add_argument("plan_id", help="Plan ID")
    show_plan_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format",
    )

    # plan start
    start_plan_parser = plan_sub.add_parser("start", help="Start plan execution")
    start_plan_parser.add_argument("plan_id", help="Plan ID")

    # plan complete
    complete_step_parser = plan_sub.add_parser("complete", help="Complete a step")
    complete_step_parser.add_argument("step_id", help="Step ID")
    complete_step_parser.add_argument("--notes", default="", help="Completion notes")

    # plan progress
    plan_sub.add_parser("progress", help="Show active plan progress")

    # profile - Project profiling (Layer 1)
    profile_parser = subparsers.add_parser(
        "profile", help="Analyze project structure and tech stack"
    )
    profile_parser.add_argument("project", help="Project name")

    # patterns - Pattern search (Layer 2)
    patterns_parser = subparsers.add_parser(
        "patterns", help="Find similar work from other projects"
    )
    patterns_parser.add_argument("project", help="Current project name")
    patterns_parser.add_argument("task", help="Task description")
    patterns_parser.add_argument("--limit", type=int, default=5, help="Maximum results")

    # mine-anti-patterns - Extract anti-patterns from failed outcomes
    mine_parser = subparsers.add_parser(
        "mine-anti-patterns", help="Extract anti-patterns from failed outcomes"
    )
    mine_parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    mine_parser.add_argument("--dry-run", action="store_true", help="Don't write to files")

    # batch
    batch_parser = subparsers.add_parser("batch", help="Batch API operations")
    batch_sub = batch_parser.add_subparsers(dest="batch_command", help="Batch subcommand")

    # batch research
    batch_research_parser = batch_sub.add_parser("research", help="Submit research batch")
    batch_research_parser.add_argument(
        "--file", required=True, help="JSON file with research items"
    )

    # batch briefing
    batch_briefing_parser = batch_sub.add_parser("briefing", help="Submit briefing batch")
    batch_briefing_parser.add_argument(
        "--file", required=True, help="JSON file with briefing contexts"
    )

    # batch status
    batch_status_parser = batch_sub.add_parser("status", help="Get batch status")
    batch_status_parser.add_argument("batch_id", help="Batch ID to check")

    # recommendations - Smart recommendations
    rec_parser = subparsers.add_parser("recommendations", help="Get smart recommendations")
    rec_sub = rec_parser.add_subparsers(dest="rec_command", help="Recommendation command")

    # recommendations report - full smart recommendations report
    rec_sub.add_parser("report", help="Get full recommendations report")

    # recommendations next - single next action
    rec_sub.add_parser("next", help="Get recommended next action")

    # recommendations alerts - risk alerts
    rec_sub.add_parser("alerts", help="Get risk alerts")

    # recommendations priorities - priority projects
    rec_priorities_parser = rec_sub.add_parser("priorities", help="Get priority projects")
    rec_priorities_parser.add_argument("--limit", type=int, default=5, help="Maximum projects")

    # recommendations get (legacy)
    rec_get_parser = rec_sub.add_parser("get", help="Get prioritized recommendations")
    rec_get_parser.add_argument("project", help="Project name")
    rec_get_parser.add_argument("--limit", type=int, default=10, help="Maximum recommendations")

    # recommendations dashboard (legacy)
    rec_dashboard_parser = rec_sub.add_parser("dashboard", help="Get recommendation dashboard")
    rec_dashboard_parser.add_argument("project", help="Project name")
    rec_dashboard_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum recommendations"
    )

    args = parser.parse_args()
    bridge = CortexBridge()

    if args.command == "context":
        print(json.dumps(bridge.get_context(args.query, project=args.project), indent=2))
    elif args.command == "inject":
        success = bridge.inject_recommendation(args.title, args.rationale, priority=args.priority)
        print(json.dumps({"success": success}))
    elif args.command == "trigger":
        print(json.dumps(bridge.trigger_action(args.agent)))
    elif args.command == "portfolio":
        if args.subcommand == "patterns":
            result = bridge.get_patterns(pattern_type=getattr(args, "type", None))
            print(json.dumps(result, indent=2))
        elif args.subcommand == "lessons":
            result = bridge.get_lessons(
                project=getattr(args, "project", None),
                pattern=getattr(args, "pattern", None),
            )
            print(json.dumps(result, indent=2))
        elif args.subcommand == "project":
            result = bridge.get_portfolio_context(args.name)
            print(json.dumps(result, indent=2))
        elif args.subcommand == "stats":
            result = bridge.get_portfolio_stats()
            print(json.dumps(result, indent=2))
        else:
            port_parser.print_help()
    elif args.command == "intelligence":
        result = bridge.query_intelligence(
            args.request, args.project, getattr(args, "type", "spec")
        )
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "similar-work":
        result = bridge.find_similar_work(args.domain, args.project, getattr(args, "limit", 5))
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "session-context":
        result = bridge.get_session_context()
        format_type = getattr(args, "format", "json")

        # Handle compact format for inject_context hook (<450 chars)
        if format_type == "compact":
            if "error" in result:
                # Fallback to empty context
                print("")
                sys.exit(0)

            max_chars = getattr(args, "max_chars", 450)
            parts = []

            # Project
            project = result.get("project", "Unknown")
            parts.append(f"Project: {project}")

            # Focus (truncate if needed)
            focus = result.get("current_focus", "No active focus")
            if len(focus) > 50:
                focus = focus[:47] + "..."
            parts.append(f"Focus: {focus}")

            # First goal if available
            if result.get("active_goals"):
                goal = result["active_goals"][0]
                if len(goal) > 40:
                    goal = goal[:37] + "..."
                parts.append(f"Goal: {goal}")

            # Build compact string
            compact = " | ".join(parts)

            # Enforce max_chars limit
            if len(compact) > max_chars:
                compact = compact[: max_chars - 3] + "..."

            print(compact)

        # Handle terminal format for shell startup display
        elif format_type == "terminal":
            if "error" in result:
                # Fail silently for startup hook
                sys.exit(0)

            print("\n🧠 Cortex Session Intelligence\n")

            # Handle nested project structure
            project_info = result.get("project", {})
            if isinstance(project_info, dict):
                project_name = project_info.get("name", "Unknown")
            else:
                project_name = project_info
            print(f"📂 Project: {project_name}")

            print(
                f"🎯 Focus: {result.get('focus', result.get('current_focus', 'No active focus'))}"
            )

            # Handle goals (could be in 'goals' or 'active_goals')
            goals = result.get("goals", result.get("active_goals", []))
            if goals:
                goals_display = goals[:3]  # Show max 3 goals
                print(f"✅ Goals: {', '.join(goals_display)}")

            # Handle recent work (could be in git.recent_commits or recent_work)
            git_info = result.get("git", {})
            recent_commits = git_info.get("recent_commits", result.get("recent_work", []))
            if recent_commits:
                print("\n📝 Recent Work:")
                for work in recent_commits[:3]:  # Show max 3 items
                    print(f"   • {work.get('summary', work.get('commit', 'Unknown'))}")

            print()  # Empty line for spacing
        else:
            # JSON format (default)
            print(json.dumps(result, indent=2, default=str))
    elif args.command == "index-spec":
        result = bridge.index_spec(args.path, args.project, getattr(args, "domain", None))
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "health":
        import subprocess

        # Delegate to data agent CLI
        cortex_root = Path(__file__).parent

        if args.health_command == "summary":
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agents.data_agent.cli",
                    "summary",
                    str(getattr(args, "days", 7)),
                ],
                cwd=cortex_root,
            )
        elif args.health_command == "project":
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agents.data_agent.cli",
                    "project",
                    args.name,
                    str(getattr(args, "days", 7)),
                ],
                cwd=cortex_root,
            )
        elif args.health_command == "compare":
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agents.data_agent.cli",
                    "compare",
                    args.project1,
                    args.project2,
                    str(getattr(args, "days", 7)),
                ],
                cwd=cortex_root,
            )
        elif args.health_command == "trends":
            subprocess.run(
                [sys.executable, "-m", "agents.data_agent.cli", "trends", args.name],
                cwd=cortex_root,
            )
        else:
            health_parser.print_help()
    elif args.command == "plan":
        if args.plan_command == "create":
            result = bridge.create_plan(args.project, title=getattr(args, "title", None))
            print(json.dumps(result, indent=2))
        elif args.plan_command == "list":
            result = bridge.list_plans(status=getattr(args, "status", None))
            print(json.dumps(result, indent=2))
        elif args.plan_command == "show":
            result = bridge.get_plan(args.plan_id, format=getattr(args, "format", "json"))
            if getattr(args, "format", "json") == "markdown":
                print(result.get("markdown", "No plan found"))
            else:
                print(json.dumps(result, indent=2))
        elif args.plan_command == "start":
            result = bridge.start_plan(args.plan_id)
            print(json.dumps(result, indent=2))
        elif args.plan_command == "complete":
            result = bridge.complete_step(args.step_id, notes=getattr(args, "notes", ""))
            print(json.dumps(result, indent=2))
        elif args.plan_command == "progress":
            result = bridge.get_plan_progress()
            print(json.dumps(result, indent=2))
        else:
            plan_parser.print_help()
    elif args.command == "profile":
        result = bridge.get_project_profile(args.project)
        print(json.dumps(result, indent=2))
    elif args.command == "patterns":
        result = bridge.find_similar_work(args.project, args.task, limit=getattr(args, "limit", 5))
        print(json.dumps(result, indent=2))
    elif args.command == "mine-anti-patterns":
        import subprocess

        script_path = os.environ.get("CORTEX_ANTI_PATTERNS_SCRIPT")
        if not script_path:
            print(
                "Error: CORTEX_ANTI_PATTERNS_SCRIPT env var not set.\n"
                "Point it to your mine_anti_patterns.py script path.",
                file=sys.stderr,
            )
            sys.exit(1)
        cmd = ["python3", script_path]
        cmd.extend(["--days", str(getattr(args, "days", 30))])
        if getattr(args, "dry_run", False):
            cmd.append("--dry-run")
        result = subprocess.run(cmd, capture_output=False)
        sys.exit(result.returncode)
    elif args.command == "recommendations":
        if args.rec_command == "report":
            result = bridge.get_recommendations()
            print(json.dumps(result, indent=2, default=str))
        elif args.rec_command == "next":
            result = bridge.get_next_action()
            # Pretty print for terminal
            print("\n🎯 Recommended Next Action")
            print(f"   Priority: {result.get('priority', 'Unknown')}")
            print(f"   Action: {result.get('action', 'Unknown')}")
            if result.get("project"):
                print(f"   Project: {result['project']}")
            print()
        elif args.rec_command == "alerts":
            alerts = bridge.get_risk_alerts()
            if not alerts or (len(alerts) == 1 and "error" in alerts[0]):
                print("\n✅ No risk alerts\n")
            else:
                print(f"\n⚠️  Risk Alerts ({len(alerts)})")
                for alert in alerts:
                    icon = (
                        "🔴"
                        if alert.get("severity") == "HIGH"
                        else "🟡"
                        if alert.get("severity") == "MEDIUM"
                        else "🟢"
                    )
                    print(
                        f"   {icon} [{alert.get('severity', 'Unknown')}] {alert.get('message', 'Unknown')}"
                    )
                    print(f"      → {alert.get('recommendation', '')}")
                print()
        elif args.rec_command == "priorities":
            priorities = bridge.get_priority_projects(limit=getattr(args, "limit", 5))
            print(f"\n📋 Priority Projects ({len(priorities)})")
            for i, p in enumerate(priorities, 1):
                health = f" [{p.get('health_score')}/100]" if p.get("health_score") else ""
                print(
                    f"   {i}. [{p.get('priority', 'Unknown')}] {p.get('project', 'Unknown')}{health}"
                )
                print(f"      {p.get('reason', '')}")
            print()
        elif args.rec_command == "get":
            result = bridge.get_smart_recommendations(
                args.project, limit=getattr(args, "limit", 10)
            )
            print(json.dumps(result, indent=2))
        elif args.rec_command == "dashboard":
            result = bridge.get_recommendation_dashboard(
                args.project, limit=getattr(args, "limit", 10)
            )
            print(json.dumps(result, indent=2))
        else:
            rec_parser.print_help()
    elif args.command == "batch":
        if args.batch_command == "research":
            # Load research items from JSON file
            with open(args.file, "r") as f:
                research_items = json.load(f)
            result = bridge.submit_research_batch(research_items)
            print(json.dumps(result, indent=2))
        elif args.batch_command == "briefing":
            # Load briefing contexts from JSON file
            with open(args.file, "r") as f:
                contexts = json.load(f)
            result = bridge.submit_briefing_batch(contexts)
            print(json.dumps(result, indent=2))
        elif args.batch_command == "status":
            result = bridge.get_batch_status(args.batch_id)
            print(json.dumps(result, indent=2))
        else:
            batch_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
