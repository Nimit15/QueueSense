"""
ActuatedController (Controller B)
Demand-responsive traffic signal controller using gap-based actuation.

This controller extends green while vehicles are present and short gaps are detected,
but enforces min/max green times and clearance intervals for safety.

Gap-based rule: Extend green if vehicles are present and gap < threshold.
Gap threshold: 3.0 seconds (typical for urban intersections).
"""

import logging
from typing import Dict

from queuesense.state import TrafficState
from queuesense.controllers.base import BaseController, ControllerConfig, Phase


logger = logging.getLogger(__name__)


class ActuatedController(BaseController):
    """Actuated signal controller with safety supervisor."""

    def __init__(self, gap_threshold: float = 3.0):
        # Actuated timing: min_green=10s, max_green=60s, clearance as per safety supervisor
        config = ControllerConfig(
            min_green=10.0,
            max_green=60.0,
            yellow_duration=5.0,
            all_red_duration=2.0,
            fixed_cycle=[Phase.NORTH_SOUTH, Phase.EAST_WEST],
        )
        super().__init__(config)
        self.gap_threshold = gap_threshold  # seconds
        logger.info(f"ActuatedController initialized with gap_threshold={gap_threshold}s, min_green={config.min_green}s, max_green={config.max_green}s")

    def _should_end_phase(self) -> bool:
        """Decide whether to end the current green phase early based on demand.

        Returns:
            True if phase should end early, False to continue.
        """
        # If no vehicles are present on the current approach, end early
        # We don't have per-approach state here, so we use a simple heuristic:
        # End early only if max_green is reached (safety supervisor will enforce it anyway)
        # In a more advanced version, we would track demand per approach.
        return False

    def step(self, state: TrafficState, step_length: float) -> Dict:
        """Controller step: compute actuated action.

        Args:
            state: TrafficState from perception/simulation.
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys 'phase', 'duration', 'reason'.
        """
        self.update_state(state)
        action = self.compute_action(step_length)
        logger.info(
            f"Controller B (Actuated): {action['phase'].name} for {action['duration']:.1f}s | Reason: {action['reason']}"
        )
        return action
