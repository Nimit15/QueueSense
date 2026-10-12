"""
FixedTimeController (Controller A)
Preset 90s cycle: 35s green North-South, 5s clearance, 35s green East-West, 5s clearance.

This is the baseline fixed-time controller for the QueueSense benchmark.
"""

import logging
from typing import Dict

from queuesense.state import TrafficState
from queuesense.controllers.base import BaseController, ControllerConfig, Phase


logger = logging.getLogger(__name__)


class FixedTimeController(BaseController):
    """Fixed-time signal controller with safety supervisor."""

    def __init__(self):
        # Fixed-time cycle: [NS green, EW green]
        config = ControllerConfig(
            min_green=35.0,
            max_green=35.0,  # Fixed duration
            yellow_duration=5.0,
            all_red_duration=2.0,
            fixed_cycle=[Phase.NORTH_SOUTH, Phase.EAST_WEST],
        )
        super().__init__(config)
        logger.info("FixedTimeController initialized with 90s cycle (35s+5s+35s+5s)")

    def _should_end_phase(self) -> bool:
        """Fixed-time never ends early; safety supervisor enforces max_green=min_green."""
        return False

    def step(self, state: TrafficState, step_length: float) -> Dict:
        """Controller step: compute fixed-time action.

        Args:
            state: TrafficState from perception/simulation.
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys 'phase', 'duration', 'reason'.
        """
        self.update_state(state)
        action = self.compute_action(step_length)
        logger.info(
            f"Controller A: {action['phase'].name} for {action['duration']:.1f}s | Reason: {action['reason']}"
        )
        return action
