"""
Bandwidth Research Module - Human-AI Collaboration Optimization

This module implements instrumentation and measurement for human-AI bandwidth research:
- Session handoff capture (context preservation across sessions)
- Bandwidth meter (signal quality, compression ratio, latency)
- Prediction tracker (confidence calibration by domain)

Storage: ~/.cortex/research/bandwidth/
"""

from intelligence.bandwidth.handoff_capture import (
    SessionHandoff,
    WorkstreamType,
    capture_handoff,
    get_recent_handoffs,
)
from intelligence.bandwidth.meter import (
    BandwidthMeter,
    BandwidthMetrics,
    get_session_metrics,
)
from intelligence.bandwidth.predictions import (
    DomainCalibration,
    PredictionTracker,
    record_outcome,
    record_prediction,
)

__all__ = [
    # Handoff Capture
    "SessionHandoff",
    "WorkstreamType",
    "capture_handoff",
    "get_recent_handoffs",
    # Bandwidth Meter
    "BandwidthMeter",
    "BandwidthMetrics",
    "get_session_metrics",
    # Prediction Tracker
    "PredictionTracker",
    "DomainCalibration",
    "record_prediction",
    "record_outcome",
]
