"""
Cortex V2 Prime: Communication Protocols

Inter-Agent Protocol (IAP) enables structured communication between AI agents and Cortex.
"""

try:
    from cortex.protocols.iap import (
        IAPHandler,
        IAPMessage,
        MessageType,
        Agent,
        AgentRole,
        ContextSnapshot,
    )
except ImportError:
    # Fallback for direct execution
    from .iap import (
        IAPHandler,
        IAPMessage,
        MessageType,
        Agent,
        AgentRole,
        ContextSnapshot,
    )

__all__ = [
    "IAPHandler",
    "IAPMessage",
    "MessageType",
    "Agent",
    "AgentRole",
    "ContextSnapshot",
]
