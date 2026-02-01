#!/usr/bin/env python3
"""
Cortex Data Quality Framework

Tracks six dimensions of data quality:
- Completeness: Required fields present
- Consistency: No contradictions
- Accuracy: Factually correct
- Timeliness: Data freshness
- Uniqueness: No duplicates
- Validity: Format/schema valid
"""

from .data_quality import DataQualityTracker, QualityDimensions
from .dimensions import DimensionCheckers
from .report import QualityReport, generate_markdown_report

__all__ = [
    "DataQualityTracker",
    "QualityDimensions",
    "DimensionCheckers",
    "QualityReport",
    "generate_markdown_report",
]
