"""
Cortex V2 Prime: 3-Engine Active Model

Engine A: Context Absorber (Input) - Real-time signal ingestion
Engine B: Synthesis Core (Processing) - Graph-based context synthesis
Engine C: Action Broker (Output) - Proactive interventions

Extended with:
- Claude Session Absorber: Real-time interaction capture from Claude Code
- Interaction Learner: Automatic learning from interaction patterns
"""

try:
    from cortex.engines.absorber import ContextAbsorber, Signal, SignalType
    from cortex.engines.augmentation_engine import AugmentationEngine, AugmentedIdea
    from cortex.engines.broker import (
        ActionBroker,
        Intervention,
        InterventionType,
        Severity,
    )
    from cortex.engines.claude_session_absorber import (
        ClaudeSessionSource,
        InteractionPattern,
        InteractionSignal,
        InteractionSignalType,
    )
    from cortex.engines.interaction_learner import (
        ImplicitOutcome,
        InteractionLearner,
        LearningInsight,
    )
    from cortex.engines.pattern_surfacer import PatternSurfacer, SurfacedPattern
    from cortex.engines.synthesis import (
        ContextGraph,
        Edge,
        EdgeType,
        Node,
        NodeType,
        SynthesisCore,
    )
    from cortex.engines.universal_signal_bus import UniversalSignalBus
    from cortex.engines.workstream_orchestrator import (
        WorkspaceSignal,
        WorkstreamOrchestrator,
        WorkstreamPhase,
        SignalSource,
        TrustLevel,
    )
except ImportError:
    # Fallback for direct execution
    from .absorber import ContextAbsorber, Signal, SignalType
    from .augmentation_engine import AugmentationEngine, AugmentedIdea
    from .broker import ActionBroker, Intervention, InterventionType, Severity
    from .claude_session_absorber import (
        ClaudeSessionSource,
        InteractionPattern,
        InteractionSignal,
        InteractionSignalType,
    )
    from .interaction_learner import (
        ImplicitOutcome,
        InteractionLearner,
        LearningInsight,
    )
    from .pattern_surfacer import PatternSurfacer, SurfacedPattern
    from .synthesis import ContextGraph, Edge, EdgeType, Node, NodeType, SynthesisCore
    from .universal_signal_bus import UniversalSignalBus
    from .workstream_orchestrator import (
        WorkspaceSignal,
        WorkstreamOrchestrator,
        WorkstreamPhase,
        SignalSource,
        TrustLevel,
    )

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
    # Claude Session Integration
    "ClaudeSessionSource",
    "InteractionSignal",
    "InteractionSignalType",
    "InteractionPattern",
    # Interaction Learning
    "InteractionLearner",
    "ImplicitOutcome",
    "LearningInsight",
    # Sprint 2: Universal Signal Bus
    "UniversalSignalBus",
    # Sprint 2: Augmentation Engine
    "AugmentationEngine",
    "AugmentedIdea",
    # Sprint 2: Pattern Surfacer
    "PatternSurfacer",
    "SurfacedPattern",
    # Workstream Orchestrator (re-exported for convenience)
    "WorkspaceSignal",
    "WorkstreamOrchestrator",
    "WorkstreamPhase",
    "SignalSource",
    "TrustLevel",
]
