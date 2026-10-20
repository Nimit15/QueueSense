"""
Regression tests for SimulationRunner metric semantics.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from queuesense.simulation.runner import SimulationRunner
from queuesense.controllers.fixed_time import FixedTimeController


class TestSimulationRunnerMetrics:
    """Test correct metric accumulation and naming."""

    def setup_method(self):
        self.runner = SimulationRunner(
            net_file="dummy.net.xml",
            route_files=["dummy.rou.xml"],
            output_dir="results/test",
            step_length=1.0,
            duration=100,
            warmup_time=0,
            controller=FixedTimeController(),
            gui=False,
            csv_prefix="test",
        )
        self.runner._arrived_cumulative = 0

    @patch("queuesense.simulation.runner.traci")
    def test_arrivals_accumulate_correctly(self, mock_traci):
        """Arrivals from consecutive steps should accumulate."""
        # Mock SUMO API
        mock_traci.simulation.getTime.return_value = 1.0
        mock_traci.simulation.getArrivedNumber.return_value = 5
        mock_traci.simulation.getMinExpectedNumber.return_value = 10
        mock_traci.simulation.getDepartedNumber.return_value = 5
        mock_traci.simulation.getLoadedNumber.return_value = 20
        mock_traci.edge.getLastStepVehicleIDs.return_value = []
        mock_traci.edge.getLastStepOccupancy.return_value = 0.5

        # First step
        self.runner._log_metrics(step=0)

        # Second step with different arrivals
        mock_traci.simulation.getTime.return_value = 2.0
        mock_traci.simulation.getArrivedNumber.return_value = 3
        self.runner._log_metrics(step=1)

        # Check cumulative accumulation
        assert len(self.runner.metrics) == 2
        assert self.runner.metrics[0]["arrived_this_step"] == 5
        assert self.runner.metrics[0]["arrived_cumulative"] == 5
        assert self.runner.metrics[1]["arrived_this_step"] == 3
        assert self.runner.metrics[1]["arrived_cumulative"] == 8

    @patch("queuesense.simulation.runner.traci")
    def test_zero_arrivals_preserve_cumulative(self, mock_traci):
        """Zero arrivals should not erase cumulative total."""
        mock_traci.simulation.getTime.return_value = 1.0
        mock_traci.simulation.getArrivedNumber.return_value = 5
        mock_traci.simulation.getMinExpectedNumber.return_value = 10
        mock_traci.simulation.getDepartedNumber.return_value = 5
        mock_traci.simulation.getLoadedNumber.return_value = 20
        mock_traci.edge.getLastStepVehicleIDs.return_value = []
        mock_traci.edge.getLastStepOccupancy.return_value = 0.5

        self.runner._log_metrics(step=0)

        # Zero arrivals step
        mock_traci.simulation.getTime.return_value = 2.0
        mock_traci.simulation.getArrivedNumber.return_value = 0
        self.runner._log_metrics(step=1)

        assert self.runner.metrics[1]["arrived_this_step"] == 0
        assert self.runner.metrics[1]["arrived_cumulative"] == 5

    @patch("queuesense.simulation.runner.traci")
    def test_remaining_expected_separate_from_completed(self, mock_traci):
        """remaining_expected should be distinct from arrived metrics."""
        mock_traci.simulation.getTime.return_value = 1.0
        mock_traci.simulation.getArrivedNumber.return_value = 3
        mock_traci.simulation.getMinExpectedNumber.return_value = 25  # vehicles remaining
        mock_traci.simulation.getDepartedNumber.return_value = 5
        mock_traci.simulation.getLoadedNumber.return_value = 30
        mock_traci.edge.getLastStepVehicleIDs.return_value = []
        mock_traci.edge.getLastStepOccupancy.return_value = 0.5

        self.runner._log_metrics(step=0)

        # remaining_expected is vehicles still in system
        assert self.runner.metrics[0]["remaining_expected"] == 25
        # arrived_cumulative is completed trips
        assert self.runner.metrics[0]["arrived_cumulative"] == 3
        # Legacy completed column now maps to arrived_cumulative (completed trips)
        # per the corrected semantics
        assert self.runner.metrics[0]["completed"] == 3

    @patch("queuesense.simulation.runner.traci")
    def test_metrics_columns_present(self, mock_traci):
        """All required metric columns should be present."""
        mock_traci.simulation.getTime.return_value = 1.0
        mock_traci.simulation.getArrivedNumber.return_value = 0
        mock_traci.simulation.getMinExpectedNumber.return_value = 10
        mock_traci.simulation.getDepartedNumber.return_value = 0
        mock_traci.simulation.getLoadedNumber.return_value = 10
        mock_traci.edge.getLastStepVehicleIDs.return_value = []
        mock_traci.edge.getLastStepOccupancy.return_value = 0.5

        self.runner._log_metrics(step=0)
        row = self.runner.metrics[0]

        required = [
            "time", "arrived_this_step", "arrived_cumulative",
            "departed_this_step", "loaded_this_step",
            "remaining_expected", "completed",
            "queue_north", "queue_south", "queue_east", "queue_west",
            "spillback_ns", "spillback_ew"
        ]
        for col in required:
            assert col in row, f"Missing column: {col}"
