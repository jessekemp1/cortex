"""System agent for Cortex V2 Prime Active Context Loop.

This agent runs the core "Active Context" loop:
1. Absorb environmental signals (Engine A)
2. Synthesize signals into context graph (Engine B)
3. Check for proactive interventions (Engine C)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import structlog
from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.models import AgentResult

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

# V2 Prime Engine imports
try:
    from cortex.engines.absorber import ContextAbsorber, create_default_absorber
    from cortex.engines.broker import ActionBroker
    from cortex.engines.synthesis import ContextGraph, SynthesisCore

    V2_PRIME_AVAILABLE = True
except ImportError as e:
    logger.warning("v2_prime_engines_not_available", error=str(e))
    V2_PRIME_AVAILABLE = False
    ContextAbsorber = None
    SynthesisCore = None
    ContextGraph = None
    ActionBroker = None


class ActiveContextAgent(BaseAgent):
    """System Agent: Runs every 30 seconds.

    Role: Executes the V2 Prime "Active Context" loop:
    - Engine A: Absorb signals from filesystem, shell, IDE
    - Engine B: Synthesize signals into context graph
    - Engine C: Check for proactive interventions
    """

    def __init__(self, root_dir: Path = None):
        """Initialize the Active Context agent.

        Args:
            root_dir: Root directory to monitor (defaults to /Users/jesse.kemp/Dev)
        """
        super().__init__(
            agent_id="system_active_context",
            name="Active Context Loop (V2 Prime)",
            description="Runs the active context absorption and synthesis loop",
            metadata=AgentMetadata(version="2.0.0", tags=["system", "v2-prime", "active-context"]),
        )

        if not V2_PRIME_AVAILABLE:
            logger.error("v2_prime_engines_not_available")
            self.absorber = None
            self.synthesis = None
            self.broker = None
            return

        # Set root directory
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = Path(root_dir)

        # Initialize Engine A: Context Absorber
        try:
            self.absorber = create_default_absorber(self.root_dir)
            # Start all signal sources
            self.absorber.start_all()
            logger.info("absorber_initialized", root_dir=str(self.root_dir))
        except Exception as e:
            logger.error("absorber_init_failed", error=str(e))
            self.absorber = None

        # Initialize Engine B: Synthesis Core
        try:
            graph = ContextGraph()
            self.synthesis = SynthesisCore(graph)
            logger.info("synthesis_initialized")
        except Exception as e:
            logger.error("synthesis_init_failed", error=str(e))
            self.synthesis = None

        # Initialize Engine C: Action Broker
        try:
            self.broker = ActionBroker()
            logger.info("broker_initialized")
        except Exception as e:
            logger.error("broker_init_failed", error=str(e))
            self.broker = None

        # Wire up callbacks: When absorber gets signals, process them
        if self.absorber and self.synthesis:

            def on_signal(signal):
                """Callback when absorber detects a signal."""
                try:
                    affected_nodes = self.synthesis.process_signal(signal)
                    logger.debug(
                        "signal_processed",
                        signal_id=signal.id,
                        signal_type=signal.type.value,
                        nodes_affected=len(affected_nodes),
                    )
                except Exception as e:
                    logger.error("signal_processing_error", signal_id=signal.id, error=str(e))

            self.absorber.register_callback(on_signal)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute one cycle of the Active Context loop.

        Args:
            context: Execution context (optional)

        Returns:
            AgentResult with summary of processed signals and interventions
        """
        if not V2_PRIME_AVAILABLE:
            return AgentResult(
                success=False,
                message="V2 Prime engines not available",
                data={"error": "engines_not_loaded"},
            )

        if not self.absorber or not self.synthesis or not self.broker:
            return AgentResult(
                success=False,
                message="V2 Prime engines not initialized",
                data={
                    "absorber": self.absorber is not None,
                    "synthesis": self.synthesis is not None,
                    "broker": self.broker is not None,
                },
            )

        summary = {
            "signals_absorbed": 0,
            "signals_processed": 0,
            "interventions_pending": 0,
            "graph_stats": {},
        }

        try:
            # Step 1: Absorb signals (Engine A)
            signals = self.absorber.absorb()
            summary["signals_absorbed"] = len(signals)

            # Signals are automatically processed via callback,
            # but we also manually process any buffered signals
            buffered = self.absorber.get_buffer()
            for signal in buffered:
                try:
                    self.synthesis.process_signal(signal)
                    summary["signals_processed"] += 1
                except Exception as e:
                    logger.error("signal_processing_error", signal_id=signal.id, error=str(e))

            # Step 2: Check for interventions (Engine C)
            pending = self.broker.get_pending()
            summary["interventions_pending"] = len(pending)

            # Step 3: Get graph stats (Engine B)
            if self.synthesis and self.synthesis.graph:
                summary["graph_stats"] = self.synthesis.graph.get_stats()

            # Log high-level summary
            if summary["signals_absorbed"] > 0 or summary["interventions_pending"] > 0:
                logger.info(
                    "active_context_cycle",
                    signals=summary["signals_absorbed"],
                    processed=summary["signals_processed"],
                    interventions=summary["interventions_pending"],
                )

            return AgentResult(
                success=True,
                message=f"Absorbed {summary['signals_absorbed']} signals, {summary['interventions_pending']} interventions pending",
                data=summary,
            )

        except Exception as e:
            logger.error("active_context_cycle_error", error=str(e))
            return AgentResult(
                success=False,
                message=f"Active context cycle failed: {str(e)}",
                data=summary,
            )

    def shutdown(self):
        """Shutdown the agent and stop signal sources."""
        if self.absorber:
            try:
                self.absorber.stop_all()
                logger.info("absorber_stopped")
            except Exception as e:
                logger.error("absorber_shutdown_error", error=str(e))
