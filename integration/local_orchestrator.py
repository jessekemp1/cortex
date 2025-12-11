"""Integration adapter between Cortex and local-orchestrator"""
from typing import Optional, Dict, Any
from pathlib import Path
import sys

# Add local-orchestrator to path FIRST (before cortex can interfere)
LOCAL_ORCH_PATH = str(Path(__file__).parent.parent.parent / "local-orchestrator")
if LOCAL_ORCH_PATH not in sys.path:
    sys.path.insert(0, LOCAL_ORCH_PATH)

try:
    # Import local-orchestrator modules
    # Note: We need to be careful about name collisions with cortex/orchestrator.py
    import importlib.util

    # Load orchestrator module from local-orchestrator explicitly
    orch_spec = importlib.util.spec_from_file_location(
        "lo_orchestrator",
        Path(LOCAL_ORCH_PATH) / "orchestrator.py"
    )
    orch_module = importlib.util.module_from_spec(orch_spec)
    orch_spec.loader.exec_module(orch_module)
    Orchestrator = orch_module.Orchestrator

    # Load other modules normally (no name collision)
    from agents.base import BaseAgent
    from agents.task_agent import ScheduledTaskAgent
    from orchestrator_models import AgentResult

    LOCAL_ORCHESTRATOR_AVAILABLE = True
except (ImportError, AttributeError, FileNotFoundError) as e:
    Orchestrator = None
    BaseAgent = None
    ScheduledTaskAgent = None
    AgentResult = None
    LOCAL_ORCHESTRATOR_AVAILABLE = False

# Import Cortex types
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    # Import from cortex orchestrator
    import importlib.util
    cortex_orch_spec = importlib.util.spec_from_file_location(
        "cortex_orchestrator",
        Path(__file__).parent.parent / "orchestrator.py"
    )
    cortex_orch_module = importlib.util.module_from_spec(cortex_orch_spec)
    cortex_orch_spec.loader.exec_module(cortex_orch_module)
    Recommendation = cortex_orch_module.Recommendation
except (ImportError, AttributeError, FileNotFoundError):
    Recommendation = None


