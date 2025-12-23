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
        self.spec_kb = SpecKnowledgeBase() if SpecKnowledgeBase else None
        self.session_mgr = SessionManager(self.root_dir) if SessionManager else None

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

    def get_portfolio_stats(self) -> Dict[str, Any]:
        """
        Get portfolio statistics.

        Returns:
            Dict with stats about projects, patterns, lessons

        Example:
            >>> bridge = CortexBridge()
            >>> stats = bridge.get_portfolio_stats()
            >>> print(stats["total_projects"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_stats()
        except Exception as e:
            return {"error": str(e)}

    # --- Intelligence Enhancement Methods ---

    def query_intelligence(
        self,
        request: str,
        project: str,
        query_type: str = "spec"
    ) -> Dict[str, Any]:
        """
        Query unified intelligence API.

        Args:
            request: User request (e.g., "enhance golden spec method")
            project: Project name (e.g., "cortex")
            query_type: Type of query ("spec", "impl", "analysis", "research")

        Returns:
            Dict representation of IntelligenceResult

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.query_intelligence("enhance golden spec", "cortex")
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
                query_type=query_type_enum
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

    def get_session_context(self) -> Dict[str, Any]:
        """
        Get current session context.

        Returns:
            SessionContext dict

        Example:
            >>> bridge = CortexBridge()
            >>> context = bridge.get_session_context()
        """
        if not self.session_mgr:
            return {"error": "Session Manager not available"}

        try:
            from dataclasses import asdict
            context = self.session_mgr.load_session_context()
            if context:
                return asdict(context)
            return {"error": "No session context available"}
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
            print(f"📂 Project: {result.get('project', 'Unknown')}")
            print(f"🎯 Focus: {result.get('current_focus', 'No active focus')}")

            if result.get('active_goals'):
                goals = result['active_goals'][:3]  # Show max 3 goals
                print(f"✅ Goals: {', '.join(goals)}")

            if result.get('recent_work'):
                print(f"\n📝 Recent Work:")
                for work in result.get('recent_work', [])[:3]:  # Show max 3 items
                    print(f"   • {work.get('summary', work.get('commit', 'Unknown'))}")

            print()  # Empty line for spacing
        else:
            # JSON format (default)
            print(json.dumps(result, indent=2, default=str))
    elif args.command == "index-spec":
        result = bridge.index_spec(args.path, args.project, getattr(args, 'domain', None))
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
