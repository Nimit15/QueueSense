import csv

csv_file = "D:/QueueSense/results/congested_test/queuesense_congested_20261015_000103.csv"
with open(csv_file, 'r') as f:
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
    print(f"Max spillback_ns: {max_ns}")
    print(f"Max spillback_ew: {max_ew}")