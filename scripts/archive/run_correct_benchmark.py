#!/usr/bin/env python3
"""
Run the CORRECT QueueSense benchmark.

This script runs all 4 controllers across all 5 scenarios with all 10 seeds.
Expected output: 200 CSV files with ~3302 rows each (time 0-3600s)
"""

import os
import sys
from pathlib import Path

# Setup path
base_dir = Path(__file__).parent.resolve()
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

print("QueueSense Benchmark Runner")
print("=" * 60)

# Configuration
NET_FILE = "sumo/network/corridor.net.xml"
ROUTE_DIR = "sumo/routes/benchmark"

# All scenarios with existing route files
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]

# All controller IDs
CONTROLLERS = ["A", "B", "C", "D"]

# All 10 seeds
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]

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
output_dir = base_dir / "results" / "benchmark_final"

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
for csv_file in sorted(csv_files)[:5]:
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if rows:
            times = [float(r['time']) for r in rows]
            arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
            print(f"  {csv_file.name}: {len(rows)} rows, time {min(times):.0f}-{max(times):.0f}s, arrived={max(arrived)}")