"""
Schema invariant: signal_bus.db DDL must not drift during the slim-down.

This is the only persistent state in the cortex system. The slim-down plan
(Phases 1-6) explicitly forbids schema changes. This test compares the
fixture in tests/fixtures/cortex_state.sql against the live DDL produced
by engines/universal_signal_bus.UniversalSignalBus._init_db.

If this test fails, EITHER:
  (a) the schema was changed intentionally — update cortex_state.sql AND
      flag the change in the PR description, OR
  (b) the schema drifted accidentally — fix universal_signal_bus.py.

Either way, don't silently update the fixture.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from engines.universal_signal_bus import UniversalSignalBus

FIXTURE = Path(__file__).parent.parent / "fixtures" / "cortex_state.sql"


def _statements(sql: str) -> set[str]:
    """Split SQL into a normalized, order-independent set of statements.

    Strips comments, collapses whitespace, removes 'IF NOT EXISTS' (SQLite
    drops it from stored DDL), and upper-cases for case-insensitive
    comparison. Returns a set so statement order in the fixture doesn't matter.
    """
    sql = re.sub(r"--[^\n]*", "", sql)
    out = set()
    for stmt in sql.split(";"):
        stmt = re.sub(r"\bIF NOT EXISTS\b", "", stmt, flags=re.IGNORECASE)
        stmt = re.sub(r"\s+", " ", stmt).strip().upper()
        if stmt:
            out.add(stmt)
    return out


def test_signal_bus_ddl_matches_fixture(tmp_path):
    """The schema produced by UniversalSignalBus._init_db must equal the fixture."""
    db_path = tmp_path / "signal_bus.db"
    UniversalSignalBus(db_path=db_path)  # triggers _init_db

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') AND sql IS NOT NULL "
            "ORDER BY type, name"
        ).fetchall()
    finally:
        conn.close()

    live_ddl = "\n".join(r[0] + ";" for r in rows)
    expected_ddl = FIXTURE.read_text()

    live = _statements(live_ddl)
    expected = _statements(expected_ddl)

    missing = expected - live
    extra = live - expected
    assert not missing and not extra, (
        "signal_bus.db schema drifted from fixture.\n"
        f"Missing from live DB: {missing}\n"
        f"Extra in live DB: {extra}\n"
        "If this change is intentional, update tests/fixtures/cortex_state.sql "
        "AND mention it explicitly in the PR description."
    )
