"""
CortexDBx Python SDK.

Works with local in-memory backend (for dev/tests) or Spark/Delta (Databricks).
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
import hashlib
from datetime import datetime
import uuid


@dataclass
class CortexDBxConfig:
    """Configuration for CortexDBx client."""

    catalog: str = "cortex_catalog"
    schema: str = "cortex_mvp"
    use_local_backend: bool = True


class LocalBackend:
    """In-memory backend for dev and testing."""

    def __init__(self) -> None:
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.strategies: Dict[str, Dict[str, Any]] = {}
        self.outcomes: List[Dict[str, Any]] = []
        self._calibration: Dict[tuple, Dict[str, Any]] = {}

    def ensure_context(self, context_id: str, context_hash: str, domain: str, factors: str) -> str:
        if context_id not in self.contexts:
            self.contexts[context_id] = {
                "context_id": context_id,
                "context_hash": context_hash,
                "domain": domain,
                "factors": factors,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
        return context_id

    def ensure_strategy(self, strategy_id: str, name: str, domain: str) -> str:
        if strategy_id not in self.strategies:
            self.strategies[strategy_id] = {
                "strategy_id": strategy_id,
                "name": name,
                "domain": domain,
                "created_at": datetime.now().isoformat(),
            }
        return strategy_id

    def append_outcome(self, outcome: Dict[str, Any]) -> None:
        self.outcomes.append(outcome)
        ctx = outcome["context_id"]
        strat = outcome["strategy_id"]
        result = outcome["result"]
        key = (ctx, strat)
        if key not in self._calibration:
            self._calibration[key] = {
                "alpha": 1.0,
                "beta": 1.0,
                "success_count": 0,
                "failure_count": 0,
                "partial_count": 0,
            }
        s = self._calibration[key]
        if result == "SUCCESS":
            s["alpha"] += 1.0
            s["success_count"] += 1
        elif result == "PARTIAL":
            s["alpha"] += 0.5
            s["beta"] += 0.5
            s["partial_count"] += 1
        else:
            s["beta"] += 1.0
            s["failure_count"] += 1

    def get_recommendations(
        self, context_hash: str, min_confidence: float, limit: int
    ) -> List[Dict[str, Any]]:
        context_id = None
        for cid, c in self.contexts.items():
            if c["context_hash"] == context_hash:
                context_id = cid
                break
        if not context_id:
            return []

        recs = []
        for (ctx_id, strat_id), cal in self._calibration.items():
            if ctx_id != context_id:
                continue
            conf = cal["alpha"] / (cal["alpha"] + cal["beta"])
            if conf >= min_confidence:
                strat = self.strategies.get(strat_id, {"name": strat_id})
                recs.append(
                    {
                        "strategy_id": strat_id,
                        "strategy_name": strat.get("name", strat_id),
                        "confidence": conf,
                        "evidence_count": cal["success_count"] + cal["failure_count"] + cal["partial_count"],
                        "explanation": f"{conf:.0%} confidence based on {cal['success_count']} successes and {cal['failure_count']} failures",
                    }
                )
        recs.sort(key=lambda x: x["confidence"], reverse=True)
        return recs[:limit]

    def get_confidence(self, context_hash: str, strategy_name: str) -> Optional[tuple]:
        context_id = None
        for cid, c in self.contexts.items():
            if c["context_hash"] == context_hash:
                context_id = cid
                break
        if not context_id:
            return None

        for strat_id, strat in self.strategies.items():
            if strat.get("name") == strategy_name:
                key = (context_id, strat_id)
                if key in self._calibration:
                    cal = self._calibration[key]
                    conf = cal["alpha"] / (cal["alpha"] + cal["beta"])
                    exp = f"{conf:.0%} confidence based on {cal['success_count']} successes and {cal['failure_count']} failures"
                    return (conf, exp)
                return (0.5, "No historical data for this context/strategy")
        return None


class CortexDBxClient:
    """
    Python SDK for CortexDBx.

    With use_local_backend=True (default): in-memory store for dev/tests.
    With use_local_backend=False: expects Spark session for Delta/UC.
    """

    def __init__(
        self,
        config: Optional[CortexDBxConfig] = None,
        spark_session: Optional[Any] = None,
    ):
        self.config = config or CortexDBxConfig()
        self._spark = spark_session
        self._local = LocalBackend() if self.config.use_local_backend else None

    def _fingerprint_context(self, context: Dict[str, Any]) -> str:
        normalized = json.dumps(sorted(context.items()))
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _ensure_context(self, context: Dict[str, Any], context_hash: str) -> str:
        domain = context.get("domain", "unknown")
        factors = json.dumps(
            [{"key": k, "value": str(v)} for k, v in sorted(context.items())]
        )
        context_id = f"ctx_{context_hash}"

        if self._local:
            self._local.ensure_context(context_id, context_hash, domain, factors)
            return context_id

        if self._spark is None:
            raise RuntimeError("Spark session required when use_local_backend=False")
        table = f"{self.config.catalog}.{self.config.schema}.contexts"
        existing = (
            self._spark.sql(f"SELECT context_id FROM {table} WHERE context_hash = '{context_hash}'")
            .collect()
        )
        if existing:
            return existing[0]["context_id"]
        row = {
            "context_id": context_id,
            "context_hash": context_hash,
            "domain": domain,
            "factors": factors,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }
        df = self._spark.createDataFrame([row])
        df.write.mode("append").saveAsTable(table)
        return context_id

    def _ensure_strategy(self, strategy: str) -> str:
        strategy_id = f"strat_{hashlib.sha256(strategy.encode()).hexdigest()[:8]}"

        if self._local:
            self._local.ensure_strategy(strategy_id, strategy, "unknown")
            return strategy_id

        if self._spark is None:
            raise RuntimeError("Spark session required when use_local_backend=False")
        table = f"{self.config.catalog}.{self.config.schema}.strategies"
        existing = (
            self._spark.sql(f"SELECT strategy_id FROM {table} WHERE name = '{strategy}' OR strategy_id = '{strategy_id}'")
            .collect()
        )
        if existing:
            return existing[0]["strategy_id"]
        row = {
            "strategy_id": strategy_id,
            "name": strategy,
            "description": None,
            "domain": "unknown",
            "category": "user_defined",
            "created_at": datetime.now().isoformat(),
        }
        df = self._spark.createDataFrame([row])
        df.write.mode("append").saveAsTable(table)
        return strategy_id

    def log_outcome(
        self,
        context: Dict[str, Any],
        strategy: str,
        result: str,
        evidence: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> str:
        """
        Log an outcome to CortexDBx.

        Args:
            context: Dictionary of context factors
            strategy: Name or ID of strategy used
            result: 'SUCCESS', 'FAILURE', or 'PARTIAL'
            evidence: Optional evidence linking to source data
            notes: Optional human notes

        Returns:
            outcome_id: ID of created outcome
        """
        context_hash = self._fingerprint_context(context)
        outcome_id = str(uuid.uuid4())
        context_id = self._ensure_context(context, context_hash)
        strategy_id = self._ensure_strategy(strategy)
        result_upper = result.upper()
        if result_upper not in ("SUCCESS", "FAILURE", "PARTIAL"):
            result_upper = "PARTIAL"

        outcome = {
            "outcome_id": outcome_id,
            "context_id": context_id,
            "strategy_id": strategy_id,
            "result": result_upper,
            "evidence": json.dumps(evidence or {}),
            "notes": notes,
            "actor": "sdk_user",
            "created_at": datetime.now().isoformat(),
        }

        if self._local:
            self._local.append_outcome(outcome)
            return outcome_id

        if self._spark is None:
            raise RuntimeError("Spark session required when use_local_backend=False")
        table = f"{self.config.catalog}.{self.config.schema}.outcomes"
        df = self._spark.createDataFrame([outcome])
        df.write.mode("append").saveAsTable(table)
        return outcome_id

    def recommend(
        self,
        context: Dict[str, Any],
        min_confidence: float = 0.5,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations for a context.

        Args:
            context: Dictionary of context factors
            min_confidence: Minimum confidence threshold
            limit: Maximum recommendations to return

        Returns:
            List of recommendations with confidence and evidence
        """
        context_hash = self._fingerprint_context(context)

        if self._local:
            return self._local.get_recommendations(
                context_hash, min_confidence, limit
            )

        if self._spark is None:
            raise RuntimeError("Spark session required when use_local_backend=False")
        table_prefix = f"{self.config.catalog}.{self.config.schema}"
        query = f"""
            SELECT
                s.strategy_id,
                s.name as strategy_name,
                s.description,
                e.confidence,
                e.success_count,
                e.failure_count
            FROM {table_prefix}.context_strategy_edges e
            JOIN {table_prefix}.contexts c ON e.context_id = c.context_id
            JOIN {table_prefix}.strategies s ON e.strategy_id = s.strategy_id
            WHERE c.context_hash = '{context_hash}'
              AND e.confidence >= {min_confidence}
            ORDER BY e.confidence DESC
            LIMIT {limit}
        """
        rows = self._spark.sql(query).collect()
        return [
            {
                "strategy_id": r["strategy_id"],
                "strategy_name": r["strategy_name"],
                "description": r["description"],
                "confidence": r["confidence"],
                "evidence_count": r["success_count"] + r["failure_count"],
                "explanation": f"{r['confidence']:.0%} confidence based on {r['success_count']} successes and {r['failure_count']} failures",
            }
            for r in rows
        ]

    def get_confidence(
        self, context: Dict[str, Any], strategy: str
    ) -> tuple:
        """
        Get confidence for a specific strategy in a context.

        Returns:
            (confidence, explanation) or (0.5, "No historical data...")
        """
        context_hash = self._fingerprint_context(context)

        if self._local:
            result = self._local.get_confidence(context_hash, strategy)
            if result:
                return result
            return 0.5, "No historical data for this context/strategy"

        if self._spark is None:
            raise RuntimeError("Spark session required when use_local_backend=False")
        table_prefix = f"{self.config.catalog}.{self.config.schema}"
        query = f"""
            SELECT e.confidence, e.success_count, e.failure_count
            FROM {table_prefix}.context_strategy_edges e
            JOIN {table_prefix}.contexts c ON e.context_id = c.context_id
            JOIN {table_prefix}.strategies s ON e.strategy_id = s.strategy_id
            WHERE c.context_hash = '{context_hash}' AND s.name = '{strategy}'
        """
        rows = self._spark.sql(query).collect()
        if not rows:
            return 0.5, "No historical data for this context/strategy"
        r = rows[0]
        return r["confidence"], (
            f"{r['confidence']:.0%} confidence based on "
            f"{r['success_count']} successes and {r['failure_count']} failures"
        )
