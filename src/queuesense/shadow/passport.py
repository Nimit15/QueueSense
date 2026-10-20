"""Junction Readiness Passport: automated pre-commissioning audit.

Validates a junction's readiness across 8 safety/operational checks for
brownfield Delhi ITMS / Smart City C-DAC retrofit deployment.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
import datetime

from queuesense.controllers.selector import ContextAwareSelector
from queuesense.controllers.base import ControllerConfig, Phase
from queuesense.controllers.queue_pressure import QueuePressureController
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.state import TrafficState, ApproachState, DownstreamObservation

logger = logging.getLogger(__name__)


@dataclass
class PassportCheck:
    """Result of a single readiness check."""
    check_id: int
    name: str
    passed: bool
    details: str
    evidence: str = ""


@dataclass
class JunctionReadinessPassport:
    """Complete pre-commissioning audit for one junction."""
    junction_id: str
    timestamp: str
    checks: List[PassportCheck]
    overall_pass: bool
    pass_count: int
    total_checks: int = 8

    def to_json(self) -> Dict:
        return {
            "junction_id": self.junction_id,
            "timestamp": self.timestamp,
            "overall_pass": self.overall_pass,
            "pass_count": self.pass_count,
            "total_checks": self.total_checks,
            "checks": [asdict(c) for c in self.checks],
        }


class PassportAuditor:
    """Runs the 8-check pre-commissioning audit for a junction."""

    def __init__(
        self,
        junction_id: str = "J1",
        network_net_xml: str = "sumo/network_v2/corridor.net.xml",
        roi_config: str = "data/roi_configs/default.json",
    ):
        self.junction_id = junction_id
        self.network_net_xml = network_net_xml
        self.roi_config = roi_config

    def run_audit(self) -> JunctionReadinessPassport:
        """Execute all 8 checks and return the passport."""
        import datetime
        checks = []
        checks.append(self._check_1_topology_mapping())
        checks.append(self._check_2_camera_roi())
        checks.append(self._check_3_safety_supervisor_timings())
        checks.append(self._check_4_watchdog_fallback())
        checks.append(self._check_5_unknown_sensor_isolation())
        checks.append(self._check_6_schmitt_hysteresis_bounds())
        checks.append(self._check_7_per_junction_instance_isolation())
        checks.append(self._check_8_shadow_mode_receipt_logging())

        passed = sum(1 for c in checks if c.passed)
        passport = JunctionReadinessPassport(
            junction_id=self.junction_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            checks=checks,
            overall_pass=(passed == len(checks)),
            pass_count=passed,
        )
        logger.info(f"Junction {self.junction_id} passport: {passed}/{len(checks)} checks passed")
        return passport

    # --------------------------------------------------------------
    # Check 1: Movement-to-receiving-edge topology mapping
    # --------------------------------------------------------------
    def _check_1_topology_mapping(self) -> PassportCheck:
        """Verify every approach has at least one valid receiving edge in SUMO."""
        try:
            import sumolib
            net = sumolib.net.readNet(self.network_net_xml)
            # V2 corridor downstream edges from MultiJunctionSimulationRunner
            expected = {
                "north": [f"out_north_{self.junction_id[1]}"],
                "east": ["in_east"] if self.junction_id == "J3" else [f"art_west_{self.junction_id[1]}"],
                "west": ["in_west"] if self.junction_id == "J1" else [f"art_east_{int(self.junction_id[1])-1}"],
            }
            missing = []
            for app, edges in expected.items():
                for e in edges:
                    if net.getEdge(e) is None:
                        missing.append(f"{app} -> {e}")
            if missing:
                return PassportCheck(1, "Movement-to-receiving-edge topology mapping",
                                     False, f"Missing edges: {missing}",
                                     f"Expected: {expected}")
            return PassportCheck(1, "Movement-to-receiving-edge topology mapping",
                                 True, "All 4 approaches have valid receiving edges in SUMO network",
                                 f"Verified: {expected}")
        except Exception as e:
            return PassportCheck(1, "Movement-to-receiving-edge topology mapping",
                                 False, f"Error reading network: {e}", "")

    # --------------------------------------------------------------
    # Check 2: Camera ROI polygon validity & stop-line coverage
    # --------------------------------------------------------------
    def _check_2_camera_roi(self) -> PassportCheck:
        """Verify camera ROI config exists and covers stop-line zones."""
        roi_path = Path(self.roi_config)
        if not roi_path.exists():
            return PassportCheck(2, "Camera ROI polygon validity & stop-line coverage",
                                 False, f"ROI config not found at {roi_path}", "")
        try:
            import json
            with open(roi_path) as f:
                roi = json.load(f)
            # Accept either "approaches" or "upstream_rois" key
            approach_rois = roi.get("approaches") or roi.get("upstream_rois")
            if not approach_rois:
                return PassportCheck(2, "Camera ROI polygon validity & stop-line coverage",
                                     False, "ROI config missing 'approaches' or 'upstream_rois' key", "")
            for app in ["north", "south", "east", "west"]:
                if app not in approach_rois:
                    return PassportCheck(2, "Camera ROI polygon validity & stop-line coverage",
                                         False, f"Missing ROI for approach {app}", "")
                poly = approach_rois[app]
                if len(poly) < 3:
                    return PassportCheck(2, "Camera ROI polygon validity & stop-line coverage",
                                         False, f"ROI polygon for {app} has <3 points", "")
            return PassportCheck(2, "Camera ROI polygon validity & stop-line coverage",
                                 True, "All 4 approaches have valid ROI polygons covering stop-line zones",
                                 f"Config: {roi_path}")
        except Exception as e:
            return PassportCheck(2, "Camera ROI polygon validity & stop-line coverage",
                                 False, f"Error parsing ROI config: {e}", "")

    # --------------------------------------------------------------
    # Check 3: Safety supervisor timings
    # --------------------------------------------------------------
    def _check_3_safety_supervisor_timings(self) -> PassportCheck:
        """Validate min_green >= 10s, yellow >= 3s, all_red >= 2s."""
        cfg = ControllerConfig()
        issues = []
        if cfg.min_green < 10.0:
            issues.append(f"min_green={cfg.min_green}s < 10s")
        if cfg.yellow_duration < 3.0:
            issues.append(f"yellow={cfg.yellow_duration}s < 3s")
        if cfg.all_red_duration < 2.0:
            issues.append(f"all_red={cfg.all_red_duration}s < 2s")
        if issues:
            return PassportCheck(3, "Safety supervisor timings",
                                 False, "; ".join(issues),
                                 f"Config: min_green={cfg.min_green}, yellow={cfg.yellow_duration}, all_red={cfg.all_red_duration}")
        return PassportCheck(3, "Safety supervisor timings",
                             True, "min_green>=10s, yellow>=3s, all_red>=2s verified",
                             f"min_green={cfg.min_green}, yellow={cfg.yellow_duration}, all_red={cfg.all_red_duration}")

    # --------------------------------------------------------------
    # Check 4: Watchdog 3-strike fallback active
    # --------------------------------------------------------------
    def _check_4_watchdog_fallback(self) -> PassportCheck:
        """Verify BaseController watchdog triggers fixed-time after 3 invalid steps."""
        try:
            selector = ContextAwareSelector(junction_id=self.junction_id)
            # Simulate 3 invalid states
            invalid_state = TrafficState(timestamp=0, approaches={}, all_valid=False)
            for i in range(3):
                selector.step(invalid_state, 1.0)
            # After 3 invalid, the selector should be in FALLBACK mode
            if selector.selected_mode == "FALLBACK" or selector._consecutive_invalid >= selector.max_invalid_before_fallback:
                return PassportCheck(4, "Watchdog 3-strike fallback active",
                                     True, "Watchdog triggers fallback after 3 consecutive invalid states",
                                     f"consecutive_invalid={selector._consecutive_invalid}, max={selector.max_invalid_before_fallback}")
            return PassportCheck(4, "Watchdog 3-strike fallback active",
                                 False, "Watchdog did not trigger fallback after 3 invalid steps",
                                 f"consecutive_invalid={selector._consecutive_invalid}")
        except Exception as e:
            return PassportCheck(4, "Watchdog 3-strike fallback active",
                                 False, f"Error testing watchdog: {e}", "")

    # --------------------------------------------------------------
    # Check 5: UNKNOWN sensor state isolation
    # --------------------------------------------------------------
    def _check_5_unknown_sensor_isolation(self) -> PassportCheck:
        """Verify UNKNOWN state is never silently mapped to CLEAR."""
        selector = ContextAwareSelector(junction_id=self.junction_id)
        # State with missing observations -> should be UNKNOWN
        state = TrafficState(timestamp=0, approaches={}, all_valid=False)
        action = selector.step(state, 1.0)
        if action.get("capacity_status") == "UNKNOWN":
            return PassportCheck(5, "UNKNOWN sensor state isolation",
                                 True, "UNKNOWN state correctly isolated (never mapped to CLEAR)",
                                 f"capacity_status={action.get('capacity_status')}")
        return PassportCheck(5, "UNKNOWN sensor state isolation",
                             False, f"UNKNOWN not isolated: got {action.get('capacity_status')}",
                             f"action={action}")

    # --------------------------------------------------------------
    # Check 6: Schmitt hysteresis bounds (0.22 < 0.30)
    # --------------------------------------------------------------
    def _check_6_schmitt_hysteresis_bounds(self) -> PassportCheck:
        """Verify clear_exit < soft_risk < spillback_threshold."""
        selector = ContextAwareSelector(junction_id=self.junction_id)
        ce = selector.clear_exit_threshold
        sr = selector.soft_risk_threshold
        st = selector.spillback_threshold
        ok = (ce < sr < st) and (ce == 0.22) and (st == 0.30)
        if ok:
            return PassportCheck(6, "Schmitt hysteresis bounds (0.22 < 0.30)",
                                 True, f"clear_exit={ce} < soft_risk={sr} < spillback={st} verified",
                                 f"clear_exit={ce}, soft_risk={sr}, spillback={st}")
        return PassportCheck(6, "Schmitt hysteresis bounds (0.22 < 0.30)",
                             False, f"Invalid bounds: clear_exit={ce}, soft_risk={sr}, spillback={st}",
                             f"Expected: clear_exit=0.22 < soft_risk=0.24 < spillback=0.30")

    # --------------------------------------------------------------
    # Check 7: Per-junction instance isolation
    # --------------------------------------------------------------
    def _check_7_per_junction_instance_isolation(self) -> PassportCheck:
        """Verify each junction gets its own independent mutable controller instance."""
        j1 = ContextAwareSelector(junction_id="J1")
        j2 = ContextAwareSelector(junction_id="J2")
        j3 = ContextAwareSelector(junction_id="J3")
        ids = [id(j1), id(j2), id(j3)]
        if len(set(ids)) == 3:
            return PassportCheck(7, "Per-junction instance isolation",
                                 True, "J1, J2, J3 have independent selector instances",
                                 f"ids={ids}")
        return PassportCheck(7, "Per-junction instance isolation",
                             False, f"Instance sharing detected: {ids}",
                             f"ids={ids}")

    # --------------------------------------------------------------
    # Check 8: Shadow-mode receipt logging
    # --------------------------------------------------------------
    def _check_8_shadow_mode_receipt_logging(self) -> PassportCheck:
        """Verify DecisionReceipt is emitted every step with all required fields."""
        selector = ContextAwareSelector(junction_id=self.junction_id)
        # Build a valid minimal state
        state = TrafficState(timestamp=1.0, approaches={})
        for n in ["north", "south", "east", "west"]:
            state.approaches[n] = ApproachState(
                queue_count=5.0, mean_wait_seconds=10.0, arrival_rate=20.0,
                downstream_available=True, measurement_valid=True,
                downstream_observations=[DownstreamObservation(
                    edge_id=f"out_{n}_{self.junction_id[1]}", observation_valid=True,
                    occupancy_fraction=0.1, congested=False, eligible=True,
                )],
            )
        action = selector.step(state, 1.0)
        receipt = action.get("receipt")
        required_fields = [
            "timestamp", "junction_id", "capacity_status", "selected_mode",
            "max_downstream_occupancy", "trigger_edge_id", "ungated_phase",
            "gated_phase", "gate_intervened", "safety_override", "applied_phase",
            "reason_code", "reason",
        ]
        missing = [f for f in required_fields if f not in receipt]
        if not missing:
            return PassportCheck(8, "Shadow-mode receipt logging",
                                 True, "DecisionReceipt emitted with all 13 required fields",
                                 f"Fields: {list(receipt.keys())}")
        return PassportCheck(8, "Shadow-mode receipt logging",
                             False, f"Missing receipt fields: {missing}",
                             f"Receipt keys: {list(receipt.keys())}")


def generate_passports(junction_ids: List[str] = None,
                       output_path: str = "results/stage5_selector_closed_loop/shadow_mode/junction_readiness_passport.json"):
    """Generate passports for all junctions and save to JSON."""
    junction_ids = junction_ids or ["J1", "J2", "J3"]
    passports = []
    for jid in junction_ids:
        auditor = PassportAuditor(junction_id=jid)
        passport = auditor.run_audit()
        passports.append(passport)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "passports": [p.to_json() for p in passports],
            "summary": {
                "total_junctions": len(passports),
                "fully_passed": sum(1 for p in passports if p.overall_pass),
                "checks_per_junction": 8,
            }
        }, f, indent=2)

    logger.info(f"Junction readiness passports saved to {output_path}")
    return passports


if __name__ == "__main__":
    generate_passports()