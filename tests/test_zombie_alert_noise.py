"""Regression tests for zombie-alert noise and MCP bridge timeouts.

Background (2026-07-13 investigation): a third-party daemon leaked 182 zombie
children over 5 days. Cortex amplified this real-but-trivial condition until
`cortex status` was unusable:

  - one CRITICAL anomaly per zombie per scan (172 alerts at once),
  - alert-impact scoring that summed severity over the whole group, so sheer
    volume outranked genuinely severe conditions in STRATEGIC FOCUS,
  - a health score that lost 15 points per zombie (-2730), pinned at 0,
  - an "Auto-kill zombie process" recommendation, which is impossible advice
    (a zombie is already dead; only its parent can reap it).

Separately, every `cortex_intelligence` MCP call timed out by construction:
the MCP server called the bridge with a 5s default timeout against an
endpoint whose measured latency is ~10.6s.

These tests pin the corrected behavior.
"""

from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace

import pytest

from intelligence.process_monitor.analyzer import ProcessAnalyzer
from intelligence.process_monitor.collector import ProcessCollector
from intelligence.process_monitor.models import (
    AnomalyType,
    ProcessCategory,
    ProcessSnapshot,
    ProcessStatus,
    ResourceMetric,
    WasteType,
)
from intelligence.process_monitor.optimizer import ResourceOptimizer
from intelligence.process_monitor.tracker import ProcessTracker


def _metric() -> ResourceMetric:
    return ResourceMetric(
        timestamp=datetime.now(),
        total_cpu_percent=5.0,
        available_memory_mb=8192.0,
        total_memory_mb=16384.0,
        process_count=10,
    )


def _proc(
    pid: int,
    name: str = "proc",
    status: ProcessStatus = ProcessStatus.RUNNING,
    parent_pid: int | None = None,
    category: ProcessCategory = ProcessCategory.OTHER,
) -> ProcessSnapshot:
    return ProcessSnapshot(
        pid=pid,
        name=name,
        category=category,
        cpu_percent=0.0,
        memory_mb=0.0,
        status=status,
        start_time=datetime.now(),
        command=f"/bin/{name}",
        parent_pid=parent_pid,
    )


class FakeCollector(ProcessCollector):
    """In-memory collector — no psutil scans."""

    def __init__(self, processes):
        self._processes = list(processes)

    def collect_snapshot(self):
        return list(self._processes)

    def get_processes_by_category(self, category):
        return [p for p in self._processes if p.category == category]


class FakeTracker(ProcessTracker):
    """In-memory tracker — no SQLite."""

    def __init__(self):
        pass

    def get_utilization_history(self, hours=24):
        return []

    def get_recent_anomalies(self, hours=24):
        return []


def _leaky_process_table():
    """Two leaking parents: one with 50 zombie children, one with 2."""
    processes = [
        _proc(100, name="leaky-daemon"),
        _proc(200, name="security-agent"),
    ]
    processes += [
        _proc(1000 + i, name="bash", status=ProcessStatus.ZOMBIE, parent_pid=100)
        for i in range(50)
    ]
    processes += [
        _proc(2000 + i, name="osqueryd", status=ProcessStatus.ZOMBIE, parent_pid=200)
        for i in range(2)
    ]
    return processes


class TestZombieAnomalyAggregation:
    def _analyzer(self, processes):
        return ProcessAnalyzer(tracker=FakeTracker(), collector=FakeCollector(processes))

    def test_one_anomaly_per_leaking_parent_not_per_zombie(self):
        analyzer = self._analyzer(_leaky_process_table())
        anomalies = analyzer.detect_anomalies(_metric())
        zombie_anomalies = [
            a for a in anomalies if a.anomaly_type == AnomalyType.ZOMBIE_PROCESS
        ]

        assert len(zombie_anomalies) == 2, (
            f"52 zombies from 2 parents must yield 2 anomalies, got {len(zombie_anomalies)}"
        )
        counts = sorted(a.metadata["zombie_count"] for a in zombie_anomalies)
        assert counts == [2, 50]

    def test_zombie_anomaly_is_warning_and_names_the_parent(self):
        analyzer = self._analyzer(_leaky_process_table())
        anomalies = analyzer.detect_anomalies(_metric())
        zombie_anomalies = [
            a for a in anomalies if a.anomaly_type == AnomalyType.ZOMBIE_PROCESS
        ]

        big = next(a for a in zombie_anomalies if a.metadata["zombie_count"] == 50)
        assert big.severity == "WARNING", "inert zombies are not CRITICAL"
        assert "leaky-daemon" in big.description
        assert "restart the parent" in big.description.lower()
        assert big.metadata["parent_pid"] == 100
        assert len(big.metadata["zombie_pids"]) <= 10, "pid sample must be bounded"

    def test_no_zombies_no_zombie_anomalies(self):
        analyzer = self._analyzer([_proc(100, name="healthy")])
        anomalies = analyzer.detect_anomalies(_metric())
        assert not [a for a in anomalies if a.anomaly_type == AnomalyType.ZOMBIE_PROCESS]


