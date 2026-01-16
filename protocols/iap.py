"""
Inter-Agent Protocol (IAP) Handler

Enables structured communication between AI agents and Cortex.

Protocol Version: Cortex-IAP/1.0

Message Types:
- handoff: Transfer work context between agents
- intervention: Proactive notification from Cortex
- query: Request context/recommendation
- response: Answer to query
- ack: Acknowledge intervention
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "Cortex-IAP/1.0"


class MessageType(Enum):
    """Types of IAP messages."""

    HANDOFF = "handoff"
    INTERVENTION = "intervention"
    QUERY = "query"
    RESPONSE = "response"
    ACK = "ack"


class AgentRole(Enum):
    """Roles that agents can have."""

    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    ORCHESTRATOR = "orchestrator"
    TESTER = "tester"
    DOCUMENTER = "documenter"


@dataclass
class Agent:
    """Agent identity."""

    id: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "role": self.role.value,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Agent":
        return cls(
            id=data["id"],
            role=AgentRole(data["role"]),
            capabilities=data.get("capabilities", []),
        )


@dataclass
class ContextSnapshot:
    """Snapshot of current context for handoff."""

    active_goal_id: Optional[str] = None
    active_project: Optional[str] = None
    relevant_files: List[str] = field(default_factory=list)
    memory_refs: List[str] = field(default_factory=list)  # pattern:id, lesson:id
    working_directory: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "active_goal_id": self.active_goal_id,
            "active_project": self.active_project,
            "relevant_files": self.relevant_files,
            "memory_refs": self.memory_refs,
            "working_directory": self.working_directory,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ContextSnapshot":
        return cls(
            active_goal_id=data.get("active_goal_id"),
            active_project=data.get("active_project"),
            relevant_files=data.get("relevant_files", []),
            memory_refs=data.get("memory_refs", []),
            working_directory=data.get("working_directory"),
            session_id=data.get("session_id"),
        )


@dataclass
class IAPMessage:
    """Inter-Agent Protocol message."""

    protocol: str = PROTOCOL_VERSION
    message_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: MessageType = MessageType.QUERY
    source_agent: Optional[Agent] = None
    target_agent: Optional[Agent] = None
    context_snapshot: Optional[ContextSnapshot] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.message_id:
            self.message_id = f"msg:{self.message_type.value}-{uuid.uuid4().hex[:8]}"
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)

    def to_dict(self) -> Dict:
        return {
            "protocol": self.protocol,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type.value,
            "source_agent": self.source_agent.to_dict() if self.source_agent else None,
            "target_agent": self.target_agent.to_dict() if self.target_agent else None,
            "context_snapshot": (
                self.context_snapshot.to_dict() if self.context_snapshot else None
            ),
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict) -> "IAPMessage":
        """Parse IAP message from dictionary."""
        return cls(
            protocol=data.get("protocol", PROTOCOL_VERSION),
            message_id=data.get("message_id", ""),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if data.get("timestamp")
                else datetime.now()
            ),
            message_type=MessageType(data.get("message_type", "query")),
            source_agent=(
                Agent.from_dict(data["source_agent"]) if data.get("source_agent") else None
            ),
            target_agent=(
                Agent.from_dict(data["target_agent"]) if data.get("target_agent") else None
            ),
            context_snapshot=(
                ContextSnapshot.from_dict(data["context_snapshot"])
                if data.get("context_snapshot")
                else None
            ),
            payload=data.get("payload", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "IAPMessage":
        return cls.from_dict(json.loads(json_str))


class IAPHandler:
    """
    Handler for Inter-Agent Protocol messages.

    Routes messages between agents and Cortex engines.
    """

    def __init__(self, synthesis_core=None, action_broker=None):
        self.synthesis = synthesis_core
        self.broker = action_broker
        self.registered_agents: Dict[str, Agent] = {}
        self._message_history: List[IAPMessage] = []

        # Register Cortex as orchestrator
        self.cortex_agent = Agent(
            id="cortex",
            role=AgentRole.ORCHESTRATOR,
            capabilities=["context_retrieval", "recommendation", "memory", "learning"],
        )

    def register_agent(self, agent: Agent) -> None:
        """Register an agent for communication."""
        self.registered_agents[agent.id] = agent
        logger.info(f"Registered agent: {agent.id} ({agent.role.value})")

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self.registered_agents:
            del self.registered_agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get a registered agent."""
        if agent_id == "cortex":
            return self.cortex_agent
        return self.registered_agents.get(agent_id)

    def handle_message(self, message: IAPMessage) -> IAPMessage:
        """
        Handle an incoming IAP message.

        Returns response message.
        """
        self._message_history.append(message)
        logger.info(
            f"Handling IAP message: {message.message_type.value} from {message.source_agent.id if message.source_agent else 'unknown'}"
        )

        try:
            if message.message_type == MessageType.QUERY:
                return self._handle_query(message)
            elif message.message_type == MessageType.HANDOFF:
                return self._handle_handoff(message)
            elif message.message_type == MessageType.ACK:
                return self._handle_ack(message)
            elif message.message_type == MessageType.INTERVENTION:
                return self._handle_intervention(message)
            else:
                return self._error_response(
                    message, f"Unknown message type: {message.message_type}"
                )
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._error_response(message, str(e))

    def _handle_query(self, message: IAPMessage) -> IAPMessage:
        """Handle a query message."""
        query = message.payload.get("query", "")
        query_type = message.payload.get("query_type", "context")
        project = message.context_snapshot.active_project if message.context_snapshot else None

        result = {}

        if query_type == "context" and self.synthesis:
            result = self.synthesis.query(query, {"project": project})
        elif query_type == "graph" and self.synthesis:
            node_type = message.payload.get("node_type")
            if node_type:
                from cortex.engines.synthesis import NodeType

                try:
                    nodes = self.synthesis.graph.get_nodes_by_type(NodeType(node_type))
                    result = {"nodes": [n.to_dict() for n in nodes]}
                except ValueError:
                    result = {"error": f"Unknown node type: {node_type}"}
            else:
                result = self.synthesis.graph.get_stats()
        elif query_type == "interventions" and self.broker:
            interventions = self.broker.get_pending()
            result = {"interventions": [i.to_dict() for i in interventions]}
        elif query_type == "status":
            result = self._get_system_status()
        else:
            result = {
                "message": "Query received but no handler available",
                "query": query,
            }

        return IAPMessage(
            message_type=MessageType.RESPONSE,
            source_agent=self.cortex_agent,
            target_agent=message.source_agent,
            context_snapshot=message.context_snapshot,
            payload={"result": result, "query": query, "query_type": query_type},
        )

    def _handle_handoff(self, message: IAPMessage) -> IAPMessage:
        """Handle a handoff message between agents."""
        target_id = message.target_agent.id if message.target_agent else None
        instruction = message.payload.get("instruction", "")

        logger.info(f"Processing handoff to {target_id}: {instruction[:50]}...")

        # Store handoff context in graph if available
        if self.synthesis and message.context_snapshot:
            from cortex.engines.synthesis import Node, NodeType

            handoff_node = Node(
                id=f"handoff:{message.message_id}",
                type=NodeType.WORK_ITEM,
                name=f"Handoff: {instruction[:50]}",
                data={
                    "source_agent": (message.source_agent.id if message.source_agent else None),
                    "target_agent": target_id,
                    "instruction": instruction,
                    "context": message.context_snapshot.to_dict(),
                    "constraints": message.payload.get("constraints", []),
                },
            )
            self.synthesis.graph.add_node(handoff_node)

        # Create intervention for target agent if broker available
        if self.broker and target_id and target_id in self.registered_agents:
            from cortex.engines.broker import InterventionType, Severity

            self.broker.create_intervention(
                intervention_type=InterventionType.CONTEXT_SWITCH,
                severity=Severity.INFO,
                title=f"Handoff from {message.source_agent.id if message.source_agent else 'unknown'}",
                description=instruction,
                context=(message.context_snapshot.to_dict() if message.context_snapshot else {}),
            )

        return IAPMessage(
            message_type=MessageType.ACK,
            source_agent=self.cortex_agent,
            target_agent=message.source_agent,
            payload={
                "status": "handoff_accepted",
                "handoff_id": message.message_id,
                "target_agent": target_id,
            },
        )

    def _handle_ack(self, message: IAPMessage) -> IAPMessage:
        """Handle acknowledgment message."""
        intervention_id = message.payload.get("intervention_id")

        if intervention_id and self.broker:
            success = self.broker.acknowledge(intervention_id)
            status = "acknowledged" if success else "not_found"
        else:
            status = "no_intervention_id"

        return IAPMessage(
            message_type=MessageType.RESPONSE,
            source_agent=self.cortex_agent,
            target_agent=message.source_agent,
            payload={"status": status, "intervention_id": intervention_id},
        )

    def _handle_intervention(self, message: IAPMessage) -> IAPMessage:
        """Handle incoming intervention (for forwarding)."""
        # This handles interventions from external sources
        # and forwards them to the appropriate agent

        target_id = message.target_agent.id if message.target_agent else None

        if target_id and target_id in self.registered_agents:
            # Agent is registered, intervention can be delivered
            return IAPMessage(
                message_type=MessageType.ACK,
                source_agent=self.cortex_agent,
                target_agent=message.source_agent,
                payload={"status": "intervention_forwarded", "target": target_id},
            )
        else:
            return IAPMessage(
                message_type=MessageType.RESPONSE,
                source_agent=self.cortex_agent,
                target_agent=message.source_agent,
                payload={"status": "target_not_registered", "target": target_id},
            )

    def _error_response(self, message: IAPMessage, error: str) -> IAPMessage:
        """Create error response."""
        return IAPMessage(
            message_type=MessageType.RESPONSE,
            source_agent=self.cortex_agent,
            target_agent=message.source_agent,
            payload={"error": error, "original_message_id": message.message_id},
        )

    def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        status = {
            "protocol_version": PROTOCOL_VERSION,
            "registered_agents": len(self.registered_agents),
            "message_history_size": len(self._message_history),
        }

        if self.synthesis:
            status["graph_stats"] = self.synthesis.graph.get_stats()

        if self.broker:
            status["broker_status"] = self.broker.get_status()

        return status

    # === Convenience Methods for Creating Messages ===

    def create_query(
        self,
        query: str,
        query_type: str = "context",
        from_agent: Optional[Agent] = None,
        context: Optional[ContextSnapshot] = None,
    ) -> IAPMessage:
        """Create a query message."""
        return IAPMessage(
            message_type=MessageType.QUERY,
            source_agent=from_agent,
            target_agent=self.cortex_agent,
            context_snapshot=context,
            payload={"query": query, "query_type": query_type},
        )

    def create_handoff(
        self,
        instruction: str,
        from_agent: Agent,
        to_agent: Agent,
        context: ContextSnapshot,
        constraints: Optional[List[str]] = None,
        expected_output: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> IAPMessage:
        """Create a handoff message."""
        return IAPMessage(
            message_type=MessageType.HANDOFF,
            source_agent=from_agent,
            target_agent=to_agent,
            context_snapshot=context,
            payload={
                "instruction": instruction,
                "constraints": constraints or [],
                "expected_output": expected_output,
                "timeout_seconds": timeout_seconds,
            },
        )

    def create_ack(
        self,
        intervention_id: str,
        from_agent: Agent,
    ) -> IAPMessage:
        """Create an acknowledgment message."""
        return IAPMessage(
            message_type=MessageType.ACK,
            source_agent=from_agent,
            target_agent=self.cortex_agent,
            payload={"intervention_id": intervention_id},
        )

    def get_message_history(self, limit: int = 100) -> List[Dict]:
        """Get recent message history."""
        return [m.to_dict() for m in self._message_history[-limit:]]


def create_default_handler() -> IAPHandler:
    """Create IAP handler with default engines."""
    try:
        from cortex.engines.broker import ActionBroker
        from cortex.engines.synthesis import ContextGraph, SynthesisCore

        graph = ContextGraph()
        synthesis = SynthesisCore(graph)
        broker = ActionBroker()

        return IAPHandler(synthesis_core=synthesis, action_broker=broker)
    except ImportError as e:
        logger.warning(f"Could not initialize engines: {e}")
        return IAPHandler()
