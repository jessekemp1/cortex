"""Registry of the data stores Cortex reads, with an owner and a freshness rule.

`project_index.json` was read confidently for three months after its last write
because nothing declared who was supposed to maintain it or how fresh it had to
be. This registry makes both explicit, so `cortex doctor` can turn silent rot
into a visible check instead of a post-mortem.

Two honesty rules are encoded in the data, not left to a comment:

  * Every store names a `writer`. A store whose writer is WRITER_NONE is a
    declared bug — something reads it and nothing maintains it. The doctor
    check fails on that regardless of age.

  * A store is either event-driven or regenerated. An event-driven store
    (an append-on-work journal like decisions.jsonl) has NO age SLA: a quiet
    day is not rot, and alerting on it would be exactly the false-positive this
    whole effort exists to remove. A regenerated store (an index or snapshot
    that must be rebuilt on a cadence) has a `max_age_days` SLA AND must have a
    scheduler; a regenerated store with `scheduled=False` is a rot risk the
    doctor reports as a warning even while it is still within SLA, because it
    will drift the moment attention moves elsewhere — which is what happened.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

WRITER_NONE = "NONE"


def _cortex_dir() -> Path:
    return Path.home() / ".cortex"


def _portfolio_dir() -> Path:
    return Path.home() / ".claude" / "portfolio"


@dataclass(frozen=True)
class Store:
    """One data store Cortex depends on.

    name:         short identifier used in check output.
    path:         absolute path on disk.
    writer:       dotted name of the function/agent that maintains it, or
                  WRITER_NONE to declare "nothing maintains this" as a bug.
    consumers:    what reads it (for the human reading a failure).
    event_driven: True = appended when work happens; no age SLA.
                  False = regenerated on a cadence; age SLA applies.
    max_age_days: SLA for regenerated stores. Ignored when event_driven.
    scheduled:    True if a scheduler/hook regenerates it automatically.
                  A regenerated store with scheduled=False will rot.
    """

    name: str
    path: Path
    writer: str
    consumers: str
    event_driven: bool
    max_age_days: Optional[float] = None
    scheduled: bool = True

    def age_days(self) -> Optional[float]:
        """Days since last write, or None if the file is absent."""
        try:
            return (time.time() - self.path.stat().st_mtime) / 86400
        except OSError:
            return None


def registry() -> List[Store]:
    """The stores a live Cortex consumer reads. Grounded in what exists.

    Kept deliberately small: only stores something actually reads at runtime,
    so a failure here always means a real consumer is affected, never a
    housekeeping file nobody depends on.
    """
    cx = _cortex_dir()
    return [
        Store(
            name="decisions",
            path=cx / "decisions.jsonl",
            writer="mcp_handlers.record_decision",
            consumers="cortex_intelligence, cortex_outcomes, recall",
            event_driven=True,
        ),
        Store(
            name="outcomes",
            path=cx / "outcomes.jsonl",
            writer="feedback.FeedbackLogger / mcp_handlers.read_outcomes",
            consumers="cortex_outcomes, recommendations",
            event_driven=True,
        ),
        Store(
            name="embedding_index",
            path=cx / "patterns" / "embeddings_meta.pkl",
            writer="intelligence.memory.hybrid_retriever",
            consumers="cortex_intelligence semantic recall",
            event_driven=False,
            max_age_days=30.0,
            scheduled=True,  # rebuilt lazily on query when decisions.jsonl grows
        ),
        Store(
            name="graph_nodes",
            path=cx / "graph" / "nodes.json",
            writer="bridge_intelligence / engines.synthesis",
            consumers="cortex_intelligence applicable_patterns, lessons",
            event_driven=True,
        ),
        Store(
            name="project_index",
            path=_portfolio_dir() / "project_index.json",
            writer="portfolio_memory.refresh_index",
            consumers="portfolio health, cortex_projects, recommendations",
            event_driven=False,
            max_age_days=30.0,
            # No scheduler writes this file — it is refreshed only when a human
            # runs portfolio_memory.refresh_index (it rotted 3.5 months once).
            # Declared honestly: an unscheduled store past its SLA is a WARN that
            # tells the human to refresh, not a hard FAIL (see evaluate()). An
            # auto-refresh in the maintenance job was rejected: that job runs
            # under launchd with no CORTEX_ROOT_DIR, so it would rebuild the
            # index against the wrong workspace root and corrupt it every cycle.
            scheduled=False,
        ),
    ]


@dataclass(frozen=True)
class StoreStatus:
    store: Store
    exists: bool
    age_days: Optional[float]
    problems: List[str] = field(default_factory=list)   # hard failures
    warnings: List[str] = field(default_factory=list)   # advisory, not a failure

    @property
    def ok(self) -> bool:
        """No hard failures. A warning does not make a store not-ok."""
        return not self.problems


def evaluate(stores: Optional[List[Store]] = None) -> List[StoreStatus]:
    """Assess each store against its own rules. Pure over the registry + disk.

    problems are hard failures (missing, past SLA, no writer). warnings are
    advisory: a real risk that has not yet materialised. The split exists so a
    within-SLA-but-unscheduled store surfaces its drift risk WITHOUT turning the
    doctor permanently red — the same absent-vs-broken distinction the honesty
    work is built on, applied to the monitor itself.
    """
    stores = stores if stores is not None else registry()
    out: List[StoreStatus] = []
    for s in stores:
        problems: List[str] = []
        warnings: List[str] = []
        age = s.age_days()
        exists = age is not None

        if s.writer == WRITER_NONE:
            problems.append("no writer declared — something reads a store nothing maintains")

        if not exists:
            problems.append(f"missing at {s.path}")
        elif not s.event_driven:
            past_sla = (
                s.max_age_days is not None and age is not None and age > s.max_age_days
            )
            if past_sla and s.scheduled:
                # A store its own scheduler is supposed to keep fresh is stale:
                # the scheduler is broken. Hard fail — someone must fix it.
                problems.append(
                    f"stale: {age:.1f}d old, SLA {s.max_age_days:.0f}d — scheduler is not keeping it fresh"
                )
            elif past_sla and not s.scheduled:
                # No scheduler by design: staleness is expected maintenance, not
                # a broken pipeline. WARN with the exact action, rather than a
                # hard FAIL that would sit red until someone gave up reading it.
                warnings.append(
                    f"stale: {age:.1f}d old, SLA {s.max_age_days:.0f}d — run {s.writer}"
                )
            elif not s.scheduled:
                warnings.append(f"no scheduler — will drift; refresh via {s.writer}")

        out.append(
            StoreStatus(
                store=s, exists=exists, age_days=age, problems=problems, warnings=warnings
            )
        )
    return out
