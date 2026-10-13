"""
BaseController: Safety Supervisor State Machine
Implements the safety supervisor with min/max green times, clearance intervals,
and fixed-time fallback on sensor fault.

This is the base class for all controllers (FixedTime, Actuated, QueuePressure, QueueSense).
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional
import logging

from queuesense.state import TrafficState


logger = logging.getLogger(__name__)


class Phase(Enum):
    """Signal phase identifiers for a 4-way intersection."""
    NORTH_SOUTH = auto()
    EAST_WEST = auto()
    ALL_RED = auto()
    YELLOW_CLEARANCE = auto()


@dataclass
class ControllerConfig:
    """Configuration for the safety supervisor and controller behavior."""
    min_green: float = 10.0
    max_green: float = 60.0
    yellow_duration: float = 5.0
    all_red_duration: float = 2.0
    fixed_cycle: Optional[list] = None


class BaseController:
    """
    Base controller with safety supervisor state machine.

    Safety Rules:
    - Minimum green time: 10s
    - Maximum green time: 60s
    - Clearance: Yellow (5s) -> All-Red (2s) enforced between phases
    - Heartbeat/watchdog: If TrafficState.all_valid is False for 3+ consecutive steps,
      fallback to fixed-time plan.
    """

    def __init__(self, config: ControllerConfig):
        self.config = config
        self.state: Optional[Phase] = None
        self.elapsed: float = 0.0
        self.consecutive_invalid: int = 0
        self.max_invalid_before_fallback = 3
        self.fixed_plan_index = 0
        # The green phase that was interrupted by a clearance interval.
        # Clearances must resume the *alternating* phase, otherwise every
        # clearance returns to fixed_cycle[0] and the second movement in the
        # cycle is never served.
        self._clearance_origin: Optional[Phase] = None

        # Define a simple fixed-time plan for fallback: [NS, EW, NS, EW]
        if self.config.fixed_cycle is None:
            self.config.fixed_cycle = [Phase.NORTH_SOUTH, Phase.EAST_WEST]

        # Start with the first phase in the fixed cycle
        self.state = self.config.fixed_cycle[0]
        self.elapsed = 0.0

        logger.info(
            f"BaseController initialized with min_green={config.min_green}s, "
            f"max_green={config.max_green}s, yellow={config.yellow_duration}s, "
            f"all_red={config.all_red_duration}s, fixed_cycle={config.fixed_cycle}"
        )

    def update_state(self, state: TrafficState) -> None:
        """Update controller with latest traffic state.

        Args:
            state: TrafficState from perception/simulation.
        """
        self._watchdog(state)

    def _watchdog(self, state: TrafficState) -> None:
        """Heartbeat/watchdog: detect sensor faults and trigger fallback.

        If all_valid is False for max_invalid_before_fallback consecutive steps,
        switch to fixed-time fallback.
        """
        if not state.all_valid:
            self.consecutive_invalid += 1
            logger.warning(
                f"Watchdog: invalid state detected (consecutive={self.consecutive_invalid}/{self.max_invalid_before_fallback})"
            )
        else:
            self.consecutive_invalid = 0

        if self.consecutive_invalid >= self.max_invalid_before_fallback:
            logger.critical(
                "Watchdog triggered: falling back to fixed-time controller due to repeated invalid state"
            )
            # Reset to fixed plan start
            self.state = self.config.fixed_cycle[0]
            self.elapsed = 0.0
            self.consecutive_invalid = 0

    def _elapsed_in_phase(self, step_length: float) -> float:
        """Return elapsed time in current phase."""
        return self.elapsed * step_length

    def _can_end_phase(self, step_length: float) -> bool:
        """Determine if current phase can be terminated safely.

        Returns:
            True if phase can end, False otherwise.
        """
        elapsed = self._elapsed_in_phase(step_length)
        if self.state == Phase.ALL_RED:
            # All-red is a fixed-duration clearance phase
            return elapsed >= self.config.all_red_duration
        elif self.state == Phase.YELLOW_CLEARANCE:
            # Yellow is a fixed-duration clearance phase
            return elapsed >= self.config.yellow_duration
        else:
            # For green phases, enforce min/max green times
            return (
                elapsed >= self.config.min_green
                and (elapsed >= self.config.max_green or self._should_end_phase())
            )

    def _clearance_expired(self, step_length: float) -> bool:
        """Return True when the current clearance phase has run its full duration.

        Clearance phases (YELLOW_CLEARANCE, ALL_RED) are fixed-duration and
        must not be interrupted.  The previous implementation checked the
        elapsed time only inside ``_can_end_phase`` and then re-entered
        ``compute_action`` without advancing ``self.state``, which left the
        controller permanently stuck in the clearance phase and never toggled
        the signal to the next green.
        """
        elapsed = self._elapsed_in_phase(step_length)
        if self.state == Phase.YELLOW_CLEARANCE:
            return elapsed >= self.config.yellow_duration
        if self.state == Phase.ALL_RED:
            return elapsed >= self.config.all_red_duration
        return False

    def _clearance_duration(self) -> float:
        """Return the fixed duration of the current clearance phase."""
        if self.state == Phase.YELLOW_CLEARANCE:
            return self.config.yellow_duration
        if self.state == Phase.ALL_RED:
            return self.config.all_red_duration
        return 0.0

    def _clearance_phase_name(self) -> str:
        """Human-readable name of the clearance phase just completed."""
        if self.state == Phase.YELLOW_CLEARANCE:
            return "Yellow"
        if self.state == Phase.ALL_RED:
            return "All-red"
        return "Clearance"

    def _should_end_phase(self) -> bool:
        """Override in subclass: decide whether to end the current green phase early.

        Returns:
            True if phase should end early, False to continue.
        """
        return False

    def _next_phase(self) -> Phase:
        """Compute next phase in sequence.

        Returns:
            Next Phase enum value.
        """
        if self.state == Phase.NORTH_SOUTH:
            return Phase.EAST_WEST
        elif self.state == Phase.EAST_WEST:
            return Phase.NORTH_SOUTH
        else:
            # After a clearance interval, resume the alternating phase rather
            # than always returning to fixed_cycle[0].  Clearances are entered
            # from a specific green phase (recorded in _clearance_origin).
            origin = self._clearance_origin
            if origin == Phase.NORTH_SOUTH:
                return Phase.EAST_WEST
            if origin == Phase.EAST_WEST:
                return Phase.NORTH_SOUTH
            # Fallback: first phase in the fixed cycle.
            return self.config.fixed_cycle[0]

    def _advance_fixed_plan(self) -> Optional[Phase]:
        """Advance the fixed-time plan cycle.

        Returns:
            Next phase if available, None if cycle complete.
        """
        idx = self.fixed_plan_index
        if idx + 1 < len(self.config.fixed_cycle):
            self.fixed_plan_index += 1
            return self.config.fixed_cycle[idx + 1]
        else:
            self.fixed_plan_index = 0
            return self.config.fixed_cycle[0]

    def compute_action(self, step_length: float) -> Dict:
        """Compute the next signal action based on safety supervisor state machine.

        Args:
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys:
                'phase': Phase enum
                'duration': Duration to hold this phase (seconds)
                'reason': str explaining decision
        """
        # If in clearance, enforce fixed duration and do not allow subclass override.
        # When the clearance has expired, advance to the next phase instead of
        # looping forever in the clearance state.
        if self.state in (Phase.YELLOW_CLEARANCE, Phase.ALL_RED):
            if not self._clearance_expired(step_length):
                duration = step_length
                reason = (
                    f"Holding {self.state.name} clearance "
                    f"({self._elapsed_in_phase(step_length):.1f}s / "
                    f"{self._clearance_duration():.1f}s)"
                )
                self.elapsed += 1
                logger.debug(f"Safety: {reason}")
                return {"phase": self.state, "duration": duration, "reason": reason}
            # Clearance complete: transition to the next phase.
            next_phase = self._next_phase()
            self.state = next_phase
            self.elapsed = 0.0
            reason = (
                f"{self._clearance_phase_name()} clearance complete, "
                f"transitioning to {next_phase.name}"
            )
            logger.info(f"Safety: {reason}")
            return self.compute_action(step_length)

        # Green phase: safety supervisor decides when to end
        if self._can_end_phase(step_length):
            # End current green phase and transition to clearance.
            # Remember which green phase we are leaving so the clearance can
            # resume the alternating movement.
            self._clearance_origin = self.state
            self.state = Phase.YELLOW_CLEARANCE
            self.elapsed = 0.0
            elapsed_sec = self._elapsed_in_phase(step_length)
            reason = (
                f"Ending green phase after {elapsed_sec:.1f}s "
                f"(min={self.config.min_green}s, max={self.config.max_green}s)"
            )
            logger.info(f"Safety: {reason}")
            return self.compute_action(step_length)

        # Continue current green phase
        duration = step_length
        reason = (
            f"Continuing {self.state.name} for {self._elapsed_in_phase(step_length):.1f}s "
            f"/ {self.config.max_green}s"
        )
        self.elapsed += 1
        logger.debug(f"Safety: {reason}")
        return {"phase": self.state, "duration": duration, "reason": reason}

    def step(self, state: TrafficState, step_length: float) -> Dict:
        """Main controller step: update state and compute action.

        Args:
            state: TrafficState from perception/simulation.
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys 'phase', 'duration', 'reason'.
        """
        self.update_state(state)
        return self.compute_action(step_length)
