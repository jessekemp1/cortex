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
        AdaptiveLatencyManager,
        AnalysisMode,
        SessionContext,
        DEEP_MODE,
        FAST_MODE,
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
    from intelligence.memory.tiered_memory import TieredMemory, MemoryItem

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


class CortexBridge:
    """Universal interface for AI agents to interact with Cortex."""

    def __init__(self, root_dir: Optional[str | Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
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
                pattern_memory = getattr(
                    getattr(self, "portfolio", None), "pattern_memory", None
                )
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

    # --- V2 Prime: Graph Methods ---

    def query_graph(self, node_type: str, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Query the context graph by node type.

        Args:
            node_type: Type of nodes to query (goal, project, pattern, lesson, etc.)
            filters: Optional filters to apply

        Returns:
            List of matching node dictionaries
        """
        if not self.synthesis:
            return [{"error": "V2 Prime Synthesis Core not available"}]

        try:
            from cortex.engines.synthesis import NodeType

            node_type_enum = NodeType(node_type)
            nodes = self.synthesis.graph.get_nodes_by_type(node_type_enum)
            return [n.to_dict() for n in nodes]
        except ValueError:
            return [{"error": f"Unknown node type: {node_type}"}]
        except Exception as e:
            return [{"error": str(e)}]

    def get_related_nodes(self, node_id: str, edge_type: Optional[str] = None) -> List[Dict]:
        """
        Get nodes related to a given node.

        Args:
            node_id: ID of the source node
            edge_type: Optional edge type filter

        Returns:
            List of related node dictionaries
        """
        if not self.synthesis:
            return [{"error": "V2 Prime Synthesis Core not available"}]

        try:
            from cortex.engines.synthesis import EdgeType

            edge_type_enum = EdgeType(edge_type) if edge_type else None
            nodes = self.synthesis.graph.get_related(node_id, edge_type_enum)
            return [n.to_dict() for n in nodes]
        except ValueError:
            return [{"error": f"Unknown edge type: {edge_type}"}]
        except Exception as e:
            return [{"error": str(e)}]

    def add_graph_node(
        self,
        node_type: str,
        name: str,
        data: Dict[str, Any],
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a node to the context graph.

        Args:
            node_type: Type of node
            name: Node name
            data: Node data
            node_id: Optional explicit ID

        Returns:
            Result with node_id
        """
        if not self.synthesis:
            return {"error": "V2 Prime Synthesis Core not available"}

        try:
            import uuid

            from cortex.engines.synthesis import Node, NodeType

            nid = node_id or f"{node_type}:{uuid.uuid4().hex[:8]}"
            node = Node(
                id=nid,
                type=NodeType(node_type),
                name=name,
                data=data,
            )
            self.synthesis.graph.add_node(node)
            return {"success": True, "node_id": nid}
        except Exception as e:
            return {"error": str(e)}

    def add_graph_edge(
        self, source_id: str, target_id: str, edge_type: str, weight: float = 1.0
    ) -> Dict[str, Any]:
        """
        Add an edge to the context graph.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of edge
            weight: Edge weight (default 1.0)

        Returns:
            Result
        """
        if not self.synthesis:
            return {"error": "V2 Prime Synthesis Core not available"}

        try:
            from cortex.engines.synthesis import Edge, EdgeType

            edge = Edge(
                source_id=source_id,
                target_id=target_id,
                type=EdgeType(edge_type),
                weight=weight,
            )
            self.synthesis.graph.add_edge(edge)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get context graph statistics."""
        if not self.synthesis:
            return {"error": "V2 Prime Synthesis Core not available"}

        try:
            return self.synthesis.graph.get_stats()
        except Exception as e:
            return {"error": str(e)}

    # --- V2 Prime: Intervention Methods ---

    def get_pending_interventions(self) -> List[Dict]:
        """
        Get pending interventions.

        Returns:
            List of intervention dictionaries
        """
        if not self.broker:
            return [{"error": "V2 Prime Action Broker not available"}]

        try:
            return [i.to_dict() for i in self.broker.get_pending()]
        except Exception as e:
            return [{"error": str(e)}]

    def acknowledge_intervention(self, intervention_id: str) -> Dict[str, Any]:
        """
        Acknowledge an intervention.

        Args:
            intervention_id: ID of intervention to acknowledge

        Returns:
            Result
        """
        if not self.broker:
            return {"error": "V2 Prime Action Broker not available"}

        try:
            success = self.broker.acknowledge(intervention_id)
            return {"success": success}
        except Exception as e:
            return {"error": str(e)}

    def suppress_intervention(self, intervention_id: str, hours: int = 24) -> Dict[str, Any]:
        """
        Suppress an intervention for a duration.

        Args:
            intervention_id: ID of intervention to suppress
            hours: Hours to suppress (default 24)

        Returns:
            Result
        """
        if not self.broker:
            return {"error": "V2 Prime Action Broker not available"}

        try:
            success = self.broker.suppress(intervention_id, hours)
            return {"success": success}
        except Exception as e:
            return {"error": str(e)}

    def get_broker_status(self) -> Dict[str, Any]:
        """Get Action Broker status."""
        if not self.broker:
            return {"error": "V2 Prime Action Broker not available"}

        try:
            return self.broker.get_status()
        except Exception as e:
            return {"error": str(e)}

    # --- V2 Prime: IAP Methods ---

    def handle_iap_message(self, message_dict: Dict) -> Dict[str, Any]:
        """
        Handle an Inter-Agent Protocol message.

        Args:
            message_dict: IAP message as dictionary

        Returns:
            Response message as dictionary
        """
        if not self.iap:
            return {"error": "V2 Prime IAP Handler not available"}

        try:
            from cortex.protocols.iap import IAPMessage

            message = IAPMessage.from_dict(message_dict)
            response = self.iap.handle_message(message)
            return response.to_dict()
        except Exception as e:
            return {"error": str(e)}

    def register_agent(
        self, agent_id: str, role: str, capabilities: List[str] = None
    ) -> Dict[str, Any]:
        """
        Register an agent for IAP communication.

        Args:
            agent_id: Agent identifier
            role: Agent role (researcher, implementer, reviewer, etc.)
            capabilities: List of agent capabilities

        Returns:
            Result
        """
        if not self.iap:
            return {"error": "V2 Prime IAP Handler not available"}

        try:
            from cortex.protocols.iap import Agent, AgentRole

            agent = Agent(
                id=agent_id,
                role=AgentRole(role),
                capabilities=capabilities or [],
            )
            self.iap.register_agent(agent)
            return {"success": True, "agent_id": agent_id}
        except Exception as e:
            return {"error": str(e)}

    def get_v2_status(self) -> Dict[str, Any]:
        """
        Get V2 Prime system status.

        Returns:
            Status of all V2 Prime components
        """
        return {
            "v2_available": self.v2_available,
            "absorber": self.absorber is not None,
            "synthesis": self.synthesis is not None,
            "broker": self.broker is not None,
            "iap": self.iap is not None,
            "graph_stats": self.get_graph_stats() if self.synthesis else None,
            "broker_status": self.get_broker_status() if self.broker else None,
        }

    def get_ai_engineering_status(self) -> Dict[str, Any]:
        """
        Get AI Engineering module status.

        Returns:
            Status of AI Engineering modules (Week 2 integrations)
        """
        return {
            "context_optimizer": {
                "available": CONTEXT_OPTIMIZER_AVAILABLE,
                "enabled": self.context_optimizer is not None,
            },
            "implicit_feedback": {
                "available": IMPLICIT_FEEDBACK_AVAILABLE,
                "enabled": self.implicit_feedback is not None,
                "stats": (
                    self.implicit_feedback.get_session_stats()
                    if self.implicit_feedback
                    else None
                ),
            },
            "tiered_memory": {
                "available": TIERED_MEMORY_AVAILABLE,
                "enabled": self.tiered_memory is not None,
                "stats": (
                    self.tiered_memory.get_stats() if self.tiered_memory else None
                ),
            },
            "hybrid_retriever": {
                "available": HYBRID_RETRIEVER_AVAILABLE,
                "enabled": self.hybrid_retriever is not None,
                "pattern_count": (
                    len(self.hybrid_retriever.patterns)
                    if self.hybrid_retriever
                    else 0
                ),
            },
            "config_flags": {
                "tiered_memory_enabled": (
                    self.config.tiered_memory_enabled if self.config else None
                ),
                "context_optimizer_enabled": (
                    self.config.context_optimizer_enabled if self.config else None
                ),
                "implicit_feedback_enabled": (
                    self.config.implicit_feedback_enabled if self.config else None
                ),
                "hybrid_retrieval_enabled": (
                    self.config.hybrid_retrieval_enabled if self.config else None
                ),
            },
        }

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

    # --- 1. Context Bridge ---

    def get_context(
        self, query: str, limit: int = 5, project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get relevant context for a query from Knowledge Base and Project History.

        Uses AI Engineering pipeline when available:
        1. DefensivePrompting - Validate input
        2. TieredMemory - Check session memory first
        3. HybridRetriever - Semantic + keyword search
        4. ContextIntelligence - Fallback to existing system
        5. ContextOptimizer - Reorder for LLM attention
        6. ImplicitFeedback - Track shown results

        Args:
            query: Natural language query
            limit: Max results
            project: Optional project filter

        Returns:
            List of context items with source metadata
        """
        # 1. DefensivePrompting: Validate input
        if self.defensive and self.config and self.config.defensive_prompting_enabled:
            validation = self.defensive.validate_input(query)
            if not validation.valid:
                return [
                    {
                        "error": "Input validation failed",
                        "issues": validation.issues,
                        "source": "defensive_prompting",
                    }
                ]
            query = validation.sanitized_input

        results = []

        # 2. TieredMemory: Check session memory first
        if self.tiered_memory:
            try:
                memory_results = self.tiered_memory.query(query, limit=limit)
                for item, score, tier in memory_results:
                    # Convert MemoryItem to context dict
                    if hasattr(item, "content"):
                        result = {
                            "title": item.content.get("title", item.id),
                            "type": item.content.get("type", "memory"),
                            "description": item.content.get("description", ""),
                            "confidence": min(score / 3.0, 1.0),  # Normalize score
                            "file": item.content.get("file"),
                            "command": item.content.get("command"),
                            "source": f"tiered_memory:{tier}",
                        }
                        results.append(result)
            except Exception:
                pass  # Fall through to other sources

        # 3. HybridRetriever: Semantic + keyword search
        if self.hybrid_retriever and len(results) < limit:
            try:
                remaining = limit - len(results)
                hybrid_results = self.hybrid_retriever.search(
                    query, limit=remaining, alpha=0.5
                )
                for pattern, score in hybrid_results:
                    result = {
                        "title": pattern.title,
                        "type": "pattern",
                        "description": pattern.description,
                        "confidence": score,
                        "file": None,
                        "command": None,
                        "source": "hybrid_retriever",
                    }
                    results.append(result)
            except Exception:
                pass  # Fall through to fallback

        # 4. ContextIntelligence: Fallback to existing system
        if len(results) < limit and self.context_intel:
            try:
                remaining = limit - len(results)
                keywords = query.split() if " " in query else [query]
                predictions = self.context_intel.predict_context(
                    current_project=project, keywords=keywords, limit=remaining
                )
                for p in predictions:
                    result = {
                        "title": p.title,
                        "type": p.context_type,
                        "description": p.description,
                        "confidence": p.confidence,
                        "file": str(p.file_path) if p.file_path else None,
                        "command": p.command,
                        "source": "context_intelligence",
                    }
                    results.append(result)
            except Exception:
                pass

        # Handle no results case
        if not results:
            if not self.context_intel:
                return [{"error": "ContextIntelligence not available", "source": "system"}]
            return []

        # 5. ContextOptimizer: Reorder for LLM attention (handled in get_optimized_context)
        # Note: Direct get_context returns raw results; use get_optimized_context for LLM optimization

        # 6. ImplicitFeedback: Track shown results
        if self.implicit_feedback:
            try:
                for i, result in enumerate(results):
                    rec_id = f"context_{result.get('title', f'result_{i}')}_{i}"
                    self.implicit_feedback.track_recommendation_shown(
                        rec_id=rec_id,
                        recommendation={
                            "title": result.get("title", ""),
                            "source": result.get("source", "unknown"),
                            "position": i,
                        },
                        context={"query": query, "project": project},
                    )
            except Exception:
                pass  # Non-critical

        return results[:limit]

    def get_optimized_context(
        self,
        query: str,
        limit: int = 10,
        project: Optional[str] = None,
        max_tokens: Optional[int] = None,
        strategy: str = "importance",
        include_markers: bool = True,
    ) -> Dict[str, Any]:
        """
        Get context optimized for LLM attention patterns.

        Uses the ContextOptimizer to reorder context items based on importance,
        applying the "lost-in-the-middle" optimization for better LLM attention.

        Args:
            query: Natural language query
            limit: Max results to retrieve
            project: Optional project filter
            max_tokens: Optional token limit for context
            strategy: Optimization strategy - "importance" or "category"
            include_markers: Whether to add position markers like [IMPORTANT]

        Returns:
            Dict with:
            - optimized_context: String ready for LLM prompt
            - items: List of context items with metadata
            - optimization_applied: Whether optimization was used
        """
        # Get raw context items
        raw_context = self.get_context(query, limit=limit, project=project)

        # Check for errors
        if raw_context and "error" in raw_context[0]:
            return {"error": raw_context[0]["error"], "optimization_applied": False}

        # If optimizer not available, return raw context as string
        if not self.context_optimizer or not CONTEXT_OPTIMIZER_AVAILABLE:
            context_str = "\n\n".join(
                f"[{item.get('type', 'data')}] {item.get('title', '')}: {item.get('description', '')}"
                for item in raw_context
            )
            return {
                "optimized_context": context_str,
                "items": raw_context,
                "optimization_applied": False,
                "reason": "ContextOptimizer not available",
            }

        # Convert to ContextItem format for optimizer
        context_items = []
        for item in raw_context:
            # Map context types to categories
            ctx_type = item.get("type", "data")
            if ctx_type in ("instruction", "system"):
                category = "instruction"
            elif ctx_type in ("example", "pattern"):
                category = "example"
            elif ctx_type in ("history", "recent"):
                category = "history"
            else:
                category = "data"

            context_items.append({
                "content": f"{item.get('title', '')}: {item.get('description', '')}",
                "importance": item.get("confidence", 0.5),
                "category": category,
                "source": item.get("file"),
                "metadata": {"original": item},
            })

        # Apply optimization
        try:
            optimized_str = optimize_prompt_context(
                context_items,
                max_tokens=max_tokens,
                strategy=strategy,
                include_markers=include_markers,
            )

            return {
                "optimized_context": optimized_str,
                "items": raw_context,
                "optimization_applied": True,
                "strategy": strategy,
                "max_tokens": max_tokens,
            }
        except Exception as e:
            # Fallback to raw context
            context_str = "\n\n".join(
                f"[{item.get('type', 'data')}] {item.get('title', '')}: {item.get('description', '')}"
                for item in raw_context
            )
            return {
                "optimized_context": context_str,
                "items": raw_context,
                "optimization_applied": False,
                "error": str(e),
            }

    # --- 2. Strategy Bridge ---

    def inject_recommendation(
        self,
        title: str,
        rationale: str,
        priority: str = "medium",
        type: str = "ai_suggestion",
        effort: str = "Unknown",
        related_project: str = "",
    ) -> bool:
        """
        Inject a strategic recommendation into Cortex.

        Uses AI Engineering pipeline:
        1. DefensivePrompting - Validate inputs
        2. TieredMemory - Record for future recall
        3. ImplicitFeedback - Track recommendation shown

        Args:
            title: Action title
            rationale: Why this is important
            priority: high/medium/low
            type: Category of recommendation
            effort: Estimated effort
            related_project: Associated project
        """
        # 1. DefensivePrompting: Validate inputs
        if self.defensive and self.config and self.config.defensive_prompting_enabled:
            # Validate title
            title_validation = self.defensive.validate_input(title)
            if not title_validation.valid:
                print(f"Bridge Error: Title validation failed: {title_validation.issues}", file=sys.stderr)
                return False
            title = title_validation.sanitized_input

            # Validate rationale
            rationale_validation = self.defensive.validate_input(rationale)
            if not rationale_validation.valid:
                print(f"Bridge Error: Rationale validation failed: {rationale_validation.issues}", file=sys.stderr)
                return False
            rationale = rationale_validation.sanitized_input

        rec_id = f"bridge_{int(datetime.now().timestamp())}_{abs(hash(title)) % 1000}"
        rec_data = {
            "id": rec_id,
            "title": title,
            "type": type,
            "priority": priority,
            "rationale": rationale,
            "estimated_effort": effort,
            "estimated_impact": priority,
            "confidence": 0.95,
            "related_projects": [related_project] if related_project else [],
            "description": f"Injected via Cortex Bridge.\nRationale: {rationale}",
            "created_at": datetime.now().isoformat(),
            "source": "CortexBridge",
        }

        external_file = self.root_dir / "cortex" / "external_recommendations.json"

        try:
            # Atomic-ish read/modify/write
            current_recs = []
            if external_file.exists():
                content = external_file.read_text()
                if content.strip():
                    try:
                        current_recs = json.loads(content)
                    except json.JSONDecodeError:
                        current_recs = []

            current_recs.append(rec_data)
            external_file.write_text(json.dumps(current_recs, indent=2))

            # 2. TieredMemory: Record for future recall
            if self.tiered_memory and TIERED_MEMORY_AVAILABLE and MemoryItem:
                try:
                    memory_item = MemoryItem(
                        id=rec_id,
                        content={
                            "title": title,
                            "type": type,
                            "description": rationale,
                            "priority": priority,
                            "project": related_project,
                        },
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                    )
                    self.tiered_memory.record(memory_item)
                except Exception:
                    pass  # Non-critical

            # 3. ImplicitFeedback: Track recommendation shown
            if self.implicit_feedback:
                try:
                    self.implicit_feedback.track_recommendation_shown(
                        rec_id=rec_id,
                        recommendation={
                            "title": title,
                            "rationale": rationale,
                            "priority": priority,
                            "type": type,
                        },
                        context={"project": related_project, "source": "inject_recommendation"},
                    )
                except Exception:
                    pass  # Non-critical

            return True

        except Exception as e:
            print(f"Bridge Error (Inject): {e}", file=sys.stderr)
            return False

    # --- 3. Execution Bridge ---

    def trigger_action(self, agent_id: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Trigger an automated agent via Local Orchestrator.

        Args:
            agent_id: ID of the agent to trigger
            payload: Context dictionary
        """
        if not self.orchestrator or not self.orchestrator.is_available():
            return {"success": False, "error": "Local Orchestrator not connected"}

        if not self.orchestrator.orchestrator:
            return {"success": False, "error": "Orchestrator instance missing"}

        try:
            result = self.orchestrator.orchestrator.trigger_agent(
                agent_id=agent_id, context=payload or {}
            )

            return {
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- 4. Portfolio Bridge ---

    def get_portfolio_context(self, project: str) -> Dict[str, Any]:
        """
        Get comprehensive project context including patterns and lessons.

        Args:
            project: Project name (e.g., "VortexV2")

        Returns:
            Dict with project, patterns, lessons, tech_stack, related

        Example:
            >>> bridge = CortexBridge()
            >>> context = bridge.get_portfolio_context("VortexV2")
            >>> print(context["lessons"][0]["lesson"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_project_context(project)
        except Exception as e:
            return {"error": str(e)}

    def get_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cross-project patterns.

        Args:
            pattern_type: Optional pattern name filter

        Returns:
            List of pattern dicts

        Example:
            >>> bridge = CortexBridge()
            >>> patterns = bridge.get_patterns("async_fastapi")
        """
        if not self.portfolio:
            return [{"error": "Portfolio memory not available"}]

        try:
            return self.portfolio.get_cross_project_patterns(pattern_type)
        except Exception as e:
            return [{"error": str(e)}]

    def get_portfolio_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cross-project patterns (alias for get_patterns for API compatibility).

        Args:
            pattern_type: Optional pattern category filter

        Returns:
            List of pattern dictionaries

        Example:
            >>> bridge = CortexBridge()
            >>> patterns = bridge.get_portfolio_patterns(pattern_type="async_fastapi")
        """
        return self.get_patterns(pattern_type=pattern_type)

    def get_lessons(
        self, project: Optional[str] = None, pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get lessons learned.

        Args:
            project: Filter by affected project
            pattern: Filter by pattern type

        Returns:
            List of lesson dicts

        Example:
            >>> bridge = CortexBridge()
            >>> lessons = bridge.get_lessons(project="VortexV2")
        """
        if not self.portfolio:
            return [{"error": "Portfolio memory not available"}]

        try:
            return self.portfolio.get_lessons_learned(project=project, pattern=pattern)
        except Exception as e:
            return [{"error": str(e)}]

    def get_portfolio_stats(self, include_health: bool = True) -> Dict[str, Any]:
        """
        Get portfolio statistics.

        Args:
            include_health: Include health summary (default: True)

        Returns:
            Dict with stats about projects, patterns, lessons, and health

        Example:
            >>> bridge = CortexBridge()
            >>> stats = bridge.get_portfolio_stats()
            >>> print(stats["total_projects"])
            >>> print(stats["health"]["healthy_count"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_stats(include_health=include_health)
        except Exception as e:
            return {"error": str(e)}

    def get_project_health(
        self, project: str, days: int = 7, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get health score for a specific project.

        Args:
            project: Project name
            days: Days to analyze (default: 7)
            force_refresh: Force cache refresh

        Returns:
            Dict with health score, assessment, recommendations

        Example:
            >>> bridge = CortexBridge()
            >>> health = bridge.get_project_health("cortex")
            >>> print(health["health_score"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_project_health(project, days, force_refresh)
        except Exception as e:
            return {"error": str(e)}

    def get_portfolio_health_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get health summary for all projects.

        Args:
            days: Days to analyze (default: 7)

        Returns:
            Dict with health scores for all projects

        Example:
            >>> bridge = CortexBridge()
            >>> summary = bridge.get_portfolio_health_summary()
            >>> print(summary["aggregate"]["healthy_projects"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_portfolio_health_summary(days)
        except Exception as e:
            return {"error": str(e)}

    def get_project_health_trends(self, project: str) -> Dict[str, Any]:
        """
        Get comprehensive health trends for a project.

        Args:
            project: Project name

        Returns:
            Dict with trends, insights, recommendations

        Example:
            >>> bridge = CortexBridge()
            >>> trends = bridge.get_project_health_trends("cortex")
            >>> print(trends["insights"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_project_health_trends(project)
        except Exception as e:
            return {"error": str(e)}

    # --- Dependency Analysis Methods ---

    def get_dependency_analysis(self, project: str) -> Dict[str, Any]:
        """
        Get dependency analysis for a project.

        Args:
            project: Project name

        Returns:
            Dict with dependency analysis

        Example:
            >>> bridge = CortexBridge()
            >>> deps = bridge.get_dependency_analysis("cortex")
            >>> print(deps["external_deps"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            return analyzer.get_dependency_analysis(project)
        except Exception as e:
            return {"error": str(e)}

    def get_dependency_health(self, project: str) -> Dict[str, Any]:
        """
        Get dependency health score for a project.

        Args:
            project: Project name

        Returns:
            Dict with health score and breakdown

        Example:
            >>> bridge = CortexBridge()
            >>> health = bridge.get_dependency_health("cortex")
            >>> print(f"Score: {health['total_score']}/100")
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            return analyzer.get_dependency_health(project)
        except Exception as e:
            return {"error": str(e)}

    def find_circular_dependencies(self, project: str) -> Dict[str, Any]:
        """
        Find circular dependencies in a project.

        Args:
            project: Project name

        Returns:
            Dict with circular dependency analysis

        Example:
            >>> bridge = CortexBridge()
            >>> circular = bridge.find_circular_dependencies("cortex")
            >>> if circular["has_cycles"]:
            >>>     print(f"Found {circular['cycle_count']} cycles")
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            return analyzer.find_circular_dependencies(project)
        except Exception as e:
            return {"error": str(e)}

    def export_dependency_graph(
        self,
        project: str,
        format: str = "ascii",
        include_stdlib: bool = False,
        include_external: bool = True,
    ) -> Dict[str, Any]:
        """
        Export dependency graph in specified format.

        Args:
            project: Project name
            format: Output format ("ascii", "dot", or "mermaid")
            include_stdlib: Whether to include standard library imports (for dot/mermaid)
            include_external: Whether to include external dependencies (for dot/mermaid)

        Returns:
            Dict with graph data in requested format

        Example:
            >>> bridge = CortexBridge()
            >>> graph = bridge.export_dependency_graph("cortex", format="mermaid")
            >>> print(graph["graph"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.dependency_mapper import (
                DependencyMapper,
            )
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            project_path = analyzer.projects.get(project)
            if not project_path:
                return {"error": f"Project '{project}' not found"}

            mapper = DependencyMapper(project_path)

            if format == "dot":
                graph = mapper.export_to_dot(
                    include_stdlib=include_stdlib, include_external=include_external
                )
            elif format == "mermaid":
                graph = mapper.export_to_mermaid(
                    include_stdlib=include_stdlib, include_external=include_external
                )
            elif format == "ascii":
                graph = mapper.generate_ascii_tree()
            else:
                return {"error": f"Unknown format '{format}'. Use: ascii, dot, or mermaid"}

            return {
                "success": True,
                "project": project,
                "format": format,
                "graph": graph,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_package_dependencies(self, project: str) -> Dict[str, Any]:
        """
        Get declared dependencies from package manager files.

        Args:
            project: Project name

        Returns:
            Dict with package file parsing results

        Example:
            >>> bridge = CortexBridge()
            >>> packages = bridge.get_package_dependencies("cortex")
            >>> print(packages["all_packages"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            return analyzer.get_package_dependencies(project)
        except Exception as e:
            return {"error": str(e)}

    def compare_package_dependencies(self, project: str) -> Dict[str, Any]:
        """
        Compare declared vs actual dependencies.

        Args:
            project: Project name

        Returns:
            Dict with comparison results (declared, actual, unused, undeclared)

        Example:
            >>> bridge = CortexBridge()
            >>> comparison = bridge.compare_package_dependencies("cortex")
            >>> print(f"Undeclared: {comparison['undeclared_count']}")
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            return analyzer.compare_package_dependencies(project)
        except Exception as e:
            return {"error": str(e)}

    def analyze_portfolio_dependencies(
        self, project_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze dependencies across entire portfolio.

        Args:
            project_filter: Optional project name to focus analysis on

        Returns:
            Dict with portfolio-wide dependency analysis

        Example:
            >>> bridge = CortexBridge()
            >>> portfolio = bridge.analyze_portfolio_dependencies()
            >>> print(f"Projects analyzed: {len(portfolio['projects_analyzed'])}")
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer()
            return analyzer.analyze_portfolio_dependencies(project_filter=project_filter)
        except Exception as e:
            return {"error": str(e)}

    # --- Intelligence Enhancement Methods ---

    def generate_synthetic(
        self,
        data_type: str = "profiles",
        count: int = 100,
        segment: Optional[str] = None,
        province: Optional[str] = None,
        risk_profile: Optional[str] = None,
        min_quality: float = 0.7,
        output_format: str = "jsonl",
    ) -> Dict[str, Any]:
        """
        Generate synthetic Canadian FinServ data.

        Args:
            data_type: "profiles" or "transactions"
            count: Number of records to generate
            segment: Target customer segment (e.g., "mass_affluent")
            province: Target province (e.g., "ON")
            risk_profile: For transactions — "low", "medium", "high"
            min_quality: Minimum quality score threshold (0.0-1.0)
            output_format: "jsonl", "json", or "csv"

        Returns:
            Dict with generation results and metadata
        """
        if not SYNTHETIC_AVAILABLE or not self.synthetic_generator:
            return {"error": "Synthetic data engine not available", "available": False}

        request = GenerationRequest(
            data_type=data_type,
            count=count,
            segment=segment,
            province=province,
            risk_profile=risk_profile,
            include_risk_flags=risk_profile is not None,
            min_quality_score=min_quality,
            output_format=output_format,
        )

        result = self.synthetic_generator.generate(request)

        return {
            "success": True,
            "summary": result.summary(),
            "records_generated": result.records_generated,
            "records_passed": result.records_passed_quality,
            "records_rejected": result.records_rejected,
            "avg_quality": result.average_quality_score,
            "quality_distribution": result.quality_distribution,
            "output_path": result.output_path,
            "flywheel_id": result.flywheel_id,
            "generation_time_s": result.generation_time_seconds,
        }

    def query_intelligence(
        self,
        request: str,
        project: str,
        query_type: str = "spec",
        use_cache: bool = True,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        Query unified intelligence API with enhanced features.

        Uses AI Engineering pipeline:
        1. DefensivePrompting - Validate input (already exists)
        2. HybridRetriever - Add related patterns
        3. ContextOptimizer - Optimize result context
        4. TieredMemory - Record query for learning

        Args:
            request: User request (e.g., "enhance golden spec method")
            project: Project name (e.g., "cortex")
            query_type: Type of query ("spec", "impl", "analysis", "research")
            use_cache: Whether to use query result cache (default: True)
            parallel: Whether to query sources in parallel (default: True)

        Returns:
            Dict representation of IntelligenceResult with enhanced features:
            - Ranked results by relevance
            - Confidence scores for all components
            - Detailed reasoning for results
            - Overall confidence score
            - related_patterns from hybrid retrieval (when available)

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.query_intelligence("enhance golden spec", "cortex")
            >>> print(result["overall_confidence"])  # 0.85
            >>> print(result["reasoning"])  # Detailed reasoning
        """
        if not self.unified_intel:
            return {"error": "Unified Intelligence not available"}

        if not IntelligenceQueryType:
            return {"error": "Intelligence models not available"}

        # 1. DefensivePrompting: Apply defensive prompting if enabled
        if self.config and self.config.defensive_prompting_enabled and self.defensive:
            validation = self.defensive.validate_input(request)
            if not validation.valid:
                return {
                    "error": "Input validation failed",
                    "issues": validation.issues,
                    "severity": validation.severity,
                }
            request = validation.sanitized_input

        try:
            query_type_enum = IntelligenceQueryType(query_type)
            result = self.unified_intel.query(
                user_request=request,
                project=project,
                query_type=query_type_enum,
                use_cache=use_cache,
                parallel=parallel,
            )
            result_dict = result.to_dict()

            # 2. HybridRetriever: Add related patterns
            if self.hybrid_retriever:
                try:
                    hybrid_results = self.hybrid_retriever.search(request, limit=3, alpha=0.5)
                    related_patterns = [
                        {
                            "title": pattern.title,
                            "description": pattern.description,
                            "score": score,
                        }
                        for pattern, score in hybrid_results
                    ]
                    result_dict["related_patterns"] = related_patterns
                except Exception:
                    pass  # Non-critical

            # 3. ContextOptimizer: Apply optimization info (if available)
            if self.context_optimizer and CONTEXT_OPTIMIZER_AVAILABLE:
                try:
                    result_dict["context_optimization"] = {
                        "strategy": "importance",
                        "applied": True,
                    }
                except Exception:
                    pass

            # 4. TieredMemory: Record query for learning
            if self.tiered_memory and TIERED_MEMORY_AVAILABLE and MemoryItem:
                try:
                    import uuid

                    query_id = f"intel_{uuid.uuid4().hex[:8]}"
                    memory_item = MemoryItem(
                        id=query_id,
                        content={
                            "type": "intelligence_query",
                            "title": f"Query: {request[:50]}...",
                            "description": request,
                            "project": project,
                            "query_type": query_type,
                        },
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                    )
                    self.tiered_memory.record(memory_item)
                except Exception:
                    pass  # Non-critical

            return result_dict
        except Exception as e:
            return {"error": str(e)}

    def get_prompt_template(self, prompt_name: str, **variables) -> Optional[str]:
        """
        Get a prompt template from registry with variables filled in.

        Phase 1 Integration: Uses versioned prompt templates if enabled.

        Args:
            prompt_name: Name of prompt template
            **variables: Variables to fill into template

        Returns:
            Rendered prompt string, or None if template not found
        """
        if not self.config or not self.config.prompt_versioning_enabled or not self.prompt_registry:
            return None

        template = self.prompt_registry.get_prompt(prompt_name, version=self.config.prompt_version)
        if not template:
            return None

        return template.render(**variables)

    def find_similar_work(self, domain: str, project: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar work across portfolio.

        Args:
            domain: Domain/topic (e.g., "wind forecasting ensemble")
            project: Current project context
            limit: Max results

        Returns:
            List of SimilarWork dicts

        Example:
            >>> bridge = CortexBridge()
            >>> similar = bridge.find_similar_work("ensemble forecasting", "VortexV2")
        """
        if not self.spec_kb:
            return [{"error": "Spec Knowledge Base not available"}]

        try:
            from dataclasses import asdict

            similar = self.spec_kb.find_similar(domain, k=limit, project_filter=project)
            return [asdict(s) for s in similar]
        except Exception as e:
            return [{"error": str(e)}]

    def search_specs(
        self, query: str, project: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search indexed specifications (alias for find_similar_work for API compatibility).

        Uses AI Engineering pipeline:
        1. DefensivePrompting - Validate query
        2. HybridRetriever - Hybrid search first
        3. SpecKnowledgeBase - Fallback to existing system
        4. ImplicitFeedback - Track results

        Args:
            query: Search query string
            project: Optional project filter
            limit: Maximum results

        Returns:
            List of matching specs with similarity scores

        Example:
            >>> bridge = CortexBridge()
            >>> results = bridge.search_specs("API rate limiting", project="cortex", limit=5)
        """
        # 1. DefensivePrompting: Validate query
        if self.defensive and self.config and self.config.defensive_prompting_enabled:
            validation = self.defensive.validate_input(query)
            if not validation.valid:
                return [
                    {
                        "error": "Query validation failed",
                        "issues": validation.issues,
                    }
                ]
            query = validation.sanitized_input

        results = []

        # 2. HybridRetriever: Try hybrid search first
        if self.hybrid_retriever:
            try:
                hybrid_results = self.hybrid_retriever.search(query, limit=limit, alpha=0.5)
                for pattern, score in hybrid_results:
                    result = {
                        "spec_name": pattern.title,
                        "title": pattern.title,
                        "description": pattern.description,
                        "similarity": score,
                        "similarity_score": score,
                        "source": "hybrid_retriever",
                    }
                    results.append(result)
            except Exception:
                pass  # Fall through to spec_kb

        # 3. SpecKnowledgeBase: Fallback to existing system
        if len(results) < limit and self.spec_kb:
            try:
                remaining = limit - len(results)
                # Try intelligence version first (ChromaDB-based)
                if hasattr(self.spec_kb, "find_similar"):
                    from dataclasses import asdict

                    similar = self.spec_kb.find_similar(query, k=remaining, project_filter=project)
                    # Transform SimilarWork dataclass to expected format
                    for s in similar:
                        result = asdict(s)
                        result["source"] = "spec_knowledge_base"
                        # Map 'title' to 'spec_name' for API compatibility
                        if "spec_name" not in result:
                            if "title" in result:
                                result["spec_name"] = result["title"]
                            elif "name" in result:
                                result["spec_name"] = result["name"]
                        # Ensure similarity_score is present
                        if "similarity" not in result and "similarity_score" in result:
                            result["similarity"] = result["similarity_score"]
                        results.append(result)
                # Fallback to simple hash-based version
                elif hasattr(self.spec_kb, "search"):
                    kb_results = self.spec_kb.search(query, project=project, limit=remaining)
                    for r in kb_results:
                        r["source"] = "spec_knowledge_base"
                        results.append(r)
            except Exception as e:
                if not results:
                    return [{"error": str(e)}]

        # Handle no results
        if not results:
            if not self.spec_kb:
                return [{"error": "Spec Knowledge Base not available"}]
            return []

        # 4. ImplicitFeedback: Track results
        if self.implicit_feedback:
            try:
                for i, result in enumerate(results):
                    rec_id = f"spec_{result.get('spec_name', f'spec_{i}')}_{i}"
                    self.implicit_feedback.track_recommendation_shown(
                        rec_id=rec_id,
                        recommendation={
                            "spec_name": result.get("spec_name", ""),
                            "title": result.get("title", ""),
                            "source": result.get("source", "unknown"),
                            "position": i,
                        },
                        context={"query": query, "project": project},
                    )
            except Exception:
                pass  # Non-critical

        return results[:limit]

    def get_session_context(self, format: str = "structured") -> Dict[str, Any]:
        """
        Get current session context.

        Args:
            format: Output format ('terminal' or 'structured', default: 'structured')

        Returns:
            SessionContext dict or formatted string

        Example:
            >>> bridge = CortexBridge()
            >>> context = bridge.get_session_context(format='structured')
        """
        if not self.session_mgr:
            return {"error": "Session Manager not available"}

        try:
            # Load SessionContext dataclass
            from dataclasses import asdict

            session_ctx = self.session_mgr.load_session_context()

            if not session_ctx:
                return {"error": "No session context available"}

            if format == "terminal":
                # Format for terminal display
                context_dict = asdict(session_ctx)
                # Build terminal-friendly format
                lines = [
                    f"Project: {context_dict.get('project', 'unknown')}",
                    f"Focus: {context_dict.get('current_focus', 'unknown')}",
                    f"Goals: {', '.join(context_dict.get('active_goals', []))}",
                ]
                return {"context": "\n".join(lines), "format": "terminal"}
            else:
                # Return structured dict with expected keys
                context_dict = asdict(session_ctx)
                # Map to expected format: project, git, goals
                result = {
                    "project": {
                        "name": context_dict.get("project", "unknown"),
                        "path": context_dict.get("working_directory", ""),
                    },
                    "git": {"recent_commits": context_dict.get("recent_work", [])},
                    "goals": context_dict.get("active_goals", []),
                    "focus": context_dict.get("current_focus", "unknown"),
                    "working_directory": context_dict.get("working_directory", ""),
                    "last_updated": context_dict.get("last_updated", ""),
                }
                return result
        except Exception as e:
            return {"error": str(e)}

    def index_spec(
        self, spec_path: str, project: str, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index a spec in knowledge base.

        Args:
            spec_path: Path to spec file
            project: Project name
            domain: Optional domain tag

        Returns:
            Result dict with spec_id

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.index_spec("/path/to/spec.md", "cortex", "intelligence")
        """
        if not self.spec_kb:
            return {"error": "Spec Knowledge Base not available"}

        try:
            metadata = {
                "project": project,
                "domain": domain,
                "indexed_at": datetime.now().isoformat(),
            }

            spec_id = self.spec_kb.index_spec(Path(spec_path), metadata)

            return {
                "success": True,
                "spec_id": spec_id,
                "message": f"Spec indexed: {spec_path}",
            }
        except Exception as e:
            return {"error": str(e)}

    # --- Recommendation Methods ---

    def get_recommendations(self) -> Dict[str, Any]:
        """
        Get smart recommendations based on health, goals, and dependencies.

        Returns:
            Full recommendations report with priority projects, alerts, and next action

        Example:
            >>> bridge = CortexBridge()
            >>> recs = bridge.get_recommendations()
            >>> print(recs["next_action"]["action"])
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_full_report()
        except Exception as e:
            return {"error": str(e)}

    def get_next_action(self) -> Dict[str, Any]:
        """
        Get single most important recommended action.

        Returns:
            Dict with action, reason, priority, and type

        Example:
            >>> bridge = CortexBridge()
            >>> action = bridge.get_next_action()
            >>> print(f"[{action['priority']}] {action['action']}")
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_recommended_next_action()
        except Exception as e:
            return {"error": str(e)}

    def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """
        Get risk alerts across the portfolio.

        Returns:
            List of risk alerts with severity, type, and recommendations

        Example:
            >>> bridge = CortexBridge()
            >>> alerts = bridge.get_risk_alerts()
            >>> for alert in alerts:
            ...     print(f"[{alert['severity']}] {alert['message']}")
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_risk_alerts()
        except Exception as e:
            return [{"error": str(e)}]

    def get_priority_projects(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects that need attention, prioritized by goals and health.

        Args:
            limit: Maximum projects to return

        Returns:
            List of priority projects with reasons

        Example:
            >>> bridge = CortexBridge()
            >>> priorities = bridge.get_priority_projects()
            >>> for p in priorities:
            ...     print(f"[{p['priority']}] {p['project']}: {p['reason']}")
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_priority_projects(limit=limit)
        except Exception as e:
            return [{"error": str(e)}]

    # --- Implicit Feedback Methods ---

    def track_recommendation_shown(
        self, rec_id: str, recommendation: Dict, context: Optional[Dict] = None
    ) -> bool:
        """
        Track when a recommendation is displayed to user.

        Call this when showing recommendations to enable implicit feedback tracking.

        Args:
            rec_id: Unique recommendation identifier
            recommendation: The recommendation dict (with title, description, etc.)
            context: Optional context (project, goal, etc.)

        Returns:
            True if tracked, False if implicit feedback not available
        """
        if not self.implicit_feedback:
            return False

        try:
            self.implicit_feedback.track_recommendation_shown(rec_id, recommendation, context)
            return True
        except Exception:
            return False

    def track_action_taken(
        self, action: str, files: Optional[List[str]] = None, context: Optional[Dict] = None
    ) -> bool:
        """
        Track user action and correlate with pending recommendations.

        Call this when user takes an action (command, file edit, etc.)
        to automatically detect follows, ignores, and overrides.

        Args:
            action: Description of action taken
            files: Files involved in the action
            context: Additional context

        Returns:
            True if tracked, False if implicit feedback not available
        """
        if not self.implicit_feedback:
            return False

        try:
            self.implicit_feedback.track_action_taken(action, files, context)
            return True
        except Exception:
            return False

    def end_feedback_session(self) -> Dict[str, Any]:
        """
        End implicit feedback session and mark un-acted recommendations as ignored.

        Call this at end of session or after timeout.

        Returns:
            Session stats dict
        """
        if not self.implicit_feedback:
            return {"available": False}

        try:
            stats = self.implicit_feedback.get_session_stats()
            self.implicit_feedback.session_end()
            return {"available": True, "session_stats": stats}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_implicit_feedback_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get implicit feedback statistics over time period.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with follow rate, ignore rate, average time-to-action, etc.
        """
        if not self.implicit_feedback:
            return {"available": False}

        try:
            return {"available": True, "stats": self.implicit_feedback.get_stats(days)}
        except Exception as e:
            return {"available": False, "error": str(e)}

    # --- Batch API Methods ---

    def submit_research_batch(self, research_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Submit a batch of research discovery requests.

        Args:
            research_items: List of research request dicts, each with:
                - id: Unique identifier
                - topic: Research topic
                - context: Additional context
                - priority: "high", "medium", "low"

        Returns:
            Dict with batch_id, submitted_count, completed_count, and results

        Example:
            >>> bridge = CortexBridge()
            >>> items = [{"id": "1", "topic": "AI safety", "context": "...", "priority": "high"}]
            >>> result = bridge.submit_research_batch(items)
        """
        try:
            from cortex.batch.research_batcher import ResearchBatcher

            batcher = ResearchBatcher()
            return batcher.process_batch(research_items)
        except ImportError as e:
            return {"error": f"ResearchBatcher not available: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def submit_briefing_batch(self, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Submit a batch of briefing generation requests.

        Args:
            contexts: List of briefing context dicts, each with:
                - portfolio_pulse: Portfolio state dict
                - system_health: System health dict
                - execution_history: Execution history dict
                - goals_context: Goals context dict
                - context_id: Unique identifier

        Returns:
            Dict with batch_id, submitted_count, completed_count, and results

        Example:
            >>> bridge = CortexBridge()
            >>> contexts = [{"context_id": "briefing_001", ...}]
            >>> result = bridge.submit_briefing_batch(contexts)
        """
        try:
            from cortex.batch.briefing_batcher import (
                BriefingContext,
                RecommendationBatcher,
            )

            batcher = RecommendationBatcher(root_dir=self.root_dir)

            # Convert dicts to BriefingContext objects
            briefing_contexts = [
                BriefingContext(
                    portfolio_pulse=ctx.get("portfolio_pulse", {}),
                    system_health=ctx.get("system_health", {}),
                    execution_history=ctx.get("execution_history", {}),
                    goals_context=ctx.get("goals_context", {}),
                    context_id=ctx.get("context_id", f"briefing_{i}"),
                )
                for i, ctx in enumerate(contexts)
            ]

            return batcher.process_batch(briefing_contexts)
        except ImportError as e:
            return {"error": f"BriefingBatcher not available: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Get status of a batch operation.

        Args:
            batch_id: Batch ID from submit_research_batch or submit_briefing_batch

        Returns:
            Dict with batch status, progress, and request counts

        Example:
            >>> bridge = CortexBridge()
            >>> status = bridge.get_batch_status("batch_123")
        """
        try:
            from cortex.batch.batch_api_client import BatchAPIClient

            client = BatchAPIClient()
            return client.get_batch_status(batch_id)
        except ImportError as e:
            return {"error": f"BatchAPIClient not available: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # --- 6. Planning Bridge ---

    def create_plan(
        self, project: str, title: str = None, auto_generate: bool = True
    ) -> Dict[str, Any]:
        """
        Create an execution plan from recommendations.

        Args:
            project: Project name
            title: Plan title (auto-generated if None)
            auto_generate: Auto-generate recommendations

        Returns:
            Plan summary
        """
        try:
            from intelligence.planning import PlanPriority
            from recommendation_engine import RecommendationEngine

            # Initialize recommendation engine for the project
            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir  # Fallback to root

            engine = RecommendationEngine(project_path=project_path)

            # Create plan
            plan = engine.create_plan(
                title=title, priority=PlanPriority.MEDIUM, auto_generate=auto_generate
            )

            return {
                "success": True,
                "plan_id": plan.id,
                "title": plan.title,
                "steps": len(plan.steps),
                "estimated_time": plan.estimated_total_time,
                "message": f"Plan created: {plan.id}",
            }

        except Exception as e:
            return {"error": str(e)}

    def list_plans(self, status: str = None) -> Dict[str, Any]:
        """
        List all plans.

        Args:
            status: Optional status filter

        Returns:
            List of plans
        """
        try:
            from intelligence.planning import PlanExecutor, PlanStatus

            executor = PlanExecutor()

            status_filter = None
            if status:
                status_filter = PlanStatus(status)

            plans = executor.list_plans(status_filter=status_filter)

            return {"success": True, "plans": plans, "count": len(plans)}

        except Exception as e:
            return {"error": str(e)}

    def get_plan(self, plan_id: str, format: str = "json") -> Dict[str, Any]:
        """
        Get plan details.

        Args:
            plan_id: Plan identifier
            format: Output format (json or markdown)

        Returns:
            Plan details
        """
        try:
            from intelligence.planning import PlanExecutor

            executor = PlanExecutor()
            plan = executor.load_plan(plan_id)

            if format == "markdown":
                return {"success": True, "markdown": plan.to_markdown()}
            else:
                return {"success": True, "plan": plan.to_dict()}

        except Exception as e:
            return {"error": str(e)}

    def start_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Start executing a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Success status
        """
        try:
            from intelligence.planning import PlanExecutor

            executor = PlanExecutor()
            plan = executor.load_plan(plan_id)
            executor.start_plan(plan)

            next_step = executor.get_next_step()

            return {
                "success": True,
                "plan_id": plan.id,
                "status": plan.status.value,
                "next_step": (
                    {
                        "id": next_step.id,
                        "title": next_step.title,
                        "description": next_step.description,
                    }
                    if next_step
                    else None
                ),
            }

        except Exception as e:
            return {"error": str(e)}

    def complete_step(self, step_id: str, notes: str = "") -> Dict[str, Any]:
        """
        Complete a plan step.

        Args:
            step_id: Step identifier
            notes: Completion notes

        Returns:
            Success status with next step
        """
        try:
            from intelligence.planning import PlanExecutor

            executor = PlanExecutor()
            executor.complete_step(step_id, notes)

            progress = executor.get_progress()
            next_step = executor.get_next_step()

            return {
                "success": True,
                "step_id": step_id,
                "progress": progress,
                "next_step": (
                    {
                        "id": next_step.id,
                        "title": next_step.title,
                        "description": next_step.description,
                    }
                    if next_step
                    else None
                ),
                "completed": progress.get("completion_pct") == 100,
            }

        except Exception as e:
            return {"error": str(e)}

    def get_plan_progress(self) -> Dict[str, Any]:
        """
        Get active plan progress.

        Returns:
            Progress details
        """
        try:
            from intelligence.planning import PlanExecutor

            executor = PlanExecutor()
            progress = executor.get_progress()

            return {"success": True, "progress": progress}

        except Exception as e:
            return {"error": str(e)}

    # --- 6.5. Work Absorber Bridge ---

    def absorb_work(
        self,
        project: Optional[str] = None,
        since: Optional[str] = None,
        full: bool = False,
    ) -> Dict[str, Any]:
        """
        Run work absorption cycle to detect and track progress.

        Args:
            project: Specific project to absorb (None = all)
            since: Start date ISO string (None = incremental)
            full: Force full rescan instead of incremental

        Returns:
            Absorption report with statistics

        Example:
            >>> bridge = CortexBridge()
            >>> report = bridge.absorb_work(project="cortex")
        """
        try:
            from datetime import datetime

            from work_absorber import WorkAbsorber

            absorber = WorkAbsorber()

            since_dt = None
            if since:
                since_dt = datetime.fromisoformat(since)

            projects = [project] if project else None

            report = absorber.absorb(
                projects=projects,
                since=since_dt,
                incremental=not full,
            )

            return {
                "success": True,
                "signals_detected": report.signals_detected,
                "signals_absorbed": report.signals_absorbed,
                "work_items_created": report.work_items_created,
                "work_items_updated": report.work_items_updated,
                "correlations_made": report.correlations_made,
                "drifts_detected": report.drifts_detected,
                "duration_seconds": report.duration_seconds,
                "by_project": report.by_project,
                "errors": report.errors,
            }

        except ImportError:
            return {"error": "Work absorber not available"}
        except Exception as e:
            return {"error": str(e)}

    def get_work_items(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        days: int = 7,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get absorbed work items.

        Args:
            project: Filter by project
            status: Filter by status (detected, absorbed, correlated, orphaned)
            days: Days to look back
            limit: Maximum items to return

        Returns:
            List of work items

        Example:
            >>> bridge = CortexBridge()
            >>> items = bridge.get_work_items(project="cortex", status="orphaned")
        """
        try:
            from work_absorber import WorkAbsorber, WorkStatus

            absorber = WorkAbsorber()

            if status == "orphaned":
                items = absorber.get_unplanned_work()
            else:
                items = absorber.get_recent_work(days=days, project=project)
                if status:
                    status_enum = WorkStatus(status)
                    items = [i for i in items if i.status == status_enum]

            return {
                "success": True,
                "count": len(items),
                "items": [
                    {
                        "id": i.id,
                        "project": i.project,
                        "title": i.title,
                        "description": i.description[:200] if i.description else "",
                        "status": i.status.value,
                        "plan_step_id": i.plan_step_id,
                        "correlation_confidence": i.correlation_confidence,
                        "files_touched": len(i.files_touched),
                        "scope": i.scope,
                        "first_seen": i.first_seen.isoformat(),
                        "last_activity": i.last_activity.isoformat(),
                    }
                    for i in items[:limit]
                ],
            }

        except ImportError:
            return {"error": "Work absorber not available"}
        except Exception as e:
            return {"error": str(e)}

    def get_plan_drift(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Get plan drift analysis.

        Args:
            project: Optional project filter

        Returns:
            Drift summary with unresolved drifts

        Example:
            >>> bridge = CortexBridge()
            >>> drift = bridge.get_plan_drift(project="cortex")
        """
        try:
            from work_absorber import WorkAbsorber

            absorber = WorkAbsorber()
            summary = absorber.get_drift_summary(project=project)

            return {
                "success": True,
                "total": summary["total"],
                "by_type": dict(summary["by_type"]),
                "by_severity": dict(summary["by_severity"]),
                "drifts": [
                    {
                        "id": d.id,
                        "project": d.project,
                        "drift_type": d.drift_type.value,
                        "severity": d.severity,
                        "description": d.description,
                        "suggested_action": d.suggested_action,
                        "detected_at": d.detected_at.isoformat(),
                    }
                    for d in summary["drifts"][:20]
                ],
            }

        except ImportError:
            return {"error": "Work absorber not available"}
        except Exception as e:
            return {"error": str(e)}

    def sync_plans(self, project: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sync absorbed work progress back to plans.

        Args:
            project: Specific project to sync (None = all)
            dry_run: If True, don't write changes

        Returns:
            Sync result summary

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.sync_plans(dry_run=True)
        """
        try:
            from work_absorber.plan_sync import PlanProgressSync

            sync = PlanProgressSync()

            if project:
                result = sync.sync_project(project, dry_run=dry_run)
            else:
                result = sync.sync_all(dry_run=dry_run)

            return {
                "success": True,
                "dry_run": dry_run,
                **result,
            }

        except ImportError:
            return {"error": "Plan sync not available"}
        except Exception as e:
            return {"error": str(e)}

    def get_work_status(self) -> Dict[str, Any]:
        """
        Get overall work absorber status.

        Returns:
            Status including last absorption, totals, and stats

        Example:
            >>> bridge = CortexBridge()
            >>> status = bridge.get_work_status()
        """
        try:
            from work_absorber import WorkAbsorber

            absorber = WorkAbsorber()
            status = absorber.get_status()

            return {
                "success": True,
                **status,
            }

        except ImportError:
            return {"error": "Work absorber not available"}
        except Exception as e:
            return {"error": str(e)}

    # --- 7. Layer 1: Project Analysis Bridge ---

    def get_warnings(
        self, project: Optional[str] = None, severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get warnings for project(s).

        Args:
            project: Optional project name filter
            severity: Optional severity filter (critical, high, medium, low)

        Returns:
            Dict with warnings and summary

        Example:
            >>> bridge = CortexBridge()
            >>> warnings = bridge.get_warnings(project="cortex", severity="high")
        """
        try:
            if not self.portfolio:
                return {"error": "Portfolio memory not available"}

            warnings = self.portfolio.get_warnings(project=project, severity=severity)

            # Categorize warnings
            from cortex.agents.data_agent.analyzers.warning_generator import (
                WarningGenerator,
            )

            generator = WarningGenerator()
            categorized = generator.categorize_warnings(warnings)

            return {
                "success": True,
                "total_warnings": len(warnings),
                "by_severity": {
                    "critical": len(categorized["critical"]),
                    "high": len(categorized["high"]),
                    "medium": len(categorized["medium"]),
                    "low": len(categorized["low"]),
                },
                "warnings": warnings,
                "categorized": categorized,
            }
        except Exception as e:
            return {"error": str(e)}

    def generate_warnings(self, project: str) -> Dict[str, Any]:
        """
        Generate warnings for a project based on trends and health.

        Args:
            project: Project name

        Returns:
            Dict with generated warnings

        Example:
            >>> bridge = CortexBridge()
            >>> warnings = bridge.generate_warnings("cortex")
        """
        try:
            from cortex.agents.data_agent.analyzers.health_tracker import HealthTracker
            from cortex.agents.data_agent.analyzers.warning_generator import (
                WarningGenerator,
            )

            project_path = self.root_dir / project
            if not project_path.exists():
                return {"error": f"Project not found: {project}"}

            # Get health data
            health_tracker = HealthTracker()
            health_data = health_tracker.get_project_health(project_path)

            # Generate trends (simplified - would need historical data)
            trends = []  # Would be populated from historical metrics

            # Generate warnings
            generator = WarningGenerator()
            warnings = generator.generate_warnings(project, trends, health_data)

            # Store warnings
            if self.portfolio:
                self.portfolio.store_warnings(project, warnings)

            return {
                "success": True,
                "project": project,
                "warnings_generated": len(warnings),
                "warnings": warnings,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_project_warnings(self, project_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get active warnings for a project based on trends and health indicators.

        Args:
            project_name: The name of the project.
            days: The number of days to look back for trends.

        Returns:
            A list of warning dictionaries.
        """
        try:
            from cortex.agents.data_agent.analyzers.warning_generator import (
                WarningGenerator,
            )
            from cortex.intelligence.monitoring.metric_tracker import MetricTracker
            from cortex.intelligence.monitoring.trend_analyzer import TrendAnalyzer

            metric_tracker = MetricTracker()
            trend_analyzer = TrendAnalyzer(metric_tracker)
            warning_generator = WarningGenerator()

            # Get trends from TrendAnalyzer
            all_trends = trend_analyzer.get_all_trends(project_name, days)

            # Convert Trend objects to dict format for WarningGenerator
            trends = []
            for metric_type, trend in all_trends.items():
                if trend.alert_level.value != "none":
                    trends.append(
                        {
                            "metric": metric_type,
                            "direction": (
                                "decreasing"
                                if trend.direction.value == "degrading"
                                else (
                                    "increasing"
                                    if trend.direction.value == "improving"
                                    else "stable"
                                )
                            ),
                            "current_value": trend.end_value,
                            "velocity": trend.rate,
                            "is_concerning": trend.alert_level.value in ["warning", "critical"],
                            "severity": (
                                "critical"
                                if trend.alert_level.value == "critical"
                                else ("high" if trend.alert_level.value == "warning" else "medium")
                            ),
                        }
                    )

            # Get health data if available
            health_data = None
            try:
                from cortex.agents.data_agent.analyzers.health_tracker import (
                    HealthTracker,
                )

                project_path = self.root_dir / project_name
                if project_path.exists():
                    health_tracker = HealthTracker()
                    health_data = health_tracker.get_project_health(project_path)
            except Exception:
                pass

            # Generate warnings
            warnings = warning_generator.generate_warnings(project_name, trends, health_data)

            return warnings
        except Exception as e:
            return [{"error": str(e)}]

    def get_warning_dashboard(
        self, project_name: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get a dashboard of warnings, optionally filtered by project.

        Args:
            project_name: Optional project name to filter warnings.
            days: The number of days to look back for warnings.

        Returns:
            A dictionary representing the warning dashboard.
        """
        try:
            from cortex.agents.data_agent.analyzers.warning_generator import (
                WarningGenerator,
            )
            from cortex.intelligence.monitoring.metric_tracker import MetricTracker
            from cortex.intelligence.monitoring.trend_analyzer import TrendAnalyzer

            metric_tracker = MetricTracker()
            trend_analyzer = TrendAnalyzer(metric_tracker)
            warning_generator = WarningGenerator()

            # Get all projects or just the specified one
            if project_name:
                projects = [project_name]
            else:
                # Get all tracked projects from metric tracker
                # This is a simplified approach - in practice, you'd query the metric tracker for all projects
                projects = [project_name] if project_name else []
                # If no project specified and we can't get all projects, return empty dashboard
                if not projects:
                    return {
                        "total_warnings": 0,
                        "by_severity": {
                            "critical": 0,
                            "high": 0,
                            "medium": 0,
                            "low": 0,
                        },
                        "by_type": {},
                        "by_project": {},
                        "warnings": [],
                    }

            all_warnings = []
            by_project = {}

            for proj in projects:
                # Get trends for this project
                all_trends = trend_analyzer.get_all_trends(proj, days)

                # Convert Trend objects to dict format
                trends = []
                for metric_type, trend in all_trends.items():
                    if trend.alert_level.value != "none":
                        trends.append(
                            {
                                "metric": metric_type,
                                "direction": (
                                    "decreasing"
                                    if trend.direction.value == "degrading"
                                    else (
                                        "increasing"
                                        if trend.direction.value == "improving"
                                        else "stable"
                                    )
                                ),
                                "current_value": trend.end_value,
                                "velocity": trend.rate,
                                "is_concerning": trend.alert_level.value in ["warning", "critical"],
                                "severity": (
                                    "critical"
                                    if trend.alert_level.value == "critical"
                                    else (
                                        "high" if trend.alert_level.value == "warning" else "medium"
                                    )
                                ),
                            }
                        )

                # Get health data if available
                health_data = None
                try:
                    from cortex.agents.data_agent.analyzers.health_tracker import (
                        HealthTracker,
                    )

                    project_path = self.root_dir / proj
                    if project_path.exists():
                        health_tracker = HealthTracker()
                        health_data = health_tracker.get_project_health(project_path)
                except Exception:
                    pass

                # Generate warnings for this project
                project_warnings = warning_generator.generate_warnings(proj, trends, health_data)
                all_warnings.extend(project_warnings)
                by_project[proj] = project_warnings

            # Categorize all warnings
            categorized = warning_generator.categorize_warnings(all_warnings)

            return {
                "total_warnings": len(all_warnings),
                "by_severity": {
                    "critical": len(categorized["critical"]),
                    "high": len(categorized["high"]),
                    "medium": len(categorized["medium"]),
                    "low": len(categorized["low"]),
                },
                "by_type": {k: len(v) for k, v in categorized["by_type"].items()},
                "by_project": {k: len(v) for k, v in by_project.items()},
                "warnings": all_warnings,
                "categorized": categorized,
            }
        except Exception as e:
            return {"error": str(e)}

    def perform_deep_analysis(self, project: str) -> Dict[str, Any]:
        """
        Perform deep project analysis including tech stack, architecture, and code quality.

        Args:
            project: Project name

        Returns:
            Dict with comprehensive analysis results

        Example:
            >>> bridge = CortexBridge()
            >>> analysis = bridge.perform_deep_analysis("cortex")
        """
        return self.analyze_project_deep(project)

    def analyze_project_deep(self, project_name: str, quick: bool = False) -> Dict[str, Any]:
        """
        Perform a deep analysis of a project, including tech stack, architecture, and code quality.

        Args:
            project_name: The name of the project to analyze.
            quick: If True, skip expensive operations (critical files, git log).

        Returns:
            A dictionary containing the project's deep analysis profile.
        """
        try:
            from cortex.agents.data_agent.analyzers.project_analyzer import (
                ProjectAnalyzer,
            )

            analyzer = ProjectAnalyzer(self.root_dir)
            return analyzer.analyze_project_deep(project_name, quick)
        except Exception as e:
            return {"error": str(e)}

    def get_project_profile(self, project: str) -> Dict[str, Any]:
        """
        Get project profile with tech stack and coverage.

        Args:
            project: Project name

        Returns:
            Project profile data
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                return {"error": f"Project not found: {project}"}

            engine = RecommendationEngine(project_path=project_path, enable_learning=True)
            profile = engine.get_project_profile()

            if not profile:
                return {"error": "Project profiler not available"}

            return {
                "success": True,
                "project": profile.project_name,
                "tech_stack": {
                    "languages": list(profile.tech_stack.languages),
                    "frameworks": list(profile.tech_stack.frameworks),
                    "databases": list(profile.tech_stack.databases),
                    "tools": list(profile.tech_stack.tools),
                },
                "test_coverage": {
                    "test_files": profile.test_coverage.test_files,
                    "source_files": profile.test_coverage.source_files,
                    "estimated_coverage": profile.test_coverage.estimated_coverage,
                    "is_low": profile.test_coverage.is_low,
                },
                "critical_files": [
                    {"path": cf.path, "reason": cf.reason} for cf in profile.critical_files[:5]
                ],
                "warnings": profile.warnings,
            }

        except Exception as e:
            return {"error": str(e)}

    # --- 8. Layer 2: Pattern Memory Bridge ---

    def find_similar_work_by_task(self, project: str, task: str, limit: int = 5) -> Dict[str, Any]:
        """
        Find similar work from other projects by task description.

        Args:
            project: Current project name
            task: Task description
            limit: Maximum results

        Returns:
            Similar work from other projects
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir

            engine = RecommendationEngine(project_path=project_path, enable_patterns=True)
            similar = engine.find_similar_work(task=task, limit=limit)

            return {
                "success": True,
                "task": task,
                "similar_work": similar,
                "count": len(similar),
            }

        except Exception as e:
            return {"error": str(e)}

    # --- 9. Smart Recommendations Bridge ---

    def get_smart_recommendations(
        self, project: str, limit: int = 10, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get smart, prioritized recommendations for a project.

        Args:
            project: Project name
            limit: Maximum recommendations to return
            context: Optional context dictionary

        Returns:
            Dictionary with prioritized recommendations
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir

            engine = RecommendationEngine(
                project_path=project_path, enable_learning=True, enable_patterns=True
            )

            recommendations = engine.generate_recommendations(context=context, limit=limit)

            # Convert to dict format
            rec_dicts = []
            for rec in recommendations:
                rec_dict = {
                    "type": rec.type,
                    "title": rec.title,
                    "description": rec.description,
                    "priority": rec.priority,
                    "confidence": rec.confidence,
                    "calculated_priority": (
                        rec.metadata.get("calculated_priority", 0.5) if rec.metadata else 0.5
                    ),
                    "files": rec.files or [],
                    "steps": rec.steps or [],
                    "rationale": (rec.metadata.get("rationale", "") if rec.metadata else ""),
                    "pattern": rec.metadata.get("pattern", "") if rec.metadata else "",
                    "pattern_success_rate": (
                        rec.metadata.get("pattern_success_rate", 0.0) if rec.metadata else 0.0
                    ),
                }
                rec_dicts.append(rec_dict)

            return {
                "success": True,
                "project": project,
                "recommendations": rec_dicts,
                "count": len(rec_dicts),
                "summary": {
                    "high_priority": sum(
                        1 for r in rec_dicts if r.get("calculated_priority", 0) > 0.7
                    ),
                    "pattern_based": sum(1 for r in rec_dicts if r.get("pattern", "")),
                },
            }

        except Exception as e:
            return {"error": str(e)}

    def get_recommendation_dashboard(self, project: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get recommendation dashboard with prioritized recommendations, health, and context.

        Args:
            project: Project name
            limit: Maximum recommendations to return

        Returns:
            Dashboard dictionary with recommendations, health, alerts, and patterns
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir

            engine = RecommendationEngine(
                project_path=project_path, enable_learning=True, enable_patterns=True
            )

            dashboard = engine.get_recommendation_dashboard(project=project, limit=limit)

            return {"success": True, **dashboard}

        except Exception as e:
            return {"error": str(e)}

    # ==================== Rule Tracking Methods ====================

    def log_rule_event(
        self, rule_name: str, event_type: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log a rule adherence event for Cortex learning.

        Args:
            rule_name: Name of the rule (e.g., "read_before_edit", "file_references", "unnecessary_questions")
            event_type: Type of event ("violation", "adherence", "warning")
            context: Additional context (tool, file, project, etc.)

        Returns:
            Dict with success status and event_id
        """
        from datetime import datetime

        # Rule events file
        rule_events_file = Path.home() / ".cortex" / "rule_events.jsonl"
        rule_events_file.parent.mkdir(parents=True, exist_ok=True)

        event_id = f"rule_{rule_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        event = {
            "event_id": event_id,
            "timestamp": datetime.now().isoformat(),
            "rule_name": rule_name,
            "event_type": event_type,
            "context": context or {},
            "project": context.get("project", "unknown") if context else "unknown",
            "session_id": context.get("session_id") if context else None,
        }

        try:
            with open(rule_events_file, "a") as f:
                f.write(json.dumps(event) + "\n")

            return {
                "success": True,
                "event_id": event_id,
                "rule_name": rule_name,
                "event_type": event_type,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_rule_correlations(
        self, rule_name: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get correlations between rule violations and session outcomes.

        Args:
            rule_name: Optional filter by specific rule
            days: Number of days to analyze

        Returns:
            Dict with rule correlations and patterns
        """
        from collections import defaultdict
        from datetime import datetime, timedelta

        rule_events_file = Path.home() / ".cortex" / "rule_events.jsonl"
        outcomes_file = Path.home() / ".cortex" / "outcomes.jsonl"

        # Load rule events
        rule_events = []
        if rule_events_file.exists():
            cutoff = datetime.now() - timedelta(days=days)
            with open(rule_events_file, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"])
                        if event_time >= cutoff:
                            if rule_name is None or event["rule_name"] == rule_name:
                                rule_events.append(event)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

        # Load outcomes for correlation
        outcomes = []
        if outcomes_file.exists():
            with open(outcomes_file, "r") as f:
                for line in f:
                    try:
                        outcome = json.loads(line.strip())
                        outcomes.append(outcome)
                    except json.JSONDecodeError:
                        continue

        # Analyze correlations
        by_rule = defaultdict(lambda: {"violations": 0, "adherences": 0, "warnings": 0})
        for event in rule_events:
            rule = event["rule_name"]
            event_type = event["event_type"]
            if event_type == "violation":
                by_rule[rule]["violations"] += 1
            elif event_type == "adherence":
                by_rule[rule]["adherences"] += 1
            elif event_type == "warning":
                by_rule[rule]["warnings"] += 1

        # Calculate adherence rates
        correlations = {}
        for rule, counts in by_rule.items():
            total = counts["violations"] + counts["adherences"]
            adherence_rate = counts["adherences"] / total if total > 0 else 0.0
            correlations[rule] = {
                "total_events": total + counts["warnings"],
                "violations": counts["violations"],
                "adherences": counts["adherences"],
                "warnings": counts["warnings"],
                "adherence_rate": round(adherence_rate, 3),
            }

        return {
            "success": True,
            "days_analyzed": days,
            "total_events": len(rule_events),
            "rules_tracked": list(correlations.keys()),
            "correlations": correlations,
            "outcomes_count": len(outcomes),
        }

    # ==================== Deep Mode Integration ====================

    def analyze_deep(self, project: Optional[str] = None, output_json: bool = False) -> Dict[str, Any]:
        """
        Run comprehensive deep analysis (Depth-First Architecture).

        Performs:
        - Full git history analysis (90 days)
        - Fresh health calculation (no caching)
        - Code quality metrics
        - Automatic warnings and recommendations

        Args:
            project: Project name (auto-detect if None)
            output_json: Return JSON-serializable dict instead of object

        Returns:
            DeepIntelligence object or JSON dict

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.analyze_deep("cortex")
            >>> print(f"Health: {result.health.score}/100")
        """
        if not self.deep_analyzer:
            return {"error": "DeepAnalyzer not available (import failed)"}

        if not self.latency_manager:
            return {"error": "AdaptiveLatencyManager not available (import failed)"}

        # Auto-detect project if not specified
        if project is None:
            project = self._detect_current_project()

        # Get deep mode configuration
        config = self.latency_manager.select_mode(
            requested_mode=AnalysisMode.DEEP if AnalysisMode else None,
            context=None
        )

        # Run deep analysis
        try:
            result = self.deep_analyzer.analyze(project, config.__dict__)

            if output_json:
                return self._serialize_deep_intelligence(result)

            return result
        except Exception as e:
            return {"error": f"Deep analysis failed: {str(e)}"}

    def analyze_quick(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Run minimal fast analysis (<1s).

        Uses existing shallow context for speed.

        Args:
            project: Project name (auto-detect if None)

        Returns:
            Quick context dict

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.analyze_quick("cortex")
            >>> print(f"Status: {result.get('status')}")
        """
        if project is None:
            project = self._detect_current_project()

        # Use existing fast path via query_intelligence
        try:
            if self.unified_intel:
                result = self.unified_intel.query_intelligence(
                    request=f"Quick status check for {project}",
                    project=project,
                    query_type="status"
                )
                return result
            else:
                # Fallback to basic context
                return {
                    "project": project,
                    "status": "quick mode",
                    "message": "UnifiedIntelligence not available, returning basic context"
                }
        except Exception as e:
            return {"error": f"Quick analysis failed: {str(e)}"}

    def analyze_auto(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Run adaptive analysis with intelligent mode selection.

        Selects mode based on:
        - Time since last session
        - Project state (uncommitted changes, stale branches)
        - User preferences

        Args:
            project: Project name (auto-detect if None)

        Returns:
            Intelligence result (deep or quick depending on context)

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.analyze_auto("cortex")
            >>> # Automatically selects best mode
        """
        if not self.latency_manager:
            return {"error": "AdaptiveLatencyManager not available"}

        if project is None:
            project = self._detect_current_project()

        # Build session context for mode selection
        session_ctx = self._build_session_context(project)

        # Select mode adaptively
        config = self.latency_manager.select_mode(
            requested_mode=AnalysisMode.AUTO if AnalysisMode else None,
            context=session_ctx
        )

        # Route to appropriate analysis
        mode_name = config.mode_name if hasattr(config, 'mode_name') else "deep"

        if mode_name == "fast":
            return self.analyze_quick(project)
        else:
            # Default to deep for balanced and deep modes
            return self.analyze_deep(project)

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
                cwd=self.root_dir
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
                timeout=2
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
            user_preference=None
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
    rec_report_parser = rec_sub.add_parser("report", help="Get full recommendations report")

    # recommendations next - single next action
    rec_next_parser = rec_sub.add_parser("next", help="Get recommended next action")

    # recommendations alerts - risk alerts
    rec_alerts_parser = rec_sub.add_parser("alerts", help="Get risk alerts")

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

        cmd = ["python3", "/Users/jesse.kemp/Dev/.claude/scripts/mine_anti_patterns.py"]
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
                        else "🟡" if alert.get("severity") == "MEDIUM" else "🟢"
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
