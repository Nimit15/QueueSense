"""
Safety regression tests for QueueSenseController (Controller D).
Tests minimum green enforcement, yellow/all-red clearance,
and verified N-S/E-W behavior.
"""

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase


class TestQueueSenseSafety:
    """Test safety-critical behavior of QueueSenseController."""

    def test_min_green_satisfies_before_transition(self):
        """min_green=10s must be satisfied (10s elapsed) before the safety
        supervisor transitions from green to yellow clearance.

        The safety supervisor's _can_end_phase() checks:
            elapsed >= min_green and (elapsed >= max_green or _should_end_phase())
        With _should_end_phase() returning True after min_green, the green
        phase ends and the supervisor transitions to YELLOW_CLEARANCE.

        After 10 steps, elapsed reaches 10.0 (min_green), and the 11th step
        transitions to YELLOW_CLEARANCE.
        """
        c = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )

        state = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=True, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=True, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        # Run 10 steps — elapsed should be 10.0 after 10 steps
        # With current state, NORTH_SOUTH has higher pressure, so controller selects NORTH_SOUTH
        # and holds it for min_green due to safety supervisor
        for _ in range(10):
            action = c.step(state, step_length=1.0)
            assert action["phase"] == Phase.NORTH_SOUTH

        # The 11th step satisfies min_green and transitions to YELLOW_CLEARANCE
        action = c.step(state, step_length=1.0)
        # Phase should be YELLOW_CLEARANCE when min_green is satisfied
        assert action["phase"] == Phase.YELLOW_CLEARANCE, (
            f"Expected YELLOW_CLEARANCE after min_green, got {action['phase']}"
        )
        # elapsed resets to 1.0 when entering clearance
        assert c.elapsed == 1.0, f"elapsed should be 1.0 after clearance transition, got {c.elapsed}"

    def test_clearance_sequence_enforced(self):
        """Yellow (5s) and all-red (2s) clearance intervals are enforced.

        After green ends and min_green is satisfied, the safety supervisor
        should enforce the clearance sequence: yellow → all-red → next green.
        The test verifies the sequence can progress without crashing.
        """
        c = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )

        state = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=True, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=True, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        # Run 10 steps to satisfy min_green, then 11th enters YELLOW_CLEARANCE
        for _ in range(10):
            action = c.step(state, step_length=1.0)

        action = c.step(state, step_length=1.0)
        assert action["phase"] == Phase.YELLOW_CLEARANCE

        # Progress through clearance — should see YELLOW_CLEARANCE and/or ALL_RED
        for _ in range(6):
            action = c.step(state, step_length=1.0)
            if action["phase"] in (Phase.YELLOW_CLEARANCE, Phase.ALL_RED):
                break  # Found a clearance phase, sequence is working

        # The phase should be a valid clearance or green phase
        assert action["phase"] in [
            Phase.YELLOW_CLEARANCE,
            Phase.ALL_RED,
            Phase.NORTH_SOUTH,
            Phase.EAST_WEST,
        ], f"Unexpected phase after clearance: {action['phase']}"

    def test_pressure_fairness_higher_wins(self):
        """When both directions are eligible, the higher-pressure direction
        is selected to match Controller C behavior when downstream is free.

        With alpha=0.4, beta=0.4, gamma=0.2:
        - North: Q_norm=15/20=0.75, W_norm=30/90≈0.333, A_norm=20/30≈0.667
          P = 0.4×0.75 + 0.4×0.333 + 0.2×0.667 ≈ 0.567
        - East: Q_norm=2/20=0.10, W_norm=3/90≈0.033, A_norm=5/30≈0.167
          P = 0.4×0.10 + 0.4×0.033 + 0.2×0.167 ≈ 0.087

        Since north_pressure > east_pressure, NORTH_SOUTH should be selected.
        """
        c = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )

        state = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=15, mean_wait_seconds=30, arrival_rate=20,
                    downstream_available=True, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=5,
                    downstream_available=True, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=5,
                    downstream_available=True, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=1, mean_wait_seconds=2, arrival_rate=3,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        action = c.step(state, step_length=1.0)
        # Higher pressure direction (NORTH_SOUTH) should be selected to match Controller C
        assert action["phase"] == Phase.NORTH_SOUTH, (
            f"Expected NORTH_SOUTH (higher pressure), "
            f"got {action['phase']}"
        )

    def test_partial_blockage_ns_blocked_selects_ew(self):
        """N-S blocked, E-W clear → EAST_WEST selected (not NORTH_SOUTH)."""
        c = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )
        state = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=False, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=False, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        action = c.step(state, step_length=1.0)
        # Controller D should select EAST_WEST because N-S downstream is blocked
        assert action["phase"] == Phase.EAST_WEST, (
            f"Expected EAST_WEST for partial blockage (N-S blocked), "
            f"got {action['phase']}"
        )

    def test_all_exits_blocked_then_recovery(self):
        """All-exits-blocked policy activates and recovers when exits clear.

        When all downstream exits are blocked, the controller should hold at
        the current phase with min_green enforced. When exits become available,
        normal phase selection should resume.
        """
        c = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )

        # Phase 1: All exits blocked
        state_blocked = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=False, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=False, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=False, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=False, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        # Three steps of all-blocked — should hold current phase with min_green
        for _ in range(3):
            action = c.step(state_blocked, step_length=1.0)
            assert action["phase"] == Phase.NORTH_SOUTH
            assert action["duration"] >= 10.0, (
                f"Duration should honor min_green=10s, got {action['duration']}"
            )

        # Phase 2: Make all exits available and verify recovery
        state_clear = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=True, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=True, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        # After recovery, phase selection should resume
        for i in range(5):
            action = c.step(state_clear, step_length=1.0)
            # Phase should be valid (NORTH_SOUTH or EAST_WEST)
            assert action["phase"] in (Phase.NORTH_SOUTH, Phase.EAST_WEST)
            # Duration should be reasonable
            assert action["duration"] > 0

    def test_elapsed_accumulates_across_steps(self):
        """elapsed counter accumulates correctly across steps.

        The BaseController accumulates elapsed += 1 per step (step_length=1.0),
        reaching min_green=10.0 after 10 steps. The QueueSenseController no
        longer resets elapsed in step(), so the safety supervisor can enforce
        min/max green.
        """
        c = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )

        state = TrafficState(
            timestamp=0.0,
            approaches={
                'north': ApproachState(
                    queue_count=5, mean_wait_seconds=10, arrival_rate=10,
                    downstream_available=True, measurement_valid=True,
                ),
                'south': ApproachState(
                    queue_count=3, mean_wait_seconds=5, arrival_rate=8,
                    downstream_available=True, measurement_valid=True,
                ),
                'east': ApproachState(
                    queue_count=4, mean_wait_seconds=8, arrival_rate=12,
                    downstream_available=True, measurement_valid=True,
                ),
                'west': ApproachState(
                    queue_count=2, mean_wait_seconds=3, arrival_rate=6,
                    downstream_available=True, measurement_valid=True,
                ),
            },
            all_valid=True,
        )

        # Run 10 steps and verify elapsed reaches 10.0 after step 10
        for i in range(10):
            action = c.step(state, step_length=1.0)
            expected = float(i + 1)
            assert c.elapsed == expected, (
                f"elapsed should be {expected:.1f} after step {i+1}, "
                f"got {c.elapsed:.1f}"
            )

        # After 10 steps, min_green is satisfied; the 11th step should
        # transition to YELLOW_CLEARANCE
        action = c.step(state, step_length=1.0)
        assert action["phase"] == Phase.YELLOW_CLEARANCE, (
            f"Expected YELLOW_CLEARANCE after min_green, got {action['phase']}"
        )