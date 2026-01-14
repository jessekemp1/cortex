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

# V2 Prime: Engine imports
try:
    from cortex.engines.absorber import ContextAbsorber, Signal, SignalType
    from cortex.engines.synthesis import SynthesisCore, ContextGraph, Node, NodeType, Edge, EdgeType
    from cortex.engines.broker import ActionBroker, Intervention, InterventionType, Severity
    V2_PRIME_AVAILABLE = True
except ImportError:
    V2_PRIME_AVAILABLE = False
    ContextAbsorber = None
    SynthesisCore = None
    ContextGraph = None
    ActionBroker = None

# V2 Prime: Protocol imports
try:
    from cortex.protocols.iap import IAPHandler, IAPMessage, MessageType, Agent, AgentRole
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

        # Initialize sub-systems
        self.context_intel = (
            ContextIntelligence(self.root_dir) if ContextIntelligence else None
        )
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
                self.iap = IAPHandler(
                    synthesis_core=self.synthesis,
                    action_broker=self.broker
                )
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
        node_id: Optional[str] = None
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
            from cortex.engines.synthesis import Node, NodeType
            import uuid
            
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
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0
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

    def register_agent(self, agent_id: str, role: str, capabilities: List[str] = None) -> Dict[str, Any]:
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

    # --- 1. Context Bridge ---

    def get_context(
        self, query: str, limit: int = 5, project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get relevant context for a query from Knowledge Base and Project History.

        Args:
            query: Natural language query
            limit: Max results
            project: Optional project filter

        Returns:
            List of context items
        """
        if not self.context_intel:
            return [{"error": "ContextIntelligence not available", "source": "system"}]

        # Split query into keywords if it looks like a sentence
        keywords = query.split() if " " in query else [query]

        predictions = self.context_intel.predict_context(
            current_project=project, keywords=keywords, limit=limit
        )

        return [
            {
                "title": p.title,
                "type": p.context_type,
                "description": p.description,
                "confidence": p.confidence,
                "file": str(p.file_path) if p.file_path else None,
                "command": p.command,
            }
            for p in predictions
        ]

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

        Args:
            title: Action title
            rationale: Why this is important
            priority: high/medium/low
            type: Category of recommendation
            effort: Estimated effort
            related_project: Associated project
        """
        rec_data = {
            "id": f"bridge_{int(datetime.now().timestamp())}_{abs(hash(title)) % 1000}",
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
            return True

        except Exception as e:
            print(f"Bridge Error (Inject): {e}", file=sys.stderr)
            return False

    # --- 3. Execution Bridge ---

    def trigger_action(
        self, agent_id: str, payload: Dict[str, Any] = None
    ) -> Dict[str, Any]:
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
        self,
        project: str,
        days: int = 7,
        force_refresh: bool = False
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer()
            return analyzer.find_circular_dependencies(project)
        except Exception as e:
            return {"error": str(e)}

    def export_dependency_graph(
        self,
        project: str,
        format: str = "ascii",
        include_stdlib: bool = False,
        include_external: bool = True
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
            from cortex.agents.data_agent.analyzers.dependency_mapper import DependencyMapper

            analyzer = ProjectAnalyzer()
            project_path = analyzer.projects.get(project)
            if not project_path:
                return {"error": f"Project '{project}' not found"}

            mapper = DependencyMapper(project_path)

            if format == "dot":
                graph = mapper.export_to_dot(
                    include_stdlib=include_stdlib,
                    include_external=include_external
                )
            elif format == "mermaid":
                graph = mapper.export_to_mermaid(
                    include_stdlib=include_stdlib,
                    include_external=include_external
                )
            elif format == "ascii":
                graph = mapper.generate_ascii_tree()
            else:
                return {"error": f"Unknown format '{format}'. Use: ascii, dot, or mermaid"}

            return {
                "success": True,
                "project": project,
                "format": format,
                "graph": graph
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer()
            return analyzer.compare_package_dependencies(project)
        except Exception as e:
            return {"error": str(e)}

    def analyze_portfolio_dependencies(
        self,
        project_filter: Optional[str] = None
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
            analyzer = ProjectAnalyzer()
            return analyzer.analyze_portfolio_dependencies(project_filter=project_filter)
        except Exception as e:
            return {"error": str(e)}

    # --- Intelligence Enhancement Methods ---

    def query_intelligence(
        self,
        request: str,
        project: str,
        query_type: str = "spec",
        use_cache: bool = True,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """
        Query unified intelligence API with enhanced features.

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

        try:
            query_type_enum = IntelligenceQueryType(query_type)
            result = self.unified_intel.query(
                user_request=request,
                project=project,
                query_type=query_type_enum,
                use_cache=use_cache,
                parallel=parallel
            )
            return result.to_dict()
        except Exception as e:
            return {"error": str(e)}

    def find_similar_work(
        self,
        domain: str,
        project: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
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
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search indexed specifications (alias for find_similar_work for API compatibility).

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
        if not self.spec_kb:
            return [{"error": "Spec Knowledge Base not available"}]

        try:
            # Try intelligence version first (ChromaDB-based)
            if hasattr(self.spec_kb, 'find_similar'):
                from dataclasses import asdict
                similar = self.spec_kb.find_similar(query, k=limit, project_filter=project)
                # Transform SimilarWork dataclass to expected format
                results = []
                for s in similar:
                    result = asdict(s)
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
                return results
            # Fallback to simple hash-based version
            elif hasattr(self.spec_kb, 'search'):
                results = self.spec_kb.search(query, project=project, limit=limit)
                # Simple version already returns dicts with spec_name
                return results
            else:
                return [{"error": "Spec KB has no search method"}]
        except Exception as e:
            return [{"error": str(e)}]

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
                    f"Goals: {', '.join(context_dict.get('active_goals', []))}"
                ]
                return {"context": "\n".join(lines), "format": "terminal"}
            else:
                # Return structured dict with expected keys
                context_dict = asdict(session_ctx)
                # Map to expected format: project, git, goals
                result = {
                    "project": {
                        "name": context_dict.get("project", "unknown"),
                        "path": context_dict.get("working_directory", "")
                    },
                    "git": {
                        "recent_commits": context_dict.get("recent_work", [])
                    },
                    "goals": context_dict.get("active_goals", []),
                    "focus": context_dict.get("current_focus", "unknown"),
                    "working_directory": context_dict.get("working_directory", ""),
                    "last_updated": context_dict.get("last_updated", "")
                }
                return result
        except Exception as e:
            return {"error": str(e)}

    def index_spec(
        self,
        spec_path: str,
        project: str,
        domain: Optional[str] = None
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
                "indexed_at": datetime.now().isoformat()
            }

            spec_id = self.spec_kb.index_spec(Path(spec_path), metadata)

            return {
                "success": True,
                "spec_id": spec_id,
                "message": f"Spec indexed: {spec_path}"
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

    # --- Batch API Methods ---

    def submit_research_batch(
        self,
        research_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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

    def submit_briefing_batch(
        self,
        contexts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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
            from cortex.batch.briefing_batcher import BriefingContext, RecommendationBatcher
            batcher = RecommendationBatcher(root_dir=self.root_dir)
            
            # Convert dicts to BriefingContext objects
            briefing_contexts = [
                BriefingContext(
                    portfolio_pulse=ctx.get("portfolio_pulse", {}),
                    system_health=ctx.get("system_health", {}),
                    execution_history=ctx.get("execution_history", {}),
                    goals_context=ctx.get("goals_context", {}),
                    context_id=ctx.get("context_id", f"briefing_{i}")
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
        self,
        project: str,
        title: str = None,
        auto_generate: bool = True
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
            from recommendation_engine import RecommendationEngine
            from intelligence.planning import PlanPriority

            # Initialize recommendation engine for the project
            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir  # Fallback to root

            engine = RecommendationEngine(project_path=project_path)

            # Create plan
            plan = engine.create_plan(
                title=title,
                priority=PlanPriority.MEDIUM,
                auto_generate=auto_generate
            )

            return {
                "success": True,
                "plan_id": plan.id,
                "title": plan.title,
                "steps": len(plan.steps),
                "estimated_time": plan.estimated_total_time,
                "message": f"Plan created: {plan.id}"
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

            return {
                "success": True,
                "plans": plans,
                "count": len(plans)
            }

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
                return {
                    "success": True,
                    "markdown": plan.to_markdown()
                }
            else:
                return {
                    "success": True,
                    "plan": plan.to_dict()
                }

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
                "next_step": {
                    "id": next_step.id,
                    "title": next_step.title,
                    "description": next_step.description
                } if next_step else None
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
                "next_step": {
                    "id": next_step.id,
                    "title": next_step.title,
                    "description": next_step.description
                } if next_step else None,
                "completed": progress.get('completion_pct') == 100
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

            return {
                "success": True,
                "progress": progress
            }

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
            from work_absorber import WorkAbsorber
            from datetime import datetime

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

    def get_warnings(self, project: Optional[str] = None, severity: Optional[str] = None) -> Dict[str, Any]:
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
            from cortex.agents.data_agent.analyzers.warning_generator import WarningGenerator
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
            from cortex.agents.data_agent.analyzers.warning_generator import WarningGenerator
            from cortex.agents.data_agent.analyzers.health_tracker import HealthTracker

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
            from cortex.agents.data_agent.analyzers.warning_generator import WarningGenerator
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
                    trends.append({
                        "metric": metric_type,
                        "direction": "decreasing" if trend.direction.value == "degrading" else ("increasing" if trend.direction.value == "improving" else "stable"),
                        "current_value": trend.end_value,
                        "velocity": trend.rate,
                        "is_concerning": trend.alert_level.value in ["warning", "critical"],
                        "severity": "critical" if trend.alert_level.value == "critical" else ("high" if trend.alert_level.value == "warning" else "medium"),
                    })
            
            # Get health data if available
            health_data = None
            try:
                from cortex.agents.data_agent.analyzers.health_tracker import HealthTracker
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

    def get_warning_dashboard(self, project_name: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Get a dashboard of warnings, optionally filtered by project.

        Args:
            project_name: Optional project name to filter warnings.
            days: The number of days to look back for warnings.

        Returns:
            A dictionary representing the warning dashboard.
        """
        try:
            from cortex.agents.data_agent.analyzers.warning_generator import WarningGenerator
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
                        "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
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
                        trends.append({
                            "metric": metric_type,
                            "direction": "decreasing" if trend.direction.value == "degrading" else ("increasing" if trend.direction.value == "improving" else "stable"),
                            "current_value": trend.end_value,
                            "velocity": trend.rate,
                            "is_concerning": trend.alert_level.value in ["warning", "critical"],
                            "severity": "critical" if trend.alert_level.value == "critical" else ("high" if trend.alert_level.value == "warning" else "medium"),
                        })
                
                # Get health data if available
                health_data = None
                try:
                    from cortex.agents.data_agent.analyzers.health_tracker import HealthTracker
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
            from cortex.agents.data_agent.analyzers.project_analyzer import ProjectAnalyzer
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
                    "tools": list(profile.tech_stack.tools)
                },
                "test_coverage": {
                    "test_files": profile.test_coverage.test_files,
                    "source_files": profile.test_coverage.source_files,
                    "estimated_coverage": profile.test_coverage.estimated_coverage,
                    "is_low": profile.test_coverage.is_low
                },
                "critical_files": [
                    {"path": cf.path, "reason": cf.reason}
                    for cf in profile.critical_files[:5]
                ],
                "warnings": profile.warnings
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
                "count": len(similar)
            }

        except Exception as e:
            return {"error": str(e)}

    # --- 9. Smart Recommendations Bridge ---

    def get_smart_recommendations(
        self,
        project: str,
        limit: int = 10,
        context: Optional[Dict[str, Any]] = None
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
                project_path=project_path,
                enable_learning=True,
                enable_patterns=True
            )
            
            recommendations = engine.generate_recommendations(
                context=context,
                limit=limit
            )
            
            # Convert to dict format
            rec_dicts = []
            for rec in recommendations:
                rec_dict = {
                    "type": rec.type,
                    "title": rec.title,
                    "description": rec.description,
                    "priority": rec.priority,
                    "confidence": rec.confidence,
                    "calculated_priority": rec.metadata.get("calculated_priority", 0.5) if rec.metadata else 0.5,
                    "files": rec.files or [],
                    "steps": rec.steps or [],
                    "rationale": rec.metadata.get("rationale", "") if rec.metadata else "",
                    "pattern": rec.metadata.get("pattern", "") if rec.metadata else "",
                    "pattern_success_rate": rec.metadata.get("pattern_success_rate", 0.0) if rec.metadata else 0.0,
                }
                rec_dicts.append(rec_dict)
            
            return {
                "success": True,
                "project": project,
                "recommendations": rec_dicts,
                "count": len(rec_dicts),
                "summary": {
                    "high_priority": sum(1 for r in rec_dicts if r.get("calculated_priority", 0) > 0.7),
                    "pattern_based": sum(1 for r in rec_dicts if r.get("pattern", "")),
                }
            }
            
        except Exception as e:
            return {"error": str(e)}

    def get_recommendation_dashboard(
        self,
        project: str,
        limit: int = 10
    ) -> Dict[str, Any]:
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
                project_path=project_path,
                enable_learning=True,
                enable_patterns=True
            )
            
            dashboard = engine.get_recommendation_dashboard(
                project=project,
                limit=limit
            )
            
            return {
                "success": True,
                **dashboard
            }
            
        except Exception as e:
            return {"error": str(e)}


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
    intel_parser.add_argument("--type", default="spec", help="Query type (spec/impl/analysis/research)")

    # similar-work
    similar_parser = subparsers.add_parser("similar-work", help="Find similar work")
    similar_parser.add_argument("domain", help="Domain/topic")
    similar_parser.add_argument("--project", required=True, help="Project name")
    similar_parser.add_argument("--limit", type=int, default=5, help="Max results")

    # session-context
    session_parser = subparsers.add_parser("session-context", help="Get session context")
    session_parser.add_argument("--format", choices=["json", "terminal", "compact"], default="json", help="Output format")
    session_parser.add_argument("--max-chars", type=int, default=450, help="Max characters for compact format")

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
    list_plans_parser.add_argument("--status", choices=["draft", "active", "completed", "cancelled"], help="Filter by status")

    # plan show
    show_plan_parser = plan_sub.add_parser("show", help="Show plan details")
    show_plan_parser.add_argument("plan_id", help="Plan ID")
    show_plan_parser.add_argument("--format", choices=["json", "markdown"], default="markdown", help="Output format")

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
    profile_parser = subparsers.add_parser("profile", help="Analyze project structure and tech stack")
    profile_parser.add_argument("project", help="Project name")

    # patterns - Pattern search (Layer 2)
    patterns_parser = subparsers.add_parser("patterns", help="Find similar work from other projects")
    patterns_parser.add_argument("project", help="Current project name")
    patterns_parser.add_argument("task", help="Task description")
    patterns_parser.add_argument("--limit", type=int, default=5, help="Maximum results")

    # batch
    batch_parser = subparsers.add_parser("batch", help="Batch API operations")
    batch_sub = batch_parser.add_subparsers(dest="batch_command", help="Batch subcommand")
    
    # batch research
    batch_research_parser = batch_sub.add_parser("research", help="Submit research batch")
    batch_research_parser.add_argument("--file", required=True, help="JSON file with research items")
    
    # batch briefing
    batch_briefing_parser = batch_sub.add_parser("briefing", help="Submit briefing batch")
    batch_briefing_parser.add_argument("--file", required=True, help="JSON file with briefing contexts")
    
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
    rec_dashboard_parser.add_argument("--limit", type=int, default=10, help="Maximum recommendations")

    args = parser.parse_args()
    bridge = CortexBridge()

    if args.command == "context":
        print(
            json.dumps(bridge.get_context(args.query, project=args.project), indent=2)
        )
    elif args.command == "inject":
        success = bridge.inject_recommendation(
            args.title, args.rationale, priority=args.priority
        )
        print(json.dumps({"success": success}))
    elif args.command == "trigger":
        print(json.dumps(bridge.trigger_action(args.agent)))
    elif args.command == "portfolio":
        if args.subcommand == "patterns":
            result = bridge.get_patterns(pattern_type=getattr(args, 'type', None))
            print(json.dumps(result, indent=2))
        elif args.subcommand == "lessons":
            result = bridge.get_lessons(
                project=getattr(args, 'project', None),
                pattern=getattr(args, 'pattern', None)
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
        result = bridge.query_intelligence(args.request, args.project, getattr(args, 'type', 'spec'))
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "similar-work":
        result = bridge.find_similar_work(args.domain, args.project, getattr(args, 'limit', 5))
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "session-context":
        result = bridge.get_session_context()
        format_type = getattr(args, 'format', 'json')

        # Handle compact format for inject_context hook (<450 chars)
        if format_type == 'compact':
            if 'error' in result:
                # Fallback to empty context
                print("")
                sys.exit(0)

            max_chars = getattr(args, 'max_chars', 450)
            parts = []

            # Project
            project = result.get('project', 'Unknown')
            parts.append(f"Project: {project}")

            # Focus (truncate if needed)
            focus = result.get('current_focus', 'No active focus')
            if len(focus) > 50:
                focus = focus[:47] + "..."
            parts.append(f"Focus: {focus}")

            # First goal if available
            if result.get('active_goals'):
                goal = result['active_goals'][0]
                if len(goal) > 40:
                    goal = goal[:37] + "..."
                parts.append(f"Goal: {goal}")

            # Build compact string
            compact = " | ".join(parts)

            # Enforce max_chars limit
            if len(compact) > max_chars:
                compact = compact[:max_chars-3] + "..."

            print(compact)

        # Handle terminal format for shell startup display
        elif format_type == 'terminal':
            if 'error' in result:
                # Fail silently for startup hook
                sys.exit(0)

            print("\n🧠 Cortex Session Intelligence\n")

            # Handle nested project structure
            project_info = result.get('project', {})
            if isinstance(project_info, dict):
                project_name = project_info.get('name', 'Unknown')
            else:
                project_name = project_info
            print(f"📂 Project: {project_name}")

            print(f"🎯 Focus: {result.get('focus', result.get('current_focus', 'No active focus'))}")

            # Handle goals (could be in 'goals' or 'active_goals')
            goals = result.get('goals', result.get('active_goals', []))
            if goals:
                goals_display = goals[:3]  # Show max 3 goals
                print(f"✅ Goals: {', '.join(goals_display)}")

            # Handle recent work (could be in git.recent_commits or recent_work)
            git_info = result.get('git', {})
            recent_commits = git_info.get('recent_commits', result.get('recent_work', []))
            if recent_commits:
                print("\n📝 Recent Work:")
                for work in recent_commits[:3]:  # Show max 3 items
                    print(f"   • {work.get('summary', work.get('commit', 'Unknown'))}")

            print()  # Empty line for spacing
        else:
            # JSON format (default)
            print(json.dumps(result, indent=2, default=str))
    elif args.command == "index-spec":
        result = bridge.index_spec(args.path, args.project, getattr(args, 'domain', None))
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "health":
        import subprocess

        # Delegate to data agent CLI
        cortex_root = Path(__file__).parent

        if args.health_command == "summary":
            subprocess.run([
                sys.executable, "-m", "agents.data_agent.cli",
                "summary", str(getattr(args, 'days', 7))
            ], cwd=cortex_root)
        elif args.health_command == "project":
            subprocess.run([
                sys.executable, "-m", "agents.data_agent.cli",
                "project", args.name, str(getattr(args, 'days', 7))
            ], cwd=cortex_root)
        elif args.health_command == "compare":
            subprocess.run([
                sys.executable, "-m", "agents.data_agent.cli",
                "compare", args.project1, args.project2, str(getattr(args, 'days', 7))
            ], cwd=cortex_root)
        elif args.health_command == "trends":
            subprocess.run([
                sys.executable, "-m", "agents.data_agent.cli",
                "trends", args.name
            ], cwd=cortex_root)
        else:
            health_parser.print_help()
    elif args.command == "plan":
        if args.plan_command == "create":
            result = bridge.create_plan(args.project, title=getattr(args, 'title', None))
            print(json.dumps(result, indent=2))
        elif args.plan_command == "list":
            result = bridge.list_plans(status=getattr(args, 'status', None))
            print(json.dumps(result, indent=2))
        elif args.plan_command == "show":
            result = bridge.get_plan(args.plan_id, format=getattr(args, 'format', 'json'))
            if getattr(args, 'format', 'json') == "markdown":
                print(result.get('markdown', 'No plan found'))
            else:
                print(json.dumps(result, indent=2))
        elif args.plan_command == "start":
            result = bridge.start_plan(args.plan_id)
            print(json.dumps(result, indent=2))
        elif args.plan_command == "complete":
            result = bridge.complete_step(args.step_id, notes=getattr(args, 'notes', ''))
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
        result = bridge.find_similar_work(args.project, args.task, limit=getattr(args, 'limit', 5))
        print(json.dumps(result, indent=2))
    elif args.command == "recommendations":
        if args.rec_command == "report":
            result = bridge.get_recommendations()
            print(json.dumps(result, indent=2, default=str))
        elif args.rec_command == "next":
            result = bridge.get_next_action()
            # Pretty print for terminal
            print(f"\n🎯 Recommended Next Action")
            print(f"   Priority: {result.get('priority', 'Unknown')}")
            print(f"   Action: {result.get('action', 'Unknown')}")
            if result.get('project'):
                print(f"   Project: {result['project']}")
            print()
        elif args.rec_command == "alerts":
            alerts = bridge.get_risk_alerts()
            if not alerts or (len(alerts) == 1 and 'error' in alerts[0]):
                print("\n✅ No risk alerts\n")
            else:
                print(f"\n⚠️  Risk Alerts ({len(alerts)})")
                for alert in alerts:
                    icon = "🔴" if alert.get("severity") == "HIGH" else "🟡" if alert.get("severity") == "MEDIUM" else "🟢"
                    print(f"   {icon} [{alert.get('severity', 'Unknown')}] {alert.get('message', 'Unknown')}")
                    print(f"      → {alert.get('recommendation', '')}")
                print()
        elif args.rec_command == "priorities":
            priorities = bridge.get_priority_projects(limit=getattr(args, 'limit', 5))
            print(f"\n📋 Priority Projects ({len(priorities)})")
            for i, p in enumerate(priorities, 1):
                health = f" [{p.get('health_score')}/100]" if p.get('health_score') else ""
                print(f"   {i}. [{p.get('priority', 'Unknown')}] {p.get('project', 'Unknown')}{health}")
                print(f"      {p.get('reason', '')}")
            print()
        elif args.rec_command == "get":
            result = bridge.get_smart_recommendations(
                args.project,
                limit=getattr(args, 'limit', 10)
            )
            print(json.dumps(result, indent=2))
        elif args.rec_command == "dashboard":
            result = bridge.get_recommendation_dashboard(
                args.project,
                limit=getattr(args, 'limit', 10)
            )
            print(json.dumps(result, indent=2))
        else:
            rec_parser.print_help()
    elif args.command == "batch":
        if args.batch_command == "research":
            # Load research items from JSON file
            with open(args.file, 'r') as f:
                research_items = json.load(f)
            result = bridge.submit_research_batch(research_items)
            print(json.dumps(result, indent=2))
        elif args.batch_command == "briefing":
            # Load briefing contexts from JSON file
            with open(args.file, 'r') as f:
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
