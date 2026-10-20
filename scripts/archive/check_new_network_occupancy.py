#!/usr/bin/env python3
"""
Check occupancies on key edges with the new network (N2 as traffic light).
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

# Monitor key occupancies
try:
    print("Step\tTime\tart_east\tout_north\tin_east\tin_west\tin_north")
    for step in range(600):  # Run for 10 minutes
        traci.simulationStep()
        if step % 10 == 0:
            time = traci.simulation.getTime()
            try:
                art_east = traci.edge.getLastStepOccupancy("art_east")
                out_north = traci.edge.getLastStepOccupancy("out_north")
                in_east = traci.edge.getLastStepOccupancy("in_east")
                in_west = traci.edge.getLastStepOccupancy("in_west")
                in_north = traci.edge.getLastStepOccupancy("in_north")
                print(f"{step}\t{time:.1f}\t{art_east:.3f}\t{out_north:.3f}\t{in_east:.3f}\t{in_west:.3f}\t{in_north:.3f}")
            except Exception as e:
                print(f"{step}\t{time:.1f}\tError\tError\tError\tError\tError")
finally:
    traci.close()