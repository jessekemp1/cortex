"""Tests for seed patterns and behavioral firewall."""

from intelligence.memory.seed_patterns import (
    get_seed_patterns,
    get_categories,
    match_seed_patterns,
)
from intelligence.safety.behavioral_firewall import BehavioralFirewall


def test_seed_patterns_load():
    patterns = get_seed_patterns()
    assert len(patterns) >= 25, f"Expected 25+ seed patterns, got {len(patterns)}"


def test_seed_categories():
    cats = get_categories()
    assert "git" in cats
    assert "testing" in cats
    assert "security" in cats
    assert "agent" in cats
    assert len(cats) >= 8


def test_seed_matching():
    matches = match_seed_patterns("fix the database schema and add migration")
    assert len(matches) > 0
    assert matches[0].id == "seed:git:uncommitted-migration"


def test_seed_matching_no_match():
    matches = match_seed_patterns("hello world")
    assert len(matches) == 0


def test_firewall_force_push():
    fw = BehavioralFirewall()
    warnings = fw.check_command("git push --force origin main")
    assert len(warnings) == 1
    assert warnings[0].severity == "critical"
    assert "force" in warnings[0].pattern_name.lower()


def test_firewall_safe_command():
    fw = BehavioralFirewall()
    warnings = fw.check_command("npm install express")
    assert len(warnings) == 0


def test_firewall_destructive():
    fw = BehavioralFirewall()
    warnings = fw.check_command("rm -rf data/")
    assert len(warnings) >= 1
    assert warnings[0].severity == "high"


def test_pattern_indexer_seed_fallback():
    """Verify load_patterns falls back to seeds when cache is empty."""
    from intelligence.memory.pattern_indexer import PatternIndexer
    from pathlib import Path
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Isolate the decisions source (now a first-class load_patterns input)
        # to the tmpdir so the global ~/.cortex/decisions.jsonl can't leak in.
        prev_home = os.environ.get("CORTEX_HOME")
        os.environ["CORTEX_HOME"] = tmpdir
        try:
            indexer = PatternIndexer(Path(tmpdir), cache_dir=Path(tmpdir) / "cache")
            patterns = indexer.load_patterns(include_seeds=True)
            assert len(patterns) >= 25, f"Expected seed patterns, got {len(patterns)}"
            assert patterns[0].project == "cortex-seeds"

            # Without seeds should be empty
            patterns_no_seed = indexer.load_patterns(include_seeds=False)
            assert len(patterns_no_seed) == 0
        finally:
            if prev_home is None:
                os.environ.pop("CORTEX_HOME", None)
            else:
                os.environ["CORTEX_HOME"] = prev_home


if __name__ == "__main__":
    test_seed_patterns_load()
    test_seed_categories()
    test_seed_matching()
    test_seed_matching_no_match()
    test_firewall_force_push()
    test_firewall_safe_command()
    test_firewall_destructive()
    test_pattern_indexer_seed_fallback()
    print("All tests passed!")
