"""Multi-Junction Simulation Runner for QueueSense V2 Corridor.

Manages all signalized junctions (J1, J2, J3) in a single coherent SUMO simulation,
integrating local controllers, safety supervisors, and the NetworkCoordinator.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import traci
import sumolib
from sumolib import checkBinary

from queuesense.state import TrafficState, ApproachState, DownstreamObservation
from queuesense.controllers.base import Phase
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.fixed_time import FixedTimeController
from queuesense.controllers.actuated import ActuatedController
from queuesense.controllers.queue_pressure import QueuePressureController
from queuesense.network.coordinator import NetworkCoordinator
from queuesense.network.state import JunctionState

logger = logging.getLogger(__name__)


class MultiJunctionSimulationRunner:
    """Runs multi-junction SUMO simulation with TraCI, NetworkCoordinator, and local controllers."""

    def __init__(
        self,
        net_file: str,
        route_files: list,
        output_dir: str = "results/network_v2_diagnostics",
        step_length: float = 1.0,
        duration: int = 3600,
        warmup_time: int = 300,
        controllers: Optional[Dict[str, object]] = None,
        use_coordinator: bool = True,
        use_spillback_gate: bool = True,
        gui: bool = False,
        csv_prefix: str = "multijunction",
        seed: int = 42,
    ):
        self.net_file = net_file
        self.route_files = route_files
        self.output_dir = Path(output_dir)
        self.step_length = step_length
        self.duration = duration
        self.warmup_time = warmup_time
        self.use_coordinator = use_coordinator
        self.use_spillback_gate = use_spillback_gate
        self.gui = gui
        self.csv_prefix = csv_prefix
        self.seed = seed

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Junctions in corridor
        self.junction_ids = ["J1", "J2", "J3"]

        # Initialize controllers for each junction
        if controllers:
            self.controllers = controllers
        else:
            # Default all junctions to QueueSenseController (or specified type)
            self.controllers = {
                "J1": QueueSenseController(),
                "J2": QueueSenseController(),
                "J3": QueueSenseController(),
            }

        # Initialize NetworkCoordinator
        self.coordinator = NetworkCoordinator(self.junction_ids)

        # Downstream edge mapping for V2 corridor
        self._downstream_edges = {
            "J1": {"west": ["art_east_1"], "east": ["art_west_1"], "north": ["out_north_1"]},
            "J2": {"west": ["art_east_2"], "east": ["art_west_2"], "north": ["out_north_2"]},
            "J3": {"west": ["out_east"], "east": ["art_west_2"], "north": ["out_north_3"]},
        }

        self.metrics = []
        self._arrived_cumulative = 0
        self._prev_vehicle_ids = {}
        self._last_downstream_occupancy = 0.0
        self._detailed_telemetry = []  # Per-receiving-edge audit trail

        # Run-level summary accumulators (added for Stage C benchmark).
        # These are cheap TraCI calls that were previously not collected,
        # so the per-run outputs could not support waiting-time, teleport,
        # gate-intervention or phase-switch analysis.  They are cumulative
        # counters over the whole run and are written to a summary JSON.
        self._gate_interventions = 0
        self._phase_switches = 0
        self._prev_phase_by_junction = {}
        self._spillback_ns_seconds = 0
        self._spillback_ew_seconds = 0
        # Gate-intervention attribution: which approach/receiving-edge the gate
        # suppressed, counted once per step per suppressed approach.  This is
        # the same event the detailed telemetry records, accumulated here so
        # the run summary can carry it without re-reading the CSV.
        self._gate_intervention_details = []

        # Per-step decision trace: one row per junction per step recording
        # the full control path (receiving edge, occupancy, eligibility,
        # ungated vs gated phase, requested phase, applied SUMO phase).
        # Written to a decision_trace.csv for end-to-end audit.
        self._decision_trace = []

        # ---- 4 explicit gate metrics (per user specification) ----
        # 1. Physical congestion observations: valid receiving-edge
        #    measurements that meet the congestion criteria (occupancy >=
        #    threshold).  Computed identically for D1 and D2; the gate does
        #    not change whether a measurement is congested.
        self._physical_congestion = 0
        # 2. Gate restrictions: an ENABLED gate makes a candidate movement
        #    ineligible (gate_suppresses=True).  D1 (gate OFF) records ZERO
        #    restrictions even when physical congestion is present.
        self._gate_restrictions = 0
        # 3. Actual phase-change interventions: the gate causes the applied
        #    phase decision to differ from the ungated decision (gate_event
        #    == "phase_change").
        self._gate_phase_changes = 0
        # 4. Gate-caused holds: the gate prevents a transition that the ungated
        #    policy would otherwise have made (gate_event == "hold").  Reported
        #    separately from phase changes.
        self._gate_holds = 0

        # Read spillback threshold from config
        try:
            import yaml
            config_path = Path("configs/experiment.yaml")
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.downstream_threshold = float(config.get('controllers', {}).get('queuesense', {}).get('spillback_threshold', 0.30))
        except Exception as e:
            logger.warning(f"Could not read spillback_threshold from config: {e}. Using default 0.30")
            self.downstream_threshold = 0.30

        logger.info(
            f"MultiJunctionSimulationRunner initialized: net={net_file}, junctions={self.junction_ids}, "
            f"coordinator={use_coordinator}, spillback_gate={use_spillback_gate}, seed={seed}"
        )

    def _init_simulation(self):
        """Initialize TraCI simulation."""
        sumo_binary = checkBinary("sumo-gui") if self.gui else checkBinary("sumo")
        traci.start(
            [sumo_binary, "-n", self.net_file, "-r", ",".join(self.route_files),
             "--step-length", str(self.step_length), "--seed", str(self.seed), "--no-step-log"],
            label="multijunction_sim",
        )
        # SUMO program mapping for 4-phase signals in V2 network
        self._phase_to_sumo = {Phase.EAST_WEST: 0, Phase.YELLOW_CLEARANCE: 1,
                               Phase.NORTH_SOUTH: 2, Phase.ALL_RED: 3}
        # Edge IDs used for waiting-time aggregation.  Collected once from the
        # network so the per-step wait sum covers every edge, not just the
        # junction approach edges.
        try:
            self._edge_ids = traci.edge.getIDList()
        except Exception:
            self._edge_ids = []
        logger.info("Multi-junction TraCI simulation started")

    def _collect_junction_state(self, junction_id: str) -> TrafficState:
        """Collect traffic state for a specific junction from TraCI."""
        approach_edges = {
            "north": f"in_north_{junction_id[1]}",
            "east": "in_east" if junction_id == "J3" else f"art_west_{int(junction_id[1])}",
            "west": "in_west" if junction_id == "J1" else f"art_east_{int(junction_id[1])-1}",
        }

        approaches = {}
        all_valid = True

        for name, edge_id in approach_edges.items():
            try:
                veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
                stopped_ids = [vid for vid in veh_ids if traci.vehicle.getSpeed(vid) < 0.1]
                queue_count = len(stopped_ids)
                mean_wait = 0.0
                if stopped_ids:
                    wait_times = [traci.vehicle.getWaitingTime(vid) for vid in stopped_ids if traci.vehicle.getSpeed(vid) < 0.1]
                    if wait_times:
                        mean_wait = sum(wait_times) / len(wait_times)

                # Arrival rate tracking
                valid_current = set(veh_ids)
                prev = self._prev_vehicle_ids.get(edge_id, set())
                newly_entered = valid_current - prev
                arrival_rate = len(newly_entered) * (3600.0 / self.step_length) if self.step_length > 0 else 0.0
                self._prev_vehicle_ids[edge_id] = valid_current

                # Downstream availability (spillback awareness)
                #
                # OCCUPANCY UNIT CONVENTION (verified for SUMO 1.28.0 edge API):
                #   traci.edge.getLastStepOccupancy() returns a normalized occupancy
                #   FRACTION in [0.0, 1.0], despite the official Python API docstring
                #   describing it as percent.  Verified empirically: 14 vehicles
                #   (70.0 m total length) on a 276.63 m single-lane edge produced
                #   0.2530 -- exactly matching the vehicle fill ratio (70/276.63).
                #   The raw return is therefore treated directly as
                #   ``edge_occupancy_fraction``.  NO /100.0 conversion is applied.
                #   The configured threshold (spillback_threshold) is expressed as a
                #   fraction: 0.30 = 30% normalized occupancy.
                #
                # DOCUMENTED DISCREPANCY: SUMO's Python TraCI API docstring states
                #   getLastStepOccupancy() returns "net occupancy in %".  The observed
                #   runtime behaviour in SUMO 1.28.0 contradicts this: the returned
                #   values are already normalized fractions.  We follow the observed
                #   implementation, not the docstring, and log both raw and normalized
                #   values so the discrepancy is auditable.
                #
                # NOTE: other occupancy sources (lane-area detectors, vision-derived
                #   occupancy) may use different scales.  Normalize each at its own
                #   boundary; do not assume every occupancy API shares the edge API's
                #   convention.
                #
                # PHYSICAL CONGESTION IS MEASURED REGARDLESS OF GATE STATE.
                # D1 (gate OFF) and D2 (gate ON) must compute identical physical congestion
                # from identical measurements.  Only the GATE DECISION differs:
                #   - D2: downstream_available=False suppresses phase selection.
                #   - D1: downstream_available is still computed, but the controller
                #          ignores it (spillback_gate_enabled=False).
                # The gate decision lives in the controller, not in the measurement.
                downstream_available = True
                downstream_occupancy_fraction = 0.0
                downstream_observations: List[DownstreamObservation] = []

                downstream_edges = self._downstream_edges.get(junction_id, {}).get(name, [])
                occ_list = []
                for dedge in downstream_edges:
                    try:
                        raw_occ = traci.edge.getLastStepOccupancy(dedge)
                        # Verified edge API: raw return IS the normalized fraction.
                        occ_fraction = raw_occ
                        occ_list.append(occ_fraction)

                        obs = DownstreamObservation(
                            edge_id=dedge,
                            observation_valid=True,
                            edge_occupancy_fraction=raw_occ,
                            occupancy_fraction=occ_fraction,
                            threshold=self.downstream_threshold,
                            congested=occ_fraction >= self.downstream_threshold,
                            eligible=occ_fraction < self.downstream_threshold,
                            gate_suppresses=self.use_spillback_gate and occ_fraction >= self.downstream_threshold,
                        )
                        downstream_observations.append(obs)
                        # Metric 1: physical congestion observation -- a VALID
                        # measurement that meets the congestion criteria.  This
                        # is gate-independent: D1 and D2 count identical
                        # observations from identical measurements.
                        if obs.observation_valid and obs.congested:
                            self._physical_congestion += 1
                        # Metric 2: gate restriction -- an ENABLED gate makes a
                        # candidate movement ineligible (gate_suppresses=True).
                        # D1 (gate OFF) records ZERO restrictions even when
                        # physical congestion is present, because
                        # gate_suppresses is False when use_spillback_gate is
                        # False.
                        if obs.gate_suppresses:
                            self._gate_restrictions += 1
                    except Exception as e:
                        # UNKNOWN state: edge lookup failed. Do NOT treat as physical blockage.
                        # Apply conservative safety fallback but log the fault separately.
                        occ_list.append(1.0)  # Conservative fallback for eligibility
                        downstream_observations.append(DownstreamObservation(
                            edge_id=dedge,
                            observation_valid=False,
                            edge_occupancy_fraction=0.0,
                            occupancy_fraction=0.0,
                            threshold=self.downstream_threshold,
                            congested=False,  # Unknown, not congested
                            eligible=False,   # Conservative: treat as ineligible
                            gate_suppresses=False,  # Gate decision requires valid observation
                            error=str(e),
                        ))

                if occ_list:
                    downstream_occupancy_fraction = max(occ_list)
                    # Approach is eligible if AT LEAST ONE receiving edge is below threshold
                    downstream_available = any(occ < self.downstream_threshold for occ in occ_list)

                approaches[name] = ApproachState(
                    queue_count=float(queue_count),
                    mean_wait_seconds=float(mean_wait),
                    arrival_rate=float(arrival_rate),
                    downstream_available=downstream_available,
                    measurement_valid=True,
                    downstream_observations=downstream_observations,
                )
                # Track downstream occupancy for logging (max fraction across all checked edges)
                if name == "west" and downstream_observations:
                    self._last_downstream_occupancy = downstream_occupancy_fraction
                    self._last_downstream_obs = downstream_observations  # For detailed audit
            except Exception as e:
                logger.warning(f"Failed to collect state for {junction_id} approach {name}: {e}")
                approaches[name] = ApproachState()
                all_valid = False

        return TrafficState(timestamp=traci.simulation.getTime(), approaches=approaches, all_valid=all_valid)

    def run(self):
        """Run the multi-junction simulation."""
        try:
            self._init_simulation()
            logger.info(f"Running multi-junction simulation for {self.duration}s")

            step = 1
            while True:
                traci.simulationStep()
                current_time = traci.simulation.getTime()

                if current_time < self.warmup_time:
                    continue
                if current_time > self.duration:
                    break

                # 1. Collect state and publish to coordinator for each junction
                junction_states = {}
                for j_id in self.junction_ids:
                    state = self._collect_junction_state(j_id)
                    j_state = JunctionState(
                        junction_id=j_id,
                        timestamp=current_time,
                        approaches=state.approaches,
                        phase=self.controllers[j_id].state,
                        all_valid=state.all_valid,
                        downstream_blocked=any(not app.downstream_available for app in state.approaches.values()),
                    )
                    self.coordinator.update_junction_state(j_state)
                    junction_states[j_id] = state

                # 2. Get network coordination recommendations
                recommendations = {}
                if self.use_coordinator:
                    recommendations = self.coordinator.generate_recommendations()

                # 3. Step each junction controller and apply action to SUMO
                for j_id in self.junction_ids:
                    controller = self.controllers[j_id]
                    state = junction_states[j_id]

                    controller.update_state(state)
                    action = controller.step(state, self.step_length)

                    # Apply coordination recommendation if active (e.g. green extension)
                    if self.use_coordinator and j_id in recommendations:
                        rec = recommendations[j_id]
                        # Get current phase from controller state
                        current_phase = controller.state if hasattr(controller, 'state') else None
                        if rec.get("extend_green") and current_phase and action["phase"] == current_phase:
                            action["duration"] += 5.0  # Coordinated extension
                            action["reason"] += f" | {rec['reason']}"

                    sumo_phase_idx = self._phase_to_sumo.get(action["phase"], 0)
                    traci.trafficlight.setPhase(j_id, sumo_phase_idx)

                    # Per-step decision trace: record the full control path for
                    # this junction BEFORE the phase-switch accounting so the
                    # applied SUMO program index is captured exactly as set.
                    # This is the audit record proving the gated decision
                    # reaches traci.trafficlight.setPhase().
                    trace_blocked_edges = []
                    trace_blocked_occ = 0.0
                    trace_eligible_approaches = []
                    for app_name, app in state.approaches.items():
                        if not app.downstream_available:
                            for obs in app.downstream_observations:
                                if obs.observation_valid and obs.congested:
                                    trace_blocked_edges.append(obs.edge_id)
                                    trace_blocked_occ = max(
                                        trace_blocked_occ, obs.edge_occupancy_fraction
                                    )
                        else:
                            trace_eligible_approaches.append(app_name)
                    self._decision_trace.append({
                        "time": current_time,
                        "run_id": self.csv_prefix,
                        "junction": j_id,
                        "controller_id": id(controller),
                        "gate_enabled": self.use_spillback_gate,
                        "blocked_receiving_edges": ",".join(trace_blocked_edges),
                        "blocked_occupancy_fraction": round(trace_blocked_occ, 4),
                        "eligible_approaches": ",".join(trace_eligible_approaches),
                        "requested_phase": action["phase"].name,
                        "sumo_phase_idx": sumo_phase_idx,
                        "ungated_phase": (
                            (action.get("ungated_phase").name if hasattr(action.get("ungated_phase"), 'name')
                             else str(action.get("ungated_phase")))
                            if action.get("ungated_phase") else ""
                        ),
                        "gate_event": action.get("gate_event") or "",
                        "reason": str(action.get("reason", "")),
                    })

                    # Phase-switch accounting: count a switch whenever the applied
                    # SUMO program index differs from the previous step's.
                    prev_idx = self._prev_phase_by_junction.get(j_id)
                    if prev_idx is not None and prev_idx != sumo_phase_idx:
                        self._phase_switches += 1
                    self._prev_phase_by_junction[j_id] = sumo_phase_idx

                    # Gate-intervention accounting: the QueueSense controller tags
                    # every downstream-blockage decision with a GATE_INTERVENTION
                    # marker in its reason string.  Count one event per junction
                    # per step where the controller actually exercised the gate
                    # (suppressed or held a phase because of downstream blockage).
                    # This is the decision-level count; the per-observation
                    # ``gate_suppresses`` flag in the detailed telemetry is the
                    # physical-congestion view and may differ when the controller
                    # does not change phase despite congestion.
                    if "GATE_INTERVENTION" in str(action.get("reason", "")):
                        self._gate_interventions += 1
                        # Attribute the intervention to the congested receiving
                        # edge(s) that drove the decision.
                        # We count one event per junction per step (controller decision),
                        # not per physical edge, to match the controller's action granularity.
                        # The matching detailed telemetry count per edge is done by the
                        # per-observation ``gate_suppresses`` flag, which may differ when
                        # the controller holds a phase but does not suppress it.
                        gate_event = action.get("gate_event")
                        ungated_phase = action.get("ungated_phase")
                        if gate_event == "phase_change":
                            self._gate_phase_changes += 1
                        elif gate_event == "hold":
                            self._gate_holds += 1
                        # Link this intervention to the actual congested receiving
                        # edge(s) observed this step, so the audit trail is not a
                        # placeholder.  Prefer the blocked edge driving the
                        # suppressed movement; fall back to any congested edge.
                        blocked_edges = []
                        blocked_occ = 0.0
                        for app_name, app in state.approaches.items():
                            for obs in app.downstream_observations:
                                if obs.observation_valid and obs.congested:
                                    blocked_edges.append(obs.edge_id)
                                    blocked_occ = max(blocked_occ, obs.edge_occupancy_fraction)
                        # Record the ungated candidate (the phase the ungated
                        # policy would have selected) and the gated decision.
                        self._gate_intervention_details.append({
                            "time": current_time,
                            "junction": j_id,
                            "approach": ",".join(blocked_edges) or "unknown",
                            "receiving_edge": ",".join(blocked_edges) or "unknown",
                            "edge_occupancy_fraction": round(blocked_occ, 4),
                            "gate_event": gate_event,
                            "ungated_phase": ungated_phase.name if ungated_phase else None,
                            "applied_phase": action["phase"].name,
                        })

                    # Log metrics
                arrived_step = int(traci.simulation.getArrivedNumber())
                self._arrived_cumulative += arrived_step
                remaining = int(traci.simulation.getMinExpectedNumber())

                # Track spillback per direction
                spillback_ns = 0
                spillback_ew = 0
                spillback_edges_ns = []
                spillback_edges_ew = []
                for j_id in self.junction_ids:
                    for name, app in junction_states[j_id].approaches.items():
                        if not app.downstream_available:
                            if name in ("north", "south"):
                                spillback_ns = 1
                                spillback_edges_ns.extend(
                                    obs.edge_id for obs in app.downstream_observations
                                    if obs.observation_valid and obs.congested
                                )
                            else:
                                spillback_ew = 1
                                spillback_edges_ew.extend(
                                    obs.edge_id for obs in app.downstream_observations
                                    if obs.observation_valid and obs.congested
                                )

                # Spillback duration: accumulate seconds during which a
                # direction is downstream-blocked (1 step = 1 second at step 1.0).
                self._spillback_ns_seconds += spillback_ns
                self._spillback_ew_seconds += spillback_ew

                # Total system waiting time across all edges (SUMO edge API).
                # Reported as a per-step sum; the run-level mean is derived
                # from the CSV by the analysis pipeline.
                total_wait = 0.0
                try:
                    for edge in self._edge_ids:
                        total_wait += float(traci.edge.getWaitingTime(edge))
                except Exception:
                    total_wait = float("nan")

                self.metrics.append({
                    "time": current_time,
                    "arrived_this_step": arrived_step,
                    "arrived_cumulative": self._arrived_cumulative,
                    "remaining_expected": remaining,
                    "queue_ns": sum(junction_states[j_id].approaches.get(n, ApproachState()).queue_count
                                    for j_id in self.junction_ids for n in ["north", "south"]),
                    "queue_ew": sum(junction_states[j_id].approaches.get(n, ApproachState()).queue_count
                                    for j_id in self.junction_ids for n in ["east", "west"]),
                    "spillback_ns": spillback_ns,
                    "spillback_ew": spillback_ew,
                    "spillback_edges_ns": ",".join(spillback_edges_ns),
                    "spillback_edges_ew": ",".join(spillback_edges_ew),
                    "downstream_occupancy": self._last_downstream_occupancy,
                    "spillback_threshold": self.downstream_threshold,
                    "spillback_gate": self.use_spillback_gate,
                    "total_wait_seconds": total_wait,
                })

                # Per-receiving-edge detailed telemetry (audit trail)
                for j_id in self.junction_ids:
                    for name, app in junction_states[j_id].approaches.items():
                        for obs in app.downstream_observations:
                            self._detailed_telemetry.append({
                                "time": current_time,
                                "junction": j_id,
                                "approach": name,
                                "receiving_edge": obs.edge_id,
                                "observation_valid": obs.observation_valid,
                                "error": obs.error,
                                "edge_occupancy_fraction": obs.edge_occupancy_fraction,
                                "occupancy_fraction": obs.occupancy_fraction,
                                "threshold": obs.threshold,
                                "congested": obs.congested,
                                "eligible": obs.eligible,
                                "gate_suppresses": obs.gate_suppresses,
                                "gate_enabled": self.use_spillback_gate,
                            })

                step += 1

            # Write metrics CSV
            import csv
            filename = self.output_dir / f"{self.csv_prefix}_seed{self.seed}.csv"
            if self.metrics:
                with open(filename, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.metrics[0].keys())
                    writer.writeheader()
                    writer.writerows(self.metrics)
                logger.info(f"Multi-junction metrics written to {filename}")

            # Run-level summary JSON.  These counters are NOT derivable from
            # the per-step CSV alone (gate interventions and phase switches are
            # controller-side events), so they are written explicitly.
            summary = {
                "csv": str(filename),
                "seed": self.seed,
                "duration": self.duration,
                "steps": len(self.metrics),
                "arrived_cumulative": self._arrived_cumulative,
                "remaining_expected": int(traci.simulation.getMinExpectedNumber()),
                "spillback_ns_seconds": self._spillback_ns_seconds,
                "spillback_ew_seconds": self._spillback_ew_seconds,
                "phase_switches": self._phase_switches,
                "gate_interventions": self._gate_interventions,
                "gate_intervention_details": self._gate_intervention_details,
                # ---- 4 explicit gate metrics (per user specification) ----
                "physical_congestion_observations": self._physical_congestion,
                "gate_restrictions": self._gate_restrictions,
                "gate_phase_change_interventions": self._gate_phase_changes,
                "gate_caused_holds": self._gate_holds,
                "spillback_gate": self.use_spillback_gate,
                "total_wait_seconds": sum(
                    float(r.get("total_wait_seconds", 0.0)) for r in self.metrics
                    if r.get("total_wait_seconds") is not None
                ),
                "mean_wait_seconds": (
                    sum(float(r.get("total_wait_seconds", 0.0)) for r in self.metrics
                        if r.get("total_wait_seconds") is not None)
                    / max(1, sum(1 for r in self.metrics if r.get("total_wait_seconds") is not None))
                ),
                # Teleport counts: vehicles that disappeared without a normal
                # arrival.  Reported as recorded, never as zero when the API is
                # unavailable (None is written to the manifest instead).
                "teleports": None,
            }
            try:
                summary["teleports"] = int(traci.simulation.getStartingTeleportNumber()) + int(traci.simulation.getEndingTeleportNumber())
            except Exception:
                summary["teleports"] = None
            summary_path = self.output_dir / f"{self.csv_prefix}_seed{self.seed}_summary.json"
            summary["decision_trace"] = str(
                self.output_dir / f"{self.csv_prefix}_seed{self.seed}_decision_trace.csv"
            )
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Run summary written to {summary_path}")

            # Write per-step decision trace (full control-path audit)
            if self._decision_trace:
                trace_filename = self.output_dir / f"{self.csv_prefix}_seed{self.seed}_decision_trace.csv"
                with open(trace_filename, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self._decision_trace[0].keys())
                    writer.writeheader()
                    writer.writerows(self._decision_trace)
                logger.info(f"Decision trace written to {trace_filename}")

            # Write per-receiving-edge detailed telemetry
            if self._detailed_telemetry:
                detail_filename = self.output_dir / f"{self.csv_prefix}_seed{self.seed}_detailed.csv"
                with open(detail_filename, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self._detailed_telemetry[0].keys())
                    writer.writeheader()
                    writer.writerows(self._detailed_telemetry)
                logger.info(f"Multi-junction detailed telemetry written to {detail_filename}")

        except Exception as e:
            logger.exception(f"Multi-junction simulation failed: {e}")
            raise
        finally:
            traci.close()
            logger.info("Multi-junction simulation closed")
