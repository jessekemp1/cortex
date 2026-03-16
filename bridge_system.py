"""
Cortex Bridge - System Mixin

V2 Prime (graph, interventions, IAP), health monitoring, dependency analysis,
batch operations, planning, work absorption, warnings, and deep analysis.

Split from bridge.py for maintainability (Feb 2026).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Conditional imports needed by mixin methods (status reporting)
try:
    from intelligence.context_optimizer import ContextOptimizer

    CONTEXT_OPTIMIZER_AVAILABLE = True
except ImportError:
    CONTEXT_OPTIMIZER_AVAILABLE = False
    ContextOptimizer = None

try:
    from intelligence.feedback.implicit_collector import ImplicitFeedbackCollector

    IMPLICIT_FEEDBACK_AVAILABLE = True
except ImportError:
    IMPLICIT_FEEDBACK_AVAILABLE = False
    ImplicitFeedbackCollector = None

try:
    from intelligence.memory.tiered_memory import TieredMemory

    TIERED_MEMORY_AVAILABLE = True
except ImportError:
    TIERED_MEMORY_AVAILABLE = False
    TieredMemory = None

try:
    from intelligence.memory.hybrid_retriever import HybridRetriever

    HYBRID_RETRIEVER_AVAILABLE = True
except ImportError:
    HYBRID_RETRIEVER_AVAILABLE = False
    HybridRetriever = None


class SystemMixin:
    """System-related methods for CortexBridge.

    This mixin provides methods for V2 Prime engine operations,
    portfolio health, dependency analysis, batch jobs, planning,
    work absorption, warnings, and project profiling.

    All methods access self.* attributes initialized by CortexBridgeBase.__init__.
    """

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
                    self.implicit_feedback.get_session_stats() if self.implicit_feedback else None
                ),
            },
            "tiered_memory": {
                "available": TIERED_MEMORY_AVAILABLE,
                "enabled": self.tiered_memory is not None,
                "stats": (self.tiered_memory.get_stats() if self.tiered_memory else None),
            },
            "hybrid_retriever": {
                "available": HYBRID_RETRIEVER_AVAILABLE,
                "enabled": self.hybrid_retriever is not None,
                "pattern_count": (
                    len(self.hybrid_retriever.patterns) if self.hybrid_retriever else 0
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

    def submit_intelligence_briefing(self, tracks: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Submit intelligence briefing research batch (7 tracks by default).

        Uses BriefingResearcher to research AI engineering, agent orchestration,
        Claude ecosystem, and Cortex-competitive landscape via Batch API.

        Args:
            tracks: Optional custom track list. Defaults to BRIEFING_TRACKS.

        Returns:
            {"batch_id": str, "submitted_count": int, "tracks": [str]}

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.submit_intelligence_briefing()
            >>> # Later: bridge.collect_intelligence_briefing(result["batch_id"])
        """
        try:
            from cortex.batch.briefing_researcher import BriefingResearcher

            researcher = BriefingResearcher(tracks=tracks)
            return researcher.submit_briefing_batch()
        except ImportError as e:
            return {"error": f"BriefingResearcher not available: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def collect_intelligence_briefing(self, batch_id: str) -> Dict[str, Any]:
        """
        Collect completed intelligence briefing and synthesize into markdown.

        Args:
            batch_id: From submit_intelligence_briefing().

        Returns:
            {"briefing_file": str, "tracks_completed": int, "summary": str}
        """
        try:
            from cortex.batch.briefing_researcher import BriefingResearcher

            researcher = BriefingResearcher()
            return researcher.collect_and_synthesize(batch_id)
        except ImportError as e:
            return {"error": f"BriefingResearcher not available: {e}"}
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
