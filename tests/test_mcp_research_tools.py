"""
Tests for CRA MCP tools — cortex_research_status, cortex_research_digest, cortex_research_proposals.

Tests use the CRA engine directly (avoiding mcp.server.fastmcp import)
since the MCP SDK may not be in the test environment.

Tests:
- Research status returns correct counts
- Weekly digest returns markdown with header
- Proposal list returns proposals with status
- Proposal approve transitions status correctly
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def cra_with_data():
    """CRA agent with sample data for MCP tool testing."""
    from engines.research_agent import Assessment, CortexResearchAgent, Discovery

    with tempfile.TemporaryDirectory() as tmpdir:
        research_dir = Path(tmpdir)
        agent = CortexResearchAgent(research_dir=research_dir)

        # Add a discovery
        discovery = Discovery(
            id="cra_mcp_test",
            source="arxiv_agent_memory",
            title="Test Discovery for MCP",
            url="https://arxiv.org/abs/2603.99999",
            summary="Test summary for MCP tool testing.",
            discovered_at=datetime.now(tz=timezone.utc).isoformat(),
            relevance_scores={"memory_retrieval": 0.7},
        )
        agent.ingest_discovery(discovery)

        # Add an assessment
        assessment = Assessment(
            discovery_id="cra_mcp_test",
            title="Test Discovery for MCP",
            source_url="https://arxiv.org/abs/2603.99999",
            disruption_risk=0.4,
            adoption_effort="small",
            expected_impact="significant",
            affected_modules=["intelligence/memory/"],
            integration_approach="Test integration approach.",
            risks=["Test risk"],
            recommendation="adopt",
            reasoning="Test reasoning for adoption.",
            assessed_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        agent.ingest_assessment(assessment)

        yield agent, research_dir


class TestMCPResearchStatus:
    """Tests for cortex_research_status equivalent logic.

    Since MCP SDK isn't in the test venv, we test the underlying CRA
    methods that the MCP tool wraps. This validates the data contract.
    """

    def test_status_has_required_keys(self, cra_with_data):
        agent, _research_dir = cra_with_data

        # Simulate what cortex_research_status() does
        discoveries = agent.load_discoveries()
        assessments = agent.load_assessments()
        adopt = agent.get_adopt_recommendations()
        threats = agent.get_urgent_threats()
        proposals = agent.get_pending_proposals()
        statuses = agent.status_tracker.get_all()

        status_counts = {}
        for _file, data in statuses.items():
            s = data.get("status", "draft")
            status_counts[s] = status_counts.get(s, 0) + 1

        result = {
            "discoveries": len(discoveries),
            "assessments": len(assessments),
            "adopt_recommendations": len(adopt),
            "urgent_threats": len(threats),
            "pending_proposals": len(proposals),
            "baseline_score": round(agent.get_baseline_score(), 4),
            "scan_due": agent.should_scan(),
            "proposal_statuses": status_counts,
        }

        # Validate JSON serializable
        serialized = json.dumps(result, indent=2)
        data = json.loads(serialized)

        required_keys = [
            "discoveries",
            "assessments",
            "adopt_recommendations",
            "urgent_threats",
            "pending_proposals",
            "baseline_score",
            "scan_due",
            "proposal_statuses",
        ]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"

    def test_counts_are_correct(self, cra_with_data):
        agent, _research_dir = cra_with_data

        assert len(agent.load_discoveries()) == 1
        assert len(agent.load_assessments()) == 1
        assert len(agent.get_adopt_recommendations()) == 1
        assert agent.get_baseline_score() == 0.5  # Default


class TestMCPResearchDigest:
    """Tests for cortex_research_digest equivalent logic."""

    def test_returns_markdown_with_header(self, cra_with_data):
        agent, _research_dir = cra_with_data

        digest = agent.weekly_digest()
        assert "CRA Weekly Digest" in digest
        assert "Test Discovery for MCP" in digest


class TestMCPResearchProposals:
    """Tests for cortex_research_proposals equivalent logic."""

    def test_list_empty(self, cra_with_data):
        agent, _research_dir = cra_with_data

        proposals = agent.get_pending_proposals()
        result = []
        for p in proposals:
            status = agent.status_tracker.get_status(p["file"])
            result.append(
                {
                    "file": p["file"],
                    "title": p["title"],
                    "created": p["created"],
                    "status": status,
                }
            )
        assert isinstance(result, list)

    def test_list_after_generate(self, cra_with_data):
        agent, _research_dir = cra_with_data

        created = agent.generate_proposals_from_assessments()
        assert len(created) > 0

        proposals = agent.get_pending_proposals()
        assert len(proposals) >= 1
        status = agent.status_tracker.get_status(proposals[0]["file"])
        assert status == "draft"

    def test_approve_transitions_status(self, cra_with_data):
        agent, _research_dir = cra_with_data

        created = agent.generate_proposals_from_assessments()
        proposal_file = created[0].name

        # Approve it
        agent.approve_proposal(proposal_file)
        assert agent.status_tracker.get_status(proposal_file) == "approved"

    def test_proposals_json_serializable(self, cra_with_data):
        """Ensure the proposal data contract works for JSON transport (MCP)."""
        agent, _research_dir = cra_with_data

        agent.generate_proposals_from_assessments()
        proposals = agent.get_pending_proposals()

        result = []
        for p in proposals:
            result.append(
                {
                    "file": p["file"],
                    "title": p["title"],
                    "created": p["created"],
                    "status": agent.status_tracker.get_status(p["file"]),
                }
            )

        # Must be JSON serializable
        serialized = json.dumps({"proposals": result, "count": len(result)}, indent=2)
        data = json.loads(serialized)
        assert data["count"] >= 1
        assert "proposals" in data
