"""Proof harness fixtures — shared ground-truth corpus for the cortex
core-outcomes proof suite (record / recall / track).

This package holds *data only* (no test logic): a set of synthetic decisions
with deliberately distinctive tokens so a retrieval hit is unambiguous, plus
seed outcomes with a known success/partial/failed mix so the accuracy formula
can be asserted by exact equality. Both the hermetic proof tests
(``test_core_outcomes_proof``) and the decisions-included recall benchmark
(``test_decision_recall_benchmark``) import from here so ground truth lives in
exactly one place.
"""
