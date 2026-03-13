"""
Tests for Cortex Research Agent (CRA).

Tests:
- Discovery ingestion and dedup
- Brief parsing (markdown → Discovery objects)
- Assessment storage and querying
- Intake integration (from_research_agent)
- Relevance scoring against capability vectors
- Dismissed findings exclusion
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def cra_dir():
    """Temporary CRA research directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def agent(cra_dir):
    """CRA instance with temp storage."""
    from engines.research_agent import CortexResearchAgent

    return CortexResearchAgent(research_dir=cra_dir)


@pytest.fixture
def sample_discovery():
    """A sample Discovery object."""
    from engines.research_agent import Discovery

    return Discovery(
        id="cra_test001",
        source="arxiv_agent_memory",
        title="Trajectory Memory for LLM Agents",
        url="https://arxiv.org/abs/2603.10600",
        summary="Trajectory-informed memory improves agent task completion by +14.3pp.",
        discovered_at=datetime.now(tz=timezone.utc).isoformat(),
        relevance_scores={
            "memory_retrieval": 0.8,
            "outcome_learning": 0.6,
            "task_orchestration": 0.3,
            "anti_patterns": 0.1,
            "context_optimization": 0.2,
            "goal_tracking": 0.0,
            "research_automation": 0.0,
        },
    )


@pytest.fixture
def sample_assessment():
    """A sample Assessment object with 'adopt' recommendation."""
    from engines.research_agent import Assessment

    return Assessment(
        discovery_id="cra_test001",
        title="Trajectory Memory for LLM Agents",
        source_url="https://arxiv.org/abs/2603.10600",
        disruption_risk=0.3,
        adoption_effort="medium",
        expected_impact="significant",
        affected_modules=["intelligence/memory/hybrid_retriever.py"],
        integration_approach="Add trajectory extraction to session capture pipeline.",
        risks=["Increased memory footprint", "Cold start without historical data"],
        recommendation="adopt",
        reasoning="Directly maps to Cortex Phase 2 trajectory memory goal.",
        assessed_at=datetime.now(tz=timezone.utc).isoformat(),
        relevance_scores={"memory_retrieval": 0.8, "outcome_learning": 0.6},
    )


@pytest.fixture
def urgent_assessment():
    """An assessment with high disruption + achievable effort (urgent)."""
    from engines.research_agent import Assessment

    return Assessment(
        discovery_id="cra_test_urgent",
        title="Anthropic Ships Native Memory API",
        source_url="https://docs.anthropic.com/memory",
        disruption_risk=0.9,
        adoption_effort="medium",
        expected_impact="transformative",
        affected_modules=["intelligence/memory/", "mcp_server.py"],
        integration_approach="Pivot to intelligence layer on top of native memory.",
        risks=["Core value proposition shift"],
        recommendation="adopt",
        reasoning="Existential threat — must adapt immediately.",
        assessed_at=datetime.now(tz=timezone.utc).isoformat(),
    )


