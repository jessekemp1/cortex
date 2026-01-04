"""
Cortex V2 Prime: 3-Engine Active Model

Engine A: Context Absorber (Input) - Real-time signal ingestion
Engine B: Synthesis Core (Processing) - Graph-based context synthesis  
Engine C: Action Broker (Output) - Proactive interventions
"""

try:
    from cortex.engines.absorber import ContextAbsorber, Signal, SignalType
    from cortex.engines.synthesis import SynthesisCore, ContextGraph, Node, NodeType, Edge, EdgeType
    from cortex.engines.broker import ActionBroker, Intervention, InterventionType, Severity
except ImportError:
    # Fallback for direct execution
    from .absorber import ContextAbsorber, Signal, SignalType
    from .synthesis import SynthesisCore, ContextGraph, Node, NodeType, Edge, EdgeType
    from .broker import ActionBroker, Intervention, InterventionType, Severity

__all__ = [
    # Engine A
    "ContextAbsorber",
    "Signal", 
    "SignalType",
    # Engine B
    "SynthesisCore",
    "ContextGraph",
    "Node",
    "NodeType",
    "Edge",
    "EdgeType",
    # Engine C
    "ActionBroker",
    "Intervention",
    "InterventionType",
    "Severity",
]
