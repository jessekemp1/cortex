"""
Pupil: Statistically-grounded agent personas for Canadian financial market analysis.

Pupil combines SynthFinServ's statistical fidelity with behavioral intelligence to create
validated agent-based predictions about Canadian financial markets.

Key Features:
- Statistically faithful Canadian financial consumer populations
- Behavioral agency with segment-specific decision models
- Temporal simulation with market scenario injection
- 9-layer flywheel validation (L1-L7 + L8 behavioral + L9 temporal)
- Privacy-proven outputs (DCR/NNDR/MIA)

Architecture:
    Statistical Foundation (SynthFinServ) + Behavioral Intelligence (Agent-based)
    = "Predictions You Can Prove to a Regulator"

Extraction-readiness: Pupil has low coupling to cortex core (single CustomerProfile
import from synthetic.schemas, flywheel treats pupil as optional via try/except).
Can be extracted to a standalone package if an external consumer emerges.
"""

from .persona import PersonaAgent
from .schemas import (
    Province,
    CustomerSegment,
    ProductType,
    CustomerProfile,
    AgentState,
    BehavioralAction,
    BehavioralActionType,
    BehavioralProfile,
    BehavioralSequence,
    Goal,
    GoalType,
    PupilRequest,
    PupilResult,
)
from .segment_models import SegmentBehavior, get_behavior, SEGMENT_MODELS
from .market_env import MarketEnvironment, CompetitionEvent, EventType, build_timeline
from .simulation import SimulationEngine, SimulationResult, StepResult
from .analysis import MarketAnalyzer, AnalysisReport
from .bridge import PupilBridge
from .behavioral_fidelity import BehavioralFidelityValidator, FidelityReport
from .temporal_coherence import TemporalCoherenceValidator, CoherenceReport
from .calibrator import SegmentCalibrator
from .explainer import DecisionExplainer, Explanation, Factor

__version__ = "0.1.0"
__all__ = [
    # Vendored types (standalone use)
    "Province",
    "CustomerSegment",
    "ProductType",
    "CustomerProfile",

    # Agent
    "PersonaAgent",

    # Schemas
    "AgentState",
    "BehavioralAction",
    "BehavioralActionType",
    "BehavioralProfile",
    "BehavioralSequence",
    "Goal",
    "GoalType",
    "PupilRequest",
    "PupilResult",

    # Segment Models
    "SegmentBehavior",
    "get_behavior",
    "SEGMENT_MODELS",

    # Market Environment
    "MarketEnvironment",
    "CompetitionEvent",
    "EventType",
    "build_timeline",

    # Simulation
    "SimulationEngine",
    "SimulationResult",
    "StepResult",

    # Analysis
    "MarketAnalyzer",
    "AnalysisReport",

    # Bridge
    "PupilBridge",

    # Validators
    "BehavioralFidelityValidator",
    "FidelityReport",
    "TemporalCoherenceValidator",
    "CoherenceReport",

    # Calibrator
    "SegmentCalibrator",

    # Explainer
    "DecisionExplainer",
    "Explanation",
    "Factor",
]