class TestDiscoveryIngestion:
    """Tests for discovery storage and deduplication."""

    def test_ingest_discovery_creates_file(self, agent, sample_discovery, cra_dir):
        agent.ingest_discovery(sample_discovery)
        assert (cra_dir / "discoveries.jsonl").exists()

    def test_ingest_discovery_appends_jsonl(self, agent, sample_discovery, cra_dir):
        agent.ingest_discovery(sample_discovery)
        lines = (cra_dir / "discoveries.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["title"] == "Trajectory Memory for LLM Agents"
        assert data["source"] == "arxiv_agent_memory"

    def test_dedup_by_url(self, agent, sample_discovery):
        agent.ingest_discovery(sample_discovery)
        agent.ingest_discovery(sample_discovery)  # Same URL
        discoveries = agent.load_discoveries(days=9999)
        assert len(discoveries) == 1

    def test_different_urls_not_deduped(self, agent, sample_discovery):
        from engines.research_agent import Discovery

        agent.ingest_discovery(sample_discovery)
        other = Discovery(
            id="cra_test002",
            source="github_trending",
            title="Different Finding",
            url="https://github.com/different/repo",
            summary="Different thing.",
            discovered_at=datetime.now(tz=timezone.utc).isoformat(),
            relevance_scores={"memory_retrieval": 0.5},
        )
        agent.ingest_discovery(other)
        discoveries = agent.load_discoveries(days=9999)
        assert len(discoveries) == 2


class TestDiscoveryProperties:
    """Tests for Discovery dataclass properties."""

    def test_max_relevance(self, sample_discovery):
        assert sample_discovery.max_relevance == 0.8

    def test_top_capability(self, sample_discovery):
        assert sample_discovery.top_capability == "memory_retrieval"

    def test_empty_relevance(self):
        from engines.research_agent import Discovery

        d = Discovery(
            id="empty",
            source="test",
            title="Empty",
            url="",
            summary="",
            discovered_at="",
            relevance_scores={},
        )
        assert d.max_relevance == 0.0
        assert d.top_capability == "unknown"


class TestAssessment:
    """Tests for assessment storage and querying."""

    def test_ingest_assessment(self, agent, sample_assessment, cra_dir):
        agent.ingest_assessment(sample_assessment)
        assert (cra_dir / "assessments.jsonl").exists()
        assessments = agent.load_assessments(days=9999)
        assert len(assessments) == 1
        assert assessments[0].recommendation == "adopt"

    def test_adopt_recommendations(self, agent, sample_assessment):
        agent.ingest_assessment(sample_assessment)
        adopt = agent.get_adopt_recommendations()
        assert len(adopt) == 1
        assert adopt[0].title == "Trajectory Memory for LLM Agents"

    def test_is_urgent_true(self, urgent_assessment):
        assert urgent_assessment.is_urgent is True

    def test_is_urgent_false(self, sample_assessment):
        # disruption_risk=0.3 < 0.7 threshold
        assert sample_assessment.is_urgent is False

    def test_urgent_threats(self, agent, urgent_assessment, sample_assessment):
        agent.ingest_assessment(urgent_assessment)
        agent.ingest_assessment(sample_assessment)
        threats = agent.get_urgent_threats()
        assert len(threats) == 1
        assert threats[0].title == "Anthropic Ships Native Memory API"

    def test_priority_score_ordering(self, sample_assessment, urgent_assessment):
        # Transformative + medium effort + high disruption > significant + medium + low disruption
        assert urgent_assessment.priority_score > sample_assessment.priority_score


class TestDismissal:
    """Tests for dismissed findings tracking."""

    def test_dismiss_records(self, agent, cra_dir):
        agent.dismiss("cra_test001", "Not relevant after deeper review")
        assert (cra_dir / "dismissed.jsonl").exists()
        ids = agent.get_dismissed_ids()
        assert "cra_test001" in ids

    def test_dismissed_ids_empty_when_no_file(self, agent):
        ids = agent.get_dismissed_ids()
        assert len(ids) == 0


class TestBriefIngestion:
    """Tests for parsing research brief markdown files."""

    def test_ingest_from_brief(self, agent):
        brief_path = (
            Path.home()
            / "Dev"
            / "cortex"
            / "research_briefs"
            / "2026-03-11_ai_development_intel.md"
        )
        if not brief_path.exists():
            pytest.skip("Research brief not available")

        discoveries = agent.ingest_from_brief(brief_path)
        assert len(discoveries) > 0

        # Each discovery should have required fields
        for d in discoveries:
            assert d.title
            assert d.summary
            assert isinstance(d.relevance_scores, dict)

    def test_ingest_missing_brief(self, agent, cra_dir):
        discoveries = agent.ingest_from_brief(cra_dir / "nonexistent.md")
        assert discoveries == []

    def test_brief_findings_have_urls(self, agent):
        brief_path = (
            Path.home()
            / "Dev"
            / "cortex"
            / "research_briefs"
            / "2026-03-11_ai_development_intel.md"
        )
        if not brief_path.exists():
            pytest.skip("Research brief not available")

        discoveries = agent.ingest_from_brief(brief_path)
        with_urls = [d for d in discoveries if d.url.startswith("http")]
        # Most findings should have source URLs
        assert len(with_urls) >= len(discoveries) * 0.5


class TestRelevanceScoring:
    """Tests for keyword-based relevance scoring."""

    def test_memory_keywords_score_high(self, agent):
        scores = agent._score_relevance(
            "hybrid retrieval BM25 embedding search memory pattern matching"
        )
        assert scores["memory_retrieval"] > 0.5

    def test_irrelevant_text_scores_low(self, agent):
        scores = agent._score_relevance("cooking recipes for dinner tonight")
        for capability, score in scores.items():
            assert score < 0.3, f"{capability} scored {score} for irrelevant text"

    def test_orchestration_keywords(self, agent):
        scores = agent._score_relevance(
            "task routing dispatch work discovery supervisor pipeline model tier"
        )
        assert scores["task_orchestration"] > 0.5


class TestProposals:
    """Tests for proposal storage."""

    def test_save_proposal(self, agent, cra_dir):
        path = agent.save_proposal(
            "Trajectory Memory Integration",
            "## Research Integration: Trajectory Memory\n\nSpec content here.",
        )
        assert path.exists()
        assert "trajectory_memory" in path.name

    def test_get_pending_proposals(self, agent):
        agent.save_proposal("Test Proposal", "Content")
        proposals = agent.get_pending_proposals()
        assert len(proposals) == 1
        assert "test proposal" in proposals[0]["title"]

    def test_adopted_proposal_excluded(self, agent):
        path = agent.save_proposal("Adopted Thing", "Content")
        agent.record_adoption(path.name, outcome="Improved retrieval by 12%")
        proposals = agent.get_pending_proposals()
        assert len(proposals) == 0


class TestIntakeIntegration:
    """Tests for CRA → supervisor intake pipeline."""

    def test_from_research_agent_empty(self):
        """No assessments → no work items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from supervisor.intake import WorkIntake

            intake = WorkIntake()
            items = intake.from_research_agent(research_dir=Path(tmpdir))
            assert items == []

    def test_from_research_agent_with_adopt(self, cra_dir, sample_assessment):
        """Adopt assessments become work items."""
        from engines.research_agent import CortexResearchAgent
        from supervisor.intake import WorkIntake

        agent = CortexResearchAgent(research_dir=cra_dir)
        agent.ingest_assessment(sample_assessment)

        intake = WorkIntake()
        items = intake.from_research_agent(research_dir=cra_dir)
        assert len(items) == 1
        assert items[0].source == "research_agent"
        assert items[0].task_type == "research"
        assert items[0].project == "cortex"
        assert "Trajectory Memory" in items[0].description
        assert items[0].defer_to_batch is True

    def test_urgent_gets_high_priority(self, cra_dir, urgent_assessment):
        """Urgent assessments get HIGH priority."""
        from engines.research_agent import CortexResearchAgent
        from supervisor.intake import WorkIntake
        from supervisor.models import WorkItemPriority

        agent = CortexResearchAgent(research_dir=cra_dir)
        agent.ingest_assessment(urgent_assessment)

        intake = WorkIntake()
        items = intake.from_research_agent(research_dir=cra_dir)
        assert len(items) == 1
        assert items[0].priority == WorkItemPriority.HIGH

    def test_monitor_not_surfaced(self, cra_dir):
        """Monitor-only assessments don't become work items."""
        from engines.research_agent import Assessment, CortexResearchAgent
        from supervisor.intake import WorkIntake

        agent = CortexResearchAgent(research_dir=cra_dir)
        monitor = Assessment(
            discovery_id="cra_monitor",
            title="Some Monitored Thing",
            source_url="https://example.com",
            disruption_risk=0.2,
            adoption_effort="large",
            expected_impact="incremental",
            affected_modules=[],
            integration_approach="Watch and wait.",
            risks=[],
            recommendation="monitor",
            reasoning="Not actionable yet.",
            assessed_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        agent.ingest_assessment(monitor)

        intake = WorkIntake()
        items = intake.from_research_agent(research_dir=cra_dir)
        assert items == []


class TestWeeklyDigest:
    """Tests for digest generation."""

    def test_empty_digest(self, agent):
        digest = agent.weekly_digest()
        assert "CRA Weekly Digest" in digest
        assert "**Discoveries:** 0" in digest

    def test_digest_with_data(self, agent, sample_discovery, sample_assessment):
        agent.ingest_discovery(sample_discovery)
        agent.ingest_assessment(sample_assessment)
        digest = agent.weekly_digest()
        assert "**Adopt:** 1" in digest
        assert "Trajectory Memory" in digest


class TestScanDue:
    """Tests for scan scheduling."""

    def test_scan_due_when_empty(self, agent):
        assert agent.should_scan() is True

    def test_scan_not_due_after_recent(self, agent, sample_discovery):
        agent.ingest_discovery(sample_discovery)
        assert agent.should_scan() is False


class TestCLI:
    """Tests for CRA CLI commands."""

    def test_status_command(self, cra_dir):
        """Status command runs without error."""
        from engines.research_agent import CortexResearchAgent

        agent = CortexResearchAgent(research_dir=cra_dir)
        discoveries = agent.load_discoveries()
        assessments = agent.load_assessments()
        # Just verify it doesn't crash
        assert isinstance(discoveries, list)
        assert isinstance(assessments, list)

    def test_get_scan_prompt(self, agent):
        prompt = agent.get_scan_prompt()
        assert "PRIORITY THREAT MONITORING" in prompt
        assert "CAPABILITY VECTORS" in prompt

    def test_get_assess_prompt(self, agent, sample_discovery):
        prompt = agent.get_assess_prompt(sample_discovery)
        assert "Trajectory Memory" in prompt
        assert "CORTEX CAPABILITIES" in prompt
