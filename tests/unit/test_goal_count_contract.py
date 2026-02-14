from pathlib import Path

from cli import _goal_counts_from_parser


def test_goal_count_parser_reads_action_plan_statuses(tmp_path: Path) -> None:
    action_plan = tmp_path / "ACTION_PLAN.md"
    action_plan.write_text(
        """## Priority A

#### 1. **Ship orchestration hardening**
**Status:** in_progress

#### 2. **Close macro test gaps**
**Status:** pending
"""
    )

    in_progress, pending = _goal_counts_from_parser(tmp_path) or (0, 0)
    assert in_progress == 1
    assert pending == 1


def test_goal_count_parser_returns_zero_when_action_plan_missing(tmp_path: Path) -> None:
    in_progress, pending = _goal_counts_from_parser(tmp_path) or (-1, -1)
    assert in_progress == 0
    assert pending == 0
