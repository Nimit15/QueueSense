import os

os.chdir('D:/QueueSense')
from pathlib import Path
sys_path = str(Path('src'))
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)

from queuesense.benchmark.runner import

route_files = {}
for scenario in ['light', 'bottleneck]:
    route_path = f'sumo/{scenario}.rou.xml'
    if os.path.exists(route_path):
        route_files[scenario] = [route_path]

output_dir = Path('results/benchmark_valid')
output_dir.mkdir(parents=True, exist
=True

runner =
Runner(
    net_file='sumo/network/corridor.net.xml',
    route_files=route_files,
    output_dir=output_dir,
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=[42, 43, 44, 45],
    scenarios=list(route_files.keys()),
    gui=False,
)

results = runner.run_benchmark()
summary = runner
write
mary)

print(f\"Total runs: {summary.get('total_runs', 0)}\")
print(f\"successful_runs: {summary.get('successful_runs', 0)}\")
print(f\"failed_runs: {summary.get('
_runs', 0)}\")

import csv
for f in sorted(output_dir.glob('*.csv')):
    with open(f) as fh:
        reader = csv.DictReader(fh)
        rows = list
)
    times = [float(r['time']) for r in rows]
    arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
    print(f\"  {f.name}: {len(rows)} rows, time {min(times):.0f}-{max(times):.0f}, arrived={max(arrived)}\")