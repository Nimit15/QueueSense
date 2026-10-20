#!/usr/bin/env python3
"""
Run a diagnostic benchmark: seed=42, scenarios light and balanced, all 4 controllers.
Output to results/diagnostics/
"""

import os
import sys
from pathlib import Path

# Setup path
base_dir = Path(__file__).parent.resolve()
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

print("QueueSense Diagnostic Benchmark")
print("=" * 60)

# Configuration
NET_FILE = "sumo/network/corridor.net.xml"
ROUTE_DIR = "sumo/routes/benchmark"

# Scenarios for diagnostic
SCENARIOS = ["light", "balanced"]

# All controller IDs
CONTROLLERS = ["A", "B", "C", "D"]

# Single seed for diagnostic
SEEDS = [42]

# Build route_files dict
route_files = {}
for scenario in SCENARIOS:
    route_path = base_dir / ROUTE_DIR / f"{scenario}.rou.xml"
    if route_path.exists():
        route_files[scenario] = [str(route_path)]
        print(f"Found route: {scenario} -> {route_path}")
    else:
        print(f"MISSING route: {scenario} -> {route_path}")

if not route_files:
    print("ERROR: No route files found!")
    sys.exit(1)

# Check net file
net_path = base_dir / NET_FILE
if not net_path.exists():
    print(f"ERROR: Network file not found: {net_path}")
    sys.exit(1)
print(f"Network file: {net_path}")

print()
print(f"Scenarios: {list(route_files.keys())}")
print(f"Controllers: {CONTROLLERS}")
print(f"Seeds: {SEEDS}")
print(f"Total runs: {len(route_files) * len(CONTROLLERS) * len(SEEDS)}")
print()

# Import after path setup
from queuesense.benchmark.runner import BenchmarkRunner

# Create runner
output_dir = base_dir / "results" / "diagnostics"

runner = BenchmarkRunner(
    net_file=str(net_path),
    route_files=route_files,
    output_dir=str(output_dir),
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=SEEDS,
    scenarios=list(route_files.keys()),
    gui=False,
)

# Run benchmark
print("Starting benchmark...")
import time
start_time = time.time()

results = runner.run_benchmark()
summary = runner.generate_summary(results)
runner.write_summary(summary)

elapsed = time.time() - start_time

print()
print("=" * 60)
print("BENCHMARK COMPLETE")
print("=" * 60)
print(f"Total runs: {summary.get('total_runs', 0)}")
print(f"Successful: {summary.get('successful_runs', 0)}")
print(f"Failed: {summary.get('failed_runs', 0)}")
print(f"Elapsed time: {elapsed:.1f} seconds")
print(f"Output directory: {output_dir}")

# Verify output files
csv_files = list(output_dir.rglob("*.csv"))
print(f"CSV files created: {len(csv_files)}")

# Show a few sample files
import csv
for csv_file in sorted(csv_files)[:10]:
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if rows:
            times = [float(r['time']) for r in rows]
            arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
            print(f"  {csv_file.name}: {len(rows)} rows, time {min(times):.0f}-{max(times):.0f}s, arrived={max(arrived)}")

# Additionally, we want to report arrived_cumulative, mean waiting time, and phase switch counts.
# However, the current CSV does not have waiting time or phase switch counts.
# We might need to look at the simulation runner for more details, but for now we can note that.
# Let's at least show the arrived_cumulative for each run.

print("\nDetailed results per run:")
for scenario in SCENARIOS:
    for controller in CONTROLLERS:
        for seed in SEEDS:
            # Find the CSV file for this combination
            pattern = f"{controller}_seed{seed}_*.csv"
            files = list((output_dir / scenario).glob(pattern))
            if files:
                latest = max(files, key=lambda x: x.stat().st_mtime)
                with open(latest) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        last_row = rows[-1]
                        arrived = int(last_row.get('arrived_cumulative', 0))
                        # We don't have waiting time or phase switches in the current output.
                        print(f"{scenario} Controller {controller} seed {seed}: arrived={arrived}")
            else:
                print(f"{scenario} Controller {controller} seed {seed}: NO FILE FOUND")