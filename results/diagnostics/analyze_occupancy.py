import csv
import numpy as np

edge_files = {
    'QueuePressure': 'edge_log_QueuePressure_seed42.csv',
    'QueueSense': 'edge_log_QueueSense_seed42.csv'
}

for ctrl, fname in edge_files.items():
    path = f'D:/QueueSense/results/diagnostics/{fname}'
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        # Initialize lists
        data = {edge: [] for edge in ['in_north', 'in_east', 'in_west', 'out_north', 'art_east', 'art_west']}
        for row in reader:
            for edge in data.keys():
                occ = float(row[f'{edge}_occupancy'])
                data[edge].append(occ)
    print(f'\n=== {ctrl} ===')
    for edge, occ_list in data.items():
        arr = np.array(occ_list)
        print(f'{edge}: min={arr.min():.6f}, mean={arr.mean():.6f}, 95th={np.percentile(arr,95):.6f}, max={arr.max():.6f}')
        above = np.sum(arr > 0.85)
        print(f'  Steps with occupancy > 0.85: {above} / {len(arr)} ({100*above/len(arr):.2f}%)')