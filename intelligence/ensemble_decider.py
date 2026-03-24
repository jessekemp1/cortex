#!/usr/bin/env python3
"""
Field-Level Ensemble Decision System

Vortex Principle: Field-level ensemble values prove out to be most accurate.

Instead of one model/strategy making the whole decision, decompose each
decision into independent "fields" and use specialized predictors per field.
The ensemble of field-level predictions outperforms any single holistic
predictor — just as in Vortex's weather forecasting.

Decision Fields:
    MODEL_TIER     → Which model tier? (haiku/sonnet/opus)
    ROUTING        → Batch or interactive?
    CONTEXT_SIZE   → How much context to include?
    PRIORITY       → How urgent is this?
    CONFIDENCE     → How confident should we be?

Each field has multiple predictors (rule-based, learned, calibrated, etc.)
that vote independently. The ensemble aggregates votes using Bayesian
confidence weighting — predictors that have been more accurate historically
get more weight.

This directly maps Vortex's field-level ensemble to Cortex's decision space.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class DecisionField(str, Enum):
    """Fields that compose a full routing/selection decision."""

    MODEL_TIER = "model_tier"
    ROUTING = "routing"
    CONTEXT_SIZE = "context_size"
    PRIORITY = "priority"
    CONFIDENCE = "confidence"


@dataclass
class FieldVote:
    """A single predictor's vote for one decision field."""

    field: DecisionField
    predictor_name: str  # Who cast this vote
    value: Any  # The predicted value
    confidence: float  # 0.0-1.0 predictor's self-assessed confidence
    reasoning: str  # Why this vote


@dataclass
class EnsembleResult:
    """The ensemble's aggregated decision for one field."""

    field: DecisionField
    value: Any  # Winning value
    confidence: float  # Weighted confidence
    agreement_ratio: float  # What % of predictors agreed
    votes: List[FieldVote]  # All individual votes
    reasoning: str  # Aggregated reasoning


