"""
Engine C: The Action Broker

Proactive intervention based on synthesized context.
This is the OUTPUT layer of Cortex V2 Prime.

Instead of waiting for `cortex next`, the Broker emits InterventionEvents when:
- A known error pattern is detected in logs
- Work drifts from the active Plan
- A blocking dependency is identified
- Context switch detected
- High-confidence recommendation available
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class InterventionType(Enum):
    """Types of proactive interventions."""
    ERROR_PATTERN_DETECTED = "error_pattern_detected"
    WORK_DRIFT = "work_drift"
    BLOCKER_IDENTIFIED = "blocker_identified"
    CONTEXT_SWITCH = "context_switch"
    RECOMMENDATION_AVAILABLE = "recommendation_available"
    LEARNING_INSIGHT = "learning_insight"
    HEALTH_ALERT = "health_alert"


class Severity(Enum):
    """Intervention severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SuggestedAction:
    """Suggested action for an intervention."""
    title: str
    rationale: str
    confidence: float
    steps: Optional[List[str]] = None
    reference_id: Optional[str] = None  # pattern:id, lesson:id, etc.

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "steps": self.steps,
            "reference_id": self.reference_id,
        }


@dataclass
class Intervention:
    """A proactive intervention from Cortex."""
    id: str
    type: InterventionType
    severity: Severity
    title: str
    description: str
    context: Dict[str, Any]
    suggested_action: Optional[SuggestedAction] = None
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    suppressed_until: Optional[datetime] = None
    source_engine: str = "broker"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "suggested_action": self.suggested_action.to_dict() if self.suggested_action else None,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "suppressed_until": self.suppressed_until.isoformat() if self.suppressed_until else None,
            "source_engine": self.source_engine,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Intervention":
        return cls(
            id=data["id"],
            type=InterventionType(data["type"]),
            severity=Severity(data["severity"]),
            title=data["title"],
            description=data["description"],
            context=data["context"],
            suggested_action=SuggestedAction(**data["suggested_action"]) if data.get("suggested_action") else None,
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            acknowledged=data.get("acknowledged", False),
            suppressed_until=datetime.fromisoformat(data["suppressed_until"]) if data.get("suppressed_until") else None,
            source_engine=data.get("source_engine", "broker"),
        )

    def to_iap_message(self, target_agent: Dict) -> Dict:
        """Convert to IAP intervention message."""
        return {
            "protocol": "Cortex-IAP/1.0",
            "message_id": f"msg:intervention-{self.id}",
            "timestamp": self.timestamp.isoformat(),
            "message_type": "intervention",
            "source_agent": {
                "id": "cortex",
                "role": "orchestrator"
            },
            "target_agent": target_agent,
            "context_snapshot": self.context,
            "payload": {
                "intervention_type": self.type.value,
                "severity": self.severity.value,
                "instruction": self.description,
                "suggested_fix": self.suggested_action.title if self.suggested_action else None,
                "confidence": self.suggested_action.confidence if self.suggested_action else 0.5,
                "constraints": []
            }
        }


