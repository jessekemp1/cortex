"""
Bandwidth Research Module - Human-AI Collaboration Optimization

This module implements instrumentation and measurement for human-AI bandwidth research:
- Session handoff capture (context preservation across sessions)
- Bandwidth meter (signal quality, compression ratio, latency)
- Prediction tracker (confidence calibration by domain)

Storage: ~/.cortex/research/bandwidth/
"""

from intelligence.bandwidth.baseline_report import generate_baseline_report
from intelligence.bandwidth.contracts import (
    ContractMetricsStore,
    ContractSessionMetrics,
)
from intelligence.bandwidth.event_adapter import (
    normalize_claude_event,
    normalize_codex_event,
)
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
from intelligence.bandwidth.queue_slo import check_queue_slo

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
    # Event Adapter
    "normalize_claude_event",
    "normalize_codex_event",
    # Metric contracts
    "ContractMetricsStore",
    "ContractSessionMetrics",
    "check_queue_slo",
    "generate_baseline_report",
    # Prediction Tracker
    "PredictionTracker",
    "DomainCalibration",
    "record_prediction",
    "record_outcome",
]