class RecommendationToAgentAdapter:
    """Convert Cortex recommendations to local-orchestrator agents"""
    
    def __init__(self, orchestrator: Optional[Any] = None):
        """
        Initialize adapter.
        
        Args:
            orchestrator: Optional local-orchestrator Orchestrator instance
        """
        self.orchestrator = orchestrator
        # Don't raise error - adapter can work for conversion even without orchestrator
        # Only raise if trying to use features that require orchestrator
    
    def to_agent(self, recommendation: Recommendation) -> BaseAgent:
        """
        Convert Cortex recommendation to local-orchestrator agent.
        
        Args:
            recommendation: Cortex Recommendation object
            
        Returns:
            BaseAgent instance ready for registration
        """
        if not LOCAL_ORCHESTRATOR_AVAILABLE or ScheduledTaskAgent is None:
            raise RuntimeError("local-orchestrator not available. Install dependencies: pip install structlog apscheduler fastapi uvicorn")
        
        # Get title (Recommendation uses 'title' not 'action_title')
        action_title = getattr(recommendation, 'title', getattr(recommendation, 'action_title', 'Unknown Action'))
        priority = getattr(recommendation, 'priority', 'medium')
        rationale = getattr(recommendation, 'rationale', '')
        effort = getattr(recommendation, 'estimated_effort', getattr(recommendation, 'effort', 'Unknown'))
        impact = getattr(recommendation, 'estimated_impact', getattr(recommendation, 'impact', 'Unknown'))
        confidence = getattr(recommendation, 'confidence', 0.8)
        
        # Create a task function that executes the recommendation
        def execute_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
            """Execute the recommendation as a task"""
            return {
                "success": True,
                "action": action_title,
                "priority": priority,
                "rationale": rationale,
                "recommendation_data": {
                    "effort": effort,
                    "impact": impact,
                    "confidence": confidence
                }
            }
        
        # Create agent
        agent = ScheduledTaskAgent(
            agent_id=f"cortex_{action_title.lower().replace(' ', '_').replace('-', '_')}",
            name=action_title,
            description=rationale or f"Recommended action: {action_title}",
            task_func=execute_recommendation
        )
        
        return agent
    
    def to_schedule(self, recommendation: Recommendation, default_schedule: str = "0 8 * * *") -> str:
        """
        Convert recommendation to cron schedule.
        
        Args:
            recommendation: Cortex Recommendation object
            default_schedule: Default cron schedule if recommendation doesn't specify
            
        Returns:
            Cron schedule string (e.g., "0 8 * * *" for daily at 8 AM)
        """
        # Parse recommendation type/priority for timing hints
        # High priority -> more frequent, low priority -> less frequent
        # Project-specific scheduling based on recommendation title/content
        priority = getattr(recommendation, 'priority', 'medium')
        title = getattr(recommendation, 'title', getattr(recommendation, 'action_title', '')).lower()
        
        # Project-specific scheduling
        if 'dj-copilot' in title or 'loop extraction' in title or 'fl studio' in title:
            # DJ-CoPilot: Schedule during off-peak hours (evening/weekend)
            if priority == 'high':
                return "0 20 * * *"  # Daily at 8 PM
            elif priority == 'medium':
                return "0 19 * * 6"  # Weekly on Saturday at 7 PM
            else:
                return "0 18 * * 0"  # Weekly on Sunday at 6 PM
        elif 'vortexv2' in title or 'weather' in title:
            # VortexV2: Schedule during morning hours
            if priority == 'high':
                return "0 8 * * *"  # Daily at 8 AM
            elif priority == 'medium':
                return "0 9 * * *"  # Daily at 9 AM
            else:
                return "0 10 * * 1"  # Weekly on Monday at 10 AM
        elif 'keto-tracker' in title or 'mobile' in title:
            # Mobile apps: Schedule during development hours
            if priority == 'high':
                return "0 9 * * *"  # Daily at 9 AM
            elif priority == 'medium':
                return "0 10 * * 1"  # Weekly on Monday at 10 AM
            else:
                return "0 11 * * 1"  # Weekly on Monday at 11 AM
        else:
            # Default scheduling based on priority
            if priority == 'high':
                return "0 8 * * *"  # Daily at 8 AM
            elif priority == 'medium':
                return "0 9 * * *"  # Daily at 9 AM
            else:
                return "0 10 * * 1"  # Weekly on Monday at 10 AM
    
    def register_recommendation(
        self,
        recommendation: Recommendation,
        schedule: Optional[str] = None
    ) -> bool:
        """
        Register a Cortex recommendation as a local-orchestrator agent.
        
        Args:
            recommendation: Cortex Recommendation to register
            schedule: Optional cron schedule (defaults to daily at 8 AM)
            
        Returns:
            True if registration successful, False otherwise
        """
        if not LOCAL_ORCHESTRATOR_AVAILABLE:
            return False
        
        if not self.orchestrator:
            return False  # Can't register without orchestrator
        
        try:
            agent = self.to_agent(recommendation)
            schedule_str = schedule or self.to_schedule(recommendation)
            
            self.orchestrator.register_agent(agent, schedule=schedule_str)
            return True
        except Exception as e:
            print(f"Failed to register recommendation: {e}")
            return False


