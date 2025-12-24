"""
Alert Adapter for bridging Layer 3 Alert format to Layer 4 Alert format.

Converts alerts from the Warning System (Layer 3) to the format expected
by the Smart Recommendation Generator (Layer 4).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List
import uuid


@dataclass
class AdaptedAlert:
    """Layer 4 compatible alert format."""
    id: str
    type: str
    severity: str
    message: str
    project_id: str
    context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_layer3_alert(cls, layer3_alert) -> "AdaptedAlert":
        """
        Convert a Layer 3 Alert to Layer 4 format.

        Args:
            layer3_alert: Alert from intelligence.monitoring.alert_generator

        Returns:
            AdaptedAlert in Layer 4 format
        """
        # Generate unique ID
        alert_id = str(uuid.uuid4())

        # Convert AlertType enum to string
        alert_type = layer3_alert.alert_type.value if hasattr(layer3_alert.alert_type, 'value') else str(layer3_alert.alert_type)

        # Convert AlertSeverity enum to string
        severity = layer3_alert.severity.value if hasattr(layer3_alert.severity, 'value') else str(layer3_alert.severity)

        # Combine title and message for richer context
        full_message = f"{layer3_alert.title}\n{layer3_alert.message}"

        # Build context dict with all Layer 3 metadata
        context = {
            "title": layer3_alert.title,
            "metric_type": layer3_alert.metric_type,
            "created_at": layer3_alert.created_at.isoformat() if isinstance(layer3_alert.created_at, datetime) else str(layer3_alert.created_at),
            **layer3_alert.metadata  # Include all metadata from Layer 3
        }

        return cls(
            id=alert_id,
            type=alert_type,
            severity=severity,
            message=full_message,
            project_id=layer3_alert.project,
            context=context
        )


def adapt_alerts(layer3_alerts: List) -> List[AdaptedAlert]:
    """
    Convert a list of Layer 3 alerts to Layer 4 format.

    Args:
        layer3_alerts: List of Alert objects from Layer 3

    Returns:
        List of AdaptedAlert objects in Layer 4 format
    """
    return [AdaptedAlert.from_layer3_alert(alert) for alert in layer3_alerts]


def adapt_alert(layer3_alert) -> AdaptedAlert:
    """
    Convert a single Layer 3 alert to Layer 4 format.

    Args:
        layer3_alert: Alert object from Layer 3

    Returns:
        AdaptedAlert in Layer 4 format
    """
    return AdaptedAlert.from_layer3_alert(layer3_alert)
