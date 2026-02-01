#!/usr/bin/env python3
"""
Quality Report Generation

Generates comprehensive quality reports with:
- Aggregate statistics
- Dimension breakdowns
- Trend tracking
- Markdown formatting
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from intelligence.quality.data_quality import QualityDimensions


@dataclass
class QualityReport:
    """Comprehensive quality report."""

    timestamp: str
    total_items_assessed: int
    average_dimensions: QualityDimensions
    dimension_details: Dict[str, Dict[str, Any]]
    trends: Optional[Dict[str, List[float]]] = None

    def overall_quality(self) -> float:
        """Get overall quality score."""
        return self.average_dimensions.overall_score()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "total_items_assessed": self.total_items_assessed,
            "overall_quality": self.overall_quality(),
            "average_dimensions": self.average_dimensions.to_dict(),
            "dimension_details": self.dimension_details,
            "trends": self.trends,
        }


def generate_markdown_report(report: QualityReport) -> str:
    """
    Generate markdown-formatted quality report.

    Args:
        report: QualityReport to format

    Returns:
        Markdown-formatted report string
    """
    lines = []

    # Header
    lines.append("# Cortex Data Quality Report")
    lines.append("")
    lines.append(f"**Generated**: {report.timestamp}")
    lines.append(f"**Items Assessed**: {report.total_items_assessed}")
    lines.append(f"**Overall Quality**: {report.overall_quality():.1%}")
    lines.append("")

    # Dimension scores
    lines.append("## Quality Dimensions")
    lines.append("")
    lines.append("| Dimension | Score | Status |")
    lines.append("|-----------|-------|--------|")

    dims = report.average_dimensions
    for dimension in [
        "completeness",
        "consistency",
        "accuracy",
        "timeliness",
        "uniqueness",
        "validity",
    ]:
        score = getattr(dims, dimension)
        status = _get_status_emoji(score)
        lines.append(f"| {dimension.capitalize()} | {score:.1%} | {status} |")

    lines.append("")

    # Dimension details
    if report.dimension_details:
        lines.append("## Details by Data Type")
        lines.append("")

        for data_type, details in report.dimension_details.items():
            lines.append(f"### {data_type.capitalize()}")
            lines.append("")
            lines.append(f"- **Count**: {details.get('count', 0)}")
            lines.append(f"- **Average Quality**: {details.get('avg_quality', 0.0):.1%}")
            lines.append("")

    # Trends
    if report.trends:
        lines.append("## Trends")
        lines.append("")

        for dimension, trend_data in report.trends.items():
            if len(trend_data) >= 2:
                current = trend_data[-1]
                previous = trend_data[-2]
                change = current - previous
                trend_arrow = "↑" if change > 0 else "↓" if change < 0 else "→"

                lines.append(
                    f"- **{dimension.capitalize()}**: {current:.1%} {trend_arrow} "
                    f"({abs(change):.1%} from previous)"
                )

        lines.append("")

    # Quality thresholds
    lines.append("## Quality Assessment")
    lines.append("")
    overall = report.overall_quality()

    if overall >= 0.8:
        lines.append("**Status**: Excellent - Data quality is high across all dimensions")
    elif overall >= 0.6:
        lines.append(
            "**Status**: Good - Data quality is acceptable with some room for improvement"
        )
    elif overall >= 0.4:
        lines.append(
            "**Status**: Fair - Data quality needs attention in several dimensions"
        )
    else:
        lines.append(
            "**Status**: Poor - Data quality is low and requires immediate improvement"
        )

    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")

    recommendations = []

    # Check each dimension
    if dims.completeness < 0.7:
        recommendations.append(
            "- **Completeness**: Ensure all required fields are populated when logging data"
        )

    if dims.consistency < 0.7:
        recommendations.append(
            "- **Consistency**: Review data validation rules to prevent contradictory entries"
        )

    if dims.accuracy < 0.7:
        recommendations.append(
            "- **Accuracy**: Implement additional fact-checking for critical data"
        )

    if dims.timeliness < 0.7:
        recommendations.append(
            "- **Timeliness**: Archive or refresh stale data to improve freshness"
        )

    if dims.uniqueness < 0.9:
        recommendations.append(
            "- **Uniqueness**: Implement duplicate detection to prevent redundant entries"
        )

    if dims.validity < 0.7:
        recommendations.append(
            "- **Validity**: Add schema validation to ensure data format compliance"
        )

    if recommendations:
        lines.extend(recommendations)
    else:
        lines.append("- No immediate actions required - quality metrics are healthy")

    lines.append("")

    return "\n".join(lines)


def _get_status_emoji(score: float) -> str:
    """Get status indicator for a score."""
    if score >= 0.8:
        return "✅ Excellent"
    elif score >= 0.6:
        return "✓ Good"
    elif score >= 0.4:
        return "⚠️ Fair"
    else:
        return "❌ Poor"


def compare_reports(
    current: QualityReport, previous: QualityReport
) -> Dict[str, Dict[str, float]]:
    """
    Compare two quality reports to identify trends.

    Args:
        current: Current quality report
        previous: Previous quality report

    Returns:
        Dictionary of dimension changes
    """
    changes = {}

    for dimension in [
        "completeness",
        "consistency",
        "accuracy",
        "timeliness",
        "uniqueness",
        "validity",
    ]:
        current_score = getattr(current.average_dimensions, dimension)
        previous_score = getattr(previous.average_dimensions, dimension)

        changes[dimension] = {
            "current": current_score,
            "previous": previous_score,
            "change": current_score - previous_score,
            "percent_change": (
                ((current_score - previous_score) / previous_score * 100)
                if previous_score > 0
                else 0.0
            ),
        }

    return changes