class TestHealthScoreZombieCap:
    def test_penalty_capped_regardless_of_zombie_count(self):
        zombies = [
            _proc(1000 + i, name="bash", status=ProcessStatus.ZOMBIE, parent_pid=100)
            for i in range(100)
        ]
        analyzer = ProcessAnalyzer(tracker=FakeTracker(), collector=FakeCollector(zombies))
        score = analyzer.get_process_health_score(ProcessCategory.OTHER)
        # 100 zombies used to cost 1500 points (score pinned at 0); now capped at 30.
        assert score == 70.0

    def test_small_zombie_counts_still_penalized(self):
        zombies = [_proc(1000, name="bash", status=ProcessStatus.ZOMBIE, parent_pid=100)]
        analyzer = ProcessAnalyzer(tracker=FakeTracker(), collector=FakeCollector(zombies))
        score = analyzer.get_process_health_score(ProcessCategory.OTHER)
        assert score == 85.0


class TestZombieWasteRecommendation:
    def test_zombie_waste_is_per_parent_and_never_auto_actionable(self):
        optimizer = ResourceOptimizer(
            collector=FakeCollector(_leaky_process_table()), tracker=FakeTracker()
        )
        waste = optimizer.detect_waste()
        zombie_waste = [w for w in waste if w.waste_type == WasteType.ZOMBIE_PROCESS]

        assert len(zombie_waste) == 2, "one waste item per leaking parent"
        for item in zombie_waste:
            assert item.auto_actionable is False, (
                "a zombie cannot be killed — it is already dead; recommending an "
                "auto-kill is impossible advice"
            )
            assert "restart" in item.recommendation.lower()
            assert "0 MB" in item.resource_cost

    def test_zombie_waste_names_the_parent_process(self):
        optimizer = ResourceOptimizer(
            collector=FakeCollector(_leaky_process_table()), tracker=FakeTracker()
        )
        waste = optimizer.detect_waste()
        zombie_waste = [w for w in waste if w.waste_type == WasteType.ZOMBIE_PROCESS]
        names = {w.process_name for w in zombie_waste}
        assert names == {"leaky-daemon", "security-agent"}


class TestAlertImpactVolumeCap:
    def _impact(self, severities):
        from intelligence.recommendations.smart_generator import (
            SmartRecommendationGenerator,
        )

        alerts = [SimpleNamespace(severity=s) for s in severities]
        return SmartRecommendationGenerator._estimate_alert_impact(None, alerts)

    def test_volume_of_trivial_alerts_does_not_become_high_impact(self):
        # 172 identical low-severity alerts (the zombie flood) must stay low.
        assert self._impact(["low"] * 172) == "low"

    def test_volume_of_medium_alerts_caps_at_medium(self):
        assert self._impact(["medium"] * 200) == "medium"

    def test_few_severe_alerts_still_rank_high(self):
        assert self._impact(["critical", "critical", "critical"]) == "high"
        assert self._impact(["critical", "critical"]) == "high"

    def test_single_critical_is_medium(self):
        assert self._impact(["critical"]) == "medium"


class TestMcpBridgeTimeouts:
    """The MCP proxy timeout must exceed the measured latency of the endpoint
    it fronts (bridge /intelligence/query measured at ~10.6s)."""

    @pytest.fixture()
    def mcp_module(self):
        mcp_server = pytest.importorskip("mcp_server")
        return mcp_server

    @staticmethod
    def _resolve_tool(mcp_module, name):
        fn = getattr(mcp_module, name)
        for attr in ("fn", "__wrapped__", "_fn"):
            wrapped = getattr(fn, attr, None)
            if callable(wrapped):
                return wrapped
        return fn

    def test_intelligence_uses_long_timeout(self, mcp_module, monkeypatch):
        captured = {}

        def fake_post(path, payload, timeout=5.0):
            captured["path"], captured["timeout"] = path, timeout
            return {}

        monkeypatch.setattr(mcp_module, "_bridge_post", fake_post)
        fn = self._resolve_tool(mcp_module, "cortex_intelligence")
        fn(query="q")
        assert captured["path"] == "/intelligence/query"
        assert captured["timeout"] >= 30.0, (
            "bridge intelligence latency is ~10.6s measured; a short proxy "
            "timeout makes every call fail by construction"
        )

    def test_recommendations_and_graph_use_raised_timeouts(self, mcp_module, monkeypatch):
        captured = {}

        def fake_get(path, timeout=3.0):
            captured[path] = timeout
            return {}

        monkeypatch.setattr(mcp_module, "_bridge_get", fake_get)
        self._resolve_tool(mcp_module, "cortex_recommendations")()
        self._resolve_tool(mcp_module, "cortex_graph_query")(node_type="pattern")
        assert captured["/intelligence/recommendations"] >= 15.0
        assert captured["/graph/query?node_type=pattern"] >= 10.0

    def test_graph_query_docstring_only_advertises_real_node_types(self, mcp_module):
        from engines.synthesis import NodeType

        fn = self._resolve_tool(mcp_module, "cortex_graph_query")
        doc = fn.__doc__ or ""
        match = re.search(r"Node types: ([^.\n]+)", doc)
        assert match, "docstring must list supported node types"
        advertised = {t.strip() for t in match.group(1).split(",")}
        valid = {n.value for n in NodeType}
        assert advertised <= valid, (
            f"docstring advertises unsupported node types: {advertised - valid} "
            f"(bridge rejects them with 'Unknown node type')"
        )
