"""
TraCI Simulation Runner
Runs a SUMO simulation with TraCI, applying a controller and logging metrics.
"""

import os
import logging
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

import traci
import sumolib
from sumolib import checkBinary

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.base import Phase
from queuesense.controllers.fixed_time import FixedTimeController


logger = logging.getLogger(__name__)


class SimulationRunner:
    """Runs SUMO simulation with TraCI and a controller."""

    def __init__(
        self,
        net_file: str,
        route_files: list,
        output_dir: str = "results/raw",
        step_length: float = 1.0,
        duration: int = 3600,
        warmup_time: int = 300,
        controller=None,
        gui: bool = False,
        csv_prefix: str = "controller",
        seed: int = 42,
    ):
        """
        Initialize simulation runner.

        Args:
            net_file: Path to SUMO network file (.net.xml)
            route_files: List of route files (.rou.xml)
            output_dir: Directory to save metrics CSV
            step_length: Simulation step length in seconds
            duration: Total simulation duration in seconds
            warmup_time: Warmup period before metrics collection (seconds)
            controller: Controller instance (defaults to FixedTimeController)
            gui: Whether to run with SUMO-GUI
            seed: Random seed for reproducible SUMO simulation
        """
        self.net_file = net_file
        self.route_files = route_files
        self.output_dir = Path(output_dir)
        self.step_length = step_length
        self.duration = duration
        self.warmup_time = warmup_time
        self.controller = controller or FixedTimeController()
        self.gui = gui
        self.csv_prefix = csv_prefix
        self.seed = seed

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Read downstream threshold from config
        try:
            import yaml
            config_path = Path("configs/experiment.yaml")
            with config_path.open('r') as f:
                config = yaml.safe_load(f)
            # Read from controllers.queuesense.spillback_threshold
            self.downstream_threshold = float(config.get('controllers', {}).get('queuesense', {}).get('spillback_threshold', 0.85))
        except Exception as e:
            logger.warning(f"Could not read spillback_threshold from configs/experiment.yaml: {e}. Using default 0.85")
            self.downstream_threshold = 0.85

        # Build downstream edges mapping from network file
        # For the specific network topology (corridor.net.xml), we define the primary
        # downstream edge for each approach based on the actual traffic flow routes:
        # - North approach (in_north) -> out_north (north-south flow)
        # - East approach (in_east) -> art_west (east-west return flow)
        # - West approach (in_west) -> art_east (west-east main flow, BOTTLENECK)
        # - South approach (out_north) -> no downstream (it's an exit edge)
        # This avoids the issue of multiple possible downstream edges from all turning movements.
        self._downstream_edges = {
            "in_north": ["out_north"],
            "in_east": ["art_west"],
            "in_west": ["art_east"],  # The bottleneck edge
            "out_north": [],  # Exit edge, no downstream
        }
        # Which direction does each downstream edge belong to?  Used to set the
        # spillback flag per direction (north_south / east_west) in _log_metrics.
        # art_east is the west->east mainline (serves the west approach, i.e.
        # EAST_WEST movement); out_north is the north->south cross street
        # (serves the north approach, i.e. NORTH_SOUTH movement).
        self._spillback_directions = {
            "art_east": "east_west",
            "out_north": "north_south",
        }

        # Verify these edges exist in the network
        try:
            tree = ET.parse(self.net_file)
            root = tree.getroot()
            existing_edges = {edge.get('id') for edge in root.findall('.//edge')}
            for from_edge, to_edges in self._downstream_edges.items():
                for to_edge in to_edges:
                    if to_edge not in existing_edges:
                        logger.warning(f"Downstream edge {to_edge} not found in network")
        except Exception as e:
            logger.warning(f"Failed to verify network edges: {e}. Downstream eligibility will be disabled.")
            self._downstream_edges = {}


        # Metrics storage
        self.metrics = []
        # Cumulative arrivals accumulator
        self._arrived_cumulative = 0
        # Previous vehicle IDs for each approach edge to compute arrival rate
        self._prev_vehicle_ids = {}

        logger.info(
            f"SimulationRunner initialized: net={net_file}, routes={route_files}, "
            f"duration={duration}s, warmup={warmup_time}s, gui={gui}, seed={seed}"
        )

    def _init_simulation(self):
        """Initialize TraCI simulation on an isolated free port.

        A fixed ``port=0`` start is unsafe when several TraCI sessions are
        launched in the same process: SUMO can bind to the same ephemeral
        port twice and the second session dies with a ``TraCIException``.
        ``port=0`` lets SUMO pick a free port deterministically, and we read
        the chosen port back from ``traci.getConnection()`` so a retry can
        start on a different one.
        """
        sumo_binary = checkBinary("sumo-gui") if self.gui else checkBinary("sumo")
        traci.start(
            [sumo_binary, "-n", self.net_file, "-r", ",".join(self.route_files),
             "--step-length", str(self.step_length), "--seed", str(self.seed)],
            label="sim",
        )
        # Map our Phase enum to SUMO phase indices for the static program
        # SUMO program N1: [0=EAST_WEST green, 1=EW yellow, 2=NORTH_SOUTH green, 3=NS yellow]
        self._phase_to_sumo = {Phase.EAST_WEST: 0, Phase.YELLOW_CLEARANCE: 1,
                               Phase.NORTH_SOUTH: 2, Phase.ALL_RED: 3}
        # Map SUMO phase index back to our Phase enum
        self._sumo_to_phase = {0: Phase.EAST_WEST, 1: Phase.YELLOW_CLEARANCE,
                               2: Phase.NORTH_SOUTH, 3: Phase.ALL_RED}
        logger.info(f"Phase mapping: {self._phase_to_sumo}")
        logger.info("TraCI simulation started")

    def _collect_traffic_state(self) -> TrafficState:
        """Collect traffic state from TraCI for all approaches.

        Returns:
            TrafficState object with approach metrics.
        """
        approaches = {}
        all_valid = True

        # Define approaches and their SUMO edge IDs
        approach_edges = {
            "north": "in_north",
            "south": "out_north",
            "east": "in_east",
            "west": "in_west",
        }

        for name, edge_id in approach_edges.items():
            try:
                # Get vehicle counts and waiting times
                veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
                stopped_ids = []
                for vid in veh_ids:
                    try:
                        if traci.vehicle.getSpeed(vid) < 0.1:
                            stopped_ids.append(vid)
                    except traci.exceptions.TraCIException:
                        # Vehicle no longer exists, skip it
                        pass

                queue_count = len(stopped_ids)
                mean_wait = 0.0
                if stopped_ids:
                    wait_times = []
                    for vid in stopped_ids:
                        try:
                            wait_times.append(traci.vehicle.getWaitingTime(vid))
                        except traci.exceptions.TraCIException:
                            # Vehicle no longer exists, skip it
                            pass
                    if wait_times:
                        mean_wait = sum(wait_times) / len(wait_times)

                # Arrival rate: vehicles entering the approach in the last step
                # Track previous vehicle IDs to compute newly entered vehicles
                # Filter out any vehicle IDs that might cause TraCI exceptions
                valid_current_veh_ids = set()
                for vid in veh_ids:
                    try:
                        # Just check if the vehicle exists by trying to get its speed
                        traci.vehicle.getSpeed(vid)
                        valid_current_veh_ids.add(vid)
                    except traci.exceptions.TraCIException:
                        # Vehicle no longer exists, skip it
                        pass

                prev_veh_ids = self._prev_vehicle_ids.get(edge_id, set())
                newly_entered = valid_current_veh_ids - prev_veh_ids
                # Convert to vehicles per minute (assuming step_length in seconds)
                arrival_rate = len(newly_entered) * (3600.0 / self.step_length) if self.step_length > 0 else 0.0
                # Update previous vehicle IDs for next step
                self._prev_vehicle_ids[edge_id] = valid_current_veh_ids

                # Downstream available: check if any of the downstream edges for this approach is not jammed
                # An approach is eligible if at least one of its downstream edges has occupancy below threshold
                downstream_available = True
                if edge_id in self._downstream_edges:
                    # Check if any downstream edge is below threshold
                    downstream_occupancies = []
                    for downstream_edge in self._downstream_edges[edge_id]:
                        try:
                            occ = traci.edge.getLastStepOccupancy(downstream_edge)
                            downstream_occupancies.append(occ)
                        except:
                            # If we can't read occupancy, assume it's blocked to be safe
                            downstream_occupancies.append(1.0)

                    # Approach is eligible if at least one downstream edge is below threshold
                    downstream_available = any(occ < self.downstream_threshold for occ in downstream_occupancies)
                else:
                    # No downstream edges found, assume eligible (should not happen in normal network)
                    downstream_available = True

                # Measurement validity: True if approach state was successfully computed.
                # A frame with zero vehicles is a valid observation, not a sensor failure.
                # measurement_valid is only False if an exception prevents state collection.
                measurement_valid = True

                approaches[name] = ApproachState(
                    queue_count=float(queue_count),
                    mean_wait_seconds=float(mean_wait),
                    arrival_rate=float(arrival_rate),
                    downstream_available=downstream_available,
                    measurement_valid=measurement_valid,
                )
            except Exception as e:
                logger.warning(f"Failed to collect state for {name}: {e}")
                approaches[name] = ApproachState()
                all_valid = False

        return TrafficState(timestamp=traci.simulation.getTime(), approaches=approaches, all_valid=all_valid)

    def _log_metrics(self, step: int):
        """Log metrics at each step."""
        time = traci.simulation.getTime()
        # Correct metric semantics per SUMO API
        # getArrivedNumber() reports vehicles arrived during latest step
        arrived_this_step = int(traci.simulation.getArrivedNumber())
        # Accumulate exactly once per step
        self._arrived_cumulative += arrived_this_step
        arrived_cumulative = self._arrived_cumulative

        # Remaining vehicles expected (in network + waiting to start)
        remaining_expected = int(traci.simulation.getMinExpectedNumber())

        # Departed and loaded for additional context
        departed_this_step = int(traci.simulation.getDepartedNumber())
        loaded_this_step = int(traci.simulation.getLoadedNumber())

        # Queue lengths per approach
        queues = {}
        for name in ["north", "south", "east", "west"]:
            edge_id = {"north": "in_north", "south": "out_north", "east": "in_east", "west": "in_west"}[name]
            veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
            stopped = [vid for vid in veh_ids if traci.vehicle.getSpeed(vid) < 0.1]
            queues[name] = len(stopped)

        # Spillback: a direction is flagged when the occupancy of its receiving
        # downstream edge reaches the threshold.  The mapping is derived from
        # ``_spillback_directions`` so it stays consistent with the eligibility
        # check in ``_collect_traffic_state``.
        spillback = {"north_south": False, "east_west": False}
        for edge_id, direction in self._spillback_directions.items():
            try:
                occ = traci.edge.getLastStepOccupancy(edge_id)
            except Exception:
                occ = 1.0  # unreadable -> assume blocked, be conservative
            if occ >= self.downstream_threshold:
                spillback[direction] = True

        # Preserve legacy column name for compatibility but document correct meaning.
        # The old 'completed' column was misused to store getMinExpectedNumber().
        # We now keep it mapped to arrived_cumulative for backward compatibility,
        # since arrived_cumulative is the correct count of completed trips.
        # Consumers should migrate to using arrived_cumulative directly.
        completed_legacy = arrived_cumulative

        # Log to CSV
        self.metrics.append({
            "time": time,
            "arrived_this_step": arrived_this_step,
            "arrived_cumulative": arrived_cumulative,
            "departed_this_step": departed_this_step,
            "loaded_this_step": loaded_this_step,
            "remaining_expected": remaining_expected,
            # Legacy compatibility
            "completed": completed_legacy,
            "queue_north": queues.get("north", 0),
            "queue_south": queues.get("south", 0),
            "queue_east": queues.get("east", 0),
            "queue_west": queues.get("west", 0),
            "spillback_ns": int(spillback["north_south"]),
            "spillback_ew": int(spillback["east_west"]),
        })

        logger.debug(f"Metrics @ t={time}s: arrived_step={arrived_this_step}, cumulative={arrived_cumulative}, remaining={remaining_expected}, queues={queues}, spillback={spillback}")

    def _write_metrics(self):
        """Write metrics to CSV file."""
        import csv

        if not self.metrics:
            logger.warning("No metrics to write")
            return

        # Create a unique filename with timestamp
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"{self.csv_prefix}_{ts}.csv"

        keys = self.metrics[0].keys()
        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.metrics)

        logger.info(f"Metrics written to {filename}")

    def run(self):
        """Run the simulation."""
        try:
            self._init_simulation()

            logger.info(f"Running simulation for {self.duration}s (warmup until {self.warmup_time}s)")

            # Log initial state at t=0 before any stepping
            if 0 < self.duration:
                # Collect state and log metrics at t=0
                state = self._collect_traffic_state()
                self.controller.update_state(state)
                action = self.controller.step(state, self.step_length)
                tls_id = "N1"
                sumo_phase_index = self._phase_to_sumo.get(action["phase"], 0)
                traci.trafficlight.setPhase(tls_id, sumo_phase_index)
                self._log_metrics(step=0)

            step = 1
            # Fixed-horizon simulation: continue until duration is reached.
            # We step first, then check whether to log. This gives observations
            # at times 1.0, 2.0, ..., up to the largest time <= duration.
            while True:
                traci.simulationStep()

                time = traci.simulation.getTime()

                # Warmup: skip metrics collection until past warmup_time
                if time < self.warmup_time:
                    continue

                # Stop if we have exceeded the configured horizon.
                # We do not log a row with time > duration.
                if time > self.duration:
                    break

                # Collect traffic state and apply controller
                try:
                    state = self._collect_traffic_state()
                    self.controller.update_state(state)

                    action = self.controller.step(state, self.step_length)
                    tls_id = "N1"  # Traffic light ID from the network
                    sumo_phase_index = self._phase_to_sumo.get(action["phase"], 0)
                    traci.trafficlight.setPhase(tls_id, sumo_phase_index)

                    # Log metrics at this time step
                    self._log_metrics(step)
                except traci.exceptions.FatalTraCIError as e:
                    # If SUMO has closed the connection (simulation ended), break gracefully
                    if "Connection closed by SUMO" in str(e) or "Connection already closed" in str(e):
                        logger.info("SUMO simulation ended (connection closed)")
                        break
                    else:
                        # Re-raise if it's a different FatalTraCIError
                        raise

                step += 1

            # Finalize
            self._write_metrics()

        except Exception as e:
            logger.exception(f"Simulation failed: {e}")
            raise
        finally:
            traci.close()
            logger.info("TraCI simulation closed")


def run_fixed_time_simulation(
    net_file: str,
    route_files: list,
    output_dir: str = "results/raw",
    step_length: float = 1.0,
    duration: int = 3600,
    warmup_time: int = 300,
    gui: bool = False,
    csv_prefix: str = "controller",
    seed: int = 42,
):
    """Convenience function to run a fixed-time simulation.

    Args:
        net_file: Path to SUMO network file
        route_files: List of route files
        output_dir: Output directory for metrics
        step_length: Simulation step length
        duration: Total duration
        warmup_time: Warmup period
        gui: Run with GUI
    """
    runner = SimulationRunner(
        net_file=net_file,
        route_files=route_files,
        output_dir=output_dir,
        step_length=step_length,
        duration=duration,
        warmup_time=warmup_time,
        controller=FixedTimeController(),
        gui=gui,
        csv_prefix=csv_prefix,
        seed=seed,
    )
    runner.run()