#!/usr/bin/env python
"""
Diagnostic script for QueueSense bottleneck scenario (seed 42).
Logs edge occupancies, vehicle counts, halting numbers, mean speeds,
and controller decisions for Controller C and Controller D.
"""
import os
import sys
import csv
import traci
import sumolib
from sumolib import checkBinary
from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.base import Phase
from queuesense.controllers.fixed_time import FixedTimeController
from queuesense.controllers.queue_pressure import QueuePressureController
from queuesense.controllers.queuesense import QueueSenseController

NET_FILE = "D:/QueueSense/sumo/network/corridor.net.xml"
ROUTE_FILE = "D:/QueueSense/sumo/routes/bottleneck.rou.xml"
DURATION = 3600
WARMUP = 300
STEP_LENGTH = 1.0
SEED = 42
OUTPUT_DIR = "D:/QueueSense/results/diagnostics"

# Edges of interest
EDGE_IDS = ["in_north", "in_east", "in_west", "out_north", "art_east", "art_west"]

def run_simulation(controller, controller_name):
    """Run simulation with given controller and log metrics."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Start SUMO
    sumo_bin = checkBinary("sumo")
    traci.start([sumo_bin, "-n", NET_FILE, "-r", ROUTE_FILE,
                 "--step-length", str(STEP_LENGTH), "--seed", str(SEED),
                 "--no-step-log", "true"])

    # Get traffic light ID (assumed N1 from network)
    TLS_ID = "N1"

    # Prepare logs
    edge_log_path = os.path.join(OUTPUT_DIR, f"edge_log_{controller_name}_seed{SEED}.csv")
    phase_log_path = os.path.join(OUTPUT_DIR, f"phase_log_{controller_name}_seed{SEED}.csv")

    with open(edge_log_path, 'w', newline='') as ef, \
         open(phase_log_path, 'w', newline='') as pf:
        edge_writer = csv.writer(ef)
        phase_writer = csv.writer(pf)

        # Edge log header
        edge_header = ["time"] + \
                      [f"{e}_occupancy" for e in EDGE_IDS] + \
                      [f"{e}_vehicle_number" for e in EDGE_IDS] + \
                      [f"{e}_halting_number" for e in EDGE_IDS] + \
                      [f"{e}_mean_speed" for e in EDGE_IDS] + \
                      [f"{e}_length" for e in EDGE_IDS]
        edge_writer.writerow(edge_header)

        # Phase log header
        phase_header = ["time", "phase_index", "phase_state", "controller_phase", "controller_reason"]
        phase_writer.writerow(phase_header)

        step = 0
        while True:
            traci.simulationStep()
            time = traci.simulation.getTime()

            if time < WARMUP:
                continue
            if time > DURATION:
                break

            # Collect edge data
            edge_row = [time]
            for eid in EDGE_IDS:
                try:
                    occ = traci.edge.getLastStepOccupancy(eid)
                    veh = traci.edge.getLastStepVehicleNumber(eid)
                    halt = traci.edge.getLastStepHaltingNumber(eid)
                    speed = traci.edge.getLastStepMeanSpeed(eid)
                    # Get edge length from sumolib
                    if hasattr(traci.edge, 'getLength'):
                        length = traci.edge.getLength(eid)
                    else:
                        net = sumolib.net.readNet(NET_FILE)
                        length = net.getEdge(eid).getLength()
                except traci.TraCIException:
                    occ = veh = halt = speed = length = 0.0
                edge_row.extend([occ, veh, halt, speed, length])
            edge_writer.writerow(edge_row)

            # Build TrafficState for controller
            approaches = {}
            all_valid = True
            # Map approach to incoming edge
            approach_edge_map = {
                "north": "in_north",
                "south": "out_north",  # Note: south is exit edge, but we keep as per original
                "east": "in_east",
                "west": "in_west"
            }
            for name, edge_id in approach_edge_map.items():
                try:
                    veh_ids = traci.edge.getLastStepVehicleIDs(edge_id)
                    stopped_ids = [vid for vid in veh_ids if traci.vehicle.getSpeed(vid) < 0.1]
                    queue_count = len(stopped_ids)
                    mean_wait = 0.0
                    if stopped_ids:
                        wait_times = [traci.vehicle.getWaitingTime(vid) for vid in stopped_ids]
                        mean_wait = sum(wait_times) / len(wait_times)
                    arrival_rate = traci.edge.getLastStepHaltingNumber(edge_id)
                    # Downstream available: check if the receiving edge is not jammed
                    downstream_available = True
                    if name in ("north", "south"):
                        downstream_available = traci.edge.getLastStepOccupancy("art_east") < 0.85
                    else:
                        downstream_available = traci.edge.getLastStepOccupancy("out_north") < 0.85
                    measurement_valid = True
                except Exception:
                    queue_count = mean_wait = arrival_rate = 0.0
                    downstream_available = False
                    measurement_valid = False
                    all_valid = False
                approaches[name] = ApproachState(
                    queue_count=float(queue_count),
                    mean_wait_seconds=float(mean_wait),
                    arrival_rate=float(arrival_rate),
                    downstream_available=downstream_available,
                    measurement_valid=measurement_valid
                )
            state = TrafficState(timestamp=time, approaches=approaches, all_valid=all_valid)

            # Update controller and get action
            controller.update_state(state)
            action = controller.step(state, STEP_LENGTH)

            # Apply action to SUMO
            sumo_phase_index = controller._phase_to_sumo.get(action["phase"], 0) if hasattr(controller, '_phase_to_sumo') else 0
            # Fallback mapping if not present
            if not hasattr(controller, '_phase_to_sumo'):
                # Default mapping from base
                phase_map = {Phase.NORTH_SOUTH: 0, Phase.YELLOW_CLEARANCE: 1, Phase.EAST_WEST: 2, Phase.ALL_RED: 3}
                sumo_phase_index = phase_map.get(action["phase"], 0)
            traci.trafficlight.setPhase(TLS_ID, sumo_phase_index)

            # Get actual phase state from SUMO
            try:
                phase_state = traci.trafficlight.getRedYellowGreenState(TLS_ID)
            except traci.TraCIException:
                phase_state = "unknown"

            # Phase log
            phase_writer.writerow([time, sumo_phase_index, phase_state,
                                action["phase"].name if hasattr(action["phase"], 'name') else str(action["phase"]),
                                action["reason"]])

    traci.close()
    print(f"Finished {controller_name} simulation. Logs written to {OUTPUT_DIR}")

def main():
    print("Running diagnostic for bottleneck seed 42...")
    # Run Controller C (QueuePressure)
    print("Running Controller C (QueuePressure)...")
    run_simulation(QueuePressureController(alpha=0.5, beta=0.3, gamma=0.2), "QueuePressure")
    # Run Controller D (QueueSense)
    print("Running Controller D (QueueSense)...")
    run_simulation(QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85), "QueueSense")

if __name__ == "__main__":
    main()