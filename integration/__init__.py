"""Integration modules for Cortex with external systems"""

from .local_orchestrator import (
    LOCAL_ORCHESTRATOR_AVAILABLE,
    CortexLocalOrchestratorIntegration,
    RecommendationToAgentAdapter,
)

__all__ = [
    "LOCAL_ORCHESTRATOR_AVAILABLE",
    "CortexLocalOrchestratorIntegration",
    "RecommendationToAgentAdapter",
]
