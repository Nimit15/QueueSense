import csv
import os
import glob

base_dir = "D:/QueueSense/results/congested_test/"
controllers = ["fixedtime", "actuated", "queuepressure", "queuesense"]
for ctrl in controllers:
    pattern = os.path.join(base_dir, f"{ctrl}_congested_*.csv")
    files = glob.glob(pattern)
    if files:
        latest = max(files, key=os.path.getctime)
        print(f"\n{ctrl.upper()}: {latest}")
        with open(latest, 'r') as f:
            reader = csv.DictReader(f)
            max_ns = 0
            max_ew = 0
            for row in reader:
                ns = int(row['spillback_ns'])
                ew = int(row['spillback_ew'])
                if ns > max_ns:
                    max_ns = ns
                if ew > max_ew:
                    max_ew = ew
            print(f"  Max spillback_ns: {max_ns}, Max spillback_ew: {max_ew}")
    else:
        print(f"\n{ctrl.upper()}: No files found")