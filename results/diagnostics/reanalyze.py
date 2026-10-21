import csv
import numpy as np

edge_ids = ["in_north", "in_east", "in_west", "out_north", "art_east", "art_west"]

def parse_log(fname):
    path = f'D:/QueueSense/results/diagnostics/{fname}'
    with open(path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)  # skip
        # Reconstruct per-edge groups: each edge has 5 fields: occ, veh, halt, speed, length
        # We'll collect occupancies
        occ_lists = {eid: [] for eid in edge_ids}
        for row in reader:
            # row[0] is time
            idx = 1
            for eid in edge_ids:
                occ = float(row[idx])
                occ_lists[eid].append(occ)
                idx += 5  # skip veh, halt, speed, length
        return occ_lists

for ctrl in ['QueuePressure', 'QueueSense']:
    occ_lists = parse_log(f'edge_log_{ctrl}_seed42.csv')
    print(f'\n=== {ctrl} ===')
    for eid in edge_ids:
        arr = np.array(occ_lists[eid])
        print(f'{eid}: min={arr.min():.6f}, mean={arr.mean():.6f}, 95th={np.percentile(arr,95):.6f}, max={arr.max():.6f}')
        above = np.sum(arr > 0.85)
        print(f'  Steps with occupancy > 0.85: {above} / {len(arr)} ({100*above/len(arr):.2f}%)')