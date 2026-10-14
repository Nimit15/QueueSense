"""
QueuePressureController (Controller C)
Adaptive controller that selects phases based on queue pressure score.

Queue pressure score: P_i = alpha * Q_i + beta * W_i + gamma * A_i
- Q_i: normalized queue burden (vehicle count)
- W_i: normalized waiting time (average waiting time / max_wait)
- A_i: normalized arrival rate (vehicles per minute / saturation flow)
- alpha + beta + gamma = 1

This controller does NOT use downstream blockage awareness (spillback prevention).
It is intentionally a simple adaptive baseline to compare against fixed-time and actuated.
"""

import logging
from typing import Dict

from queuesense.state import TrafficState
from queuesense.controllers.base import BaseController, ControllerConfig, Phase


logger = logging.getLogger(__name__)


class QueuePressureController(BaseController):
    """Queue-pressure-only adaptive controller."""

    def __init__(self, alpha: float = 0.4, beta: float = 0.4, gamma: float = 0.2, max_wait: float = 90.0):
        # Safety supervisor timing
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
        self.max_wait = max_wait  # seconds (starvation cap)
        logger.info(f"QueuePressureController initialized with alpha={alpha}, beta={beta}, gamma={gamma}, max_wait={max_wait}s")

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

    def _should_end_phase(self) -> bool:
        """Decide whether to end the current green phase early based on pressure comparison.

        Returns:
            True if phase should end early, False to continue.
        """
        # Only consider ending if we have been in green for at least min_green
        if self._elapsed_in_phase(1.0) < self.config.min_green:
            return False

        # Calculate pressure for current phase and the other phase
        current_pressure = self._calculate_pressure(self.last_state, self.state)
        other_phase = Phase.EAST_WEST if self.state == Phase.NORTH_SOUTH else Phase.NORTH_SOUTH
        other_pressure = self._calculate_pressure(self.last_state, other_phase)

        # If the other phase has significantly higher pressure, consider ending early
        if other_pressure > current_pressure * 1.2:
            logger.info(f"QueuePressure: Ending {self.state.name} early (P_current={current_pressure:.2f}, P_other={other_pressure:.2f})")
            return True

        return False

    def update_state(self, state: TrafficState) -> None:
        """Update controller with latest traffic state.

        Args:
            state: TrafficState from perception/simulation.
        """
        self.last_state = state  # Store for pressure calculation
        super().update_state(state)

    def step(self, state: TrafficState, step_length: float) -> Dict:
        """Controller step: compute queue-pressure action.

        Args:
            state: TrafficState from perception/simulation.
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys 'phase', 'duration', 'reason'.
        """
        self.update_state(state)
        action = self.compute_action(step_length)
        logger.info(
            f"Controller C (QueuePressure): {action['phase'].name} for {action['duration']:.1f}s | Reason: {action['reason']}"
        )
        return action
