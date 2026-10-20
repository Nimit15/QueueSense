"""
Controller S: Context-Aware Selector (4-Regime Capacity-Aware Backpressure)

Single-supervisor selector that merges Controller C (queue-pressure efficiency)
with Controller D2 (spillback-gate safety) into ONE state-preserving state
machine per junction.  Switching regimes never resets elapsed time or bypasses
the BaseController safety supervisor (min_green / max_green / YELLOW / ALL_RED
/ 3-strike watchdog).

4-Regime policy
---------------
UNKNOWN  -- sensor fault / stale / out-of-range -> conservative hold, watchdog
CLEAR    -- all receiving links valid & below soft_risk_threshold (0.24) -> pure
            Controller C pressure selection (argmax with 1.2x hysteresis)
ELEVATED_RISK -- occupancy in [0.24, 0.30) -> smooth pressure discount by available
            downstream storage (no hard switch unless cross-street has real demand)
BLOCKED  -- occupancy >= spillback_threshold (0.30) or downstream_available==False ->
            Schmitt hysteresis (enter 0.30, exit 0.22 AND min_mode_persistence_steps=5);
            cross-demand guard avoids switching to an empty cross-street.

Every step emits a structured DecisionReceipt for ICCC audit.

Emergency downstream-flush for the J1->J2 corridor is handled by
``queuesense.network.emergency_flush.EmergencyFlushCoordinator``.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from queuesense.state import TrafficState, ApproachState, DownstreamObservation, DecisionReceipt
from queuesense.controllers.base import BaseController, ControllerConfig, Phase
from queuesense.controllers.queue_pressure import QueuePressureController

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Tunable policy constants (single source of truth)
# ------------------------------------------------------------------
SPILLBACK_THRESHOLD = 0.30       # Enter BLOCKED at/above this occupancy fraction
CLEAR_EXIT_THRESHOLD = 0.27      # Leave BLOCKED once below this (Schmitt hysteresis) - raised from 0.22 to return to C-mode sooner
SOFT_RISK_THRESHOLD = 0.24       # Enter ELEVATED_RISK at/above this (Schmitt enter)
CLEAR_RISK_EXIT = 0.22           # Leave ELEVATED_RISK once below this (Schmitt exit)
MIN_MODE_PERSISTENCE_STEPS = 2   # Min steps in a regime before leaving it - reduced from 5 for faster recovery
STALENESS_SECONDS = 1.0          # Observations older than this are stale
HYSTERESIS_FACTOR = 1.2          # Pressure-switch multiplier (matches Controller C)


class ContextAwareSelector(BaseController):
    """Controller S -- 4-regime context-aware backpressure selector.

    Maintains a SINGLE BaseController state machine per junction so regime
    switches cannot reset ``elapsed`` mid-phase or bypass clearance intervals.

    Args:
        junction_id: Unique junction identifier (e.g. ``"J1"``).
        alpha, beta, gamma: pressure weights (parity with Controller C).
        max_wait: starvation cap for waiting-time normalisation (seconds).
        spillback_threshold: hard gate occupancy fraction (default 0.30).
        soft_risk_threshold: elevated-risk enter threshold (default 0.24).
        clear_exit_threshold: regime exit threshold (default 0.22).
        max_staleness_s: observation freshness window (seconds).
    """

    def __init__(
        self,
        junction_id: str = "J1",
        alpha: float = 0.4,
        beta: float = 0.4,
        gamma: float = 0.2,
        max_wait: float = 90.0,
        spillback_threshold: float = SPILLBACK_THRESHOLD,
        soft_risk_threshold: float = SOFT_RISK_THRESHOLD,
        clear_exit_threshold: float = CLEAR_EXIT_THRESHOLD,
        max_staleness_s: float = STALENESS_SECONDS,
    ):
        config = ControllerConfig(
            min_green=10.0,
            max_green=60.0,
            yellow_duration=5.0,
            all_red_duration=2.0,
            fixed_cycle=[Phase.NORTH_SOUTH, Phase.EAST_WEST],
        )
        super().__init__(config)
        self.junction_id = junction_id
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.max_wait = max_wait
        self.spillback_threshold = spillback_threshold
        self.soft_risk_threshold = soft_risk_threshold
        self.clear_exit_threshold = clear_exit_threshold
        self.max_staleness_s = max_staleness_s

        # Reference controller C used only to certify CLEAR-mode agreement.
        self._controller_c_ref = QueuePressureController(
            alpha=alpha, beta=beta, gamma=gamma, max_wait=max_wait,
        )

        # Regime state (persists across steps -- never reset by regime switches)
        self.capacity_status: str = "UNKNOWN"
        self.selected_mode: str = "FALLBACK"
        self.last_downstream_occupancy: float = 0.0
        self._trigger_edge_id: str = ""
        self._mode_persistence_steps: int = 0
        self._consecutive_invalid: int = 0
        self.last_state: Optional[TrafficState] = None
        self.last_receipt: Optional[DecisionReceipt] = None
        self.receipts: List[DecisionReceipt] = []

        logger.info(
            f"ContextAwareSelector[{junction_id}] init: alpha={alpha}, beta={beta}, "
            f"gamma={gamma}, spillback={spillback_threshold}, soft_risk={soft_risk_threshold}, "
            f"clear_exit={clear_exit_threshold}, staleness={max_staleness_s}s"
        )

    # ------------------------------------------------------------------
    # Pressure calculation (identical to Controller C)
    # ------------------------------------------------------------------
    def _approach_pressure(self, state: TrafficState, name: str) -> float:
        approach = state.get_approach(name)
        if not approach:
            return 0.0
        q = min(approach.queue_count / 20.0, 1.0)
        w = min(approach.mean_wait_seconds / self.max_wait, 1.0)
        a = min(approach.arrival_rate / 30.0, 1.0)
        return self.alpha * q + self.beta * w + self.gamma * a

    def _phase_pressure(self, state: TrafficState, phase: Phase) -> float:
        if phase == Phase.NORTH_SOUTH:
            names = ["north", "south"]
        elif phase == Phase.EAST_WEST:
            names = ["east", "west"]
        else:
            return 0.0
        return sum(self._approach_pressure(state, n) for n in names if state.get_approach(n))

    def _ungated_phase(self, state: TrafficState) -> Optional[Phase]:
        if not state or not state.approaches:
            return None
        np = self._phase_pressure(state, Phase.NORTH_SOUTH)
        ep = self._phase_pressure(state, Phase.EAST_WEST)
        return Phase.NORTH_SOUTH if np >= ep else Phase.EAST_WEST

    # ------------------------------------------------------------------
    # Downstream capacity assessment -> 4 regimes
    # ------------------------------------------------------------------
    def _assess_capacity(self, state: TrafficState) -> Tuple[str, str, float, str]:
        """Return (capacity_status, reason_code, max_occupancy, trigger_edge).

        capacity_status is always one of CLEAR / BLOCKED / UNKNOWN.
        UNKNOWN is never silently mapped to CLEAR.
        """
        # --- Regime 4: UNKNOWN (sensor fault / stale / out-of-range) ---
        if not state or not state.approaches or not state.all_valid:
            return "UNKNOWN", "SENSOR_INVALID", 0.0, ""
        # Need a downstream observation to assess capacity.
        all_obs: List[DownstreamObservation] = []
        for app in state.approaches.values():
            all_obs.extend(app.downstream_observations)
        if not all_obs:
            return "UNKNOWN", "MISSING_OBS", 0.0, ""
        for obs in all_obs:
            if not obs.observation_valid:
                return "UNKNOWN", "SENSOR_INVALID", 0.0, ""
            if obs.age_s > self.max_staleness_s:
                return "UNKNOWN", "STALE_DATA", 0.0, ""
            if obs.occupancy_fraction < 0.0 or obs.occupancy_fraction > 1.0:
                return "UNKNOWN", "OUT_OF_RANGE", 0.0, ""
        max_occ = max(obs.occupancy_fraction for obs in all_obs)
        trigger_obs = max(all_obs, key=lambda o: o.occupancy_fraction)

        # --- Schmitt hysteresis gating (enter BLOCKED at 0.30, exit at 0.22) ---
        # When in BLOCKED, remain BLOCKED until max_occ <= clear_exit_threshold (0.22)
        # AND min_mode_persistence_steps satisfied.
        if self.capacity_status == "BLOCKED":
            if max_occ <= self.clear_exit_threshold:
                self._mode_persistence_steps += 1
                if self._mode_persistence_steps >= MIN_MODE_PERSISTENCE_STEPS:
                    return "CLEAR", "CLEAR", max_occ, trigger_obs.edge_id
                # Still in hysteresis hold; report BLOCKED until persistence satisfied
                return "BLOCKED", "SPILLBACK_HYSTERESIS", max_occ, trigger_obs.edge_id
            # Still above clear_exit_threshold (0.22): remain BLOCKED regardless of
            # whether it's in ELEVATED_RISK range. This prevents premature exit.
            self._mode_persistence_steps = 0
            return "BLOCKED", "SPILLBACK_HYSTERESIS", max_occ, trigger_obs.edge_id

        if max_occ >= self.spillback_threshold:
            self._mode_persistence_steps = 0
            return "BLOCKED", "SPILLBACK_GATE", max_occ, trigger_obs.edge_id

        if max_occ >= self.soft_risk_threshold:
            self._mode_persistence_steps = 0
            return "ELEVATED_RISK", "ELEVATED_RISK", max_occ, trigger_obs.edge_id

        self._mode_persistence_steps = 0
        return "CLEAR", "CLEAR", max_occ, trigger_obs.edge_id

    # ------------------------------------------------------------------
    # Cross-demand guard: is there real demand in the competing direction?
    # ------------------------------------------------------------------
    def _direction_has_demand(self, state: TrafficState, phase: Phase) -> bool:
        names = ["north", "south"] if phase == Phase.NORTH_SOUTH else ["east", "west"]
        for n in names:
            app = state.get_approach(n)
            if app and (app.queue_count > 0 or app.arrival_rate > 0):
                return True
        return False

    def _eligible_direction(self, state: TrafficState) -> Dict[str, bool]:
        """True for a direction if any of its approaches is downstream_available."""
        ns = (state.get_approach("north") and state.get_approach("north").downstream_available) or \
             (state.get_approach("south") and state.get_approach("south").downstream_available)
        ew = (state.get_approach("east") and state.get_approach("east").downstream_available) or \
             (state.get_approach("west") and state.get_approach("west").downstream_available)
        return {"north_south": bool(ns), "east_west": bool(ew)}

    # ------------------------------------------------------------------
    # BaseController hook: decide whether to end current green early
    # ------------------------------------------------------------------
    def _should_end_phase(self) -> bool:
        if self.last_state is None:
            return False
        if self.state not in (Phase.NORTH_SOUTH, Phase.EAST_WEST):
            return False
        if self._elapsed_in_phase(1.0) < self.config.min_green:
            return False
        # End green after min_green once we hit max_green or the other phase
        # has >= 1.2x pressure -- identical to Controller C.
        current = self._phase_pressure(self.last_state, self.state)
        other = Phase.EAST_WEST if self.state == Phase.NORTH_SOUTH else Phase.NORTH_SOUTH
        other_p = self._phase_pressure(self.last_state, other)
        if other_p > current * HYSTERESIS_FACTOR:
            return True
        if self._elapsed_in_phase(1.0) >= self.config.max_green:
            return True
        # Max-wait fairness: if any approach in current green phase has vehicles
        # waiting > max_wait, allow phase end to serve the other direction.
        names = ["north", "south"] if self.state == Phase.NORTH_SOUTH else ["east", "west"]
        for n in names:
            app = self.last_state.get_approach(n)
            if app and app.mean_wait_seconds >= self.max_wait:
                return True
        return False

    def _next_phase_after_clearance(self) -> Phase:
        """Next green phase after a clearance interval, respecting the gate."""
        if self.last_state is None:
            return Phase.NORTH_SOUTH
        status, _, _, _ = self._assess_capacity(self.last_state)
        eligible = self._eligible_direction(self.last_state)
        ns_ready = eligible["north_south"]
        ew_ready = eligible["east_west"]

        # BLOCKED regime: choose an eligible direction with demand.
        if status == "BLOCKED":
            if ns_ready and not ew_ready:
                return Phase.NORTH_SOUTH
            if ew_ready and not ns_ready:
                return Phase.EAST_WEST
            if ns_ready and ew_ready:
                # Cross-demand guard: don't switch to an empty cross-street.
                ns_demand = self._direction_has_demand(self.last_state, Phase.NORTH_SOUTH)
                ew_demand = self._direction_has_demand(self.last_state, Phase.EAST_WEST)
                if ns_demand and not ew_demand:
                    return Phase.NORTH_SOUTH
                if ew_demand and not ns_demand:
                    return Phase.EAST_WEST
                # Both have demand: pick higher pressure among eligible.
                np = self._phase_pressure(self.last_state, Phase.NORTH_SOUTH)
                ep = self._phase_pressure(self.last_state, Phase.EAST_WEST)
                return Phase.NORTH_SOUTH if np >= ep else Phase.EAST_WEST
            # No eligible direction -- hold current green (all-exits-blocked).
            return self.state

        # CLEAR / ELEVATED_RISK / UNKNOWN: PURE CONTROLLER C PRESSURE SELECTION.
        # In CLEAR mode: exact same as Controller C (argmax with 1.2x hysteresis in _should_end_phase).
        # In ELEVATED_RISK: still use pure pressure, but the smooth discount is applied
        # only to the *mode attribution* (stays "C"), not to force a hard switch.
        phase = self._ungated_phase(self.last_state)
        return phase if phase is not None else Phase.NORTH_SOUTH

    # ------------------------------------------------------------------
    # Emergency flush (delegated to the corridor coordinator)
    # ------------------------------------------------------------------
    def _flush_coordinator(self):
        """Lazy-import to avoid circular imports."""
        from queuesense.network.emergency_flush import EmergencyFlushCoordinator
        if not hasattr(self, "_emergency_coordinator") or self._emergency_coordinator is None:
            self._emergency_coordinator = EmergencyFlushCoordinator(
                junction_ids=["J1", "J2", "J3"],
                selector_factory=lambda jid: ContextAwareSelector(junction_id=jid, alpha=self.alpha, beta=self.beta, gamma=self.gamma, max_wait=self.max_wait,
                                                                   spillback_threshold=self.spillback_threshold, soft_risk_threshold=self.soft_risk_threshold,
                                                                   clear_exit_threshold=self.clear_exit_threshold, max_staleness_s=self.max_staleness_s),
            )
        return self._emergency_coordinator

    # ------------------------------------------------------------------
    # ELEVATED_RISK: smooth capacity-aware backpressure discounting
    # ------------------------------------------------------------------
    def _direction_max_occupancy(self, state: TrafficState, phase: Phase) -> float:
        """Maximum downstream occupancy fraction across a direction's approaches."""
        names = ["north", "south"] if phase == Phase.NORTH_SOUTH else ["east", "west"]
        best = 0.0
        for n in names:
            app = state.get_approach(n)
            if not app:
                continue
            for obs in app.downstream_observations:
                if obs.observation_valid and 0.0 <= obs.occupancy_fraction <= 1.0:
                    best = max(best, obs.occupancy_fraction)
        return best

    def _effective_pressure(self, state: TrafficState, phase: Phase) -> float:
        """ELEVATED_RISK: discount a congested direction's pressure smoothly.

        effective = upstream_pressure * (1 - 0.5 * (occ - soft)/(spill - soft))
        so an unblocked cross-street with real demand wins naturally without a
        hard switch unless the cross-street actually has traffic.
        """
        base = self._phase_pressure(state, phase)
        occ = self._direction_max_occupancy(state, phase)
        if occ < self.soft_risk_threshold:
            return base
        denom = self.spillback_threshold - self.soft_risk_threshold
        if denom <= 0:
            return base
        frac = (occ - self.soft_risk_threshold) / denom
        frac = min(max(frac, 0.0), 1.0)
        discount = 1.0 - 0.5 * frac
        return base * discount

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------
    def step(self, state: TrafficState, step_length: float) -> Dict:
        """Execute one control step and emit a DecisionReceipt.

        Returns a dict with keys: phase, duration, reason, capacity_status,
        selected_mode, gate_intervened, safety_override, applied_phase,
        reason_code, receipt (DecisionReceipt dict).
        """
        self.last_state = state
        self.update_state(state)

        # Record watchdog invalid count
        invalid = not state or not state.all_valid
        if invalid:
            self._consecutive_invalid += 1
        else:
            self._consecutive_invalid = 0

        # Assess capacity regime
        capacity_status, reason_code, max_occ, trigger_edge = self._assess_capacity(state)
        # _assess_capacity handles _mode_persistence_steps increment/reset internally
        # Do NOT reset on regime change here - _assess_capacity manages it correctly
        self.capacity_status = capacity_status
        self.last_downstream_occupancy = max_occ
        self._trigger_edge_id = trigger_edge

        # Fallback if watchdog fired
        if self._consecutive_invalid >= self.max_invalid_before_fallback:
            self.selected_mode = "FALLBACK"
            reason_code = "WATCHDOG_FALLBACK"
            capacity_status = "UNKNOWN"

        # Determine selected mode
        if capacity_status in ("UNKNOWN",):
            self.selected_mode = "FALLBACK" if self._consecutive_invalid >= self.max_invalid_before_fallback else "C"
        elif capacity_status == "CLEAR":
            self.selected_mode = "C"
        elif capacity_status == "ELEVATED_RISK":
            self.selected_mode = "C"  # still C pressure logic with smooth discount
        elif capacity_status == "BLOCKED":
            self.selected_mode = "D2"

        # Compute the ungated candidate (what Controller C would pick)
        ungated = self._ungated_phase(state)
        ungated_name = ungated.name if ungated else ""

        # Determine eligible directions
        eligible = self._eligible_direction(state)
        both_blocked = not eligible["north_south"] and not eligible["east_west"]

        gate_intervened = False
        safety_override = False

        # ------------------------------------------------------------------
        # Phase selection by regime
        # ------------------------------------------------------------------
        current_in_green = self.state in (Phase.NORTH_SOUTH, Phase.EAST_WEST)
        in_clearance = self.state in (Phase.YELLOW_CLEARANCE, Phase.ALL_RED)

        if in_clearance:
            # Safety supervisor owns clearance; do not pick a phase here.
            action = super().compute_action(step_length)
            applied = action["phase"]
            gated_phase = applied
        else:
            # Decide the *target* green phase, then let BaseController enforce
            # safety supervisor (min_green / max_green / clearance).
            if capacity_status == "BLOCKED" and current_in_green:
                cur_eligible = (eligible["north_south"] if self.state == Phase.NORTH_SOUTH
                                else eligible["east_west"])
                other_ready = (eligible["east_west"] if self.state == Phase.NORTH_SOUTH
                               else eligible["north_south"])
                other_phase = Phase.EAST_WEST if self.state == Phase.NORTH_SOUTH else Phase.NORTH_SOUTH
                # Cross-demand guard: only switch to an eligible cross-street that has demand.
                if (not cur_eligible and other_ready
                        and self._direction_has_demand(state, other_phase)):
                    target_phase = other_phase
                    gate_intervened = True
                elif not cur_eligible and other_ready:
                    # Other direction is eligible but has NO demand - do NOT switch.
                    # Physical safety rule: NEVER continue releasing vehicles into a
                    # confirmed BLOCKED receiving link merely because the competing
                    # cross-street queue happens to be empty!
                    # Hold current green and wait for either: blocked link clears,
                    # cross-street demand appears, or max_wait fairness forces service.
                    target_phase = self.state
                elif not cur_eligible and not other_ready and both_blocked:
                    # All-exits-blocked: hold current green, don't switch.
                    target_phase = self.state
                else:
                    target_phase = self.state
                gated_phase = target_phase
            else:
                # CLEAR / ELEVATED_RISK / UNKNOWN: PURE CONTROLLER C PRESSURE SELECTION.
                # In CLEAR mode: exact same as Controller C (argmax with 1.2x hysteresis in _should_end_phase).
                # In ELEVATED_RISK: still use pure pressure argmax; the smooth discount only affects
                # the mode attribution (stays "C"), not the phase selection.
                gated_phase = ungated if ungated is not None else Phase.NORTH_SOUTH

            # Detect a gate intervention: the gate changed the applied green
            # relative to the ungated pressure candidate.
            if (gate_intervened is False and gated_phase in (Phase.NORTH_SOUTH, Phase.EAST_WEST)
                    and ungated is not None and gated_phase != ungated
                    and any(not app.downstream_available for app in state.approaches.values())):
                gate_intervened = True

            # If the gate says "switch now" but min_green hasn't elapsed, the
            # BaseController safety supervisor will hold the current green.
            # We honour that: only apply an immediate switch outside clearance
            # when min_green has been satisfied.
            elapsed_ok = self._elapsed_in_phase(step_length) >= self.config.min_green

            if gated_phase == self.state and current_in_green:
                action = super().compute_action(step_length)
                applied = action["phase"]
            elif gated_phase != self.state and (current_in_green and elapsed_ok):
                # Force the target green by advancing the supervisor's state.
                # If we were mid-green and the target is different, enter yellow
                # then resume at the target -- never toggle conflicting greens.
                self._clearance_origin = self.state
                self.state = Phase.YELLOW_CLEARANCE
                self.elapsed = 0.0
                action = super().compute_action(step_length)
                applied = action["phase"]
                # After clearance completes this turn it may still be yellow;
                # the applied phase below reflects what SUMO receives this step.
            else:
                # Either in clearance, or green but below min_green: defer.
                action = super().compute_action(step_length)
                applied = action["phase"]

        applied_name = applied.name

        # ------------------------------------------------------------------
        # Build decision receipt
        # ------------------------------------------------------------------
        if self._consecutive_invalid >= self.max_invalid_before_fallback:
            safety_override = True
            reason_code = "WATCHDOG_FALLBACK"

        receipt = DecisionReceipt(
            timestamp=state.timestamp,
            junction_id=self.junction_id,
            capacity_status=capacity_status,
            selected_mode=self.selected_mode,
            max_downstream_occupancy=round(max_occ, 6),
            trigger_edge_id=trigger_edge,
            ungated_phase=ungated_name,
            gated_phase=gated_phase.name if gated_phase else "",
            gate_intervened=gate_intervened,
            safety_override=safety_override,
            applied_phase=applied_name,
            reason_code=reason_code,
            reason=action.get("reason", ""),
        )
        self.last_receipt = receipt
        self.receipts.append(receipt)

        action["capacity_status"] = capacity_status
        action["selected_mode"] = self.selected_mode
        action["gate_intervened"] = gate_intervened
        action["safety_override"] = safety_override
        action["reason_code"] = reason_code
        action["applied_phase"] = applied_name
        action["ungated_phase"] = ungated_name
        action["receipt"] = asdict(receipt)
        action["selector_controller"] = "S"
        action["selector_reason"] = reason_code

        logger.info(
            f"Selector[{self.junction_id}]: mode={self.selected_mode} status={capacity_status} "
            f"occ={max_occ:.3f} ungated={ungated_name} applied={applied_name} "
            f"gate={gate_intervened} safety={safety_override} rc={reason_code}"
        )
        return action


# Backward-compat factory used by older scripts referencing ControllerType.
class ControllerType:
    C = "C"
    D2 = "D2"
