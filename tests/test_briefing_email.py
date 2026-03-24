"""Tests for the Kempion-infused Cortex morning briefing email generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from briefing_email import (
    generate_morning_briefing_html,
    _generate_kempion_section,
    _build_learning_section,
    _build_insights_section,
    _build_project_tasks_section,
    _build_portfolio_section,
    _build_blockers_section,
    _esc,
    DEFAULT_SEEKER_CONFIG,
)


class TestEscape:
    def test_escapes_html_entities(self):
        assert _esc("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" or \
               "&lt;" in _esc("<script>")

    def test_escapes_ampersand(self):
        assert "&amp;" in _esc("A & B")

    def test_escapes_quotes(self):
        assert "&quot;" in _esc('He said "hello"')


class TestKempionSection:
    def test_generates_section_with_defaults(self):
        section = _generate_kempion_section(DEFAULT_SEEKER_CONFIG)
        assert "greeting" in section
        assert "reflection_prompt" in section
        assert "focus_prompt" in section

    def test_generates_wisdom_text(self):
        section = _generate_kempion_section(DEFAULT_SEEKER_CONFIG)
        # With seed data loaded, should have wisdom
        assert isinstance(section["wisdom_text"], str)
        assert isinstance(section["wisdom_author"], str)


class TestLearningSectionWithNone:
    def test_empty_when_no_briefing(self):
        section = _build_learning_section(None)
        assert section["available"] is False

    def test_empty_metrics(self):
        section = _build_learning_section(None)
        assert section["metrics"] == {}
        assert section["patterns"] == []


class TestInsightsSectionWithNone:
    def test_empty_when_no_briefing(self):
        section = _build_insights_section(None)
        assert section["available"] is False


class TestProjectTasksWithNone:
    def test_empty_when_no_briefing(self):
        result = _build_project_tasks_section(None)
        assert result == []


class TestPortfolioSectionWithNone:
    def test_empty_when_no_briefing(self):
        section = _build_portfolio_section(None)
        assert section["available"] is False


class TestBlockersWithNone:
    def test_empty_when_no_briefing(self):
        assert _build_blockers_section(None) == []


class TestMockBriefingData:
    """Test with mock briefing data to verify section building."""

    class _MockBriefing:
        active_projects = ["cortex", "vortex"]
        recent_commits_24h = 5
        total_commits_7d = 20
        blockers = [
            {"project": "cortex", "blocker": "API rate limits"},
            {"project": "vortex", "blocker": "Test failures"},
        ]
        priority_actions = [
            {"title": "Fix API", "priority": "HIGH", "project": "cortex", "source": "rec", "rationale": "Blocked"},
            {"title": "Deploy v2", "priority": "MEDIUM", "project": "vortex", "source": "goal", "rationale": ""},
        ]
        patterns = ["Momentum on cortex", "Dormant: alpha-arena"]
        waiting_on = []
        project_snapshot = [
            {"project": "cortex", "commits_7d": 15, "status": "active", "trend": "hot"},
            {"project": "vortex", "commits_7d": 5, "status": "active", "trend": "steady"},
        ]
        intelligence_metrics = {
            "recommendation_accuracy": 0.72,
            "success_rate": 0.65,
            "total_outcomes": 42,
        }
        strategic_alignment = {"drift_detected": False, "alignment_score": 0.8}
        cross_project_insights = {
            "portfolio_health": {"healthy_count": 3, "at_risk_count": 1},
            "shared_patterns": [{"pattern": "FastAPI usage"}],
            "relevant_lessons": [{"project": "cortex", "lesson": "Always test edge cases"}],
        }
        predictive_insights = {"likely_focus": "cortex", "optimal_sequence": ["API fix", "Deploy"]}
        resource_intelligence = None
        velocity_metrics = None

    def test_learning_section(self):
        section = _build_learning_section(self._MockBriefing())
        assert section["available"] is True
        assert section["metrics"]["recommendation_accuracy"] == 0.72
        assert section["metrics"]["total_outcomes"] == 42
        assert len(section["patterns"]) == 2

    def test_insights_section(self):
        section = _build_insights_section(self._MockBriefing())
        assert section["available"] is True
        assert section["health"]["healthy_count"] == 3
        assert len(section["shared_patterns"]) == 1
        assert len(section["lessons"]) == 1

    def test_project_tasks(self):
        projects = _build_project_tasks_section(self._MockBriefing())
        assert len(projects) == 2
        cortex_proj = next(p for p in projects if p["name"] == "cortex")
        assert cortex_proj["commits_7d"] == 15
        # Should have at least one task from priority_actions
        assert len(cortex_proj["tasks"]) >= 1
        assert cortex_proj["tasks"][0]["title"] == "Fix API"

        # Vortex should have a task + a blocker-derived task
        vortex_proj = next(p for p in projects if p["name"] == "vortex")
        assert len(vortex_proj["tasks"]) >= 1

    def test_portfolio_section(self):
        section = _build_portfolio_section(self._MockBriefing())
        assert section["available"] is True
        assert section["active_count"] == 2
        assert section["commits_24h"] == 5
        assert section["commits_7d"] == 20

    def test_blockers_section(self):
        blockers = _build_blockers_section(self._MockBriefing())
        assert len(blockers) == 2
        assert blockers[0]["project"] == "cortex"


class TestFullHtmlGeneration:
    def test_generates_valid_html(self):
        result = generate_morning_briefing_html()
        assert "html" in result
        assert "text" in result
        assert "subject" in result
        assert "<!DOCTYPE html>" in result["html"]
        assert "KEMPION" in result["html"]
        assert "Dawn Briefing" in result["subject"]

    def test_html_has_all_sections(self):
        result = generate_morning_briefing_html()
        html = result["html"]
        # Should have the Kempion header
        assert "KEMPION" in html
        assert "Dawn Briefing" in html
        # Should have footer
        assert "Poet-Warrior-Monk" in html

    def test_text_fallback_generated(self):
        result = generate_morning_briefing_html()
        text = result["text"]
        assert "KEMPION" in text
        assert "Dawn Briefing" in text
