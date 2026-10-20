#!/usr/bin/env python3
"""
Check detailed statistics on art_east to understand queue formation.
"""

import traci
import sumolib
from sumolib import checkBinary

net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
route_file = "D:/QueueSense/sumo/routes/bottleneck_congested.rou.xml"

# Start simulation
sumo_binary = checkBinary("sumo")
traci.start([sumo_binary, "-n", net_file, "-r", route_file,
             "--step-length", "1.0", "--seed", "42"],
            label="sim")

# Monitor detailed statistics
try:
    print("Step\tTime\tOccupancy\tVeh_Length\tVeh_Count\tMean_Speed\tJam_Length_Veh")
    vehicle_length = 7.5  # typical vehicle length in meters, SUMO default
    for step in range(1800):  # Run for 30 minutes
        traci.simulationStep()
        if step % 30 == 0:  # Every 30 seconds
            time = traci.simulation.getTime()
            try:
                occupancy = traci.edge.getLastStepOccupancy("art_east")
                veh_ids = traci.edge.getLastStepVehicleIDs("art_east")
                veh_count = len(veh_ids)
                mean_speed = traci.edge.getLastStepMeanSpeed("art_east")
                # Calculate jam length in vehicles
                jam_length_m = occupancy * traci.lane.getLength("art_east_0") if veh_count > 0 else 0
                jam_length_veh = jam_length_m / vehicle_length if vehicle_length > 0 else 0
                print(f"{step}\t{time:.1f}\t{occupancy:.3f}\t{veh_count * vehicle_length:.1f}\t{veh_count}\t{mean_speed:.1f}\t{jam_length_veh:.1f}")
            except Exception as e:
                print(f"{step}\t{time:.1f}\tError\tError\tError\tError\tError")
finally:
    traci.close()