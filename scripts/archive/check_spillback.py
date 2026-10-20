import csv
import os

def get_max_spillback(csv_file, column):
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        max_val = 0
        for row in reader:
            val = int(row[column])
            if val > max_val:
                max_val = val
        return max_val

base_dir = "D:/QueueSense/results/congested_test/"
controllers = [
    ("FixedTime", "fixedtime_congested_20261014_235847.csv"),
    ("Actuated", "actuated_congested_20261014_235928.csv"),
    ("QueuePressure", "queuepressure_congested_20261015_000014.csv"),
    ("QueueSense", "queuesense_congested_20261015_000103.csv")
]

print("Controller\tMax Spillback NS\tMax Spillback EW")
print("-" * 50)
for name, filename in controllers:
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        max_ns = get_max_spillback(path, 'spillback_ns')
        max_ew = get_max_spillback(path, 'spillback_ew')
        print(f"{name}\t{max_ns}\t\t{max_ew}")
    else:
        print(f"{name}\tFile not found")