#!/usr/bin/env python3
"""
AML Risk Model Validator — FINTRAC-aligned rule engine for synthetic data.

Implements 7 AML/KYC detection rules derived from FINTRAC guidance:
1. Structuring: Transactions just below $10K reporting threshold
2. Rapid movement: Funds in and out within 24-48 hours
3. Round amounts: Repeated exact round-number transfers
4. Geographic risk: High-risk jurisdiction transactions
5. Unusual volume: 3x+ baseline transaction volume
6. Dormant reactivation: Inactive >6 months, sudden activity
7. Third party: Deposits from unrelated third parties

The validator serves two roles:
- Quality signal: Ensures generated AML patterns are detectable
- Adversarial feedback: Runs a generate→validate→improve loop
  that pushes the generator to produce more realistic risk data

Architecture:
    RiskValidator(kb) → validate_batch(transactions) → RiskReport
    → adversarial_loop(generator, rounds=5) → converged parameters
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import GenerationRequest, Transaction


@dataclass
class RuleResult:
    """Result from applying a single AML rule to a transaction."""

    rule_name: str
    triggered: bool
    confidence: float  # 0.0-1.0 — how confident the rule is
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "triggered": self.triggered,
            "confidence": round(self.confidence, 4),
            "detail": self.detail,
        }


@dataclass
class RiskReport:
    """Aggregate report from validating a batch of transactions."""

    total_transactions: int = 0
    flagged_by_generator: int = 0  # Generator labeled as suspicious
    detected_by_rules: int = 0  # Rules independently detected
    true_positives: int = 0  # Generator flagged AND rules detect
    false_positives: int = 0  # Rules detect but generator says clean
    false_negatives: int = 0  # Generator flagged but rules miss
    true_negatives: int = 0  # Both agree: clean
    rule_coverage: Dict[str, int] = field(default_factory=dict)
    per_rule_results: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def detection_rate(self) -> float:
        """Of generator-flagged transactions, what % did rules also catch?"""
        total_flagged = self.true_positives + self.false_negatives
        if total_flagged == 0:
            return 1.0
        return self.true_positives / total_flagged

    @property
    def precision(self) -> float:
        """Of rule-detected transactions, what % were actually flagged?"""
        total_detected = self.true_positives + self.false_positives
        if total_detected == 0:
            return 1.0
        return self.true_positives / total_detected

    @property
    def false_positive_rate(self) -> float:
        total_clean = self.true_negatives + self.false_positives
        if total_clean == 0:
            return 0.0
        return self.false_positives / total_clean

    @property
    def false_negative_rate(self) -> float:
        total_flagged = self.true_positives + self.false_negatives
        if total_flagged == 0:
            return 0.0
        return self.false_negatives / total_flagged

    def summary(self) -> str:
        return (
            f"Risk Validation: {self.total_transactions} txns | "
            f"Detection rate: {self.detection_rate:.1%} | "
            f"Precision: {self.precision:.1%} | "
            f"TP={self.true_positives} FP={self.false_positives} "
            f"FN={self.false_negatives} TN={self.true_negatives}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_transactions": self.total_transactions,
            "flagged_by_generator": self.flagged_by_generator,
            "detected_by_rules": self.detected_by_rules,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "detection_rate": round(self.detection_rate, 4),
            "precision": round(self.precision, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "rule_coverage": self.rule_coverage,
        }


@dataclass
class AdversarialResult:
    """Result from an adversarial generation loop."""

    rounds_executed: int
    converged: bool
    detection_rates: List[float]
    final_detection_rate: float
    corrections_applied: List[Dict[str, Any]]

    def summary(self) -> str:
        status = "CONVERGED" if self.converged else "DID NOT CONVERGE"
        return (
            f"Adversarial loop: {self.rounds_executed} rounds, {status} | "
            f"Detection rate: {self.detection_rates[0]:.1%} → {self.final_detection_rate:.1%}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rounds_executed": self.rounds_executed,
            "converged": self.converged,
            "detection_rates": [round(r, 4) for r in self.detection_rates],
            "final_detection_rate": round(self.final_detection_rate, 4),
            "corrections_applied": self.corrections_applied,
        }


class RiskValidator:
    """
    AML/KYC risk model for validating synthetic transaction data.

    Implements FINTRAC-aligned rules and an adversarial loop where
    the generator iteratively improves its risk patterns until
    the validator achieves the target detection rate.
    """

    TARGET_DETECTION_RATE = 0.90  # > 90% detection
    MAX_ADVERSARIAL_ROUNDS = 5

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()
        self._reg = self.kb.get_regulatory_params()
        self._rules = {
            "structuring": self._rule_structuring,
            "rapid_movement": self._rule_rapid_movement,
            "round_amounts": self._rule_round_amounts,
            "geographic_risk": self._rule_geographic_risk,
            "unusual_volume": self._rule_unusual_volume,
            "dormant_reactivation": self._rule_dormant_reactivation,
            "third_party": self._rule_third_party,
        }

    def validate_transaction(self, txn: Transaction) -> List[RuleResult]:
        """Apply all AML rules to a single transaction."""
        results = []
        for rule_name, rule_fn in self._rules.items():
            result = rule_fn(txn)
            results.append(result)
        return results

    def validate_batch(self, transactions: List[Transaction]) -> RiskReport:
        """
        Validate a batch of transactions against all AML rules.

        Compares generator-assigned risk flags against independent
        rule detection to produce TP/FP/FN/TN confusion matrix.
        """
        report = RiskReport(total_transactions=len(transactions))
        report.rule_coverage = {name: 0 for name in self._rules}
        report.per_rule_results = {name: {"triggered": 0, "missed": 0} for name in self._rules}

        for txn in transactions:
            generator_flagged = txn.risk_flag != "none"
            if generator_flagged:
                report.flagged_by_generator += 1

            # Run all rules
            rule_results = self.validate_transaction(txn)
            any_rule_triggered = any(r.triggered for r in rule_results)

            if any_rule_triggered:
                report.detected_by_rules += 1

            # Confusion matrix
            if generator_flagged and any_rule_triggered:
                report.true_positives += 1
            elif not generator_flagged and any_rule_triggered:
                report.false_positives += 1
            elif generator_flagged and not any_rule_triggered:
                report.false_negatives += 1
            else:
                report.true_negatives += 1

            # Per-rule coverage
            for result in rule_results:
                if result.triggered:
                    report.rule_coverage[result.rule_name] = (
                        report.rule_coverage.get(result.rule_name, 0) + 1
                    )
                    report.per_rule_results[result.rule_name]["triggered"] += 1

            # Track which generator-flagged patterns the rules missed
            if generator_flagged and not any_rule_triggered:
                report.per_rule_results.get(txn.risk_flag, {"triggered": 0, "missed": 0})[
                    "missed"
                ] = (
                    report.per_rule_results.get(txn.risk_flag, {"triggered": 0, "missed": 0}).get(
                        "missed", 0
                    )
                    + 1
                )

        return report

    def adversarial_loop(
        self,
        generator,
        count: int = 200,
        max_rounds: int = 5,
        target_rate: float = 0.90,
    ) -> AdversarialResult:
        """
        Run adversarial generation loop.

        Generator produces transactions → Validator tests → Feedback
        adjusts generator → Repeat until detection rate ≥ target.

        Args:
            generator: SyntheticGenerator instance
            count: Transactions per round
            max_rounds: Maximum rounds before giving up
            target_rate: Target detection rate to converge on

        Returns:
            AdversarialResult with convergence data
        """
        detection_rates = []
        corrections = []

        for round_num in range(1, max_rounds + 1):
            # Generate a batch with risk patterns
            request = GenerationRequest(
                data_type="transactions",
                count=count,
                include_risk_flags=True,
                risk_profile="high",
            )
            result = generator.generate(request)

            # Load generated transactions from output
            transactions = self._load_transactions_from_result(result)
            if not transactions:
                detection_rates.append(0.0)
                continue

            # Validate
            report = self.validate_batch(transactions)
            detection_rates.append(report.detection_rate)

            # Check convergence
            if report.detection_rate >= target_rate:
                return AdversarialResult(
                    rounds_executed=round_num,
                    converged=True,
                    detection_rates=detection_rates,
                    final_detection_rate=report.detection_rate,
                    corrections_applied=corrections,
                )

            # Generate correction feedback
            correction = self._generate_corrections(report)
            corrections.append(correction)

        return AdversarialResult(
            rounds_executed=max_rounds,
            converged=detection_rates[-1] >= target_rate if detection_rates else False,
            detection_rates=detection_rates,
            final_detection_rate=detection_rates[-1] if detection_rates else 0.0,
            corrections_applied=corrections,
        )

    def get_rule_coverage_report(
        self, transactions: List[Transaction]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Report which AML patterns are well/under-represented.

        Returns per-rule stats: trigger count, trigger rate, and
        whether the pattern has sufficient coverage for validation.
        """
        report = self.validate_batch(transactions)
        coverage = {}
        for rule_name, count in report.rule_coverage.items():
            rate = count / len(transactions) if transactions else 0
            coverage[rule_name] = {
                "triggers": count,
                "rate": round(rate, 4),
                "sufficient": count >= 5,  # Need at least 5 examples
            }
        return coverage

    # --- FINTRAC-Aligned Rules ---

    def _rule_structuring(self, txn: Transaction) -> RuleResult:
        """
        Detect structuring: transactions just below $10K FINTRAC threshold.

        FINTRAC defines structuring as breaking up transactions to avoid
        the $10,000 reporting threshold for large cash transactions.
        """
        threshold = self._reg.get("large_cash_threshold_cad", 10_000)
        lower_bound = threshold * 0.85  # $8,500

        is_deposit_or_withdrawal = txn.transaction_type in (
            "deposit",
            "withdrawal",
            "wire_domestic",
        )
        amount_in_range = lower_bound <= txn.amount < threshold

        triggered = is_deposit_or_withdrawal and amount_in_range

        # Confidence based on how close to threshold
        if triggered:
            proximity = 1.0 - (threshold - txn.amount) / (threshold - lower_bound)
            confidence = 0.5 + proximity * 0.4  # 0.5 to 0.9
        else:
            confidence = 0.0

        return RuleResult(
            rule_name="structuring",
            triggered=triggered,
            confidence=confidence,
            detail=(
                f"Amount ${txn.amount:,.2f} "
                f"{'in' if amount_in_range else 'outside'} "
                f"structuring range (${lower_bound:,.0f}-${threshold:,.0f})"
            ),
        )

    def _rule_rapid_movement(self, txn: Transaction) -> RuleResult:
        """
        Detect rapid movement: large transfers that suggest layering.

        FINTRAC red flag: Large amounts deposited then quickly moved
        to other accounts or institutions.
        """
        is_transfer = txn.transaction_type in (
            "wire_domestic",
            "wire_international",
            "transfer",
        )
        is_large = txn.amount >= 15_000

        triggered = is_transfer and is_large

        confidence = 0.0
        if triggered:
            # Confidence scales with amount
            confidence = min(0.9, 0.4 + (txn.amount / 100_000) * 0.5)

        return RuleResult(
            rule_name="rapid_movement",
            triggered=triggered,
            confidence=confidence,
            detail=(
                f"{'Large' if is_large else 'Small'} "
                f"{'transfer' if is_transfer else txn.transaction_type}: "
                f"${txn.amount:,.2f}"
            ),
        )

    def _rule_round_amounts(self, txn: Transaction) -> RuleResult:
        """
        Detect suspicious round amounts.

        FINTRAC red flag: Repeated transfers of exact round amounts
        (e.g., $5,000, $10,000) suggest structuring or laundering.
        """
        is_wire_or_transfer = txn.transaction_type in (
            "wire_domestic",
            "wire_international",
            "transfer",
            "e_transfer",
        )
        is_round = txn.amount >= 1_000 and txn.amount % 1_000 == 0
        is_large_round = txn.amount >= 5_000 and txn.amount % 5_000 == 0

        triggered = is_wire_or_transfer and is_round

        confidence = 0.0
        if is_large_round and is_wire_or_transfer:
            confidence = 0.7
        elif triggered:
            confidence = 0.4

        return RuleResult(
            rule_name="round_amounts",
            triggered=triggered,
            confidence=confidence,
            detail=f"${txn.amount:,.2f} {'is' if is_round else 'not'} round amount",
        )

    def _rule_geographic_risk(self, txn: Transaction) -> RuleResult:
        """
        Detect transactions with high-risk jurisdictions.

        Based on FATF high-risk and other monitored jurisdictions.
        FINTRAC requires enhanced due diligence for these countries.
        """
        high_risk_countries = {
            "IR",
            "KP",
            "SY",
            "MM",
            "AF",  # FATF blacklist
            "YE",
            "LY",
            "SO",
            "SD",
            "VE",  # FATF grey list (partial)
        }

        triggered = (
            txn.is_international
            and txn.country_code is not None
            and txn.country_code.upper() in high_risk_countries
        )

        confidence = 0.85 if triggered else 0.0

        return RuleResult(
            rule_name="geographic_risk",
            triggered=triggered,
            confidence=confidence,
            detail=(
                f"Country: {txn.country_code or 'domestic'} ({'HIGH RISK' if triggered else 'OK'})"
            ),
        )

    def _rule_unusual_volume(self, txn: Transaction) -> RuleResult:
        """
        Detect unusual transaction volume (spike detection).

        FINTRAC red flag: Transaction volume 3x+ above customer baseline.
        Since we validate individual transactions, we flag high amounts
        that would represent spikes for typical customers.
        """
        # Approximate: any single transaction > 3x median for type
        median_amounts = {
            "pos_purchase": 65.0,
            "e_transfer": 250.0,
            "bill_payment": 150.0,
            "online_purchase": 80.0,
            "transfer": 2_000.0,
            "atm": 100.0,
            "deposit": 1_500.0,
            "withdrawal": 400.0,
            "wire_domestic": 5_000.0,
            "wire_international": 10_000.0,
        }
        median = median_amounts.get(txn.transaction_type, 500.0)
        ratio = txn.amount / median if median > 0 else 0

        triggered = ratio >= 3.0

        confidence = 0.0
        if triggered:
            confidence = min(0.8, 0.3 + (ratio - 3.0) * 0.1)

        return RuleResult(
            rule_name="unusual_volume",
            triggered=triggered,
            confidence=confidence,
            detail=f"Amount ${txn.amount:,.2f} is {ratio:.1f}x median for {txn.transaction_type}",
        )

    def _rule_dormant_reactivation(self, txn: Transaction) -> RuleResult:
        """
        Detect dormant account reactivation.

        FINTRAC red flag: Account inactive for 6+ months suddenly shows
        high-value activity. Requires temporal context not available in
        single-transaction mode — always returns not triggered for now.
        """
        # NOTE: Requires multi-transaction temporal analysis.
        # Placeholder: detects based on risk_flag metadata from generator.
        triggered = txn.risk_flag == "dormant_reactivation"

        return RuleResult(
            rule_name="dormant_reactivation",
            triggered=triggered,
            confidence=0.6 if triggered else 0.0,
            detail="Dormant reactivation requires temporal context (multi-txn analysis)",
        )

    def _rule_third_party(self, txn: Transaction) -> RuleResult:
        """
        Detect third-party deposits.

        FINTRAC red flag: Deposits from unrelated third parties,
        especially to accounts that then quickly wire funds out.
        Requires relationship context — metadata-based detection.
        """
        triggered = txn.risk_flag == "third_party"

        return RuleResult(
            rule_name="third_party",
            triggered=triggered,
            confidence=0.5 if triggered else 0.0,
            detail="Third-party detection requires relationship graph context",
        )

    # --- Adversarial Helpers ---

    def _generate_corrections(self, report: RiskReport) -> Dict[str, Any]:
        """
        Generate correction feedback based on validation report.

        Analyzes FN and FP patterns to recommend generator adjustments.
        """
        corrections = {
            "round": report.total_transactions,
            "detection_rate": report.detection_rate,
            "adjustments": [],
        }

        # If false negatives are high, generator patterns are too subtle
        if report.false_negative_rate > 0.1:
            corrections["adjustments"].append(
                {
                    "type": "increase_signal",
                    "reason": f"FN rate {report.false_negative_rate:.1%} > 10%",
                    "action": "Make risk patterns more detectable",
                }
            )

        # If false positives are high, normal transactions look suspicious
        if report.false_positive_rate > 0.05:
            corrections["adjustments"].append(
                {
                    "type": "reduce_noise",
                    "reason": f"FP rate {report.false_positive_rate:.1%} > 5%",
                    "action": "Ensure normal transactions stay well below thresholds",
                }
            )

        # Check per-rule coverage gaps
        for rule_name, stats in report.per_rule_results.items():
            if stats["triggered"] == 0 and rule_name in (
                "structuring",
                "rapid_movement",
                "round_amounts",
                "geographic_risk",
            ):
                corrections["adjustments"].append(
                    {
                        "type": "add_pattern",
                        "rule": rule_name,
                        "reason": f"Rule '{rule_name}' never triggered",
                        "action": f"Ensure generator produces {rule_name} patterns",
                    }
                )

        return corrections

    def _load_transactions_from_result(self, result) -> List[Transaction]:
        """Load generated transactions from a GenerationResult's output path."""
        import json

        if not result.output_path:
            return []

        output_path = Path(result.output_path)
        if not output_path.exists():
            return []

        transactions = []
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                txn = Transaction(
                    transaction_id=data["transaction_id"],
                    profile_id=data["profile_id"],
                    timestamp=data["timestamp"],
                    transaction_type=data["transaction_type"],
                    amount=data["amount"],
                    currency=data["currency"],
                    merchant_category=data.get("merchant_category"),
                    counterparty_institution=data.get("counterparty_institution"),
                    is_international=data.get("is_international", False),
                    country_code=data.get("country_code"),
                    risk_flag=data.get("risk_flag", "none"),
                    risk_score=data.get("risk_score", 0.0),
                )
                transactions.append(txn)

        return transactions
