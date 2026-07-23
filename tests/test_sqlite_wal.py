"""Shared-store SQLite hardening: WAL + busy_timeout via _connect().

Multiple processes share the cortex SQLite stores (MCP servers per Claude
session, the CLI, the bridge daemon). _connect() must put the database in
WAL mode so a writer doesn't block readers, and set busy_timeout so a
second writer waits instead of instantly raising 'database is locked'.
"""

from __future__ import annotations

import pytest

from intelligence.memory.tiered_memory import _connect as tiered_connect
from intelligence.spec_knowledge_base import _connect as spec_connect


@pytest.mark.parametrize("connect", [tiered_connect, spec_connect], ids=["tiered_memory", "spec_kb"])
def test_connect_enables_wal_and_busy_timeout(tmp_path, connect):
    conn = connect(tmp_path / "store.db")
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        conn.close()


def test_two_connections_can_interleave_writes(tmp_path):
    db = tmp_path / "store.db"
    a = tiered_connect(db)
    b = tiered_connect(db)
    try:
        a.execute("CREATE TABLE t (v TEXT)")
        a.commit()
        # Reader sees the table while the other connection writes (WAL).
        b.execute("INSERT INTO t VALUES ('from-b')")
        b.commit()
        a.execute("INSERT INTO t VALUES ('from-a')")
        a.commit()
        rows = {r[0] for r in b.execute("SELECT v FROM t").fetchall()}
        assert rows == {"from-a", "from-b"}
    finally:
        a.close()
        b.close()
