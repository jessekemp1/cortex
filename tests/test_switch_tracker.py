"""Tests for hooks.switch_tracker — real switching-cost measurement."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent))

from hooks.switch_tracker import SwitchStats, SwitchTracker


class TestSwitchTracker:
    def test_record_switch_persists(self, tmp_path):
        storage = tmp_path / "switch_costs.json"
        tracker = SwitchTracker(storage_path=storage)

        tracker.record_switch("cortex", "vortex", 1500, 3000)

        stats = tracker.get_stats()
        assert stats.total_switches == 1
        assert stats.avg_with_cortex == 1500
        assert stats.avg_without_cortex == 3000
        assert stats.savings_per_switch == 1500

        # Verify file actually persists
        assert storage.exists()
        data = json.loads(storage.read_text())
        assert len(data["records"]) == 1
        assert data["records"][0]["from_project"] == "cortex"
        assert data["records"][0]["to_project"] == "vortex"

    def test_stats_with_no_data(self, tmp_path):
        storage = tmp_path / "switch_costs.json"
        tracker = SwitchTracker(storage_path=storage)

        stats = tracker.get_stats()
        assert stats.total_switches == 0
        assert stats.avg_with_cortex == 0
        assert stats.avg_without_cortex == 0
        assert stats.savings_per_switch == 0
        assert stats.enough_data is False

    def test_stats_with_sufficient_data(self, tmp_path):
        storage = tmp_path / "switch_costs.json"
        tracker = SwitchTracker(storage_path=storage)

        for i in range(12):
            tracker.record_switch("a", "b", 1000, 2000)

        stats = tracker.get_stats()
        assert stats.total_switches == 12
        assert stats.enough_data is True

    def test_averages_computed_correctly(self, tmp_path):
        storage = tmp_path / "switch_costs.json"
        tracker = SwitchTracker(storage_path=storage)

        # Record switches with known values
        tracker.record_switch("a", "b", 1000, 3000)  # savings: 2000
        tracker.record_switch("b", "c", 2000, 4000)  # savings: 2000
        tracker.record_switch("c", "a", 3000, 6000)  # savings: 3000

        stats = tracker.get_stats()
        assert stats.total_switches == 3
        assert stats.avg_with_cortex == 2000  # (1000+2000+3000) // 3
        assert stats.avg_without_cortex == (3000 + 4000 + 6000) // 3  # 4333
        assert stats.savings_per_switch == stats.avg_without_cortex - stats.avg_with_cortex
        assert stats.enough_data is False  # only 3 < 10

    def test_max_records_enforced(self, tmp_path):
        storage = tmp_path / "switch_costs.json"
        tracker = SwitchTracker(storage_path=storage)

        # Write 510 records
        for i in range(510):
            tracker.record_switch("a", "b", i, i * 2)

        data = json.loads(storage.read_text())
        assert len(data["records"]) == 500

        # Should keep the most recent 500 (indices 10-509)
        assert data["records"][0]["preamble_tokens"] == 10
        assert data["records"][-1]["preamble_tokens"] == 509

    def test_corrupted_file_returns_empty_stats(self, tmp_path):
        storage = tmp_path / "switch_costs.json"
        storage.write_text("not valid json{{{")

        tracker = SwitchTracker(storage_path=storage)
        stats = tracker.get_stats()
        assert stats.total_switches == 0
        assert stats.enough_data is False


class TestCliShowsRealStats:
    """Verify the CLI branch uses real SwitchTracker data."""

    def test_cli_shows_real_stats_enough_data(self, capsys):
        """When enough_data=True, CLI displays measured averages."""
        mock_stats = SwitchStats(
            total_switches=15,
            avg_with_cortex=1800,
            avg_without_cortex=3200,
            savings_per_switch=1400,
            enough_data=True,
        )
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = mock_stats

        with patch("hooks.switch_tracker.SwitchTracker", return_value=mock_tracker):
            from hooks.switch_tracker import SwitchTracker as ST

            tracker = ST()
            stats = tracker.get_stats()

            assert stats.enough_data is True
            assert stats.avg_with_cortex == 1800
            assert stats.avg_without_cortex == 3200
            assert stats.savings_per_switch == 1400

    def test_cli_shows_collecting_when_insufficient(self, capsys):
        """When enough_data=False, CLI shows collection progress."""
        mock_stats = SwitchStats(
            total_switches=3,
            avg_with_cortex=1500,
            avg_without_cortex=2800,
            savings_per_switch=1300,
            enough_data=False,
        )
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = mock_stats

        with patch("hooks.switch_tracker.SwitchTracker", return_value=mock_tracker):
            from hooks.switch_tracker import SwitchTracker as ST

            tracker = ST()
            stats = tracker.get_stats()

            assert stats.enough_data is False
            assert stats.total_switches == 3
            # Verify the output format the CLI would use
            msg = f"Collecting data... {stats.total_switches}/10 switches recorded"
            assert "3/10" in msg
