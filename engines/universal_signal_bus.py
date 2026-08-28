"""
Universal Signal Bus

Routes WorkspaceSignal objects from any tool source to all three V2 Prime
engines simultaneously. The connective tissue for Sprint 2.

Architecture:
    UniversalSignalBus
    ├── Fan-out to WorkstreamOrchestrator.record_signal()
    ├── Fan-out to SynthesisCore.query() (via process path)
    └── Event log → SQLite at ~/.cortex/signal_bus.db

The bus never blocks signal ingestion — all engine errors are caught and logged.
Tools that cannot import Python can POST to bridge /signal/absorb.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from cortex.engines.workstream_orchestrator import (
        WorkspaceSignal,
        WorkstreamOrchestrator,
    )
    from cortex.engines.synthesis import SynthesisCore
except ImportError:
    from .workstream_orchestrator import WorkspaceSignal, WorkstreamOrchestrator
    from .synthesis import SynthesisCore


class UniversalSignalBus:
    """
    Fan-out bus: routes signals from any source to all three engines.

    Usage:
        bus = UniversalSignalBus()
        bus.absorb(signal)                       # Fan-out to all engines
        ctx = bus.query("auth issue", "vortex")  # Pull context for a tool
        patterns = bus.get_cross_project_patterns("cortex")  # Cross-project
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "signal_bus.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Lazy-initialized engine references
        self._orchestrator: Optional[WorkstreamOrchestrator] = None
        self._synthesis: Optional[SynthesisCore] = None

        self._init_db()

    # ─── Engine Access (lazy) ────────────────────────────────

    def _get_orchestrator(self) -> WorkstreamOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = WorkstreamOrchestrator()
        return self._orchestrator

    def _get_synthesis(self) -> SynthesisCore:
        if self._synthesis is None:
            self._synthesis = SynthesisCore()
        return self._synthesis

    # ─── Public Interface ────────────────────────────────────

    def absorb(self, signal: WorkspaceSignal) -> None:
        """Fan-out a signal to all three engines.

        Never raises — all engine errors are silently caught and logged.
        The event is always written to the bus log.
        """
        self._log_event(signal)

        # Engine 1: WorkstreamOrchestrator
        try:
            self._get_orchestrator().record_signal(signal)
        except Exception as e:
            logger.warning("orchestrator fan-out failed: %s", e)

        # Engine 2: SynthesisCore — register as a pattern node if content is rich
        try:
            self._maybe_register_in_graph(signal)
        except Exception as e:
            logger.warning("synthesis fan-out failed: %s", e)

    def query(
        self,
        context: str,
        project: str,
        tool_source: str = "unknown",
    ) -> Dict[str, Any]:
        """Pull relevant context for any tool.

        Queries synthesis graph + trust summary + recent signals.
        Returns an empty-safe dict — never raises.
        """
        result: Dict[str, Any] = {
            "context": context,
            "project": project,
            "tool_source": tool_source,
            "timestamp": datetime.now().isoformat(),
            "graph_nodes": [],
            "recent_signals": [],
            "trust": {},
        }

        try:
            synthesis = self._get_synthesis()
            graph_result = synthesis.query(context)
            result["graph_nodes"] = graph_result.get("nodes", [])[:5]
        except Exception as e:
            logger.warning("synthesis query failed: %s", e)

        try:
            orchestrator = self._get_orchestrator()
            recent = orchestrator.get_recent_signals(project=project, limit=10)
            result["recent_signals"] = [
                {
                    "source": s.source.value,
                    "type": s.content_type,
                    "content": s.content[:200],
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in recent
            ]
            trust_summary = orchestrator.get_trust_summary()
            result["trust"] = trust_summary.get("domains", {})
        except Exception as e:
            logger.warning("orchestrator query failed: %s", e)

        return result

    def get_cross_project_patterns(
        self,
        active_project: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Surface patterns from other projects relevant to current work.

        Searches the synthesis graph for pattern/lesson nodes that belong
        to a different project than the one currently active.
        Returns at most `limit` results.
        """
        patterns: List[Dict[str, Any]] = []
        graph = None

        try:
            synthesis = self._get_synthesis()
            graph = synthesis.graph

            from cortex.engines.synthesis import NodeType
        except ImportError:
            try:
                from .synthesis import NodeType
            except ImportError:
                return patterns
        except Exception as e:
            logger.warning("cross-project patterns failed: %s", e)
            return patterns

        # Relevance gate (added 2026-08-28, briefing redesign — dec_7422762e0f7b):
        # for a customer-account (DSA) query, only surface patterns from OTHER
        # DSA accounts. Cortex-internal dev projects (vortex, dev, alpha_arena,
        # winfield, ...) must not leak into an account-scoped query — that noise
        # ("Alpha Arena", "Backend Tests", "Mock patch namespace") made
        # cross_project_patterns unusable for DSA work. Non-DSA (internal-dev)
        # active projects keep the prior all-other-projects behavior.
        DSA_ACCOUNTS = {
            "interac", "manulife-genie", "manulife", "manulife-lakebase",
            "manulife-vietnam", "clio", "clio-genie-workshop", "twin",
        }
        active_is_dsa = active_project in DSA_ACCOUNTS

        if graph is None:
            return patterns

        try:
            for node in graph.nodes.values():
                if node.type not in (NodeType.PATTERN, NodeType.LESSON):
                    continue

                node_project = node.data.get("project", "")
                if not node_project or node_project == active_project:
                    continue

                # DSA account query: restrict cross-project learnings to other
                # DSA accounts; never surface Cortex-internal dev patterns.
                if active_is_dsa and node_project not in DSA_ACCOUNTS:
                    continue

                patterns.append(
                    {
                        "pattern": node.name,
                        "project_source": node_project,
                        "node_type": node.type.value,
                        "summary": str(node.data.get("description", node.name))[:200],
                        "node_id": node.id,
                    }
                )

            return patterns[:limit]
        except Exception as e:
            logger.warning("pattern iteration failed: %s", e)
            return patterns

    def get_bus_stats(self) -> Dict[str, Any]:
        """Return bus event log statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM bus_events"
            ).fetchone()
            conn.close()
            return {
                "total_events": row[0],
                "first_event": row[1],
                "last_event": row[2],
            }
        except Exception as e:
            return {"error": str(e)}

    # ─── Internal Helpers ────────────────────────────────────

    def _maybe_register_in_graph(self, signal: WorkspaceSignal) -> None:
        """Register high-confidence signals as graph nodes."""
        if signal.confidence < 0.6:
            return
        if signal.content_type not in ("insight", "decision", "pattern"):
            return

        synthesis = self._get_synthesis()

        try:
            from cortex.engines.synthesis import Node, NodeType
        except ImportError:
            from .synthesis import Node, NodeType


        node_id = f"signal:{signal.signal_id}"
        if node_id in synthesis.graph.nodes:
            return

        node = Node(
            id=node_id,
            type=NodeType.PATTERN,
            name=signal.content[:60],
            data={
                "project": signal.project,
                "source": signal.source.value,
                "content": signal.content,
                "confidence": signal.confidence,
                "timestamp": signal.timestamp.isoformat(),
            },
        )
        synthesis.graph.add_node(node)

    def _log_event(self, signal: WorkspaceSignal) -> None:
        """Write signal to bus event log."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR IGNORE INTO bus_events
                (signal_id, source, project, content_type, content, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.signal_id,
                    signal.source.value,
                    signal.project,
                    signal.content_type,
                    signal.content[:500],
                    signal.confidence,
                    signal.timestamp.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("bus event log failed: %s", e)

    def _init_db(self) -> None:
        """Initialize the bus event log database."""
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bus_events (
                signal_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                project TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT,
                confidence REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_bus_project ON bus_events(project);
            CREATE INDEX IF NOT EXISTS idx_bus_timestamp ON bus_events(timestamp);
            """
        )
        conn.close()
