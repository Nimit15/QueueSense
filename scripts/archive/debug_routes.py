#!/usr/bin/env python3
"""
Debug what routes vehicles are taking and where they spend time.
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

# Monitor where vehicles are spending time
try:
    print("Step\tTime\tVeh_ID\tRoute_ID\tEdge_ID\tSpeed")
    vehicle_first_seen = {}
    for step in range(200):
        traci.simulationStep()
        if step % 20 == 0:  # Less frequent output
            time = traci.simulation.getTime()
            # Get all vehicles in the simulation
            veh_ids = traci.vehicle.getIDList()
            for vid in veh_ids[:10]:  # Just first 10 vehicles
                try:
                    route_id = traci.vehicle.getRouteID(vid)
                    edge_id = traci.vehicle.getRoadID(vid)
                    speed = traci.vehicle.getSpeed(vid)
                    if vid not in vehicle_first_seen:
                        vehicle_first_seen[vid] = step
                        print(f"{step}\t{time:.1f}\t{vid}\t{route_id}\t{edge_id}\t{speed:.1f}")
                except:
                    pass
finally:
    traci.close()