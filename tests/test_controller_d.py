"""
Unit tests for QueueSenseController (Controller D).
Tests downstream blockage eligibility, all-exits-blocked policy,
partial blockage fairness, and watchdog integration.
"""

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase


class TestQueueSenseController:
    """Test QueueSenseController phase selection and blockage logic."""

    def setup_method(self):
        self.controller = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0
        )

    def test__select_phase_from_pressure_all_blocked(self):
        """All approaches have blocked downstream exits → returns None."""
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=False, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=False, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=False, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=False, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        result = self.controller._select_phase_from_pressure(state)
        assert result is None

    def test__select_phase_from_pressure_ns_only(self):
        """Only N-S direction has eligible approaches → returns NORTH_SOUTH."""
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=True, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=True, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=False, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=False, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        result = self.controller._select_phase_from_pressure(state)
        assert result == Phase.NORTH_SOUTH

    def test__select_phase_from_pressure_ew_only(self):
        """Only E-W direction has eligible approaches → returns EAST_WEST."""
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=False, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=False, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        result = self.controller._select_phase_from_pressure(state)
        assert result == Phase.EAST_WEST

    def test__select_phase_from_pressure_both_eligible_higher_pressure(self):
        """Both directions eligible → selects direction with higher pressure.

        North approach has high pressure (high queue/wait/arrival), east has low pressure.
        Expected: select NORTH_SOUTH (higher pressure).
        """
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=15, mean_wait_seconds=30, arrival_rate=20,
                    downstream_available=True, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=5,
                    downstream_available=True, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=5,
                    downstream_available=True, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=1, mean_wait_seconds=2, arrival_rate=3,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        result = self.controller._select_phase_from_pressure(state)
        assert result == Phase.NORTH_SOUTH

    def test__select_phase_from_pressure_both_eligible_lower_pressure(self):
        """Both directions eligible → selects direction with lower pressure (reverse).

        East approach has high pressure, north has low pressure.
        Expected: select EAST_WEST (lower pressure).
        """
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=5,
                    downstream_available=True, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=1, mean_wait_seconds=2, arrival_rate=3,
                    downstream_available=True, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=15, mean_wait_seconds=30, arrival_rate=20,
                    downstream_available=True, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=1, mean_wait_seconds=2, arrival_rate=3,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        result = self.controller._select_phase_from_pressure(state)
        assert result == Phase.EAST_WEST

    def test_step_all_exits_blocked_returns_valid_action(self):
        """All-exits-blocked step() returns a valid action dict without crashing."""
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=False, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=False, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=False, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=False, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        # Controller starts in NORTH_SOUTH (from BaseController.__init__)
        action = self.controller.step(state, step_length=1.0)
        assert "phase" in action, f"Action missing 'phase': {action}"
        assert "duration" in action, f"Action missing 'duration': {action}"
        assert "reason" in action, f"Action missing 'reason': {action}"
        # Duration should honor min_green = 10s
        assert action["duration"] >= 10.0, (
            f"Duration {action['duration']} < min_green 10s"
        )
        # Phase should be the current phase (NORTH_SOUTH)
        assert action["phase"] == Phase.NORTH_SOUTH

    def test_step_partial_blockage_ns_blocked_ew_clear(self):
        """N-S blocked, E-W clear → EAST_WEST selected (Controller C would select N-S)."""
        controller = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0
        )
        state = TrafficState(
            timestamp=0.0,
            approaches={
                "north": ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=False, measurement_valid=True,
                ),
                "south": ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=False, measurement_valid=True,
                ),
                "east": ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )
        action = controller.step(state, step_length=1.0)
        # Controller D should select EAST_WEST because N-S downstream is blocked
        assert action["phase"] == Phase.EAST_WEST, (
            f"Expected EAST_WEST for partial blockage, got {action['phase']}"
        )

    def test_watchdog_with_controller_d(self):
        """Watchdog triggers fallback on 3 consecutive invalid TrafficState updates."""
        state_valid = TrafficState(
            timestamp=0.0,
            approaches={},
            all_valid=True,
        )
        state_invalid = TrafficState(
            timestamp=0.0,
            approaches={},
            all_valid=False,
        )
        # Three invalid steps → watchdog triggers on the 3rd
        for _ in range(3):
            self.controller.step(state_invalid, step_length=1.0)
        # After watchdog: state reset to fixed plan start (NORTH_SOUTH),
        # consecutive_invalid reset to 0
        assert self.controller.state == Phase.NORTH_SOUTH
        assert self.controller.consecutive_invalid == 0

    def test_step_then_watchdog_reset(self):
        """After watchdog fallback, subsequent valid steps resume normal operation."""
        state_invalid = TrafficState(
            timestamp=0.0,
            approaches={},
            all_valid=False,
        )
        state_valid = TrafficState(
            timestamp=0.0,
            approaches={},
            all_valid=True,
        )
        # Trigger watchdog with 3 invalid steps
        for _ in range(3):
            self.controller.step(state_invalid, step_length=1.0)
        assert self.controller.state == Phase.NORTH_SOUTH
        assert self.controller.consecutive_invalid == 0
        # Now 3 valid steps should keep watchdog clear
        for _ in range(3):
            self.controller.step(state_valid, step_length=1.0)
        assert self.controller.consecutive_invalid == 0
        # State should still be NORTH_SOUTH (or whatever the fixed plan dictates)
        assert self.controller.state == Phase.NORTH_SOUTH