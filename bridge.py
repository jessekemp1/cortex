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
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

# Add parent directory to path to import Cortex modules
CORTEX_ROOT = Path(__file__).parent.parent
if str(CORTEX_ROOT) not in sys.path:
    sys.path.insert(0, str(CORTEX_ROOT))

# Import Cortex modules
try:
    from cortex.context_intelligence import ContextIntelligence
    from cortex.integration.local_orchestrator import CortexLocalOrchestratorIntegration
except ImportError:
    ContextIntelligence = None
    CortexLocalOrchestratorIntegration = None


class CortexBridge:
    """Universal interface for AI agents to interact with Cortex."""

    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = Path(root_dir)
        
        # Initialize sub-systems
        self.context_intel = ContextIntelligence(self.root_dir) if ContextIntelligence else None
        self.orchestrator = CortexLocalOrchestratorIntegration(self.root_dir) if CortexLocalOrchestratorIntegration else None

    # --- 1. Context Bridge ---

    def get_context(self, query: str, limit: int = 5, project: Optional[str] = None) -> List[Dict[str, Any]]:
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
            current_project=project,
            keywords=keywords,
            limit=limit
        )

        return [
            {
                "title": p.title,
                "type": p.context_type,
                "description": p.description,
                "confidence": p.confidence,
                "file": str(p.file_path) if p.file_path else None,
                "command": p.command
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
        related_project: str = ""
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
            "source": "CortexBridge"
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
                agent_id=agent_id,
                context=payload or {}
            )
            
            return {
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

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
    
    args = parser.parse_args()
    bridge = CortexBridge()
    
    if args.command == "context":
        print(json.dumps(bridge.get_context(args.query, project=args.project), indent=2))
    elif args.command == "inject":
        success = bridge.inject_recommendation(args.title, args.rationale, priority=args.priority)
        print(json.dumps({"success": success}))
    elif args.command == "trigger":
        print(json.dumps(bridge.trigger_action(args.agent)))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
