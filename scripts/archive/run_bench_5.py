#!/usr/bin
python3
import os, sys
sys.path.insert(0, r'D:\QueueSense\src')
os.chdir('D:\QueueSense')

from queuesense.benchmark.runner import
from queuesense.controllers import
import time

print('Imports OK')

# Build route files manually
route_files = {
    'light': ['D:/QueueSense/src/queuesense/benchmark/light.rou.xml'],
    'bottle': ['D:/QueueSense/src/queuesense/benchmark/bottle.rou.xml'],
    'surge': ['D:/QueueSense/src/queuesense/benchmark/surge.rou.xml'],
    'uneven': ['D:/QueueSense/src/queuesense/benchmark/uneven.rou.xml'],
}

print('Route files: OK')

# Create runner
output_dir = 'results/benchmark_valid'
os.makedirs(output_dir, exist=True)

runner =
Runner(
    net_file='D:/QueueSense/src/queuesense/simulation/corridor.net.xml',
    route_files=route_files,
    output_dir=output_dir,
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=[42, 43, 44, 45, 46, 47, 48, 49, 50, 51],
    scenarios=['light', 'bottle', 'surge', 'uneven'],
    gui=False,
)

print('Runner created, running...')
start = time.time()
results = runner.run_benchmark()
summary = runner
write
mary)
elapsed = time.time() - start

print('Summary:')
print('  Total runs:', summary.get('total_runs', 0))
print('  Successful:', summary.get('successful_runs', 0))
print('  Failed:', summary.get('__runs', 0))
print('  Time:', round(elelapsed, 1
' seconds')

# List output files
import csv
output_files = sorted(os.listdir(output_dir))
print()
print('Output files:')
for f in output_files:
    if f
'.csv'):
        with open(os.path.join(output_dir, f)) as fh:
            reader = csv.DictReader(fh)
            rows = list
        )
    times = [float(r['time']) for r in rows]
    arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
    first = rows[0] if rows else {}
    last = rows[-1] if rows else {}
    print('  ' + f + ':': ' + str(len(rows)) + ' rows, time ' + str(min(times)) + '-''- ' + str
(max(times)) + ', arrived ' + str
(max(arrived)) + ', first=' + str
(first.get('time', '?')) + ', last=' + str
(last(last
last.get('time', '?'))