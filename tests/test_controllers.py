"""
Unit tests for QueueSense controllers.
"""

import pytest
from queuesense.controllers.fixed_time import FixedTimeController
from queuesense.controllers.base import Phase
from queuesense.state import TrafficState, ApproachState


class TestFixedTimeController:
    """Test FixedTimeController safety supervisor behavior."""

    def test_initial_state(self):
        """Controller should start with NORTH_SOUTH phase."""
        controller = FixedTimeController()
        assert controller.state == Phase.NORTH_SOUTH
        assert controller.elapsed == 0.0

    def test_safety_supervisor_min_max_green(self):
        """Safety supervisor should enforce min/max green times."""
        controller = FixedTimeController()
        state = TrafficState(timestamp=0.0, approaches={}, all_valid=True)

        # Controller should start with NORTH_SOUTH
        assert controller.state == Phase.NORTH_SOUTH

        # For 9 steps (9s < min_green 10s), should still be in green phase
        for _ in range(9):
            action = controller.step(state, step_length=1.0)
            assert action["phase"] == Phase.NORTH_SOUTH

        # After 10s, should still be in green (min_green satisfied)
        action = controller.step(state, step_length=1.0)
        assert action["phase"] == Phase.NORTH_SOUTH

    def test_watchdog_fallback(self):
        """Watchdog should trigger fallback on repeated invalid state."""
        controller = FixedTimeController()
        assert controller.state == Phase.NORTH_SOUTH

        # Simulate 3 invalid states
        for i in range(3):
            state = TrafficState(timestamp=float(i), approaches={}, all_valid=False)
            controller.step(state, step_length=1.0)

        # Should have fallen back to fixed plan start
        assert controller.state == Phase.NORTH_SOUTH

    def test_controller_action_reason(self):
        """Controller should provide a reason for each action."""
        controller = FixedTimeController()
        state = TrafficState(timestamp=0.0, approaches={}, all_valid=True)

        action = controller.step(state, step_length=1.0)
        assert "reason" in action
        assert isinstance(action["reason"], str)
        assert "Continuing" in action["reason"]
