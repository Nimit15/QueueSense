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


class TestD1D2GateDecisionPath:
    """End-to-end gate decision-path regression test.

    Same valid traffic state is fed to D1 (spillback_gate_enabled=False) and
    D2 (spillback_gate_enabled=True).  EAST_WEST's mapped receiving link is
    blocked above the 0.30 threshold; NORTH_SOUTH is clear.  The ungated
    pressure policy favours EAST_WEST, and minimum-green / clearance
    conditions permit a safe transition.

    Expected:
      - D1 (gate OFF) ignores downstream blockage and selects EAST_WEST.
      - D2 (gate ON) suppresses the blocked EAST_WEST movement and selects
        NORTH_SOUTH instead.

    This test fails if the gate only logs congestion without changing the
    applied control decision.
    """

    @staticmethod
    def _blocked_ew_clear_ns_state():
        """EAST_WEST receiving links blocked; NORTH_SOUTH clear; EW higher pressure."""
        return TrafficState(
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
                    downstream_available=False, measurement_valid=True,
                ),
                "west": ApproachState(
                    queue_count=1, mean_wait_seconds=2, arrival_rate=3,
                    downstream_available=False, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

    def test_d1_selects_ungated_east_west(self):
        """D1 (gate OFF) must retain the ungated EAST_WEST choice."""
        d1 = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.30, max_wait=90.0,
            spillback_gate_enabled=False,
        )
        state = self._blocked_ew_clear_ns_state()

        # Advance past min_green (10s) so a transition is permitted.
        for _ in range(20):
            action = d1.step(state, step_length=1.0)

        assert d1.state == Phase.EAST_WEST, (
            f"D1 (gate OFF) should select ungated EAST_WEST, got {d1.state}"
        )

    def test_d2_selects_north_south_when_ew_blocked(self):
        """D2 (gate ON) must suppress blocked EAST_WEST and select NORTH_SOUTH."""
        d2 = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.30, max_wait=90.0,
            spillback_gate_enabled=True,
        )
        state = self._blocked_ew_clear_ns_state()

        for _ in range(20):
            action = d2.step(state, step_length=1.0)

        assert d2.state == Phase.NORTH_SOUTH, (
            f"D2 (gate ON) should suppress blocked EAST_WEST and select "
            f"NORTH_SOUTH, got {d2.state}"
        )

    def test_d1_and_d2_diverge_on_identical_state(self):
        """D1 and D2 must make different phase choices on identical state."""
        d1 = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.30, max_wait=90.0,
            spillback_gate_enabled=False,
        )
        d2 = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.30, max_wait=90.0,
            spillback_gate_enabled=True,
        )
        state = self._blocked_ew_clear_ns_state()

        for _ in range(20):
            d1.step(state, step_length=1.0)
            d2.step(state, step_length=1.0)

        assert d1.state != d2.state, (
            f"D1 ({d1.state}) and D2 ({d2.state}) must diverge when the "
            f"gate is the only differing configuration"
        )
        assert d1.state == Phase.EAST_WEST
        assert d2.state == Phase.NORTH_SOUTH

    def test_d2_gate_tags_intervention_when_ew_blocked(self):
        """D2 must record a gate intervention, not silently hold the phase."""
        d2 = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.30, max_wait=90.0,
            spillback_gate_enabled=True,
        )
        state = self._blocked_ew_clear_ns_state()

        gate_events = []
        reasons = []
        for _ in range(20):
            action = d2.step(state, step_length=1.0)
            gate_events.append(action.get("gate_event"))
            reasons.append(str(action.get("reason", "")))

        assert any(e in ("phase_change", "hold") for e in gate_events), (
            f"D2 must record at least one gate intervention "
            f"(phase_change/hold), got {gate_events}"
        )
        assert any("GATE_INTERVENTION" in r for r in reasons), (
            "D2 reason string must carry the GATE_INTERVENTION marker"
        )

    def test_d1_gate_does_not_tag_intervention(self):
        """D1 (gate OFF) must never record a gate intervention."""
        d1 = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.30, max_wait=90.0,
            spillback_gate_enabled=False,
        )
        state = self._blocked_ew_clear_ns_state()

        gate_events = []
        for _ in range(20):
            action = d1.step(state, step_length=1.0)
            gate_events.append(action.get("gate_event"))

        # gate_event is absent (None) during clearance phases; the only
        # acceptable values for D1 are "none" and None.
        assert all(e in ("none", None) for e in gate_events), (
            f"D1 (gate OFF) must never record a gate intervention, got {gate_events}"
        )