@dataclass
class FullDecision:
    """Complete decision assembled from field-level ensemble results."""

    model_tier: str
    routing: str
    context_size: str  # "minimal", "standard", "full"
    priority: str  # "low", "medium", "high", "critical"
    overall_confidence: float
    field_results: Dict[str, EnsembleResult]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class FieldPredictor:
    """
    A predictor specialized for one decision field.

    Each predictor wraps a function that takes task context and returns
    a FieldVote. The predictor tracks its own accuracy over time so
    the ensemble can weight it appropriately.
    """

    def __init__(
        self,
        name: str,
        field: DecisionField,
        predict_fn: Callable[..., FieldVote],
    ):
        self.name = name
        self.field = field
        self.predict_fn = predict_fn
        # Bayesian accuracy tracking (Beta prior)
        self.alpha = 1.0  # successes + prior
        self.beta = 1.0  # failures + prior
        self.total_predictions = 0

    @property
    def accuracy(self) -> float:
        """Posterior mean of Beta distribution."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def weight(self) -> float:
        """
        Ensemble weight — accuracy modulated by evidence count.
        New predictors (low evidence) have weight pulled toward 0.5.
        Proven predictors (high evidence) have weight near their accuracy.
        """
        evidence_factor = min(1.0, self.total_predictions / 20)
        return 0.5 + (self.accuracy - 0.5) * evidence_factor

    def predict(self, task_context: Dict[str, Any]) -> FieldVote:
        """Generate a prediction for this field."""
        self.total_predictions += 1
        return self.predict_fn(task_context)

    def record_outcome(self, was_correct: bool):
        """Update accuracy tracking with observed outcome."""
        if was_correct:
            self.alpha += 1.0
        else:
            self.beta += 1.0


class FieldEnsembleDecider:
    """
    Decomposes decisions into fields, ensembles specialized predictors.

    This is the Cortex implementation of Vortex's core insight:
    field-level ensembles outperform holistic single-model predictions.

    Usage:
        decider = FieldEnsembleDecider()

        # Each field gets multiple predictors
        decider.register_predictor(rule_based_model_predictor)
        decider.register_predictor(learned_model_predictor)
        decider.register_predictor(calibration_model_predictor)
        decider.register_predictor(rule_based_routing_predictor)
        decider.register_predictor(utilization_routing_predictor)
        # ...

        decision = decider.decide(task_context)
        # decision.model_tier, decision.routing, etc.

        # After outcome observed:
        decider.record_outcome(decision, actual_outcome)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "ensemble" / "decisions.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._predictors: Dict[DecisionField, List[FieldPredictor]] = {
            f: [] for f in DecisionField
        }
        self._init_database()
        self._register_default_predictors()
        self._load_predictor_weights()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS predictor_accuracy (
                    predictor_name TEXT,
                    field TEXT,
                    alpha REAL DEFAULT 1.0,
                    beta REAL DEFAULT 1.0,
                    total_predictions INTEGER DEFAULT 0,
                    last_updated TEXT,
                    PRIMARY KEY (predictor_name, field)
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ensemble_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    task_context_hash TEXT,
                    model_tier TEXT,
                    routing TEXT,
                    context_size TEXT,
                    priority TEXT,
                    overall_confidence REAL,
                    field_results_json TEXT,
                    outcome TEXT DEFAULT 'pending'
                )
            """
            )
            conn.commit()

    def _load_predictor_weights(self):
        """Load persisted accuracy data for predictors."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM predictor_accuracy").fetchall()

        weight_map = {(r["predictor_name"], r["field"]): r for r in rows}

        for field_type, predictors in self._predictors.items():
            for pred in predictors:
                key = (pred.name, field_type.value)
                if key in weight_map:
                    row = weight_map[key]
                    pred.alpha = row["alpha"]
                    pred.beta = row["beta"]
                    pred.total_predictions = row["total_predictions"]

    def _save_predictor_weights(self):
        """Persist predictor accuracy data."""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now().isoformat()
            for field_type, predictors in self._predictors.items():
                for pred in predictors:
                    conn.execute(
                        """
                        INSERT INTO predictor_accuracy
                        (predictor_name, field, alpha, beta, total_predictions, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(predictor_name, field) DO UPDATE SET
                            alpha = ?, beta = ?, total_predictions = ?, last_updated = ?
                    """,
                        (
                            pred.name,
                            field_type.value,
                            pred.alpha,
                            pred.beta,
                            pred.total_predictions,
                            now,
                            pred.alpha,
                            pred.beta,
                            pred.total_predictions,
                            now,
                        ),
                    )
            conn.commit()

    # ──────────────────────────────────────────────
    # Default predictors for each field
    # ──────────────────────────────────────────────

    def _register_default_predictors(self):
        """Register the built-in predictor ensemble."""

        # MODEL_TIER: 3 independent predictors
        self.register_predictor(
            FieldPredictor(
                "rules_model",
                DecisionField.MODEL_TIER,
                self._rules_model_predictor,
            )
        )
        self.register_predictor(
            FieldPredictor(
                "complexity_model",
                DecisionField.MODEL_TIER,
                self._complexity_model_predictor,
            )
        )
        self.register_predictor(
            FieldPredictor(
                "historical_model",
                DecisionField.MODEL_TIER,
                self._historical_model_predictor,
            )
        )

        # ROUTING: 3 independent predictors
        self.register_predictor(
            FieldPredictor(
                "pattern_routing",
                DecisionField.ROUTING,
                self._pattern_routing_predictor,
            )
        )
        self.register_predictor(
            FieldPredictor(
                "utilization_routing",
                DecisionField.ROUTING,
                self._utilization_routing_predictor,
            )
        )
        self.register_predictor(
            FieldPredictor(
                "learned_routing",
                DecisionField.ROUTING,
                self._learned_routing_predictor,
            )
        )

        # CONTEXT_SIZE: 2 predictors
        self.register_predictor(
            FieldPredictor(
                "token_context",
                DecisionField.CONTEXT_SIZE,
                self._token_context_predictor,
            )
        )
        self.register_predictor(
            FieldPredictor(
                "task_context",
                DecisionField.CONTEXT_SIZE,
                self._task_context_predictor,
            )
        )

        # PRIORITY: 2 predictors
        self.register_predictor(
            FieldPredictor(
                "signal_priority",
                DecisionField.PRIORITY,
                self._signal_priority_predictor,
            )
        )
        self.register_predictor(
            FieldPredictor(
                "deadline_priority",
                DecisionField.PRIORITY,
                self._deadline_priority_predictor,
            )
        )

    # ── Model Tier Predictors ──

    @staticmethod
    def _rules_model_predictor(ctx: Dict) -> FieldVote:
        """Rule-based model selection (maps task_type → tier)."""
        task_type = ctx.get("task_type", "")
        mapping = {
            "architecture": "opus",
            "security_audit": "opus",
            "planning": "opus",
            "code_review": "sonnet",
            "implementation": "sonnet",
            "refactoring": "sonnet",
            "bug_fix": "sonnet",
            "documentation": "haiku",
            "classification": "haiku",
            "quick_qa": "haiku",
        }
        tier = mapping.get(task_type, "sonnet")
        return FieldVote(
            field=DecisionField.MODEL_TIER,
            predictor_name="rules_model",
            value=tier,
            confidence=0.70,
            reasoning=f"Rule mapping: {task_type} → {tier}",
        )

    @staticmethod
    def _complexity_model_predictor(ctx: Dict) -> FieldVote:
        """Complexity-based model selection."""
        token_estimate = ctx.get("token_estimate", 5000)
        file_count = ctx.get("file_count", 1)

        # Score complexity from features
        score = 0.0
        if token_estimate > 50000:
            score += 0.4
        elif token_estimate > 15000:
            score += 0.2
        if file_count > 10:
            score += 0.3
        elif file_count > 3:
            score += 0.15
        if ctx.get("requires_iteration"):
            score += 0.2

        if score >= 0.6:
            tier = "opus"
        elif score >= 0.3:
            tier = "sonnet"
        else:
            tier = "haiku"

        return FieldVote(
            field=DecisionField.MODEL_TIER,
            predictor_name="complexity_model",
            value=tier,
            confidence=0.65,
            reasoning=f"Complexity score {score:.2f} → {tier}",
        )

    @staticmethod
    def _historical_model_predictor(ctx: Dict) -> FieldVote:
        """History-based model selection from outcome logs."""
        task_type = ctx.get("task_type", "")
        project = ctx.get("project", "")

        try:
            from intelligence.outcome_logger import compare_model_performance

            perf = compare_model_performance(task_type, project, min_samples=3)
            if perf and task_type in perf.get("by_task_type", {}):
                best = perf["by_task_type"][task_type]
                return FieldVote(
                    field=DecisionField.MODEL_TIER,
                    predictor_name="historical_model",
                    value=best["best_model"],
                    confidence=min(0.90, 0.6 + best.get("samples", 0) / 50),
                    reasoning=f"Historical best: {best['best_model']} at {best['success_rate']:.0%} (n={best.get('samples', 0)})",
                )
        except (ImportError, Exception):
            pass

        # Fallback: no data → defer with low confidence
        return FieldVote(
            field=DecisionField.MODEL_TIER,
            predictor_name="historical_model",
            value="sonnet",
            confidence=0.30,
            reasoning="Insufficient historical data, defaulting to sonnet",
        )

    # ── Routing Predictors ──

    @staticmethod
    def _pattern_routing_predictor(ctx: Dict) -> FieldVote:
        """Pattern-based routing (keywords → batch/interactive)."""
        request = ctx.get("request_text", "").lower()
        batch_keywords = ["review all", "audit", "analyze codebase", "generate docs", "run tests on"]
        interactive_keywords = ["fix this", "help me", "debug", "explain", "quick"]

        for kw in interactive_keywords:
            if kw in request:
                return FieldVote(
                    field=DecisionField.ROUTING,
                    predictor_name="pattern_routing",
                    value="interactive",
                    confidence=0.80,
                    reasoning=f"Interactive keyword: '{kw}'",
                )

        for kw in batch_keywords:
            if kw in request:
                return FieldVote(
                    field=DecisionField.ROUTING,
                    predictor_name="pattern_routing",
                    value="batch",
                    confidence=0.75,
                    reasoning=f"Batch keyword: '{kw}'",
                )

        return FieldVote(
            field=DecisionField.ROUTING,
            predictor_name="pattern_routing",
            value="interactive",
            confidence=0.50,
            reasoning="No strong pattern signal",
        )

    @staticmethod
    def _utilization_routing_predictor(ctx: Dict) -> FieldVote:
        """Subscription utilization awareness for routing."""
        utilization_pct = ctx.get("utilization_pct")
        tokens_at_risk = ctx.get("tokens_at_risk", 0)

        if utilization_pct is not None and utilization_pct < 50 and tokens_at_risk > 50_000:
            return FieldVote(
                field=DecisionField.ROUTING,
                predictor_name="utilization_routing",
                value="batch",
                confidence=0.65,
                reasoning=f"Subscription {utilization_pct:.0f}% utilized, {tokens_at_risk:,} tokens at risk",
            )

        if utilization_pct is not None and utilization_pct > 90:
            return FieldVote(
                field=DecisionField.ROUTING,
                predictor_name="utilization_routing",
                value="batch",
                confidence=0.70,
                reasoning=f"Near cap ({utilization_pct:.0f}%), batch to conserve",
            )

        return FieldVote(
            field=DecisionField.ROUTING,
            predictor_name="utilization_routing",
            value="interactive",
            confidence=0.40,
            reasoning="Utilization normal, no routing pressure",
        )

    @staticmethod
    def _learned_routing_predictor(ctx: Dict) -> FieldVote:
        """Learned routing from UtilizationLearningEngine."""
        task_type = ctx.get("task_type", "")
        try:
            from batch.utilization_learning import UtilizationLearningEngine

            engine = UtilizationLearningEngine()
            adj = engine.get_routing_adjustment(task_type)
            if adj and "preferred_route" in adj:
                route = "batch" if adj["preferred_route"] == "suggest_batch" else "interactive"
                return FieldVote(
                    field=DecisionField.ROUTING,
                    predictor_name="learned_routing",
                    value=route,
                    confidence=adj.get("confidence", 0.6),
                    reasoning=adj.get("reasoning", "Learned preference"),
                )
        except (ImportError, Exception):
            pass

        return FieldVote(
            field=DecisionField.ROUTING,
            predictor_name="learned_routing",
            value="interactive",
            confidence=0.30,
            reasoning="No learned routing data",
        )

    # ── Context Size Predictors ──

    @staticmethod
    def _token_context_predictor(ctx: Dict) -> FieldVote:
        """Token budget awareness for context sizing."""
        token_estimate = ctx.get("token_estimate", 5000)
        budget_pct = ctx.get("budget_remaining_pct", 100)

        if budget_pct < 30:
            size = "minimal"
            conf = 0.80
            reason = f"Low budget ({budget_pct:.0f}% remaining)"
        elif token_estimate > 30000:
            size = "full"
            conf = 0.70
            reason = "Large task benefits from full context"
        else:
            size = "standard"
            conf = 0.60
            reason = "Standard context for moderate task"

        return FieldVote(
            field=DecisionField.CONTEXT_SIZE,
            predictor_name="token_context",
            value=size,
            confidence=conf,
            reasoning=reason,
        )

    @staticmethod
    def _task_context_predictor(ctx: Dict) -> FieldVote:
        """Task type awareness for context sizing."""
        task_type = ctx.get("task_type", "")
        full_context_tasks = {"architecture", "security_audit", "refactoring", "code_review"}
        minimal_context_tasks = {"quick_qa", "classification", "documentation"}

        if task_type in full_context_tasks:
            return FieldVote(
                field=DecisionField.CONTEXT_SIZE,
                predictor_name="task_context",
                value="full",
                confidence=0.75,
                reasoning=f"{task_type} benefits from full codebase context",
            )
        elif task_type in minimal_context_tasks:
            return FieldVote(
                field=DecisionField.CONTEXT_SIZE,
                predictor_name="task_context",
                value="minimal",
                confidence=0.70,
                reasoning=f"{task_type} needs minimal context",
            )

        return FieldVote(
            field=DecisionField.CONTEXT_SIZE,
            predictor_name="task_context",
            value="standard",
            confidence=0.55,
            reasoning="Default context for unclassified task",
        )

    # ── Priority Predictors ──

    @staticmethod
    def _signal_priority_predictor(ctx: Dict) -> FieldVote:
        """Priority based on detected signals."""
        signals = ctx.get("active_signals", [])
        high_signals = {"SECURITY", "TEST_FAILURE"}
        medium_signals = {"VALIDATION_GAP", "TECH_DEBT", "PERFORMANCE"}

        for sig in signals:
            sig_type = sig if isinstance(sig, str) else sig.get("type", "")
            if sig_type in high_signals:
                return FieldVote(
                    field=DecisionField.PRIORITY,
                    predictor_name="signal_priority",
                    value="critical",
                    confidence=0.85,
                    reasoning=f"Critical signal detected: {sig_type}",
                )
            if sig_type in medium_signals:
                return FieldVote(
                    field=DecisionField.PRIORITY,
                    predictor_name="signal_priority",
                    value="high",
                    confidence=0.70,
                    reasoning=f"Important signal: {sig_type}",
                )

        return FieldVote(
            field=DecisionField.PRIORITY,
            predictor_name="signal_priority",
            value="medium",
            confidence=0.50,
            reasoning="No urgent signals detected",
        )

    @staticmethod
    def _deadline_priority_predictor(ctx: Dict) -> FieldVote:
        """Priority based on time pressure."""
        time_sensitive = ctx.get("time_sensitive", False)
        days_remaining = ctx.get("days_remaining_in_cycle", 30)

        if time_sensitive:
            return FieldVote(
                field=DecisionField.PRIORITY,
                predictor_name="deadline_priority",
                value="critical",
                confidence=0.90,
                reasoning="Marked as time-sensitive",
            )

        if days_remaining <= 2:
            return FieldVote(
                field=DecisionField.PRIORITY,
                predictor_name="deadline_priority",
                value="high",
                confidence=0.75,
                reasoning=f"Only {days_remaining} days left in billing cycle",
            )

        return FieldVote(
            field=DecisionField.PRIORITY,
            predictor_name="deadline_priority",
            value="medium",
            confidence=0.45,
            reasoning="No time pressure",
        )

    # ──────────────────────────────────────────────
    # Core ensemble logic
    # ──────────────────────────────────────────────

    def register_predictor(self, predictor: FieldPredictor):
        """Register a predictor for a decision field."""
        self._predictors[predictor.field].append(predictor)

    def decide(self, task_context: Dict[str, Any]) -> FullDecision:
        """
        Make a full decision by ensembling field-level predictions.

        Each field is decided independently by its predictor ensemble,
        then assembled into a complete decision.
        """
        field_results = {}

        for field_type in DecisionField:
            if field_type == DecisionField.CONFIDENCE:
                continue  # Computed from other fields

            predictors = self._predictors.get(field_type, [])
            if not predictors:
                continue

            # Collect votes from all predictors for this field
            votes = []
            for pred in predictors:
                try:
                    vote = pred.predict(task_context)
                    votes.append((vote, pred.weight))
                except Exception:
                    continue

            if not votes:
                continue

            # Weighted vote aggregation
            result = self._aggregate_votes(field_type, votes)
            field_results[field_type.value] = result

        # Assemble full decision
        overall_confidence = self._compute_overall_confidence(field_results)

        decision = FullDecision(
            model_tier=field_results.get("model_tier", EnsembleResult(
                DecisionField.MODEL_TIER, "sonnet", 0.5, 0.0, [], "default"
            )).value,
            routing=field_results.get("routing", EnsembleResult(
                DecisionField.ROUTING, "interactive", 0.5, 0.0, [], "default"
            )).value,
            context_size=field_results.get("context_size", EnsembleResult(
                DecisionField.CONTEXT_SIZE, "standard", 0.5, 0.0, [], "default"
            )).value,
            priority=field_results.get("priority", EnsembleResult(
                DecisionField.PRIORITY, "medium", 0.5, 0.0, [], "default"
            )).value,
            overall_confidence=overall_confidence,
            field_results=field_results,
        )

        self._persist_decision(decision, task_context)
        return decision

    def _aggregate_votes(
        self,
        field_type: DecisionField,
        weighted_votes: List[Tuple[FieldVote, float]],
    ) -> EnsembleResult:
        """
        Aggregate votes using confidence-weighted voting.

        Weight = predictor_accuracy_weight × vote_confidence
        Winner = value with highest total weight
        """
        # Accumulate weighted scores per value
        value_scores: Dict[Any, float] = {}
        all_votes = []

        for vote, predictor_weight in weighted_votes:
            combined_weight = predictor_weight * vote.confidence
            value_scores[vote.value] = value_scores.get(vote.value, 0) + combined_weight
            all_votes.append(vote)

        if not value_scores:
            return EnsembleResult(
                field=field_type, value=None, confidence=0.0,
                agreement_ratio=0.0, votes=[], reasoning="No votes",
            )

        # Winner is the value with highest weighted score
        winner = max(value_scores, key=value_scores.get)
        total_weight = sum(value_scores.values())
        winner_weight = value_scores[winner]

        # Confidence = winner's proportion of total weight
        confidence = winner_weight / total_weight if total_weight > 0 else 0

        # Agreement = how many predictors voted for winner
        winner_count = sum(1 for v in all_votes if v.value == winner)
        agreement = winner_count / len(all_votes) if all_votes else 0

        # Build reasoning from winning votes
        winner_votes = [v for v in all_votes if v.value == winner]
        reasoning = " | ".join(v.reasoning for v in winner_votes[:3])

        return EnsembleResult(
            field=field_type,
            value=winner,
            confidence=round(confidence, 3),
            agreement_ratio=round(agreement, 2),
            votes=all_votes,
            reasoning=reasoning,
        )

    @staticmethod
    def _compute_overall_confidence(field_results: Dict[str, EnsembleResult]) -> float:
        """Overall confidence = geometric mean of field confidences."""
        if not field_results:
            return 0.5

        confidences = [r.confidence for r in field_results.values() if r.confidence > 0]
        if not confidences:
            return 0.5

        # Geometric mean
        product = 1.0
        for c in confidences:
            product *= c
        return round(product ** (1.0 / len(confidences)), 3)

    def record_outcome(self, decision: FullDecision, actual_outcome: Dict[str, Any]):
        """
        Record the actual outcome to update predictor weights.

        This is the learning step — predictors that voted correctly
        get their accuracy boosted, incorrect ones get penalized.
        The next decision will weight them accordingly.

        Args:
            decision: The decision that was made
            actual_outcome: Dict mapping field names to actual correct values
                           e.g. {"model_tier": "opus", "routing": "interactive"}
        """
        for field_name, result in decision.field_results.items():
            actual = actual_outcome.get(field_name)
            if actual is None:
                continue

            for vote in result.votes:
                was_correct = vote.value == actual
                # Find the predictor and update
                for pred in self._predictors.get(DecisionField(field_name), []):
                    if pred.name == vote.predictor_name:
                        pred.record_outcome(was_correct)
                        break

        self._save_predictor_weights()

    def _persist_decision(self, decision: FullDecision, task_context: Dict):
        """Save decision for audit trail."""
        ctx_hash = str(hash(json.dumps(task_context, sort_keys=True, default=str)))[:16]
        field_json = json.dumps(
            {
                k: {
                    "value": v.value,
                    "confidence": v.confidence,
                    "agreement_ratio": v.agreement_ratio,
                    "reasoning": v.reasoning,
                }
                for k, v in decision.field_results.items()
            }
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO ensemble_decisions
                (timestamp, task_context_hash, model_tier, routing,
                 context_size, priority, overall_confidence, field_results_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    decision.timestamp,
                    ctx_hash,
                    decision.model_tier,
                    decision.routing,
                    decision.context_size,
                    decision.priority,
                    decision.overall_confidence,
                    field_json,
                ),
            )
            conn.commit()

    def format_decision_report(self, decision: FullDecision) -> str:
        """Format a human-readable decision report showing ensemble reasoning."""
        lines = [
            "=== Field-Level Ensemble Decision ===",
            "",
            f"Model Tier:    {decision.model_tier}",
            f"Routing:       {decision.routing}",
            f"Context Size:  {decision.context_size}",
            f"Priority:      {decision.priority}",
            f"Confidence:    {decision.overall_confidence:.1%}",
            "",
        ]

        for field_name, result in decision.field_results.items():
            lines.append(f"--- {field_name} ---")
            lines.append(
                f"  Winner: {result.value} "
                f"(confidence={result.confidence:.0%}, "
                f"agreement={result.agreement_ratio:.0%})"
            )
            for vote in result.votes:
                marker = "✓" if vote.value == result.value else "✗"
                weight_indicator = "●" * int(vote.confidence * 5) + "○" * (5 - int(vote.confidence * 5))
                lines.append(
                    f"  {marker} [{weight_indicator}] {vote.predictor_name}: "
                    f"{vote.value} — {vote.reasoning}"
                )
            lines.append("")

        return "\n".join(lines)

    def get_predictor_leaderboard(self) -> str:
        """Show which predictors are most accurate per field."""
        lines = ["=== Predictor Leaderboard ===", ""]

        for field_type in DecisionField:
            if field_type == DecisionField.CONFIDENCE:
                continue

            predictors = self._predictors.get(field_type, [])
            if not predictors:
                continue

            lines.append(f"--- {field_type.value} ---")
            ranked = sorted(predictors, key=lambda p: p.accuracy, reverse=True)
            for i, pred in enumerate(ranked, 1):
                acc_bar = "█" * int(pred.accuracy * 10) + "░" * (10 - int(pred.accuracy * 10))
                lines.append(
                    f"  {i}. [{acc_bar}] {pred.accuracy:.0%} "
                    f"{pred.name} (n={pred.total_predictions}, weight={pred.weight:.2f})"
                )
            lines.append("")

        return "\n".join(lines)
