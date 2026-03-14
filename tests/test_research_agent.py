"""
Tests for Cortex Research Agent (CRA).

Tests:
- Discovery ingestion and dedup
- Brief parsing (markdown → Discovery objects)
- Assessment storage and querying
- Intake integration (from_research_agent)
- Relevance scoring against capability vectors
- Dismissed findings exclusion
- ProposalResult + adoption_outcome_score (autoresearch-inspired)
- Research directives loading and parsing
- Experiment loop runner
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


class TestProposalResult:
    """Tests for ProposalResult dataclass and adoption_outcome_score."""

    def test_perfect_result_scores_high(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        result = ProposalResult(
            proposal_title="Perfect integration",
            tests_passing=100,
            tests_total=100,
            capability_score_delta=1.0,
            addresses_threat=True,
        )
        score = adoption_outcome_score(result)
        assert score == 1.0

    def test_all_tests_fail_scores_low(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        result = ProposalResult(
            proposal_title="Broken integration",
            tests_passing=0,
            tests_total=100,
            capability_score_delta=1.0,
            addresses_threat=True,
        )
        score = adoption_outcome_score(result)
        # 0.5*0 + 0.3*1.0 + 0.2*1.0 = 0.5
        assert score == pytest.approx(0.5)

    def test_zero_tests_scores_zero_test_weight(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        result = ProposalResult(
            proposal_title="No tests",
            tests_passing=0,
            tests_total=0,
            capability_score_delta=0.0,
            addresses_threat=False,
        )
        score = adoption_outcome_score(result)
        assert score == 0.0

    def test_test_pass_rate(self):
        from engines.research_agent import ProposalResult

        result = ProposalResult(
            proposal_title="Partial",
            tests_passing=75,
            tests_total=100,
            capability_score_delta=0.0,
            addresses_threat=False,
        )
        assert result.test_pass_rate == 0.75

    def test_test_pass_rate_zero_total(self):
        from engines.research_agent import ProposalResult

        result = ProposalResult(
            proposal_title="Empty",
            tests_passing=0,
            tests_total=0,
            capability_score_delta=0.0,
            addresses_threat=False,
        )
        assert result.test_pass_rate == 0.0

    def test_capability_delta_clamped(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        result = ProposalResult(
            proposal_title="Over-promising",
            tests_passing=100,
            tests_total=100,
            capability_score_delta=5.0,  # > 1.0, should clamp
            addresses_threat=False,
        )
        score = adoption_outcome_score(result)
        # 0.5*1.0 + 0.3*1.0(clamped) + 0.2*0.0 = 0.8
        assert score == pytest.approx(0.8)

    def test_negative_delta_clamped(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        result = ProposalResult(
            proposal_title="Regression",
            tests_passing=100,
            tests_total=100,
            capability_score_delta=-0.5,  # Negative, should clamp to 0
            addresses_threat=False,
        )
        score = adoption_outcome_score(result)
        # 0.5*1.0 + 0.3*0.0 + 0.2*0.0 = 0.5
        assert score == pytest.approx(0.5)

    def test_threat_bonus(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        no_threat = ProposalResult(
            proposal_title="No threat",
            tests_passing=80,
            tests_total=100,
            capability_score_delta=0.5,
            addresses_threat=False,
        )
        with_threat = ProposalResult(
            proposal_title="With threat",
            tests_passing=80,
            tests_total=100,
            capability_score_delta=0.5,
            addresses_threat=True,
        )
        assert adoption_outcome_score(with_threat) > adoption_outcome_score(no_threat)
        assert adoption_outcome_score(with_threat) - adoption_outcome_score(
            no_threat
        ) == pytest.approx(0.2)

    def test_typical_good_result(self):
        from engines.research_agent import ProposalResult, adoption_outcome_score

        result = ProposalResult(
            proposal_title="Typical",
            tests_passing=95,
            tests_total=100,
            capability_score_delta=0.4,
            addresses_threat=True,
        )
        score = adoption_outcome_score(result)
        # 0.5*0.95 + 0.3*0.4 + 0.2*1.0 = 0.475 + 0.12 + 0.2 = 0.795
        assert score == pytest.approx(0.795)


class TestResearchDirectives:
    """Tests for research_directives.md loading and parsing."""

    def test_load_directives_from_file(self):
        from engines.research_agent import load_research_directives

        directives = load_research_directives()
        # Should load the actual research_directives.md we created
        assert len(directives) > 100
        assert "Cortex Research Directives" in directives

    def test_load_directives_missing_file(self):
        from engines.research_agent import load_research_directives

        result = load_research_directives(Path("/nonexistent/directives.md"))
        assert result == ""

    def test_parse_priorities_from_real_file(self):
        from engines.research_agent import (
            load_research_directives,
            parse_directives_priorities,
        )

        directives = load_research_directives()
        if not directives:
            pytest.skip("research_directives.md not available")
        priorities = parse_directives_priorities(directives)
        assert len(priorities["priority_1"]) >= 3
        assert len(priorities["priority_2"]) >= 3
        assert len(priorities["priority_3"]) >= 1

    def test_parse_priorities_extracts_bold_names(self):
        from engines.research_agent import parse_directives_priorities

        test_md = """
