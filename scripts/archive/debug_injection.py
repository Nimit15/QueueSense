#!/usr/bin/env python3
"""
Debug vehicle injection and see what's happening on art_east.
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

# Monitor vehicle numbers and art_east occupancy
try:
    print("Step\tTime\tLoaded\tArtEast_Occ\tOutNorth_Occ\tVehicles_on_art_east")
    for step in range(1000):
        traci.simulationStep()
        if step % 10 == 0:
            time = traci.simulation.getTime()
            loaded = traci.simulation.getLoadedNumber()
            try:
                art_east_occ = traci.edge.getLastStepOccupancy("art_east")
                out_north_occ = traci.edge.getLastStepOccupancy("out_north")
                # Get vehicles actually on art_east
                veh_ids = traci.edge.getLastStepVehicleIDs("art_east")
                num_veh = len(veh_ids)
                print(f"{step}\t{time:.1f}\t{loaded}\t{art_east_occ:.3f}\t{out_north_occ:.3f}\t{num_veh}")
            except Exception as e:
                print(f"{step}\t{time:.1f}\t{loaded}\tError\tError\tError")
finally:
    traci.close()