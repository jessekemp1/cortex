#!/usr/bin/env python3
"""
Agent 9: E2E Validation

Comprehensive end-to-end tests for Week 1 Minimal Viable Intelligence

Test Scenarios:
1. Session context generation
2. Portfolio memory queries
3. Spec knowledge base search
4. Bridge API integration
5. Metrics tracking
6. Data persistence across restarts
7. Performance benchmarks
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

from metrics_tracker import MetricsTracker

# Import all core modules
from portfolio_memory import PortfolioMemory
from session_manager import SessionManager
from spec_knowledge_base import SpecKnowledgeBase


class E2EValidator:
    """End-to-end validation test suite"""

    def __init__(self):
        self.results = {"total_tests": 0, "passed": 0, "failed": 0, "tests": []}
        self.portfolio = None
        self.session = None
        self.specs = None
        self.metrics = None

    def test(self, name: str, test_func):
        """Run a test and record result"""
        self.results["total_tests"] += 1
        print(f"\n{'='*60}")
        print(f"TEST {self.results['total_tests']}: {name}")
        print("=" * 60)

        start_time = time.time()

        try:
            result = test_func()
            elapsed = (time.time() - start_time) * 1000  # ms

            self.results["passed"] += 1
            self.results["tests"].append(
                {
                    "name": name,
                    "status": "PASS",
                    "time_ms": round(elapsed, 1),
                    "result": result,
                }
            )

            print(f"✅ PASS ({elapsed:.1f}ms)")
            return True

        except AssertionError as e:
            elapsed = (time.time() - start_time) * 1000

            self.results["failed"] += 1
            self.results["tests"].append(
                {
                    "name": name,
                    "status": "FAIL",
                    "time_ms": round(elapsed, 1),
                    "error": str(e),
                }
            )

            print(f"❌ FAIL: {e}")
            return False

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000

            self.results["failed"] += 1
            self.results["tests"].append(
                {
                    "name": name,
                    "status": "ERROR",
                    "time_ms": round(elapsed, 1),
                    "error": str(e),
                }
            )

            print(f"💥 ERROR: {e}")
            return False

    def run_all_tests(self):
        """Run complete validation suite"""
        print("=" * 60)
        print("AGENT 9: E2E VALIDATION")
        print("Week 1 Minimal Viable Intelligence - Complete Test Suite")
        print("=" * 60)

        # Test 1: Module imports
        self.test("Module Imports", self.test_imports)

        # Test 2: Session context
        self.test("Session Context Generation", self.test_session_context)

        # Test 3: Portfolio queries
        self.test("Portfolio Memory Queries", self.test_portfolio_queries)

        # Test 4: Spec search
        self.test("Spec Knowledge Base Search", self.test_spec_search)

        # Test 5: Metrics tracking
        self.test("Metrics Tracking", self.test_metrics)

        # Test 6: Data persistence
        self.test("Data Persistence", self.test_persistence)

        # Test 7: Performance benchmarks
        self.test("Performance Benchmarks", self.test_performance)

        # Test 8: Bridge integration
        self.test("Bridge API Integration", self.test_bridge)

        # Test 9: Cross-module queries
        self.test("Cross-Module Queries", self.test_cross_module)

        # Print summary
        self.print_summary()

        return self.results["failed"] == 0

    # === TEST IMPLEMENTATIONS ===

    def test_imports(self) -> str:
        """Test that all modules can be imported"""
        self.portfolio = PortfolioMemory()
        self.session = SessionManager()
        self.specs = SpecKnowledgeBase()
        self.metrics = MetricsTracker()

        assert self.portfolio is not None, "PortfolioMemory failed to initialize"
        assert self.session is not None, "SessionManager failed to initialize"
        assert self.specs is not None, "SpecKnowledgeBase failed to initialize"
        assert self.metrics is not None, "MetricsTracker failed to initialize"

        return "All modules imported successfully"

    def test_session_context(self) -> str:
        """Test session context generation"""
        context = self.session.get_context(format="structured")
        context_data = json.loads(context)

        assert "project" in context_data, "Missing project field"
        assert "git" in context_data, "Missing git field"

        # Check git data structure
        git_data = context_data["git"]
        assert "branch" in git_data, "Missing git branch"
        assert "recent_commits" in git_data, "Missing recent commits"
        assert isinstance(git_data["recent_commits"], list), "recent_commits should be list"

        # Test terminal format
        terminal_context = self.session.get_context(format="terminal")
        assert len(terminal_context) > 0, "Terminal context is empty"

        project_name = context_data.get("project", {}).get("name", "unknown")
        return f"Context generated for project: {project_name}"

    def test_portfolio_queries(self) -> str:
        """Test portfolio memory queries"""
        stats = self.portfolio.get_stats()

        assert "total_projects" in stats, "Missing total_projects"
        assert "by_priority" in stats, "Missing priority breakdown"
        assert "top_technologies" in stats, "Missing tech stack"

        # Verify we have the migrated data
        assert stats["total_projects"] >= 3, f"Expected ≥3 projects, got {stats['total_projects']}"

        return f"Portfolio stats: {stats['total_projects']} projects, {len(stats['top_technologies'])} technologies"

    def test_spec_search(self) -> str:
        """Test spec knowledge base search"""
        count = self.specs.count()
        assert count > 0, "No specs indexed"

        # Test search
        results = self.specs.search("portfolio intelligence", limit=3)
        assert isinstance(results, list), "Search results should be list"
        assert len(results) <= 3, "Should respect limit"

        # Test project listing
        projects = self.specs.list_projects()
        assert len(projects) > 0, "No projects with specs"

        return f"{count} specs indexed across {len(projects)} projects"

    def test_metrics(self) -> str:
        """Test metrics tracking"""
        # Record a test metric
        self.metrics.record_velocity(
            task="E2E Test Task",
            time_without_cortex=10,
            time_with_cortex=2,
            project="Cortex",
            notes="E2E validation test",
        )

        # Get stats
        stats = self.metrics.get_velocity_stats(days=1)
        assert stats["total_tasks"] > 0, "No velocity metrics recorded"

        dashboard = self.metrics.get_dashboard()
        assert "velocity" in dashboard, "Missing velocity metrics"
        assert "mistakes" in dashboard, "Missing mistake metrics"
        assert "calibration" in dashboard, "Missing calibration metrics"
        assert "roi" in dashboard, "Missing ROI metrics"

        return f"Metrics dashboard operational with {stats['total_tasks']} velocity entries"

    def test_persistence(self) -> str:
        """Test that data persists to disk"""
        portfolio_path = Path.home() / ".claude" / "portfolio"

        # Check required files exist
        required_files = [
            "project_index.json",
            "patterns.json",
            "lessons.json",
            "calibration.json",
            "metrics.json",
        ]

        for filename in required_files:
            filepath = portfolio_path / filename
            assert filepath.exists(), f"Missing file: {filename}"

            # Verify it's valid JSON
            with open(filepath, "r") as f:
                data = json.load(f)
                assert data is not None, f"Invalid JSON in {filename}"

        # Check specs index
        specs_index = Path.home() / ".claude" / "specs" / "index.json"
        assert specs_index.exists(), "Missing specs index"

        return f"All {len(required_files) + 1} data files verified"

    def test_performance(self) -> str:
        """Test performance benchmarks"""
        benchmarks = {}

        # Benchmark: Portfolio stats
        start = time.time()
        stats = self.portfolio.get_stats()
        benchmarks["portfolio_stats_ms"] = (time.time() - start) * 1000
        assert (
            benchmarks["portfolio_stats_ms"] < 100
        ), f"Portfolio stats too slow: {benchmarks['portfolio_stats_ms']:.1f}ms"

        # Benchmark: Session context (relaxed to 500ms - git operations variable)
        start = time.time()
        context = self.session.get_context()
        benchmarks["session_context_ms"] = (time.time() - start) * 1000
        assert (
            benchmarks["session_context_ms"] < 500
        ), f"Session context too slow: {benchmarks['session_context_ms']:.1f}ms"

        # Benchmark: Spec search
        start = time.time()
        results = self.specs.search("test query", limit=5)
        benchmarks["spec_search_ms"] = (time.time() - start) * 1000
        assert (
            benchmarks["spec_search_ms"] < 1000
        ), f"Spec search too slow: {benchmarks['spec_search_ms']:.1f}ms"

        # Benchmark: Metrics dashboard
        start = time.time()
        dashboard = self.metrics.get_dashboard()
        benchmarks["metrics_dashboard_ms"] = (time.time() - start) * 1000
        assert (
            benchmarks["metrics_dashboard_ms"] < 100
        ), f"Metrics dashboard too slow: {benchmarks['metrics_dashboard_ms']:.1f}ms"

        perf_summary = ", ".join(f"{k}: {v:.1f}ms" for k, v in benchmarks.items())
        return f"All benchmarks passed - {perf_summary}"

    def test_bridge(self) -> str:
        """Test bridge API integration"""
        import subprocess

        # Test session-context command
        result = subprocess.run(
            ["python3", "bridge.py", "session-context"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, f"session-context failed: {result.stderr}"

        # Test portfolio stats command
        result = subprocess.run(
            ["python3", "bridge.py", "portfolio", "stats"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, f"portfolio stats failed: {result.stderr}"

        return "Bridge API commands working"

    def test_cross_module(self) -> str:
        """Test cross-module integration"""
        # Get data from all modules simultaneously
        session_data = json.loads(self.session.get_context(format="structured"))
        portfolio_data = self.portfolio.get_stats()
        spec_count = self.specs.count()
        metrics_data = self.metrics.get_dashboard()

        # Verify we can access all data
        assert session_data is not None, "Session data failed"
        assert portfolio_data is not None, "Portfolio data failed"
        assert spec_count > 0, "Spec count failed"
        assert metrics_data is not None, "Metrics data failed"

        # Verify data consistency
        project_name = session_data.get("project")
        assert project_name is not None, "No project detected"

        return f"All modules operational for project: {project_name}"

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("E2E VALIDATION SUMMARY")
        print("=" * 60)

        total = self.results["total_tests"]
        passed = self.results["passed"]
        failed = self.results["failed"]
        pass_rate = (passed / total * 100) if total > 0 else 0

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Pass Rate: {pass_rate:.1f}%")

        # Performance summary
        print("\n📊 Performance Summary:")
        for test in self.results["tests"]:
            status_icon = "✅" if test["status"] == "PASS" else "❌"
            print(f"  {status_icon} {test['name']}: {test['time_ms']}ms")

        # Overall status
        print("\n" + "=" * 60)
        if failed == 0:
            print("✅ ALL TESTS PASSED - WEEK 1 CORE COMPLETE")
        else:
            print(f"❌ {failed} TEST(S) FAILED - REVIEW REQUIRED")
        print("=" * 60)

        # Save results
        results_file = Path.home() / "Dev" / "cortex" / "e2e_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\nResults saved: {results_file}")


def main():
    """Run E2E validation"""
    validator = E2EValidator()
    success = validator.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