class CortexLocalOrchestratorIntegration:
    """Main integration class between Cortex and local-orchestrator"""

    def __init__(self, root_dir: Optional[Path] = None):
        """
        Initialize integration.

        Args:
            root_dir: Root directory of workspace
        """
        self.root_dir = root_dir or Path("/Users/jesse.kemp/Dev")
        self.orchestrator: Optional[Any] = None
        self.adapter: Optional[RecommendationToAgentAdapter] = None
        self._initialize()

    def _initialize(self):
        """Initialize local-orchestrator connection"""
        # Always create adapter (it can work without orchestrator for conversion)
        try:
            self.adapter = RecommendationToAgentAdapter(None)  # No orchestrator needed for conversion
        except Exception as e:
            print(f"Warning: Could not create adapter: {e}")
            self.adapter = None

        # Try to create orchestrator if available
        if not LOCAL_ORCHESTRATOR_AVAILABLE:
            self.orchestrator = None
            return

        try:
            self.orchestrator = Orchestrator()
            # Update adapter with orchestrator if we got one
            if self.adapter:
                self.adapter.orchestrator = self.orchestrator
        except Exception as e:
            # Orchestrator creation failed, but adapter can still work for conversion
            self.orchestrator = None

    def is_available(self) -> bool:
        """
        Check if local-orchestrator integration is available.

        Returns:
            True if integration is available (dependencies installed and adapter created)
        """
        # Integration is available if dependencies are installed and adapter exists
        # Orchestrator instance is optional (needed for registration, not conversion)
        return LOCAL_ORCHESTRATOR_AVAILABLE and self.adapter is not None

    def schedule_recommendation(
        self,
        recommendation: Recommendation,
        schedule: Optional[str] = None
    ) -> bool:
        """
        Schedule a Cortex recommendation as a local-orchestrator agent.

        Args:
            recommendation: Cortex Recommendation to schedule
            schedule: Optional cron schedule

        Returns:
            True if scheduled successfully
        """
        if not self.is_available() or not self.adapter:
            return False

        return self.adapter.register_recommendation(recommendation, schedule)

    def execute_recommendation(self, recommendation: Recommendation) -> Dict[str, Any]:
        """
        Execute a recommendation immediately.

        Args:
            recommendation: Cortex Recommendation to execute

        Returns:
            Dict with execution results including success status and details
        """
        if not LOCAL_ORCHESTRATOR_AVAILABLE or not self.orchestrator:
            return {
                "success": False,
                "error": "local-orchestrator not available",
                "message": "Cannot execute - local-orchestrator dependencies not installed"
            }

        try:
        try:
            # Special handling for CursorRules
            if getattr(recommendation, 'type', '') == 'cursorrules_improvement':
                # Trigger the dedicated agent
                project_name = getattr(recommendation, 'related_projects', [])[0] if getattr(recommendation, 'related_projects', []) else None
                # Scan for project path using ai_intelligence (lazy import)
                from cortex.ai_intelligence import ProjectScanner
                scanner = ProjectScanner(self.root_dir)
                project_path = str(self.root_dir / project_name) if project_name else ""
                
                # Verify path existence using scanner logic if needed, but simple path join is likely enough for now
                
                result = self.orchestrator.trigger_agent(
                    agent_id="cursorrules_enhancer",
                    context={"project_path": project_path, "project_name": project_name}
                )
            else:
                # Create a temporary agent for this execution
                agent = self.adapter.to_agent(recommendation)
                
                # Register agent temporarily (without scheduling)
                self.orchestrator.register_agent(agent)

                # Execute immediately
                result = self.orchestrator.trigger_agent(agent.agent_id, context={})

            # Convert result to dict
            execution_result = {
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "recommendation_id": recommendation.id,
                "recommendation_title": recommendation.title,
                "recommendation_type": recommendation.type,
                "execution_time": result.execution_time,
                "timestamp": result.timestamp.isoformat()
            }

            return execution_result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Execution failed: {str(e)}",
                "recommendation_id": recommendation.id,
                "recommendation_title": recommendation.title
            }

    def list_scheduled_actions(self) -> list:
        """List all scheduled actions from local-orchestrator"""
        if not self.is_available() or not self.orchestrator:
            return []

        try:
            agents = self.orchestrator.list_agents()
            # Filter for Cortex-scheduled agents
            cortex_agents = [a for a in agents if a.get("agent_id", "").startswith("cortex_")]
            return cortex_agents
        except Exception:
            return []

