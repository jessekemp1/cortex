"""
Domain Experts - Project-specific intelligence modules.

Layer 3 of Cortex Intelligence Stack: Domain Knowledge

Provides:
- BaseDomainExpert - Abstract base class for domain experts
- VortexExpert - Marine weather forecasting domain knowledge
- (Future: AlphaArenaExpert, DJCoPilotExpert, CortexExpert)
"""

from intelligence.domains.base_expert import BaseDomainExpert, DomainInsight

__all__ = ["BaseDomainExpert", "DomainInsight"]
