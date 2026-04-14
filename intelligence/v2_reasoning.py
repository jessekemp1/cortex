"""
Cortex V2 Reasoning Layer — graph lessons to ActionBroker interventions.

Pure rule engine, no LLM. Connects LESSON/PATTERN graph nodes
to proactive recommendations via confidence threshold.
"""

from __future__ import annotations

from typing import Any, Dict, List  # List used in evaluate return type; Any in __init__


class V2ReasoningLayer:
    """Connects graph lessons -> ActionBroker interventions. Pure rule engine, no LLM."""

    def __init__(self, synthesis: Any):
        self._synthesis = synthesis

    def evaluate(self, context: str, project: str) -> List[Dict]:
        """Query graph for LESSON/PATTERN nodes, generate interventions."""
        try:
            results = self._synthesis.query(context)
            interventions = []
            for node in results.get("nodes", []):
                if node.get("type") in ("LESSON", "PATTERN") and node.get("confidence", 0) > 0.6:
                    interventions.append(
                        {
                            "type": "recommendation",
                            "source": "v2_reasoning",
                            "lesson": node.get("name", ""),
                            "project": project,
                            "confidence": node.get("confidence", 0),
                        }
                    )
            return interventions
        except Exception:
            return []
