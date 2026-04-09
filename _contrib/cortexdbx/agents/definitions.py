"""Agent definitions for CortexDBx domain experts."""

from dataclasses import dataclass
from enum import Enum
from typing import List


class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    DOMAIN_EXPERT = "domain_expert"
    CALIBRATOR = "calibrator"
    RECOMMENDER = "recommender"
    EVALUATOR = "evaluator"


@dataclass
class AgentConfig:
    """Configuration for a CortexDBx agent."""

    role: AgentRole
    domain: str
    capabilities: List[str]
    prompt_template: str
    tools: List[str]


AGENT_CONFIGS = {
    "orchestrator": AgentConfig(
        role=AgentRole.ORCHESTRATOR,
        domain="all",
        capabilities=[
            "coordinate_domain_agents",
            "aggregate_results",
            "manage_parallelism",
            "handle_failures",
        ],
        prompt_template=(
            "You are the CortexDBx Orchestrator Agent. "
            "Current task: {task}. Available domain agents: {agents}"
        ),
        tools=["spawn_agent", "wait_for_agents", "aggregate_results"],
    ),
    "fraud_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="fraud_investigation",
        capabilities=[
            "analyze_fraud_patterns",
            "recommend_investigation_priority",
            "learn_from_resolution_outcomes",
        ],
        prompt_template=(
            "You are the Fraud Investigation Domain Agent. Context: {context}. Task: {task}"
        ),
        tools=["query_outcomes", "update_calibration", "generate_recommendation"],
    ),
    "healthcare_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="clinical_trial",
        capabilities=[
            "analyze_enrollment_patterns",
            "recommend_criteria_adjustments",
            "learn_from_trial_outcomes",
        ],
        prompt_template=(
            "You are the Clinical Trial Domain Agent. Context: {context}. Task: {task}"
        ),
        tools=["query_outcomes", "update_calibration", "generate_recommendation"],
    ),
    "maintenance_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="maintenance",
        capabilities=[
            "analyze_maintenance_patterns",
            "recommend_repair_strategy",
            "learn_from_repair_outcomes",
        ],
        prompt_template=("You are the Maintenance Domain Agent. Context: {context}. Task: {task}"),
        tools=["query_outcomes", "update_calibration", "generate_recommendation"],
    ),
    "marketing_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="marketing_campaign",
        capabilities=[
            "analyze_campaign_patterns",
            "recommend_creative_strategy",
            "learn_from_campaign_outcomes",
        ],
        prompt_template=(
            "You are the Marketing Campaign Domain Agent. Context: {context}. Task: {task}"
        ),
        tools=["query_outcomes", "update_calibration", "generate_recommendation"],
    ),
    "security_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="security_incident",
        capabilities=[
            "analyze_incident_patterns",
            "recommend_playbook",
            "learn_from_response_outcomes",
        ],
        prompt_template=(
            "You are the Security Incident Domain Agent. Context: {context}. Task: {task}"
        ),
        tools=["query_outcomes", "update_calibration", "generate_recommendation"],
    ),
    "supply_chain_domain": AgentConfig(
        role=AgentRole.DOMAIN_EXPERT,
        domain="supply_chain",
        capabilities=[
            "analyze_routing_patterns",
            "recommend_supplier_strategy",
            "learn_from_delivery_outcomes",
        ],
        prompt_template=("You are the Supply Chain Domain Agent. Context: {context}. Task: {task}"),
        tools=["query_outcomes", "update_calibration", "generate_recommendation"],
    ),
}