class ActionBroker:
    """
    Engine C: Proactive intervention system.
    
    This is the output layer of Cortex V2 Prime.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".cortex" / "interventions.json"
        self.interventions: List[Intervention] = []
        self._callbacks: List[Callable[[Intervention], None]] = []
        self._suppression_rules: Dict[str, datetime] = {}  # type -> suppressed_until
        self._load()

    def _load(self) -> None:
        """Load pending interventions from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for item in data:
                        intervention = Intervention.from_dict(item)
                        self.interventions.append(intervention)
                logger.info(f"Loaded {len(self.interventions)} interventions")
            except Exception as e:
                logger.error(f"Failed to load interventions: {e}")

    def _save(self) -> None:
        """Save interventions to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump([i.to_dict() for i in self.interventions], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save interventions: {e}")

    def register_callback(self, callback: Callable[[Intervention], None]) -> None:
        """Register callback for new interventions."""
        self._callbacks.append(callback)

    def emit(self, intervention: Intervention) -> None:
        """Emit a new intervention."""
        # Check suppression
        if self._is_suppressed(intervention.type):
            logger.debug(f"Intervention suppressed: {intervention.type}")
            return

        self.interventions.append(intervention)
        self._save()
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(intervention)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        logger.info(f"Intervention emitted: [{intervention.severity.value}] {intervention.title}")

    def _is_suppressed(self, intervention_type: InterventionType) -> bool:
        """Check if an intervention type is suppressed."""
        suppressed_until = self._suppression_rules.get(intervention_type.value)
        if suppressed_until and datetime.now() < suppressed_until:
            return True
        return False

    def create_intervention(
        self,
        intervention_type: InterventionType,
        severity: Severity,
        title: str,
        description: str,
        context: Dict[str, Any],
        suggested_action: Optional[SuggestedAction] = None
    ) -> Intervention:
        """Create and emit an intervention."""
        intervention = Intervention(
            id=uuid.uuid4().hex[:8],
            type=intervention_type,
            severity=severity,
            title=title,
            description=description,
            context=context,
            suggested_action=suggested_action,
        )
        self.emit(intervention)
        return intervention

    def get_pending(self) -> List[Intervention]:
        """Get unacknowledged interventions."""
        now = datetime.now()
        return [
            i for i in self.interventions
            if not i.acknowledged and (
                i.suppressed_until is None or i.suppressed_until < now
            )
        ]

    def get_by_severity(self, severity: Severity) -> List[Intervention]:
        """Get interventions by severity."""
        return [i for i in self.interventions if i.severity == severity]

    def get_by_type(self, intervention_type: InterventionType) -> List[Intervention]:
        """Get interventions by type."""
        return [i for i in self.interventions if i.type == intervention_type]

    def acknowledge(self, intervention_id: str) -> bool:
        """Mark an intervention as acknowledged."""
        for intervention in self.interventions:
            if intervention.id == intervention_id:
                intervention.acknowledged = True
                self._save()
                logger.info(f"Intervention acknowledged: {intervention_id}")
                return True
        return False

    def suppress(self, intervention_id: str, hours: int = 24) -> bool:
        """Suppress an intervention for a duration."""
        for intervention in self.interventions:
            if intervention.id == intervention_id:
                intervention.suppressed_until = datetime.now() + timedelta(hours=hours)
                self._save()
                logger.info(f"Intervention suppressed for {hours}h: {intervention_id}")
                return True
        return False

    def suppress_type(self, intervention_type: InterventionType, hours: int = 24) -> None:
        """Suppress all interventions of a type."""
        self._suppression_rules[intervention_type.value] = datetime.now() + timedelta(hours=hours)
        logger.info(f"Suppressed {intervention_type.value} for {hours}h")

    def clear_suppression(self, intervention_type: InterventionType) -> None:
        """Clear suppression for an intervention type."""
        if intervention_type.value in self._suppression_rules:
            del self._suppression_rules[intervention_type.value]

    # === Trigger Methods for Specific Intervention Types ===

    def trigger_error_pattern(
        self,
        pattern_id: str,
        lesson_id: str,
        relevant_files: List[str],
        description: str,
        project: Optional[str] = None,
    ) -> Intervention:
        """Trigger an error pattern intervention."""
        return self.create_intervention(
            intervention_type=InterventionType.ERROR_PATTERN_DETECTED,
            severity=Severity.HIGH,
            title=f"Error pattern detected: {pattern_id}",
            description=description,
            context={
                "pattern_id": pattern_id,
                "lesson_id": lesson_id,
                "relevant_files": relevant_files,
                "project": project,
            },
            suggested_action=SuggestedAction(
                title="Apply lesson to prevent issue",
                rationale=f"This pattern has caused issues before. See {lesson_id}",
                confidence=0.85,
                reference_id=lesson_id,
            ),
        )

    def trigger_work_drift(
        self,
        active_goal_id: str,
        expected_files: List[str],
        actual_files: List[str],
        drift_description: str,
        project: Optional[str] = None,
    ) -> Intervention:
        """Trigger a work drift intervention."""
        return self.create_intervention(
            intervention_type=InterventionType.WORK_DRIFT,
            severity=Severity.MEDIUM,
            title="Work drift detected",
            description=drift_description,
            context={
                "active_goal_id": active_goal_id,
                "expected_files": expected_files,
                "actual_files": actual_files,
                "project": project,
            },
            suggested_action=SuggestedAction(
                title="Review current work against active goal",
                rationale="Work appears to have drifted from the planned scope",
                confidence=0.75,
                reference_id=active_goal_id,
            ),
        )

    def trigger_blocker(
        self,
        goal_id: str,
        blocker_description: str,
        blocking_dependencies: List[str],
        alternatives: Optional[List[str]] = None,
        project: Optional[str] = None,
    ) -> Intervention:
        """Trigger a blocker identified intervention."""
        return self.create_intervention(
            intervention_type=InterventionType.BLOCKER_IDENTIFIED,
            severity=Severity.HIGH,
            title="Blocker identified",
            description=blocker_description,
            context={
                "goal_id": goal_id,
                "blocking_dependencies": blocking_dependencies,
                "alternatives": alternatives or [],
                "project": project,
            },
            suggested_action=SuggestedAction(
                title="Consider alternative approach or escalate",
                rationale="Current path is blocked. Review alternatives.",
                confidence=0.80,
                steps=alternatives,
            ),
        )

    def trigger_context_switch(
        self,
        from_project: str,
        to_project: str,
        relevant_patterns: List[str],
        relevant_lessons: List[str],
    ) -> Intervention:
        """Trigger a context switch intervention."""
        return self.create_intervention(
            intervention_type=InterventionType.CONTEXT_SWITCH,
            severity=Severity.INFO,
            title=f"Context switch: {from_project} -> {to_project}",
            description=f"Switching from {from_project} to {to_project}. Relevant context attached.",
            context={
                "from_project": from_project,
                "to_project": to_project,
                "relevant_patterns": relevant_patterns,
                "relevant_lessons": relevant_lessons,
            },
            suggested_action=SuggestedAction(
                title=f"Review {to_project} context",
                rationale="Context switch detected. Relevant patterns and lessons provided.",
                confidence=0.90,
            ),
        )

    def trigger_recommendation(
        self,
        recommendation_id: str,
        title: str,
        rationale: str,
        confidence: float,
        project: Optional[str] = None,
        steps: Optional[List[str]] = None,
    ) -> Intervention:
        """Trigger a recommendation available intervention."""
        return self.create_intervention(
            intervention_type=InterventionType.RECOMMENDATION_AVAILABLE,
            severity=Severity.MEDIUM if confidence > 0.8 else Severity.LOW,
            title=f"Recommendation: {title}",
            description=rationale,
            context={
                "recommendation_id": recommendation_id,
                "project": project,
            },
            suggested_action=SuggestedAction(
                title=title,
                rationale=rationale,
                confidence=confidence,
                steps=steps,
                reference_id=recommendation_id,
            ),
        )

    def trigger_health_alert(
        self,
        project: str,
        health_score: float,
        issues: List[str],
        recommendations: List[str],
    ) -> Intervention:
        """Trigger a health alert intervention."""
        severity = Severity.CRITICAL if health_score < 30 else Severity.HIGH if health_score < 50 else Severity.MEDIUM
        
        return self.create_intervention(
            intervention_type=InterventionType.HEALTH_ALERT,
            severity=severity,
            title=f"Project health alert: {project} ({health_score:.0f}/100)",
            description=f"Project health has degraded. Issues: {', '.join(issues[:3])}",
            context={
                "project": project,
                "health_score": health_score,
                "issues": issues,
            },
            suggested_action=SuggestedAction(
                title="Address project health issues",
                rationale=f"Health score is {health_score:.0f}/100",
                confidence=0.85,
                steps=recommendations,
            ),
        )

    def trigger_learning_insight(
        self,
        insight_type: str,
        insight: str,
        data: Dict[str, Any],
    ) -> Intervention:
        """Trigger a learning insight intervention."""
        return self.create_intervention(
            intervention_type=InterventionType.LEARNING_INSIGHT,
            severity=Severity.INFO,
            title=f"Learning insight: {insight_type}",
            description=insight,
            context={
                "insight_type": insight_type,
                "data": data,
            },
        )

    def get_status(self) -> Dict[str, Any]:
        """Get broker status."""
        pending = self.get_pending()
        
        by_severity = {}
        for sev in Severity:
            by_severity[sev.value] = len([i for i in pending if i.severity == sev])

        by_type = {}
        for itype in InterventionType:
            by_type[itype.value] = len([i for i in pending if i.type == itype])

        return {
            "total_interventions": len(self.interventions),
            "pending_count": len(pending),
            "by_severity": by_severity,
            "by_type": by_type,
            "suppression_rules": {k: v.isoformat() for k, v in self._suppression_rules.items()},
        }

    def cleanup_old(self, days: int = 30) -> int:
        """Remove acknowledged interventions older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)
        original_count = len(self.interventions)
        
        self.interventions = [
            i for i in self.interventions
            if not i.acknowledged or i.timestamp > cutoff
        ]
        
        removed = original_count - len(self.interventions)
        if removed > 0:
            self._save()
            logger.info(f"Cleaned up {removed} old interventions")
        
        return removed
