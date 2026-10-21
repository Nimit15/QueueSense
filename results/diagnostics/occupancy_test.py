import traci
import sumolib
from sumolib import checkBinary
import csv

NET_FILE = "D:/QueueSense/sumo/network/corridor.net.xml"
ROUTE_FILE = "D:/QueueSense/sumo/routes/bottleneck.rou.xml"

sumo_bin = checkBinary("sumo")
traci.start([sumo_bin, "-n", NET_FILE, "-r", ROUTE_FILE,
             "--step-length", "1.0", "--seed", "42",
             "--no-step-log", "true"])

# Wait until after warmup
for _ in range(300):
    traci.simulationStep()

edges = ["in_north", "in_east", "in_west", "out_north", "art_east", "art_west"]
occ_data = {e: [] for e in edges}
for step in range(300):  # log 300 steps after warmup
    traci.simulationStep()
    for eid in edges:
        occ = traci.edge.getLastStepOccupancy(eid)
        occ_data[eid].append(occ)

traci.close()

for eid, vals in occ_data.items():
    print(f"{eid}: min={min(vals):.6f}, mean={sum(vals)/len(vals):.6f}, max={max(vals):.6f}")
    above = sum(1 for v in vals if v > 0.85)
    print(f"  >0.85 steps: {above}/{len(vals)} ({100*above/len(vals):.2f}%)")