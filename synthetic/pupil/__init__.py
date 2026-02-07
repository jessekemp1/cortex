#!/usr/bin/env python3
"""
Pupil — Behavioral Agent Simulation for Canadian Financial Markets.

Builds on SynthFinServ's statistically-grounded generation engine to create
agent personas that make behavioral predictions validated through a 9-layer
trust flywheel.

Architecture:
    SynthFinServ profiles → PersonaAgent (behavioral model + state machine)
    → SimulationEngine (time-stepping) → MarketAnalyzer (intelligence outputs)
    → Trust Layer (7+2 flywheel validation)
"""

__version__ = "0.1.0"

from .market_env import (
    CompetitionEvent,
    EventType,
    MarketEnvironment,
    build_timeline,
)
from .segment_models import (
    SEGMENT_MODELS,
    SegmentBehavior,
    get_behavior,
)
from .persona import (
    Action,
    ActionType,
    LifecycleState,
    PersonaAgent,
)
from .simulation import (
    SimulationEngine,
    SimulationResult,
    StepResult,
)
from .analysis import (
    AnalysisReport,
    MarketAnalyzer,
    MigrationFlow,
    SegmentAnalysis,
)

__all__ = [
    # Market Environment
    "MarketEnvironment",
    "CompetitionEvent",
    "EventType",
    "build_timeline",
    # Segment Models
    "SegmentBehavior",
    "SEGMENT_MODELS",
    "get_behavior",
    # Persona
    "PersonaAgent",
    "Action",
    "ActionType",
    "LifecycleState",
    # Simulation
    "SimulationEngine",
    "SimulationResult",
    "StepResult",
    # Analysis
    "MarketAnalyzer",
    "AnalysisReport",
    "MigrationFlow",
    "SegmentAnalysis",
]
