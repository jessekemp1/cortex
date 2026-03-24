#!/usr/bin/env python3
"""
Add missing indices to existing Cortex SQLite databases.

Run this once to optimize query performance across all databases.
Safe to run multiple times (uses CREATE INDEX IF NOT EXISTS).
"""

import sqlite3
from pathlib import Path

from cortex.state_paths import get_cortex_dir


def add_missing_indices() -> dict:
    """
    Add missing indices to all Cortex SQLite databases.

    Returns dict of {db_name: [indices_added]}.
    """
    cortex_dir = get_cortex_dir()
    results = {}

    # 1. subscriptions/utilization.db
    util_db = cortex_dir / "subscriptions" / "utilization.db"
    if util_db.exists():
        indices = []
        with sqlite3.connect(util_db) as conn:
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_token_usage(date)",
                "CREATE INDEX IF NOT EXISTS idx_daily_usage_provider ON daily_token_usage(provider)",
                "CREATE INDEX IF NOT EXISTS idx_waste_date ON waste_events(date)",
                "CREATE INDEX IF NOT EXISTS idx_waste_type ON waste_events(waste_type)",
            ]:
                try:
                    conn.execute(idx_sql)
                    indices.append(idx_sql.split("idx_")[1].split(" ON")[0])
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        results["utilization.db"] = indices

    # 2. subscriptions/learning.db
    learn_db = cortex_dir / "subscriptions" / "learning.db"
    if learn_db.exists():
        indices = []
        with sqlite3.connect(learn_db) as conn:
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_routing_timestamp ON routing_observations(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_suggestion_timestamp ON suggestion_observations(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_pacing_date ON daily_pacing(date)",
                "CREATE INDEX IF NOT EXISTS idx_policies_expires ON learned_policies(expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_policies_type ON learned_policies(policy_type)",
            ]:
                try:
                    conn.execute(idx_sql)
                    indices.append(idx_sql.split("idx_")[1].split(" ON")[0])
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        results["learning.db"] = indices

    # 3. ensemble/decisions.db
    dec_db = cortex_dir / "ensemble" / "decisions.db"
    if dec_db.exists():
        indices = []
        with sqlite3.connect(dec_db) as conn:
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON ensemble_decisions(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_decisions_outcome ON ensemble_decisions(outcome)",
                "CREATE INDEX IF NOT EXISTS idx_decisions_model ON ensemble_decisions(model_tier)",
            ]:
                try:
                    conn.execute(idx_sql)
                    indices.append(idx_sql.split("idx_")[1].split(" ON")[0])
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        results["decisions.db"] = indices

    # 4. ensemble/expertise.db
    exp_db = cortex_dir / "ensemble" / "expertise.db"
    if exp_db.exists():
        indices = []
        with sqlite3.connect(exp_db) as conn:
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_predictions_domain ON predictions(domain)",
                "CREATE INDEX IF NOT EXISTS idx_predictions_correct ON predictions(was_correct)",
                "CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp)",
            ]:
                try:
                    conn.execute(idx_sql)
                    indices.append(idx_sql.split("idx_")[1].split(" ON")[0])
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        results["expertise.db"] = indices

    # 5. ensemble/temporal.db
    temp_db = cortex_dir / "ensemble" / "temporal.db"
    if temp_db.exists():
        indices = []
        with sqlite3.connect(temp_db) as conn:
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_temporal_timestamp ON temporal_classifications(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_temporal_horizon ON temporal_classifications(horizon)",
                "CREATE INDEX IF NOT EXISTS idx_temporal_outcome ON temporal_classifications(outcome)",
            ]:
                try:
                    conn.execute(idx_sql)
                    indices.append(idx_sql.split("idx_")[1].split(" ON")[0])
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        results["temporal.db"] = indices

    # 6. working_memory.db — already has idx_last_accessed
    wm_db = cortex_dir / "working_memory.db"
    if wm_db.exists():
        indices = []
        with sqlite3.connect(wm_db) as conn:
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_wm_outcome ON memory_items(outcome)",
            ]:
                try:
                    conn.execute(idx_sql)
                    indices.append(idx_sql.split("idx_")[1].split(" ON")[0])
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        results["working_memory.db"] = indices

    return results


if __name__ == "__main__":
    results = add_missing_indices()
    for db, indices in results.items():
        print(f"{db}: {len(indices)} indices added/verified")
        for idx in indices:
            print(f"  - {idx}")