### Priority 1: Existential Threat Monitoring
1. **Anthropic native memory API** — If Claude gets built-in persistent memory
2. **Mem0 adds orchestration** — If Mem0 ships task routing

### Priority 2: Capability Amplification
1. **Trajectory memory** — Learn from HOW tasks were solved
2. **Memory admission control** — Decide what NOT to remember

## Constraints
"""
        priorities = parse_directives_priorities(test_md)
        assert priorities["priority_1"] == [
            "Anthropic native memory API",
            "Mem0 adds orchestration",
        ]
        assert priorities["priority_2"] == [
            "Trajectory memory",
            "Memory admission control",
        ]
        assert priorities["priority_3"] == []

    def test_parse_empty_directives(self):
        from engines.research_agent import parse_directives_priorities

        priorities = parse_directives_priorities("")
        assert priorities == {
            "priority_1": [],
            "priority_2": [],
            "priority_3": [],
        }

    def test_scan_prompt_includes_directives(self, agent):
        prompt = agent.get_scan_prompt()
        assert "HUMAN RESEARCH DIRECTIVES" in prompt
        # Should include actual priority items from file
        assert "Priority 1" in prompt or "priority_1" in prompt.lower()

    def test_scan_prompt_includes_autoresearch_source(self, agent):
        sources = agent.get_sources()
        assert "autoresearch_ecosystem" in sources
        assert "karpathy autoresearch" in sources["autoresearch_ecosystem"]["queries"]


class TestExperimentLoop:
    """Tests for the CRA experiment loop runner (autoresearch-inspired)."""

    def test_evaluate_proposal_keep(self, agent, cra_dir):
        from engines.research_agent import ProposalResult

        result = ProposalResult(
            proposal_title="Good integration",
            tests_passing=98,
            tests_total=100,
            capability_score_delta=0.6,
            addresses_threat=False,
            branch_name="cra/good-integration",
        )
        outcome = agent.evaluate_experiment(result, baseline_score=0.5)
        assert outcome["decision"] == "keep"
        assert outcome["score"] > 0.5

    def test_evaluate_proposal_discard(self, agent, cra_dir):
        from engines.research_agent import ProposalResult

        result = ProposalResult(
            proposal_title="Bad integration",
            tests_passing=40,
            tests_total=100,
            capability_score_delta=0.1,
            addresses_threat=False,
            branch_name="cra/bad-integration",
        )
        outcome = agent.evaluate_experiment(result, baseline_score=0.5)
        assert outcome["decision"] == "discard"
        assert outcome["score"] <= 0.5

    def test_evaluate_proposal_with_error(self, agent, cra_dir):
        from engines.research_agent import ProposalResult

        result = ProposalResult(
            proposal_title="Errored integration",
            tests_passing=0,
            tests_total=0,
            capability_score_delta=0.0,
            addresses_threat=False,
            error="ImportError: no module named 'foo'",
        )
        outcome = agent.evaluate_experiment(result, baseline_score=0.5)
        assert outcome["decision"] == "discard"
        assert "error" in outcome

    def test_experiment_log_persists(self, agent, cra_dir):
        from engines.research_agent import ProposalResult

        result = ProposalResult(
            proposal_title="Logged integration",
            tests_passing=100,
            tests_total=100,
            capability_score_delta=0.8,
            addresses_threat=True,
        )
        agent.evaluate_experiment(result, baseline_score=0.3)
        log_path = cra_dir / "experiment_log.jsonl"
        assert log_path.exists()
        entries = log_path.read_text().strip().splitlines()
        assert len(entries) == 1
        entry = json.loads(entries[0])
        assert entry["decision"] == "keep"
        assert entry["proposal_title"] == "Logged integration"

    def test_get_baseline_score_default(self, agent):
        baseline = agent.get_baseline_score()
        assert baseline == 0.5  # Default when no experiments logged

    def test_get_baseline_score_from_log(self, agent, cra_dir):
        from engines.research_agent import ProposalResult

        # Run a successful experiment to establish baseline
        result = ProposalResult(
            proposal_title="Baseline setter",
            tests_passing=90,
            tests_total=100,
            capability_score_delta=0.5,
            addresses_threat=False,
        )
        agent.evaluate_experiment(result, baseline_score=0.5)
        baseline = agent.get_baseline_score()
        # Baseline should be the score of the last kept experiment
        assert baseline > 0.5


class TestLiveExperiment:
    """Tests for _execute_live_experiment with mocked subprocess."""

    def test_parses_pytest_all_pass(self, agent, cra_dir):
        from unittest.mock import patch

        # Create a proposal file so the method can read it
        proposal_dir = cra_dir / "proposals"
        proposal_dir.mkdir(exist_ok=True)
        spec_file = proposal_dir / "2026-03-14_test_integration.md"
        spec_file.write_text(
            "## Research Integration: Test\n\nMemory retrieval improvement using hybrid search.\n"
        )

        proposal = {
            "title": "test integration",
            "path": str(spec_file),
            "file": spec_file.name,
            "created": "2026-03-14",
        }

        mock_result = type(
            "Result",
            (),
            {
                "stdout": "57 passed in 0.18s\n",
                "stderr": "",
                "returncode": 0,
            },
        )()

        with patch("subprocess.run", return_value=mock_result):
            result = agent._execute_live_experiment(proposal)

        assert result.tests_passing == 57
        assert result.tests_total == 57
        assert result.test_pass_rate == 1.0
        assert result.error == ""
        assert result.capability_score_delta > 0.0  # Spec has relevant keywords

    def test_parses_pytest_with_failures(self, agent, cra_dir):
        from unittest.mock import patch

        proposal = {"title": "failing integration"}

        mock_result = type(
            "Result",
            (),
            {
                "stdout": "45 passed, 3 failed, 1 error in 2.5s\n",
                "stderr": "",
                "returncode": 1,
            },
        )()

        with patch("subprocess.run", return_value=mock_result):
            result = agent._execute_live_experiment(proposal)

        assert result.tests_passing == 45
        assert result.tests_total == 49  # 45 + 3 + 1
        assert result.test_pass_rate == pytest.approx(45 / 49)
        assert result.error != ""  # returncode=1 means error captured

    def test_handles_timeout(self, agent, cra_dir):
        import subprocess
        from unittest.mock import patch

        proposal = {"title": "slow integration"}

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=300),
        ):
            result = agent._execute_live_experiment(proposal)

        assert result.tests_passing == 0
        assert result.tests_total == 0
        assert "timed out" in result.error

    def test_threat_detection_from_spec(self, agent, cra_dir):
        from unittest.mock import patch

        proposal_dir = cra_dir / "proposals"
        proposal_dir.mkdir(exist_ok=True)
        spec_file = proposal_dir / "2026-03-14_threat_response.md"
        spec_file.write_text(
            "## Threat Response: Anthropic native memory API\n\n"
            "Pivot Cortex to intelligence layer on top of native memory.\n"
        )

        proposal = {
            "title": "threat response",
            "path": str(spec_file),
            "file": spec_file.name,
            "created": "2026-03-14",
        }

        mock_result = type(
            "Result",
            (),
            {
                "stdout": "100 passed in 1.0s\n",
                "stderr": "",
                "returncode": 0,
            },
        )()

        with patch("subprocess.run", return_value=mock_result):
            result = agent._execute_live_experiment(proposal)

        assert result.addresses_threat is True

    def test_no_threat_when_spec_unrelated(self, agent, cra_dir):
        from unittest.mock import patch

        proposal_dir = cra_dir / "proposals"
        proposal_dir.mkdir(exist_ok=True)
        spec_file = proposal_dir / "2026-03-14_minor_improvement.md"
        spec_file.write_text(
            "## Minor: Add logging to retriever\n\nImproved debug output for hybrid search.\n"
        )

        proposal = {
            "title": "minor improvement",
            "path": str(spec_file),
            "file": spec_file.name,
            "created": "2026-03-14",
        }

        mock_result = type(
            "Result",
            (),
            {
                "stdout": "50 passed in 0.5s\n",
                "stderr": "",
                "returncode": 0,
            },
        )()

        with patch("subprocess.run", return_value=mock_result):
            result = agent._execute_live_experiment(proposal)

        assert result.addresses_threat is False

    def test_score_integrates_correctly(self, agent, cra_dir):
        """Full integration: live experiment → adoption_outcome_score."""
        from unittest.mock import patch

        from engines.research_agent import adoption_outcome_score

        proposal_dir = cra_dir / "proposals"
        proposal_dir.mkdir(exist_ok=True)
        spec_file = proposal_dir / "2026-03-14_full_test.md"
        spec_file.write_text(
            "## Research Integration: Trajectory Memory\n\n"
            "Memory retrieval improvement using trajectory pattern matching.\n"
            "Responds to Anthropic native memory API threat.\n"
        )

        proposal = {
            "title": "full test",
            "path": str(spec_file),
            "file": spec_file.name,
            "created": "2026-03-14",
        }

        mock_result = type(
            "Result",
            (),
            {
                "stdout": "95 passed, 5 failed in 3.0s\n",
                "stderr": "",
                "returncode": 1,
            },
        )()

        with patch("subprocess.run", return_value=mock_result):
            result = agent._execute_live_experiment(proposal)

        score = adoption_outcome_score(result)
        # 0.5 * (95/100) + 0.3 * capability_delta + 0.2 * 1.0(threat)
        assert 0.5 < score < 1.0
        assert result.addresses_threat is True
        assert result.capability_score_delta > 0.0
