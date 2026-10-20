import csv
import os

def read_csv_columns(csv_file, columns):
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        data = {col: [] for col in columns}
        for row in reader:
            for col in columns:
                data[col].append(float(row[col]))
        return data

base_dir = "D:/QueueSense/results/congested_test/"
controllers = [
    ("FixedTime", "fixedtime_congested_20261014_235847.csv"),
    ("Actuated", "actuated_congested_20261014_235928.csv"),
    ("QueuePressure", "queuepressure_congested_20261015_000014.csv"),
    ("QueueSense", "queuesense_congested_20261015_000103.csv")
]

columns = ['queue_north', 'queue_south', 'queue_east', 'queue_west']

for name, filename in controllers:
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        data = read_csv_columns(path, columns)
        avg_north = sum(data['queue_north'])/len(data['queue_north'])
        avg_south = sum(data['queue_south'])/len(data['queue_south'])
        avg_east = sum(data['queue_east'])/len(data['queue_east'])
        avg_west = sum(data['queue_west'])/len(data['queue_west'])
        print(f"{name}:")
        print(f"  Avg queue north: {avg_north:.2f}")
        print(f"  Avg queue south: {avg_south:.2f}")
        print(f"  Avg queue east: {avg_east:.2f}")
        print(f"  Avg queue west: {avg_west:.2f}")
        total_avg = avg_north + avg_south + avg_east + avg_west
        print(f"  Total avg queue: {total_avg:.2f}")
        print()
    else:
        print(f"{name}: File not found")