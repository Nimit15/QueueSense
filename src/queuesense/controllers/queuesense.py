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
from typing import Dict, Optional
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
    7. spillback_gate_enabled: When True, downstream blockage suppresses green
       phase selection. When False, all approaches remain eligible (D1: gate OFF).

    Configuration parameters (from CLAUDE.md / configs/experiment.yaml):
      - alpha, beta, gamma: weights for queue, wait, arrival (sum to 1.0)
      - spillback_threshold: downstream road occupancy threshold (default 0.30,
        expressed as fraction; 0.30 = 30% SUMO occupancy)
      - max_wait: starvation cap for normalising waiting time (default 90s)
      - spillback_gate_enabled: True (D2: gate ON suppresses spillback;
        False = D1: gate OFF, all approaches remain eligible)
    """

    def __init__(
        self,
        alpha: float = 0.4,
        beta: float = 0.4,
        gamma: float = 0.2,
        spillback_threshold: float = 0.30,
        max_wait: float = 90.0,
        spillback_gate_enabled: bool = True,
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
        self.spillback_gate_enabled = spillback_gate_enabled
        self.last_state = None  # To store the last TrafficState for pressure calculation
        logger.info(
            f"QueueSenseController initialized: alpha={alpha}, beta={beta}, "
            f"gamma={gamma}, spillback_threshold={spillback_threshold}, "
            f"spillback_gate_enabled={spillback_gate_enabled}, max_wait={max_wait}s"
        )

    def update_state(self, state: TrafficState) -> None:
        """Update controller with latest traffic state and store it for pressure calculation.

        Args:
            state: TrafficState from perception/simulation.
        """
        self.last_state = state
        super().update_state(state)

    # ------------------------------------------------------------------
    # Queue-pressure score calculation
    # ------------------------------------------------------------------

    def _approach_pressure(self, state: TrafficState, approach_name: str) -> float:
        """Calculate pressure for a single approach.

        Args:
            state: TrafficState
            approach_name: Approach name ('north', 'south', 'east', 'west')

        Returns:
            Pressure score for the approach (higher = more).
        """
        approach = state.get_approach(approach_name)
        if not approach:
            return 0.0
        # Normalize queue burden: vehicle count
        queue_norm = min(approach.queue_count / 20.0, 1.0)

        # Normalize waiting time: average waiting time / max_wait
        wait_norm = min(approach.mean_wait_seconds / self.max_wait, 1.0)

        # Normalize arrival rate: vehicles per minute / saturation flow (assume 1800 veh/hr = 30 veh/min)
        arrival_norm = min(approach.arrival_rate / 30.0, 1.0)

        return self.alpha * queue_norm + self.beta * wait_norm + self.gamma * arrival_norm

    def _calculate_pressure(self, state: TrafficState, phase: Phase) -> float:
        """Calculate queue pressure score for a given phase.

        Args:
            state: TrafficState
            phase: Candidate phase to evaluate (NORTH_SOUTH or EAST_WEST)

        Returns:
            Pressure score (higher = more). Sum of the two opposing approaches.
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

    def _eligible_approaches(self, state: TrafficState) -> Dict[str, ApproachState]:
        """Return approaches with eligible downstream exits (downstream_available=True).

        When spillback_gate_enabled=False (D1), all approaches remain eligible
        regardless of downstream_available, since the gate is OFF and
        downstream blockage does not suppress phase selection.

        When spillback_gate_enabled=True (D2), only approaches with
        downstream_available=True are eligible.

        Args:
            state: TrafficState to evaluate.

        Returns:
            Dictionary of approach names to ApproachState for eligible approaches.
        """
        eligible = {}
        for name, approach in state.approaches.items():
            if self.spillback_gate_enabled:
                # D2: gate ON — suppress approaches with blocked downstream
                if approach.downstream_available:
                    eligible[name] = approach
            else:
                # D1: gate OFF — all approaches remain eligible
                eligible[name] = approach
        return eligible

    def _select_phase_from_pressure(self, state: TrafficState) -> Optional[Phase]:
        """Select the phase with the higher queue-pressure score among eligible approaches.

        Returns None if no approaches have eligible downstream exits.

        Args:
            state: TrafficState to evaluate.

        Returns:
            The Phase with the higher pressure among eligible approaches (ties go to NORTH_SOUTH),
            or None if no approaches are eligible.
        """
        if state is None or not state.approaches:
            return None

        # Get eligible approaches
        eligible = self._eligible_approaches(state)

        if not eligible:
            # All approaches have blocked downstream exits
            return None

        # Determine which directions have at least one eligible approach
        north_eligible = "north" in eligible or "south" in eligible
        east_eligible = "east" in eligible or "west" in eligible

        if north_eligible and not east_eligible:
            return Phase.NORTH_SOUTH
        if east_eligible and not north_eligible:
            return Phase.EAST_WEST

        # Both directions have eligible approaches: compare pressure of eligible approaches only
        # Calculate pressure for each direction using only eligible approaches
        north_pressure = 0.0
        if "north" in eligible:
            north_pressure += self._approach_pressure(state, "north")
        if "south" in eligible:
            north_pressure += self._approach_pressure(state, "south")

        east_pressure = 0.0
        if "east" in eligible:
            east_pressure += self._approach_pressure(state, "east")
        if "west" in eligible:
            east_pressure += self._approach_pressure(state, "west")

        if north_pressure >= east_pressure:
            logger.info(
                f"QueuePressure: NORTH_SOUTH pressure ({north_pressure:.2f}) >= "
                f"EAST_WEST ({east_pressure:.2f}); selecting NORTH_SOUTH"
            )
            return Phase.NORTH_SOUTH
        else:
            logger.info(
                f"QueuePressure: EAST_WEST pressure ({east_pressure:.2f}) > "
                f"NORTH_SOUTH ({north_pressure:.2f}); selecting EAST_WEST"
            )
            return Phase.EAST_WEST

    def _ungated_phase(self) -> Optional[Phase]:
        """Phase the pressure policy would select with the gate OFF.

        Computes queue pressure over ALL approaches regardless of
        downstream_available, i.e. the decision the controller would make
        if spillback gating were disabled.  Used to attribute gate
        interventions: the gate is exercised whenever the gated decision
        differs from this ungated candidate.

        Returns:
            Phase, or None if no state is available.
        """
        if self.last_state is None or not self.last_state.approaches:
            return None

        north_pressure = self._approach_pressure(self.last_state, "north") + \
            self._approach_pressure(self.last_state, "south")
        east_pressure = self._approach_pressure(self.last_state, "east") + \
            self._approach_pressure(self.last_state, "west")

        if north_pressure >= east_pressure:
            return Phase.NORTH_SOUTH
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
    # Override _next_phase from BaseController to incorporate downstream blockage awareness
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

        # Both directions have eligible approaches: compare pressure of eligible approaches only
        # Calculate pressure for each direction using only eligible approaches
        north_pressure = 0.0
        if "north" in eligible:
            north_pressure += self._approach_pressure(self.last_state, "north")
        if "south" in eligible:
            north_pressure += self._approach_pressure(self.last_state, "south")

        east_pressure = 0.0
        if "east" in eligible:
            east_pressure += self._approach_pressure(self.last_state, "east")
        if "west" in eligible:
            east_pressure += self._approach_pressure(self.last_state, "west")

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
    # Note: update_state is already overridden above to store last_state
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Controller step — main entry point
    # ------------------------------------------------------------------

    def compute_action(self, step_length: float) -> Dict:
        """Compute the next signal action based on safety supervisor state machine and downstream blockage awareness.

        Args:
            step_length: Simulation step length in seconds.

        Returns:
            Dict with keys:
                'phase': Phase enum
                'duration': Duration to hold this phase (seconds)
                'reason': str explaining decision
        """
        # If in clearance, enforce fixed duration and do not allow subclass override.
        if self.state in (Phase.YELLOW_CLEARANCE, Phase.ALL_RED):
            return super().compute_action(step_length)

        # Green phase: handle downstream blockage and pressure-based selection
        if self.state in (Phase.NORTH_SOUTH, Phase.EAST_WEST):
            # Determine eligibility using spillback gate setting
            if self.spillback_gate_enabled:
                # D2: gate ON — eligibility depends on downstream_available
                if self.state == Phase.NORTH_SOUTH:
                    current_eligible = ("north" in self.last_state.approaches and self.last_state.approaches["north"].downstream_available) or \
                                       ("south" in self.last_state.approaches and self.last_state.approaches["south"].downstream_available)
                    other_eligible = ("east" in self.last_state.approaches and self.last_state.approaches["east"].downstream_available) or \
                                     ("west" in self.last_state.approaches and self.last_state.approaches["west"].downstream_available)
                else:  # EAST_WEST
                    current_eligible = ("east" in self.last_state.approaches and self.last_state.approaches["east"].downstream_available) or \
                                       ("west" in self.last_state.approaches and self.last_state.approaches["west"].downstream_available)
                    other_eligible = ("north" in self.last_state.approaches and self.last_state.approaches["north"].downstream_available) or \
                                     ("south" in self.last_state.approaches and self.last_state.approaches["south"].downstream_available)
            else:
                # D1: gate OFF — all approaches remain eligible regardless of downstream
                current_eligible = True
                other_eligible = True

            other_phase = Phase.NORTH_SOUTH if self.state == Phase.EAST_WEST else Phase.EAST_WEST

            # Store the current state before any changes
            current_state_before = self.state

            # If current direction is blocked but other direction is clear, switch immediately
            if not current_eligible and other_eligible:
                self.state = other_phase
                self.elapsed = 0.0
                action = super().compute_action(step_length)
                # Tag the decision so the runner can attribute it to the gate.
                # The base controller's reason does not mention downstream blockage,
                # so without this marker a reason-string probe misses the event.
                action["reason"] = f"{action['reason']} | GATE_INTERVENTION: downstream blockage"
                # Explicit event type for the 4-metric instrumentation:
                # the gate caused the applied phase to differ from the ungated
                # decision (the ungated policy would have kept the current green).
                action["gate_event"] = "phase_change"
                # Ungated decision is what the controller would have selected if gate was OFF
                action["ungated_phase"] = current_state_before
                return action

            # If all exits are blocked, hold current phase and indicate min_green commitment
            if not current_eligible and not other_eligible:
                # Hold the current phase (don't change state)
                # Update elapsed same as BaseController: increment by 1 step
                self.elapsed += 1
                # Return duration >= min_green to indicate commitment due to blocked exits
                duration = self.config.min_green
                reason = (
                    f"All exits blocked: holding {self.state.name} for {duration:.1f}s "
                    f"(min_green={self.config.min_green}s) | GATE_INTERVENTION: downstream blockage"
                )
                return {
                    "phase": self.state,
                    "duration": duration,
                    "reason": reason,
                    # Gate-caused hold: the ungated policy would have transitioned
                    # (or at least evaluated a switch), but the gate prevented it.
                    "gate_event": "hold",
                    "ungated_phase": self.state,
                }

            # Normal situation: at least one direction eligible (gate OFF keeps all eligible)
            # Fall back to BaseController logic (which includes pressure-based switching after min_green)
            action = super().compute_action(step_length)

            if self.spillback_gate_enabled:
                # Determine what the UNGATED policy would have selected on the
                # identical state (gate OFF = all approaches eligible).  The
                # gate intervention is real whenever the gated decision differs
                # from this ungated candidate -- including the case where the
                # gate suppresses one approach inside a direction that still
                # has an eligible approach (e.g. east blocked, west clear).
                ungated_phase = self._ungated_phase()
                gated_phase = action["phase"]
                # The gate is exercised whenever at least one approach is
                # suppressed (downstream_available=False) in this state.
                any_suppressed = any(
                    not app.downstream_available
                    for app in self.last_state.approaches.values()
                )
                # The ungated-vs-gated comparison is only meaningful between
                # green phases.  When the safety supervisor transitions to a
                # clearance phase (YELLOW_CLEARANCE / ALL_RED), that decision
                # is driven by min/max green enforcement, not the gate, and
                # must not be attributed to downstream blockage.
                both_green = gated_phase in (Phase.NORTH_SOUTH, Phase.EAST_WEST) \
                    and ungated_phase in (Phase.NORTH_SOUTH, Phase.EAST_WEST)
                if any_suppressed and both_green and ungated_phase != gated_phase:
                    # The gate changed the applied phase relative to the
                    # ungated pressure decision.
                    action["reason"] = (
                        f"{action.get('reason', '')} | "
                        f"GATE_INTERVENTION: downstream blockage "
                        f"(ungated={ungated_phase.name}, gated={gated_phase.name})"
                    )
                    action["gate_event"] = "phase_change"
                    action["ungated_phase"] = ungated_phase
                elif any_suppressed and both_green:
                    # Blockage exists but the controller held the current
                    # green anyway (pressure tie/lead): gate-caused hold.
                    action["reason"] = (
                        f"{action.get('reason', '')} | "
                        f"GATE_INTERVENTION: downstream blockage"
                    )
                    action["gate_event"] = "hold"
                    action["ungated_phase"] = ungated_phase
                else:
                    action["gate_event"] = "none"
            else:
                # For D1 (gate OFF), no gate activity at all
                action["gate_event"] = "none"
            return action

        # For non-green phases (shouldn't happen) or green phases that don't meet the above conditions, use the base logic.
        return super().compute_action(step_length)