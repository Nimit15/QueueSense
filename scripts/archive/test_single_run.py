#!/usr/bin/env python3
"""Quick test: Run one controller/scenario/seed combo to verify the pipeline."""

import os
import sys
import time
from pathlib import Path

# Setup
base_dir = Path("D:/QueueSense")
sys.path.insert(0, str(base_dir / "src"))
os.chdir(base_dir)

from queuesense.benchmark.runner import BenchmarkRunner

# Minimal config - just one scenario, one controller, one seed
route_files = {
    "light": ["sumo/routes/benchmark/light.rou.xml"],
}
# Make paths absolute-ish - they need to be relative to cwd or absolute

print("Initializing minimal benchmark runner...")
runner = BenchmarkRunner(
    net_file=r"D:\QueueSense\sumo\network\corridor.net.xml",
    route_files=route_files,
    output_dir="results/test_valid",
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=[42],
    scenarios=["light"],
    gui=False,
)

print("Running single test...")
start = time.time()
results = runner.run_benchmark()
elapsed = time.time() - start

print(f"\nResults: {len(results)} runs completed in {elapsed:.1f}s")
for r in results:
    print(f"  {r.get('scenario')}/{r.get('controller')}/seed{r.get('seed')}: "
          f"status={r.get('status')}, time={r.get('time')}, "
          f"arrived={r.get('arrived_cumulative')}, remaining={r.get('remaining_expected')}")

# Verify output
output_dir = Path("results/test_valid")
csv_files = list(output_dir.rglob("*.csv"))
print(f"\nCSV files created: {len(csv_files)}")
if csv_files:
    import csv
    f = sorted(csv_files)[0]
    with open(f) as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        times = [float(r['time']) for r in rows]
        arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
        print(f"  {f.name}: {len(rows)} rows, time {min(times):.0f}-{max(times):.0f}s, "
              f"arrived={max(arrived)}")