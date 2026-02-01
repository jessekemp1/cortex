"""
Agent orchestrator for CortexDBx.

Coordinates domain agents for parallel processing of outcomes.
"""

from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from cortexdbx.calibration.engine import CalibrationEngine
from cortexdbx.agents.definitions import AGENT_CONFIGS

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Coordinates domain agents for parallel processing.

    Ingests outcomes by domain and updates a shared calibration engine.
    """

    def __init__(self, max_workers: int = 6):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.calibration = CalibrationEngine()
        self._domain_agents: Dict[str, bool] = {
            d: True for d in AGENT_CONFIGS if d != "orchestrator"
        }

    def process_outcomes(self, outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a list of outcomes: group by domain and update calibration.

        outcomes: list of dicts with context_id, strategy_id, result
        Returns: aggregated stats (processed, by_domain)
        """
        by_domain: Dict[str, List[Dict[str, Any]]] = {}
        for o in outcomes:
            domain = o.get("domain", "unknown")
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(o)

        total_ingested = 0
        by_domain_stats: Dict[str, int] = {}

        for domain, domain_outcomes in by_domain.items():
            count = self.calibration.ingest_outcomes(domain_outcomes)
            by_domain_stats[domain] = count
            total_ingested += count

        return {
            "total_processed": len(outcomes),
            "total_ingested": total_ingested,
            "by_domain": by_domain_stats,
        }

    def process_outcomes_parallel(
        self, outcomes: List[Dict[str, Any]], chunk_size: int = 500
    ) -> Dict[str, Any]:
        """
        Process outcomes in parallel chunks.

        Splits outcomes into chunks and processes each chunk in a worker.
        """
        chunks: List[List[Dict[str, Any]]] = []
        for i in range(0, len(outcomes), chunk_size):
            chunks.append(outcomes[i : i + chunk_size])

        all_results: List[Dict[str, Any]] = []
        futures = {
            self.executor.submit(self.process_outcomes, chunk): chunk
            for chunk in chunks
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                logger.error("Chunk processing failed: %s", e)

        total_processed = sum(r["total_processed"] for r in all_results)
        total_ingested = sum(r["total_ingested"] for r in all_results)
        by_domain: Dict[str, int] = {}
        for r in all_results:
            for d, c in r.get("by_domain", {}).items():
                by_domain[d] = by_domain.get(d, 0) + c

        return {
            "total_processed": total_processed,
            "total_ingested": total_ingested,
            "by_domain": by_domain,
            "chunks_processed": len(all_results),
        }

    def get_recommendations(
        self, context_id: str, min_confidence: float = 0.7, limit: int = 10
    ) -> List[tuple]:
        """Get top strategy recommendations for a context from calibration."""
        return self.calibration.get_top_strategies(
            context_id, min_confidence=min_confidence, limit=limit
        )

    def evaluate_calibration(
        self, ground_truth: Dict[str, float]
    ) -> Dict[str, Any]:
        """Evaluate calibration quality against ground truth."""
        return self.calibration.evaluate_calibration(ground_truth)

    def shutdown(self) -> None:
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)
