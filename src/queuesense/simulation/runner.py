"""
TraCI Simulation Runner
Runs a SUMO simulation with TraCI, applying a controller and logging metrics.
"""

import os
import logging
from pathlib import Path
from typing import Optional

import traci
import sumolib
from sumolib import checkBinary

from queuesense.state import TrafficState, ApproachState
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
        """
        self.net_file = net_file
        self.route_files = route_files
        self.output_dir = Path(output_dir)
        self.step_length = step_length
        self.duration = duration
        self.warmup_time = warmup_time
        self.controller = controller or FixedTimeController()
        self.gui = gui

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Metrics storage
        self.metrics = []

        logger.info(
            f"SimulationRunner initialized: net={net_file}, routes={route_files}, "
            f"duration={duration}s, warmup={warmup_time}s, gui={gui}"
        )

    def _init_simulation(self):
        """Initialize TraCI simulation."""
        sumo_binary = checkBinary("sumo-gui") if self.gui else checkBinary("sumo")
        traci.start(
            [sumo_binary, "-n", self.net_file, "-r", ",".join(self.route_files), "--step-length", str(self.step_length)],
            label="sim",
        )
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
                stopped_ids = [vid for vid in veh_ids if traci.vehicle.getSpeed(vid) < 0.1]

                queue_count = len(stopped_ids)
                mean_wait = 0.0
                if stopped_ids:
                    wait_times = [traci.vehicle.getWaitingTime(vid) for vid in stopped_ids]
                    mean_wait = sum(wait_times) / len(wait_times)

                # Arrival rate: vehicles entering the approach in the last step
                arrival_rate = traci.edge.getLastStepHaltingNumber(edge_id)

                # Downstream available: check if the receiving edge is not jammed
                # For north/south: receiving edge is the cross street
                # For east/west: receiving edge is the main arterial
                downstream_available = True
                if name in ("north", "south"):
                    # Receiving edge is the main arterial (east-west)
                    downstream_available = traci.edge.getLastStepOccupancy("art_east") < 0.85
                else:
                    # Receiving edge is the cross street (north-south)
                    downstream_available = traci.edge.getLastStepOccupancy("out_north") < 0.85

                # Measurement validity: if edge has vehicles, assume valid
                measurement_valid = len(veh_ids) > 0 or True  # Always valid for now

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
        completed = traci.simulation.getMinExpectedNumber()
        # Queue lengths per approach
        queues = {}
        for name in ["north", "south", "east", "west"]:
            edge_id = {"north": "in_north", "south": "out_north", "east": "in_east", "west": "in_west"}[name]
            veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
            stopped = [vid for vid in veh_ids if traci.vehicle.getSpeed(vid) < 0.1]
            queues[name] = len(stopped)

        # Spillback: if downstream edge occupancy > threshold
        spillback = {
            "north_south": traci.edge.getLastStepOccupancy("art_east") >= 0.85,
            "east_west": traci.edge.getLastStepOccupancy("out_north") >= 0.85,
        }

        # Log to CSV
        self.metrics.append({
            "time": time,
            "completed": completed,
            "queue_north": queues.get("north", 0),
            "queue_south": queues.get("south", 0),
            "queue_east": queues.get("east", 0),
            "queue_west": queues.get("west", 0),
            "spillback_ns": int(spillback["north_south"]),
            "spillback_ew": int(spillback["east_west"]),
        })

        logger.debug(f"Metrics @ t={time}s: queues={queues}, spillback={spillback}")

    def _write_metrics(self):
        """Write metrics to CSV file."""
        import csv

        if not self.metrics:
            logger.warning("No metrics to write")
            return

        # Create a unique filename with timestamp
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"controller_A_{ts}.csv"

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

            step = 0
            while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() <= self.duration:
                traci.simulationStep()

                time = traci.simulation.getTime()

                # Warmup: skip metrics collection
                if time < self.warmup_time:
                    step += 1
                    continue

                # Collect traffic state
                state = self._collect_traffic_state()
                self.controller.update_state(state)

                # Compute and apply controller action
                action = self.controller.step(state, self.step_length)
                # Log the controller action
                logger.info(f"Controller action: {action}")

                # Log metrics
                self._log_metrics(step)

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
    )
    runner.run()
