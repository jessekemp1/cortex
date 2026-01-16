"""Tests for typed memory store."""

import tempfile
from pathlib import Path

import pytest
from cortex.v2.memory.store import TypedMemoryStore
from cortex.v2.memory.types import Decision, Incident, Pattern, Skill


@pytest.fixture
def store():
    """Create a temporary memory store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        s = TypedMemoryStore(data_dir=Path(tmpdir))
        yield s


class TestTypedMemoryStore:
    """Test TypedMemoryStore class."""

    def test_add_pattern(self, store):
        """Test adding a pattern."""
        pattern = Pattern.create(
            title="Redis Caching",
            problem="Slow API responses",
            solution="Use Redis for caching",
            projects=["VortexV2"],
        )

        result = store.add(pattern)
        assert result.id == pattern.id
        assert len(store.patterns) == 1

    def test_add_skill(self, store):
        """Test adding a skill."""
        skill = Skill.create(
            title="Deploy to Production",
            steps=["Run tests", "Build image", "Push to registry", "Deploy"],
            prerequisites=["All tests passing", "Staging verified"],
            projects=["VortexV2"],
        )

        result = store.add(skill)
        assert result.id == skill.id
        assert len(store.skills) == 1

    def test_add_incident(self, store):
        """Test adding an incident."""
        incident = Incident.create(
            title="Redis Connection Exhaustion",
            what_happened="API started timing out",
            root_cause="Connection pool limit too low",
            resolution="Increased pool size from 10 to 50",
            severity="major",
            projects=["VortexV2"],
        )

        result = store.add(incident)
        assert len(store.incidents) == 1

    def test_add_decision(self, store):
        """Test adding a decision."""
        decision = Decision.create(
            title="Database Choice",
            question="Which database for VortexV2?",
            chosen_option="PostgreSQL",
            alternatives=["MySQL", "MongoDB"],
            rationale="Better JSON support and PostGIS for geo queries",
            projects=["VortexV2"],
        )

        result = store.add(decision)
        assert len(store.decisions) == 1

    def test_get_memory(self, store):
        """Test retrieving a memory by ID."""
        pattern = Pattern.create(title="Test Pattern", problem="Test", solution="Test")
        store.add(pattern)

        retrieved = store.get(pattern.id)
        assert retrieved is not None
        assert retrieved.title == "Test Pattern"

    def test_delete_memory(self, store):
        """Test deleting a memory."""
        pattern = Pattern.create(title="Test", problem="Test", solution="Test")
        store.add(pattern)
        assert len(store.patterns) == 1

        assert store.delete(pattern.id)
        assert len(store.patterns) == 0

    def test_query_by_type(self, store):
        """Test querying by memory type."""
        store.add(Pattern.create("P1", "Problem", "Solution"))
        store.add(Skill.create("S1", ["Step 1"]))
        store.add(Incident.create("I1", "What", "Cause", "Resolution"))

        patterns = store.query("anything", types=["pattern"])
        skills = store.query("anything", types=["skill"])
        incidents = store.query("anything", types=["incident"])

        # Results depend on matching, but should filter by type
        assert all(isinstance(m, Pattern) for m in patterns)
        assert all(isinstance(m, Skill) for m in skills)
        assert all(isinstance(m, Incident) for m in incidents)

    def test_query_intent_detection_how_to(self, store):
        """Test intent detection for how-to queries."""
        store.add(Skill.create(title="Deploy Application", steps=["Build", "Test", "Deploy"]))
        store.add(
            Pattern.create(title="Deploy Pattern", problem="Need to deploy", solution="Use CI/CD")
        )

        # "How do I" should return skills and patterns
        detected = store._detect_intent("how do i deploy")
        assert "skill" in detected
        assert "pattern" in detected

    def test_query_intent_detection_why(self, store):
        """Test intent detection for why queries."""
        detected = store._detect_intent("why did we choose postgres")
        assert "decision" in detected
        assert "incident" in detected

    def test_query_intent_detection_what_happened(self, store):
        """Test intent detection for incident queries."""
        detected = store._detect_intent("what went wrong yesterday")
        assert "incident" in detected

    def test_query_by_project(self, store):
        """Test filtering by project."""
        store.add(
            Pattern.create(title="Pattern A", problem="P", solution="S", projects=["VortexV2"])
        )
        store.add(
            Pattern.create(title="Pattern B", problem="P", solution="S", projects=["AlphaArena"])
        )

        results = store.query("pattern", projects=["VortexV2"])
        assert len(results) == 1
        assert results[0].title == "Pattern A"

    def test_find_pattern(self, store):
        """Test finding a specific pattern."""
        store.add(
            Pattern.create(
                title="Redis Caching",
                problem="Slow API responses",
                solution="Use Redis",
            )
        )

        pattern = store.find_pattern("slow api")
        assert pattern is not None
        assert "Redis" in pattern.title

    def test_find_skill(self, store):
        """Test finding a specific skill."""
        store.add(Skill.create(title="Deploy to Production", steps=["Build", "Deploy"]))

        skill = store.find_skill("deploy")
        assert skill is not None
        assert "Deploy" in skill.title

    def test_stats(self, store):
        """Test store statistics."""
        store.add(Pattern.create("P1", "Problem", "Solution", projects=["A"]))
        store.add(Pattern.create("P2", "Problem", "Solution", projects=["B"]))
        store.add(Skill.create("S1", ["Step"], projects=["A"]))

        stats = store.stats()
        assert stats["total"] == 3
        assert stats["patterns"] == 2
        assert stats["skills"] == 1
        assert stats["by_project"]["A"] == 2
        assert stats["by_project"]["B"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
