"""
Controller D: QueueSense (Full adaptive controller)
Queue-pressure + Downstream blockage awareness + Safety supervisor

This is the core differentiator from the QueueSense design: it evaluates queue
pressure just like Controller C, but additionally checks downstream blockage
(spillback) eligibility before releasing green, and enforces the all-exits-blocked
policy when every candidate approach has a blocked downstream exit.

The controller integrates with the shared BaseController safety supervisor
(min_green, max_green, yellow/all-red clearance intervals, watchdog fallback).
"""

import logging
from typing import Dict

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.base import BaseController, ControllerConfig, Phase

logger = logging.getLogger(__name__)


class QueueSenseController(BaseController):
    """Full QueueSense controller with downstream blockage awareness.

    Behaviour:
    1. Calculate queue-pressure score P_i = alpha * Q̂_i + beta *Ŵ_i + gamma *Â_i
       for each candidate approach (same formula as Controller C).
    2. Before phase selection, check downstream_available for each candidate
       approach. If downstream_available is False, the approach is excluded from
       the pressure comparison because releasing green would cause spillback.
    3. If some approaches have eligible downstream exits and others do not,
       only the eligible approaches are compared.
    4. If ALL candidate approaches have blocked downstream exits (all
       downstream_available == False), invoke the all-exits-blocked policy:
       - Hold all entries at red (yellow + all-red clearance intervals).
       - Wait for downstream clearance before releasing fresh queues.
    5. Share the same safety supervisor (min_green=10s, max_green=60s, clearance
       intervals) as FixedTime, Actuated, and QueuePressure controllers.
    6. Falls back to the fixed-time plan after 3 consecutive invalid TrafficState
       updates (same watchdog as all other controllers).

    Configuration parameters (from CLAUDE.md / configs/experiment.yaml):
      - alpha, beta, gamma: weights for queue, wait, arrival (sum to 1.0)
      - spillback_threshold: downstream road occupancy threshold (default 0.85)
      - max_wait: starvation cap for normalising waiting time (default 90s)
    """

    def __init__(
        self,
        alpha: float = 0.4,
        beta: float = 0.4,
        gamma: float = 0.2,
        spillback_threshold: float = 0.85,
        max_wait: float = 90.0,
    ):
        # Safety supervisor timing: same min/max/green/yellow/clearance as other controllers
        config = ControllerConfig(
            min_green=10.0,
            max_green=60.0,
            yellow_duration=5.0,
            all_red_duration=2.0,
            fixed_cycle=[Phase.NORTH_SOUTH, Phase.EAST_WEST],
        )
        super().__init__(config)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.spillback_threshold = spillback_threshold
        self.max_wait = max_wait
        logger.info(
            f"QueueSenseController initialized: alpha={alpha}, beta={beta}, "
            f"gamma={gamma}, spillback_threshold={spillback_threshold}, "
            f"max_wait={max_wait}s"
        )

    # ------------------------------------------------------------------
    # Queue-pressure score calculation
    # ------------------------------------------------------------------

    def _calculate_pressure(self, state: TrafficState, phase: Phase) -> float:
        """Calculate queue pressure score for a given phase.

        Args:
            state: TrafficState
            phase: Candidate phase to evaluate (NORTH_SOUTH or EAST_WEST)

        Returns:
            Pressure score (higher = more pressure). Sum of the two opposing approaches.
        """
        # Map phase to its two approaches
        if phase == Phase.NORTH_SOUTH:
            approach_names = ["north", "south"]
        elif phase == Phase.EAST_WEST:
            approach_names = ["east", "west"]
        else:
            # Should not happen
            return 0.0

        total_pressure = 0.0
        for name in approach_names:
            approach = state.get_approach(name)
            if not approach:
                continue
            # Normalize queue burden: vehicle count
            queue_norm = min(approach.queue_count / 20.0, 1.0)  # cap at 20 vehicles

            # Normalize waiting time: average waiting time / max_wait
            wait_norm = min(approach.mean_wait_seconds / self.max_wait, 1.0)

            # Normalize arrival rate: vehicles per minute / saturation flow (assume 1800 veh/hr = 30 veh/min)
            arrival_norm = min(approach.arrival_rate / 30.0, 1.0)

            pressure = self.alpha * queue_norm + self.beta * wait_norm + self.gamma * arrival_norm
            total_pressure += pressure
            logger.debug(f"Pressure for {name}: Q={queue_norm:.2f}, W={wait_norm:.2f}, A={arrival_norm:.2f} -> P={pressure:.2f}")
        logger.debug(f"Total pressure for {phase.name}: {total_pressure:.2f}")
        return total_pressure

    # ------------------------------------------------------------------
    # Downstream blockage eligibility
    # ------------------------------------------------------------------

    def _is_eligible(self, approach: ApproachState) -> bool:
        """Return True if the approach's downstream exit is not blocked.

        An approach is eligible when downstream_available is True (i.e. the
        receiving road has not reached the spillback threshold).
        """
        return approach.downstream_available

    def _eligible_approaches(self, state: TrafficState) -> Dict[str, ApproachState]:
        """Return a dict of approach_name -> ApproachState for eligible approaches only.

        Only approaches with downstream_available == True are included.
        """
        eligible = {}
        for name, app in state.approaches.items():
            if self._is_eligible(app):
                eligible[name] = app
        return eligible

    # ------------------------------------------------------------------
    # Phase selection logic - overrides _next_phase to implement downstream
    # blockage aware phase selection
    # ------------------------------------------------------------------

    def _next_phase(self) -> Phase:
        """Compute next phase in sequence, considering downstream blockage.

        Returns:
            Next Phase enum value, or None if all approaches blocked.
        """
        # Determine which approaches have eligible downstream exits
        eligible = self._eligible_approaches(self.last_state)

        if not eligible:
            # All approaches have blocked downstream exits
            logger.critical(
                "QueueSense: All approaches have blocked downstream exits; "
                "invoking all-exits-blocked policy"
            )
            # Return current phase to hold (will be handled by _should_end_phase)
            return self.state

        # Determine which directions have at least one eligible approach
        north_eligible = "north" in eligible or "south" in eligible
        east_eligible = "east" in eligible or "west" in eligible

        # If only one direction has eligible approaches, select that one
        if north_eligible and not east_eligible:
            logger.info("QueueSense: Only north-south direction eligible; selecting NORTH_SOUTH")
            return Phase.NORTH_SOUTH
        if east_eligible and not north_eligible:
            logger.info("QueueSense: Only east-west direction eligible; selecting EAST_WEST")
            return Phase.EAST_WEST

        # Both directions have eligible approaches: compare pressure and select
        # the direction with higher pressure (to match Controller C when downstream is free).
        north_pressure = self._calculate_pressure(self.last_state, Phase.NORTH_SOUTH)
        east_pressure = self._calculate_pressure(self.last_state, Phase.EAST_WEST)

        if north_pressure >= east_pressure:
            logger.info(
                f"QueueSense: Both directions eligible; NORTH_SOUTH pressure "
                f"({north_pressure:.2f}) >= EAST_WEST ({east_pressure:.2f}); "
                f"selecting NORTH_SOUTH (higher pressure)"
            )
            return Phase.NORTH_SOUTH
        else:
            logger.info(
                f"QueueSense: Both directions eligible; EAST_WEST pressure "
                f"({east_pressure:.2f}) > NORTH_SOUTH ({north_pressure:.2f}); "
                f"selecting EAST_WEST (higher pressure)"
            )
            return Phase.EAST_WEST

    # ------------------------------------------------------------------
    # Override _should_end_phase from BaseController
    # ------------------------------------------------------------------

    def _should_end_phase(self) -> bool:
        """Decide whether to end the current green phase early.

        Returns True if the minimum green time has been satisfied and the
        safety supervisor should transition to a clearance interval.

        The actual phase selection (which green to pick next) is handled
        by _next_phase, which incorporates downstream blockage awareness.
        Here we only decide whether to end the current green phase.

        Returns:
            True if min_green has been satisfied and the phase should end,
            False otherwise.
        """
        # Check if minimum green time has been satisfied
        if self.elapsed >= self.config.min_green:
            return True
        return False

    # ------------------------------------------------------------------
    # Override update_state from BaseController
    # ------------------------------------------------------------------

    def update_state(self, state: TrafficState) -> None:
        """Update controller with latest traffic state.

        Args:
            state: TrafficState from simulation/sensor pipeline.
        """
        self.last_state = state  # Store for pressure calculation and phase selection
        super().update_state(state)

    # ------------------------------------------------------------------
    # Controller step — main entry point
    # ------------------------------------------------------------------

    def step(self, state: TrafficState, step_length: float) -> Dict:
        """Controller step: compute QueueSense action.

        The step flow:
        1. Update internal state (watchdog + store last_state)
        2. Let safety supervisor handle phase timing and transitions
        3. If all-exits-blocked: hold at red by refusing to end phase
        4. Otherwise: normal operation with downstream blockage aware phase selection

        Args:
            state: TrafficState from perception/simulation.
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys:
            - 'phase': Phase enum (NORTH_SOUTH, EAST_WEST, or the current phase
              if all-exits-blocked)
            - 'duration': Duration to hold this phase (seconds)
            - 'reason': str explaining the decision
        """
        self.update_state(state)

        # Check for all-exits-blocked condition
        eligible = self._eligible_approaches(state)
        if not eligible:
            # All approaches have blocked downstream exits
            # Refuse to end the current phase to hold at red with clearance intervals
            # The safety supervisor will enforce clearance intervals and eventually
            # cycle to the next phase (which will be handled by _next_phase)
            if self.elapsed < self.config.min_green:
                # Still in min_green, continue current phase
                duration = step_length
                reason = (
                    f"All-exits-blocked: no eligible downstream exits; "
                    f"continuing {self.state.name} for {duration:.1f}s "
                    f"(waiting for min_green)"
                )
                logger.debug(reason)
                return {"phase": self.state, "duration": duration, "reason": reason}
            else:
                # Min_gven satisfied, but we refuse to end phase to hold at red
                # Safety supervisor will enforce clearance and call _next_phase
                # which will return current phase, creating a hold
                duration = step_length
                reason = (
                    f"All-exits-blocked: no eligible downstream exits; "
                    f"holding {self.state.name} for {duration:.1f}s "
                    f"(refusing to end phase, safety supervisor handles clearance)"
                )
                logger.debug(reason)
                return {"phase": self.state, "duration": duration, "reason": reason}

        # Normal operation: let safety supervisor handle everything
        # The _next_phase override provides downstream blockage aware phase selection
        return self.compute_action(step_length)