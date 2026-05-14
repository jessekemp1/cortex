-- Cortex persistent-state schema snapshot.
--
-- Phase 0 deliverable from /root/.claude/plans/can-we-also-run-shimmying-globe.md
-- ("3. signal_bus.db schema. Only persistent state in the system. NO schema
--  changes during slim-down. Add a migration test in Phase 0 that asserts the
--  DDL is unchanged.").
--
-- This file is the source of truth for the signal_bus.db schema. Any change
-- to engines/universal_signal_bus.py:_init_db that affects this DDL MUST also
-- update this file, and must be called out explicitly in the PR.
--
-- Tests using this fixture: tests/contract/test_schema_invariant.py

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
