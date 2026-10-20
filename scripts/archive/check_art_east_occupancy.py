#!/usr/bin/env python3
"""
Check art_east occupancy during simulation to see if spillback threshold is reached.
"""

import traci
import sumolib
from sumolib import checkBinary
import xml.etree.ElementTree as ET

net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
route_file = "D:/QueueSense/sumo/routes/bottleneck_congested.rou.xml"

# Start simulation
sumo_binary = checkBinary("sumo")
traci.start([sumo_binary, "-n", net_file, "-r", route_file,
             "--step-length", "1.0", "--seed", "42"],
            label="sim")

# We'll just run and print occupancies
try:
    max_art_east = 0.0
    max_out_north = 0.0
    for step in range(500):  # Run longer to see if congestion builds
        traci.simulationStep()
        if step % 10 == 0:
            time = traci.simulation.getTime()
            try:
                art_east_occ = traci.edge.getLastStepOccupancy("art_east")
                out_north_occ = traci.edge.getLastStepOccupancy("out_north")
                if art_east_occ > max_art_east:
                    max_art_east = art_east_occ
                if out_north_occ > max_out_north:
                    max_out_north = out_north_occ
                if step % 50 == 0:  # Print every 50 steps
                    print(f"Time {time}: art_east={art_east_occ:.3f}, out_north={out_north_occ:.3f}")
            except Exception as e:
                print(f"Error reading occupancy: {e}")
    print(f"\nMaximum occupancies:")
    print(f"  art_east: {max_art_east:.3f}")
    print(f"  out_north: {max_out_north:.3f}")
    print(f"  Spillback threshold: 0.85")
    print(f"  art_east exceeded threshold: {max_art_east >= 0.85}")
    print(f"  out_north exceeded threshold: {max_out_north >= 0.85}")
finally:
    traci.close()